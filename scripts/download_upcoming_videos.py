"""Download the Vikings/Scots preview videos (1080p video-only + audio) for frame extraction.

Videos and audio go to .cache/upcoming-videos/<id>.mp4 / <id>.m4a (not committed). Frames are read from these by
scripts/extract_video_frames.py. Usage: python -X utf8 scripts/download_upcoming_videos.py [--only id1,id2] [--audio-only]
"""
import argparse, json, pathlib, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/upcoming-videos'
DEFAULT = ['nd74LibluQ0', 'c_oaynL66jY', 'uNw-K34ZDPs', 'qlogYcWhKEU', 'ehO1BOe7wG8', 'wzT5WTqIIU4',
           'vKPxGYSbN2Q', 'xjYytU_zXTA', 'qARfRxyhRhA', 'OCna8RhsP9E']

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--only'); ap.add_argument('--audio-only', action='store_true')
    args = ap.parse_args()
    from yt_dlp import YoutubeDL
    OUT.mkdir(parents=True, exist_ok=True)
    ids = args.only.split(',') if args.only else DEFAULT
    for vid in ids:
        url = f'https://www.youtube.com/watch?v={vid}'
        jobs = [('m4a', '140/bestaudio[ext=m4a]/bestaudio')]
        if not args.audio_only:
            jobs.insert(0, ('mp4', '299/137/bestvideo[height<=1080][vcodec^=avc1]/bestvideo[height<=1080]'))
        for ext, fmt in jobs:
            target = OUT / f'{vid}.{ext}'
            if target.exists() and target.stat().st_size > 1_000_000:
                print(json.dumps({'id': vid, 'ext': ext, 'status': 'cached'}), flush=True); continue
            opts = {'format': fmt, 'outtmpl': str(OUT / f'%(id)s.{ext}'), 'quiet': True, 'no_warnings': True,
                    'noprogress': True, 'cachedir': str(ROOT / '.cache/yt-dlp'), 'concurrent_fragment_downloads': 4,
                    'retries': 5, 'fragment_retries': 10}
            try:
                with YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                print(json.dumps({'id': vid, 'ext': ext, 'status': 'ok', 'title': info.get('title'),
                                  'height': info.get('height'), 'duration': info.get('duration')}, ensure_ascii=False), flush=True)
            except Exception as exc:  # noqa: BLE001 - report and continue
                print(json.dumps({'id': vid, 'ext': ext, 'status': 'error', 'error': str(exc)[:300]}), flush=True)
            time.sleep(3)

if __name__ == '__main__':
    main()
