/* Win rates section (#winrates): civilization win-rate leaderboards for the current patch.
 * Data: data/winrates.json (window.WINRATES), aggregated by scripts/build_winrates.py from ranked match rows that
 * scripts/collect_relic_matches.py reads straight from Relic's community API. Each row is a count over recorded
 * matches: games, wins, picks. The page shows Solo (1v1) and Team (2v2 + 3v3 + 4v4 added together) by default; the
 * view switch splits team games by size. The map filter narrows every board to one map (rows stay civilizations);
 * the civilization filter turns the rows into maps for that civilization. Clicking a row's name sets that filter.
 * The rank filter lists the bands the data holds (Diamond+ only for now). */
const WINRATES=window.WINRATES&&window.WINRATES.ranks?window.WINRATES:{ranks:{},bands:[],maps:{},sample:{},patch:{},rules:{}};
const WR_MODE_LABELS={solo:['Solo','1v1'],team:['Team','2v2 + 3v3 + 4v4'],'2v2':['2v2','Team ranked'],'3v3':['3v3','Team ranked'],'4v4':['4v4','Team ranked']};
const WR_VIEWS={overall:['solo','team'],sizes:['solo','2v2','3v3','4v4']};
const WR_MIN_GAMES=30;   // rows with fewer games are listed below the ranking, not ranked
const WR_KEY='aoe-crafter-winrates-v1';
let wrState={rank:'',view:'overall',map:'',civ:'',sort:'rate'};
try{Object.assign(wrState,JSON.parse(localStorage.getItem(WR_KEY)||'{}'));}catch{}
const wrNumber=n=>Math.round(n).toLocaleString('en-US');
const wrPercent=(x,digits=1)=>(100*x).toFixed(digits)+'%';
// Wilson score interval for a win share: the range the true rate lies in at 95% confidence given this many games.
function wrInterval(wins,games){if(!games)return [0,1];const z=1.96,p=wins/games,d=1+z*z/games,c=(p+z*z/(2*games))/d,h=z*Math.sqrt(p*(1-p)/games+z*z/(4*games*games))/d;return [Math.max(0,c-h),Math.min(1,c+h)];}
function wrBand(){const bands=WINRATES.bands||[];return bands.find(b=>b.id===wrState.rank)||bands[0]||null;}
function wrMode(mode){const band=wrBand();return band&&WINRATES.ranks[band.id]?.modes?.[mode]||null;}
function wrMapName(slug){return WINRATES.maps?.[slug]?.name||slug;}
const wrPicks=scope=>Object.values(scope.civs).reduce((s,v)=>s+v[2],0);
const wrMake=(kind,key,[games,wins,picked],picks)=>({kind,key,games,wins,picked,rate:games?wins/games:0,pick:picks?picked/picks:0,interval:wrInterval(wins,games)});
// A board is one mode's table. Rows are civilizations (all maps, or the chosen map), or maps when a civilization is chosen.
function wrBoard(mode){const data=wrMode(mode);if(!data)return null;let rows,games,total=null;
  if(wrState.civ){rows=Object.entries(data.maps||{}).filter(([,m])=>m.civs[wrState.civ]).map(([slug,m])=>wrMake('map',slug,m.civs[wrState.civ],wrPicks(m)));const all=data.civs[wrState.civ]||[0,0,0];games=all[0];total=wrMake('civ',wrState.civ,all,wrPicks(data));}
  else{const scope=wrState.map?data.maps?.[wrState.map]||{games:0,civs:{}}:data,picks=wrPicks(scope);rows=Object.entries(scope.civs).map(([civ,v])=>wrMake('civ',civ,v,picks));games=scope.games;}
  const by=wrState.sort;rows.sort((a,b)=>by==='games'?b.games-a.games||b.rate-a.rate:by==='pick'?b.pick-a.pick||b.rate-a.rate:b.rate-a.rate||b.games-a.games);
  return {mode,games,total,ranked:rows.filter(r=>r.games>=WR_MIN_GAMES),thin:rows.filter(r=>r.games<WR_MIN_GAMES).sort((a,b)=>b.games-a.games)};}
