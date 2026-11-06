"""Extract the game icons the catalog names but the local art folder lacks, from the installed UIArt.sga.

The first extraction was made on Steam build 24231237, before Vikings, Scots and several variant civilizations had
art in the archive. This script lists every catalog record whose `icon` path has no PNG under
games/kb/aoe4/extract/UIArt, adds those paths to tools/icon-extract/requested.json, extracts exactly those files with
tools/icon-extract (read only on the installation) and decodes each .rrtex to PNG beside it with the Essence CLI.
Then run: python -X utf8 scripts/enrich_catalog.py && python -X utf8 scripts/test_catalog_enrichment.py

Usage: python -X utf8 scripts/extract_missing_icons.py
"""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT.parent / 'games/kb/aoe4/extract/UIArt'
ARCHIVE = pathlib.Path('C:/Program Files (x86)/Steam/steamapps/common/Age of Empires IV/cardinal/archives/UIArt.sga')
CLI = ROOT.parent / 'games/tools/aoe4-essence/AOEMods.Essence.CLI/bin/Release/net6.0/AOEMods.Essence.CLI.exe'
PROJECT = ROOT / 'tools/icon-extract/IconExtract.csproj'
REQUESTED = ROOT / 'tools/icon-extract/requested.json'


def run(cmd, timeout):
    print('>', ' '.join(str(c) for c in cmd)[:200], flush=True)
    return subprocess.run([str(c) for c in cmd], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)


def main():
    catalog = json.loads((ROOT / 'data/game-catalog.json').read_text(encoding='utf-8'))
    missing = set()
    for kind in ('units', 'buildings', 'technologies', 'civilizations'):
        for record in catalog[kind]:
            icon = (record.get('icon') or '').replace('\\', '/').strip('/')
            if icon and not (RAW / 'ui/icons' / (icon + '.png')).is_file():
                missing.add('ui/icons/' + icon + '.rrtex')
    print(len(missing), 'icon paths without local art')
    if not missing:
        return
    requested = sorted(set(json.loads(REQUESTED.read_text(encoding='utf-8'))) | missing)
    REQUESTED.write_text(json.dumps(requested, indent=1), encoding='utf-8')
    batch = ROOT / 'tools/icon-extract/obj/missing.json'
    batch.parent.mkdir(parents=True, exist_ok=True)
    batch.write_text(json.dumps(sorted(missing)), encoding='utf-8')

    dll = ROOT / 'tools/icon-extract/bin/Release/net8.0/IconExtract.dll'
    if not dll.is_file():
        built = run(['dotnet', 'build', PROJECT, '-c', 'Release', '-p:NoWarn=CA2252'], 300)
        if built.returncode or not dll.is_file():
            sys.exit('IconExtract build failed:\n' + built.stdout[-1500:] + built.stderr[-500:])
    out = run(['dotnet', dll, ARCHIVE, RAW, batch], 600)
    print(out.stdout.strip().splitlines()[-1] if out.stdout.strip() else out.stderr[-400:])
    decoded = failed = 0
    for path in sorted(missing):
        source = RAW / path
        if not source.is_file():
            continue
        target = source.with_suffix('.png')
        result = run([CLI, 'rrtex-decode', source, target], 60) if not target.is_file() else None
        if target.is_file() and target.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n':
            decoded += 1
        else:
            failed += 1
            print('  not decoded:', path, (result.stderr or result.stdout)[-160:] if result else '')
    absent = sum(1 for p in missing if not (RAW / p).is_file())
    print(f'{decoded} decoded to PNG, {failed} failed, {absent} not in the archive')


if __name__ == '__main__':
    main()
