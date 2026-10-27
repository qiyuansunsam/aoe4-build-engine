import argparse
import json
import shutil
from pathlib import Path
from urllib.request import urlopen

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'


def main():
    parser = argparse.ArgumentParser(description='Prepare pinned research dependencies without launching the game')
    parser.add_argument('--recorder', action='store_true', help='Also download the MIT recorder source, not bundled executables')
    args = parser.parse_args()
    sources = json.loads((BASE/'sources.json').read_text())
    DATA.mkdir(exist_ok=True)
    for name in ['latest10-manifest.json','metric-tech-data.json']:
        if not (DATA/name).exists():
            shutil.copy2(BASE/'evidence'/name,DATA/name)
    for key in ['parser'] + (['recorder'] if args.recorder else []):
        source = sources[key]
        repository = source['repository'].removeprefix('https://github.com/')
        destination = DATA/('viewer-probe' if key == 'parser' else 'tactical-recorder')
        for name in source['files']:
            target = destination/name
            if not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True)
                with urlopen(f'https://raw.githubusercontent.com/{repository}/{source["commit"]}/{name}',timeout=30) as response:
                    target.write_bytes(response.read())
        print(key, source['commit'])
    probe = DATA/'viewer-probe'
    (probe/'package.json').write_text('{"type":"module"}')
    shutil.copy2(BASE/'probe.ts',probe/'probe.ts')


if __name__ == '__main__':
    main()
