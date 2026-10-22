"""Backend-agnostic pieces of the AI assistant.

The assistant answers a historian's natural-language question by writing SQL
against the catalogue database. Everything that is independent of *which* LLM
runs the conversation lives here:

  * schema introspection (built from the Django models, so it never goes stale)
  * SQL safety checks and execution
  * the prompt
  * the agent loop itself (`run_sql_agent`)

Concrete backends supply only a `chat(conversation) -> str` callable:
`ai_tools_ollama` (local, default) and `ai_tools_openai` (paid API).
"""

import json
import re
import time
from datetime import datetime, date, time as dt_time

from django.apps import apps
from django.conf import settings
from django.db import connection

from .models import Manuscripts

# Never expose these to the assistant: Django internals plus our own
# bookkeeping tables, which hold no historical data. The "improve our data"
# form stores visitors' e-mail addresses, and anonymous visitors may use the
# assistant on some instances.
FORBIDDEN_TABLE_PREFIXES = (
    'auth_', 'django_', 'etl_', 'indexerapp_aiquery',
    'indexerapp_improveourdataentry', 'indexerapp_profile',
)
FORBIDDEN_TABLES = ('user_openai_api_key',)

# Hard cap on rows handed back to the browser (and to the model).
MAX_RESULT_ROWS = 2000
# Rows of a result set that get quoted back into the conversation. The model
# only needs a sample to see the query worked; full rows go to the user.
MAX_ROWS_IN_CONVERSATION = 25


def _is_forbidden_table(table_name):
    name = table_name.lower()
    return name.startswith(FORBIDDEN_TABLE_PREFIXES) or name in FORBIDDEN_TABLES


# --------------------------------------------------------------------------
# Schema description
# --------------------------------------------------------------------------

def _column_type(field):
    """Short, SQL-ish type description for a Django field."""
    # A FK column has the type of the column it points at, not "foreignkey".
    if field.remote_field is not None:
        return _column_type(field.target_field)

    internal = field.get_internal_type()
    simple = {
        'AutoField': 'int',
        'BigAutoField': 'bigint',
        'IntegerField': 'int',
        'BigIntegerField': 'bigint',
        'PositiveIntegerField': 'int',
        'PositiveSmallIntegerField': 'int',
        'SmallIntegerField': 'int',
        'FloatField': 'float',
        'BooleanField': 'bool',
        'DateField': 'date',
        'DateTimeField': 'datetime',
        'TimeField': 'time',
        'TextField': 'text',
        'UUIDField': 'char(36)',
        'JSONField': 'json',
    }
    if internal in simple:
        return simple[internal]
    if internal == 'DecimalField':
        return f'decimal({field.max_digits},{field.decimal_places})'
    if internal in ('CharField', 'ImageField', 'FileField', 'EmailField', 'URLField', 'SlugField'):
        return f'varchar({field.max_length})'
    return internal.replace('Field', '').lower()


def _relational_models():
    """Concrete indexerapp models whose tables the assistant may query."""
    models = []
    for model in apps.get_app_config('indexerapp').get_models():
        if model._meta.abstract or model._meta.proxy:
            continue
        if _is_forbidden_table(model._meta.db_table):
            continue
        models.append(model)
    return sorted(models, key=lambda m: m._meta.db_table)


def _describe_field(field):
    """One schema line for a concrete (non-m2m) field, or None to skip it."""
    column = field.column
    line = f'  {column}: {_column_type(field)}'

    notes = []
    if field.primary_key:
        notes.append('PK')
    if field.remote_field is not None:
        target = field.target_field
        notes.append(f'-> {target.model._meta.db_table}.{target.column}')
    if getattr(field, 'choices', None):
        pairs = ', '.join(
            f'{value}' if str(value) == str(label) else f'{value}={label}'
            for value, label in field.choices
        )
        notes.append(f'one of: {pairs}')

    if notes:
        line += '  # ' + '; '.join(notes)
    return line


def _m2m_through_tables(model):
    """Auto-created link tables of a model's many-to-many fields."""
    return [
        field.remote_field.through._meta.db_table
        for field in model._meta.many_to_many
        if field.remote_field.through._meta.auto_created
    ]


