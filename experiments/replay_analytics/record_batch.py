"""Record the manifest's replays in the installed game with the MIT recorder (BigManJohn000/aoe4-replay-viewer,
pinned in sources.json, cloned at .cache/aoe4-replay-viewer) and keep a per-match status.

Usage: python -X utf8 record_batch.py [--only GID ...] [--limit N] [--recorder DIR] [--workers N] [--game-dir DIR]

Each replay data/replay-<gid>.rec is staged as <recorder>/replays/aoe4world/aoe4_<gid>.rec and recorded with
tools/record_replay.py (launches AoE4 through Steam on the replay, lowers graphics for the run, restores them after,
closes the game). A complete recording (<recorder>/recordings/aoe4_<gid>.rlog with header, end coverage, no errors or
gaps) is skipped. Status, wall time and the recorder's output go to data/recording-status.json and data/record-<gid>.log.

Direct launches outside Steam exit cleanly (code 0) 220-280 s after launch (seen 8 times, 2026-10-28), and Steam will
not start the game while a direct one runs, so --workers > 1 only suits replays that finish within that window (about
17 game-minutes); longer ones belong to the one-at-a-time Steam path (--hide keeps it out of sight).
--workers N (2026-10-28) plays N replays at once: each worker starts RelicCardinal.exe directly (record_replay.py
--direct; the game folder needs steam_appid.txt = 1466860 and Steam running), launches are staggered by --stagger
seconds, graphics are lowered once for the whole batch (windowed, since several full-screen games fight over the
display) and restored at the end (--hide does the same for one-at-a-time Steam runs); hide_games.GameHider keeps every game window 640x360 off-screen, off the taskbar and
out of the foreground (--visible turns that off). --game-dir picks the install to play with (e.g. a kept 16.3 copy after an update).
"""
import argparse, json, shutil, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
DEFAULT_RECORDER = HERE.parents[1] / '.cache' / 'aoe4-replay-viewer'
STATUS_LOCK = threading.Lock()
LAUNCH_LOCK = threading.Lock()
next_launch = [0.0]


def load_status():
    path = DATA / 'recording-status.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'matches': {}}


def save_status(status):
    with STATUS_LOCK:
        status['updated_at'] = datetime.now(timezone.utc).isoformat()
        tmp = DATA / 'recording-status.json.tmp'
        tmp.write_text(json.dumps(status, indent=2), encoding='utf-8')
        tmp.replace(DATA / 'recording-status.json')


def powershell(script):
    return subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(HERE / script)],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60).stdout.strip()


def elevated(name):
    """True when a process with this image name runs elevated: its token cannot be queried from this (normal) process.
    Admin Steam launches the game elevated, and the recorder's posted console keys are then refused (2026-10-28)."""
    import ctypes, ctypes.wintypes as wt
    import psutil
    k32, adv = ctypes.WinDLL('kernel32'), ctypes.WinDLL('advapi32')
    k32.OpenProcess.restype = wt.HANDLE
    for p in psutil.process_iter(['name']):
        if (p.info['name'] or '').lower() != name:
            continue
        h, tok = k32.OpenProcess(0x1000, False, p.pid), wt.HANDLE()
        if not h or not adv.OpenProcessToken(h, 0x8, ctypes.byref(tok)):
            return True
        elev, size = wt.DWORD(), wt.DWORD()
        adv.GetTokenInformation(tok, 20, ctypes.byref(elev), 4, ctypes.byref(size))
        k32.CloseHandle(tok); k32.CloseHandle(h)
        if elev.value:
            return True
    return False


