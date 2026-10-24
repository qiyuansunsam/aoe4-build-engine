"""Extract the datamined records jeandogaming.com embeds in its explorer pages (React Server Component payload).

Each explorer page carries JSON records for the civ's units (and, on building/tech pages, buildings and
technologies): {"id": "unit_crossbowman_3_vik", "name", "className", "age", "hitpoints", "speed", "sight",
"armor": {...}, "costs": {"food", "gold", "time", ...}, "weapons": [...], "unitTypes": [...], ...}. The site labels
these "Figures taken from the game files". Fetches one unit, one building and one technology page per civ (plus the
pages they link), merges records by id, and writes data/upcoming-civs/raw/jeando/<civ>_dataset.json.
Usage: python -X utf8 scripts/extract_jeando_dataset.py [--civ vikings,scots]
"""
import argparse, json, pathlib, re, time, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/upcoming-civs/raw/jeando'
BASE = 'https://jeandogaming.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode('utf-8', errors='replace')

def payload(page):
    dec, parts = json.JSONDecoder(), []
    for m in re.finditer(r'self\.__next_f\.push\(\[1,', page):
        try:
            val, _ = dec.raw_decode(page, m.end())
            if isinstance(val, str): parts.append(val)
        except ValueError:
            pass
    return ''.join(parts)

def records(text):
    dec, out = json.JSONDecoder(), {}
    for m in re.finditer(r'\{"id":"', text):
        try:
            obj, _ = dec.raw_decode(text, m.start())
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get('id') and any(k in obj for k in ('costs', 'hitpoints', 'effects', 'civKey')):
            prev = out.get(obj['id'], {})
            out[obj['id']] = {**prev, **obj} if len(json.dumps(obj)) >= len(json.dumps(prev)) else {**obj, **prev}
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--civ', default='vikings,scots'); args = ap.parse_args()
    for civ in args.civ.split(','):
        seen_pages, recs, queue = set(), {}, [f'{BASE}/en/aoe4/explorer/{civ}']
        # one page of each kind is enough when it embeds the full lists; follow links of kinds not yet covered
        while queue and len(seen_pages) < 12:
            url = queue.pop(0)
            if url in seen_pages: continue
            final, page = get(url); seen_pages.add(url); seen_pages.add(final)
            found = records(payload(page))
            recs.update({k: {**recs.get(k, {}), **v} for k, v in found.items()})
            for kind in ('buildings', 'techs', 'units'):
                links = re.findall(rf'href="(/en/aoe4/explorer/{civ}/{kind}/[^"]+)"', page)
                if links and not any(f'/{kind}/' in p for p in seen_pages): queue.append(BASE + links[0])
            print(json.dumps({'civ': civ, 'page': final, 'records': len(found), 'total': len(recs)}), flush=True)
            time.sleep(0.5)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f'{civ}_dataset.json').write_text(json.dumps({'source': f'{BASE}/en/aoe4/explorer/{civ}', 'note': 'jeandogaming.com explorer, "Figures taken from the game files."',
                                                              'fetchedAt': time.strftime('%Y-%m-%dT%H:%M:%S'), 'pages': sorted(seen_pages), 'records': recs},
                                                             ensure_ascii=False, indent=1), encoding='utf-8')
        kinds = {}
        for r in recs.values(): kinds[r['id'].split('_')[0]] = kinds.get(r['id'].split('_')[0], 0) + 1
        print(civ, len(recs), kinds, flush=True)

if __name__ == '__main__':
    main()
