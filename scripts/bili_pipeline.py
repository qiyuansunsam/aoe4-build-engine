"""Download bilibili parts listed in .cache/bili/parts.json, extract + OCR frames, then free disk.

parts.json comes from a logged-in browser tab (bilibili answers scripted API calls with HTTP 412); each entry has
bvid, page, duration and a signed 1080p avc `url` (+ `backup`) that expires about two hours after it was issued.
Per part: curl the stream (Referer www.bilibili.com) to .cache/upcoming-videos/<bvid>_p<page>.mp4, run
scripts/extract_video_frames.py with GPU OCR, then delete the mp4 of parts longer than 20 minutes and every frame
no moment uses. Expired URLs are listed in .cache/bili/expired.json for a refresh from the browser.
Usage: python -X utf8 scripts/bili_pipeline.py [--ahead 2]
"""
import argparse, json, os, pathlib, subprocess, threading, queue, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
ROOT = pathlib.Path(__file__).resolve().parents[1]
VIDEOS = ROOT / '.cache/upcoming-videos'
FRAMES = ROOT / '.cache/upcoming-frames'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'

def vid_of(p):
    return f"{p['bvid']}_p{p['page']}"

MIRRORS = ['upos-sz-mirrorcosov.bilivideo.com', 'upos-sz-mirrorali.bilivideo.com', 'upos-sz-mirrorhw.bilivideo.com']
CHUNK = 8 * 1024 * 1024

def _get(url, start=None, end=None, timeout=60):
    headers = {'User-Agent': UA, 'Referer': 'https://www.bilibili.com/'}
    if start is not None: headers['Range'] = f'bytes={start}-{end}'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        return r.headers, r.read()

def download(p):
    """Parallel 8 MB range requests rotated over three mirrors (one connection is throttled to ~0.3 MB/s)."""
    target = VIDEOS / f'{vid_of(p)}.mp4'
    if target.exists() and target.stat().st_size > 1_000_000: return 'cached'
    u = urllib.parse.urlparse(p['url'])
    try:
        headers, _ = _get(p['url'], 0, 0)
        total = int(headers['Content-Range'].split('/')[-1])
    except Exception as exc:  # noqa: BLE001 - expired signature or blocked
        return f'failed: {exc}'[:120]
    tmp = target.with_suffix('.part')
    with open(tmp, 'wb') as fh: fh.truncate(total)
    def fetch(i):
        start = i * CHUNK; end = min(total, start + CHUNK) - 1
        for attempt in range(6):  # the issuing host is fast (~14 MB/s per chunk); other mirrors only as late fallbacks
            host = u.netloc if attempt < 4 else MIRRORS[(i + attempt) % len(MIRRORS)]
            mirror = u._replace(netloc=host).geturl()
            try:
                _, data = _get(mirror, start, end, timeout=20)
                if len(data) == end - start + 1:
                    with open(tmp, 'r+b') as fh: fh.seek(start); fh.write(data)
                    return True
            except Exception:  # noqa: BLE001 - retry on the next mirror
                time.sleep(1 + attempt)
        return False
    with ThreadPoolExecutor(max_workers=10) as pool:
        ok = all(pool.map(fetch, range((total + CHUNK - 1) // CHUNK)))
    if not ok: tmp.unlink(missing_ok=True); return 'failed: chunk'
    tmp.replace(target); return 'ok'

def prune(vid, keep_video):
    out = FRAMES / vid
    ms = json.loads((out / 'moments.json').read_text(encoding='utf-8'))
    keep = {t for m in ms for t in m['frames']}
    removed = 0
    for f in out.glob('s_*.jpg'):
        if int(f.stem.split('_')[1]) not in keep: f.unlink(); removed += 1
    if not keep_video: (VIDEOS / f'{vid}.mp4').unlink(missing_ok=True)
    return len(ms), removed

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--ahead', type=int, default=2)
    args = ap.parse_args()
    parts = json.loads((ROOT / '.cache/bili/parts.json').read_text(encoding='utf-8'))
    todo = [p for p in parts if not (FRAMES / vid_of(p) / 'moments.json').exists()]
    ready, expired = queue.Queue(maxsize=args.ahead), []

    def downloader():
        for p in todo:
            status = download(p)
            print(json.dumps({'id': vid_of(p), 'download': status}), flush=True)
            if status.startswith('failed'): expired.append(p); continue
            ready.put(p)
        ready.put(None)
    threading.Thread(target=downloader, daemon=True).start()

    env = {**os.environ, 'OCR_DML': '1'}
    py = str(ROOT / '.cache/ocr-venv/Scripts/python.exe')
    while (p := ready.get()) is not None:
        vid = vid_of(p); fps = '1' if p['duration'] <= 1000 else ('0.5' if p['duration'] <= 3000 else '0.33')
        r = subprocess.run([py, '-X', 'utf8', str(ROOT / 'scripts/extract_video_frames.py'), vid, '--fps', fps, '--workers', '3'],
                           env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=7200)
        last = [l for l in r.stdout.splitlines() if l.startswith('{')][-1:] or [r.stderr[-300:]]
        if r.returncode == 0:
            n, removed = prune(vid, keep_video=p['duration'] <= 1200)
            print(json.dumps({'id': vid, 'fps': fps, 'moments': n, 'prunedFrames': removed}), flush=True)
        else:
            print(json.dumps({'id': vid, 'error': last[0]}), flush=True)
    (ROOT / '.cache/bili/expired.json').write_text(json.dumps(expired, ensure_ascii=False), encoding='utf-8')
    print('ALLDONE expired=%d' % len(expired), flush=True)

if __name__ == '__main__':
    main()