def _non_empty_tables(tables):
    """The tables among `tables` that hold at least one row, in one query.

    EXISTS stops at the first row, so each table costs one index probe rather
    than a COUNT(*): all ~70 tables take a fraction of a second.
    """
    if not tables:
        return set()
    quote = connection.ops.quote_name
    sql = ' UNION ALL '.join(
        f'SELECT %s, EXISTS(SELECT 1 FROM {quote(table)})' for table in tables
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, list(tables))
        return {name for name, filled in cursor.fetchall() if filled}


def _describe_model(model, shown_tables):
    """Schema block of one table. Foreign keys and link tables leading to a
    table outside `shown_tables` (forbidden or empty) are left out."""
    meta = model._meta
    lines = [f'TABLE {meta.db_table}']

    for field in meta.concrete_fields:
        if field.remote_field is not None and (
            field.target_field.model._meta.db_table not in shown_tables
        ):
            continue
        lines.append(_describe_field(field))

    # Many-to-many link tables are queryable too and are usually where the
    # "who wrote this down" style questions end up.
    for field in meta.many_to_many:
        through = field.remote_field.through
        if through._meta.auto_created is False or through._meta.db_table not in shown_tables:
            continue
        columns = [
            f'{f.column} -> {f.target_field.model._meta.db_table}.{f.target_field.column}'
            for f in through._meta.concrete_fields
            if f.remote_field is not None
        ]
        lines.append(f'  # m2m {field.name} via {through._meta.db_table}({"; ".join(columns)})')

    return '\n'.join(lines)


# Empty tables are left out of the schema: an instance that uses few of them
# (eCLLA fills 15 of ~70) would otherwise send the model looking in tables that
# cannot answer anything. Rebuilt every few minutes, so a table that gets its
# first rows shows up without a restart.
SCHEMA_CACHE_SECONDS = 600
_schema_cache = None  # (built at, shown tables, schema text)


def _schema():
    global _schema_cache
    if _schema_cache is None or time.monotonic() - _schema_cache[0] > SCHEMA_CACHE_SECONDS:
        models = _relational_models()
        tables = [m._meta.db_table for m in models]
        tables += [t for m in models for t in _m2m_through_tables(m) if not _is_forbidden_table(t)]
        shown = _non_empty_tables(tables)
        text = '\n\n'.join(
            _describe_model(m, shown) for m in models if m._meta.db_table in shown
        )
        _schema_cache = (time.monotonic(), shown, text)
    return _schema_cache


def get_shown_tables():
    """Tables (including link tables) that appear in the schema description."""
    return _schema()[1]


def get_schema_description():
    """Compact schema of the non-empty tables, generated from the models.

    Generating it (rather than hand-maintaining it in the prompt) is what keeps
    the assistant working after schema changes — the uuid foreign-key migration
    would otherwise have silently broken every generated join.
    """
    return _schema()[2]


def get_table_list():
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES;")
        tables = [row[0] for row in cursor.fetchall()]
    return '\n'.join(t for t in tables if not _is_forbidden_table(t))


# The list is pasted into the system prompt, so it must stay small enough that
# the whole prompt fits the model's context window (32k tokens on our Ollama)
# with room left for the conversation. ~0.37 tokens per char on real data.
MANUSCRIPT_LIST_MAX_CHARS = 30000


def get_all_manuscript_names(projectId):
    queryset = Manuscripts.objects.all()

    if projectId != 0:
        queryset = queryset.filter(ms_projects__project_uuid__id=projectId)

    # Start with headers
    csv_data = '"id","name","rism_id","foreign_id","shelf_mark"\n'

    # Iterate over the queryset to create CSV rows
    for manuscript in queryset:
        row = f'"{manuscript.id}","{manuscript.name}","{manuscript.rism_id or ""}","{manuscript.foreign_id or ""}","{manuscript.shelf_mark or ""}"\n'
        csv_data += row

    return csv_data


