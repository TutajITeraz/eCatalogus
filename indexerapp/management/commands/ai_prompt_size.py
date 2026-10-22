"""Measure which parts of the AI assistant's system prompt eat the context window.

Token counts are exact: Ollama reports `prompt_eval_count` for a raw prompt. A
piece longer than the model's context window is reported truncated (the count
stops near the window size), so read such numbers as ">= window".
"""

import json
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand

from indexerapp import ai_tools_common as common
from indexerapp.models import Manuscripts


def count_tokens(text, model):
    payload = json.dumps({
        "model": model,
        "prompt": text,
        "raw": True,
        "stream": False,
        "options": {"num_predict": 1},
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.OLLAMA_HOST}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read().decode("utf-8")).get("prompt_eval_count", 0)


class Command(BaseCommand):
    help = "Print the token size of each part of the AI assistant system prompt."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, default=0, help="project id (0 = all)")
        parser.add_argument("--model", default=settings.OLLAMA_MODEL)

    def handle(self, *args, **options):
        project, model = options["project"], options["model"]

        def row(label, text):
            self.stdout.write(f"{label:<45}{len(text):>9} chars{count_tokens(text, model):>9} tokens")

        self.stdout.write(f"model={model} project={project}\n")

        schema = common.get_schema_description()
        row("schema (non-empty tables)", schema)
        blocks = schema.split("\n\n")
        for block in sorted(blocks, key=len, reverse=True)[:8]:
            row(f"   {block.splitlines()[0][:40]}", block)
        row("domain notes", common.domain_notes())
        row("instance notes", common.instance_notes())

        full = common.build_instructions(project, 15, 5)
        section = common.manuscript_list_prompt_section(project)
        row("prompt without manuscript list", full.replace(section, ""))
        row("manuscript section as sent now", section)
        row("whole prompt as sent now", full)

        queryset = Manuscripts.objects.all()
        if project != 0:
            queryset = queryset.filter(ms_projects__project_uuid__id=project)
        rows = list(queryset.values_list("id", "name", "rism_id", "foreign_id", "shelf_mark"))
        self.stdout.write(f"\nmanuscripts: {len(rows)}")

        def lines(*cols):
            return "\n".join(",".join(f'"{r[c] or ""}"' for c in cols) for r in rows)

        row("list: id,name,rism,foreign,shelf (current)", lines(0, 1, 2, 3, 4))
        row("list: id+name", lines(0, 1))
        row("list: name only", lines(1))
        row("list: id only", lines(0))
        row("list: name+shelf_mark", lines(1, 4))
