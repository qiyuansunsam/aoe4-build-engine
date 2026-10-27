"""Build data/i18n-zh-game.json: the game's own Simplified Chinese text for what the app shows.

Joins the installed game's English and Simplified Chinese UCS locale files (unpacked read-only from
cardinal/archives/LocaleEnglish.sga and LocaleSimplifiedChinese.sga with the AOEMods.Essence CLI
`sga-unpack`, see data/INSTALLED_DATA.md) and keeps only strings the UI renders:

- names of every unit, building and technology in data/game-catalog.json, joined by the record's
  nameLocalizationId (the locale id the catalog carries); records without one, civilizations and the
  17.0 preview records (data/catalog-preview-17.0.json) join by exact English text. Vikings and Scots
  names that are not in the 16.3 locale stay English.
- descriptions: the catalog keeps no help-text id, so they join by exact English text. Technology
  descriptions that exist only as a %1% template are resolved with their argument the way the app
  does (observedTechDescription) on both sides.
- age names, resource names (cost labels), weapon names, armor types, map names and the mechanics
  and score terms in MECHANICS (Golden Age, Sheep, Total Score ...), by exact text.

Keys are English text with whitespace collapsed (the app shows descriptions both line-split and
collapsed); values keep the official line breaks. A key whose locale ids disagree takes the most
common translation; the count is reported.

Usage: python -X utf8 scripts/build_zh_locale.py [--en UCS] [--zh UCS] [--out FILE]
"""
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRACT = Path('C:/Users/Sam/projects/games/kb/aoe4/extract/installed-24231237')
AGES = ['Dark Age', 'Feudal Age', 'Castle Age', 'Imperial Age']
ARMOR = ['Melee', 'Ranged', 'Fire', 'True Damage', 'Siege', 'Melee Armor', 'Ranged Armor']
# Game terms the engine, metrics and match summaries show that are not catalog record names.
MECHANICS = ['Golden Age', 'Sheep', 'Deer', 'Berry Bush', 'Berries', 'Boar', 'Fish', 'Population', 'Villagers',
             'Military Units', 'Landmark', 'Landmarks', 'Relic', 'Relics', 'Sacred Site', 'Sacred Sites', 'Camels',
             'Town Centers', 'Stables', 'Blacksmiths', 'Army Value', 'Resources Gathered', 'Total Score',
             'Society Score', 'Technology Score', 'Units Killed', 'Units Lost', 'Buildings Lost', 'Win Rate',
             'Age I', 'Age II', 'Age III', 'Age IV', 'Move Speed', 'Attack Speed', 'Health', 'Armor', 'Damage',
             'Infantry', 'Cavalry', 'Naval', 'Religious', 'Ship', 'Monk', 'Free for All', 'Influence']


def load_ucs(path):
    raw = path.read_bytes()
    text = raw.decode('utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig')
    out = {}
    for line in text.splitlines():
        key, sep, val = line.partition('\t')
        if sep and key.isdigit():
            out[int(key)] = val
    return out


def clean(value):
    # Same cleanup as scripts/populate_game_catalog.py clean_name, so English matches catalog text.
    return re.sub(r'<[^>]*>', '', value or '').replace('\\r\\n', '\n')


