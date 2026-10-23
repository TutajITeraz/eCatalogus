"""Translate Formulas.text (Latin) into Formulas.translation_pl with translategemma.

Resumable: by default only formulas with an empty translation_pl are processed,
so an interrupted run just continues where it stopped. Progress is written
after every formula to a JSON file that `scripts/run_translate_formulas_pl.sh
status` reads.
"""

import csv
import json
import os
import signal
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from indexerapp.ai_tools_ollama import _fix_byte_fallback_tokens
from indexerapp.models import Formulas

OLLAMA_HOST = getattr(settings, 'OLLAMA_HOST', 'http://127.0.0.1:11434')
DEFAULT_MODEL = 'translategemma:4b'

# The exact prompt translategemma was trained on; do not reword it.
PROMPT_TEMPLATE = (
    "You are a professional {source_lang} ({source_code}) to {target_lang} ({target_code}) translator. "
    "Your goal is to accurately convey the meaning and nuances of the original {source_lang} text "
    "while adhering to {target_lang} grammar, vocabulary, and cultural sensitivities.\n"
    "Produce only the {target_lang} translation, without any additional explanations or commentary. "
    "Please translate the following {source_lang} text into {target_lang}:\n"
    "\n"
    "\n"
    "{text}"
)


def build_prompt(text):
    return PROMPT_TEMPLATE.format(
        source_lang='Latin', source_code='la',
        target_lang='Polish', target_code='pl',
        text=text,
    )


