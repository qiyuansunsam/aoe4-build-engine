import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fetch_replays import fetch

ROOT = Path(__file__).resolve().parent / "data"


def main():
    manifest = json.loads((ROOT/'latest10-manifest.json').read_text(encoding='utf8'))
    report = []
    for entry in manifest['unique_games']:
        game = entry['game']['game_id']
        profile = entry['profile_for_download']
        status = {'game_id':game, 'requested_by':entry['requested_by']}
        summary_path = ROOT/f'summary-{game}.txt'
        if game == 255410440 and not summary_path.exists() and (ROOT/'summary.txt').exists():
            summary_path.write_bytes((ROOT/'summary.txt').read_bytes())
        try:
            if not summary_path.exists():
                url = f'https://aoe4world.com/players/{profile}/games/{game}/summary'
                request = Request(url, headers={'User-Agent':'mcaoe4/0.1 (personal four-player analysis; github.com/qiyuansunsam)'})
                with urlopen(request, timeout=45) as response:
                    data = response.read()
                parsed = json.loads(data)
                if parsed.get('game_id') != game or not parsed.get('players'):
                    raise ValueError('Incomplete summary response')
                summary_path.write_bytes(data)
                time.sleep(2)
            status['summary'] = 'cached'
        except Exception as error:
            status['summary_error'] = str(error)
            if isinstance(error, HTTPError) and error.code == 429:
                status['retry_after'] = error.headers.get('Retry-After')
                report.append(status)
                print(json.dumps(status), flush=True)
                break
        try:
            status['replay'] = fetch(game, profile)
            if not (ROOT/f'replay-{game}.parsed.json').exists():
                result = subprocess.run(['node','--experimental-strip-types','probe.ts',str(game)],
                                        cwd=ROOT/'viewer-probe', capture_output=True, text=True, timeout=90)
                if result.returncode:
                    raise RuntimeError(result.stderr[:1200])
            status['parsed'] = True
        except Exception as error:
            status['replay_error'] = str(error)
        report.append(status)
        (ROOT/'collection-status.json').write_text(json.dumps({'updated_at':datetime.now(timezone.utc).isoformat(), 'matches':report},indent=2),encoding='utf8')
        print(json.dumps(status),flush=True)
    (ROOT/'collection-status.json').write_text(json.dumps({'updated_at':datetime.now(timezone.utc).isoformat(), 'matches':report},indent=2),encoding='utf8')


if __name__ == '__main__':
    main()
