"""Add 104x56 flags for the 17.0 preview civilizations (Vikings, Scots) to data/civilization-flags.json.

The installed game and the aoe4world overlay flag set have no Vikings or Scots art yet. jeandogaming.com hosts their
vertical banners (images/flag-rotated/<Civ>_AoE4.png, 563x1000). This composes a horizontal flag in the size the
Library uses: the banner's cloth (top band, scaled to 104x56) as background and the emblem band centred at full
height. Pixels are derived, not the original art; provenance goes to data/civilization-flags-provenance.json.
Usage: python -X utf8 scripts/package_preview_flags.py   (banners cached in .cache/flags/<Civ>.png)
"""
import base64, hashlib, io, json, pathlib, urllib.request
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache/flags'
URL = 'https://jeandogaming.com/images/flag-rotated/{}_AoE4.png'
CIVS = {'vikings': 'Vikings', 'scots': 'Scots'}
MODE = {'vikings': 'emblem', 'scots': 'crop'}  # Vikings banner = raven emblem on cloth; Scots banner = saltire pattern
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'

def compose(banner, mode='emblem'):
    banner = banner.convert('RGBA'); w, h = banner.size
    if mode == 'crop':  # a patterned banner: take the centre at the flag's aspect ratio
        ch = int(w * 56 / 104); top = (h - ch) // 2
        return banner.crop((0, top, w, top + ch)).resize((104, 56), Image.LANCZOS)
    cloth = banner.crop((0, 0, w, int(h * 0.16))).resize((104, 56), Image.LANCZOS)
    emblem = banner.crop((0, int(h * 0.18), w, int(h * 0.80)))
    emblem.thumbnail((104, 56), Image.LANCZOS)
    out = cloth.copy(); out.alpha_composite(emblem, ((104 - emblem.width) // 2, (56 - emblem.height) // 2))
    return out

def main():
    flags_path = ROOT / 'data/civilization-flags.json'; flags = json.loads(flags_path.read_text(encoding='utf-8'))
    prov_path = ROOT / 'data/civilization-flags-provenance.json'; prov = json.loads(prov_path.read_text(encoding='utf-8'))
    CACHE.mkdir(parents=True, exist_ok=True)
    added = []
    for civ, name in CIVS.items():
        src = CACHE / f'{name}.png'
        if not src.exists():
            with urllib.request.urlopen(urllib.request.Request(URL.format(name), headers={'User-Agent': UA}), timeout=30) as r: src.write_bytes(r.read())
        buf = io.BytesIO(); compose(Image.open(src), MODE[civ]).save(buf, 'PNG', optimize=True)
        flags[civ] = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        added.append({'civilization': civ, 'source': URL.format(name), 'sourceSha256': hashlib.sha256(src.read_bytes()).hexdigest(),
                      'outputSha256': hashlib.sha256(buf.getvalue()).hexdigest(), 'size': [104, 56],
                      'note': '17.0 preview civilization: ' + ('cloth background + centred emblem' if MODE[civ] == 'emblem' else 'centre crop') + ' of the vertical banner; not original flag art'})
    entries = prov.get('preview17', []) if isinstance(prov, dict) else []
    entries = [e for e in entries if e['civilization'] not in CIVS] + added
    if isinstance(prov, dict): prov['preview17'] = entries
    flags_path.write_text(json.dumps(flags, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')  # same compact form as the packaged file
    prov_path.write_text(json.dumps(prov, ensure_ascii=False, indent=1), encoding='utf-8')
    for civ in CIVS:
        pathlib.Path(CACHE / f'{civ}_flag.png').write_bytes(base64.b64decode(flags[civ].split(',')[1]))
    print('flags added', list(CIVS))

if __name__ == '__main__':
    main()