def manuscript_list_prompt_section(projectId):
    """Manuscript list for the prompt, shrunk step by step to fit the budget.

    1. every column (id, name, rism_id, foreign_id, shelf_mark)
    2. without the id: the SQL joins on uuid, the historian speaks in names
    3. names only
    4. names only, cut after the last row that fits
    """
    queryset = Manuscripts.objects.all()
    if projectId != 0:
        queryset = queryset.filter(ms_projects__project_uuid__id=projectId)
    rows = list(queryset.values_list('id', 'name', 'rism_id', 'foreign_id', 'shelf_mark'))

    def render(columns, header, limit=None):
        body = ''.join(
            ','.join(f'"{row[c] or ""}"' for c in columns) + '\n' for row in rows[:limit]
        )
        return f'{header}\n{body}'

    tiers = (
        ((0, 1, 2, 3, 4), '"id","name","rism_id","foreign_id","shelf_mark"'),
        ((1, 2, 3, 4), '"name","rism_id","foreign_id","shelf_mark"'),
        ((1,), '"name"'),
    )
    intro = (
        "The user may refer to these manuscripts by name, RISM id or foreign id. "
        "Filter on the matching manuscript when they do:\n"
    )
    for columns, header in tiers:
        text = render(columns, header)
        if len(text) <= MANUSCRIPT_LIST_MAX_CHARS:
            return intro + text

    names_only = tiers[-1]
    shown = len(render(*names_only, limit=0))
    for count, row in enumerate(rows):
        shown += len(f'"{row[1] or ""}"\n')
        if shown > MANUSCRIPT_LIST_MAX_CHARS:
            break
    else:
        count = len(rows)
    return (
        f"The user may refer to manuscripts by name, RISM id, foreign id or shelf mark. "
        f"Only the first {count} of {len(rows)} manuscript names are listed below; for any "
        "other, look the manuscript up in `manuscripts` with an exploratory query "
        "(e.g. WHERE `name` LIKE '%...%') before filtering on it.\n"
        + render(*names_only, limit=count)
    )


# --------------------------------------------------------------------------
# SQL execution
# --------------------------------------------------------------------------

_COMMENT_RE = re.compile(r'(--[^\n]*\n)|(/\*.*?\*/)', re.DOTALL)
_ALLOWED_STARTS = ('select', 'with', 'describe', 'desc', 'show', 'explain')
# Mutating verbs. `replace` is deliberately matched only in its statement form
# (`REPLACE INTO`) so the REPLACE() string function stays usable.
_FORBIDDEN_RE = re.compile(
    r'\b(insert\s+into|update\s+\S|delete\s+from|drop\s+|alter\s+|create\s+|truncate\s+|'
    r'replace\s+into|grant\s+|revoke\s+|into\s+outfile|into\s+dumpfile|load_file|'
    r'benchmark\s*\(|sleep\s*\()',
    re.IGNORECASE,
)
_TABLE_REF_RE = re.compile(r'\b(?:from|join|into|update)\s+`?([a-zA-Z0-9_]+)`?', re.IGNORECASE)


def _strip_sql_comments(query):
    return _COMMENT_RE.sub(' ', query + '\n')


def check_sql_is_safe(query):
    """Raise if `query` is anything other than a single read-only statement."""
    bare = _strip_sql_comments(query).strip()

    # A trailing semicolon is fine; anything after it is a second statement.
    if ';' in bare.rstrip().rstrip(';'):
        raise Exception("Only a single SQL statement is allowed.")

    if not bare.lower().startswith(_ALLOWED_STARTS):
        raise Exception(
            "Niedozwolone operacje na bazie danych. Konsekwencje będą wyciągnięte."
        )

    if _FORBIDDEN_RE.search(bare):
        raise Exception(
            "Niedozwolone operacje na bazie danych. Konsekwencje będą wyciągnięte."
        )

    for table in _TABLE_REF_RE.findall(bare):
        if _is_forbidden_table(table):
            raise Exception(
                "Dostęp do tabel systemowych jest niedozwolony. Konsekwencje będą wyciągnięte."
            )


def make_json_serializable(obj):
    if isinstance(obj, (datetime, date, dt_time)):
        return obj.isoformat()
    elif isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(i) for i in obj]
    elif isinstance(obj, tuple):
        return tuple(make_json_serializable(i) for i in obj)
    else:
        return obj


