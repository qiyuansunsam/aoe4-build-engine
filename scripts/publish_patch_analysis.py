"""Verify a patch-worker snapshot and refresh the local site without a game client."""
import argparse
import json
import shutil
import time
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=ROOT / '.cache/patch-analysis')
    args = parser.parse_args()
    lock_file=(args.base/'publish.lock').open('a+b');lock_file.seek(0);lock_file.write(b'0');lock_file.flush();lock_file.seek(0)
    if sys.platform=='win32':
        import msvcrt
        msvcrt.locking(lock_file.fileno(),msvcrt.LK_LOCK,1)
    else:
        import fcntl
        fcntl.flock(lock_file.fileno(),fcntl.LOCK_EX)
    source_snapshots=args.base/'snapshots'
    snapshots=args.base/'publication-inputs';snapshots.mkdir(exist_ok=True)
    for attempt in range(3):
        initial=(source_snapshots/'snapshot.json').read_bytes()
        for name in ('player-games.json','batch-match-history.json','tc-milestones.json','snapshot.json'):
            shutil.copy2(source_snapshots/name,snapshots/name)
        if initial==(source_snapshots/'snapshot.json').read_bytes():break
        time.sleep(2)
    else:raise RuntimeError('Snapshot changed during publication; retry with the next completed checkpoint')
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
    live_config=args.base/'live-publication.json'
    if live_config.exists() and json.loads(live_config.read_text(encoding='utf-8')).get('enabled'):
        run('deploy_live.py')
    stamp = {'publishedAt': datetime.now(timezone.utc).isoformat(), 'snapshot': json.loads((snapshots / 'snapshot.json').read_text(encoding='utf-8')), 'profiles': 5, 'tacticalRadar': 'preserved; publisher age components refreshed'}
    target = args.base / 'published.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(stamp, indent=2), encoding='utf-8')
    temporary.replace(target)
    print(json.dumps(stamp))


if __name__ == '__main__':
    main()
