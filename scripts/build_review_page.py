"""Build the Vikings/Scots stat review page from the merged checklist.

Input:  data/upcoming-civs/checklist.json, data/upcoming-civs/videos.json, .cache/bili/parts.json (source names)
Output: data/upcoming-civs/review.html — a self-contained page (Artifact page contract: no doctype/html/body tags)
        listing every object with its values, status, sources, dissent and tier values.
Usage:  python -X utf8 scripts/build_review_page.py
"""
import json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]
DIR = ROOT / 'data/upcoming-civs'

def source_names():
    names = {'jeando-datamined': 'Datamined 17.0 records (jeandogaming.com explorer)',
             'installed-catalog-16.3': 'Installed game files 16.3 (Attrib.sga)',
             'aoe4world-buildings': 'aoe4world building data (standard ages)', 'text': 'Official / wiki text'}
    for v in json.loads((DIR / 'videos.json').read_text(encoding='utf-8'))['videos']:
        m = re.search(r'v=([\w-]{11})', v['url'])
        if m: names[m.group(1)] = f"{v['channel']}: {v['title']}"
    parts = ROOT / '.cache/bili/parts.json'
    if parts.exists():
        for p in json.loads(parts.read_text(encoding='utf-8')):
            names[f"{p['bvid']}_p{p['page']}"] = f"{p['owner']} (bilibili): {p['title']}" + (f" P{p['page']}" if p['page'] > 1 else '')
    return names

def slim(chk):
    items = []
    for it in chk['items']:
        fields = []
        for f in it['fields']:
            srcs = [[s.get('videoId'), s.get('timestamp'), s.get('confidence'), (s.get('quote') or '')[:150], s.get('value')] for s in f.get('videoSources') or []]
            row = {'f': f['field'], 'v': f['value'], 's': f['status'], 'src': srcs}
            if f.get('dissent'): row['d'] = [[x.get('value'), x.get('videoId'), x.get('timestamp'), (x.get('note') or '')[:150]] for x in f['dissent']]
            if f.get('candidates'): row['c'] = [[x.get('value'), x.get('videoId'), x.get('timestamp')] for x in f['candidates']]
            if f.get('alternatives'): row['a'] = f['alternatives']
            if f.get('variants'): row['t'] = [[x.get('variant'), x.get('value'), x.get('videoId')] for x in f['variants']][:24]
            if f.get('textValue'): row['tv'] = f['textValue']
            fields.append(row)
        items.append({'civ': it['civ'], 'kind': it['kind'], 'name': it['name'], 'o': it.get('origin', 'text'), 'desc': (it.get('description') or '')[:300], 'fields': fields})
    return items

