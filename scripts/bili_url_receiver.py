"""Local receiver for bilibili stream URLs posted from a logged-in browser tab.

bilibili answers scripted API calls with HTTP 412, so the signed DASH URLs are fetched in the browser
(api.bilibili.com/x/player/playurl with credentials) and POSTed here as JSON. Writes .cache/bili/<name>.json.
Usage: python -X utf8 scripts/bili_url_receiver.py [--port 8799]   (stops after --max posts or on timeout)
"""
import argparse, json, pathlib, re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/bili'

class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', 'https://www.bilibili.com')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Private-Network', 'true')

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_POST(self):
        name = re.sub(r'[^A-Za-z0-9_-]', '', self.path.rsplit('/', 1)[-1]) or 'posted'
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        if 'x-www-form-urlencoded' in self.headers.get('Content-Type', ''):  # top-level form POST from the tab
            body = parse_qs(body.decode('utf-8'))['data'][0].encode('utf-8')
        json.loads(body)  # reject anything that is not JSON
        OUT.mkdir(parents=True, exist_ok=True); (OUT / f'{name}.json').write_bytes(body)
        self.send_response(200); self._cors(); self.end_headers(); self.wfile.write(b'ok')
        print('saved', name, len(body), flush=True)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--port', type=int, default=8799)
    HTTPServer(('127.0.0.1', ap.parse_args().port), Handler).serve_forever()
