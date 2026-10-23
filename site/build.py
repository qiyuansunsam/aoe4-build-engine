"""Inline engine.js into index.template.html -> dist/index.html (single file)."""
import os, pathlib
here = pathlib.Path(__file__).parent
eng = open(here / "engine.js", encoding="utf-8").read()
html = open(here / "index.template.html", encoding="utf-8").read()
html = html.replace("/*__ENGINE__*/", eng.replace("</script", "<\\/script"))
os.makedirs(here / "dist", exist_ok=True)
open(here / "dist" / "index.html", "w", encoding="utf-8").write(html)
print("dist/index.html", len(html) // 1024, "KB")
