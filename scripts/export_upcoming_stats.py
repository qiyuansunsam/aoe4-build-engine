"""Export the merged Vikings/Scots checklist as a compact stat table for the build engine.

Input:  data/upcoming-civs/checklist.json (scripts/merge_checklist_fills.py)
Output: data/upcoming-civs/stats.json
  {civ: {kind: {name: {"values": {field: value}, "status": {field: status}, "tiers": {label: {field: value}},
                       "origin": "text-sources" | "discovered"}}}}
`values` hold every field that is not unknown (status says how well it is supported); `tiers` hold the per-tier
readings of the datamined records (Hardened / Veteran / Elite / Early / age-named tiers), which are complete per tier,
plus frame readings for tiers the records lack. Context variants (upgrades, auras, discounts) stay in checklist.json.
Usage: python -X utf8 scripts/export_upcoming_stats.py
"""
import json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]
DIR = ROOT / 'data/upcoming-civs'
TIER = re.compile(r'^(Early|Hardened|Veteran|Elite|Feudal Age|Castle Age|Imperial Age)$')

def main():
    chk = json.loads((DIR / 'checklist.json').read_text(encoding='utf-8'))
    out = {'source': 'data/upcoming-civs/checklist.json', 'builtAt': chk.get('builtAt'), 'summary': chk['summary'], 'civilizations': {}}
    for it in chk['items']:
        entry = {'origin': it.get('origin', 'text-sources'), 'values': {}, 'status': {}, 'tiers': {}}
        for f in it['fields']:
            if f['status'] != 'unknown': entry['values'][f['field']] = f['value']
            entry['status'][f['field']] = f['status']
            for v in f.get('variants') or []:
                label = (v.get('variant') or '').strip()
                if TIER.match(label) and (v.get('confidence') == 'datamined' or label not in entry['tiers'] or f['field'] not in entry['tiers'][label]):
                    entry['tiers'].setdefault(label, {})[f['field']] = v['value']
        out['civilizations'].setdefault(it['civ'], {}).setdefault(it['kind'], {})[it['name']] = entry
    (DIR / 'stats.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    counts = {c: {k: len(v) for k, v in kinds.items()} for c, kinds in out['civilizations'].items()}
    print(json.dumps(counts))

if __name__ == '__main__':
    main()
