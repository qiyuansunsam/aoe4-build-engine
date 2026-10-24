"""Group each video's tooltip moments into distinct tooltips and split them into batches for frame-reading agents.

Input:  .cache/upcoming-frames/<id>/moments.json (scripts/extract_video_frames.py)
Output: .cache/frame-batches/<id>_<n>.json  ({"videoId", "batch", "clusters": [{"best": "s_00530.jpg" path, "timestamp": "mm:ss",
        "alternates": [paths], "names", "kind", "ocr"}]}) and prints an index the workflow script takes as args.
Clusters: one per OCR tooltip title (frames with different numbers kept as variants), untitled stat panels per number set, overview screens per name set.
Usage:  python -X utf8 scripts/plan_frame_batches.py <id> [<id> ...] [--size 30]
"""
import argparse, json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from extract_video_frames import anchor_lines  # noqa: E402
FRAMES = ROOT / '.cache/upcoming-frames'
OUT = ROOT / '.cache/frame-batches'

def words(text):
    return set(re.findall(r'[a-z一-鿿]{3,}', text.lower()))

def numbers(text):
    return frozenset(re.findall(r'(?<![\d.])\d{1,4}(?:\.\d+)?(?![\d.])', text))

def core_key(lines):
    """Tooltip identity from one frame's OCR lines: caps title + numbers inside a tight box around the anchor lines."""
    anchors = anchor_lines(lines)
    if not anchors:
        return None
    x0 = min(l[2][0] for l in anchors) - 160; x1 = max(l[2][2] for l in anchors) + 160
    y0 = min(l[2][1] for l in anchors) - 160; y1 = max(l[2][3] for l in anchors) + 120
    core = [l for l in lines if '@' not in l[0] and not re.search(r'\d:\d\d', l[0])
            and x0 <= (l[2][0] + l[2][2]) / 2 <= x1 and y0 <= (l[2][1] + l[2][3]) / 2 <= y1]
    titles = [l for l in core if re.fullmatch(r"[A-Z][A-Z' \-]{3,}", l[0].strip())]
    title = re.sub(r'[^A-Z]', '', min(titles, key=lambda l: l[2][1])[0]) if titles else ''
    nums = frozenset(n for l in core for n in re.findall(r'(?<![\d.])\d{1,4}(?:\.\d+)?(?![\d.])', l[0]))
    return title, nums

def mmss(t):
    return f'{t // 60}:{t % 60:02d}'

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('ids', nargs='+'); ap.add_argument('--size', type=int, default=30)
    ap.add_argument('--titles', help='regex over OCR titles (caps, no spaces); keep only matching titled tooltips')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for vid in args.ids:
        ms = json.loads((FRAMES / vid / 'moments.json').read_text(encoding='utf-8'))
        ocr = {}
        for line in (FRAMES / vid / 'ocr.jsonl').read_text(encoding='utf-8').splitlines():
            rec = json.loads(line); ocr[rec['t']] = rec['lines']
        # One cluster per tooltip title (all its tiers/cost variants together); untitled stat panels per number set;
        # overview screens per set of names. Each cluster keeps one frame per distinct number set, strongest first.
        groups = {}
        for m in ms:
            key = core_key(ocr.get(m['best'], [])) if m['kind'] == 'tooltip' else None
            if key and key[0]: gkey, sub = ('title', key[0]), key[1]
            elif key: gkey, sub = ('panel', key[1]), key[1]
            else: gkey, sub = ('overview', frozenset(m['names'])), frozenset()
            if args.titles and not (gkey[0] == 'title' and re.search(args.titles, gkey[1])): continue
            g = groups.setdefault(gkey, {'subs': {}, 'members': []})
            g['members'].append(m); g['subs'].setdefault(sub, []).append(m)
        rows = []
        for gkey, g in groups.items():
            reps = []
            for sub, members in sorted(g['subs'].items(), key=lambda kv: -len(kv[1])):
                reps.append(max(members, key=lambda m: (m['anchors'], m['nums'], len(m['frames']))))
            reps = reps[:4]
            frame = lambda m: str(FRAMES / vid / f's_{m["best"]:05d}.jpg').replace('\\', '/')
            rows.append({'title': gkey[1] if gkey[0] == 'title' else None, 'kind': gkey[0],
                         'best': frame(reps[0]), 'timestamp': mmss(reps[0]['best']),
                         'variants': [{'frame': frame(m), 'timestamp': mmss(m['best']), 'ocr': m['text'][:500]} for m in reps[1:]],
                         'seenAt': sorted({mmss(m['best']) for m in g['members']}, key=lambda s: [int(x) for x in s.split(':')])[:10],
                         'names': sorted({x for m in g['members'] for x in m['names']}), 'ocr': reps[0]['text'][:900]})
        rows.sort(key=lambda r: [int(x) for x in r['timestamp'].split(':')])
        for b in range(0, len(rows), args.size):
            path = OUT / f'{vid}_{b // args.size:02d}.json'
            path.write_text(json.dumps({'videoId': vid, 'batch': b // args.size, 'clusters': rows[b:b + args.size]}, ensure_ascii=False, indent=1), encoding='utf-8')
            index.append({'videoId': vid, 'batch': b // args.size, 'path': str(path).replace('\\', '/'), 'clusters': len(rows[b:b + args.size]),
                          'from': rows[b]['timestamp'], 'to': rows[min(b + args.size, len(rows)) - 1]['timestamp']})
        print(json.dumps({'id': vid, 'moments': len(ms), 'distinct': len(rows)}))
    (OUT / 'index.json').write_text(json.dumps(index, indent=1), encoding='utf-8')
    print(json.dumps(index))

if __name__ == '__main__':
    main()
