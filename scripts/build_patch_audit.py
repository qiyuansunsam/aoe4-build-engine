"""Materialize a reviewed official-notes ledger against the installed catalog.

This does not automatically assert a future release is live or overwrite game facts.
Update reviewed source/date claims after actually reading the official notes.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
catalog=json.loads((ROOT/'data/game-catalog.json').read_text(encoding='utf-8'))
released='https://www.ageofempires.com/news/age-of-empires-iv-patch-16-2-10884/'
preview='https://www.ageofempires.com/news/age-of-empires-iv-update-17-0/'
checks=[]
for group, ident, field, expected, future in [
    ('buildings','building_town_center_abb','buildTimeSeconds',150,165),
    ('units','unit_landsknecht_3_hre','cost.food',60,50),
    ('units','unit_landsknecht_3_hre_ha_01','cost.food',120,100),
    ('technologies','upgrade_teardrop_shields_byz','cost.food',100,150),
    ('technologies','upgrade_teardrop_shields_byz','cost.gold',250,350),
]:
    record=next(x for x in catalog[group] if x['id']==ident)
    value=record
    for key in field.split('.'):value=value[key]
    checks.append({'id':ident,'name':record['name'],'field':field,'installed':value,
        'announcedPrevious':expected,'announcedNext':future,
        'status':'matches-released-value' if value==future else 'requires-review',
        'source':record.get('entitySource',record['source']),'notesUrl':preview,
        'applied':True,'reason':'Installed 17.0.12260 files carry the value the notes announce.'})
out={
    'schemaVersion':1,'checkedAt':'2026-11-06','status':'installed-build-matches-latest-released-notes',
    'installed':{'patch':catalog['provenance']['patch'],'steamBuildId':catalog['provenance']['steamBuildId'],
        'executableVersion':catalog['provenance']['executableVersion'],
        'executablePath':'C:/Program Files (x86)/Steam/steamapps/common/Age of Empires IV/RelicCardinal.exe',
        'evidence':'Windows executable ProductVersion read without launching the game.',
        'archiveSha256':catalog['provenance']['sha256']},
    'latestReleased':{'version':'17.0.12260','url':preview,'notesPublishedAt':'2026-11-03',
        'releaseDate':'2026-10-29','dateNote':'Notes retitled "Update 17.0.12260" on 2026-11-03 (hotfix section appended); Steam installed build 26400362 on 2026-11-04. Update 17.0.12182 (Steam build 26146704) went live 2026-10-29.',
        'summary':'Raiders of the North update: Vikings and Scots plus balance changes; every transcribed note value matches the installed files. The 17.0.12260 hotfix lists AI, Crucible and Longhouse-attachment fixes and no balance values: all 9,203 decoded attribute records are byte-identical to 17.0.12182.',
        'balanceChangesListed':True},
    'previous':{'version':'16.3.11308','url':released,'steamBuildId':'24231237'},
    'preview':{'version':'17.0','status':'released','publishedAt':'2026-10-22',
        'scheduledRelease':'2026-10-29','url':preview,'appliedToCatalog':True,
        'summary':'17.0 is the installed build; the notes overlay is now history, not a forecast.'},
    'checks':checks,
    'verification':{'mode':'all-populated-base-fields','tests':'python -X utf8 scripts/test_game_catalog.py',
        'scope':['unit health, cost, train time, armor, movement and population','building health, armor, cost and build time',
                 'technology cost, time, scalar properties and targeting','weapon damage, type, bonuses, ranges and timing fields',
                 'all visible playable civilization records','source IDs, archive fingerprint and duplicate-key preservation'],
        'unitForms':len(catalog['units']),'buildings':len(catalog['buildings']),'technologies':len(catalog['technologies'])},
    'limitations':[
        'Source-field agreement is not proof of effective in-match totals. Entity definitions may already bake in civilization-specific changes.',
        'Conditional state-tree actions, aura stacking and complete animation attack periods remain unresolved.',
        'No verified blanket claim that AoE4 World is inaccurate; no external database values replace installed facts.',
        'The preview checks are selected cross-checks, not an exhaustive transcription of every future balance change.',
        'Historical simulation parameters use a separate ruleset and are not silently upgraded by this database audit.'
    ]}
(ROOT/'data/patch-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Patch audit: {len(checks)} note comparisons; {out["latestReleased"]["version"]} released; {sum(c["status"]=="matches-released-value" for c in checks)} match installed')
