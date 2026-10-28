"""Stream local summary exports into the collector's existing import queue.

No network calls or aggregate writes. JSONL/NDJSON (optionally gzip) stream one
bounded record at a time; individual JSON files/arrays are bounded at 10 MiB.
The running collector remains the only writer of summaries and aggregates.
"""
import argparse
import collections
import gzip
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path

from .strategy import DIRECTORY, ROOT

MAX_BYTES = 10 * 1024 * 1024
SUFFIXES = ('.json', '.json.gz', '.jsonl', '.jsonl.gz', '.ndjson', '.ndjson.gz')


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def series(value):
    return isinstance(value, list) and len(value) <= 100000 and all(number(v) for v in value)


def positive_id(value):
    return type(value) is int and 0 < value <= 9007199254740991


def summary_record(payload):
    """Accept raw camelCase summaries and the app's data/summary envelopes."""
    for _ in range(3):
        if not isinstance(payload, dict) or 'gameId' in payload:
            break
        payload = payload.get('summary', payload.get('data', payload))
    if not isinstance(payload, dict) or not positive_id(payload.get('gameId')):
        raise ValueError('Expected a camelCase summary with a positive integer gameId')
    players = payload.get('players')
    if not isinstance(players, list) or not 1 <= len(players) <= 16:
        raise ValueError('Expected 1 to 16 players')
    if not number(payload.get('duration')) or payload['duration'] > 86400:
        raise ValueError('Invalid duration')
    if not isinstance(payload.get('leaderboard', 'unknown'), str):
        raise ValueError('Invalid leaderboard')
    if payload.get('startedAt') is not None and (
        not number(payload['startedAt']) or payload['startedAt'] > 253402300799
    ):
        raise ValueError('Invalid startedAt timestamp')
    seen = set()
    for player in players:
        if not isinstance(player, dict) or not positive_id(player.get('profileId')):
            raise ValueError('Invalid player profileId')
        if player['profileId'] in seen:
            raise ValueError('Duplicate player profileId')
        seen.add(player['profileId'])
        if not isinstance(player.get('civilization'), str) or not player['civilization']:
            raise ValueError('Missing player civilization')
        if not isinstance(player.get('name'), str) or len(player['name']) > 256:
            raise ValueError('Invalid player name')
        if type(player.get('team')) is not int or not 0 <= player['team'] < 16:
            raise ValueError('Invalid player team')
        if player.get('result') not in ('win', 'loss'):
            raise ValueError('Only completed win/loss summaries can be aggregated')
        rows = player.get('buildOrder')
        resources = player.get('resources')
        if not isinstance(rows, list) or not isinstance(resources, dict):
            raise ValueError('Expected buildOrder and resources; match metadata is not a summary')
        if not series(resources.get('timestamps')) or not all(series(v) for v in resources.values()):
            raise ValueError('Invalid resource timelines')
        timestamps = resources['timestamps']
        if any(a > b for a, b in zip(timestamps, timestamps[1:])):
            raise ValueError('Resource timestamps must be ordered')
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('icon'), str) or not isinstance(row.get('type'), str):
                raise ValueError('Invalid buildOrder entry')
            if any(key in row and not series(row[key]) for key in ('finished', 'constructed', 'destroyed')):
                raise ValueError('Invalid buildOrder event times')
        actions = player.get('actions', {})
        analysis = player.get('analysis', {})
        if not isinstance(actions, dict) or not isinstance(analysis, dict):
            raise ValueError('Invalid actions or analysis')
        if any(key in actions and not series(actions[key]) for key in ('feudalAge', 'castleAge', 'imperialAge')):
            raise ValueError('Invalid age timings')
        landmarks = analysis.get('landmarks', [])
        if not isinstance(landmarks, list) or any(
            not isinstance(row, dict) or 'pbgid' not in row
            or not isinstance(row.get('name'), str) or not isinstance(row.get('icon'), str)
            for row in landmarks
        ):
            raise ValueError('Invalid landmarks')
    return payload


def input_files(paths, directory):
    protected = [directory.resolve(), (ROOT / 'data/samples').resolve()]
    for source in paths:
        source = Path(source).resolve()
        if not source.exists():
            raise ValueError(f'Input does not exist: {source}')
        files = source.rglob('*') if source.is_dir() else (source,)
        for path in files:
            if not path.is_file() or not path.name.lower().endswith(SUFFIXES):
                continue
            resolved = path.resolve()
            if any(resolved == p or p in resolved.parents for p in protected):
                continue
            yield resolved


