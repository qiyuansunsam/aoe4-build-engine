"""Record the manifest's replays in the installed game with the MIT recorder (BigManJohn000/aoe4-replay-viewer,
pinned in sources.json, cloned at .cache/aoe4-replay-viewer) and keep a per-match status.

Usage: python -X utf8 record_batch.py [--only GID ...] [--limit N] [--recorder DIR]

Each replay data/replay-<gid>.rec is staged as <recorder>/replays/aoe4world/aoe4_<gid>.rec and recorded with
tools/record_replay.py (launches AoE4 through Steam on the replay, lowers graphics for the run, restores them after,
closes the game). A complete recording (<recorder>/recordings/aoe4_<gid>.rlog with header, end coverage, no errors or
gaps) is skipped. Status, wall time and the recorder's output go to data/recording-status.json and data/record-<gid>.log.
"""
import argparse, json, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
DEFAULT_RECORDER = HERE.parents[1] / '.cache' / 'aoe4-replay-viewer'


def load_status():
    path = DATA / 'recording-status.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'matches': {}}


def save_status(status):
    status['updated_at'] = datetime.now(timezone.utc).isoformat()
    tmp = DATA / 'recording-status.json.tmp'
    tmp.write_text(json.dumps(status, indent=2), encoding='utf-8')
    tmp.replace(DATA / 'recording-status.json')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--only', type=int, nargs='*')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--recorder', type=Path, default=DEFAULT_RECORDER)
    args = ap.parse_args()
    recorder = args.recorder.resolve()
    sys.path.insert(0, str(recorder / 'tools'))
    import record_replay, recfile  # noqa: E402
    manifest = json.loads((DATA / 'latest10-manifest.json').read_text(encoding='utf-8'))
    status = load_status()
    done = 0
    for entry in manifest['unique_games']:
        gid = entry['game']['game_id']
        if args.only and gid not in args.only:
            continue
        src = DATA / f'replay-{gid}.rec'
        row = status['matches'].setdefault(str(gid), {'game_id': gid, 'requested_by': entry['requested_by']})
        if not src.exists():
            row['status'] = 'no_replay'
            save_status(status)
            continue
        staged_dir = recorder / 'replays' / 'aoe4world'
        staged_dir.mkdir(parents=True, exist_ok=True)
        staged = staged_dir / f'aoe4_{gid}.rec'
        if not staged.exists() or staged.stat().st_size != src.stat().st_size:
            shutil.copyfile(src, staged)
        rlog = recorder / 'recordings' / f'aoe4_{gid}.rlog'
        duration = recfile.load(staged).duration_seconds
        row['replay_seconds'] = duration
        if rlog.exists() and record_replay.is_complete(rlog, duration):
            row['status'] = 'complete'
            row['rlog'] = str(rlog)
            save_status(status)
            continue
        if args.limit and done >= args.limit:
            break
        print(f'Recording {gid} ({duration:.0f} s)...', flush=True)
        row['status'] = 'recording'
        row['started_at'] = datetime.now(timezone.utc).isoformat()
        save_status(status)
        t0 = time.time()
        log_path = DATA / f'record-{gid}.log'
        with log_path.open('w', encoding='utf-8') as log:
            proc = subprocess.Popen([sys.executable, '-X', 'utf8', str(recorder / 'tools' / 'record_replay.py'), str(staged)],
                                    cwd=recorder, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            muted = False
            while proc.poll() is None:
                time.sleep(5)
                if not muted and time.time() - t0 > 20:  # the game is up by now: silence its audio session (Sam, 2026-10-27)
                    out = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(HERE / 'mute_game.ps1')],
                                         capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60).stdout.strip()
                    muted = out.startswith('muted')
                    tuck = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(HERE / 'tuck_game.ps1')],
                                          capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60).stdout.strip()
                    log.write(f'\n[record_batch] {out}\n[record_batch] {tuck}\n'); log.flush()
                if time.time() - t0 > 3600:
                    proc.kill()
        row['wall_seconds'] = round(time.time() - t0, 1)
        row['exit_code'] = proc.returncode
        row['rlog'] = str(rlog) if rlog.exists() else None
        row['status'] = 'complete' if rlog.exists() and record_replay.is_complete(rlog, duration) else 'failed'
        tail = log_path.read_text(encoding='utf-8', errors='replace').strip().splitlines()[-3:]
        row['log_tail'] = tail
        save_status(status)
        print(f'  {row["status"]} in {row["wall_seconds"]} s ({duration / max(row["wall_seconds"], 1):.1f}x)', flush=True)
        done += 1
    summary = {k: sum(1 for m in status['matches'].values() if m.get('status') == k) for k in ('complete', 'failed', 'no_replay')}
    print('Recording status', summary)


if __name__ == '__main__':
    main()
