"""AI assistant entry point — picks a backend and runs the query.

Backends:
  'ollama' (default)  local model on this server, free, no API key, data stays
                      on the machine. See `ai_tools_ollama`.
  'openai'            the original paid OpenAI implementation, unchanged in
                      behaviour. See `ai_tools_openai`.

Choose with AI_ASSISTANT_BACKEND in settings (or the environment variable of
the same name). Everything the two share — schema, prompt, SQL safety, the
agent loop — lives in `ai_tools_common`.
"""

from django.conf import settings

from .ai_tools_common import (  # re-exported for callers and tests
    execute_sql,
    extract_comment_above,
    format_sql_result,
    get_all_manuscript_names,
    get_schema_description,
    get_table_list,
    make_json_serializable,
)
from .models import AIQuery

DEFAULT_BACKEND = 'ollama'

__all__ = [
    'process_ai_query',
    'get_backend',
    'get_backend_name',
    'execute_sql',
    'extract_comment_above',
    'format_sql_result',
    'get_all_manuscript_names',
    'get_schema_description',
    'get_table_list',
    'make_json_serializable',
]


def get_backend_name():
    return getattr(settings, 'AI_ASSISTANT_BACKEND', DEFAULT_BACKEND).strip().lower()


def get_backend(name=None):
    name = name or get_backend_name()
    if name == 'openai':
        from . import ai_tools_openai
        return ai_tools_openai
    if name == 'ollama':
        from . import ai_tools_ollama
        return ai_tools_ollama
    raise ValueError(f"Unknown AI_ASSISTANT_BACKEND: {name!r} (use 'ollama' or 'openai')")


def process_ai_query(ai_query_id):
    """Answer the question stored on AIQuery `ai_query_id`, in place.

    Called in a background thread by AssistantStartView; the browser polls the
    AIQuery row for status and results.
    """
    ai_query = AIQuery.objects.get(id=ai_query_id)
    ai_query.status = 'running'
    ai_query.save()

    try:
        get_backend().process_ai_query(ai_query)
    except Exception as e:
        print(f"Error in process: {str(e)}")
        ai_query.error = str(e)
        ai_query.status = 'error'
        ai_query.save()
