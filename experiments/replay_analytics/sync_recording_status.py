"""Bring data/recording-status.json in line with the recordings on disk without launching anything: a manifest game whose
.rlog is complete (header, end coverage, no errors or gaps) becomes 'complete'; one left at 'recording' by a stopped batch
with no complete .rlog becomes 'failed'. Use after record_batch.py was stopped while games were still playing.

Usage: python -X utf8 sync_recording_status.py
"""
import json, sys
from pathlib import Path

import record_batch

RECORDER = record_batch.DEFAULT_RECORDER


def main():
    sys.path.insert(0, str(RECORDER / 'tools'))
    import record_replay, recfile
    manifest = json.loads((record_batch.DATA / 'latest10-manifest.json').read_text(encoding='utf-8'))
    status = record_batch.load_status()
    changed = []
    for entry in manifest['unique_games']:
        gid = entry['game']['game_id']
        row = status['matches'].get(str(gid))
        rlog = RECORDER / 'recordings' / f'aoe4_{gid}.rlog'
        staged = RECORDER / 'replays' / 'aoe4world' / f'aoe4_{gid}.rec'
        if row is None or row.get('status') == 'complete' or not staged.exists():
            continue
        done = rlog.exists() and record_replay.is_complete(rlog, recfile.load(staged).duration_seconds)
        if done or row.get('status') == 'recording':
            row['status'] = 'complete' if done else 'failed'
            row['rlog'] = str(rlog) if rlog.exists() else None
            changed.append((gid, row['status']))
    record_batch.save_status(status)
    print('changed', changed)
    print({k: sum(1 for m in status['matches'].values() if m.get('status') == k) for k in ('complete', 'failed', 'no_replay', 'recording')})


if __name__ == '__main__':
    main()
