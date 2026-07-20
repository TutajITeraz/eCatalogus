"""AI assistant backend backed by a local Ollama instance.

Same model and endpoint as the OCR autofix tool running on this server, so
Ollama keeps a single copy of the weights loaded for both applications.

Costs nothing per query, needs no user API key, and the data never leaves the
machine. `ai_tools_openai` remains available as an alternative backend.
"""

import json
import re
import time
import urllib.error
import urllib.request

from django.conf import settings

from . import ai_tools_common as common

OLLAMA_HOST = getattr(settings, 'OLLAMA_HOST', 'http://127.0.0.1:11434')
OLLAMA_CHAT_URL = f'{OLLAMA_HOST}/api/chat'
OLLAMA_TAGS_URL = f'{OLLAMA_HOST}/api/tags'

# Must match the model the OCR autofix tool uses, so Ollama loads it once.
DEFAULT_MODEL = getattr(settings, 'OLLAMA_MODEL', 'gemma4:12b-it-qat')

# SQL generation wants determinism, not creativity.
DEFAULT_TEMPERATURE = getattr(settings, 'OLLAMA_TEMPERATURE', 0.05)
# A 12B model on a shared GPU needs far longer than the OpenAI backend did:
# this is the budget for one turn, and AI_ASSISTANT_TIMEOUT for the whole query.
REQUEST_TIMEOUT = getattr(settings, 'OLLAMA_REQUEST_TIMEOUT', 300)
STALL_TIMEOUT = 60
THINK_MODE = getattr(settings, 'OLLAMA_THINK', False)

# Models with byte-fallback tokenisation stream rare codepoints (the ligatures
# common in liturgical Latin, e.g. U+A753 "ꝓ") one byte at a time, which
# llama.cpp emits as literal "<0xHH>" placeholders. Reassemble them.
_BYTE_FALLBACK_RUN_RE = re.compile(r"(?:<0x[0-9A-Fa-f]{2}>)+")
_BYTE_FALLBACK_TOKEN_RE = re.compile(r"<0x([0-9A-Fa-f]{2})>")


def _fix_byte_fallback_tokens(text):
    def _decode_run(match):
        raw = bytes(int(h, 16) for h in _BYTE_FALLBACK_TOKEN_RE.findall(match.group()))
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return match.group()

    return _BYTE_FALLBACK_RUN_RE.sub(_decode_run, text)


def get_ollama_models():
    """Names of the models installed in the local Ollama instance."""
    try:
        with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        print(f"Cannot connect to Ollama: {e}")
        return []


def is_available():
    try:
        urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=5).read()
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def chat(conversation, model=None, temperature=DEFAULT_TEMPERATURE, timeout=REQUEST_TIMEOUT):
    """Send `conversation` to Ollama and return the assistant's reply text.

    Streams the response so a stalled generation can be detected and aborted
    rather than blocking the whole request timeout.
    """
    payload = json.dumps({
        "model": model or DEFAULT_MODEL,
        "stream": True,
        "think": bool(THINK_MODE),
        "options": {
            "temperature": temperature,
            "repeat_penalty": 1.12,
            "top_p": 0.92,
        },
        "messages": conversation,
    }).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_CHAT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    collected = []
    started = time.time()
    last_activity = started
    eval_count = 0

    with urllib.request.urlopen(request, timeout=timeout) as response:
        for line in response:
            now = time.time()
            if now - started > timeout:
                print(f"   Ollama hard timeout ({timeout}s) - truncating response")
                break
            if now - last_activity > STALL_TIMEOUT:
                print(f"   Ollama stalled (no data for {STALL_TIMEOUT}s) - aborting")
                break
            if not line.strip():
                continue
            last_activity = now

            try:
                chunk = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue

            message = chunk.get("message") or {}
            # Reasoning tokens are not part of the answer we parse for SQL.
            if not message.get("thinking"):
                collected.append(message.get("content", ""))

            if chunk.get("done", False):
                eval_count = chunk.get("eval_count", 0) or 0
                break

    text = _fix_byte_fallback_tokens("".join(collected)).strip()
    print(
        f"Ollama assistant: model={model or DEFAULT_MODEL} "
        f"took={time.time() - started:.1f}s tokens={eval_count}"
    )
    return text


def process_ai_query(ai_query):
    if not is_available():
        ai_query.error = f"Local AI model is not reachable at {OLLAMA_HOST}."
        ai_query.status = 'error'
        ai_query.save()
        print(f"Error in process: {ai_query.error}")
        return

    common.run_sql_agent(
        ai_query,
        chat,
        max_iterations=getattr(settings, 'AI_ASSISTANT_MAX_ITERATIONS', 15),
        timeout_seconds=getattr(settings, 'AI_ASSISTANT_TIMEOUT', 900),
    )


__all__ = ['chat', 'process_ai_query', 'get_ollama_models', 'is_available', 'DEFAULT_MODEL']
