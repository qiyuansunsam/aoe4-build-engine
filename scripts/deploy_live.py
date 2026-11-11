"""Build bounded static assets and publish the existing mcaoe4 Cloudflare Worker."""
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'deploy/cloudflare'


def main():
    lock_path=ROOT/'.cache/deploy.lock';lock_path.parent.mkdir(exist_ok=True)
    lock_file=lock_path.open('a+b');lock_file.seek(0);lock_file.write(b'0');lock_file.flush();lock_file.seek(0)
    if sys.platform=='win32':
        import msvcrt
        msvcrt.locking(lock_file.fileno(),msvcrt.LK_NBLCK,1)
    else:
        import fcntl
        fcntl.flock(lock_file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    subprocess.run([sys.executable, '-X', 'utf8', 'site/build.py', '--split-data', '--out', str(TARGET / 'dist')], cwd=ROOT, check=True)
    files = [p for p in (TARGET / 'dist').rglob('*') if p.is_file()]
    if len(files) > 20000 or any(p.stat().st_size > 25 * 1024 * 1024 for p in files):
        raise RuntimeError('Static assets exceed the current Cloudflare limits; deployment was not attempted')
    npx = shutil.which('npx.cmd') or shutil.which('npx')
    if not npx:
        raise RuntimeError('npx is required; Cloudflare credentials stay in the existing Wrangler store')
    subprocess.run([npx, '--yes', 'wrangler@4.160.0', 'deploy'], cwd=TARGET, check=True)
    record = {'deployedAt': datetime.now(timezone.utc).isoformat(), 'url': 'https://mcaoe4.qiyuansunsam.workers.dev', 'assets': len(files)}
    target = ROOT / '.cache/live-deployment.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(record, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
