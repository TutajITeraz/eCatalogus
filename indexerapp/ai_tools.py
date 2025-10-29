from openai import OpenAI
import re
import json
import time
from datetime import datetime, date, time as dt_time
from django.db import connection
from django.contrib.auth.models import User
from .models import UserOpenAIAPIKey, Manuscripts, AIQuery

def get_all_manuscript_names(projectId):
    queryset = Manuscripts.objects.all()

    if projectId != 0:
        queryset = queryset.filter(ms_projects__project__id=projectId)

    # Start with headers
    csv_data = '"id","name","rism_id","foreign_id","shelf_mark"\n'

    # Iterate over the queryset to create CSV rows
    for manuscript in queryset:
        row = f'"{manuscript.id}","{manuscript.name}","{manuscript.rism_id or ""}","{manuscript.foreign_id or ""}","{manuscript.shelf_mark or ""}"\n'
        csv_data += row

    return csv_data

def get_table_list():
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES;")
        tables = [row[0] for row in cursor.fetchall()]
    forbidden_patterns = ['auth_', 'django_admin_log', 'django_session', 'django_migrations']
    filtered_tables = [t for t in tables if not any(t.startswith(p) if p.endswith('_') else t == p for p in forbidden_patterns)]
    return '\n'.join(filtered_tables)

def extract_comment_above(query, message):
    # Simple regex to find -- comment before the query in the message
    lines = message.split('\n')
    query_lines = query.split('\n')
    first_query_line = query_lines[0].strip()
    comment = ''
    collecting_comment = False
    for line in lines:
        if first_query_line in line:
            break
        if line.startswith('--'):
            comment += line + '\n'
            collecting_comment = True
        elif collecting_comment and line.strip():
            collecting_comment = False
    return comment.strip()

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
    query_lower = query.lower()
    forbidden_operations = ['insert', 'update', 'delete', 'drop', 'alter', 'create', 'truncate', 'replace']
    if any(op in query_lower for op in forbidden_operations):
        raise Exception("Niedozwolone operacje na bazie danych. Konsekwencje będą wyciągnięte.")

    forbidden_table_pattern = r'\b(from|join)\s+`(?:auth_.+|django_admin_log|django_session|django_migrations)`'
    if re.search(forbidden_table_pattern, query_lower, re.IGNORECASE):
        raise Exception("Dostęp do tabel systemowych jest niedozwolony. Konsekwencje będą wyciągnięte.")

    #print(f"Executing SQL: {query}")
    with connection.cursor() as cursor:
        try:
            cursor.execute(query)
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                # Convert rows to list of lists and make serializable
                serializable_rows = [[make_json_serializable(value) for value in row] for row in rows]
                return {"columns": columns, "rows": serializable_rows}
            else:
                return {"affected_rows": cursor.rowcount}
        except Exception as e:
            #print(f"SQL Error: {str(e)}")
            raise e

def format_sql_result(result, query, is_final=False):
    if "columns" in result:
        num_rows = len(result['rows'])
        status = f"{num_rows} row(s) returned"
        results_str = "# " + ", ".join(result['columns']) + "\n"
        for row in result['rows']:
            results_str += "\t".join(str(v) if v is not None else 'NULL' for v in row) + "\n"
        tag_prefix = "FINAL_SQL" if is_final else "INTERNAL_SQL"
        if num_rows == 0 and is_final:
            results_str = "No data returned. Please check your query or assumptions."
        return f"<{tag_prefix}_QUERY>\n{query}\n</{tag_prefix}_QUERY>\n<{tag_prefix}_RESULTS_STATUS>{status}</{tag_prefix}_RESULTS_STATUS>\n<{tag_prefix}_RESULTS>\n{results_str}</{tag_prefix}_RESULTS>"
    else:
        status = f"{result['affected_rows']} row(s) affected"
        tag_prefix = "FINAL_SQL" if is_final else "INTERNAL_SQL"
        return f"<{tag_prefix}_QUERY>\n{query}\n</{tag_prefix}_QUERY>\n<{tag_prefix}_RESULTS_STATUS>{status}</{tag_prefix}_RESULTS_STATUS>"