def records(path):
    """Yield (position, payload, error) without loading an entire JSONL file."""
    opener = gzip.open if path.suffix.lower() == '.gz' else open
    line_format = path.name.lower().endswith(('.jsonl', '.jsonl.gz', '.ndjson', '.ndjson.gz'))
    with opener(path, 'rb') as stream:
        if not line_format:
            raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                yield 'file', None, 'JSON file exceeds 10 MiB; use JSONL for large exports'
                return
            try:
                payload = json.loads(raw.decode('utf-8-sig'))
                for index, item in enumerate(payload if isinstance(payload, list) else [payload], 1):
                    yield str(index), item, None
            except (ValueError, UnicodeError, RecursionError) as exc:
                yield 'file', None, type(exc).__name__
            return
        line_number = 0
        while True:
            raw = stream.readline(MAX_BYTES + 1)
            if not raw:
                return
            line_number += 1
            if len(raw) > MAX_BYTES:
                while raw and not raw.endswith(b'\n'):
                    raw = stream.readline(MAX_BYTES + 1)
                yield str(line_number), None, 'JSONL record exceeds 10 MiB'
                continue
            if not raw.strip():
                continue
            try:
                yield str(line_number), json.loads(raw.decode('utf-8-sig')), None
            except (ValueError, UnicodeError, RecursionError) as exc:
                yield str(line_number), None, type(exc).__name__


def canonical(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def enqueue(summary, directory, dry_run=False):
    game_id = summary['gameId']
    body = canonical(summary)
    if len(body) > MAX_BYTES:
        raise ValueError('Unwrapped summary exceeds 10 MiB')
    digest = hashlib.sha256(body).hexdigest()
    queue = directory / 'queue'
    destination = queue / f'bulk-{game_id}.json'
    existing_paths = [directory / 'summaries' / f'{game_id}.json', ROOT / 'data/samples' / f'{game_id}.json', destination]
    for path in existing_paths:
        try:
            with path.open('rb') as handle:
                raw = handle.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                return 'conflict'
            prior = summary_record(json.loads(raw.decode('utf-8-sig')))
            return 'duplicate' if hashlib.sha256(canonical(prior)).hexdigest() == digest else 'conflict'
        except FileNotFoundError:
            continue
        except (ValueError, UnicodeError, RecursionError):
            return 'conflict'
    if dry_run:
        return 'wouldQueue'
    queue.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.bulk-', suffix='.pending', dir=queue)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            # Link publishes complete bytes atomically and never replaces a
            # queue file written by another importer. NTFS supports this too.
            os.link(temporary, destination)
        except FileExistsError:
            return 'duplicatePending'
    finally:
        Path(temporary).unlink(missing_ok=True)
    return 'queued'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--directory', type=Path, default=DIRECTORY)
    parser.add_argument('--dry-run', action='store_true', help='Read and count without queue writes')
    args = parser.parse_args()
    counts = collections.Counter()
    # One digest per ID, not the summary bodies, bounds repeat-record memory.
    seen = {}
    try:
        for path in input_files(args.inputs, args.directory):
            counts['files'] += 1
            try:
                for position, payload, error in records(path):
                    counts['records'] += 1
                    try:
                        if error:
                            raise ValueError(error)
                        summary = summary_record(payload)
                        digest = hashlib.sha256(canonical(summary)).hexdigest()
                        game_id = summary['gameId']
                        if game_id in seen:
                            result = 'duplicate' if seen[game_id] == digest else 'conflict'
                        else:
                            result = enqueue(summary, args.directory, args.dry_run)
                            seen[game_id] = digest
                        counts[result] += 1
                        if result == 'conflict':
                            print(f'{path.name}:{position}: game {game_id} differs from an existing record; retained existing data', file=sys.stderr)
                    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
                        counts['invalid'] += 1
                        print(f'{path.name}:{position}: {exc}', file=sys.stderr)
            except (OSError, EOFError) as exc:
                counts['fileErrors'] += 1
                print(f'{path.name}: {type(exc).__name__}', file=sys.stderr)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(dict(counts), sort_keys=True))
    if counts['invalid'] or counts['fileErrors'] or counts['conflict']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
