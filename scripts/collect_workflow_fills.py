"""Turn a finished Vikings/Scots workflow run into fill files for scripts/merge_checklist_fills.py.

Reads the workflow's final return value (saved JSON: a list of {batch, fills, observations} from the frame-read
workflow, or {key, verified, videos, sourcesChecked} from the web sweep) and writes:
  data/upcoming-civs/fills/frames-<videoId>-<batch>.json   accepted frame fills (verdict agreed / tiebreak-*)
  data/upcoming-civs/fills/web-<key>.json                  web fills whose source re-fetch confirmed them
  data/upcoming-civs/fills/rejected/<same name>.json       everything refused, with the reason
  data/upcoming-civs/observations.jsonl                     non-numeric observations, one per line
Frames cited by accepted fills are copied to data/upcoming-civs/frames/<videoId>/ as evidence.
Usage: python -X utf8 scripts/collect_workflow_fills.py <result.json> [--kind frames|web]
"""
import argparse, json, pathlib, re, shutil
ROOT = pathlib.Path(__file__).resolve().parents[1]
DIR = ROOT / 'data/upcoming-civs'
ACCEPT = {'agreed', 'tiebreak-kept', 'tiebreak-corrected', 'not-verified-text'}

def write(name, by, fills, rejected):
    (DIR / 'fills').mkdir(exist_ok=True); (DIR / 'fills/rejected').mkdir(exist_ok=True)
    if fills:
        (DIR / 'fills' / name).write_text(json.dumps({'transcribedBy': by, 'fills': fills}, ensure_ascii=False, indent=1), encoding='utf-8')
    if rejected:
        (DIR / 'fills/rejected' / name).write_text(json.dumps({'transcribedBy': by, 'fills': rejected}, ensure_ascii=False, indent=1), encoding='utf-8')

def source_id(url):
    """The evidence behind a web claim: the datamined records, a video we also read frames from, or the page itself.
    Re-citing the same evidence through a different URL must not count as a second, independent source."""
    if not url: return None
    if 'jeandogaming.com' in url: return 'jeando-datamined'
    m = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})', url)
    if m: return m.group(1)
    m = re.search(r'bilibili\.com/video/(BV\w+)(?:.*?[?&]p=(\d+))?', url)
    if m: return f'{m.group(1)}_p{m.group(2) or 1}'
    return url

def append_unique(path, rows):
    seen = set(path.read_text(encoding='utf-8').splitlines()) if path.exists() else set()
    with open(path, 'a', encoding='utf-8') as fh:
        for r in rows:
            line = json.dumps(r, ensure_ascii=False, sort_keys=True)
            if line not in seen: fh.write(line + '\n'); seen.add(line)

def evidence(frame, vid):
    src = pathlib.Path(frame)
    if not src.exists(): return frame
    dst = DIR / 'frames' / vid / src.name; dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists(): shutil.copy2(src, dst)
    return str(dst.relative_to(ROOT)).replace('\\', '/')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('result'); ap.add_argument('--kind', choices=['frames', 'web', 'gaps'], default='frames')
    args = ap.parse_args()
    data = json.loads(pathlib.Path(args.result).read_text(encoding='utf-8'))
    obs_path = DIR / 'observations.jsonl'; totals = {'accepted': 0, 'rejected': 0}
    for chunk in data:
        if not chunk: continue
        if args.kind == 'frames':
            vid, batch = chunk['batch']['videoId'], chunk['batch']['batch']
            ok, bad = [], []
            for f in chunk['fills']:
                f = {**f, 'videoId': vid}
                if f.get('verdict') in ACCEPT:
                    f['frame'] = evidence(f['frame'], vid)
                    f['verifiedBy'] = f.pop('verdict'); ok.append(f)
                else: bad.append(f)
            write(f'frames-{vid}-{batch:02d}.json', f'opus-agent frame read {vid}#{batch} + blind re-read', ok, bad)
            append_unique(obs_path, [{'videoId': vid, 'text': o} for o in chunk.get('observations', [])])
        elif args.kind == 'gaps':
            key = chunk['key']; ok, bad = [], []
            for f in chunk['fills']:
                f = dict(f)
                if f.get('verdict') in ACCEPT:
                    f['frame'] = evidence(f['frame'], f.get('videoId') or 'misc')
                    f['verifiedBy'] = f.pop('verdict'); ok.append(f)
                else: bad.append(f)
            write(f'gaps-{key}.json', f'opus-agent gap hunt {key} + blind re-read', ok, bad)
            append_unique(DIR / 'gap-findings.jsonl', [{'group': key, 'finding': x} for x in chunk.get('findings', [])]
                          + [{'group': key, 'notFound': x} for x in chunk.get('notFound', [])])
        else:
            key = chunk['key']; ok, bad = [], []
            for f in chunk.get('verified', []):
                f = dict(f)
                if f.get('verdict') == 'refuted' and f.get('correctedValue') is not None:
                    f['originalValue'], f['value'] = f['value'], f['correctedValue']; f['verdict'] = 'corrected-by-verifier'
                if f.get('verdict') in ('confirmed', 'corrected-by-verifier'):
                    f['verifiedBy'] = f.pop('verdict'); f['videoId'] = source_id(f.get('sourceUrl')); ok.append(f)
                else: bad.append(f)
            write(f'web-{key}.json', f'opus-agent web sweep {key} + source re-fetch', ok, bad)
            append_unique(obs_path, [{'sweep': key, 'video': v} for v in chunk.get('videos', [])])
        totals['accepted'] += len(ok); totals['rejected'] += len(bad)
    print(json.dumps(totals))

if __name__ == '__main__':
    main()