def ollama_post(path, body, timeout):
    request = urllib.request.Request(
        f'{OLLAMA_HOST}{path}',
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def loaded_model_info(model):
    """'<vram>/<size> GB on GPU' for a loaded model, from Ollama's /api/ps."""
    try:
        with urllib.request.urlopen(f'{OLLAMA_HOST}/api/ps', timeout=10) as response:
            models = json.loads(response.read().decode("utf-8")).get("models", [])
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return 'unknown'
    for m in models:
        if m.get("name") == model or m.get("model") == model:
            size, vram = m.get("size", 0), m.get("size_vram", 0)
            pct = 100 * vram / size if size else 0
            return f"{vram / 1e9:.1f}/{size / 1e9:.1f} GB on GPU ({pct:.0f}%)"
    return 'not loaded'


def unload_model(model):
    try:
        ollama_post('/api/generate', {"model": model, "keep_alive": 0}, timeout=60)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        pass


def translate(text, model, timeout, keep_alive='5m'):
    data = ollama_post('/api/chat', {
        "model": model,
        "stream": False,
        "keep_alive": keep_alive,
        "messages": [{"role": "user", "content": build_prompt(text)}],
        "options": {
            "temperature": 0,
            # Polish runs longer than Latin; cap it so a looping generation ends.
            "num_predict": max(256, len(text) * 2),
        },
    }, timeout)
    if data.get("error"):
        raise RuntimeError(data["error"])
    content = (data.get("message") or {}).get("content", "")
    return _fix_byte_fallback_tokens(content).strip(), data.get("done_reason", "")


class Command(BaseCommand):
    help = "Translate Latin formulas into Polish (translation_pl) with a local Ollama translategemma model"

    def add_arguments(self, parser):
        parser.add_argument('--model', default=DEFAULT_MODEL)
        parser.add_argument('--limit', type=int, default=0, help='Stop after this many formulas (0 = all)')
        parser.add_argument('--ids', default='', help='Comma-separated formula ids to translate')
        parser.add_argument('--overwrite', action='store_true', help='Also re-translate formulas that already have translation_pl')
        parser.add_argument('--dry-run', action='store_true', help='Print translations without saving them')
        parser.add_argument('--timeout', type=int, default=300, help='Seconds allowed per formula')
        parser.add_argument('--retries', type=int, default=2)
        parser.add_argument('--keep-alive', default='5m', help='How long Ollama keeps the model loaded between formulas')
        parser.add_argument('--compare', default='', help='Comma-separated models: translate a sample with each, write a CSV, save nothing')
        parser.add_argument('--sample', type=int, default=10, help='Number of formulas for --compare (ignored with --ids)')
        parser.add_argument('--compare-file', default=os.path.join(settings.BASE_DIR, 'logs', 'translate_formulas_pl.compare.csv'))
        parser.add_argument('--progress-file', default=os.path.join(settings.BASE_DIR, 'logs', 'translate_formulas_pl.progress.json'))

    def handle(self, *args, **options):
        model = options['model']
        self._stop = False
        signal.signal(signal.SIGTERM, self._request_stop)
        signal.signal(signal.SIGINT, self._request_stop)

        try:
            urllib.request.urlopen(f'{OLLAMA_HOST}/api/tags', timeout=10).read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise CommandError(f"Ollama is not reachable at {OLLAMA_HOST}: {e}")

        queryset = Formulas.objects.exclude(text__isnull=True).exclude(text__exact='')
        if not options['overwrite']:
            queryset = queryset.filter(Q(translation_pl__isnull=True) | Q(translation_pl__exact=''))
        if options['ids']:
            queryset = queryset.filter(pk__in=[int(i) for i in options['ids'].split(',') if i.strip()])
        queryset = queryset.order_by('pk')

        if options['compare']:
            return self._compare(queryset, options)

        total = queryset.count()
        if options['limit']:
            total = min(total, options['limit'])
        ids = list(queryset.values_list('pk', flat=True)[:total])

        self.progress_file = options['progress_file']
        os.makedirs(os.path.dirname(self.progress_file), exist_ok=True)
        progress = {
            'status': 'running',
            'pid': os.getpid(),
            'model': model,
            'started_at': timezone.now().isoformat(),
            'total': total,
            'done': 0,
            'failed': 0,
            'failed_ids': [],
            'last_id': None,
            'last_text': '',
            'last_translation': '',
            'avg_seconds': None,
            'eta_seconds': None,
            'dry_run': options['dry_run'],
        }
        self._write_progress(progress)
        self.stdout.write(f"Translating {total} formulas la -> pl with {model}")

        started = time.time()
        for index, pk in enumerate(ids, start=1):
            if self._stop:
                break
            formula = Formulas.objects.filter(pk=pk).first()
            if formula is None:
                continue

            translation = None
            for attempt in range(1, options['retries'] + 2):
                try:
                    translation, done_reason = translate(formula.text, model, options['timeout'], options['keep_alive'])
                    if done_reason == 'length':
                        self.stdout.write(f"  [{pk}] output hit num_predict cap, may be truncated")
                    if translation:
                        break
                except (urllib.error.URLError, TimeoutError, OSError, RuntimeError, json.JSONDecodeError) as e:
                    self.stdout.write(f"  [{pk}] attempt {attempt} failed: {e}")
                    time.sleep(5 * attempt)

            if translation:
                if not options['dry_run']:
                    formula.translation_pl = translation
                    # entry_date is auto_now, so ETL watermarks pick the change up.
                    formula.save(update_fields=['translation_pl', 'entry_date'])
                progress['done'] += 1
                progress['last_translation'] = translation
                self.stdout.write(f"[{index}/{total}] #{pk}\n  la: {formula.text}\n  pl: {translation}")
            else:
                progress['failed'] += 1
                progress['failed_ids'].append(pk)
                self.stdout.write(self.style.ERROR(f"[{index}/{total}] #{pk} FAILED"))

            elapsed = time.time() - started
            progress['last_id'] = pk
            progress['last_text'] = formula.text
            progress['avg_seconds'] = round(elapsed / index, 2)
            progress['eta_seconds'] = round(progress['avg_seconds'] * (total - index))
            self._write_progress(progress)

        progress['status'] = 'stopped' if self._stop else 'finished'
        progress['finished_at'] = timezone.now().isoformat()
        progress['eta_seconds'] = 0 if not self._stop else progress['eta_seconds']
        self._write_progress(progress)
        self.stdout.write(self.style.SUCCESS(
            f"{progress['status'].capitalize()}: {progress['done']} translated, {progress['failed']} failed"
        ))

    def _compare(self, queryset, options):
        models = [m.strip() for m in options['compare'].split(',') if m.strip()]
        if options['ids']:
            formulas = list(queryset)
        else:
            # Spread the sample over the table instead of taking the first rows.
            ids = list(queryset.values_list('pk', flat=True))
            step = max(1, len(ids) // max(1, options['sample']))
            formulas = list(Formulas.objects.filter(pk__in=ids[::step][:options['sample']]).order_by('pk'))

        results = {f.pk: {} for f in formulas}
        summary = []
        for model in models:
            if self._stop:
                break
            self.stdout.write(f"=== {model}: {len(formulas)} formulas ===")
            started = time.time()
            gpu_info = 'not loaded'
            failed = 0
            for formula in formulas:
                if self._stop:
                    break
                t0 = time.time()
                try:
                    translation, _ = translate(formula.text, model, options['timeout'], options['keep_alive'])
                except (urllib.error.URLError, TimeoutError, OSError, RuntimeError, json.JSONDecodeError) as e:
                    translation = f"ERROR: {e}"
                    failed += 1
                if gpu_info == 'not loaded':
                    gpu_info = loaded_model_info(model)
                    self.stdout.write(f"  loaded: {gpu_info}")
                results[formula.pk][model] = translation
                self.stdout.write(f"  #{formula.pk} ({time.time() - t0:.1f}s) pl: {translation}")
            elapsed = time.time() - started
            # Free the GPU for other jobs before the next model loads.
            unload_model(model)
            summary.append((model, gpu_info, elapsed / max(1, len(formulas)), failed))

        os.makedirs(os.path.dirname(options['compare_file']), exist_ok=True)
        with open(options['compare_file'], 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'la'] + models)
            for formula in formulas:
                writer.writerow([formula.pk, formula.text] + [results[formula.pk].get(m, '') for m in models])

        self.stdout.write("\n=== Summary ===")
        for model, gpu_info, avg, failed in summary:
            self.stdout.write(f"{model}: {avg:.1f}s per formula, {failed} failed, {gpu_info}")
        self.stdout.write(self.style.SUCCESS(f"Side-by-side CSV: {options['compare_file']}"))

    def _request_stop(self, signum, frame):
        self.stdout.write("Stop requested, finishing the current formula...")
        self._stop = True

    def _write_progress(self, progress):
        tmp_path = f"{self.progress_file}.tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.progress_file)
