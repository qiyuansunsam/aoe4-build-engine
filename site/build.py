"""Inline engine.js into index.template.html -> dist/index.html (single file).

Usage: python -X utf8 site/build.py [--out DIR] [--extra-css FILE ...] [--extra-js FILE ...]
--out writes the page to another directory (used for isolated UI variants); it does not copy
game-perspectives there. --extra-css/--extra-js append experiment files after the shared sources.
--split-data writes content-addressed data scripts in OUT/data, splitting large JSON into bounded
chunks loaded in order. It also copies referenced evidence and game-perspectives; Cloudflare caps files at 25 MiB
(deploy/README.md).
"""
import os, pathlib, json, shutil, argparse, hashlib
here = pathlib.Path(__file__).parent
parser = argparse.ArgumentParser()
parser.add_argument("--out", default=str(here / "dist"))
parser.add_argument("--extra-css", action="append", default=[])
parser.add_argument("--extra-js", action="append", default=[])
parser.add_argument("--split-data", action="store_true")
args = parser.parse_args()
out = pathlib.Path(args.out)
# site/uplift/active.json selects the UI uplift variant files that ship in the default build:
# {"css": ["site/uplift/chart-a.css", ...], "js": ["site/uplift/chart-a.js", ...]} (paths relative to the repo root).
active = here / "uplift" / "active.json"
if active.exists() and not args.extra_css and not args.extra_js:
    chosen = json.loads(active.read_text(encoding="utf-8"))
    args.extra_css = [str(here.parent / f) for f in chosen.get("css", [])]
    args.extra_js = [str(here.parent / f) for f in chosen.get("js", [])]
# engine.js (historical Abbasid engine) dispatches other civilizations to engine-civs.js (installed 16.3 rules).
eng = open(here / "engine.js", encoding="utf-8").read() + "\n" + open(here / "engine-civs.js", encoding="utf-8").read()
# civilization mechanics modules (site/civ-mech/<civ>.js) register themselves after engine-civs.js
for f in sorted((here / "civ-mech").glob("*.js")):
    eng += "\n" + f.read_text(encoding="utf-8")
html = open(here / "index.template.html", encoding="utf-8").read()
for marker, filename in [("/*__CRAFTER_CSS__*/", "crafter.css"), ("/*__CRAFTER_JS__*/", "crafter.js"), ("/*__CONTEXT_CSS__*/", "context-actions.css"), ("/*__CATALOG_CSS__*/", "catalog.css"), ("/*__GAMES_CSS__*/", "games.css"), ("/*__CONTEXT_JS__*/", "context-actions.js"), ("/*__I18N_CSS__*/", "i18n.css"), ("/*__I18N_JS__*/", "i18n.js")]:
    content = (here / filename).read_text(encoding="utf-8")
    if filename == "crafter.js":
        content = (here / "observed-army.js").read_text(encoding="utf-8") + "\n" + (here / "observed-derived.js").read_text(encoding="utf-8") + "\n" + (here / "unit-tiers.js").read_text(encoding="utf-8") + "\n" + content + "\n" + (here / "players.js").read_text(encoding="utf-8") + "\n" + (here / "winrates.js").read_text(encoding="utf-8") + "\n" + (here / "patch-notes.js").read_text(encoding="utf-8") + "\n" + (here / "patch-changes.js").read_text(encoding="utf-8")
    if filename == "crafter.css":
        content += "\n" + (here / "build-timeline.css").read_text(encoding="utf-8")
    if filename == "games.css":
        content += "\n" + (here / "unit-tiers.css").read_text(encoding="utf-8") + "\n" + (here / "players.css").read_text(encoding="utf-8") + "\n" + (here / "winrates.css").read_text(encoding="utf-8") + "\n" + (here / "patch-notes.css").read_text(encoding="utf-8") + "\n" + (here / "patch-changes.css").read_text(encoding="utf-8")
        for extra in args.extra_css:
            content += "\n/* extra: " + extra + " */\n" + pathlib.Path(extra).read_text(encoding="utf-8")
    if filename == "context-actions.js":
        for extra in args.extra_js:
            content += "\n/* extra: " + extra + " */\n" + pathlib.Path(extra).read_text(encoding="utf-8")
    html = html.replace(marker, content.replace("</script", "<\\/script"))
html = html.replace("/*__ENGINE__*/", eng.replace("</script", "<\\/script"))
out.mkdir(parents=True, exist_ok=True)
data_scripts = []
evidence_files = set()


