"""Extract 1 fps frames from a downloaded preview video and OCR them to find stat tooltips and unit cards.

Input:  .cache/upcoming-videos/<id>.mp4 (scripts/download_upcoming_videos.py)
Output: .cache/upcoming-frames/<id>/s_<second>.jpg  (frame at that second, full 1080p)
        .cache/upcoming-frames/<id>/ocr.jsonl       ({"t": second, "lines": [[text, score, [x0,y0,x1,y1]], ...]})
        .cache/upcoming-frames/<id>/moments.json    (runs of consecutive stat-looking frames, best frame per run)
Usage:  python -X utf8 scripts/extract_video_frames.py <id> [--fps 1] [--workers 12] [--skip-extract]
"""
import argparse, json, os, pathlib, re, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
ROOT = pathlib.Path(__file__).resolve().parents[1]
VIDEOS = ROOT / '.cache/upcoming-videos'
FRAMES = ROOT / '.cache/upcoming-frames'

STAT_WORDS = ['health', 'hitpoints', 'armor', 'armour', 'damage', 'attack', 'speed', 'range', 'cost', 'population',
              'train', 'research', 'requires', 'produced', 'produces', 'strong against', 'weak against', 'seconds',
              'hardened', 'veteran', 'elite', 'upgrade', 'build time', 'gather', 'bonus', 'per second', 'landmark',
              'line of sight', 'sight', 'garrison', 'influence', 'tooltip', 'age i', 'age ii', 'age iii', 'age iv',
              'feudal', 'castle', 'imperial', 'dark age', 'unlocks', 'technology', 'increases', 'reduces']
NAMES = ['bondi', 'berserker', 'hirdman', 'hirdmen', 'jylland', 'skane', 'skåne', 'shield maiden', 'volur', 'völur', 'longship',
         'drakkar', 'knarr', 'longhouse', 'sacred grove', 'saga', 'konungr', 'baugr', 'valdemar', 'gullinn', 'gullínn',
         'kongens', 'rikets', 'ríkets', 'danevirke', 'ulfberht', 'leikr', 'hagl', 'hamrammr', 'farmathr', 'folkekirken',
         'turnshoes', 'sunstones', 'leding', 'snaerisspjot', 'extra oars', 'ship barding', 'reinforced keel', 'bee skep',
         'farmstead', 'pasture', 'smithy', 'hamingja', 'northern migration',
         'highland', 'cattle', 'pikeman', 'cateran', 'gallowglass', 'border reiver', 'reiver', 'kirkman', 'ghillie',
         'tacksman', 'lochaber', 'tower house', 'mustering', 'muster', 'fishpond', 'barmkin', 'basket-hilted', 'birlinn',
         'fermtoun', 'feuds aside', "lion's duty", 'snaphance', 'stew pond', "wallace", 'we stand alone', 'seven sisters',
         'abbey of the isles', 'stone of destiny', 'snowdoun', 'tower of skye', 'dhun', 'dhùn', 'three loch', 'clan traditions',
         "cateran's trail", 'fortified tower']

def extract(vid, fps):
    out = FRAMES / vid; out.mkdir(parents=True, exist_ok=True)
    if any(out.glob('s_*.jpg')):
        return out
    tmp = out / 'raw_%05d.jpg'
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-i', str(VIDEOS / f'{vid}.mp4'),
           '-vf', f'fps={fps}', '-q:v', '3', str(tmp)]
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)
    for p in sorted(out.glob('raw_*.jpg')):  # ffmpeg fps filter: frame n (1-based) is centred at (n-1)/fps seconds
        n = int(p.stem.split('_')[1]); sec = int(round((n - 1) / fps))
        target = out / f's_{sec:05d}.jpg'
        if target.exists(): p.unlink()
        else: p.rename(target)
    return out

_ENGINE = None
def _ocr_one(path):
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        if os.environ.get('OCR_DML'):  # GPU via DirectML; run with .cache/ocr-venv (onnxruntime-directml)
            _ENGINE = RapidOCR(det_use_dml=True, rec_use_dml=True, cls_use_dml=True)
        else:
            _ENGINE = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
    res, _ = _ENGINE(str(path), use_cls=False)
    lines = []
    for box, text, score in (res or []):
        xs = [pt[0] for pt in box]; ys = [pt[1] for pt in box]
        lines.append([text, round(float(score), 3), [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]])
    return int(path.stem.split('_')[1]), lines

def score_lines(lines):
    text = ' '.join(l[0] for l in lines).lower()
    stat = sum(1 for w in STAT_WORDS if w in text)
    names = sorted({n for n in NAMES if n in text})
    nums = len(re.findall(r'(?<![\d:])\d{1,4}(?:\.\d+)?(?![\d:])', text))
    return stat, names, nums, text