def record_one(gid, staged, row, status, recorder, record_replay, args):
    if args.workers > 1:
        with LAUNCH_LOCK:  # one game loading at a time: disk-heavy, and session log folders are named by the second
            wait = next_launch[0] - time.time()
            if wait > 0:
                time.sleep(wait)
            next_launch[0] = time.time() + args.stagger
    duration = row['replay_seconds']
    print(f'Recording {gid} ({duration:.0f} s)...', flush=True)
    row['status'] = 'recording'
    row['started_at'] = datetime.now(timezone.utc).isoformat()
    row['workers'] = args.workers
    save_status(status)
    cmd = [sys.executable, '-X', 'utf8', str(recorder / 'tools' / 'record_replay.py'), str(staged)]
    if args.workers > 1:
        cmd += ['--direct', '--no-graphics', '--no-convert']
    elif args.hide:
        cmd += ['--no-graphics', '--no-convert']
    if args.game_dir:
        cmd += ['--game-dir', str(args.game_dir)]
    t0 = time.time()
    log_path = DATA / f'record-{gid}.log'
    with log_path.open('w', encoding='utf-8') as log:
        proc = subprocess.Popen(cmd, cwd=recorder, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        # No Windows session mute: Windows keeps it per executable after the game closes, so Sam's own game stayed muted
        # (2026-10-28). The recorder's RECORDING_GRAPHICS sets the in-game volumes to 0 and restores them instead.
        while proc.poll() is None:
            time.sleep(5)
            if time.time() - t0 > 3600:
                proc.kill()
    rlog = recorder / 'recordings' / f'aoe4_{gid}.rlog'
    row['wall_seconds'] = round(time.time() - t0, 1)
    row['exit_code'] = proc.returncode
    row['rlog'] = str(rlog) if rlog.exists() else None
    row['status'] = 'complete' if rlog.exists() and record_replay.is_complete(rlog, duration) else 'failed'
    row['log_tail'] = log_path.read_text(encoding='utf-8', errors='replace').strip().splitlines()[-3:]
    save_status(status)
    print(f'  {gid} {row["status"]} in {row["wall_seconds"]} s ({duration / max(row["wall_seconds"], 1):.1f}x)', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--only', type=int, nargs='*')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--recorder', type=Path, default=DEFAULT_RECORDER)
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--stagger', type=float, default=20.0, help='seconds between parallel game launches')
    ap.add_argument('--game-dir', type=Path, help='game install to play with (default: the Steam one)')
    ap.add_argument('--hide', action='store_true', help='one game at a time through Steam, but windowed and hidden like the parallel runs')
    ap.add_argument('--visible', action='store_true', help='parallel runs: leave the game windows where the game puts them')
    args = ap.parse_args()
    recorder = args.recorder.resolve()
    sys.path.insert(0, str(recorder / 'tools'))
    import record_replay, recfile  # noqa: E402
    manifest = json.loads((DATA / 'latest10-manifest.json').read_text(encoding='utf-8'))
    status = load_status()
    jobs = []
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
        row['replay_seconds'] = recfile.load(staged).duration_seconds
        if rlog.exists() and record_replay.is_complete(rlog, row['replay_seconds']):
            row['status'] = 'complete'
            row['rlog'] = str(rlog)
            save_status(status)
            continue
        if args.limit and len(jobs) >= args.limit:
            break
        jobs.append((gid, staged, row))
    if jobs and args.workers == 1 and elevated('steam.exe'):
        raise SystemExit('Steam runs as administrator: the game it launches is elevated and refuses the recorder. '
                         'Restart Steam normally first.')
    lowered = False
    if (args.workers > 1 or args.hide) and jobs:
        windowed = dict(record_replay.RECORDING_GRAPHICS, windowmode='2')
        record_replay.RECORDING_GRAPHICS.clear()
        record_replay.RECORDING_GRAPHICS.update(windowed)
        lowered = record_replay.lower_graphics()
    hider = None
    if (args.workers > 1 or args.hide) and jobs and not args.visible:
        from hide_games import GameHider  # Sam, 2026-10-28: run them without him noticing
        hider = GameHider()
        hider.start()
    t0 = time.time()
    try:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            for f in [pool.submit(record_one, gid, staged, row, status, recorder, record_replay, args) for gid, staged, row in jobs]:
                f.result()
        # With three games at once some exited mid-replay (2026-10-28); give each failure one more run on its own.
        retry = [(gid, staged, row) for gid, staged, row in jobs if row['status'] == 'failed'] if args.workers > 1 else []
        for gid, staged, row in retry:
            print(f'Retrying {gid} alone', flush=True)
            row['retried'] = True
            record_one(gid, staged, row, status, recorder, record_replay, args)
    finally:
        if hider:
            hider.stop.set()
        if lowered:
            record_replay.restore_graphics()
    if jobs:
        game = sum(row['replay_seconds'] for _, _, row in jobs)
        print(f'Batch: {len(jobs)} replays, {game / 60:.0f} game-minutes in {(time.time() - t0) / 60:.1f} min '
              f'({game / max(time.time() - t0, 1):.1f}x overall, {args.workers} workers)', flush=True)
    summary = {k: sum(1 for m in status['matches'].values() if m.get('status') == k) for k in ('complete', 'failed', 'no_replay')}
    print('Recording status', summary)


if __name__ == '__main__':
    main()
