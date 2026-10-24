"""Build site/uplift/gallery.html: side-by-side screenshots of every UI uplift variant (a vs b) per area/theme/page."""
import base64, json, pathlib, re, collections
here = pathlib.Path(__file__).parent
shots = here / 'shots-small'  # JPEG copies made by: ffmpeg -i shots/X.png -vf scale=1200:-1 -q:v 6 shots-small/X.jpg
pat = re.compile(r'^(?P<area>chart|shell|rail)-(?P<variant>[ab])-(?P<theme>dark|light)-(?P<page>.+)\.jpg$')
groups = collections.defaultdict(dict)
for f in sorted(shots.glob('*.jpg')):
    m = pat.match(f.name)
    if not m: continue
    groups[(m['area'], m['theme'], m['page'])][m['variant']] = f
notes = json.loads((here / 'gallery-notes.json').read_text(encoding='utf-8')) if (here / 'gallery-notes.json').exists() else {}
def img(f):
    return '<img loading="lazy" alt="%s" src="data:image/jpeg;base64,%s">' % (f.name, base64.b64encode(f.read_bytes()).decode()) if f else '<div class="missing">no screenshot</div>'
order = {'chart': 0, 'shell': 1, 'rail': 2}
rows = []
for (area, theme, page), v in sorted(groups.items(), key=lambda kv: (order[kv[0][0]], kv[0][2], kv[0][1])):
    rows.append(f'<section class="pair" data-area="{area}" data-theme="{theme}"><h3>{area} · {page} · {theme}</h3><div class="two"><figure><figcaption>Variant A · restrained</figcaption>{img(v.get("a"))}</figure><figure><figcaption>Variant B · expressive</figcaption>{img(v.get("b"))}</figure></div></section>')
areas = ''.join(f'<section class="area"><h2>{a.title()}</h2><p>{notes.get(a, "")}</p></section>' for a in ('chart', 'shell', 'rail'))
html = f'''<title>AoE4 UI Uplift Gallery</title><meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Fraunces:opsz,wght@9..144,500&display=swap">
<style>/* layout: one column of A|B pairs, filter chips on top */
:root{{--bg:#eef1f5;--fg:#1c2330;--muted:#5d6878;--card:#ffffff;--line:#d9dfe7;--a:#1f63a8;--b:#a85a24;--display:'Fraunces',Georgia,serif;--sans:'IBM Plex Sans',Segoe UI,system-ui,sans-serif}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#16181c;--fg:#e4e7eb;--muted:#9ea6b1;--card:#1e2126;--line:#2e333b;--a:#7fb6ec;--b:#edb07a;color-scheme:dark}}}}
:root[data-theme=dark]{{--bg:#16181c;--fg:#e4e7eb;--muted:#9ea6b1;--card:#1e2126;--line:#2e333b;--a:#7fb6ec;--b:#edb07a;color-scheme:dark}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 var(--sans)}}main{{max-width:1680px;margin:0 auto;padding-block:24px 64px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}}
h1{{font:500 32px/1.15 var(--display);margin:0 0 6px;text-wrap:balance}}h2{{font:500 22px/1.2 var(--display);margin:28px 0 4px}}h3{{font-size:13px;color:var(--muted);margin:28px 0 8px;font-weight:600;letter-spacing:.02em;text-transform:uppercase}}p{{color:var(--muted);margin:0 0 8px;max-width:72ch}}
.filters{{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 8px}}.filters button{{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:999px;padding:6px 14px;cursor:pointer;font:inherit}}.filters button[aria-pressed=true]{{border-color:var(--a);color:var(--a)}}.filters button:focus-visible{{outline:2px solid var(--a);outline-offset:2px}}
.two{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}@media(max-width:900px){{.two{{grid-template-columns:minmax(0,1fr)}}}}
figure{{margin:0;min-width:0;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}}figcaption{{padding:8px 12px;font-size:13px;color:var(--muted);border-bottom:1px solid var(--line)}}
figure:first-child figcaption{{color:var(--a)}}figure:last-child figcaption{{color:var(--b)}}img{{display:block;width:100%;max-width:100%;height:auto}}.missing{{padding:48px;text-align:center;color:var(--muted)}}
.pair[hidden]{{display:none}}.ship{{display:inline-block;font-size:12px;border:1px solid var(--line);border-radius:999px;padding:2px 10px;margin-left:8px;color:var(--muted)}}</style><main>
<h1>Mathmatically Correct AoE 4 路 UI uplift variants</h1><p>Each row shows the same page in two looks produced from one brief: A keeps the glass restrained, B turns up tint and motion. Layout and features are unchanged in both. Motion is only visible in the app itself (http://127.0.0.1:8765); these are stills at 1440 px. The build currently ships chart A, shell B and rail B; switch any area in <code>site/uplift/active.json</code> and rebuild.</p>
<div class="filters" role="group" aria-label="Filter"><button data-filter="all" aria-pressed="true">All</button><button data-filter="chart">Chart</button><button data-filter="shell">Shell</button><button data-filter="rail">Rail</button><button data-filter="dark">Dark</button><button data-filter="light">Light</button></div>
{areas}{''.join(rows)}
<script>document.querySelectorAll('.filters button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.filters button').forEach(x=>x.setAttribute('aria-pressed',x===b));const f=b.dataset.filter;document.querySelectorAll('.pair').forEach(p=>p.hidden=!(f==='all'||p.dataset.area===f||p.dataset.theme===f));}});</script>
</main>'''
(here / 'gallery.html').write_text(html, encoding='utf-8')
print('gallery.html', len(html) // 1024, 'KB', len(rows), 'pairs')
