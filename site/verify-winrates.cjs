// Win rates section: the default view shows the Solo and Team boards for the first rank band; every row's numbers
// equal the counts in data/winrates.json; the team-size view shows 1v1, 2v2, 3v3 and 4v4; the map filter narrows each
// board to that map's counts; sorting works; the Chinese layer covers the new text; no horizontal overflow at 390 px.
// Run with the server up: node site/verify-winrates.cjs [--shots]
const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const shots=process.argv.includes('--shots'),shotDir=path.join(__dirname,'shots');
const BASE='http://127.0.0.1:8765/';
(async()=>{const b=await chromium.launch(),ctx=await b.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
if(shots)fs.mkdirSync(shotDir,{recursive:true});
await p.addInitScript(()=>{try{if(!sessionStorage.getItem('wr-verify')){localStorage.removeItem('aoe-crafter-winrates-v1');localStorage.removeItem('aoe-crafter-lang');sessionStorage.setItem('wr-verify','1');}}catch{}});
await p.goto(BASE+'#winrates',{waitUntil:'networkidle'});await p.waitForSelector('.wr-board');
const data=await p.evaluate(()=>WINRATES),band=data.bands[0],modes=data.ranks[band.id].modes;
assert.equal(await p.title(),'Win rates · Mathmatically Correct AoE 4');
assert.equal(await p.locator('nav [data-page="winrates"][aria-current="page"]').count(),1,'sidebar marks Win rates');
assert.equal(band.id,'diamond_plus');assert.equal(await p.locator('#wr-rank option').count(),data.bands.length,'rank filter lists the bands in the data');
const read=()=>p.evaluate(()=>[...document.querySelectorAll('.wr-board')].map(s=>({mode:s.dataset.wrMode,title:s.querySelector('h2').textContent,meta:s.querySelector('.panel-head .meta').textContent,
  rows:[...s.querySelectorAll('tbody tr:not(.wr-divider)')].map(r=>({thin:r.classList.contains('wr-thin'),rank:r.querySelector('.wr-rank').textContent,civ:r.querySelector('.wr-name .wr-link, .wr-name span').textContent,rate:r.querySelector('.wr-rate').textContent,games:r.querySelector('.wr-games').textContent,pick:r.querySelector('.wr-pick').textContent,fill:r.querySelector('.wr-fill')?.className||''}))})));
const names=await p.evaluate(()=>Object.fromEntries(GAME_CATALOG.civilizations.map(c=>[c.name,c.id])));
const check=(board,scope,label)=>{const total=Object.values(scope.civs).reduce((s,v)=>s+v[2],0);assert.ok(board.meta.includes(scope.games.toLocaleString('en-US')+' games'),`${label} game count`);
  assert.equal(board.rows.length,Object.keys(scope.civs).length,`${label} one row per civilization`);
  for(const r of board.rows){const [games,wins,picked]=scope.civs[names[r.civ]]||[];assert.ok(games!==undefined,`${label} ${r.civ} is in the data`);
    assert.equal(r.games,games.toLocaleString('en-US'),`${label} ${r.civ} games`);if(games)assert.equal(r.rate,(100*wins/games).toFixed(1)+'%',`${label} ${r.civ} win rate`);
    assert.equal(r.pick,(100*picked/total).toFixed(1)+'%',`${label} ${r.civ} pick rate`);assert.equal(r.thin,games<30,`${label} ${r.civ} ranked only with 30+ games`);
    if(games)assert.ok(r.fill.includes(wins/games>=.5?'up':'down'),`${label} ${r.civ} bar side`);}
  const ranked=board.rows.filter(r=>!r.thin).map(r=>parseFloat(r.rate));assert.deepEqual(ranked,[...ranked].sort((x,y)=>y-x),`${label} ranked by win rate`);
  assert.deepEqual(board.rows.filter(r=>!r.thin).map(r=>r.rank),ranked.map((_,i)=>String(i+1)),`${label} rank numbers`);};
let boards=await read();
assert.deepEqual(boards.map(x=>x.mode),['solo','team'],'default view is Solo and Team');check(boards[0],modes.solo,'solo');check(boards[1],modes.team,'team');
for(const civ of ['vikings','scots'])assert.ok(modes.solo.civs[civ]&&modes.team.civs[civ],`${civ} is in the data`);
// team is the sum of the three team sizes
for(const civ of Object.keys(modes.team.civs))for(const i of [0,1,2])assert.equal(modes.team.civs[civ][i],['2v2','3v3','4v4'].reduce((s,m)=>s+(modes[m].civs[civ]?.[i]||0),0),`team ${civ} adds the team sizes`);
if(shots)await p.screenshot({path:path.join(shotDir,'winrates-default-dark.png'),fullPage:true});
// team-size view
await p.click('[data-wr-view="sizes"]');await p.waitForSelector('[data-wr-mode="4v4"]');boards=await read();
assert.deepEqual(boards.map(x=>x.mode),['solo','2v2','3v3','4v4']);for(const x of boards)check(x,modes[x.mode],x.mode);
if(shots)await p.screenshot({path:path.join(shotDir,'winrates-sizes-dark.png'),fullPage:true});
// map filter (custom select mirrors the native one)
const map=Object.keys(modes.team.maps)[0];
await p.evaluate(slug=>{const s=document.querySelector('#wr-map');s.value=slug;s.dispatchEvent(new Event('change',{bubbles:true}));},map);await p.waitForFunction(()=>document.querySelector('#wr-map').value!=='');
boards=await read();for(const x of boards)check(x,modes[x.mode].maps[map]||{games:0,civs:{}},`${x.mode} on ${map}`);
await p.click('[data-wr-view="overall"]');await p.waitForFunction(()=>document.querySelectorAll('.wr-board').length===2);
if(shots)await p.screenshot({path:path.join(shotDir,'winrates-map-dark.png'),fullPage:true});
// civilization filter: rows become maps for that civilization, with its all-maps row on top; clicking a map goes back to civilizations on that map
await p.click('[data-wr-mode="team"] [data-wr-civ="french"]');await p.waitForSelector('.wr-total');
const civView=await p.evaluate(()=>({civ:document.querySelector('#wr-civ').value,map:document.querySelector('#wr-map').value,head:document.querySelector('[data-wr-mode="team"] thead th:nth-child(2)').textContent,
  total:[...document.querySelectorAll('[data-wr-mode="team"] .wr-total td')].map(td=>td.textContent),rows:[...document.querySelectorAll('[data-wr-mode="team"] tbody tr[data-wr-row]:not(.wr-total)')].map(r=>({slug:r.dataset.wrRow,rate:r.querySelector('.wr-rate').textContent,games:r.querySelector('.wr-games').textContent}))}));
assert.equal(civView.civ,'french');assert.equal(civView.map,'');assert.equal(civView.head,'Map');
{const [g,w]=modes.team.civs.french;assert.equal(civView.total[2],(100*w/g).toFixed(1)+'%','all-maps row is the civilization total');assert.equal(civView.total[3],g.toLocaleString('en-US'));}
assert.equal(civView.rows.length,Object.values(modes.team.maps).filter(m=>m.civs.french).length,'one row per map the civilization was played on');
for(const r of civView.rows){const [g,w]=modes.team.maps[r.slug].civs.french;assert.equal(r.games,g.toLocaleString('en-US'),`french on ${r.slug} games`);if(g)assert.equal(r.rate,(100*w/g).toFixed(1)+'%',`french on ${r.slug} win rate`);}
if(shots)await p.screenshot({path:path.join(shotDir,'winrates-civ-dark.png'),fullPage:true});
await p.click('[data-wr-mode="team"] [data-wr-map]');await p.waitForFunction(()=>document.querySelector('#wr-map').value!==''&&document.querySelector('#wr-civ').value==='');
await p.evaluate(()=>{const s=document.querySelector('#wr-map');s.value='';s.dispatchEvent(new Event('change',{bubbles:true}));});await p.waitForFunction(()=>document.querySelector('#wr-map').value==='');
// sort by games
await p.click('[data-wr-mode="team"] [data-wr-sort="games"]');boards=await read();
const g=boards[1].rows.filter(r=>!r.thin).map(r=>Number(r.games.replace(/,/g,'')));assert.deepEqual(g,[...g].sort((x,y)=>y-x),'sorted by games');
await p.click('[data-wr-mode="team"] [data-wr-sort="rate"]');
await p.evaluate(()=>{const s=document.querySelector('#wr-map');s.value='';s.dispatchEvent(new Event('change',{bubbles:true}));});
// light theme
await p.evaluate(()=>{const s=document.querySelector('#theme');s.value='light';s.dispatchEvent(new Event('change',{bubbles:true}));});
if(shots){await p.waitForTimeout(400);await p.screenshot({path:path.join(shotDir,'winrates-default-light.png'),fullPage:true});}
await p.evaluate(()=>{const s=document.querySelector('#theme');s.value='dark';s.dispatchEvent(new Event('change',{bubbles:true}));});
// Chinese layer
await p.click('#lang-toggle');await p.waitForFunction(()=>document.querySelector('nav [data-page="games"]').textContent.includes('\u5bf9\u5c40'));await p.waitForSelector('.wr-board');
const zh=await p.evaluate(()=>[...document.querySelectorAll('nav [data-page="winrates"],.wr-filter label,.wr-view-label,.wr-view button,.wr-board h2,.wr-board .panel-head .meta,.wr-table thead th,.wr-name .wr-link,.wr-name span,.wr-divider td,.wr-source,#wr-map option,.wr-filter .select-trigger')].map(e=>(e.childNodes[0]?.nodeType===3?e.childNodes[0].data:e.textContent).trim()).filter(Boolean));
const latin=[...new Set(zh.filter(t=>/[A-Za-z]{3}/.test(t.replace(/Relic|Tacksman|Border Reiver/g,''))))];assert.deepEqual(latin,[],'Win rates text translated: '+latin.join(' | '));
if(shots)await p.screenshot({path:path.join(shotDir,'winrates-default-zh.png'),fullPage:true});
await p.click('#lang-toggle');await p.waitForFunction(()=>document.documentElement.lang==='en');
// narrow screen
await p.setViewportSize({width:390,height:844});await p.goto(BASE+'#winrates',{waitUntil:'networkidle'});await p.waitForSelector('.wr-board');
assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'no horizontal overflow at 390 px');
if(shots)await p.screenshot({path:path.join(shotDir,'winrates-narrow.png'),fullPage:true});
assert.deepEqual(errors,[],'no page errors');
console.log(JSON.stringify({band:band.label,games:data.ranks[band.id].games,solo:modes.solo.games,team:modes.team.games,maps:Object.keys(modes.team.maps).length,civs:Object.keys(modes.team.civs).length},null,1));
console.log('win rates verified');await b.close();})().catch(e=>{console.error(e);process.exit(1);});
