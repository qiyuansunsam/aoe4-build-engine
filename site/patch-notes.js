/* Patch notes section (#notes, #notes/<civilization id>) and the Library's per-civilization notes panel.
 * Data: data/patch-notes.json (window.PATCH_NOTES), built by scripts/build_patch_notes.py from the official article.
 * Each line is the article's own text split into plain text and references; a reference links to the record's Library
 * page and carries the record's game icon. The civilization filter shows that civilization's own section plus every
 * line elsewhere in the notes that concerns it (item.civs). Note text stays in the language it was published in. */
const PATCH_NOTES=window.PATCH_NOTES&&Array.isArray(window.PATCH_NOTES.sections)?window.PATCH_NOTES:{sections:[],version:''};
const PN_OPEN_KEY='aoe-crafter-civ-notes-open';
let pnQuery='';
// Hotfix sections (titled "Update <build>") read first, newest build on top; the rest keeps the article's order.
function pnSections(){const hot=PATCH_NOTES.sections.filter(s=>/^Update \d/.test(s.title)).sort((a,b)=>b.title.localeCompare(a.title,undefined,{numeric:true}));return [...hot,...PATCH_NOTES.sections.filter(s=>!hot.includes(s))];}
function pnRef(seg){const icon=gameIcon(seg.r);return `<a class="pn-ref" href="#database/${encodeURIComponent(seg.r)}">${icon.startsWith('<img')?icon:''}<span>${esc(seg.n)}</span></a>`;}
// "150 → 165" style changes are set apart so the eye finds the numbers.
function pnText(text){return esc(text).replace(/([+\-−]?\d[\d.,/]*%?(?: ?(?:seconds|second|sec|s))?) → ([+\-−]?\d[\d.,/]*%?)/g,'<b class="pn-change">$1 → $2</b>');}
function pnSegs(segs){return segs.map(s=>typeof s==='string'?pnText(s):pnRef(s)).join('');}
const pnPlain=node=>node.segs.map(s=>typeof s==='string'?s:s.n).join('')+(node.children||[]).map(pnPlain).join(' ');
function pnItem(item){return `<li>${pnSegs(item.segs)}${item.children?.length?`<ul>${item.children.map(pnItem).join('')}</ul>`:''}</li>`;}
// Keep the parts of a group that pass: `own` = the group belongs to the chosen civilization (everything stays).
function pnFilterGroup(group,civ,terms){const own=!civ||group.civ===civ,hit=node=>terms.every(t=>pnPlain(node).toLowerCase().includes(t)),concerns=node=>own||node.civs?.includes(civ)||(node.children||[]).some(concerns),blocks=[];let label=null;
  for(const b of group.blocks){if(b.type==='label'){label=b;continue;}
    if(b.type==='list'){const items=b.items.filter(i=>concerns(i)&&hit(i));if(items.length){if(label)blocks.push(label);label=null;blocks.push({type:'list',items});}}
    else if(own&&(!terms.length||hit(b)))blocks.push(b);}
  return blocks.length?{...group,blocks}:null;}
function pnBlock(b){return b.type==='list'?`<ul class="pn-list">${b.items.map(pnItem).join('')}</ul>`:b.type==='label'?`<h4 class="pn-label">${esc(b.text)}</h4>`:b.type==='note'?`<blockquote class="pn-note">${pnSegs(b.segs)}</blockquote>`:`<p class="pn-para">${pnSegs(b.segs)}</p>`;}
const pnLines=items=>(items||[]).reduce((n,i)=>n+1+pnLines(i.children),0),pnCount=blocks=>blocks.reduce((n,b)=>n+pnLines(b.items),0);
function pnGroupHtml(group,civHeading){const title=group.civ?`<h3 class="pn-civ-title">${civFlag(group.civ)}<a href="#notes/${esc(group.civ)}">${esc(civName(group.civ))}</a></h3>`:group.title?`<h3 data-i18n-skip>${esc(group.title)}</h3>`:'';
  return `<div class="pn-group${group.civ?' pn-civ-group':''}">${civHeading===false?'':title}<div class="pn-body" data-i18n-skip>${group.blocks.map(pnBlock).join('')}</div></div>`;}
