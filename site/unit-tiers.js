function tierCalculation(u,category){
  const units=category==='units',f=x=>x.toFixed(6),sum=u.winWeight+u.lossWeight;
  const group=(label,n,weight)=>`<p>${label}: ${n} × ${f(n?weight/n:0)} average share ≈ <b>${f(weight)}</b></p>`;
  return `<details class="unit-tier-evidence"><summary>Calculation</summary><div data-i18n-skip>${units?`${group('Wins',u.wins,u.winWeight)}${group('Losses',u.losses,u.lossWeight)}<p>Weighted win: ${f(u.winWeight)} ÷ (${f(u.winWeight)} + ${f(u.lossWeight)}) = ${(u.winRate*100).toFixed(1)}%</p><p>Average share: ${f(sum)} ÷ ${u.usedIn} = ${(u.averageShareWhenUsed*100).toFixed(1)}%</p><details data-share-games="${esc(u.id)}"><summary>Per-game shares (${u.usedIn})</summary><div class="unit-share-table"></div></details>`:`<p>Win: ${u.wins} ÷ (${u.wins} + ${u.losses}) = ${(u.winRate*100).toFixed(1)}%</p>`}<p>Usage: ${u.usedIn} ÷ ${u.eligiblePlayerGames} = ${(u.usageRate*100).toFixed(1)}%</p></div></details>`;
}
/* Observed win-rate associations. Usage is reported separately from ranking. */
const unitTierState={category:'units',civilization:'__all__',query:''};
const tierModeState={modes:['4']};
const tierRankState={rank:'all'};
function tierRankPicker(){
 const bands=[...(window.UNIT_USAGE_TIERS?.rankBands||window.WINRATES?.bands||[{id:'all',label:'All ranks'}])].sort((a,b)=>a.id==='all'?-1:b.id==='all'?1:0);
 if(!bands.some(b=>b.id===tierRankState.rank))tierRankState.rank=bands[0]?.id||'all';
 return `<label>Pre-match rating<select id="tier-rank">${bands.map(b=>`<option value="${esc(b.id)}" ${b.id===tierRankState.rank?'selected':''}>${esc(b.label)}</option>`).join('')}</select></label>`;
}
function bindTierRank(render){document.querySelector('#tier-rank').addEventListener('change',e=>{tierRankState.rank=e.target.value;render();enhanceSelects();});}
const tierModeOptions=[['1','1v1'],['2','2v2'],['3','3v3'],['4','4v4']];
function tierModePicker(){
 const all=tierModeState.modes.length===4,label=all?'All modes':tierModeOptions.filter(([id])=>tierModeState.modes.includes(id)).map(([,name])=>name).join(' + ');
 return `<div class="tier-mode-field"><span id="tier-mode-label">Game modes</span><details class="tier-mode-picker"><summary aria-labelledby="tier-mode-label tier-mode-value"><span id="tier-mode-value">${label}</span></summary><div class="tier-mode-options" role="group" aria-label="Game modes"><label><input type="checkbox" data-tier-mode="all" ${all?'checked':''}>All modes</label>${tierModeOptions.map(([id,name])=>`<label><input type="checkbox" data-tier-mode="${id}" ${tierModeState.modes.includes(id)?'checked':''}>${name}</label>`).join('')}</div></details></div>`;
}
function tierCloseModes(event){const picker=document.querySelector('.tier-mode-picker');if(picker?.open&&!picker.contains(event.target))picker.open=false;}
function bindTierModes(render){
 document.removeEventListener('pointerdown',tierCloseModes);document.addEventListener('pointerdown',tierCloseModes);
 document.querySelectorAll('[data-tier-mode]').forEach(input=>input.addEventListener('change',()=>{
  const id=input.dataset.tierMode;
  const next=id==='all'?(input.checked?['1','2','3','4']:[tierModeState.modes[0]]):input.checked?[...tierModeState.modes,id]:tierModeState.modes.filter(x=>x!==id);
  if(!next.length){input.checked=true;return;}
  tierModeState.modes=[...new Set(next)].sort();render();enhanceSelects();
  const picker=document.querySelector('.tier-mode-picker');picker.open=true;picker.querySelector(`[data-tier-mode="${id}"]`)?.focus();
 }));
 const picker=document.querySelector('.tier-mode-picker');picker.addEventListener('keydown',e=>{if(e.key==='Escape'){picker.open=false;picker.querySelector('summary').focus();}});
}
function tierCombineCohorts(cohorts,civ,category){
 const byId=new Map(),sum=key=>cohorts.reduce((n,c)=>n+(c[key]||0),0);
 for(const cohort of cohorts)for(const item of cohort.items){
  let combined=byId.get(item.id);
  if(!combined){combined={...item,usedIn:0,wins:0,losses:0,winWeight:0,lossWeight:0,observedEvents:0,matchesUsed:0,calculationGames:[],calculationUrls:[],eligibleCivilizations:[...(item.eligibleCivilizations||[])]};byId.set(item.id,combined);}
  for(const key of ['usedIn','wins','losses','winWeight','lossWeight','observedEvents','matchesUsed'])combined[key]+=item[key]||0;
  combined.eligibleCivilizations=[...new Set([...combined.eligibleCivilizations,...(item.eligibleCivilizations||[])])];
  if(item.calculationGames)combined.calculationGames=combined.calculationGames.concat(item.calculationGames);
  if(item.calculationUrl)combined.calculationUrls.push(item.calculationUrl);
 }
 for(const item of byId.values()){
  item.eligiblePlayerGames=cohorts.reduce((n,cohort)=>{
   const existing=cohort.items.find(r=>r.id===item.id);if(existing)return n+existing.eligiblePlayerGames;
   const counts=item.id.startsWith('generic-tc-')?cohort.tcCountsByCivilization:cohort.countsByCivilization;
   if(!counts)return n; // Legacy data cannot infer a missing item's eligible civilization denominator.
   const civs=civ==='__all__'?item.eligibleCivilizations:[civ];return n+civs.reduce((a,c)=>a+(counts[c]||0),0);
  },0);
  const weight=item.winWeight+item.lossWeight;
  item.winRate=category==='units'?(weight?item.winWeight/weight:0):item.wins/item.usedIn;
  item.averageShareWhenUsed=item.usedIn?weight/item.usedIn:0;
  item.usageRate=item.eligiblePlayerGames?item.usedIn/item.eligiblePlayerGames:0;
  item.tier=item.usedIn<(window.UNIT_USAGE_TIERS.minimumAppearances||30)?'Unrated':item.winRate>=.6?'S':item.winRate>=.55?'A':item.winRate>=.5?'B':item.winRate>=.45?'C':'D';
 }
 return {items:[...byId.values()],games:sum('games'),players:cohorts.length===1?cohorts[0].players:null,unmappedRows:sum('unmappedRows'),playerGamesWithUnmappedRows:sum('playerGamesWithUnmappedRows')};
}
const tierEvidenceCache=new Map();
async function tierEvidence(item){
 const results=await Promise.all((item.calculationUrls||[]).map(url=>{
  if(!tierEvidenceCache.has(url))tierEvidenceCache.set(url,fetch(url).then(response=>{if(!response.ok)throw Error(`Evidence request failed (${response.status})`);return response.json();}).catch(error=>{tierEvidenceCache.delete(url);throw error;}));
  return tierEvidenceCache.get(url);
 }));
 return [...(item.calculationGames||[]),...results.flat()];
}

