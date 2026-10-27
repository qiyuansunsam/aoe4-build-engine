// Players section (skill analysis): the index lists the tracked players with a radar each, a profile page shows the
// large radar with every axis's component rows (value, percentile, n) and the analysed-games table, a game page shows
// the roster with per-player axis scores and the evidence tables, and the Chinese layer covers the new text.
// Run with the server up: node site/verify-players.cjs
const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch(),ctx=await b.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.addInitScript(()=>{try{localStorage.removeItem('aoe-crafter-v2');localStorage.removeItem('aoe-crafter-lang');}catch{}});
await p.goto('http://127.0.0.1:8765/#players',{waitUntil:'networkidle'});
const snapshot=await p.evaluate(()=>({ids:PLAYER_PROFILES.players.map(x=>x.profileId),tracked:PLAYER_PROFILES.players.filter(x=>x.tracked).length,matches:PLAYER_ANALYSIS.matches.length,pool:PLAYER_ANALYSIS.poolSize,analysis:Object.fromEntries(Object.entries(PLAYER_ANALYSIS.players).map(([k,v])=>[k,v.analyzedGames]))}));
assert.equal(snapshot.tracked,snapshot.ids.length,'every profile is a tracked player');assert.ok(snapshot.matches>=1,'analysis has recorded matches');
assert.equal(await p.locator('.player-card').count(),snapshot.ids.length,'one card per player');assert.equal(await p.locator('.player-card .radar').count(),snapshot.ids.length,'one radar per card');
assert.equal(await p.locator('nav [data-page="players"][aria-current="page"]').count(),1,'sidebar marks Players');
const report=[];
for(const id of snapshot.ids){await p.goto('http://127.0.0.1:8765/#players/'+id,{waitUntil:'networkidle'});await p.waitForSelector('.player-head');
  const games=snapshot.analysis[String(id)]||[];
  const r=await p.evaluate(()=>({civPills:document.querySelectorAll('.civ-pill').length,phase:!!document.querySelector('.phase-panel'),name:document.querySelector('.player-head h1').textContent,title:document.title,radar:!!document.querySelector('.radar-large'),axisBlocks:document.querySelectorAll('.axis-block').length,metricRows:document.querySelectorAll('.metric-table tbody tr').length,gameRows:document.querySelectorAll('.analysis-games tbody tr a').length,tiles:document.querySelectorAll('.head-modes .mode-tile').length}));
  assert.equal(r.title,'Players · Mathmatically Correct AoE 4');assert.ok(r.tiles>=1,`${id} rank tiles`);
  if(games.length){assert.ok(r.radar,`${id} large radar`);assert.equal(r.axisBlocks,9,`${id} nine axes`);assert.ok(r.metricRows>=30,`${id} component rows`);assert.ok(r.civPills>=2,`${id} civilization filter`);assert.equal(r.gameRows,games.length,`${id} analysed game rows`);
    await p.goto('http://127.0.0.1:8765/#players/'+id+'/'+games[0],{waitUntil:'networkidle'});await p.waitForSelector('.evidence-panel');
    const g=await p.evaluate(()=>({roster:document.querySelectorAll('.game-detail-player').length,me:document.querySelectorAll('.game-detail-player.is-me').length,axes:document.querySelectorAll('.mini-axes').length,evidence:document.querySelectorAll('.evidence-panel').length,blocks:document.querySelectorAll('.evidence-block').length,spark:!!document.querySelector('.spark')}));
    assert.ok(g.roster>=2&&g.me===1,`${id} roster highlights the player`);assert.equal(g.axes,g.roster,`${id} axis scores per roster player`);assert.equal(g.evidence,6,`${id} six evidence panels`);assert.ok(g.blocks>=5,`${id} evidence tables`);assert.ok(g.spark,`${id} villager sparkline`);
    Object.assign(r,{game:games[0],...g});}
  report.push(r);}
// Chinese layer: the new UI labels translate (names, numbers and ids stay).
await p.goto('http://127.0.0.1:8765/#players',{waitUntil:'networkidle'});await p.click('#lang-toggle');await p.waitForFunction(()=>document.querySelector('nav [data-page="games"]').textContent.includes('\u5bf9\u5c40'));await p.waitForSelector('.player-card');
const zhIndex=await p.evaluate(()=>[...document.querySelectorAll('.axis-mini span,.player-card-recent>span,nav [data-page="players"]')].map(e=>e.textContent.trim()));
let latin=zhIndex.filter(t=>/[A-Za-z]{3}/.test(t.replace(/AoE4 World|ELO/g,'')));assert.deepEqual(latin,[],'index UI text translated: '+latin.join(' | '));
const first=snapshot.ids.find(id=>(snapshot.analysis[String(id)]||[]).length);
if(first){await p.goto('http://127.0.0.1:8765/#players/'+first,{waitUntil:'networkidle'});await p.waitForSelector('.axis-block');
  const zhProfile=await p.evaluate(()=>[...document.querySelectorAll('.summary-heading h2,.axis-block h3,.metric-table th[scope=row] > b,.analysis-games thead th,.result-pill')].map(e=>e.textContent.trim()));
  latin=[...new Set(zhProfile.filter(t=>/[A-Za-z]{3}/.test(t.replace(/ELO|\bI{1,3}\b/g,''))))];assert.deepEqual(latin,[],'profile UI text translated: '+latin.join(' | '));
  await p.goto('http://127.0.0.1:8765/#players/'+first+'/'+snapshot.analysis[String(first)][0],{waitUntil:'networkidle'});await p.waitForSelector('.evidence-panel');
  const zhMatch=await p.evaluate(()=>[...document.querySelectorAll('.evidence-panel h2,.evidence-block h3,.evidence-block th,.mode-facts dt')].map(e=>e.textContent.trim()));
  latin=[...new Set(zhMatch.filter(t=>/[A-Za-z]{3}/.test(t.replace(/p90|\bI{1,3}\b/g,''))))];assert.deepEqual(latin,[],'match UI text translated: '+latin.join(' | '));}
assert.deepEqual(errors,[],'no page errors');
console.log(JSON.stringify({snapshot:{players:snapshot.ids.length,matches:snapshot.matches,pool:snapshot.pool},report},null,1));await b.close();
})().catch(e=>{console.error(e);process.exit(1);});
