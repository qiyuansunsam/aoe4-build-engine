"""Player profile snapshots for the reference-game players (AoE4 World public API, on demand).

The Players section shows the players whose recorded games are the reference games of the build
library. Their profiles are fetched from the AoE4 World API in bounded, user-requested calls
(one profile call and a few games pages per player), normalised here and written to
data/player-profiles.json, which build.py embeds in the page. Nothing is crawled: refreshing is a
local action (scripts/build_player_profiles.py or the page's Refresh button through
POST /api/players/refresh) and the public deployment serves the snapshot only.
"""
import json
import time
from pathlib import Path

from player_search import fetch_api
from timeline_download import CIV, TimelineError, atomic_json, read

GAMES_PAGES = 2          # 40 games per page: the last 80 games per player
GAMES_PER_PAGE = 40
MODES = ('rm_team', 'rm_solo', 'rm_1v1_elo', 'rm_2v2_elo', 'rm_3v3_elo', 'rm_4v4_elo', 'qm_1v1', 'qm_2v2', 'qm_3v3', 'qm_4v4')


def civ_id(value):
    return CIV.get(value, value or 'unknown')


def _int(value):
    return value if type(value) is int else None


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def normalize_mode(raw):
    if not isinstance(raw, dict):
        return None
    games = _int(raw.get('games_count')) or 0
    history = []
    for key, entry in sorted((raw.get('rating_history') or {}).items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdecimal() else 0):
        if not str(key).isdecimal() or not isinstance(entry, dict) or _int(entry.get('rating')) is None:
            continue
        history.append({'at': int(key), 'rating': entry['rating'], 'wins': _int(entry.get('wins_count')), 'games': _int(entry.get('games_count')), 'streak': _int(entry.get('streak'))})
    civs = []
    for row in raw.get('civilizations') or []:
        if not isinstance(row, dict) or not row.get('civilization'):
            continue
        civs.append({'civilization': civ_id(row['civilization']), 'games': _int(row.get('games_count')) or 0, 'winRate': _num(row.get('win_rate')), 'pickRate': _num(row.get('pick_rate'))})
    civs.sort(key=lambda c: (-c['games'], c['civilization']))
    seasons = []
    for row in raw.get('previous_seasons') or []:
        if not isinstance(row, dict) or _int(row.get('season')) is None:
            continue
        seasons.append({'season': row['season'], 'rating': _int(row.get('rating')), 'maxRating': _int(row.get('max_rating')), 'rank': _int(row.get('rank')), 'rankLevel': row.get('rank_level'), 'games': _int(row.get('games_count')) or 0, 'wins': _int(row.get('wins_count')) or 0, 'losses': _int(row.get('losses_count')) or 0, 'winRate': _num(row.get('win_rate')), 'streak': _int(row.get('streak'))})
    seasons.sort(key=lambda s: -s['season'])
    if not games and not history and not seasons:
        return None
    return {'rating': _int(raw.get('rating')), 'maxRating': _int(raw.get('max_rating')), 'rank': _int(raw.get('rank')), 'rankLevel': raw.get('rank_level') or 'unranked', 'streak': _int(raw.get('streak')) or 0, 'games': games, 'wins': _int(raw.get('wins_count')) or 0, 'losses': _int(raw.get('losses_count')) or 0, 'drops': _int(raw.get('drops_count')) or 0, 'winRate': _num(raw.get('win_rate')), 'lastGameAt': raw.get('last_game_at'), 'season': _int(raw.get('season')), 'ratingHistory': history, 'civilizations': civs, 'previousSeasons': seasons}


def normalize_profile(raw):
    pid = _int(raw.get('profile_id'))
    if pid is None or pid <= 0:
        raise TimelineError('invalid_player_data', 'AoE4 World returned incomplete player data.', 502)
    avatars = raw.get('avatars') or {}
    modes = {}
    for mode in MODES:
        entry = normalize_mode((raw.get('modes') or {}).get(mode))
        if entry:
            modes[mode] = entry
    return {'profileId': pid, 'name': raw.get('name') or str(pid), 'country': raw.get('country'), 'avatar': avatars.get('medium') or avatars.get('small') or avatars.get('full'), 'siteUrl': raw.get('site_url') or f'https://aoe4world.com/players/{pid}', 'lastGameAt': raw.get('last_game_at'), 'modes': modes}


