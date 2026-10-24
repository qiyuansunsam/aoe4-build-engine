"""Search the OCR text of every extracted video frame (.cache/upcoming-frames/<id>/ocr.jsonl).

Prints one line per hit: video id, mm:ss, whether the frame image still exists, and the matching OCR lines.
Frames that were pruned can be re-extracted from .cache/upcoming-videos/<id>.mp4 with
  ffmpeg -ss <seconds> -i .cache/upcoming-videos/<id>.mp4 -frames:v 1 -q:v 3 <out>.jpg
Usage: python -X utf8 scripts/search_frames.py "<regex>" [--video id] [--limit 40] [--context]
"""
import argparse, json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAMES = ROOT / '.cache/upcoming-frames'

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('pattern'); ap.add_argument('--video'); ap.add_argument('--limit', type=int, default=40)
    ap.add_argument('--context', action='store_true', help='print every OCR line of the hit frame')
    args = ap.parse_args()
    rx = re.compile(args.pattern, re.I); n = 0; last = {}
    for ocr in sorted(FRAMES.glob('*/ocr.jsonl')):
        vid = ocr.parent.name
        if args.video and vid != args.video: continue
        for line in ocr.read_text(encoding='utf-8').splitlines():
            rec = json.loads(line); hits = [l[0] for l in rec['lines'] if rx.search(l[0])]
            if not hits or rec['t'] - last.get(vid, -99) <= 3: continue  # one hit per few seconds
            last[vid] = rec['t']; frame = FRAMES / vid / f's_{rec["t"]:05d}.jpg'
            text = ' | '.join(l[0] for l in rec['lines']) if args.context else ' | '.join(hits)
            print(f'{vid} {rec["t"] // 60}:{rec["t"] % 60:02d} {"frame" if frame.exists() else "pruned"} {str(frame).replace(chr(92), "/")} :: {text[:400]}')
            n += 1
            if n >= args.limit: return

if __name__ == '__main__':
    main()