// One shared scale for every board on the page, so bar lengths compare across boards: the largest distance from 50%
// among ranked rows, rounded up to the next 5 points (at least 5, at most 25).
function wrSpan(boards){let far=0;for(const b of boards)for(const r of b.total?[b.total,...b.ranked]:b.ranked)if(r.games>=WR_MIN_GAMES)far=Math.max(far,Math.abs(r.rate-.5));return Math.min(.25,Math.max(.05,Math.ceil(far*20-1e-9)/20));}
function wrBar(row,span){const pos=x=>50+50*Math.max(-1,Math.min(1,(x-.5)/span)),at=pos(row.rate),lo=pos(row.interval[0]),hi=pos(row.interval[1]),up=row.rate>=.5;
  return `<span class="wr-bar" aria-hidden="true"><i class="wr-range" style="left:${lo.toFixed(2)}%;width:${Math.max(0,hi-lo).toFixed(2)}%"></i><i class="wr-fill ${up?'up':'down'}" style="left:${Math.min(50,at).toFixed(2)}%;width:${Math.abs(at-50).toFixed(2)}%"></i><i class="wr-mid"></i></span>`;}
function wrRow(row,index,span,cls){const name=row.kind==='civ'?civName(row.key):wrMapName(row.key),tip=`${name}: ${wrNumber(row.wins)} wins in ${wrNumber(row.games)} games, 95% range ${wrPercent(row.interval[0])} to ${wrPercent(row.interval[1])}, picked ${wrNumber(row.picked)} times`;
  const label=cls==='wr-total'?`${civFlag(row.key)}<span>All maps</span>`:row.kind==='civ'?`${civFlag(row.key)}<button type="button" class="wr-link" data-wr-civ="${esc(row.key)}">${esc(name)}</button>`:`<button type="button" class="wr-link" data-wr-map="${esc(row.key)}">${esc(name)}</button>`;
  return `<tr class="${cls}" data-wr-row="${esc(row.key)}" title="${esc(tip)}"><td class="wr-rank">${cls?'':index+1}</td><th scope="row" class="wr-name">${label}</th><td class="wr-barcell">${row.games?wrBar(row,span):''}</td><td class="wr-rate">${row.games?wrPercent(row.rate):'–'}</td><td class="wr-games">${wrNumber(row.games)}</td><td class="wr-pick">${wrPercent(row.pick)}</td></tr>`;}