def process_ai_query(ai_query_id):
    #print(f"Starting process for AIQuery {ai_query_id}")
    ai_query = AIQuery.objects.get(id=ai_query_id)
    ai_query.status = 'running'
    ai_query.save()

    start_time = time.time()

    try:
        user_api_key = UserOpenAIAPIKey.objects.get(user=ai_query.user).api_key
        client = OpenAI(api_key=user_api_key)
        projectId = ai_query.project_id
        db_structure = get_table_list()
        manuscript_names = get_all_manuscript_names(projectId)

        instructions = """
You are a super data scientist that gets questions from users that does not know database and sql, and your task is to translate user questions to the SQL query. 
This is the list of tables and relations between them:
""" + db_structure + """

Always start by exploring the schema: Use <INTERNAL_SQL_QUERY> with DESCRIBE table_name; for suspected tables (e.g., DESCRIBE manuscripts; DESCRIBE quires; DESCRIBE content;) to see all columns, types, and constraints. Then, use information_schema.KEY_COLUMN_USAGE to check foreign keys and relationships, like in this example:
<INTERNAL_SQL_QUERY>
SELECT 
    table_name,
    column_name,
    constraint_name,
    referenced_table_name,
    referenced_column_name
FROM information_schema.KEY_COLUMN_USAGE
WHERE table_schema = DATABASE()
  AND referenced_table_name IS NOT NULL
  AND table_name IN ('manuscripts', 'quires', 'content');
</INTERNAL_SQL_QUERY>
This helps you understand joins (e.g., manuscript_id is common) and avoid assumptions.

For quire-related questions (e.g., "quire 3" or "quire 22"), the quire number is ALWAYS in `quires.sequence_of_the_quire` (an integer like 3 or 22), NOT `type_of_the_quire` (which is a string like "quaternion"). Confirm with DESCRIBE quires;.

To find content on a specific quire, first get the quire's page range from `quires.where_in_ms_from` and `quires.where_in_ms_to`. Then join with `content` on the same `manuscript_id` and overlapping page ranges (e.g., using BETWEEN or >=/<= for varchar page strings like '15r' to '22v'). Example join for content on quire 3:
<INTERNAL_SQL_QUERY>
SELECT
q.id AS quire_id,
q.sequence_of_the_quire,
q.type_of_the_quire,
q.where_in_ms_from AS quire_start,
q.where_in_ms_to AS quire_end,
c.id AS content_id,
c.formula_text,
c.biblical_reference,
c.comments,
c.where_in_ms_from AS content_start,
c.where_in_ms_to AS content_end
FROM quires AS q
JOIN content AS c
ON c.manuscript_id = q.manuscript_id
AND (
  (c.where_in_ms_from BETWEEN q.where_in_ms_from AND q.where_in_ms_to)
  OR (c.where_in_ms_to BETWEEN q.where_in_ms_from AND q.where_in_ms_to)
  OR (q.where_in_ms_from BETWEEN c.where_in_ms_from AND c.where_in_ms_to)
)
WHERE q.manuscript_id = [manuscript_id]
AND q.sequence_of_the_quire = 3
ORDER BY c.sequence_in_ms;
</INTERNAL_SQL_QUERY>

Always break down complex questions into smaller, simpler internal queries to verify assumptions and gather information step by step before attempting the final query. This helps avoid creating overly complicated queries that return no results.

First you should query the database to get to know its structure and sample data (use LIMIT!) using DESCRIBE and SELECT * ... LIMIT 5 to see actual data. To do so put your SQL query (with no additional comments, because this is an automated process) between <INTERNAL_SQL_QUERY> and </INTERNAL_SQL_QUERY> tags. The result of internal query will be presented to you.
Then if you have all the information needed, please write final query between <FINAL_SQL_QUERY> and </FINAL_SQL_QUERY> tags. This final query results will be presented to the user.
Use MySQL syntax.

You can perform up to 15 internal queries in total, but try to minimize them and execute the final query as soon as you have sufficient information. You must produce the final query before running out of iterations (15 total). You have up to 5 attempts for the final query if it fails or returns no results. The system will inform you of the remaining number of internal and final queries with each iteration.

If the final query returns no results, you will be informed, and you should analyze why (e.g., wrong assumptions, missing data, incorrect joins) using additional <INTERNAL_SQL_QUERY> to investigate the issue (e.g., check sample data, verify joins, or DESCRIBE other tables), and then try again with a corrected final query.

For questions about database structure or meta-information (e.g., "In which table are data about manuscript damages stored?"), include a short, friendly natural language explanation as a SQL comment (starting with --) before the final query. This comment should answer the question directly without mentioning SQL details or implementation, as the user doesn't need to know that. Keep it concise and user-friendly.

If you need more information or the question is ambiguous, use <INTERNAL_SQL_QUERY> to explore and gather the necessary details first. Only use <COMMENT> </COMMENT> tag if you absolutely cannot proceed without user clarification or if it's the final response to the user (e.g., to ask for more details or explain why no data is available). Do not stop after outputting <COMMENT>; continue with queries if possible.

Respond ONLY with SQL code inside the tags. You can add comments inside SQL code, but only as SQL comments (starting from --). You cannot write anything but the tags with SQL code and comments inside SQL.
Make sure that you will use table names and column names only after querying the structure.
If user asks you question about some objects, please ALWAYS include the NAME of the objects too (if available in the schema). 
Include a name, even if the user doesn't specifically ask for it.
Always include both name and id.
If you include id, include name too.
Answer in the same language that user used.
Always use the MySQL syntax.

If you cannot answer - please use the <COMMENT> tag to tell why.

You can write only SELECT statements. You cannot write INSERT, DROP, DELETE or any other queries.

Please write multiple <INTERNAL_SQL_QUERY> if needed, but try to minimize them.
For final, you can write multiple <FINAL_SQL_QUERY> if needed for the answer.

ALWAYS wrap the table names and the column names in backticks ( ` )!

About the data:
If some tables has field where_in_ms_from or where_in_ms_to - you can join those tables using this data and manuscript_id even if they do not have direct foreign keys. 

User can reffer to the following manuscripts by name rism or foreign id. If so, then filter the query with the proper ids:
""" + manuscript_names + """

Dont use comments columns. Always try to find the best table match for task.
If you dont know, or not sure about what table to use or what columnt to use - use internal queries to explore!

If user asks about some table - sql should output all columns from that table.
If user asks about some place reffered by current, modern name, look in the columns with suffix _today_eng.
century_from is ALWAYS less than century_to - this represents range between century_from and century_to
year_from is ALWAYS less than year_to - this represents range between year_from and year_to
For example proper way for asking about century between 5 and 15 is:
`century_from` >= 5 AND `time_reference`.`century_to` <= 15

Do not use any column that was not mentioned in queried structure!
Date of the manuscript is the date for all its content.

When you are asked about formula text - it can be saved as formula_text or as formula_id reference to formulas table, which have "text" column. Always look in both places. 
e.g. If you use:
 WHERE (`content`.`formula_text` LIKE '%some_text%' 
Always add this OR statement too:
 OR `content`.`formula_id` IN (
    SELECT `formulas`.`id` FROM `formulas` WHERE `formulas`.`text` LIKE '%some_text%'
))

scribes, scribblers are in the Hands table. Scribes is another name of Hands.

where_in_ms_from - this is the page number (i.e., folio or pagination), not the quire number.

places - contains a list of all modern and historical places. If the user asks about a country, region, city, or repository, find it first in these columns. Example:
# id, longitude, latitude, country_today_eng, region_today_eng, city_today_eng, repository_today_eng, country_today_local_language, region_today_local_language, city_today_local_language, repository_today_local_language, country_historic_eng, region_historic_eng, city_historic_eng, repository_historic_eng, country_historic_local_language, region_historic_local_language, city_historic_local_language, repository_historic_local_language, country_historic_latin, region_historic_latin, city_historic_latin, repository_historic_latin, place_type
'2', '17.894833', '52.206194', 'Poland', 'Great Poland', 'Ląd', 'Ląd Abbey', 'Polska', 'Wielkopolska', 'Ląd', 'Opactwo Cystersów w Lądzie', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL


If the user asks about dates, year, century, find the appropriate date range first. Example:
# id, time_description, century_from, century_to, year_from, year_to
'5', 'IV', '4', '4', '301', '400'
'6', 'IV 1/2', '4', '4', '301', '350'
'7', 'IV 2/2', '4', '4', '351', '400'

other tables connect to this table for date descriptions.

Always, tables that are connected by manuscript_id can also be joined by where_in_ms_from.

Field enum dictionaries:
"manuscripts","form_of_an_item","varchar", can be ("C" for "CODEX"),("F" for "FRAGMENT"),("P" for "PALIMPSEST"),("L" for "LOST")

"manuscripts","foliation_or_pagination","varchar", can be "FOLIATION" or "PAGINATION"


"quires","type_of_the_quire","varchar", can be "bifolium","binion","ternion","quaternion","quinternion","seksternion","septernion","okternion"


"places","place_type","varchar", can be "library", "center", "scriptory" or "multiple"


"content","similarity_by_user","varchar", can be "0" meaning "the formula not in the editions"),("0.5" meaning "paraphrase"),("1" meaning "exact match"


"bindings","category","varchar", can be: "original", ("early" meaning "early modern"),("historical" meaning "Historical rebinding"),("conservation" meaning "Conservation binding"),("restored" meaning "Restored binding")

"liturgical_genres","title","varchar", can be: "Graduale", "Benedictional", "Ritual", "Calendar", "Collectar", "Pontifical", "Missal", "Sacramentary" 

"decoration","monochrome_or_colour","varchar", can be "M" if monochromatic, "B" if bicolored, or "C" if multicolored

"decoration","location_on_the_page","varchar", can be: "WITHIN" meaning "within the column"), ("MARGIN" meaning "on the margin"),("IN_TEXT" meaning "in the text line")
"decoration","size_characteristic","varchar", can be: [("SMALL" meaning "small"),("1LINE" meaning "1-line"),("2LINES" meaning "2-lines"),("3LINES" meaning "3-lines"),("1SYSTEM" meaning "1-system"),("2SYSTEMS" meaning "2-systems"),("LARGE" meaning "large"),("FULL" meaning "full page")]

"decoration","original_or_added","varchar", can be: "ORIGINAL" or "ADDED"

"condition","damage","varchar", can be "very" if very damaged, "average" or "slightly" or null

"colours","name","varchar", can be: creamy,copper,gray,gold,silver,brown,rose,purple,cyan,orange,yellow,black,white,blue,green,red

"layouts","pricking","varchar", can be "yes", "no", "partially"

"layouts","ruling_method","varchar", can be "blind-point","board","ink""lead-point","rake","rake-lead","rake-ink","rake-lead-ink"

"""

        conversation = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": ai_query.question}
        ]
        ai_query.conversation = json.dumps(conversation)
        ai_query.save()

        max_iterations = 15  # Increased to allow more internal queries
        max_final_attempts = 5
        final_attempts = 0
        internal_query_count = 0
        iteration = 0

        while iteration < max_iterations:
            if time.time() - start_time > 90:
                ai_query.error = "Timeout after 90 seconds"
                ai_query.status = 'error'
                ai_query.save()
                print(f"Timeout for AIQuery {ai_query_id}")
                return

            print(f"Iteration {iteration} for AIQuery {ai_query_id}")
            remaining_internal = max(15 - internal_query_count, 0)
            remaining_final = max_final_attempts - final_attempts
            conversation.append({
                "role": "user",
                "content": f"Remaining internal queries: {remaining_internal}. Remaining final query attempts: {remaining_final}."
            })
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=conversation,
                temperature=0.7,
            )
            ai_message = response.choices[0].message.content
            #print(f"AI Response: {ai_message}")

            conversation.append({"role": "assistant", "content": ai_message})
            ai_query.conversation = json.dumps(conversation)
            ai_query.save()

            # Handle comments if any
            comments = re.findall(r"<COMMENT>(.*?)</COMMENT>", ai_message, re.DOTALL)
            if comments:
                # Treat as completed with comment if no final query in this message
                if not re.findall(r"<FINAL_SQL_QUERY>(.*?)</FINAL_SQL_QUERY>", ai_message, re.DOTALL):
                    ai_query.result = json.dumps([{"comment": "\n".join(comments)}])
                    ai_query.status = 'completed'
                    ai_query.save()
                    #print(f"Completed with comment for AIQuery {ai_query_id}")
                    return
                else:
                    # If there is final query, continue processing
                    pass

            internal_queries = re.findall(r"<INTERNAL_SQL_QUERY>(.*?)</INTERNAL_SQL_QUERY>", ai_message, re.DOTALL)
            for iq in internal_queries:
                iq = iq.strip()
                print(f"Internal Query: {iq}")
                internal_query_count += 1
                try:
                    result = execute_sql(iq)
                    result_str = format_sql_result(result, iq)
                except Exception as e:
                    result_str = f"<INTERNAL_SQL_ERROR>{str(e)}</INTERNAL_SQL_ERROR>"
                conversation.append({"role": "user", "content": result_str})
                ai_query.conversation = json.dumps(conversation)
                ai_query.save()

            final_queries = re.findall(r"<FINAL_SQL_QUERY>(.*?)</FINAL_SQL_QUERY>", ai_message, re.DOTALL)
            if final_queries:
                all_success = True
                results = []
                for fq in final_queries:
                    fq = fq.strip()
                    #print(f"Final Query: {fq}")
                    try:
                        result = execute_sql(fq)
                        if "columns" in result and len(result["rows"]) == 0:
                            if final_attempts >= max_final_attempts:
                                raise Exception("Max final attempts reached with empty results.")
                            final_attempts += 1
                            result_str = format_sql_result(result, fq, is_final=True)
                            conversation.append({"role": "user", "content": result_str})
                            ai_query.conversation = json.dumps(conversation)
                            ai_query.save()
                            all_success = False
                            break  # Break to retry in next iteration
                        comment = extract_comment_above(fq, ai_message)
                        results.append({"query": fq, "result": result, "comment": comment})
                    except Exception as e:
                        conversation.append({"role": "user", "content": f"<FINAL_SQL_ERROR>{str(e)}</FINAL_SQL_ERROR>"})
                        ai_query.conversation = json.dumps(conversation)
                        ai_query.save()
                        all_success = False
                if all_success:
                    # Serialize results with custom converter
                    serializable_results = make_json_serializable(results)
                    ai_query.result = json.dumps(serializable_results)
                    ai_query.status = 'completed'
                    ai_query.save()
                    print(f"Completed AIQuery {ai_query_id}")
                    return
            iteration += 1
        ai_query.error = "Max iterations reached without final query."
        ai_query.status = 'error'
        ai_query.save()
    except Exception as e:
        print(f"Error in process: {str(e)}")
        ai_query.error = str(e)
        ai_query.status = 'error'
        ai_query.save()
