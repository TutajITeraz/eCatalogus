#!/usr/bin/env python
"""Build the small UI bundle for a site that serves the pages but not the assets.

eCLLA's public UI lives on eclla.henrybradshawsociety.org (HBS), the API on
api.eclla.ecatalogus.ispan.pl. `collectstatic` produces ~70 MB (53 MB of JavaScript), but the
pages only need to be *served* from HBS; scripts, styles and images can come from the
faster API host. This script copies just the pages (the top-level ``*.html`` files of the
static directory) and rewrites every asset reference from ``/static/<dir>/...`` to
``<api-root>/static/<dir>/...``. Links to pages (``/static/page.html?p=...``) stay relative so
navigation remains on the site.

    python scripts/export_ui_bundle.py --instance eclla --output ~/eclla_ui.tgz
    python scripts/export_ui_bundle.py --api-root https://api.example.org --output /tmp/ui   # a directory

The API host must send ``Access-Control-Allow-Origin`` for ``/static/`` (fonts, models):
see the nginx CUSTOM3 block in ECLLA_MIGRATION.md.
"""

import argparse
import html
import re
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# "/static/" followed by "<dir>/...": an asset in a subdirectory. Top-level pages
# ("/static/page.html", "/static/login.html") have no slash after the first segment, and a
# template placeholder ("/static/${page}.html") does not start with a directory name.
ASSET_RE = re.compile(r'(?<![A-Za-z0-9_.:/-])/static/(?=[A-Za-z0-9_-]+/)')


# only the main page has the generic title that the instance name replaces
TITLE_RE = re.compile(r'<title>eCatalogus</title>')


def api_root_from_registry(instance):
    import tomllib

    registry = tomllib.loads((BASE_DIR / 'scripts' / 'config' / 'instance_registry.toml').read_text(encoding='utf8'))
    try:
        return registry['instances'][instance]['public_url'].rstrip('/')
    except KeyError:
        sys.exit(f'No public_url for instance {instance!r} in scripts/config/instance_registry.toml')


def site_name_from_registry(instance):
    import tomllib

    registry = tomllib.loads((BASE_DIR / 'scripts' / 'config' / 'instance_registry.toml').read_text(encoding='utf8'))
    return registry['instances'][instance].get('site_name', '')


def rewrite(text, api_root, site_name=''):
    text = ASSET_RE.sub(f'{api_root}/static/', text)
    if site_name and TITLE_RE.search(text):
        text = TITLE_RE.sub(lambda m: f'<title>{html.escape(site_name)}</title>', text, count=1)
    return text


def build(static_dir, api_root, out_dir, site_name=''):
    pages = sorted(p for p in static_dir.glob('*.html') if p.is_file())
    if not pages:
        sys.exit(f'No *.html pages in {static_dir}; run collectstatic first.')
    rewritten = 0
    for page in pages:
        text = page.read_text(encoding='utf8')
        new = rewrite(text, api_root, site_name)
        rewritten += text != new
        (out_dir / page.name).write_text(new, encoding='utf8')
    return len(pages), rewritten


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--static-dir', default=str(BASE_DIR / 'static_assets'), help='collectstatic output (default: static_assets)')
    parser.add_argument('--instance', help='read the API root (public_url) from the instance registry')
    parser.add_argument('--api-root', help='API origin, e.g. https://api.eclla.ecatalogus.ispan.pl')
    parser.add_argument('--site-name', help='replaces the generic <title> of page.html (default: site_name of --instance)')
    parser.add_argument('--output', required=True, help='a .tgz/.tar.gz file, or a directory')
    args = parser.parse_args()

    api_root = (args.api_root or (api_root_from_registry(args.instance) if args.instance else '')).rstrip('/')
    if not api_root:
        sys.exit('Give --api-root or --instance.')

    site_name = args.site_name or (site_name_from_registry(args.instance) if args.instance else '')
    static_dir = Path(args.static_dir)
    output = Path(args.output).expanduser()
    as_archive = output.name.endswith(('.tgz', '.tar.gz'))

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / 'static' if as_archive else output
        out_dir.mkdir(parents=True, exist_ok=True)
        count, changed = build(static_dir, api_root, out_dir, site_name)
        if as_archive:
            with tarfile.open(output, 'w:gz') as archive:
                # members are relative to static/, i.e. `tar xzf x.tgz -C ~/site/static`
                for path in sorted(out_dir.iterdir()):
                    archive.add(path, arcname=path.name)
    size = output.stat().st_size / 1024 if as_archive else sum(f.stat().st_size for f in output.glob('*')) / 1024
    print(f'{count} pages ({changed} with rewritten asset URLs) -> {output} ({size:.0f} KB), assets from {api_root}')


if __name__ == '__main__':
    main()
