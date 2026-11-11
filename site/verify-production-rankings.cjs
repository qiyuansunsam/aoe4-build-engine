const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const {AxeBuilder}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/@axe-core/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const out=path.join(__dirname,'shots','production-rankings');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch();const context=await browser.newContext({viewport:{width:1440,height:1000}});const page=await context.newPage();
 const tab=async category=>{await page.locator(`[data-tier-category="${category}"]`).click();await page.waitForFunction(c=>document.querySelector(`[data-tier-category="${c}"]`)?.getAttribute('aria-current')==='page',category);};
 const setModes=async wanted=>{
  await page.locator('.tier-mode-picker').evaluate(el=>el.open=true);
  for(const id of wanted)await page.locator(`[data-tier-mode="${id}"]`).check();
  for(const id of ['1','2','3','4'].filter(x=>!wanted.includes(x)))await page.locator(`[data-tier-mode="${id}"]`).uncheck();
  await page.waitForFunction(ids=>JSON.stringify(tierModeState.modes)===JSON.stringify([...ids].sort()),wanted);
  await page.locator('.tier-mode-picker').evaluate(el=>el.open=false);
 };
 const errors=[],failures=[],checks=[];page.on('pageerror',e=>errors.push(e.message));page.on('requestfailed',r=>failures.push({url:r.url(),error:r.failure()?.errorText}));
 page.on('response',r=>{if(r.status()>=400&&!r.url().endsWith('/favicon.ico'))failures.push({url:r.url(),status:r.status()});});
 await page.goto('http://127.0.0.1:8765/#players/7195780',{waitUntil:'networkidle',timeout:60000});
 await page.locator('.player-radar-panel').waitFor();
 assert.equal(await page.locator('.production-profile,#production-profile-host').count(),0);
 assert.ok(await page.locator('.player-radar-panel .axis-block').count()>0,'Original player metric matrix retained');
 assert.ok(await page.locator('.radar').count()>0,'Original radar retained');
 checks.push('Original player radar and metric matrix retained; Production & openings removed');
 for(const theme of ['dark','light']){
  await page.locator('#theme').selectOption(theme,{force:true});
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:1000});await page.locator('.player-radar-panel').scrollIntoViewIfNeeded();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'Profile page overflow');
   await page.screenshot({path:path.join(out,`profile-${theme}-${width}.png`),animations:"disabled"});
   const scan=await new AxeBuilder({page}).include('.player-radar-panel').analyze();assert.deepEqual(scan.violations.map(v=>({id:v.id,impact:v.impact})),[]);
  }
 }
 await page.setViewportSize({width:1440,height:1000});await page.goto('http://127.0.0.1:8765/#unit-tiers',{waitUntil:'networkidle',timeout:60000});
 assert.match(await page.locator('h1').innerText(),/tier lists/i);assert.equal(await page.locator('#unit-tier-civ').inputValue(),'__all__');assert.equal(await page.locator('#unit-tier-civ option').first().getAttribute('value'),'__all__');assert.equal(await page.locator('[data-item-id="generic-unit:Spearman"]').count(),1);assert.equal(await page.locator('[data-item-id="generic-unit:Battering Ram"]').count(),1);assert.equal(await page.locator('aside a[data-page="unit-tiers"]').count(),1);assert.equal(await page.locator('aside a[data-page="winrates"]').count(),0);await tab('civilizations');await page.locator('.wr-board').first().waitFor();assert.equal(await page.locator('aside a[data-page="unit-tiers"]').getAttribute('aria-current'),'page');await tab('units');
 for(const category of ['units','technologies','buildings']){
  await tab(category);assert.equal(await page.locator(`[data-tier-category="${category}"]`).getAttribute('aria-current'),'page');
  assert.ok(await page.locator('.unit-tier-card').count()>0,category+' cards');
  await page.locator('.unit-tier-evidence summary').first().click();assert.match(await page.locator('.unit-tier-evidence').first().innerText(),/[Ww]in(?: rate)?:/);
  assert.match(await page.locator('.unit-tier-evidence').first().innerText(),/Usage:/);
  const shown=await page.locator('.unit-tier-card').first().getAttribute('data-item-id');
  const item=await page.evaluate(({category,shown})=>window.UNIT_USAGE_TIERS.cohorts.find(c=>c.category===category&&(c.rankBand||'all')===tierRankState.rank&&c.civilization===document.querySelector('#unit-tier-civ').value&&String(c.matchTypeId)===tierModeState.modes[0]).items.find(i=>i.id===shown),{category,shown});
  assert.equal(item.usedIn,item.wins+item.losses);assert.ok(Math.abs(item.winRate-(category==='units'?item.winWeight/(item.winWeight+item.lossWeight):item.wins/item.usedIn))<1e-10);if(category==='units'){await page.locator('details[data-share-games] summary').first().click();await page.locator('.unit-share-table table').first().waitFor();assert.equal(await page.locator('.unit-share-table tbody tr').count(),item.usedIn);assert.ok(item.averageShareWhenUsed>0);assert.match(await page.locator('.unit-tier-share').first().innerText(),/avg. share when used/);}assert.ok(Math.abs(item.usageRate-item.usedIn/item.eligiblePlayerGames)<1e-10);
  assert.equal(await page.locator('.unit-tier-frequency b').first().innerText(),`${(item.winRate*100).toFixed(1)}%`);
  assert.ok((await page.locator('.unit-tier-outcomes').first().innerText()).includes(`${item.losses} L`));
  assert.ok((await page.locator('.unit-tier-usage').first().innerText()).includes(`${(item.usageRate*100).toFixed(1)}% usage`));
  
  if(category==='buildings'){assert.equal(await page.locator('[data-item-id="generic-keep"]').count(),1);assert.equal(await page.locator('[data-item-id="generic-tc-2"]').count(),1);assert.equal(await page.locator('[data-item-id="generic-tc-3"]').count(),1);}
  if(category==='technologies'){
   const generic=await page.locator('.unit-tier-civ-label').allTextContents();assert.ok(generic.includes('Generic'),'Generic upgrades identified');
  }
  checks.push(category+' category and displayed calculation');
 }
 await tab('units');
 for(const modes of [['1'],['1','2'],['1','3'],['1','2','3','4']]){
  await setModes(modes);
  const expected=await page.evaluate(()=>{
   const cohorts=window.UNIT_USAGE_TIERS.cohorts.filter(c=>c.category==='units'&&(c.rankBand||'all')===tierRankState.rank&&c.civilization==='__all__'&&tierModeState.modes.includes(String(c.matchTypeId)));
   const items=cohorts.map(c=>c.items.find(i=>i.id==='generic-unit:Spearman')).filter(Boolean),wins=items.reduce((s,i)=>s+i.winWeight,0),losses=items.reduce((s,i)=>s+i.lossWeight,0),used=items.reduce((s,i)=>s+i.usedIn,0),eligible=items.reduce((s,i)=>s+i.eligiblePlayerGames,0);
   return {rate:wins/(wins+losses),share:(wins+losses)/used,usage:used/eligible};
  });
  const card=page.locator('[data-item-id="generic-unit:Spearman"]');assert.equal(await card.locator('.unit-tier-frequency b').innerText(),`${(expected.rate*100).toFixed(1)}%`);assert.ok((await card.locator('.unit-tier-share').innerText()).includes(`${(expected.share*100).toFixed(1)}%`));assert.ok((await card.locator('.unit-tier-usage').innerText()).includes(`${(expected.usage*100).toFixed(1)}%`));
  await tab('civilizations');assert.equal(await page.locator('.wr-board').count(),1);
  const expectedGames=await page.evaluate(()=>tierModeState.modes.reduce((sum,id)=>sum+(WINRATES.ranks[wrBand().id].modes[{'1':'solo','2':'2v2','3':'3v3','4':'4v4'}[id]]?.games||0),0));
  assert.ok((await page.locator('.wr-board .panel-head').innerText()).includes(expectedGames.toLocaleString('en-US')));
  await tab('units');
 }
 const ratingBands=await page.locator('#tier-rank option').evaluateAll(es=>es.map(e=>e.value));
 for(const band of ratingBands){
  await page.locator('#tier-rank').selectOption(band,{force:true});
  const expectedMatches=await page.evaluate(()=>window.UNIT_USAGE_TIERS.cohorts.filter(c=>c.category==='units'&&c.civilization==='__all__'&&(c.rankBand||'all')===tierRankState.rank&&tierModeState.modes.includes(String(c.matchTypeId))).reduce((n,c)=>n+c.games,0));
  assert.ok((await page.locator('.unit-tier-sample').innerText()).includes(`${expectedMatches} matches`));
  await tab('civilizations');assert.equal(await page.locator('#tier-rank').inputValue(),band);assert.equal(await page.locator('.wr-board').count(),1);await tab('units');assert.equal(await page.locator('#tier-rank').inputValue(),band);
 }
 await page.locator('#tier-rank').selectOption('all',{force:true});
 await setModes(['4']);checks.push('Arbitrary mode subsets aggregate raw contributions and persist across item/civilization tabs; civilization board stays one column');
 await tab('buildings');
 await page.locator('#unit-tier-query').fill('House of Wisdom');assert.ok(await page.locator('.unit-tier-card').count()>0);
 await page.locator('#unit-tier-query').fill('no-such-item-987');assert.equal(await page.locator('.unit-tier-card').count(),0);await page.locator('#unit-tier-query').fill('');
 await tab('units');
 const civOptions=await page.locator('#unit-tier-civ option').evaluateAll(es=>es.map(e=>e.value));
 if(civOptions.includes('mongol_ha_gol')){await page.locator('#unit-tier-civ').selectOption('mongol_ha_gol',{force:true});await tab('buildings');assert.match(await page.locator('#unit-tier-results').innerText(),/Golden Tent/);}
 await page.locator('#unit-tier-civ').selectOption('abbasid',{force:true});await tab('units');
 for(const theme of ['dark','light']){
  await page.locator('#theme').selectOption(theme,{force:true});
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:1000});await page.evaluate(()=>scrollTo(0,0));
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'Rankings overflow');
   await page.screenshot({path:path.join(out,`rankings-${theme}-${width}.png`),animations:"disabled"});
   const scan=await new AxeBuilder({page}).include('.unit-tier-page').analyze();assert.deepEqual(scan.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)})),[]);
  }
 }
 assert.deepEqual(errors,[]);assert.deepEqual(failures,[]);
 fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify({checks,errors,failures,responsiveWidths:[1440,390],themes:['light','dark'],accessibility:'Axe scans of both new UI regions in all4 viewport/theme combinations'},null,2));
 await browser.close();console.log('Original player matrix and three item ranking categories passed calculation display, browser interactions, responsive/axe checks, and console/network checks.');
})().catch(e=>{console.error(e);process.exit(1)});
