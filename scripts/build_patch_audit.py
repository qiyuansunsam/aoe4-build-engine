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
        'status':'matches-pre-release-value' if value==expected else 'requires-review',
        'source':record.get('entitySource',record['source']),'notesUrl':preview,
        'applied':False,'reason':'17.0 is a preview scheduled for 2026-10-29; audit date is 2026-10-23.'})
out={
    'schemaVersion':1,'checkedAt':'2026-10-23','status':'installed-build-matches-latest-released-notes',
    'installed':{'patch':catalog['provenance']['patch'],'steamBuildId':catalog['provenance']['steamBuildId'],
        'executableVersion':catalog['provenance']['executableVersion'],
        'executablePath':'C:/Program Files (x86)/Steam/steamapps/common/Age of Empires IV/RelicCardinal.exe',
        'evidence':'Windows executable ProductVersion read without launching the game.',
        'archiveSha256':catalog['provenance']['sha256']},
    'latestReleased':{'version':'16.3.11308','url':released,'notesPublishedAt':'2026-06-18',
        'releaseDate':None,'dateNote':'Hotfix appended to older notes; no separate publication date stated.',
        'summary':'The appended hotfix addresses a console startup crash. No balance changes are listed for it.',
        'balanceChangesListed':False},
    'preview':{'version':'17.0','status':'announced-not-released','publishedAt':'2026-10-22',
        'scheduledRelease':'2026-10-29','url':preview,'appliedToCatalog':False,
        'summary':'Upcoming changes remain separate from installed facts. Re-extract after the game updates.'},
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
print(f'Patch audit: {len(checks)} preview comparisons; {out["latestReleased"]["version"]} released; no preview changes applied')
