"""Package the existing authentic civilization flag cache without modifying pixels."""
from pathlib import Path
import base64
import hashlib
import io
import json
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'aoe4world/public/assets/flags'
SOURCE = 'https://raw.githubusercontent.com/aoe4world/overlay/main/src/assets/flags/'
FILES = {
    'abbasid': 'abbasid_dynasty', 'abbasid_ha_01': 'ayyubids',
    'byzantine': 'byzantines', 'byzantine_ha_mac': 'macedonian_dynasty',
    'chinese': 'chinese', 'chinese_ha_01': 'zhu_xis_legacy',
    'english': 'english', 'french': 'french', 'french_ha_01': 'jeanne_darc',
    'hre': 'holy_roman_empire', 'hre_ha_01': 'order_of_the_dragon',
    'japanese': 'japanese', 'japanese_ha_sen': 'sengoku_daimyo',
    'jin_dynasty': 'jin_dynasty', 'lancaster': 'house_of_lancaster',
    'malian': 'malians', 'mongol': 'mongols', 'mongol_ha_gol': 'golden_horde',
    'ottoman': 'ottomans', 'rus': 'rus', 'sultanate': 'delhi_sultanate',
    'sultanate_ha_tug': 'tughlaq_dynasty', 'templar': 'knights_templar',
}

def main():
    catalog = json.loads((ROOT / 'data/game-catalog.json').read_text(encoding='utf-8'))
    civilizations = catalog['civilizations']
    assert set(FILES) == {c['id'] for c in civilizations}, 'Flag mapping must cover exact installed civilization set'
    flags, evidence = {}, []
    for civ in civilizations:
        name = FILES[civ['id']]
        source = CACHE / (name + '.png')
        body = source.read_bytes()
        with Image.open(io.BytesIO(body)) as im:
            assert im.format == 'PNG'
            size = im.size
            im.verify()
        uri = 'data:image/png;base64,' + base64.b64encode(body).decode('ascii')
        flags[civ['id']] = uri
        flags[name] = uri  # AoE4 World / observed game alias
        evidence.append({
            'id': civ['id'], 'name': civ['name'], 'alias': name,
            'sourceType': 'existing-aoe4world-art-cache',
            'cachePath': str(source), 'sourceUrl': SOURCE + name + '.png',
            'sha256': hashlib.sha256(body).hexdigest(), 'size': list(size),
            'installedIconReference': civ.get('icon'),
            'variantFallback': False,
        })
    (ROOT / 'data/civilization-flags.json').write_text(json.dumps(flags, separators=(',', ':')), encoding='utf-8')
    (ROOT / 'data/civilization-flags-provenance.json').write_text(json.dumps({
        'schemaVersion': 1,
        'civilizationCount': len(civilizations),
        'sourceNote': 'Cached by mcaoe/scripts/sync-assets.py from the AoE4 World overlay artwork repository. Exact civilization and variant artwork; no parent-civilization fallbacks or pixel changes.',
        'flags': evidence,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Packaged {len(evidence)} authentic flags, {len(flags)} installed/observed keys; all PNG payloads verified')

if __name__ == '__main__':
    main()