def execute_sql(query):
    check_sql_is_safe(query)

    with connection.cursor() as cursor:
        cursor.execute(query)
        if cursor.description:
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchmany(MAX_RESULT_ROWS)
            serializable_rows = [[make_json_serializable(value) for value in row] for row in rows]
            return {"columns": columns, "rows": serializable_rows}
        else:
            return {"affected_rows": cursor.rowcount}


def format_sql_result(result, query, is_final=False):
    tag_prefix = "FINAL_SQL" if is_final else "INTERNAL_SQL"

    if "columns" not in result:
        status = f"{result['affected_rows']} row(s) affected"
        return (
            f"<{tag_prefix}_QUERY>\n{query}\n</{tag_prefix}_QUERY>\n"
            f"<{tag_prefix}_RESULTS_STATUS>{status}</{tag_prefix}_RESULTS_STATUS>"
        )

    num_rows = len(result['rows'])
    status = f"{num_rows} row(s) returned"
    results_str = "# " + ", ".join(result['columns']) + "\n"
    for row in result['rows'][:MAX_ROWS_IN_CONVERSATION]:
        results_str += "\t".join(str(v) if v is not None else 'NULL' for v in row) + "\n"
    if num_rows > MAX_ROWS_IN_CONVERSATION:
        results_str += f"... ({num_rows - MAX_ROWS_IN_CONVERSATION} more rows not shown)\n"
    if num_rows == 0 and is_final:
        results_str = "No data returned. Please check your query or assumptions."

    return (
        f"<{tag_prefix}_QUERY>\n{query}\n</{tag_prefix}_QUERY>\n"
        f"<{tag_prefix}_RESULTS_STATUS>{status}</{tag_prefix}_RESULTS_STATUS>\n"
        f"<{tag_prefix}_RESULTS>\n{results_str}</{tag_prefix}_RESULTS>"
    )


# --------------------------------------------------------------------------
# Parsing the model's replies
# --------------------------------------------------------------------------

_FENCE_RE = re.compile(r'^\s*```(?:sql)?\s*|\s*```\s*$', re.IGNORECASE)


def _clean_query(text):
    return _FENCE_RE.sub('', text).strip()


def extract_tagged(message, tag):
    """Pull the contents of every <TAG>...</TAG> block out of `message`.

    Small local models drop the closing tag fairly often, so an unterminated
    opening tag is treated as running to the end of the message rather than
    being silently ignored (which would waste a whole iteration).
    """
    blocks = [
        _clean_query(block)
        for block in re.findall(rf"<{tag}>(.*?)</{tag}>", message, re.DOTALL)
    ]
    if not blocks:
        unterminated = re.search(rf"<{tag}>(?!.*</{tag}>)(.*)$", message, re.DOTALL)
        if unterminated:
            blocks = [_clean_query(unterminated.group(1))]
    return [b for b in blocks if b]


def extract_comment_above(query, message):
    """Find the `-- comment` lines the model put right above `query`."""
    lines = message.split('\n')
    first_query_line = query.split('\n')[0].strip()
    comment = ''
    collecting_comment = False
    for line in lines:
        if first_query_line and first_query_line in line:
            break
        if line.startswith('--'):
            comment += line + '\n'
            collecting_comment = True
        elif collecting_comment and line.strip():
            collecting_comment = False
    return comment.strip()


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------

DOMAIN_NOTES = """
About the data:

Foreign keys in this database point at `uuid` columns, not at `id`. Always join
on the uuid columns shown in the schema above, e.g.
`content`.`manuscript_uuid` = `manuscripts`.`uuid`.
Tables that share a `manuscript_uuid` describe the same manuscript.

`where_in_ms_from` / `where_in_ms_to` are page references (folio or pagination,
e.g. '15r', '22v'), NOT quire numbers. Tables that share a `manuscript_uuid`
can also be joined on overlapping `where_in_ms_from`/`where_in_ms_to` ranges
even when no foreign key connects them.

Do not use `comments` columns as a data source. Prefer the dedicated column.
"""

