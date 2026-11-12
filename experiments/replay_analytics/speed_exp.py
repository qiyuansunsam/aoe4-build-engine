"""Timing harness for recording-speed experiments (Sam, 2026-11-13: "can we somehow try to speedup the recording").

One direct-launched game plays one replay with the recorder plus the given probe scripts; the run goes to the recorder's
recordings/probes/ folder (never the real recordings) and this prints how far the replay got at fixed wall-clock marks,
when and how the game ended, and the lines the probes printed.

Usage: python -X utf8 speed_exp.py GID --label NAME [--probe FILE ...] [--res W:H] [--steam-env] [--max-wall S]
       [--steam] (launch through Steam instead of directly) [--visible]
"""
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
RECORDER = HERE.parents[1] / '.cache' / 'aoe4-replay-viewer'
PROBES = HERE / 'speed_probes'
STEAM_ENV = {'SteamAppId': '1466860', 'SteamGameId': '1466860', 'SteamOverlayGameId': '1466860', 'SteamClientLaunch': '1', 'SteamEnv': '1'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('gid', type=int)
    ap.add_argument('--label', required=True)
    ap.add_argument('--probe', action='append', default=[])
    ap.add_argument('--res', help='render resolution W:H instead of 1280:720')
    ap.add_argument('--steam-env', action='store_true', help="give the direct game the environment Steam's launcher sets")
    ap.add_argument('--env-json', help='JSON file of extra environment variables for the game')
    ap.add_argument('--max-wall', type=float, default=420)
    ap.add_argument('--steam', action='store_true')
    ap.add_argument('--visible', action='store_true')
    args = ap.parse_args()
    sys.path.insert(0, str(RECORDER / 'tools'))
    import record_replay
    low = dict(record_replay.RECORDING_GRAPHICS, windowmode='2')
    if args.res:
        low['resolution'] = f'"{args.res}:0:0"'
    record_replay.RECORDING_GRAPHICS.clear()
    record_replay.RECORDING_GRAPHICS.update(low)
    staged = RECORDER / 'replays' / 'aoe4world' / f'aoe4_{args.gid}.rec'
    if not staged.exists():
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes((DATA / f'replay-{args.gid}.rec').read_bytes())
    probes = args.probe or ['noop']
    cmd = [sys.executable, '-X', 'utf8', str(RECORDER / 'tools' / 'record_replay.py'), str(staged), '--no-graphics', '--no-convert']
    if not args.steam:
        cmd.append('--direct')
    for p in probes:
        cmd += ['--probe', str(PROBES / f'{p}.lua')]
    env = dict(os.environ)
    if args.steam_env:
        env.update(STEAM_ENV)
    if args.env_json:
        env.update(json.loads(Path(args.env_json).read_text(encoding='utf-8')))
    lowered = record_replay.lower_graphics()
    hider = None
    if not args.visible:
        sys.path.insert(0, str(HERE))
        from hide_games import GameHider
        hider = GameHider(log=lambda *a: None)
        hider.start()
    log_path = DATA / f'speedexp-{args.label}.log'
    t0 = time.time()
    try:
        with log_path.open('w', encoding='utf-8') as log:
            proc = subprocess.Popen(cmd, cwd=RECORDER, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env)
            while proc.poll() is None and time.time() - t0 < args.max_wall:
                time.sleep(2)
            timed_out = proc.poll() is None
            if timed_out:  # stop the controller, then its game (hard kill: writes no settings back)
                import psutil
                kids = psutil.Process(proc.pid).children(recursive=True)
                proc.kill()
                for k in kids:
                    try:
                        k.kill()
                    except psutil.Error:
                        pass
                for p in psutil.process_iter(['name', 'cmdline']):
                    if (p.info['name'] or '').lower() == 'reliccardinal.exe' and f'aoe4_{args.gid}.rec' in ' '.join(p.info['cmdline'] or []):
                        p.kill()
    finally:
        if hider:
            hider.stop.set()
        time.sleep(3)
        if lowered:
            record_replay.restore_graphics()
    wall = time.time() - t0
    text = log_path.read_text(encoding='utf-8', errors='replace')
    samples = re.findall(r'(\d+):(\d\d) / \d+:\d\d\s+\(([\d.]+)x\)', text)  # one per 2 s of wall time once recording started
    clocks = [int(m) * 60 + int(s) for m, s, _ in samples]
    marks = {w: clocks[w // 2 - 1] for w in (30, 60, 90, 120, 150, 180, 210, 240, 300, 360) if w // 2 - 1 < len(clocks)}
    tail = [l for l in re.split(r'[\r\n]+', text) if l.strip() and not re.match(r'\s*\d+:\d\d / ', l)][-6:]
    out = {'label': args.label, 'gid': args.gid, 'probes': probes, 'res': args.res, 'steam_env': args.steam_env, 'steam': args.steam,
           'wall_s': round(wall, 1), 'timed_out': timed_out, 'recording_wall_s': 2 * len(clocks),
           'game_s_at_wall': marks, 'final_game_s': clocks[-1] if clocks else None,
           'avg_x': samples[-1][2] if samples else None, 'tail': tail}
    # Probe output straight from the game's own script log (a run stopped at --max-wall writes no .rlog).
    sessions = sorted(record_replay.LOG_DIR.glob('AoE4_*'), key=lambda d: d.stat().st_mtime)
    logs = sorted(sessions[-1].glob('scarlog.*.txt')) if sessions else []
    if logs:
        lines = [l for l in logs[-1].read_text(encoding='utf-8', errors='replace').splitlines() if 'R|PROBE|' in l or 'R|API|' in l]
        out['probe_lines'] = len(lines)
        (DATA / f'speedexp-{args.label}.probe.txt').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(out, indent=1))
    with (DATA / 'speedexp-results.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(out) + '\n')


if __name__ == '__main__':
    main()
