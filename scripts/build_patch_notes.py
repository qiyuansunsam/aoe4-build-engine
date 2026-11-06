"""Build data/patch-notes.json: the official release notes of the installed update as readable, linked sections.

Input:  data/patch-next/raw/update-17-0-12260-page.html  (the official article as downloaded; URL in SOURCE_URL)
        data/game-catalog.json, data/catalog-enrichment.json (names to link, read only)
Output: data/patch-notes.json  (window.PATCH_NOTES; site/patch-notes.js renders it)

The article's change lists are kept verbatim: headings, list items (with their nesting), map / topic labels and
developer notes. The launch announcement of the expansion, images and the site's own footer blocks are left out.
Every list item is split into text and references: a reference is a unit, building or technology of the installed
catalog named in the line (longest name first, plural forms included). Inside a civilization's section a name
resolves to that civilization's record; elsewhere a name that only one civilization (and its variant) owns resolves
to that record, and a shared name resolves to one representative record. Each item also lists the civilizations it
concerns outside its own section: civilizations named in the line and owners of a referenced record that is theirs
alone. The Library uses that list for a civilization's notes.

Usage: python -X utf8 scripts/build_patch_notes.py
"""
import json, re, sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data/patch-next/raw/update-17-0-12260-page.html'
OUT = ROOT / 'data/patch-notes.json'
SOURCE_URL = 'https://www.ageofempires.com/news/age-of-empires-iv-update-17-0/'
META = {'version': '17.0.12260', 'title': 'Update 17.0', 'released': '2026-10-29', 'hotfix': '2026-11-04', 'notesUpdated': '2026-11-03',
        'downloadedAt': '2026-11-06', 'sourceUrl': SOURCE_URL}

FIRST, LAST = 'Build Spotlight', 'Become an Age Insider!'
SKIP_SECTIONS = {"What's on the Horizon"}
SKIP_GROUPS = {('Build Spotlight', 'Raiders of the North is Available October 29!')}
NO_PARAGRAPHS = {'Build Spotlight'}                     # announcement prose; its lists stay
SKIP_PARAGRAPH = re.compile(r"^(Editor's note|Please Note)", re.I)
CIV_SECTION = 'Civilization-Specific Changes'
# Section headings of the article that are not the catalog's civilization name.
CIV_HEADINGS = {'Macedonians': 'byzantine_ha_mac'}
# How a line names a civilization besides its catalog name.
CIV_ALIASES = {
    'abbasid': ['Abbasid'], 'abbasid_ha_01': ['Ayyubid'], 'byzantine': ['Byzantine'], 'byzantine_ha_mac': ['Macedonians', 'Macedonian'],
    'hre': ['HRE'], 'japanese_ha_sen': ['Sengoku'], 'jin_dynasty': ['Jin'], 'lancaster': ['Lancaster'], 'malian': ['Malian'],
    'mongol': ['Mongol'], 'ottoman': ['Ottoman'], 'scots': ['Scottish'], 'sultanate': ['Delhi'], 'sultanate_ha_tug': ['Tughlaq'],
    'templar': ['Templar'], 'vikings': ['Viking'],
}
# Catalog names that read as ordinary words in the notes, or as something other than the record.
STOP_NAMES = {'Trade', 'Gold', 'Stone', 'Food', 'Wood', 'Fire', 'Capital', 'Outpost Arrowslits', 'Sheep', 'Deer', 'Wolf', 'Boar', 'Camp'}
TIER_PREFIX = re.compile(r'^(?:Early|Hardened|Veteran|Elite|Vanguard) ')
# How the notes write a record the catalog names differently: form in the notes -> catalog name.
WRITTEN_AS = {'Ram': 'Battering Ram', 'Rams': 'Battering Ram', 'Trebuchet': 'Counterweight Trebuchet', 'Trebuchets': 'Counterweight Trebuchet',
              'Pasture & Loom': 'Pasture and Loom'}


def straight(text):
    """Same-length copy with typographic quotes made plain, so offsets match the original."""
    return text.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')


