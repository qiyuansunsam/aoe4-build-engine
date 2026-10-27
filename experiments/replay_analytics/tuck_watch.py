"""Watch for each newly launched game process during a recording batch and tuck its window away (mute_game.ps1 +
tuck_game.ps1) a few seconds after it appears, so the batch already running picks the behaviour up without a restart.
Usage: python -X utf8 tuck_watch.py [--seconds 7000]
"""
import argparse, subprocess, time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def game_pid():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq RelicCardinal.exe', '/FO', 'CSV', '/NH'], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if parts and parts[0].lower() == 'reliccardinal.exe':
            return int(parts[1])
    return None


def run(script):
    return subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(HERE / script)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60).stdout.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seconds', type=int, default=7000)
    args = ap.parse_args()
    end = time.time() + args.seconds
    seen = None
    while time.time() < end:
        pid = game_pid()
        if pid and pid != seen:
            time.sleep(15)  # the window exists once the map loads
            if game_pid() == pid:
                print(time.strftime('%H:%M:%S'), pid, run('mute_game.ps1'), '|', run('tuck_game.ps1'), flush=True)
                seen = pid
        elif not pid:
            seen = None
        time.sleep(5)


if __name__ == '__main__':
    main()
