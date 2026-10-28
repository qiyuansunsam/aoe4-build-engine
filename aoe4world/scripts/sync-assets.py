"""Cache the published AoE4 World catalog and authentic game artwork locally.

Uses the public GitHub repositories when the data website rejects automated
requests. Bounded concurrency; successful files are reused on subsequent runs.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'data/catalog'
PUBLIC = ROOT / 'public/assets'
DATA = 'https://raw.githubusercontent.com/aoe4world/data/main/'
FLAGS = 'https://raw.githubusercontent.com/aoe4world/overlay/main/src/assets/flags/'
for directory in (CATALOG, PUBLIC / 'flags', PUBLIC / 'icons'):
    directory.mkdir(parents=True, exist_ok=True)

def fetch(url, target):
    if target.exists() and target.stat().st_size:
        return
    request = Request(url, headers={'User-Agent': 'AoE4TrueStats/0.2 (local asset cache)'})
    with urlopen(request, timeout=30) as response:
        body = response.read()
    target.write_bytes(body)

def load(name, remote):
    target = CATALOG / name
    fetch(DATA + remote, target)
    return json.loads(target.read_text(encoding='utf-8'))

civs = load('civs-index.json', 'civilizations/civs-index.json')
units = load('units.json', 'units/all.json')['data']
buildings = load('buildings.json', 'buildings/all.json')['data']
technologies = load('technologies.json', 'technologies/all.json')['data']
fetch(DATA + 'README.md', CATALOG / 'SOURCE.md')
jobs, icons, pbgids = {}, {}, {}
for civ in civs.values():
    jobs[PUBLIC / 'flags' / (civ['id'] + '.png')] = FLAGS + civ['id'] + '.png'
jobs[PUBLIC / 'flags/unknown.png'] = FLAGS + 'unknown.png'
for item in units + buildings + technologies:
    original = item.get('icon')
    if not original:
        continue
    remote_path = original.split('data.aoe4world.com/')[-1]
    filename = remote_path.removeprefix('images/').replace('/', '--')
    local = '/assets/icons/' + filename
    jobs[PUBLIC / 'icons' / filename] = DATA + remote_path
    icons[original] = local
    icons[remote_path] = local
    pbgids[str(item['pbgid'])] = local

# Summary records use Relic icon paths. An exact known PBGID provides evidence
# for an alias; ambiguous paths are intentionally left unresolved.
alias_candidates = {}
def collect_aliases(value):
    if isinstance(value, dict):
        icon = value.get('icon')
        local = pbgids.get(str(value.get('pbgid', '')))
        if isinstance(icon, str) and icon.startswith('icons/') and local:
            alias_candidates.setdefault(icon, set()).add(local)
        for child in value.values():
            collect_aliases(child)
    elif isinstance(value, list):
        for child in value:
            collect_aliases(child)
for sample in [*(ROOT / 'data/samples').glob('*.json'), *(ROOT / 'data/strategy/summaries').glob('*.json')]:
    collect_aliases(json.loads(sample.read_text(encoding='utf-8-sig')))
for raw_icon, candidates in alias_candidates.items():
    if len(candidates) == 1:
        local = next(iter(candidates))
        icons[raw_icon] = local
        icons['https://data.aoe4world.com/' + raw_icon + '.png'] = local

failures = []
with ThreadPoolExecutor(max_workers=5) as pool:
    futures = {pool.submit(fetch, url, path): (url, path) for path, url in jobs.items()}
    for index, future in enumerate(as_completed(futures), 1):
        try:
            future.result()
        except Exception as error:
            failures.append({'url': futures[future][0], 'error': str(error)})
        if index % 100 == 0:
            print(f'Cached {index}/{len(jobs)} assets', flush=True)

normalized = []
for unit in units:
    row = {key: unit.get(key) for key in ('id', 'baseId', 'name', 'pbgid', 'age', 'description', 'classes', 'displayClasses', 'unique', 'costs', 'hitpoints', 'weapons', 'armor', 'movement', 'producedBy')}
    row['civs'] = [civs[c]['id'] for c in unit['civs'] if c in civs]
    row['icon'] = icons.get(unit.get('icon'))
    row['sourceIcon'] = unit.get('icon')
    normalized.append(row)

manifest = {
    'source': 'https://github.com/aoe4world/data',
    'flagsSource': 'https://github.com/aoe4world/overlay/tree/main/src/assets/flags',
    'generatedAt': datetime.now(timezone.utc).isoformat(),
    'catalogSha256': hashlib.sha256((CATALOG / 'units.json').read_bytes()).hexdigest(),
    'civilizations': {c['id']: {'name': c['name'], 'flag': '/assets/flags/' + c['id'] + '.png'} for c in civs.values()},
    'units': normalized, 'icons': icons, 'pbgids': pbgids,
    'counts': {'civilizations': len(civs), 'unitVariants': len(units), 'buildings': len(buildings), 'technologies': len(technologies), 'assets': len(jobs)},
    'failures': failures,
    'attribution': 'Age of Empires IV © Microsoft Corporation. Game data and artwork via AoE4 World. Subject to Microsoft Game Content Usage Rules. Not endorsed by Microsoft.'
}
(PUBLIC / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
(PUBLIC / 'ATTRIBUTION.txt').write_text(manifest['attribution'] + '\nhttps://www.xbox.com/en-US/developers/rules\nhttps://github.com/aoe4world/data#license-and-rights\nhttps://github.com/aoe4world/overlay\n', encoding='utf-8')
print(json.dumps({'counts': manifest['counts'], 'failures': failures}, indent=2))