function tierListTabs(active){
  const tabs=[['civilizations','Civilizations'],['units','Units'],['technologies','Technologies'],['buildings','Buildings & landmarks']];
  return `<nav class="unit-tier-categories" aria-label="Tier list category">${tabs.map(([id,label])=>`<a href="${id==='civilizations'?'#winrates':'#unit-tiers/'+id}" data-tier-category="${id}" ${id===active?'aria-current="page"':''}>${label}</a>`).join('')}</nav>`;
}
function renderUnitTiers(){
  let requested=location.hash.split('/')[1];if(requested==='landmarks')requested='buildings';if(['units','technologies','buildings'].includes(requested)){if(requested!==unitTierState.category)unitTierState.query='';unitTierState.category=requested;}
  const data=window.UNIT_USAGE_TIERS,host=document.querySelector('#page');
  if(!data?.cohorts?.length){host.innerHTML='<h1>Tier lists</h1><p>No usage sample is available.</p>';return;}
  const rankPicker=tierRankPicker();
  const civName=id=>id==='generic'?'Generic':data.civilizations[id]||id;
  const selected=data.cohorts.filter(c=>c.category===unitTierState.category&&(c.rankBand||'all')===tierRankState.rank),civs=[...new Set(['__all__',...selected.map(c=>c.civilization)])].sort((a,b)=>a==='__all__'?-1:b==='__all__'?1:civName(a).localeCompare(civName(b)));
  if(!civs.includes(unitTierState.civilization))unitTierState.civilization=civs[0];
  const cohorts=selected.filter(c=>c.civilization===unitTierState.civilization&&tierModeState.modes.includes(String(c.matchTypeId)));
  const cohort=tierCombineCohorts(cohorts,unitTierState.civilization,unitTierState.category);
  host.innerHTML=`<div class="unit-tier-page"><header class="unit-tier-heading"><div><h1>Tier lists</h1></div><a href="#players">Player profiles →</a></header>${tierListTabs(unitTierState.category)}<div class="unit-tier-filters">${rankPicker}<label>Civilization<select id="unit-tier-civ">${civs.map(c=>`<option value="${esc(c)}" ${c===unitTierState.civilization?'selected':''}>${esc(civName(c))}</option>`).join('')}</select></label>${tierModePicker()}<label class="unit-tier-search">Find an item<input id="unit-tier-query" type="search" placeholder="Search this category" value="${esc(unitTierState.query)}"></label></div><p class="unit-tier-sample" data-i18n-skip>${cohort.games} matches${cohort.players!==null?` · ${cohort.players} players`:""}</p><div id="unit-tier-results" aria-live="polite"></div><details class="unit-tier-method page-panel"><summary>Calculations, tiers and data limits</summary><ul>${data.method.map(s=>`<li>${esc(s)}</li>`).join('')}</ul><p>${cohort.unmappedRows} event rows across ${cohort.playerGamesWithUnmappedRows} player-games could not be matched to the installed catalog and are excluded.</p><p>Source: ${esc(data.source)}. Sample: ${new Date(data.provenance.startTimestamp*1000).toLocaleDateString('en-GB')}–${new Date(data.provenance.endTimestamp*1000).toLocaleDateString('en-GB')}.</p></details></div>`;
  const draw=()=>{
    const query=unitTierState.query.toLocaleLowerCase().trim(),rows=cohort.items.filter(u=>u.name.toLocaleLowerCase().includes(query)).sort((a,b)=>b.winRate-a.winRate||b.usedIn-a.usedIn||a.name.localeCompare(b.name));
    document.querySelector('#unit-tier-results').innerHTML=rows.length?data.bands.filter(b=>rows.some(u=>u.tier===b.id)).map(b=>`<section class="unit-tier-band" aria-label="${esc(b.id+' '+b.label)}"><div class="unit-tier-rank"><strong>${b.id==='Unrated'?'?':b.id}</strong><span>${esc(b.label)}</span>${b.id==='Unrated'?'<small>More evidence needed</small>':''}</div><div class="unit-tier-cards">${rows.filter(u=>u.tier===b.id).map(u=>`<article class="unit-tier-card" data-item-id="${esc(u.id)}"><a class="unit-tier-unit" href="#database/${encodeURIComponent(u.catalogId)}">${gameIcon(u.catalogId)}<span><strong>${esc(u.name)}${u.variantLabel?`<small class="unit-tier-civ-label">${esc(u.variantLabel)}</small>`:''}</strong>${unitTierState.civilization==='__all__'||u.civilization==='generic'?`<small class="unit-tier-civ-label">${esc(civName(u.civilization))}</small>`:''}</span></a><div class="unit-tier-frequency" data-i18n-skip><b>${(u.winRate*100).toFixed(1)}%</b><span>${unitTierState.category==='units'?'weighted win':'win'}</span></div><div class="unit-tier-meter" aria-hidden="true"><span style="width:${u.winRate*100}%"></span></div><p class="unit-tier-outcomes" data-i18n-skip>${u.wins} W · ${u.losses} L</p><p class="unit-tier-usage" data-i18n-skip><strong>${(u.usageRate*100).toFixed(1)}% usage</strong> · ${u.usedIn} / ${u.eligiblePlayerGames} </p>${unitTierState.category==='units'?`<p class="unit-tier-share" data-i18n-skip><strong>${(u.averageShareWhenUsed*100).toFixed(1)}%</strong> avg. share when used</p>`:''}${tierCalculation(u,unitTierState.category)}</article>`).join('')}</div></section>`).join(''):'<div class="page-panel unit-tier-empty">No observed items match this selection.</div>';

  };

  document.querySelector('#unit-tier-civ').addEventListener('change',e=>{unitTierState.civilization=e.target.value;renderUnitTiers();enhanceSelects();});
  bindTierModes(renderUnitTiers);bindTierRank(renderUnitTiers);
  document.querySelector('#unit-tier-results').addEventListener('toggle',async e=>{
    const detail=e.target;if(!detail.matches('details[data-share-games]')||!detail.open||detail.dataset.loaded||detail.dataset.loading)return;
    const item=cohort.items.find(u=>u.id===detail.dataset.shareGames);if(!item)return;
    const host=detail.querySelector('.unit-share-table');detail.dataset.loading='true';host.textContent='Loading…';
    try{
      const games=await tierEvidence(item);
      host.innerHTML=`<table><thead><tr><th>Game / player</th><th>Result</th><th>Unit / military</th><th>Share</th></tr></thead><tbody>${games.map(([game,player,count,total,win])=>`<tr><td>${game}<br>${player}</td><td>${win?'W':'L'}</td><td>${count} / ${total}</td><td>${(count/total).toFixed(6)}</td></tr>`).join('')}</tbody><tfoot><tr><th colspan="3">Winning sum</th><td>${item.winWeight.toFixed(6)}</td></tr><tr><th colspan="3">Losing sum</th><td>${item.lossWeight.toFixed(6)}</td></tr></tfoot></table>`;detail.dataset.loaded='true';
    }catch(error){host.textContent=error.message+' — close and reopen to retry.';}finally{delete detail.dataset.loading;}
  },true);
  document.querySelector('#unit-tier-query').addEventListener('input',e=>{unitTierState.query=e.target.value;draw();});draw();
}
