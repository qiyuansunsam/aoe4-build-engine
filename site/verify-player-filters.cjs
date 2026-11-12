// Player profile game filters (2026-11-13): the browser recomputes a profile from chosen games. Checks that the
// recomputation equals skill_metrics.py's own numbers (all games -> the stored profile radar, one civilization -> the
// stored byCiv radar), and that the result / recency pills and per-game checkboxes change the listed and counted games.
// Run with the server up: node site/verify-player-filters.cjs [port]
const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
const port=process.argv[2]||'8765';
(async()=>{const b=await chromium.launch(),ctx=await b.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.addInitScript(()=>{try{localStorage.removeItem('aoe-crafter-v2');localStorage.removeItem('aoe-crafter-lang');}catch{}});
await p.goto(`http://127.0.0.1:${port}/#players`,{waitUntil:'networkidle'});
const parity=await p.evaluate(()=>{const out={players:0,axes:0,components:0,civs:0,worst:0,bad:[]};
const cmp=(mine,theirs,tag)=>{for(const ax of Object.keys(PLAYER_ANALYSIS.axes)){const a=mine[ax],t=theirs?.[ax];if(!t)continue;out.axes++;
if((a.score==null)!==(t.score==null)||(a.score!=null&&Math.abs(a.score-t.score)>0.11))out.bad.push([tag,ax,a.score,t.score]);else if(a.score!=null)out.worst=Math.max(out.worst,Math.abs(a.score-t.score));
for(const [path,c] of Object.entries(t.components||{})){out.components++;const m=a.components[path];if(!m||Math.abs(m.percentile-c.percentile)>0.11||Math.abs(m.value-c.value)>0.0006||m.n!==c.n||m.games!==c.games)out.bad.push([tag,path,m,c]);}
for(const path of Object.keys(a.components))if(!(path in (t.components||{})))out.bad.push([tag,path,'extra']);}};
for(const [pid,a] of Object.entries(PLAYER_ANALYSIS.players)){if(!a.matches.length)continue;out.players++;
const fulls=a.matches.map(m=>PLAYER_ANALYSIS.matches.find(x=>x.gameId===m.gameId).players.find(x=>String(x.profileId)===pid));
cmp(radarFromGames(fulls),a.radar,pid);
const ph=phaseFromGames(fulls);if(JSON.stringify(ph.phase)!==JSON.stringify(a.strongestPhase))out.bad.push([pid,'phase',ph.phase,a.strongestPhase]);
for(const [civ,c] of Object.entries(a.byCiv||{})){out.civs++;cmp(radarFromGames(fulls.filter(f=>f.civ===civ)),c.radar,pid+':'+civ);}}
return out;});
assert.deepEqual(parity.bad.slice(0,5),[],'browser recomputation equals the stored radars');assert.ok(parity.players>=4&&parity.components>100,'parity covered the profiles');
// Live ranks: after the AoE4 World read every card shows the rating now held in memory; the read itself is reported.
await p.evaluate(()=>window.playerRanksReady());
const ranks=await p.evaluate(()=>playerProfiles.players.map(x=>({id:x.profileId,live:!!x.ranksAsOf,rating:x.modes?.rm_team?.rating??null,snapshot:PLAYER_PROFILES.players.find(y=>y.profileId===x.profileId)?.modeSnapshotAsOf||null})));
for(const r of ranks){if(r.rating==null)continue;const text=await p.locator(`.player-card:has(a[href="#players/${r.id}"]) .player-meta`).innerText();assert.ok(text.replace(/,/g,'').includes(String(r.rating)),`card ${r.id} shows rating ${r.rating}: ${text}`);}
// Home page pills: the cards' game counts and radars follow the result / recency choice, and the choice carries into a profile.
const homeFacts=await p.evaluate(()=>Object.fromEntries(Object.entries(PLAYER_ANALYSIS.players).map(([id,a])=>[id,{all:a.analyzedGames.length,wins:a.matches.filter(m=>m.result==='win').length}])));
const cardGames=()=>p.evaluate(()=>Object.fromEntries([...document.querySelectorAll('.player-card')].map(c=>[c.querySelector('a.match-open').getAttribute('href').split('/')[1],+c.querySelector('.player-card-recent b').textContent])));
assert.deepEqual(await cardGames(),Object.fromEntries(Object.entries(homeFacts).map(([k,v])=>[k,v.all])),'home: every analysed game counted');
await p.locator('.players-filter .filter-pill[data-key="result"][data-value="win"]').click();
assert.deepEqual(await cardGames(),Object.fromEntries(Object.entries(homeFacts).map(([k,v])=>[k,v.wins])),'home: wins only');
const homeScores=await p.evaluate(()=>Object.fromEntries([...document.querySelectorAll('.player-card')].map(c=>{const id=c.querySelector('a.match-open').getAttribute('href').split('/')[1],a=PLAYER_ANALYSIS.players[id],fulls=a.matches.filter(m=>m.result==='win').map(m=>PLAYER_ANALYSIS.matches.find(x=>x.gameId===m.gameId).players.find(x=>String(x.profileId)===id)),r=radarFromGames(fulls);
return [id,[[...c.querySelectorAll('.axis-mini b')].map(b=>b.textContent.trim()),Object.keys(PLAYER_ANALYSIS.axes).map(ax=>r[ax].score==null?'—':String(r[ax].score))]];})));
for(const [id,[shown,expected]] of Object.entries(homeScores))assert.deepEqual(shown,expected,`home: card ${id} axis scores are those of its wins`);
await p.locator('.player-card a.match-open').first().click();await p.waitForSelector('.game-filter .filter-pill');
assert.equal(await p.locator('.filter-pill.active[data-key="result"]').getAttribute('data-value'),'win','the home choice carries into the profile');
await p.locator('.filter-pill[data-key="result"][data-value=""]').click();
await p.goto(`http://127.0.0.1:${port}/#players`,{waitUntil:'networkidle'});assert.deepEqual(await cardGames(),Object.fromEntries(Object.entries(homeFacts).map(([k,v])=>[k,v.all])),'home: cleared');
const pid=await p.evaluate(()=>Object.entries(PLAYER_ANALYSIS.players).sort((x,y)=>y[1].matches.length-x[1].matches.length)[0][0]);
await p.goto(`http://127.0.0.1:${port}/#players/${pid}`,{waitUntil:'networkidle'});
const facts=await p.evaluate(pid=>{const a=PLAYER_ANALYSIS.players[pid];return {all:a.matches.length,wins:a.matches.filter(m=>m.result==='win').length,losses:a.matches.filter(m=>m.result==='loss').length,
patch:a.matches.filter(m=>(PLAYER_ANALYSIS.matches.find(x=>x.gameId===m.gameId).patch||0)>=12182).length};},pid);
const count=async()=>(await p.locator('.filter-count').innerText()).split('/').map(x=>+x.trim());
const rowsN=()=>p.locator('.analysis-games tbody tr:has(.pick-game)').count();
const shownScores=()=>p.evaluate(()=>Object.fromEntries([...document.querySelectorAll('.axis-block')].map(b=>[b.dataset.axis,b.querySelector('header b').textContent.trim()])));
const expectScores=sel=>p.evaluate(({pid,sel})=>{const a=PLAYER_ANALYSIS.players[pid],ids=new Set(sel),fulls=a.matches.filter(m=>ids.has(m.gameId)).map(m=>PLAYER_ANALYSIS.matches.find(x=>x.gameId===m.gameId).players.find(x=>String(x.profileId)===pid)),r=radarFromGames(fulls);return Object.fromEntries(Object.entries(r).map(([k,v])=>[k,v.score==null?'\u2014':String(v.score)]));},{pid,sel});
const listedIds=()=>p.evaluate(()=>[...document.querySelectorAll('.pick-game')].filter(c=>c.checked).map(c=>+c.dataset.game));
assert.deepEqual(await count(),[facts.all,facts.all],'no filter: every game counted');assert.equal(await rowsN(),facts.all);
const dates=await p.evaluate(()=>[...document.querySelectorAll('.pick-game')].map(c=>PLAYER_ANALYSIS.matches.find(x=>x.gameId===+c.dataset.game).startedAt));
assert.deepEqual(dates,[...dates].sort().reverse(),'games listed newest first');
await p.locator('.filter-pill[data-key="result"][data-value="win"]').click();
assert.deepEqual(await count(),[facts.wins,facts.wins],'wins only');assert.equal(await p.locator('.analysis-games tbody tr.loss').count(),0,'no loss rows under Wins');
assert.deepEqual(await shownScores(),await expectScores(await listedIds()),'axis scores are those of the winning games');
await p.locator('.pick-game').first().uncheck();
assert.deepEqual(await count(),[facts.wins-1,facts.wins],'one game unticked');assert.equal(await p.locator('.analysis-games tbody tr.off').count(),1);
assert.deepEqual(await shownScores(),await expectScores(await listedIds()),'axis scores follow the ticked games');
await p.locator('#pick-all').check();assert.deepEqual(await count(),[facts.wins,facts.wins],'tick all restores');
await p.locator('.filter-pill[data-key="result"][data-value="loss"]').click();assert.deepEqual(await count(),[facts.losses,facts.losses],'losses only');
assert.equal(await p.locator('.analysis-games tbody tr.win').count(),0,'no win rows under Losses');
await p.locator('.filter-pill[data-key="result"][data-value=""]').click();
await p.locator('.filter-pill[data-key="recent"][data-value="10"]').click();assert.deepEqual(await count(),[Math.min(10,facts.all),Math.min(10,facts.all)],'last 10');
assert.deepEqual((await p.evaluate(()=>[...document.querySelectorAll('.pick-game')].map(c=>PLAYER_ANALYSIS.matches.find(x=>x.gameId===+c.dataset.game).startedAt))),dates.slice(0,10),'last 10 are the newest ten');
assert.deepEqual(await shownScores(),await expectScores(await listedIds()),'axis scores are those of the last ten');
await p.locator('.filter-pill[data-key="recent"][data-value="patch"]').click();assert.deepEqual(await count(),[facts.patch,facts.patch],'since 17.0');
await p.locator('.filter-pill[data-key="recent"][data-value=""]').click();assert.deepEqual(await count(),[facts.all,facts.all],'filters cleared');
assert.equal(await p.locator('.radar-area').count(),1,'radar drawn');
await p.setViewportSize({width:390,height:800});assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1),'no page scroll at 390 px');
await p.screenshot({path:process.argv[3]||'player-filters.png',fullPage:false});
assert.deepEqual(errors,[],'no page errors');
console.log('player filters OK',JSON.stringify({ranks,parity:{players:parity.players,axes:parity.axes,components:parity.components,civs:parity.civs,worstScoreDiff:parity.worst},facts}));await b.close();})().catch(e=>{console.error(e);process.exit(1);});