# Notes about particular tables, sent only when every table they name is in
# the schema: a note about an empty table would send the model there.
TABLE_NOTES = (
    (('quires', 'content'), """
The quire number is `quires`.`sequence_of_the_quire` (an integer), never
`type_of_the_quire` (a string such as "quaternion"). To find the content of a
quire, prefer `content`.`quire_uuid`; that column is not always filled in, so
if it yields nothing, take the quire's page range and join `content` of the
same manuscript on overlapping page ranges instead."""),
    (('content', 'formulas'), """
Formula text is stored either inline in `content`.`formula_text` or via
`content`.`formula_uuid` referencing `formulas`.`text`. Always search both:
  WHERE `content`.`formula_text` LIKE '%x%'
     OR `content`.`formula_uuid` IN (SELECT `uuid` FROM `formulas` WHERE `text` LIKE '%x%')"""),
    (('hands',), """
Scribes / scribblers are the `hands` table. "Scribe" is another name for a hand."""),
    (('places',), """
`places` holds all modern and historical places. If the user asks about a
country, region, city or repository, look there first. Modern names are in the
columns suffixed `_today_eng`, historical ones in `_historic_eng` /
`_historic_latin`."""),
    (('time_reference',), """
`time_reference` holds datings: `century_from` <= `century_to` and
`year_from` <= `year_to` describe a range. Other tables link to it for their
dates. Asking for centuries 5 to 15 means
`century_from` >= 5 AND `century_to` <= 15.
The date of a manuscript is the date of all of its content."""),
)


def domain_notes():
    shown = get_shown_tables()
    notes = [text for tables, text in TABLE_NOTES if all(t in shown for t in tables)]
    return DOMAIN_NOTES + '\n'.join(notes)


def instance_notes():
    """Notes for this instance only (registry key `assistant_prompt_notes`)."""
    notes = (getattr(settings, 'AI_ASSISTANT_PROMPT_NOTES', '') or '').strip()
    return f'About this catalogue:\n\n{notes}\n' if notes else ''


def build_instructions(project_id, max_internal_queries, max_final_attempts):
    """System prompt: schema, rules, domain knowledge."""
    return f"""You are a data expert working for a historian who studies medieval
liturgical manuscripts. The historian does not know SQL and must never be shown
any. Your job is to turn their question into MySQL queries against the
catalogue database and return the data they asked for.

This is the complete database schema. Column names, types, allowed values and
foreign keys are all listed here, so you normally do NOT need to run DESCRIBE:

{get_schema_description()}

How to answer:

1. If you need to check what the data actually looks like (spellings, sample
   values, whether a join returns anything), run an exploratory query:
   <INTERNAL_SQL_QUERY>
   SELECT `name`, `uuid` FROM `manuscripts` LIMIT 5;
   </INTERNAL_SQL_QUERY>
   Its result is shown to you, not to the user. Always use LIMIT here.
2. When you know how to answer, write the query whose result the user will see:
   <FINAL_SQL_QUERY>
   SELECT ...
   </FINAL_SQL_QUERY>

Rules:
- Write ONE query per message, inside the tags, and nothing else. No prose
  outside the tags, no markdown code fences.
- SELECT statements only. Never INSERT, UPDATE, DELETE, DROP or ALTER.
- Wrap every table and column name in backticks.
- Use only columns that appear in the schema above.
- Whenever you return an id or uuid, return the human-readable name of the same
  object as well, even when the user did not ask for it. The historian needs
  names, not identifiers.
- Break complicated questions into small exploratory queries first. A simple
  query that returns rows beats a clever one that returns nothing.
- You have {max_internal_queries} exploratory queries and {max_final_attempts}
  attempts at the final query. You will be told how many remain.
- If a final query returns no rows, work out why (wrong assumption, wrong join,
  no such data) with exploratory queries and then try a corrected final query.
- Put a short, friendly one-sentence explanation of the answer as an SQL
  comment (starting with --) on the line above the final query, in the language
  the user asked in. This sentence is shown to the historian, so describe the
  history, never the SQL, the tables or the columns.
- If you truly cannot answer, explain why in plain language inside
  <COMMENT></COMMENT> tags, in the user's language, without mentioning SQL.

{domain_notes()}

{instance_notes()}
{manuscript_list_prompt_section(project_id)}
"""