def norm(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def js_number(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def resolve_template(template, args):
    value = (args or {}).get('int_value', (args or {}).get('float_value'))
    filled = template.replace('%1%', js_number(value) if value is not None else '\u2014')
    return filled.replace('%%', '%')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--en', type=Path, default=EXTRACT / 'LocaleEnglish/en/cardinal.en.ucs')
    ap.add_argument('--zh', type=Path, default=EXTRACT / 'LocaleSimplifiedChinese/zh-hans/cardinal.zh-hans.ucs')
    ap.add_argument('--out', type=Path, default=ROOT / 'data/i18n-zh-game.json')
    args = ap.parse_args()

    en_raw, zh_raw = load_ucs(args.en), load_ucs(args.zh)
    en = {k: clean(v) for k, v in en_raw.items()}
    zh = {k: clean(v) for k, v in zh_raw.items()}
    by_text = defaultdict(list)
    for k in sorted(en):
        if en[k].strip():
            by_text[norm(en[k])].append(k)

    catalog = json.loads((ROOT / 'data/game-catalog.json').read_text(encoding='utf-8-sig'))
    preview = json.loads((ROOT / 'data/catalog-preview-17.0.json').read_text(encoding='utf-8-sig'))
    library = json.loads((ROOT / 'data/game-library.json').read_text(encoding='utf-8-sig'))

    votes = {'terms': defaultdict(Counter), 'text': defaultdict(Counter)}
    stats = Counter()
    missing = defaultdict(set)

    def usable(english, chinese):
        return chinese and chinese.strip() and norm(chinese) != norm(english)

    def by_english(section, english, kind, display=None):
        """Vote translations of every locale id whose English text equals `english`."""
        key = norm(english)
        if not key or not re.search('[A-Za-z]', key):
            return False
        ids = by_text.get(key, [])
        found = False
        for i in ids:
            if usable(en[i], zh.get(i)):
                chinese = zh[i]
                if display:
                    chinese = display(chinese)
                votes[section][norm(display(english) if display else english)][chinese.strip()] += 1
                found = True
        stats[kind + (' joined by text' if found else ' not in locale')] += 1
        if not found:
            missing[kind].add(key)
        return found

    records = [(kind, r, False) for kind in ('units', 'buildings', 'technologies') for r in catalog[kind]]
    records += [(kind, r, True) for kind in ('units', 'buildings', 'technologies') for r in preview.get(kind, [])]
    for kind, r, is_preview in records:
        label = ('preview ' if is_preview else '') + kind
        loc = r.get('nameLocalizationId')
        name = r.get('name') or ''
        if loc and not is_preview and norm(en.get(loc)) == norm(name) and usable(name, zh.get(loc)):
            votes['terms'][norm(name)][zh[loc].strip()] += 1
            stats[label + ' names joined by locale id'] += 1
        else:
            by_english('terms', name, label + ' names')
        if r.get('description'):
            by_english('text', r['description'], label + ' descriptions')
        elif kind == 'technologies' and r.get('descriptionTemplate'):
            template = r['descriptionTemplate']
            filled = lambda s, a=r.get('descriptionArguments'): resolve_template(s, a)
            by_english('text', template, label + ' template descriptions', display=filled)
        for w in r.get('weapon') or []:
            if w.get('name'):
                by_english('terms', w['name'], 'weapon names')

    for civ in catalog['civilizations'] + preview.get('civilizations', []):
        by_english('terms', civ['name'], 'civilization names')
    for age in AGES:
        by_english('terms', age, 'age names')
    labels = {v for kind in ('units', 'buildings', 'technologies') for r in catalog[kind] for v in (r.get('costLabels') or {}).values()}
    labels |= {r['name'] for r in catalog.get('resourceTypes', [])}
    for label in sorted(labels):
        if label not in ('action', 'popcap'):
            by_english('terms', label, 'resource names')
    for label in ARMOR:
        by_english('terms', label, 'armor and damage types')
    for label in MECHANICS:
        by_english('terms', label, 'mechanics and score terms')
    maps = {g.get('map') for g in library.get('games', []) + library.get('matches', []) if g.get('map')}
    for m in sorted(maps):
        by_english('terms', m, 'map names')

    out = {}
    disagreements = Counter()
    for section in ('terms', 'text'):
        out[section] = {}
        for key in sorted(votes[section], key=str.lower):
            ranked = votes[section][key].most_common()
            if len(ranked) > 1:
                disagreements[section] += 1
            out[section][key] = ranked[0][0]

    payload = {
        '_comment': ('Generated by scripts/build_zh_locale.py; do not edit by hand. Official Simplified Chinese text from the '
                     'installed game locale. terms: game names (units, buildings, technologies, civilizations, ages, '
                     'resources, weapons, armor types, maps); text: descriptions. Keys are English with whitespace '
                     'collapsed; site/i18n.js looks them up before data/i18n-zh-ui.json.'),
        'source': {
            'steamBuild': catalog.get('provenance', {}).get('steamBuildId'),
            'en': {'file': args.en.name, 'sha256': sha(args.en), 'strings': len(en_raw)},
            'zh': {'file': args.zh.name, 'sha256': sha(args.zh), 'strings': len(zh_raw)},
            'joined': dict(sorted(stats.items())),
            'disagreements': dict(disagreements),
            'namesNotInLocale': {k: sorted(v)[:60] for k, v in sorted(missing.items()) if 'description' not in k},
        },
        'terms': out['terms'],
        'text': out['text'],
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=0, separators=(',', ':')) + '\n', encoding='utf-8')
    print(args.out, args.out.stat().st_size // 1024, 'KB')
    print('terms', len(out['terms']), 'text', len(out['text']), 'disagreements', dict(disagreements))
    for k, v in sorted(stats.items()):
        print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