def write_data_scripts(filename, text):
    """Content-addressed classic scripts preserve load order and stay below asset limits."""
    folder = out / "data"
    folder.mkdir(parents=True, exist_ok=True)
    key = json.dumps(filename)
    stem = filename.rsplit(".", 1)[0]
    prefix = "(window.__AOE_DATA=window.__AOE_DATA||{})[" + key + "]="
    direct = prefix + text + ";\n"
    scripts = []
    if len(direct.encode("utf-8")) <= 16 * 1024 * 1024:
        scripts.append(direct)
    else:
        # Two million Unicode characters need at most 12 MB after JSON string
        # escaping. Joining and parsing happens once, after the final script.
        chunks = [text[i:i + 2_000_000] for i in range(0, len(text), 2_000_000)]
        for index, chunk in enumerate(chunks):
            script = ("(window.__AOE_JSON=window.__AOE_JSON||{})[" + key + "]=[];\n") if index == 0 else ""
            script += "window.__AOE_JSON[" + key + "].push(" + json.dumps(chunk, ensure_ascii=False) + ");\n"
            if index == len(chunks) - 1:
                script += prefix + "JSON.parse(window.__AOE_JSON[" + key + "].join(''));delete window.__AOE_JSON[" + key + "];\n"
            scripts.append(script)
    written = set()
    for index, script in enumerate(scripts):
        encoded = script.encode("utf-8")
        if len(encoded) > 16 * 1024 * 1024:
            raise ValueError(f"Generated data chunk too large: {filename}/{index}")
        digest = hashlib.sha256(encoded).hexdigest()[:16]
        name = f"{stem}.{index:03d}.{digest}.js"
        (folder / name).write_bytes(encoded)
        written.add(name)
        data_scripts.append(f'<script src="data/{name}"></script>')
    # Only this builder's generated dataset scripts are removed, never source data.
    for candidate in [folder / (stem + '.js'), *folder.glob(stem + '.*.js')]:
        if candidate.is_file() and candidate.name not in written:
            assert candidate.resolve().is_relative_to(out.resolve())
            candidate.unlink()

for marker, filename in [("/*__BUILD_LIBRARY__*/", "build-library.json"), ("/*__GAME_CATALOG__*/", "game-catalog.json"), ("/*__PATCH_AUDIT__*/", "patch-audit.json"), ("/*__GAME_LIBRARY__*/", "game-library.json"), ("/*__GAME_ICONS__*/", "game-icons.json"), ("/*__CIV_FLAGS__*/", "civilization-flags.json"), ("/*__CATALOG_META__*/", "catalog-enrichment.json"), ("/*__PATCH_NEXT__*/", "patch-next.json"), ("/*__PREVIEW_CATALOG__*/", "catalog-preview-17.0.json"), ("/*__CATALOG_AGES__*/", "catalog-ages.json"), ("/*__I18N_ZH_GAME__*/", "i18n-zh-game.json"), ("/*__I18N_ZH_UI__*/", "i18n-zh-ui.json"), ("/*__CIV_ENGINE_RULES__*/", "civ-engine-rules.json"), ("/*__THEORY_BUILDS__*/", "theory-builds.json"), ("/*__PLAYER_PROFILES__*/", "player-profiles.json"), ("/*__PLAYER_ANALYSIS__*/", "player-analysis.json"), ("/*__UNIT_USAGE_TIERS__*/", "unit-usage-tiers.json"), ("/*__WINRATES__*/", "winrates.json"), ("/*__PATCH_NOTES__*/", "patch-notes.json"), ("/*__PATCH_CHANGES__*/", "patch-changes.json")]:
    if marker in html:
        source = here.parent / "data" / filename
        if not source.exists():
            raise FileNotFoundError(f"Required UI data missing: {source}")
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
        if filename == "unit-usage-tiers.json":
            evidence_files.update(item['calculationUrl'].rsplit('/', 1)[-1]
                                  for cohort in payload.get('cohorts', []) for item in cohort.get('items', [])
                                  if item.get('calculationUrl', '').startswith('data/tier-evidence/'))
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        if args.split_data:
            key = json.dumps(filename)
            write_data_scripts(filename, text)
            html = html.replace(marker, "window.__AOE_DATA[" + key + "]")
        else:
            html = html.replace(marker, text)
if data_scripts:
    html = html.replace("</head>", "".join(data_scripts) + "</head>", 1)
os.makedirs(out, exist_ok=True)

if (here.parent / "data/tier-evidence").exists():
    evidence_out = out / "data/tier-evidence"
    evidence_out.mkdir(parents=True, exist_ok=True)
    for name in sorted(evidence_files):
        if pathlib.Path(name).name != name:
            raise ValueError("Invalid evidence filename")
        shutil.copy2(here.parent / "data/tier-evidence" / name, evidence_out / name)
    if args.split_data:
        for candidate in evidence_out.glob('*.json'):
            if candidate.name not in evidence_files:
                assert candidate.resolve().is_relative_to(out.resolve())
                candidate.unlink()

(out / "index.html.tmp").write_text(html, encoding="utf-8")
(out / "index.html.tmp").replace(out / "index.html")
print(str(out / "index.html"), len(html) // 1024, "KB")

if (out.resolve() == (here / "dist").resolve() or args.split_data) and (here.parent / "data/game-perspectives").exists():
    shutil.copytree(here.parent / "data/game-perspectives", out / "game-perspectives", dirs_exist_ok=True)