# --------------------------------------------------------------------------
# Agent loop
# --------------------------------------------------------------------------

def run_sql_agent(
    ai_query,
    chat,
    max_iterations=15,
    max_final_attempts=5,
    timeout_seconds=90,
):
    """Drive the question -> SQL -> answer conversation to completion.

    `chat(conversation)` takes the message list and returns the assistant's
    reply as a string; that is the only thing backends differ in. The result is
    written straight onto `ai_query`.
    """
    start_time = time.time()

    def finish(**fields):
        fields.setdefault('execution_time', time.time() - start_time)
        for key, value in fields.items():
            setattr(ai_query, key, value)
        ai_query.save()

    instructions = build_instructions(
        ai_query.project_id, max_iterations, max_final_attempts
    )
    conversation = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": ai_query.question},
    ]
    ai_query.conversation = json.dumps(conversation)
    ai_query.save()

    def push(role, content):
        # Consecutive user turns are merged: some chat APIs reject alternating
        # violations, and a small model follows one combined message better
        # than a pile of short ones.
        if conversation and conversation[-1]["role"] == role == "user":
            conversation[-1]["content"] += "\n\n" + content
        else:
            conversation.append({"role": role, "content": content})
        ai_query.conversation = json.dumps(conversation)
        ai_query.save()

    final_attempts = 0
    internal_query_count = 0

    for iteration in range(max_iterations):
        if time.time() - start_time > timeout_seconds:
            finish(error=f"Timeout after {timeout_seconds} seconds", status='error')
            print(f"Timeout for AIQuery {ai_query.id}")
            return

        print(f"Iteration {iteration} for AIQuery {ai_query.id}")
        push("user", (
            f"(Remaining exploratory queries: {max(max_iterations - internal_query_count, 0)}. "
            f"Remaining final query attempts: {max_final_attempts - final_attempts}.)"
        ))

        ai_message = chat(conversation)
        push("assistant", ai_message)

        final_queries = extract_tagged(ai_message, "FINAL_SQL_QUERY")

        comments = re.findall(r"<COMMENT>(.*?)</COMMENT>", ai_message, re.DOTALL)
        if comments and not final_queries:
            finish(
                result=json.dumps([{"comment": "\n".join(c.strip() for c in comments)}]),
                status='completed',
            )
            return

        for internal_query in extract_tagged(ai_message, "INTERNAL_SQL_QUERY"):
            print(f"Internal Query: {internal_query}")
            internal_query_count += 1
            try:
                result_str = format_sql_result(execute_sql(internal_query), internal_query)
            except Exception as e:
                result_str = f"<INTERNAL_SQL_ERROR>{str(e)}</INTERNAL_SQL_ERROR>"
            push("user", result_str)

        if not final_queries:
            if not extract_tagged(ai_message, "INTERNAL_SQL_QUERY"):
                push("user", (
                    "Your reply contained no query. Answer with exactly one "
                    "<INTERNAL_SQL_QUERY> or <FINAL_SQL_QUERY> block and nothing else."
                ))
            continue

        all_success = True
        results = []
        for final_query in final_queries:
            try:
                result = execute_sql(final_query)
                if "columns" in result and len(result["rows"]) == 0:
                    final_attempts += 1
                    if final_attempts >= max_final_attempts:
                        finish(
                            error="Max final attempts reached with empty results.",
                            status='error',
                        )
                        return
                    push("user", format_sql_result(result, final_query, is_final=True))
                    all_success = False
                    break
                results.append({
                    "query": final_query,
                    "result": result,
                    "comment": extract_comment_above(final_query, ai_message),
                })
            except Exception as e:
                final_attempts += 1
                push("user", f"<FINAL_SQL_ERROR>{str(e)}</FINAL_SQL_ERROR>")
                all_success = False

        if all_success and results:
            finish(
                result=json.dumps(make_json_serializable(results)),
                status='completed',
            )
            print(f"Completed AIQuery {ai_query.id}")
            return

    finish(error="Max iterations reached without final query.", status='error')
