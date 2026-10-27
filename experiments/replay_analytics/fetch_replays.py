import gzip
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent / "data"
MATCHES = [(255410440, 18518902), (257307543, 7195780), (257209177, 7999822)]


def fetch(game, profile):
    target = ROOT / f'replay-{game}.rec'
    if target.exists():
        return {'game': game, 'status': 'cached', 'bytes': target.stat().st_size}
    url = f'https://api.ageofempires.com/api/GameStats/AgeIV/GetMatchReplay/?matchId={game}&profileId={profile}'
    request = Request(url, headers={'User-Agent': 'mcaoe4/0.1 (personal replay research)'})
    with urlopen(request, timeout=45) as response:
        packed = response.read()
    raw = gzip.decompress(packed) if packed[:2] == b'\x1f\x8b' else packed
    if raw[4:12] != b'AOE4_RE\0':
        raise ValueError('Response is not a replay')
    (ROOT / f'replay-{game}.download').write_bytes(packed)
    target.write_bytes(raw)
    metadata = {'game': game, 'profile': profile, 'url': url, 'compressed_bytes': len(packed),
                'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    (ROOT / f'replay-{game}.metadata.json').write_text(json.dumps(metadata, indent=2))
    return metadata


if __name__ == '__main__':
    for game, profile in MATCHES:
        print(json.dumps(fetch(game, profile)))