function wrBoardHtml(board,span){const [title,sub]=WR_MODE_LABELS[board.mode],head=(key,label,cls)=>`<th scope="col" class="${cls}"><button type="button" class="wr-sort" data-wr-sort="${key}" aria-pressed="${wrState.sort===key}">${label}</button></th>`;
  const lo=wrPercent(.5-span,0),hi=wrPercent(.5+span,0),any=board.ranked.length||board.thin.length;
  return `<section class="page-panel wr-board" data-wr-mode="${board.mode}"><div class="panel-head"><h2>${title}</h2><span class="meta">${esc(sub)} · ${wrNumber(board.games)} games</span></div>${any?`<div class="table-scroll"><table class="wr-table"><thead><tr><th scope="col" class="wr-rank">#</th><th scope="col">${wrState.civ?'Map':'Civilization'}</th><th scope="col" class="wr-barcell"><span class="wr-axis" aria-hidden="true"><span>${lo}</span><span>50%</span><span>${hi}</span></span></th>${head('rate','Win rate','wr-rate')}${head('games','Games','wr-games')}${head('pick','Pick rate','wr-pick')}</tr></thead><tbody>${board.total?wrRow(board.total,0,span,'wr-total'):''}${board.ranked.map((r,i)=>wrRow(r,i,span,'')).join('')}${board.thin.length?`<tr class="wr-divider"><td colspan="6">Under ${WR_MIN_GAMES} games</td></tr>${board.thin.map((r,i)=>wrRow(r,i,span,'wr-thin')).join('')}`:''}</tbody></table></div>`:'<p class="meta">No games recorded.</p>'}</section>`;}
function wrDate(iso){if(!iso)return '';const [y,m,d]=iso.split('-').map(Number);return `${d} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1]} ${y}`;}
function renderWinrates(){const bands=WINRATES.bands||[],band=wrBand();
  if(!band){$('#page').innerHTML=pageTop('Win rates','')+'<section class="page-panel"><p class="meta">No win-rate data in this build.</p></section>';return;}
  const all=WINRATES.ranks[band.id]?.modes||{},mapGames={},civs=new Set();
  for(const mode of ['solo','team']){for(const [slug,m] of Object.entries(all[mode]?.maps||{}))mapGames[slug]=(mapGames[slug]||0)+m.games;for(const civ of Object.keys(all[mode]?.civs||{}))civs.add(civ);}
  if(wrState.map&&!mapGames[wrState.map])wrState.map='';
  if(wrState.civ&&!civs.has(wrState.civ))wrState.civ='';
  if(wrState.civ)wrState.map='';
  if(!WR_VIEWS[wrState.view])wrState.view='overall';
  const boards=WR_VIEWS[wrState.view].map(wrBoard).filter(Boolean),span=wrSpan(boards);
  const maps=Object.entries(mapGames).sort((a,b)=>b[1]-a[1]),sample=WINRATES.sample||{},patch=WINRATES.patch||{},rules=WINRATES.rules||{};
  const source=[`Relic match history`,`Update ${patch.label||''}${patch.builds?.length?` (builds ${patch.builds.join(', ')})`:''}`,`${wrNumber(WINRATES.ranks[band.id]?.games||0)} ranked games`,sample.firstMatch&&sample.lastMatch?`${wrDate(sample.firstMatch)} to ${wrDate(sample.lastMatch)}`:'',`average rating ${band.minRating}+ before the match`,rules.minDurationSeconds?`games under ${Math.round(rules.minDurationSeconds/60)}:00 left out`:'',rules.soloMirrorsExcluded?'1v1 mirror games left out of win rate':''].filter(Boolean);
  $('#page').innerHTML=pageTop('Win rates','')+`<div class="page-filter library-filter wr-filter"><label>Rank<select id="wr-rank">${bands.map(b=>`<option value="${esc(b.id)}"${b.id===band.id?' selected':''}>${esc(b.label)}</option>`).join('')}</select></label><label>Map<select id="wr-map"><option value="">All maps</option>${maps.map(([slug])=>`<option value="${esc(slug)}"${slug===wrState.map?' selected':''}>${esc(wrMapName(slug))}</option>`).join('')}</select></label><label>Civilization<select id="wr-civ"><option value="">All civilizations</option>${civOptions([...civs]).replace(`value="${esc(wrState.civ)}"`,`value="${esc(wrState.civ)}" selected`)}</select></label><div class="wr-view"><span class="wr-view-label" id="wr-view-label">Boards</span><div class="segmented" role="group" aria-labelledby="wr-view-label"><button type="button" data-wr-view="overall" aria-pressed="${wrState.view==='overall'}">Solo and team</button><button type="button" data-wr-view="sizes" aria-pressed="${wrState.view==='sizes'}">By team size</button></div></div></div><div class="wr-grid wr-grid-${boards.length}">${boards.map(b=>wrBoardHtml(b,span)).join('')}</div><p class="wr-source meta">${source.map(esc).join(' · ')}</p>`;
  const save=()=>{try{localStorage.setItem(WR_KEY,JSON.stringify(wrState));}catch{}},again=focus=>{save();renderWinrates();enhanceSelects();if(focus)document.querySelector(focus)?.focus({preventScroll:true});};
  $('#wr-rank').onchange=e=>{wrState.rank=e.target.value;again();};
  $('#wr-map').onchange=e=>{wrState.map=e.target.value;if(wrState.map)wrState.civ='';again();};
  $('#wr-civ').onchange=e=>{wrState.civ=e.target.value;if(wrState.civ)wrState.map='';again();};
  $$('[data-wr-view]').forEach(b=>b.onclick=()=>{if(wrState.view===b.dataset.wrView)return;wrState.view=b.dataset.wrView;again(`[data-wr-view="${wrState.view}"]`);});
  $$('[data-wr-sort]').forEach(b=>b.onclick=()=>{const mode=b.closest('[data-wr-mode]').dataset.wrMode;wrState.sort=b.dataset.wrSort;again(`[data-wr-mode="${mode}"] [data-wr-sort="${wrState.sort}"]`);});
  $$('[data-wr-civ]').forEach(b=>b.onclick=()=>{wrState.civ=b.dataset.wrCiv;wrState.map='';again('.wr-board .wr-link');});
  $$('[data-wr-map]').forEach(b=>b.onclick=()=>{wrState.map=b.dataset.wrMap;wrState.civ='';again('.wr-board .wr-link');});
}
