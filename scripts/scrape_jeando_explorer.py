"""Scrape jeandogaming.com's AoE4 explorer ("Figures taken from the game files.") for Vikings and Scots.

The explorer is the only public source with datamined numbers for the 17.0 civs before release. Every unit tier,
building and technology page is fetched in English, parsed into fields, and saved with its rendered text so each
number stays traceable: data/upcoming-civs/raw/jeando/<civ>/<kind>/<id>.json (+ _index.json).
Usage: python -X utf8 scripts/scrape_jeando_explorer.py [--civ vikings,scots] [--delay 0.5]
"""
import argparse, html, json, pathlib, re, time, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/upcoming-civs/raw/jeando'
BASE = 'https://jeandogaming.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode('utf-8', errors='replace')

def text_of(fragment):
    fragment = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', fragment, flags=re.S)
    t = html.unescape(re.sub(r'<[^>]+>', '|', fragment))
    return re.sub(r'\|(\s*\|)+', '|', t).strip('|')

def parse(page):
    i = page.find('<h1'); j = page.find('self.__next_f.push', i)
    main = page[i:j if j > 0 else i + 80000]
    out = {'title': text_of(main[:main.find('</h1>') + 5])}
    m = re.search(r'</h1><span[^>]*>([^<]+)</span>', main); out['classes'] = html.unescape(m.group(1)) if m else None
    costs = {}
    for res, val in re.findall(r'<div class="flex items-center gap-1" title="([A-Za-z ]+)">.*?<span[^>]*>([^<]+)</span>', main[:20000], flags=re.S):
        costs.setdefault(res.lower(), val.strip())
    out['costs'] = costs
    out['text'] = text_of(main)
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--civ', default='vikings,scots'); ap.add_argument('--delay', type=float, default=0.5)
    args = ap.parse_args()
    for civ in args.civ.split(','):
        url, page = get(f'{BASE}/en/aoe4/explorer/{civ}')
        links = sorted(set(re.findall(rf'href="(/en/aoe4/explorer/{civ}/(units|buildings|technologies)/([A-Za-z0-9_\-]+))"', page)))
        # each unit page links its tier siblings via the I-IV buttons only client-side, so add _1.._4 variants explicitly
        extra = set()
        for href, kind, ident in links:
            m = re.match(r'(.*_)(\d)(_[a-z]+)$', ident)
            if kind == 'units' and m:
                for tier in '1234': extra.add((f'/en/aoe4/explorer/{civ}/units/{m.group(1)}{tier}{m.group(3)}', 'units', f'{m.group(1)}{tier}{m.group(3)}'))
        todo = sorted(set(links) | extra)
        index = []
        for href, kind, ident in todo:
            target = OUT / civ / kind / f'{ident}.json'
            if target.exists():
                index.append(json.loads(target.read_text(encoding='utf-8')) | {'text': None}); continue
            try:
                final, page = get(BASE + href)
            except Exception as exc:  # noqa: BLE001 - tier that does not exist returns 404
                index.append({'id': ident, 'kind': kind, 'error': str(exc)[:120]}); continue
            if not final.rstrip('/').endswith(ident):
                index.append({'id': ident, 'kind': kind, 'redirectedTo': final}); continue
            rec = {'id': ident, 'kind': kind, 'civ': civ, 'url': final, 'fetchedAt': time.strftime('%Y-%m-%dT%H:%M:%S'), **parse(page)}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
            index.append(rec | {'text': None})
            print(json.dumps({'civ': civ, 'id': ident, 'title': rec['title'], 'costs': rec['costs']}, ensure_ascii=False), flush=True)
            time.sleep(args.delay)
        (OUT / civ).mkdir(parents=True, exist_ok=True)
        (OUT / civ / '_index.json').write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding='utf-8')
        print(civ, 'pages', len(index), flush=True)

if __name__ == '__main__':
    main()
