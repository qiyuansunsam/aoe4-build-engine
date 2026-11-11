'use strict';
const WC_TYPES={units:'Units',technologies:'Technologies',landmarks:'Landmarks'};
const WC_ITEM_LABELS={units:'Unit',technologies:'Technology',landmarks:'Landmark'};
const WC_MODES=[['','All ranked modes'],['rm_1v1','Solo'],['team','Team'],['rm_2v2','2v2'],['rm_3v3','3v3'],['rm_4v4','4v4']];
const WC_RATINGS=[['','All collected ratings'],['under1000','Below 1000'],['1000-1399','1000 to 1399'],['1400plus','1400 and above'],['unknown','Rating unavailable']];
let wcState={mode:'',rating:'',search:'',sort:'difference'};
try{Object.assign(wcState,JSON.parse(localStorage.getItem('aoe-crafter-winrate-items-v1')||'{}'));}catch{}
function wcData(){return window.TIERLISTS?.schemaVersion===2?window.TIERLISTS:{groups:[],items:{},civilizations:[],coverage:{},patch:{}};}
function wcAggregate(data,type,filters){
  const groups=(data.groups||[]).filter(group=>(!filters.mode||(filters.mode==='team'?['rm_2v2','rm_3v3','rm_4v4'].includes(group.mode):group.mode===filters.mode))&&(!filters.civ||group.civ===filters.civ)&&(!filters.rating||group.ratingBand===filters.rating));
  const items=(data.items?.[type]||[]).filter(item=>(!filters.civ||!item.civs?.length||item.civs.includes(filters.civ))&&(!filters.search||`${item.name} ${item.id}`.toLowerCase().includes(filters.search.toLowerCase())));
  const rows=items.map(item=>{
    const eligible=groups.filter(group=>!item.civs?.length||item.civs.includes(group.civ));
    const row={item,games:0,wins:0,uses:0,usedWins:0,shareSum:0,winShareSum:0,lossShareSum:0,bands:Array.from({length:5},()=>({games:0,wins:0,shareSum:0}))};
    for(const group of eligible){
      const category=group[type]||{},entry=category.items?.[item.id]||{};
      row.games+=category.games||0;row.wins+=category.wins||0;row.uses+=entry.uses||0;row.usedWins+=entry.wins||0;
      for(const key of ['shareSum','winShareSum','lossShareSum'])row[key]+=entry[key]||0;
      (entry.bands||[]).forEach((band,index)=>{if(index<5)for(const key of ['games','wins','shareSum'])row.bands[index][key]+=band[key]||0;});
    }
    row.losses=row.games-row.wins;row.rate=row.uses?row.usedWins/row.uses:null;row.usage=row.games?row.uses/row.games:null;
    row.share=row.games?row.shareSum/row.games:null;row.winShare=row.wins?row.winShareSum/row.wins:null;row.lossShare=row.losses?row.lossShareSum/row.losses:null;
    row.difference=row.winShare!==null&&row.lossShare!==null?row.winShare-row.lossShare:null;
    row.interval=wrInterval(row.usedWins,row.uses);
    return row;
  }).filter(row=>row.uses>0);
  const sort=filters.sort||'rate',value=row=>sort==='difference'?row.difference:sort==='share'?row.share:sort==='usage'?row.usage:sort==='games'?row.uses:row.rate;
  const compare=(a,b)=>(value(b)??-Infinity)-(value(a)??-Infinity)||b.uses-a.uses||a.item.name.localeCompare(b.item.name);
  const ranked=rows.filter(row=>row.uses>=WR_MIN_GAMES).sort(compare),thin=rows.filter(row=>row.uses<WR_MIN_GAMES).sort((a,b)=>b.uses-a.uses||compare(a,b));
  return {ranked,thin,games:groups.reduce((sum,g)=>sum+(g[type]?.games||0),0),allGames:groups.reduce((sum,g)=>sum+(g.games||0),0),groups};
}
function wcPercent(value){return value===null?'–':wrPercent(value);}
function wcDifference(value){return value===null?'–':`${value>0?'+':''}${(value*100).toFixed(1)}`;}
function wcItemIcon(item){return gameIcon(item.catalogId||item.name);}
function wcProductionBar(row){
  const line=(label,value,kind)=>`<span class="wc-share-line ${kind}"><span class="sr-only">${label}</span><span class="wc-share-track"><i style="width:${value===null?0:Math.min(100,value*100).toFixed(3)}%"></i></span><strong>${wcPercent(value)}</strong></span>`;
  return `<span class="wc-share-pair">${line('Winning games',row.winShare,'wc-win')}${line('Losing games',row.lossShare,'wc-loss')}</span>`;
}
function wcDetailHtml(row,type){
  const names=(row.item.civs||[]).map(id=>civName(id)),summary=names.length?names.map(esc).join(', '):'All civilizations';
  const shareRows=row.bands.map((band,index)=>`<tr><th scope="row" data-i18n-skip>${index*20}${index===0?'':'+'}–${(index+1)*20}%</th><td>${band.games?wrPercent(band.wins/band.games):'–'}</td><td>${wrNumber(band.wins)} / ${wrNumber(band.games)}</td></tr>`).join('');
  return `<div class="wc-detail-copy"><p><strong>${esc(row.item.name)}</strong><span>${summary}</span></p>${type==='units'?`<p>Shares average across all eligible player-games, including zero when this unit was not ordered. The winning and losing groups are averaged separately.</p><table class="wc-band-table"><caption>Composition bands</caption><thead><tr><th scope="col">Production share</th><th scope="col">Win rate</th><th scope="col">Wins / player-games</th></tr></thead><tbody>${shareRows}</tbody></table>`:''}<p><span>Win rate when ordered</span>: ${wcPercent(row.rate)} · <span>95% descriptive interval</span>: ${wrPercent(row.interval[0])}–${wrPercent(row.interval[1])}</p><p>Commands record intent, not completion. These associations do not measure the effect of choosing this item.</p></div>`;
}
function wcRowHtml(row,index,type,thin){
  const identity=`<button type="button" class="wc-item" data-wc-detail="${esc(row.item.id)}" aria-expanded="false">${wcItemIcon(row.item)}<span>${esc(row.item.name)}</span><span class="wc-expand" aria-hidden="true">+</span></button>`;
  const cells=type==='units'?`<td class="wc-share-cell">${wcProductionBar(row)}</td><td class="wc-number wc-difference ${row.difference>0?'positive':row.difference<0?'negative':''}">${wcDifference(row.difference)}</td><td class="wc-number">${wcPercent(row.share)}</td>`:`<td class="wr-barcell">${wrBar({...row,rate:row.rate??0},.25)}</td>`;
  return `<tr data-wc-row="${esc(row.item.id)}" class="${thin?'wr-thin':''}"><td class="wr-rank">${thin?'':index+1}</td><th scope="row" class="wc-name">${identity}</th>${cells}<td class="wc-number">${wcPercent(row.usage)}</td><td class="wc-number wc-winrate">${wcPercent(row.rate)}</td><td class="wc-number wc-sample">${wrNumber(row.usedWins)} / ${wrNumber(row.uses)}<small>${wrNumber(row.games)} <span>eligible</span></small></td></tr><tr class="wc-detail" data-wc-detail-row="${esc(row.item.id)}" hidden><td colspan="${type==='units'?8:6}">${wcDetailHtml(row,type)}</td></tr>`;
}
function renderWinrateChoices(type){
  const data=wcData(),civs=data.civilizations||[],category=WC_TYPES[type]||WC_TYPES.units;
  if(wrState.civ&&!civs.some(c=>c.id===wrState.civ))wrState.civ='';
  if(type!=='units'&&['difference','share'].includes(wcState.sort))wcState.sort='rate';
  const filters={...wcState,civ:wrState.civ},result=wcAggregate(data,type,filters),patch=data.patch||{},coverage=data.coverage||{};
  const options=(values,selected)=>values.map(([id,label])=>`<option value="${esc(id)}" ${id===selected?'selected':''}>${esc(label)}</option>`).join('');
  const sorted=(key,label,cls='wc-number')=>`<th scope="col" class="${cls}"><button class="wr-sort" type="button" data-wc-sort="${key}" aria-pressed="${wcState.sort===key}">${label}</button></th>`;
  const headings=type==='units'?`<th scope="col" class="wc-share-cell">Production share<span class="wc-share-legend"><span class="wc-win">Winning games</span><span class="wc-loss">Losing games</span></span></th>${sorted('difference','Difference')} ${sorted('share','Overall share')}`:'<th scope="col" class="wr-barcell"><span class="wr-axis"><span>25%</span><span>50%</span><span>75%</span></span></th>';
  const rows=result.ranked.map((row,index)=>wcRowHtml(row,index,type,false)).join('')+(result.thin.length?`<tr class="wr-divider"><td colspan="${type==='units'?8:6}">Under ${WR_MIN_GAMES} games</td></tr>${result.thin.map((row,index)=>wcRowHtml(row,index,type,true)).join('')}`:'');
  const empty=!data.groups.length?'No replay analysis in this build.':!result.games?'No usable replay data matches these filters.':'No matching items were ordered in this sample.';
  $('#page').innerHTML=pageTop('Win rates','')+wrCategoryTabs()+`<div class="page-filter library-filter wr-filter wc-filter"><label>Mode<select id="wc-mode">${options(WC_MODES,wcState.mode)}</select></label><label>Civilization<select id="wc-civ">${options([['','All civilizations'],...civs.map(c=>[c.id,c.name])],wrState.civ)}</select></label><label>Rating band<select id="wc-rating">${options(WC_RATINGS,wcState.rating)}</select></label><label>Search<input id="wc-search" type="search" placeholder="${category}" value="${esc(wcState.search)}"></label></div><section class="page-panel wc-board"><div class="panel-head"><div class="wc-heading"><h2>${category}</h2><span class="meta">Update ${esc(patch.label||patch.id||'unconfirmed')}</span></div><span class="meta"><span>${wrNumber(result.games)} <span>eligible player-games</span></span><span>${wrNumber(result.allGames)} <span>collected player-games</span></span></span></div><p class="wc-explainer">${type==='units'?'Average military production share in winning and losing games. Click a unit for composition bands.':'Match outcomes when a research or construction order was issued. Click an item for its sample details.'}</p>${rows?`<p class="wc-scroll-hint">Scroll sideways to compare shares and samples.</p><div class="table-scroll"><table class="wr-table wc-table"><thead><tr><th scope="col" class="wr-rank">#</th><th scope="col">${WC_ITEM_LABELS[type]}</th>${headings}${sorted('usage','Used in')}${sorted('rate','Win rate when used')}${sorted('games','Wins / player-games')}</tr></thead><tbody>${rows}</tbody></table></div>`:`<p class="wc-empty meta" role="status">${empty}</p>`}</section><p class="wr-source meta"><span>Official match results and replay commands</span> · <span>Update ${esc(patch.label||patch.id||'unconfirmed')}</span> · <span>${wrNumber(coverage.parsedReplays||0)} <span>parsed replays</span></span>${coverage.unavailableReplays?` · <span>${wrNumber(coverage.unavailableReplays)} <span>unavailable replays</span></span>`:''}</p><details class="wc-method"><summary>How to read these rankings</summary><p>Unit production includes training and field-construction orders. Starting units are excluded. Cancelled and unfinished orders may remain; completion is not inferred.</p><p>Unit shares include zero-use games among eligible civilizations, and exclude player-games without military production or with unresolved possible unit orders. Technology and landmark orders count once per player-game. Failed or unavailable replays do not count as non-use.</p><p>Rows with at least 30 uses are ranked; smaller samples are listed below. Differences are percentage points. A higher share in wins is an association, not proof that producing more of a unit causes wins. Civilizations, game length, opponents and team composition also affect outcomes.</p><p>Intervals are descriptive and do not adjust for repeated players or teammates. Civilizations use the larger match-history dataset; unit, technology and landmark figures use the separately collected replay sample.</p></details>`;
  wrBindCategories();
  const save=()=>{try{localStorage.setItem('aoe-crafter-winrate-items-v1',JSON.stringify(wcState));localStorage.setItem(WR_KEY,JSON.stringify(wrState));}catch{}},again=()=>{save();renderWinrateChoices(type);enhanceSelects();};
  $('#wc-mode').onchange=event=>{wcState.mode=event.target.value;again();};$('#wc-civ').onchange=event=>{wrState.civ=event.target.value;again();};$('#wc-rating').onchange=event=>{wcState.rating=event.target.value;again();};
  $('#wc-search').oninput=event=>{const start=event.target.selectionStart;wcState.search=event.target.value;again();$('#wc-search').focus();$('#wc-search').setSelectionRange(start,start);};
  $$('[data-wc-sort]').forEach(button=>button.onclick=()=>{wcState.sort=button.dataset.wcSort;again();});
  $$('[data-wc-detail]').forEach(button=>button.onclick=()=>{const row=button.closest('tr').nextElementSibling,open=button.getAttribute('aria-expanded')!=='true';button.setAttribute('aria-expanded',String(open));button.querySelector('.wc-expand').textContent=open?'−':'+';row.hidden=!open;});
}
window.WinrateItems={aggregate:wcAggregate};
