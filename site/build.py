"""Inline engine.js into index.template.html -> dist/index.html (single file).

Usage: python -X utf8 site/build.py [--out DIR] [--extra-css FILE ...] [--extra-js FILE ...]
--out writes the page to another directory (used for isolated UI variants); it does not copy
game-perspectives there. --extra-css/--extra-js append experiment files after the shared sources.
--split-data writes each data payload to OUT/data/<name>.js (loaded by script tags in <head>) instead of
inlining it, and copies game-perspectives into OUT; Cloudflare static assets cap a file at 25 MiB
(deploy/README.md).
"""
import os, pathlib, json, shutil, argparse
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
eng = open(here / "engine.js", encoding="utf-8").read()
html = open(here / "index.template.html", encoding="utf-8").read()
for marker, filename in [("/*__CRAFTER_CSS__*/", "crafter.css"), ("/*__CRAFTER_JS__*/", "crafter.js"), ("/*__CONTEXT_CSS__*/", "context-actions.css"), ("/*__CATALOG_CSS__*/", "catalog.css"), ("/*__GAMES_CSS__*/", "games.css"), ("/*__CONTEXT_JS__*/", "context-actions.js")]:
    content = (here / filename).read_text(encoding="utf-8")
    if filename == "crafter.js":
        content = (here / "observed-army.js").read_text(encoding="utf-8") + "\n" + (here / "observed-derived.js").read_text(encoding="utf-8") + "\n" + content
    if filename == "crafter.css":
        content += "\n" + (here / "build-timeline.css").read_text(encoding="utf-8")
    if filename == "games.css":
        for extra in args.extra_css:
            content += "\n/* extra: " + extra + " */\n" + pathlib.Path(extra).read_text(encoding="utf-8")
    if filename == "context-actions.js":
        for extra in args.extra_js:
            content += "\n/* extra: " + extra + " */\n" + pathlib.Path(extra).read_text(encoding="utf-8")
    html = html.replace(marker, content.replace("</script", "<\\/script"))
html = html.replace("/*__ENGINE__*/", eng.replace("</script", "<\\/script"))
out.mkdir(parents=True, exist_ok=True)
data_scripts = []
for marker, filename in [("/*__BUILD_LIBRARY__*/", "build-library.json"), ("/*__GAME_CATALOG__*/", "game-catalog.json"), ("/*__PATCH_AUDIT__*/", "patch-audit.json"), ("/*__GAME_LIBRARY__*/", "game-library.json"), ("/*__GAME_ICONS__*/", "game-icons.json"), ("/*__CIV_FLAGS__*/", "civilization-flags.json"), ("/*__CATALOG_META__*/", "catalog-enrichment.json"), ("/*__PATCH_NEXT__*/", "patch-next.json"), ("/*__PREVIEW_CATALOG__*/", "catalog-preview-17.0.json"), ("/*__CATALOG_AGES__*/", "catalog-ages.json")]:
    if marker in html:
        source = here.parent / "data" / filename
        if not source.exists():
            raise FileNotFoundError(f"Required UI data missing: {source}")
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        if args.split_data:
            key = json.dumps(filename)
            (out / "data").mkdir(parents=True, exist_ok=True)
            (out / "data" / (filename.rsplit(".", 1)[0] + ".js")).write_text("(window.__AOE_DATA=window.__AOE_DATA||{})[" + key + "]=" + text + ";\n", encoding="utf-8")
            data_scripts.append('<script src="data/' + filename.rsplit(".", 1)[0] + '.js"></script>')
            html = html.replace(marker, "window.__AOE_DATA[" + key + "]")
        else:
            html = html.replace(marker, text)
if data_scripts:
    html = html.replace("</head>", "".join(data_scripts) + "</head>", 1)
os.makedirs(out, exist_ok=True)
open(out / "index.html", "w", encoding="utf-8").write(html)
print(str(out / "index.html"), len(html) // 1024, "KB")

if (out.resolve() == (here / "dist").resolve() or args.split_data) and (here.parent / "data/game-perspectives").exists():
    shutil.copytree(here.parent / "data/game-perspectives", out / "game-perspectives", dirs_exist_ok=True)