# Phrases that only occur inside AoE4 tooltips / stat panels (English and Chinese UI), never in the HUD;
# a frame needs two of them. Chat lines (containing '@') are ignored.
ANCHORS = [re.compile(p, re.I) for p in [
    r'unique to (the )?(vikings|scots)', r'\bvs\.? ?(melee|ranged|fire|siege)', r'attack speed', r'tiles ?(/s|range)',
    r'movement speed', r'^\+?\d{1,3}(\.\d)?s$', r'(light|heavy) (melee )?(infantry|cavalry)', r'ranged (infantry|cavalry)',
    r'(military|economic|religious|defensive|naval|technology|landmark) (building|unit|technology)', r'produced (at|by)',
    r'^requires', r'research', r'^health$', r'^armor$', r'^attack$', r'bonus damage', r'line of sight', r'strong against',
    r'weak against', r'counter(ed)? by', r'^\+ ?\w', r'^- ?\w', r'unlocks', r'construction', r'garrison',
    r'维京独有|苏格兰独有|独有', r'近战护甲|远程护甲|护甲', r'生命值|血量', r'攻击速度|攻速', r'移动速度|移速', r'射程', r'训练|研究|建造',
    r'克制|被克制', r'对.{0,4}(步兵|骑兵|建筑)']]

def anchor_lines(lines):
    return [l for l in lines if '@' not in l[0] and any(a.search(l[0].strip()) for a in ANCHORS)]

def tooltip_lines(lines, anchors):
    x0 = min(l[2][0] for l in anchors) - 350; x1 = max(l[2][2] for l in anchors) + 350
    y0 = min(l[2][1] for l in anchors) - 250; y1 = max(l[2][3] for l in anchors) + 250
    return [l for l in lines if '@' not in l[0] and x0 <= (l[2][0] + l[2][2]) / 2 <= x1 and y0 <= (l[2][1] + l[2][3]) / 2 <= y1]

def moments(records, fps=1):
    rows = []
    for t, lines in sorted(records.items()):
        anchors = anchor_lines(lines)
        clean = [l for l in lines if '@' not in l[0]]
        all_names = sorted({n for n in NAMES if n in ' '.join(l[0] for l in clean).lower()})
        if len(anchors) >= 2:
            tip = tooltip_lines(lines, anchors); kind = 'tooltip'
        elif len(all_names) >= 3:  # overview screens: saga list, lobby civ card, tech tree
            tip = clean; kind = 'overview'
        else:
            continue
        text = ' | '.join(l[0] for l in tip)
        rows.append({'t': t, 'kind': kind, 'anchors': len(anchors), 'names': sorted({n for n in NAMES if n in text.lower()}),
                     'nums': len(re.findall(r'\d+(?:\.\d+)?', text)), 'text': text})
    def tokens(r):
        return set(re.findall(r'[a-z一-鿿]{3,}|\d+(?:\.\d+)?', r['text'].lower()))
    gap = max(2, 2 / fps)
    runs, cur = [], []
    for r in rows:
        if cur:
            a, b = tokens(cur[-1]), tokens(r)
            same = len(a & b) / max(1, len(a | b))
            if r['t'] - cur[-1]['t'] > gap or r['kind'] != cur[-1]['kind'] or same < 0.6:
                runs.append(cur); cur = []
        cur.append(r)
    if cur: runs.append(cur)
    out = []
    for run in runs:
        best = max(run, key=lambda r: (r['anchors'] * 2 + len(r['names']) * 3 + min(r['nums'], 30), -r['t']))
        out.append({'start': run[0]['t'], 'end': run[-1]['t'], 'best': best['t'], 'kind': best['kind'],
                    'names': sorted({n for r in run for n in r['names']}), 'anchors': best['anchors'], 'nums': best['nums'],
                    'text': best['text'][:1500], 'frames': [r['t'] for r in run]})
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('vid'); ap.add_argument('--fps', type=float, default=1)
    ap.add_argument('--workers', type=int, default=12); ap.add_argument('--skip-extract', action='store_true')
    ap.add_argument('--moments-only', action='store_true', help='recompute moments.json from an existing ocr.jsonl')
    args = ap.parse_args()
    if args.moments_only:
        out = FRAMES / args.vid; done = {}
        for line in (out / 'ocr.jsonl').read_text(encoding='utf-8').splitlines():
            rec = json.loads(line); done[rec['t']] = rec['lines']
        ms = moments(done, args.fps)
        (out / 'moments.json').write_text(json.dumps(ms, ensure_ascii=False, indent=1), encoding='utf-8')
        print(json.dumps({'id': args.vid, 'moments': len(ms), 'frames': len(done)})); return
    out = FRAMES / args.vid if args.skip_extract else extract(args.vid, args.fps)
    ocr_path = out / 'ocr.jsonl'
    done = {}
    if ocr_path.exists():
        for line in ocr_path.read_text(encoding='utf-8').splitlines():
            rec = json.loads(line); done[rec['t']] = rec['lines']
    todo = [p for p in sorted(out.glob('s_*.jpg')) if int(p.stem.split('_')[1]) not in done]
    print(json.dumps({'id': args.vid, 'frames': len(done) + len(todo), 'todo': len(todo)}), flush=True)
    with open(ocr_path, 'a', encoding='utf-8') as fh, ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, (t, lines) in enumerate(pool.map(_ocr_one, todo, chunksize=4)):
            done[t] = lines; fh.write(json.dumps({'t': t, 'lines': lines}, ensure_ascii=False) + '\n')
            if i % 200 == 0: fh.flush(); print(f'{args.vid} ocr {i}/{len(todo)}', flush=True)
    ms = moments(done, args.fps)
    (out / 'moments.json').write_text(json.dumps(ms, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'id': args.vid, 'moments': len(ms), 'frames': len(done)}), flush=True)

if __name__ == '__main__':
    main()