def normalize_game(raw, pid):
    gid = _int(raw.get('game_id'))
    if gid is None or gid <= 0 or raw.get('ongoing'):
        return None
    players = []
    for team, items in enumerate(raw.get('teams') or []):
        for entry in items or []:
            p = entry.get('player', entry) if isinstance(entry, dict) else {}
            if _int(p.get('profile_id')) is None:
                continue
            players.append({'profileId': p['profile_id'], 'name': p.get('name') or str(p['profile_id']), 'civilization': civ_id(p.get('civilization')), 'team': team, 'result': p.get('result'), 'rating': _int(p.get('rating')), 'ratingDiff': _int(p.get('rating_diff'))})
    me = next((p for p in players if p['profileId'] == pid), None)
    if not me:
        return None
    return {'gameId': gid, 'matchId': f'online-{gid}', 'startedAt': raw.get('started_at'), 'duration': _int(raw.get('duration')), 'map': raw.get('map') or 'Unknown map', 'mode': raw.get('kind') or raw.get('leaderboard') or 'unknown', 'leaderboard': raw.get('leaderboard'), 'season': _int(raw.get('season')), 'patch': str(raw.get('patch') or 'unknown'), 'server': raw.get('server'), 'averageRating': _int(raw.get('average_rating')), 'civilization': me['civilization'], 'result': me['result'], 'rating': me['rating'], 'ratingDiff': me['ratingDiff'], 'team': me['team'], 'players': players, 'url': f'https://aoe4world.com/players/{pid}/games/{gid}'}


def reference_players(library):
    """The players whose recorded games are the build library's reference games, in library order."""
    out = []
    for game in library.get('games') or []:
        pid, gid = _int(game.get('profileId')), _int(game.get('gameId'))
        if not game.get('buildId') or game.get('sourceType') != 'observed' or pid is None or gid is None:
            continue
        if any(r['profileId'] == pid for r in out):
            continue
        out.append({'profileId': pid, 'name': game.get('playerName') or str(pid), 'reference': {'buildId': game['buildId'], 'gameId': gid, 'matchId': game.get('matchId') or f'online-{gid}', 'perspectiveId': game.get('id'), 'title': game.get('title'), 'civilization': game.get('civilization'), 'map': game.get('map'), 'mode': game.get('mode'), 'result': game.get('result'), 'duration': game.get('duration')}})
    return out


def collection_matches(library, pid):
    """Match ids in the local collection that include this player, so the profile can link to them."""
    out = {}
    for match in library.get('matches') or []:
        for p in match.get('players') or []:
            if _int(p.get('profileId')) == pid:
                out[match['id']] = bool(match.get('perspectiveIds'))
    return out


def tracked_players(root):
    """The players of the replay skill analysis (experiments/replay_analytics/data/latest10-manifest.json), in
    manifest order; these are the Players section's players when the manifest exists."""
    path = Path(root) / 'experiments/replay_analytics/evidence/latest10-manifest.json'
    if not path.exists():
        return []
    manifest = read(path)
    names = manifest.get('names') or {}
    roles = manifest.get('roles') or {}
    return [{'profileId': int(pid), 'name': names.get(pid) or str(pid), 'reference': None, 'tracked': True, 'role': roles.get(pid, 'tracked')} for pid in manifest.get('players', {})]


def build_snapshot(root, transport=fetch_api, pages=GAMES_PAGES, only=None, now=None):
    root = Path(root)
    library = read(root / 'data/game-library.json')
    players = []
    for ref in tracked_players(root) or reference_players(library):
        pid = ref['profileId']
        if only and pid not in only:
            continue
        profile = normalize_profile(transport(f'https://aoe4world.com/api/v0/players/{pid}'))
        games = []
        for page in range(1, pages + 1):
            raw = transport(f'https://aoe4world.com/api/v0/players/{pid}/games?page={page}&limit={GAMES_PER_PAGE}&include_alts=false')
            rows = raw.get('games') if isinstance(raw, dict) else None
            if not isinstance(rows, list):
                raise TimelineError('invalid_player_data', 'AoE4 World returned incomplete games data.', 502)
            games.extend(g for row in rows[:GAMES_PER_PAGE] if isinstance(row, dict) for g in [normalize_game(row, pid)] if g)
            if raw.get('next_page') is None or len(rows) < GAMES_PER_PAGE:
                break
        games.sort(key=lambda g: g['startedAt'] or '', reverse=True)
        local = collection_matches(library, pid)
        for g in games:
            if g['matchId'] in local:
                g['inCollection'] = True
                g['timeline'] = local[g['matchId']]
        players.append({**profile, 'reference': ref.get('reference'), 'tracked': bool(ref.get('tracked')), 'role': ref.get('role', 'tracked'), 'recentGames': games, 'recentGamesWindow': len(games), 'collectionMatches': len(local), 'collectionTimelines': sum(local.values())})
    return {'schemaVersion': 1, 'generatedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)), 'source': {'provider': 'AoE4 World public API', 'calls': 'players/{id} and players/{id}/games (pages of 40, alternate accounts excluded)', 'policy': 'on-demand, user-requested; the public site serves this snapshot only'}, 'players': players}


def write_snapshot(root, **kwargs):
    root = Path(root)
    snapshot = build_snapshot(root, **kwargs)
    atomic_json(root / 'data/player-profiles.json', snapshot)
    return snapshot
