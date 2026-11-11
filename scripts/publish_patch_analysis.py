"""Verify a patch-worker snapshot and refresh the local site without a game client."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=ROOT / '.cache/patch-analysis')
    args = parser.parse_args()
    snapshots = args.base / 'snapshots'
    common = ['--source', str(snapshots / 'player-games.json'), '--history', str(snapshots / 'batch-match-history.json'), '--tc-cache', str(snapshots / 'tc-milestones.json')]
    paths = [ROOT / 'data' / name for name in ('unit-usage-tiers.json', 'player-analysis.json', 'player-profiles.json', 'winrates.json')]
    previous = {path: path.read_bytes() for path in paths}
    def run(script, *arguments):
        subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / script), *arguments], cwd=ROOT, check=True)
    try:
        run('export_unit_tiers.py', *common, '--external-evidence')
        run('verify_usage_rankings.py', *common)
        run('export_publisher_matrix.py', '--source', str(snapshots / 'player-games.json'))
        run('build_winrates.py')
        subprocess.run([sys.executable, '-X', 'utf8', 'site/build.py'], cwd=ROOT, check=True)
    except Exception:
        for path, content in previous.items():
            temporary = path.with_suffix('.restore.tmp')
            temporary.write_bytes(content)
            temporary.replace(path)
        raise
    stamp = {'publishedAt': datetime.now(timezone.utc).isoformat(), 'snapshot': json.loads((snapshots / 'snapshot.json').read_text(encoding='utf-8')), 'profiles': 5, 'tacticalRadar': 'preserved; publisher age components refreshed'}
    target = args.base / 'published.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(stamp, indent=2), encoding='utf-8')
    temporary.replace(target)
    print(json.dumps(stamp))


if __name__ == '__main__':
    main()
