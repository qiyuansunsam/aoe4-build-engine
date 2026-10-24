"""Rebuild the verified result of a Vikings/Scots workflow run from its journal.jsonl.

The frame-read workflow (agents labelled read:/blind:/tiebreak:<videoId>:<batch>) and the web sweep
(sweep:<key>, verify:<key>:<url>) record every agent's return value in the run's journal. This applies the
same verdict rules as the workflow script, so the output equals the workflow's return value and can be fed to
scripts/collect_workflow_fills.py without copying it out of a notification.
Usage: python -X utf8 scripts/replay_workflow_journal.py <journal.jsonl> [...] -o result.json [--kind frames|web]
"""
import argparse, json, pathlib, re

def num(v):
    if isinstance(v, bool): return None
    if isinstance(v, (int, float)): return float(v)
    if isinstance(v, str) and re.fullmatch(r'\s*-?\d+(\.\d+)?\s*', v): return float(v)
    return None

def same(a, b):
    x, y = num(a), num(b)
    if x is not None and y is not None: return abs(x - y) < 1e-6
    return str(a).strip().lower() == str(b).strip().lower()

def load(paths):
    by_label = {}
    for p in paths:
        starts = {}
        for line in pathlib.Path(p).read_text(encoding='utf-8').splitlines():
            r = json.loads(line)
            if r.get('type') == 'started': starts[r['key']] = r.get('label')
            elif r.get('type') == 'result' and starts.get(r['key']):
                by_label.setdefault(starts[r['key']], []).append(r.get('result'))
    return by_label

def frames(by_label):
    out = []
    for label in sorted(l for l in by_label if l.startswith('read:')):
        _, vid, batch = label.rsplit(':', 2) if label.count(':') >= 2 else (None, None, None)
        read = by_label[label][-1] or {}
        fills = read.get('fills', [])
        blind = {x['index']: x for b in by_label.get(f'blind:{vid}:{batch}', []) if b for x in b.get('results', [])}
        tie = {x['index']: x for t in by_label.get(f'tiebreak:{vid}:{batch}', []) if t for x in t.get('results', [])}
        res = []
        for i, f in enumerate(fills):
            if num(f.get('value')) is None: res.append({**f, 'verdict': 'not-verified-text'}); continue
            g, t = blind.get(i), tie.get(i)
            if g and g.get('value') is not None and same(g['value'], f['value']): res.append({**f, 'verdict': 'agreed'})
            elif t and t.get('value') is not None and same(t['value'], f['value']): res.append({**f, 'verdict': 'tiebreak-kept', 'tieReason': t.get('reason')})
            elif t and t.get('value') is not None: res.append({**f, 'value': t['value'], 'originalValue': f['value'], 'verdict': 'tiebreak-corrected', 'tieReason': t.get('reason')})
            else: res.append({**f, 'verdict': 'rejected', 'blindValue': g.get('value') if g else None, 'tieReason': t.get('reason') if t else ''})
        out.append({'batch': {'videoId': vid, 'batch': int(batch)}, 'fills': res, 'observations': read.get('observations', [])})
    return out

def gaps(by_label):
    """Gap-hunt runs: hunt:<key> returns {fills, notFound, findings}; blind:/tiebreak:<key> re-read its numbers."""
    out = []
    for label in sorted(l for l in by_label if l.startswith('hunt:')):
        key = label.split(':', 1)[1]; r = by_label[label][-1] or {}
        fills = r.get('fills', [])
        blind = {x['index']: x for b in by_label.get(f'blind:{key}', []) if b for x in b.get('results', [])}
        tie = {x['index']: x for t in by_label.get(f'tiebreak:{key}', []) if t for x in t.get('results', [])}
        res = []
        for i, f in enumerate(fills):
            if num(f.get('value')) is None and str(f.get('value')).lower() != 'n/a': res.append({**f, 'verdict': 'not-verified-text'}); continue
            g, t = blind.get(i), tie.get(i)
            if g and g.get('value') is not None and same(g['value'], f['value']): res.append({**f, 'verdict': 'agreed'})
            elif t and t.get('value') is not None and same(t['value'], f['value']): res.append({**f, 'verdict': 'tiebreak-kept', 'tieReason': t.get('reason')})
            elif t and t.get('value') is not None: res.append({**f, 'value': t['value'], 'originalValue': f['value'], 'verdict': 'tiebreak-corrected', 'tieReason': t.get('reason')})
            else: res.append({**f, 'verdict': 'rejected', 'blindValue': g.get('value') if g else None, 'tieReason': t.get('reason') if t else ''})
        out.append({'key': key, 'fills': res, 'notFound': r.get('notFound', []), 'findings': r.get('findings', [])})
    return out

def web(by_label):
    out = []
    for label in sorted(l for l in by_label if l.startswith('sweep:')):
        key = label.split(':', 1)[1]; r = by_label[label][-1] or {}
        verdicts = {}
        for vl in (l for l in by_label if l.startswith(f'verify:{key}:')):
            for v in by_label[vl]:
                for x in (v or {}).get('results', []): verdicts[x['index']] = x
        verified = [{**f, 'verdict': verdicts[i]['verdict'] if i in verdicts else 'unchecked',
                     'verdictReason': verdicts[i].get('reason', '') if i in verdicts else '',
                     'correctedValue': verdicts[i].get('correctedValue') if i in verdicts else None} for i, f in enumerate(r.get('fills', []))]
        out.append({'key': key, 'fills': r.get('fills', []), 'verified': verified, 'videos': r.get('videos', []), 'sourcesChecked': r.get('sourcesChecked', [])})
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('journals', nargs='+'); ap.add_argument('-o', required=True)
    ap.add_argument('--kind', choices=['frames', 'web', 'gaps'], default='frames')
    args = ap.parse_args()
    by_label = load(args.journals)
    data = {'frames': frames, 'web': web, 'gaps': gaps}[args.kind](by_label)
    pathlib.Path(args.o).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    counts = {}
    for c in data:
        for f in c.get('verified' if args.kind == 'web' else 'fills', []): counts[f.get('verdict')] = counts.get(f.get('verdict'), 0) + 1
    print(json.dumps({'chunks': len(data), **counts}))

if __name__ == '__main__':
    main()