function pnDate(iso){if(!iso)return '';const [y,m,d]=iso.split('-').map(Number);return `${d} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1]} ${y}`;}
function pnCivs(){const ids=new Set();for(const s of PATCH_NOTES.sections)for(const g of s.groups){if(g.civ)ids.add(g.civ);const walk=n=>{(n.civs||[]).forEach(c=>ids.add(c));(n.children||[]).forEach(walk);};g.blocks.forEach(b=>(b.items||[]).forEach(walk));}return [...ids].filter(id=>GAME_CATALOG.civilizations.some(c=>c.id===id));}
function renderPatchNotes(){const parts=location.hash.replace(/^#notes\/?/,'').split('/').map(decodeURIComponent).filter(Boolean),civs=pnCivs(),civ=civs.includes(parts[0])?parts[0]:'';
  if(!PATCH_NOTES.sections.length){$('#page').innerHTML=pageTop('Patch notes','')+'<section class="page-panel"><p class="meta">No patch notes in this build.</p></section>';return;}
  const terms=pnQuery.toLowerCase().trim().split(/\s+/).filter(Boolean),sections=pnSections().map(s=>({...s,groups:s.groups.map(g=>pnFilterGroup(g,civ,terms)).filter(Boolean)})).filter(s=>s.groups.length);
  if(civ)sections.sort((a,b)=>b.groups.some(g=>g.civ===civ)-a.groups.some(g=>g.civ===civ));
  const lines=sections.reduce((n,s)=>n+s.groups.reduce((m,g)=>m+pnCount(g.blocks),0),0),meta=[`Build ${PATCH_NOTES.version}`,PATCH_NOTES.released?`released ${pnDate(PATCH_NOTES.released)}`:'',PATCH_NOTES.hotfix?`hotfix ${pnDate(PATCH_NOTES.hotfix)}`:''].filter(Boolean);
  $('#page').innerHTML=pageTop('Patch notes','')+`<div class="pn-head"><div><h2>${esc(PATCH_NOTES.title||'Patch notes')}</h2><span class="meta">${meta.map(esc).join(' · ')}</span></div><a class="pn-source" href="${esc(PATCH_NOTES.sourceUrl)}" target="_blank" rel="noopener">Official notes ↗</a></div><div class="page-filter library-filter pn-filter"><label>Search<input id="pn-search" type="search" placeholder="Unit, building, technology or text" value="${esc(pnQuery)}"></label><label>Civilization<select id="pn-civ"><option value="">All civilizations</option>${civOptions(civs).replace(`value="${esc(civ)}"`,`value="${esc(civ)}" selected`)}</select></label></div><nav class="pn-nav" aria-label="Sections">${sections.map(s=>`<button type="button" data-i18n-skip data-pn-jump="${esc(s.id)}">${esc(s.title)}</button>`).join('')}<span class="pn-count">${lines} lines</span></nav><div id="pn-content">${sections.map(s=>`<section class="page-panel pn-section" id="pn-${esc(s.id)}"><div class="panel-head"><h2 data-i18n-skip>${esc(s.title)}</h2></div><div class="${s.groups.filter(g=>g.civ).length>2?'pn-columns':'pn-stack'}">${s.groups.map(g=>pnGroupHtml(g)).join('')}</div></section>`).join('')||'<section class="page-panel"><p class="meta">No lines match.</p></section>'}</div>`;
  $('#pn-search').oninput=e=>{pnQuery=e.target.value;const at=e.target.selectionStart;renderPatchNotes();enhanceSelects();const box=$('#pn-search');box.focus();box.setSelectionRange(at,at);};
  $('#pn-civ').onchange=e=>{location.hash='notes'+(e.target.value?'/'+encodeURIComponent(e.target.value):'');};
  $$('[data-pn-jump]').forEach(b=>b.onclick=()=>document.getElementById('pn-'+b.dataset.pnJump)?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'}));
}
// Library: the chosen civilization's notes above its roster (own section first, then lines elsewhere that concern it).
function pnRemember(open){try{localStorage.setItem(PN_OPEN_KEY,open?'1':'0');}catch{}}
function civPatchNotesPanel(civ){if(!PATCH_NOTES.sections.length)return '';
  const sections=pnSections().map(s=>({...s,groups:s.groups.map(g=>pnFilterGroup(g,civ,[])).filter(Boolean)})).filter(s=>s.groups.length);if(!sections.length)return '';
  const own=sections.flatMap(s=>s.groups.filter(g=>g.civ===civ)),other=sections.map(s=>({...s,groups:s.groups.filter(g=>g.civ!==civ)})).filter(s=>s.groups.length),lines=sections.reduce((n,s)=>n+s.groups.reduce((m,g)=>m+pnCount(g.blocks),0),0);
  let open=true;try{open=localStorage.getItem(PN_OPEN_KEY)!=='0';}catch{}
  return `<details class="page-panel pn-civ-panel" ${open?'open':''} ontoggle="pnRemember(this.open)"><summary><span class="pn-civ-summary">${civFlag(civ)}<b>${esc(PATCH_NOTES.title||'Patch notes')} notes</b><span class="meta">${lines} lines</span></span><a class="pn-source" href="#notes/${esc(civ)}">All patch notes</a></summary>${own.map(g=>pnGroupHtml(g,false)).join('')}${other.map(s=>`<div class="pn-elsewhere"><h3 data-i18n-skip>${esc(s.title)}</h3>${s.groups.map(g=>`<div class="pn-body" data-i18n-skip>${g.blocks.map(pnBlock).join('')}</div>`).join('')}</div>`).join('')}</details>`;}
