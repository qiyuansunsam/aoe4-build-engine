/* What changed in the installed patch, read from the game files (data/patch-changes.json, window.PATCH_CHANGES, built
 * by scripts/build_patch_changes.py as the difference between the previous installed catalog and the current one).
 * Two places use it: a brief overview on top of the Library (all civilizations, or the chosen one) and a "Changed in"
 * block on a record's page. Records that did not change show nothing; the stats on the page are the installed values. */
const PATCH_CHANGES=window.PATCH_CHANGES&&window.PATCH_CHANGES.records?window.PATCH_CHANGES:{records:{},added:[],families:[],shared:[],newByCiv:{},from:{},to:{}};
const PC_BRIEF=6;                      // rows shown before "Show all"
let pcExpanded=false;
const pcAdded=new Set(PATCH_CHANGES.added||[]);
const pcVersion=()=>String(PATCH_CHANGES.to?.patch||'').split('.').slice(0,2).join('.');
// Labels built from a weapon name, a target class or an engine property come straight from the files and are not translated.
const pcRawLabel=label=>/ (?:damage|range|bonus vs .+|wind-up \(s\)|wind-down \(s\)|cooldown \(s\))$|^Effect · /.test(label);
function pcValue(c){if(c.o==null)return `<b>${esc(c.n)}</b>`;if(c.n==null)return `<s>${esc(c.o)}</s>`;return `${esc(c.o)} → <b>${esc(c.n)}</b>`;}
function pcChip(c){if(c.t)return `<span class="pc-chip pc-text" title="${esc((c.o||'')+' → '+(c.n||''))}"><i>Tooltip</i><span data-i18n-skip>${esc(c.n||c.o||'')}</span></span>`;
  return `<span class="pc-chip"><i${pcRawLabel(c.l)?' data-i18n-skip':''}>${esc(c.l)}</i><span class="pc-value" data-i18n-skip>${pcValue(c)}</span></span>`;}
function pcRow(f,note=''){const icon=gameIcon(f.id);return `<a class="pc-row" href="#database/${encodeURIComponent(f.id)}">${icon}<span class="pc-name"><b>${esc(f.name)}</b>${note}</span><span class="pc-chips">${f.changes.map(pcChip).join('')}</span></a>`;}
function pcNewLine(civ){const n=PATCH_CHANGES.newByCiv?.[civ];if(!n)return '';const parts=[['units','units'],['buildings','buildings'],['technologies','technologies']].filter(([k])=>n[k]).map(([k,label])=>`${n[k]} ${label}`);return parts.length?`<p class="pc-new"><span class="badge a">New in ${esc(pcVersion())}</span> <span>${esc(parts.join(', '))}</span></p>`:'';}
// Library top: brief overview. No civilization chosen: changes every civilization shares, then a count per civilization.
function libChangesPanel(civ){if(!PATCH_CHANGES.families.length&&!pcAdded.size)return '';
  const from=PATCH_CHANGES.from?.patch,to=PATCH_CHANGES.to?.patch,head=`<div class="panel-head pc-head"><div><h2>Changes in ${esc(pcVersion())}</h2><span class="meta">Installed files · ${esc(from)} → ${esc(to)}</span></div><a class="pn-source" href="#notes${civ?'/'+esc(civ):''}">Patch notes</a></div>`;
  if(civ){const rows=PATCH_CHANGES.families.filter(f=>f.civ===civ),shown=pcExpanded?rows:rows.slice(0,PC_BRIEF);
    return `<section class="page-panel pc-panel" id="lib-changes">${head}${pcNewLine(civ)}${rows.length?`<div class="pc-rows">${shown.map(f=>pcRow(f)).join('')}</div>${rows.length>PC_BRIEF?`<button type="button" class="quiet pc-more" data-pc-more aria-expanded="${pcExpanded}">${pcExpanded?'Show fewer':`Show all ${rows.length}`}</button>`:''}`:PATCH_CHANGES.newByCiv?.[civ]?'':'<p class="meta">No record of this civilization changed.</p>'}</section>`;}
  const counts={};for(const f of PATCH_CHANGES.families)if(GAME_CATALOG.civilizations.some(c=>c.id===f.civ))counts[f.civ]=(counts[f.civ]||0)+1;
  for(const id of Object.keys(PATCH_CHANGES.newByCiv||{}))counts[id]=counts[id]||0;
  const civs=Object.keys(counts).sort((a,b)=>counts[b]-counts[a]||civName(a).localeCompare(civName(b)));
  return `<section class="page-panel pc-panel" id="lib-changes">${head}<div class="pc-rows">${(PATCH_CHANGES.shared||[]).map(s=>pcRow(s,`<small>${s.civs.length} civilizations</small>`)).join('')}</div><div class="pc-civs">${civs.map(id=>{const n=PATCH_CHANGES.newByCiv?.[id],isNew=n&&(n.units||n.buildings);return `<button type="button" class="pc-civ" data-pc-civ="${esc(id)}">${civFlag(id)}<span>${esc(civName(id))}</span>${isNew?`<small class="badge a">New</small>`:`<small data-i18n-skip>${counts[id]}</small>`}</button>`;}).join('')}</div></section>`;}
function bindLibChanges(){$$('[data-pc-civ]').forEach(b=>b.onclick=()=>{dbCiv=b.dataset.pcCiv;catalogBuilding='';dbLimit=80;pcExpanded=false;if(dbKind==='civilizations')dbKind='units';renderDatabase();enhanceSelects();});
  const more=$('[data-pc-more]');if(more)more.onclick=()=>{pcExpanded=!pcExpanded;const y=scrollY;renderDatabase();enhanceSelects();scrollTo(0,y);$('[data-pc-more]')?.focus({preventScroll:true});};}
// Record page: only records that changed or are new get a block.
function recordChangesMarkup(r){const changes=PATCH_CHANGES.records?.[r.id],from=PATCH_CHANGES.from?.patch,to=PATCH_CHANGES.to?.patch;
  if(pcAdded.has(r.id))return `<section class="catalog-section pc-record"><h3>New in ${esc(pcVersion())}</h3><p class="quiet-note">Not in the ${esc(from)} files.</p></section>`;
  if(!changes?.length)return '';
  return `<section class="catalog-section pc-record"><h3>Changed in ${esc(pcVersion())}</h3><div class="pc-record-rows">${changes.map(c=>c.t?`<div class="pc-record-row pc-record-text"><span>Tooltip</span><span data-i18n-skip>${c.o?`<s>${esc(c.o)}</s>`:''}${c.n?`<b>${esc(c.n)}</b>`:''}</span></div>`:`<div class="pc-record-row"><span${pcRawLabel(c.l)?' data-i18n-skip':''}>${esc(c.l)}</span><span class="pc-value" data-i18n-skip>${pcValue(c)}</span></div>`).join('')}</div><p class="quiet-note">Installed files · ${esc(from)} → ${esc(to)}</p></section>`;}
