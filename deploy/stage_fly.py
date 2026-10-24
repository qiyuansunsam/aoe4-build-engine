"""Stage the Fly API image context in deploy/fly/build.

Copies the server (no tests), the game library and every match summary the library can serve.
Summaries the library references by absolute local path (mcaoe) are copied to
data/downloaded-summaries/<gameId>.json, which the server checks first.
Usage: python -X utf8 deploy/stage_fly.py
"""
import json, pathlib, shutil

root = pathlib.Path(__file__).resolve().parents[1]
out = root / "deploy/fly/build"
if out.exists():
    shutil.rmtree(out)
(out / "server").mkdir(parents=True)
(out / "data/downloaded-summaries").mkdir(parents=True)
for f in (root / "server").glob("*.py"):
    if not f.name.startswith("test_"):
        shutil.copy2(f, out / "server" / f.name)
for name in ("Dockerfile", "fly.toml"):
    shutil.copy2(root / "deploy/fly" / name, out / name)
shutil.copy2(root / "data/game-library.json", out / "data/game-library.json")
for f in (root / "data/downloaded-summaries").glob("*.json"):
    shutil.copy2(f, out / "data/downloaded-summaries" / f.name)
library = json.loads((root / "data/game-library.json").read_text(encoding="utf-8-sig"))
copied = missing = 0
for game in library.get("games", []):
    source = game.get("source") or {}
    local = source.get("localFile") if isinstance(source, dict) else None
    target = out / "data/downloaded-summaries" / f"{game.get('gameId')}.json"
    if not isinstance(local, str) or target.exists():
        continue
    if pathlib.Path(local).is_file():
        shutil.copy2(local, target); copied += 1
    else:
        missing += 1
size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
print(f"staged {out} · {copied} referenced summaries copied, {missing} missing · {size / 1e6:.1f} MB")