class Notes(HTMLParser):
    """Flat walk of the article: headings, paragraphs, labels, developer notes and nested lists."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections, self.section, self.group = [], None, None
        self.active = False
        self.capture = None      # ('h2'|'h3'|'p'|'li', buffer)
        self.lists = []          # stack of item lists being filled
        self.items = []          # stack of open <li> items
        self.quote = 0
        self.strong_only = None  # paragraph made of one <strong>: a label
        self.skip = 0            # depth inside figure / script / style / nav blocks

    def text(self, buf):
        return re.sub(r'\s+', ' ', ''.join(buf)).strip()

    def blocks(self):
        if self.group is None:
            self.group = {'title': None, 'blocks': []}
            self.section['groups'].append(self.group)
        return self.group['blocks']

    def handle_starttag(self, tag, attrs):
        if tag in ('figure', 'script', 'style', 'picture', 'form'):
            self.skip += 1
        if self.skip:
            return
        if tag in ('h2', 'h3'):
            self.capture = (tag, [])
        if not self.active or self.section is None:
            return
        if tag == 'blockquote':
            self.quote += 1
        elif tag == 'ul' or tag == 'ol':
            if self.items:
                self.flush_item_text()
                self.lists.append(self.items[-1]['children'])
            else:
                block = {'type': 'list', 'items': []}
                self.blocks().append(block)
                self.lists.append(block['items'])
        elif tag == 'li' and self.lists:
            item = {'text': '', 'children': []}
            self.lists[-1].append(item)
            self.items.append(item)
            self.capture = ('li', [])
        elif tag == 'p' and not self.items:
            self.capture = ('p', [])
            self.strong_only = {'strong': 0, 'outside': False}
        elif tag == 'strong' and self.capture and self.capture[0] == 'p':
            self.strong_only['strong'] += 1
            self.strong_only['in'] = True

    def flush_item_text(self):
        if self.capture and self.capture[0] == 'li' and self.items and not self.items[-1]['text']:
            self.items[-1]['text'] = self.text(self.capture[1])
        if self.capture and self.capture[0] == 'li':
            self.capture = ('li-done', [])

    def handle_endtag(self, tag):
        if tag in ('figure', 'script', 'style', 'picture', 'form'):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in ('h2', 'h3') and self.capture and self.capture[0] == tag:
            title = straight(self.text(self.capture[1]))
            self.capture = None
            if tag == 'h2':
                if title == FIRST:
                    self.active = True
                elif title == LAST:
                    self.active = False
                if self.active:
                    self.section = None if title in SKIP_SECTIONS else {'title': title, 'groups': []}
                    self.group = None
                    if self.section:
                        self.sections.append(self.section)
            elif self.active and self.section is not None and title:
                self.group = {'title': title, 'blocks': []}
                self.section['groups'].append(self.group)
            return
        if not self.active or self.section is None:
            return
        if tag == 'blockquote':
            self.quote = max(0, self.quote - 1)
        elif tag == 'strong' and self.strong_only is not None:
            self.strong_only['in'] = False
        elif tag == 'p' and self.capture and self.capture[0] == 'p':
            text = self.text(self.capture[1])
            label = self.strong_only and self.strong_only['strong'] == 1 and not self.strong_only['outside']
            self.capture, self.strong_only = None, None
            if text:
                kind = 'note' if self.quote else 'label' if label and len(text) < 60 else 'para'
                self.blocks().append({'type': kind, 'text': text})
        elif tag == 'li' and self.items:
            self.flush_item_text()
            self.items.pop()
            self.capture = ('li-done', []) if self.items else None
        elif tag in ('ul', 'ol') and self.lists:
            self.lists.pop()

    def handle_data(self, data):
        if self.skip or not self.capture:
            return
        if self.capture[0] == 'p' and self.strong_only is not None and not self.strong_only.get('in') and data.strip():
            self.strong_only['outside'] = True
        if self.capture[0] != 'li-done':
            self.capture[1].append(data)


def plural_forms(name):
    forms = {name, name + 's'}
    if name.endswith('man'):
        forms.add(name[:-3] + 'men')
    if name.endswith('men'):                             # the catalog names some units in the plural
        forms.add(name[:-3] + 'man')
    if 'Man-at-Arms' in name:
        forms.add(name.replace('Man-at-Arms', 'Men-at-Arms'))
    if name.endswith('y') and name[-2:] not in ('ay', 'ey', 'oy'):
        forms.add(name[:-1] + 'ies')
    if name.endswith(('s', 'x', 'ch', 'sh')):
        forms.add(name + 'es')
    return forms


def main():
    catalog = json.loads((ROOT / 'data/game-catalog.json').read_text(encoding='utf-8'))
    meta = json.loads((ROOT / 'data/catalog-enrichment.json').read_text(encoding='utf-8'))
    civ_name = {c['id']: c['name'] for c in catalog['civilizations']}
    civ_by_heading = {straight(v): k for k, v in civ_name.items()} | CIV_HEADINGS

    index, form_to_name = defaultdict(list), {}
    for kind in ('units', 'buildings', 'technologies'):
        for r in catalog[kind]:
            name = straight(r.get('name') or '')
            if len(name) < 3 or not name[0].isupper() or name in STOP_NAMES or r.get('civilization') not in civ_name:
                continue
            index[name].append((kind, r))
    for name in index:
        for form in plural_forms(name):
            form_to_name.setdefault(form, name)
    for name in index:               # an exact name always wins over another name's plural
        form_to_name[name] = name
    for form, name in WRITTEN_AS.items():
        if name not in index:
            sys.exit(f'WRITTEN_AS names a record the catalog does not have: {name!r}')
        form_to_name[form] = name
    forms = sorted(form_to_name, key=len, reverse=True)
    matcher = re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(f) for f in forms) + r')(?!\w)')
    owners = {name: {r['civilization'] for _, r in rows} for name, rows in index.items()}

    def rank(entry):
        kind, r = entry
        m = meta.get(r['id']) or {}
        tier = re.search(r'_(\d)_', r['id'])
        return (m.get('available') is False or m.get('rosterAvailable') is False, bool(TIER_PREFIX.match(r['name'])),
                r.get('age') or (int(tier.group(1)) if tier else 9), 'landmark' in r['id'], len(r['id']), r['id'])

    def pick(name, civ):
        rows = index[name]
        own = [e for e in rows if e[1]['civilization'] == civ] if civ else []
        if not own and civ and '_ha_' in civ:                       # a variant falls back to its parent civilization
            own = [e for e in rows if e[1]['civilization'] == civ.split('_ha_')[0]]
        pool = own or ([e for e in rows if e[1]['civilization'] == 'english'] if len(owners[name]) > 2 else rows) or rows
        return min(pool, key=rank)

    alias_patterns = []
    for civ, name in civ_name.items():
        for alias in [straight(name)] + CIV_ALIASES.get(civ, []):
            alias_patterns.append((civ, re.compile(r'(?<![A-Za-z])' + re.escape(alias) + r"(?:'s)?(?![A-Za-z])")))

    stats = Counter()

    def family(civ):
        return civ.split('_ha_')[0]

    def link(text, civ, second=False):
        plain, segs, last, civs = straight(text), [], 0, set()
        if not civ and not second:
            # Outside a civilization's section, a line that concerns one civilization resolves shared names to it.
            _, concerned = link(text, None, True)
            exact = {c for c in concerned if any(p.search(plain) for a, p in alias_patterns if a == c)} or concerned
            if len(exact) == 1 or len({family(c) for c in exact}) == 1:
                civ = sorted(exact, key=len)[0]
        for m in matcher.finditer(plain):
            name = form_to_name[m.group(0)]
            kind, record = pick(name, civ)
            if m.start() > last:
                segs.append(text[last:m.start()])
            segs.append({'r': record['id'], 'n': text[m.start():m.end()], 'k': kind[:-1] if kind != 'technologies' else 'technology'})
            last = m.end()
            if not second:
                stats[name] += 1
            if len(owners[name]) <= 2:
                civs |= owners[name]
        if last < len(text):
            segs.append(text[last:])
        for alias_civ, pattern in alias_patterns:
            if pattern.search(plain):
                civs.add(alias_civ)
        if 'Jin' in plain and 'jin_dynasty' in civs and not re.search(r'(?<![A-Za-z])Jin(?: Dynasty)?(?![A-Za-z])', plain):
            civs.discard('jin_dynasty')
        return segs, civs

    parser = Notes()
    parser.feed(RAW.read_text(encoding='utf-8', errors='replace'))

    def convert(items, civ):
        out = []
        for item in items:
            segs, civs = link(item['text'], civ)
            node = {'segs': segs}
            if civs - ({civ} if civ else set()):
                node['civs'] = sorted(civs - ({civ} if civ else set()))
            if item['children']:
                node['children'] = convert(item['children'], civ)
            out.append(node)
        return out

    def lines(items):
        return sum(1 + lines(i.get('children', [])) for i in items)

    sections, counts = [], Counter()
    for s in parser.sections:
        groups = []
        for g in s['groups']:
            if (s['title'], g['title']) in SKIP_GROUPS:
                continue
            civ = civ_by_heading.get(g['title']) if s['title'] == CIV_SECTION else None
            if s['title'] == CIV_SECTION and g['title'] and not civ:
                sys.exit(f'No catalog civilization for the section heading {g["title"]!r}')
            blocks = []
            for b in g['blocks']:
                if b['type'] == 'list':
                    items = convert(b['items'], civ)
                    if items:
                        blocks.append({'type': 'list', 'items': items})
                        counts['items'] += lines(items)
                elif b['type'] == 'para' and (s['title'] in NO_PARAGRAPHS or SKIP_PARAGRAPH.match(straight(b['text']))):
                    continue
                elif b['type'] == 'label':
                    blocks.append({'type': 'label', 'text': b['text']})
                else:
                    segs, civs = link(b['text'], civ)
                    blocks.append({'type': b['type'], 'segs': segs})
            if blocks:
                group = {'title': g['title'], 'blocks': blocks}
                if civ:
                    group['civ'] = civ
                groups.append(group)
        if groups:
            sid = re.sub(r'[^a-z0-9]+', '-', s['title'].lower()).strip('-')
            sections.append({'id': sid, 'title': s['title'], 'groups': groups})
            counts['sections'] += 1
            counts['groups'] += len(groups)
    refs = sum(stats.values())
    OUT.write_text(json.dumps({'schemaVersion': 1, **META, 'counts': {**counts, 'references': refs, 'namesLinked': len(stats)}, 'sections': sections},
                              ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(OUT, OUT.stat().st_size // 1024, 'KB', dict(counts), 'references', refs, 'names', len(stats))
    for s in sections:
        print(' ', s['title'], '|', ', '.join(f"{g['title']}({sum(len(b.get('items', [])) for b in g['blocks'])})" for g in s['groups'])[:300])
    print('most linked:', ', '.join(f'{n} {c}' for n, c in stats.most_common(70)))
    print('short or single-word names linked:', ', '.join(sorted(n for n in stats if ' ' not in n and '-' not in n)))


if __name__ == '__main__':
    main()
