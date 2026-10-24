"""Download metadata and auto-generated transcripts for the Vikings/Scots preview videos.

Input: data/upcoming-civs/videos.json  -> {"videos":[{"url":..., "title":..., "channel":..., "note":...}]}
Output: data/upcoming-civs/transcripts/<video id>.json  (title, channel, uploadDate, description, chapters,
        duration, language, segments:[{"start": seconds, "end": seconds, "text": ...}]) and <id>.txt
        (one line per segment: [mm:ss] text) for agents to read.
Uses the yt_dlp Python library (same path as the MyMusic companion). No video/audio is downloaded.
Usage: python -X utf8 scripts/fetch_video_transcripts.py [--langs en,zh-Hans,zh] [--only <id>]
"""
import json, pathlib, re, sys, argparse, html
ROOT = pathlib.Path(__file__).resolve().parents[1]
DIR = ROOT / 'data/upcoming-civs'
OUT = DIR / 'transcripts'

def parse_vtt(text):
    segs = []
    blocks = re.split(r'\n\s*\n', text.replace('\r', ''))
    stamp = re.compile(r'(\d+):(\d+):(\d+)\.(\d+)\s+-->\s+(\d+):(\d+):(\d+)\.(\d+)')
    last = None
    for block in blocks:
        m = stamp.search(block)
        if not m: continue
        g = list(map(int, m.groups()))
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000; end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        body = block[m.end():]
        body = re.sub(r'<[^>]+>', '', body)  # strip word timing tags
        body = html.unescape(' '.join(line.strip() for line in body.splitlines() if line.strip() and '-->' not in line))
        if not body or body == last: continue
        last = body
        segs.append({'start': round(start, 2), 'end': round(end, 2), 'text': body})
    return segs

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--langs', default='en,en-orig,zh-Hans,zh,zh-Hant'); ap.add_argument('--only')
    args = ap.parse_args()
    from yt_dlp import YoutubeDL
    videos = json.loads((DIR / 'videos.json').read_text(encoding='utf-8'))['videos']
    OUT.mkdir(parents=True, exist_ok=True)
    langs = args.langs.split(',')
    summary = []
    for v in videos:
        url = v['url']
        opts = {'skip_download': True, 'writesubtitles': True, 'writeautomaticsub': True, 'subtitleslangs': langs, 'subtitlesformat': 'vtt',
                'outtmpl': str(OUT / '%(id)s.%(ext)s'), 'quiet': True, 'no_warnings': True, 'cachedir': str(ROOT / '.cache/yt-dlp'),
                'allowed_extractors': ['youtube.*', 'bili.*', 'twitch.*']}
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as exc:  # noqa: BLE001 - report and continue
            summary.append({'url': url, 'error': str(exc)[:300]}); continue
        vid = info.get('id');
        if args.only and vid != args.only: continue
        segments, lang = [], None
        for candidate in sorted(OUT.glob(f'{vid}.*.vtt')):
            segments = parse_vtt(candidate.read_text(encoding='utf-8', errors='replace')); lang = candidate.suffixes[0].lstrip('.')
            if segments: break
        record = {'id': vid, 'url': url, 'title': info.get('title'), 'channel': info.get('channel') or info.get('uploader'), 'uploadDate': info.get('upload_date'),
                  'duration': info.get('duration'), 'description': info.get('description'), 'chapters': info.get('chapters'), 'language': lang,
                  'note': v.get('note'), 'segments': segments}
        (OUT / f'{vid}.json').write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
        (OUT / f'{vid}.txt').write_text('\n'.join(f"[{int(s['start'])//60:02d}:{int(s['start'])%60:02d}] {s['text']}" for s in segments), encoding='utf-8')
        summary.append({'id': vid, 'title': record['title'], 'channel': record['channel'], 'segments': len(segments), 'language': lang, 'duration': record['duration']})
        print(json.dumps(summary[-1], ensure_ascii=False), flush=True)
    (OUT / '_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    print('done', len(summary), 'videos')

if __name__ == '__main__':
    main()
