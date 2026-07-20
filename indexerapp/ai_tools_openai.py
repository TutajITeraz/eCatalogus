"""AI assistant backend backed by the paid OpenAI API.

This is the original implementation, kept working so it can be switched back on
at any time (AI_ASSISTANT_BACKEND = 'openai'). It needs each user to have an
OpenAI API key stored in their preferences and costs money per query; the
default backend is now the local model in `ai_tools_ollama`.
"""

from django.conf import settings
from openai import OpenAI

from . import ai_tools_common as common
from .models import UserOpenAIAPIKey

DEFAULT_MODEL = getattr(settings, 'OPENAI_MODEL', 'gpt-4o')
DEFAULT_TEMPERATURE = getattr(settings, 'OPENAI_TEMPERATURE', 0.7)


def make_chat(client, model=DEFAULT_MODEL, temperature=DEFAULT_TEMPERATURE):
    """Build the `chat(conversation) -> str` callable the agent loop expects."""
    def chat(conversation):
        response = client.chat.completions.create(
            model=model,
            messages=conversation,
            temperature=temperature,
        )
        return response.choices[0].message.content

    return chat


def process_ai_query(ai_query):
    try:
        user_api_key = UserOpenAIAPIKey.objects.get(user=ai_query.user).api_key
    except UserOpenAIAPIKey.DoesNotExist:
        ai_query.error = "No OpenAI API key set. Add one in your user preferences."
        ai_query.status = 'error'
        ai_query.save()
        return

    common.run_sql_agent(
        ai_query,
        make_chat(OpenAI(api_key=user_api_key)),
        max_iterations=getattr(settings, 'AI_ASSISTANT_MAX_ITERATIONS', 15),
        timeout_seconds=getattr(settings, 'AI_ASSISTANT_TIMEOUT', 90),
    )


__all__ = ['make_chat', 'process_ai_query', 'DEFAULT_MODEL']