PAGE = r"""<title>Raiders of the North Stat Sheet</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: one column — summary band, sticky filter bar, then object rows that expand into a per-field evidence table. */
:root{
  --bg:#f3f5f6; --panel:#ffffff; --ink:#18212b; --muted:#5b6876; --line:#d8dee4;
  --accent:#1f5f8b; --vik:#2b5d8f; --sco:#3f6b3a;
  --ok:#2f7d4f; --one:#a86a12; --bad:#b4332b; --none:#8b96a1; --na:#6f7c8a;
  --ok-bg:#e3f2e8; --one-bg:#fbefd9; --bad-bg:#f8e1df; --none-bg:#eceff2; --na-bg:#e9edf1;
  --display:'Archivo', 'Segoe UI', system-ui, sans-serif; --mono:'IBM Plex Mono', ui-monospace, 'Cascadia Mono', Consolas, monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#11161c; --panel:#18202a; --ink:#e4e9ee; --muted:#9aa7b4; --line:#2a3542;
  --accent:#6fb0e0; --vik:#7fb0e2; --sco:#93c08b;
  --ok:#5cc489; --one:#e3a64c; --bad:#ef7b72; --none:#77838f; --na:#8995a1;
  --ok-bg:#16301f; --one-bg:#33270f; --bad-bg:#3a1a18; --none-bg:#1f2731; --na-bg:#1f2731; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#11161c; --panel:#18202a; --ink:#e4e9ee; --muted:#9aa7b4; --line:#2a3542;
  --accent:#6fb0e0; --vik:#7fb0e2; --sco:#93c08b;
  --ok:#5cc489; --one:#e3a64c; --bad:#ef7b72; --none:#77838f; --na:#8995a1;
  --ok-bg:#16301f; --one-bg:#33270f; --bad-bg:#3a1a18; --none-bg:#1f2731; --na-bg:#1f2731; color-scheme:dark}
body{background:var(--bg);color:var(--ink);font-family:var(--display);font-size:14px;line-height:1.45}
.wrap{max-width:1180px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:20px 48px;display:flex;flex-direction:column;gap:18px}
h1{font-size:26px;font-weight:800;letter-spacing:-.01em;margin:0;text-wrap:balance}
.lede{color:var(--muted);max-width:70ch;margin:4px 0 0}
.civs{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
.civ{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:14px;display:flex;flex-direction:column;gap:8px;min-width:0}
.civ h2{margin:0;font-size:16px;font-weight:700;display:flex;justify-content:space-between;gap:8px}
.civ h2 .n{font-family:var(--mono);font-weight:500;color:var(--muted);font-size:12px}
.bar{display:flex;height:10px;border-radius:3px;overflow:hidden;background:var(--none-bg)}
.bar span{display:block;height:100%}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--muted);font-family:var(--mono)}
.legend b{font-weight:500;color:var(--ink)}
.dot{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:5px;vertical-align:baseline}
.st-confirmed{--c:var(--ok);--cb:var(--ok-bg)} .st-single-source{--c:var(--one);--cb:var(--one-bg)} .st-conflict{--c:var(--bad);--cb:var(--bad-bg)}
.st-unknown{--c:var(--none);--cb:var(--none-bg)} .st-na{--c:var(--na);--cb:var(--na-bg)} .st-known-text{--c:var(--one);--cb:var(--one-bg)}
.filters{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--bg);padding-block:10px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;border-bottom:1px solid var(--line)}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:10;background:var(--bg)}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:5px;overflow:hidden;background:var(--panel)}
.seg button{font:inherit;font-size:13px;border:0;background:transparent;color:var(--ink);padding:6px 10px;cursor:pointer}
.seg button+button{border-left:1px solid var(--line)}
.seg button[aria-pressed="true"]{background:var(--accent);color:var(--panel)}
.seg button:focus-visible,input:focus-visible,.obj>button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
input[type=search]{font:inherit;font-size:13px;padding:6px 10px;border:1px solid var(--line);border-radius:5px;background:var(--panel);color:var(--ink);min-width:0;flex:1 1 180px}
label.chk{font-size:13px;color:var(--muted);display:inline-flex;gap:6px;align-items:center}
.count{font-family:var(--mono);font-size:12px;color:var(--muted);margin-left:auto}
.list{display:flex;flex-direction:column;gap:8px}
.obj{background:var(--panel);border:1px solid var(--line);border-radius:6px;min-width:0}
.obj>button{all:unset;box-sizing:border-box;width:100%;cursor:pointer;padding:10px 12px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 12px;align-items:center}
.oname{font-weight:700;font-size:15px;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;min-width:0}
.tag{font-family:var(--mono);font-size:11px;font-weight:500;padding:1px 6px;border-radius:3px;border:1px solid var(--line);color:var(--muted)}
.tag.vikings{color:var(--vik);border-color:var(--vik)} .tag.scots{color:var(--sco);border-color:var(--sco)}
.chips{display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end}
.chip{font-family:var(--mono);font-size:11px;padding:1px 6px;border-radius:3px;background:var(--cb);color:var(--c)}
.kv{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:4px 14px;font-family:var(--mono);font-size:12px;color:var(--muted)}
.kv span b{color:var(--ink);font-weight:500}
.kv span{border-bottom:2px solid var(--c)}
.detail{border-top:1px solid var(--line);padding:10px 12px 14px;display:flex;flex-direction:column;gap:8px}
.desc{color:var(--muted);max-width:90ch}
.tbl{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{text-align:left;vertical-align:top;padding:6px 8px;border-bottom:1px solid var(--line)}
th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600}
td.v{font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
td .src{display:block;color:var(--muted);font-size:11.5px;margin-bottom:3px}
td .src em{font-style:normal;color:var(--ink)}
.stbadge{font-family:var(--mono);font-size:11px;padding:1px 6px;border-radius:3px;background:var(--cb);color:var(--c);white-space:nowrap}
.note{font-size:12px;color:var(--muted)}
.empty{padding:30px;text-align:center;color:var(--muted)}
@media (max-width:560px){.obj>button{grid-template-columns:1fr}.chips{justify-content:flex-start}}
@media (prefers-reduced-motion:no-preference){.obj{transition:border-color .15s}.obj:hover{border-color:var(--accent)}}
</style>
<div class="wrap">
  <header>
    <h1>Raiders of the North stat sheet</h1>
    <p class="lede">Every Vikings and Scots number for Update 17.0, merged from early-access video frames (OCR-indexed and read twice, blind), the datamined 17.0 records, the installed 16.3 game files for standard objects, and verified web sources. Built __BUILT__. Open an object to see each value's sources, disagreements and tier values.</p>
  </header>
  <section class="civs" id="civs" aria-label="Coverage by civilization"></section>
  <div class="filters" role="toolbar" aria-label="Filters">
    <div class="seg" id="fciv"></div>
    <div class="seg" id="fkind"></div>
    <div class="seg" id="fstat"></div>
    <label class="chk"><input type="checkbox" id="funique"> Unique only</label>
    <input type="search" id="q" placeholder="Search names, fields, sources" aria-label="Search">
    <span class="count" id="count"></span>
  </div>
  <section class="list" id="list" aria-live="polite"></section>
</div>
<script>
const DATA = __DATA__;
const SOURCES = __SOURCES__;
const ST_LABEL = {'confirmed':'confirmed','single-source':'one source','conflict':'conflict','unknown':'unknown','n/a':'n/a','known-text':'text only'};
const ORDER = ['confirmed','single-source','known-text','conflict','unknown','n/a'];
const KEY = {unit:['cost.food','cost.wood','cost.gold','cost.stone','trainTimeSeconds','hp','armor.melee','armor.ranged','damage','attackSpeed','range','speed'],
  building:['cost.food','cost.wood','cost.gold','cost.stone','buildTimeSeconds','hp','age'], landmark:['cost.food','cost.gold','buildTimeSeconds','hp','age','region'],
  technology:['cost.food','cost.wood','cost.gold','cost.stone','researchTimeSeconds','age','building'], bonus:['effectValue','interval','cap']};
const SHORT = {'cost.food':'F','cost.wood':'W','cost.gold':'G','cost.stone':'S','trainTimeSeconds':'train','buildTimeSeconds':'build','researchTimeSeconds':'research','armor.melee':'mArm','armor.ranged':'rArm','attackSpeed':'atkSpd','productionTimeSeconds':'every'};
const cls = s => 'st-' + (s === 'n/a' ? 'na' : s);
const esc = v => String(v ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const srcName = id => SOURCES[id] || id || 'unnamed source';
const state = {civ:'all', kind:'all', stat:'all', unique:false, q:'', open:new Set()};
try { const s = JSON.parse(localStorage.getItem('rotn-filters') || '{}'); Object.assign(state, s, {open:new Set()}); } catch (e) {}

function seg(id, opts, key){
  const el = document.getElementById(id); el.innerHTML = '';
  opts.forEach(([v, label]) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = label;
    b.setAttribute('aria-pressed', String(state[key] === v)); b.onclick = () => { state[key] = v; save(); render(); }; el.appendChild(b); });
}
function save(){ try { localStorage.setItem('rotn-filters', JSON.stringify({civ:state.civ, kind:state.kind, stat:state.stat, unique:state.unique})); } catch (e) {} }

function summary(){
  const el = document.getElementById('civs'); el.innerHTML = '';
  ['vikings','scots'].forEach(civ => {
    const counts = {}; let total = 0, objs = 0;
    DATA.filter(i => i.civ === civ).forEach(i => { objs++; i.fields.forEach(f => { counts[f.s] = (counts[f.s] || 0) + 1; total++; }); });
    const bar = ORDER.filter(s => counts[s]).map(s => `<span class="${cls(s)}" style="width:${(100*counts[s]/total).toFixed(2)}%;background:var(--c)" title="${ST_LABEL[s]}: ${counts[s]}"></span>`).join('');
    const legend = ORDER.filter(s => counts[s]).map(s => `<span class="${cls(s)}"><i class="dot" style="background:var(--c)"></i><b>${counts[s]}</b> ${ST_LABEL[s]}</span>`).join('');
    el.insertAdjacentHTML('beforeend', `<div class="civ"><h2><span>${civ === 'vikings' ? 'Vikings' : 'Scots'}</span><span class="n">${objs} objects · ${total} fields</span></h2><div class="bar">${bar}</div><div class="legend">${legend}</div></div>`);
  });
}

function fmt(v){ return v === null || v === undefined ? '—' : (typeof v === 'number' ? (Math.round(v*1000)/1000).toString() : v); }

function detail(i){
  const rows = i.fields.map(f => {
    const srcs = (f.src || []).map(s => `<span class="src"><em>${esc(fmt(s[4]))}</em> · ${esc(srcName(s[0]))}${s[1] ? ' @ ' + esc(s[1]) : ''} · ${esc(s[2] || '')}${s[3] ? ' — “' + esc(s[3]) + '”' : ''}</span>`).join('');
    const extra = [];
    if (f.d) extra.push('<div class="note">Dissent: ' + f.d.map(x => `${esc(fmt(x[0]))} (${esc(srcName(x[1]))}${x[2] ? ' @ ' + esc(x[2]) : ''}${x[3] ? ': ' + esc(x[3]) : ''})`).join('; ') + '</div>');
    if (f.c) extra.push('<div class="note">Candidates: ' + f.c.map(x => `${esc(fmt(x[0]))} (${esc(srcName(x[1]))}${x[2] ? ' @ ' + esc(x[2]) : ''})`).join('; ') + '</div>');
    if (f.a) extra.push('<div class="note">Also: ' + f.a.map(x => esc(fmt(x))).join('; ') + '</div>');
    if (f.tv) extra.push('<div class="note">Wiki wording: ' + esc(f.tv) + '</div>');
    if (f.t) extra.push('<div class="note">Tiers and context: ' + f.t.map(x => `${esc(x[0])} = ${esc(fmt(x[1]))}`).join('; ') + '</div>');
    return `<tr><td>${esc(f.f)}</td><td class="v">${esc(fmt(f.v))}</td><td><span class="stbadge ${cls(f.s)}">${ST_LABEL[f.s] || f.s}</span></td><td>${srcs}${extra.join('')}</td></tr>`;
  }).join('');
  return `<div class="detail">${i.desc ? `<div class="desc">${esc(i.desc)}</div>` : ''}<div class="tbl"><table><thead><tr><th>Field</th><th>Value</th><th>Status</th><th>Sources</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}

function render(){
  seg('fciv', [['all','Both'],['vikings','Vikings'],['scots','Scots']], 'civ');
  seg('fkind', [['all','All'],['unit','Units'],['building','Buildings'],['landmark','Landmarks'],['technology','Techs'],['bonus','Bonuses']], 'kind');
  seg('fstat', [['all','Any status'],['conflict','Conflicts'],['unknown','Unknown'],['single-source','One source'],['confirmed','Confirmed']], 'stat');
  document.getElementById('funique').checked = state.unique;
  const q = state.q.toLowerCase();
  const items = DATA.filter(i => (state.civ === 'all' || i.civ === state.civ) && (state.kind === 'all' || i.kind === state.kind)
    && (!state.unique || i.o !== 'discovered') && (state.stat === 'all' || i.fields.some(f => f.s === state.stat))
    && (!q || i.name.toLowerCase().includes(q) || i.fields.some(f => f.f.toLowerCase().includes(q) || (f.src || []).some(s => srcName(s[0]).toLowerCase().includes(q)))));
  document.getElementById('count').textContent = `${items.length} objects`;
  const list = document.getElementById('list');
  if (!items.length) { list.innerHTML = '<div class="empty">No objects match these filters.</div>'; return; }
  list.innerHTML = items.map((i, n) => {
    const key = i.civ + '|' + i.kind + '|' + i.name; const counts = {};
    i.fields.forEach(f => counts[f.s] = (counts[f.s] || 0) + 1);
    const chips = ORDER.filter(s => counts[s]).map(s => `<span class="chip ${cls(s)}">${counts[s]} ${ST_LABEL[s]}</span>`).join('');
    const kv = (KEY[i.kind] || []).map(k => i.fields.find(f => f.f === k)).filter(Boolean)
      .map(f => `<span class="${cls(f.s)}">${esc(SHORT[f.f] || f.f)} <b>${esc(fmt(f.v))}</b></span>`).join('');
    return `<article class="obj"><button type="button" aria-expanded="${state.open.has(key)}" data-key="${esc(key)}"><div class="oname">${esc(i.name)} <span class="tag ${i.civ}">${i.civ === 'vikings' ? 'Vikings' : 'Scots'}</span><span class="tag">${i.kind}</span>${i.o === 'discovered' ? '<span class="tag">standard / discovered</span>' : ''}</div><div class="chips">${chips}</div><div class="kv">${kv}</div></button>${state.open.has(key) ? detail(i) : ''}</article>`;
  }).join('');
  list.querySelectorAll('.obj>button').forEach(b => b.onclick = () => { const k = b.dataset.key; state.open.has(k) ? state.open.delete(k) : state.open.add(k); render(); });
}
document.getElementById('q').addEventListener('input', e => { state.q = e.target.value; render(); });
document.getElementById('funique').addEventListener('change', e => { state.unique = e.target.checked; save(); render(); });
summary(); render();
</script>
"""

def main():
    chk = json.loads((DIR / 'checklist.json').read_text(encoding='utf-8'))
    items = slim(chk)
    order = {'unit': 0, 'landmark': 1, 'building': 2, 'technology': 3, 'bonus': 4}
    items.sort(key=lambda i: (i['civ'], i['o'] == 'discovered', order.get(i['kind'], 9), i['name']))
    page = PAGE.replace('__DATA__', json.dumps(items, ensure_ascii=False).replace('</', '<\\/')) \
               .replace('__SOURCES__', json.dumps(source_names(), ensure_ascii=False).replace('</', '<\\/')) \
               .replace('__BUILT__', chk.get('builtAt') or '')
    out = DIR / 'review.html'; out.write_text(page, encoding='utf-8')
    print(out, round(len(page.encode('utf-8')) / 2**20, 2), 'MB', len(items), 'objects')

if __name__ == '__main__':
    main()
