const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const {AxeBuilder}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/@axe-core/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch(),context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage(),errors=[],checks=[];
 page.on('pageerror',e=>errors.push(e.message));
 const out=path.join(__dirname,'shots/redesign');fs.mkdirSync(out,{recursive:true});
 await page.goto('http://127.0.0.1:8765/#workspace',{waitUntil:'networkidle'});
 const time=async n=>{await page.locator('#time-input').fill(String(n));await page.locator('#time-input').dispatchEvent('change');};
 const track=async key=>{if(!await page.locator(`[data-track-row="${key}"]`).count()){await page.locator('.tracking-menu summary').click();await page.locator(`[data-track="${key}"]`).check();}};
 const stat=async k=>Number(await page.locator(`[data-stat="${k}"] strong`).textContent());
 const near=(actual,expected)=>assert.ok(Math.abs(actual-expected)<.12,`${actual} ≈ ${expected}`);
 assert.equal(await page.locator('input[type=range]').count(),0);
 assert.equal(await page.locator('.slot-name,.slot-caption,.timeline-help,.page-foot,.rail-foot,.detail-tabs').count(),0);
 assert.equal(await page.locator('.comparison-main #object-detail').count(),1);
 assert.equal(await page.locator('.slot .select-trigger').count(),2);
 assert.ok(await page.locator('#overview-chart [data-event-path]').count()>0);
 await time(0);await page.locator('[data-track-row="villagers"][data-path="0"]').click();
 near(await stat('Gold / minute'),36.9863);near(await stat('Stone / minute'),36.9863);near(await stat('Wood / minute'),34.9693);
 await page.locator('.slot-strip').hover();
 const chart=await page.locator('#overview-chart > svg').innerHTML();
 await page.locator('[data-preview-tech="wheelbarrow"]').click();
 near(await stat('Gold / minute'),39.1378);near(await stat('Wood / minute'),37.8003);
 assert.equal(await page.locator('#overview-chart > svg').innerHTML(),chart,'What-if leaves actual graph unchanged');
 await page.locator('#clear-preview').click();
 await page.locator('[data-preview-tech="specialized-pick"]').click();near(await stat('Gold / minute'),41.6911);near(await stat('Stone / minute'),41.6911);
 await page.locator('[data-preview-tech="shaft-mining"]').click();near(await stat('Gold / minute'),46.8762);
 await page.locator('#clear-preview').click();near(await stat('Gold / minute'),36.9863);
 await page.locator('[data-track-row="camels"][data-path="0"]').click();assert.equal(await stat('Hit points'),270);
 await page.locator('[data-preview-tech="biology"]').click();assert.equal(await stat('Hit points'),338);
 await page.locator('[data-preview-tech="elite-camel-riders"]').click();assert.equal(await stat('Hit points'),400);
 await time(600);await page.locator('[data-track-row="income"][data-path="0"]').click();if(!await page.locator('.resource-card').count()){console.log(errors,await page.locator('#object-detail').innerText());await page.screenshot({path:'site/shots/redesign/failure.png',fullPage:true});}assert.equal(await page.locator('.resource-card').count(),4);assert.match(await page.locator('#object-detail').textContent(),/Gold.*Stone/s);
 await track('spent');await page.locator('[data-track-row="spent"][data-path="0"]').click();assert.equal(await page.locator('.resource-card').count(),4);assert.ok(await page.locator('.spending-distribution').count());
 await page.locator('[data-track-row="technologies"][data-path="0"]').click();assert.match(await page.locator('#object-detail').textContent(),/Wheelbarrow/);
 for(const key of ['bank','tcs','farms','technologies','gathered','army']){await page.locator('.tracking-menu summary').click();await page.locator(`[data-track="${key}"]`).check();if(await page.locator('.tracking-menu').getAttribute('open')!==null)await page.locator('.tracking-menu summary').click();}

 await page.locator('[data-event-path]').first().click();assert.ok(await page.locator('#object-detail h2').textContent());
 const cluster=page.locator('.graph-event-cluster').first();await cluster.locator('summary').click();assert.ok(await cluster.locator('[data-event-path]').first().isVisible());await cluster.locator('[data-event-path]').first().click();assert.ok(await page.locator('#object-detail h2').textContent());
 const picker=page.locator('.custom-select').filter({has:page.locator('#slot-0')}),trigger=picker.locator('.select-trigger');
 await trigger.click();await page.keyboard.press('Escape');assert.equal(await trigger.getAttribute('aria-expanded'),'false');assert.equal(await trigger.evaluate(e=>e===document.activeElement),true);
 await trigger.focus();await page.keyboard.press('ArrowDown');await page.keyboard.press('ArrowDown');await page.keyboard.press('End');await page.keyboard.press('Enter');
 assert.equal(await page.locator('#slot-0').inputValue(),'observed:japanese-observed-4v4');
 if(!await page.locator('#scenario-settings').evaluate(e=>e.open))await page.locator('#scenario-settings > summary').click();await page.locator('#reset').click();await page.locator('#scenario-settings > summary').click();await time(600);await page.locator('.slot-strip').click();
 assert.ok(await page.locator('#metric-picker option').count()>6);
 await page.locator('#metric-picker').selectOption('bank',{force:true});assert.equal(await page.locator('#metric-title').textContent(),'Resource bank');
 await page.locator('#metric-picker').selectOption('population',{force:true});
 
 assert.equal(await page.locator('#object-detail #detail-path,#object-detail .detail-nav,#object-detail .unit-picker').count(),0);
 await page.locator('[data-track-row="camels"][data-path="0"]').dragTo(page.locator('#object-detail'),{targetPosition:{x:100,y:40}});assert.match(await page.locator('#object-detail h2').textContent(),/Camel/);
 await page.locator('[data-track-row="income"][data-path="0"]').dragTo(page.locator('#object-detail'),{targetPosition:{x:100,y:40}});assert.equal(await page.locator('#object-detail .resource-card').count(),4);
 const beforeInvalid=await page.locator('#object-detail').innerHTML();
 await page.locator('#object-detail').evaluate(el=>{const dataTransfer=new DataTransfer();dataTransfer.setData('application/x-aoe-object',JSON.stringify({type:'unit',name:'not-a-unit',path:0}));el.dispatchEvent(new DragEvent('drop',{dataTransfer,bubbles:true}));});
 assert.equal(await page.locator('#object-detail').innerHTML(),beforeInvalid);
 await page.locator('[data-track-row="villagers"][data-path="0"]').click();await page.locator('.slot-strip').click();
 await page.locator('.compare-track[data-object-name="camel"] .metric-name').dragTo(page.locator('#object-detail'),{targetPosition:{x:100,y:40}});assert.match(await page.locator('#object-detail h2').textContent(),/Camel/);
 await page.locator('.compare-track[data-object-name="villager"] .metric-name').dragTo(page.locator('#object-detail'),{targetPosition:{x:100,y:40}});assert.match(await page.locator('#object-detail h2').textContent(),/Villager/);
 await page.locator('[data-track-row="villagers"][data-path="1"]').click();await page.locator('.compare-track[data-object-name="camel"] .metric-name').dragTo(page.locator('#object-detail'),{targetPosition:{x:100,y:40}});assert.equal(await page.locator('#object-detail').getAttribute('data-active-path'),'1','Label drag follows active build');
 await page.locator('[data-track-row="villagers"][data-path="0"]').dragTo(page.locator('#object-detail'),{targetPosition:{x:100,y:40}});assert.equal(await page.locator('#object-detail').getAttribute('data-active-path'),'0','Value drag keeps its own build');
 assert.equal(await page.locator('#graph-view').count(),0);assert.equal(await page.locator('#collapse-chart').count(),0);assert.equal((await page.locator('#overview-chart').boundingBox()).height,240);
 const selectedTime=await page.locator('#time-input').inputValue();
 
 await page.locator('.compare-track[data-object-name="camel"] .metric-name').dragTo(page.locator('#overview-chart'),{targetPosition:{x:150,y:40}});
 await page.locator('.slot-strip').hover();assert.equal(await page.locator('#metric-picker').inputValue(),'camels');assert.equal(await page.locator('#time-input').inputValue(),selectedTime);
 await track('goldIncome');await page.locator('.compare-track[data-track-metric="goldIncome"] .metric-name').dragTo(page.locator('#overview-chart'),{targetPosition:{x:150,y:100}});await page.locator('.slot-strip').hover();assert.equal(await page.locator('#metric-picker').inputValue(),'goldIncome');assert.equal(await page.locator('#metric-title').textContent(),'Gold income');
 await page.locator('.compare-track[data-track-metric="goldIncome"] .metric-name').dragTo(page.locator('#object-detail'),{targetPosition:{x:100,y:40}});assert.equal(await page.locator('#object-detail .resource-card').count(),4);assert.equal(await page.locator('#metric-picker').inputValue(),'goldIncome','Detail drop does not replace chart metric');
 await page.locator('#metric-picker').selectOption('population',{force:true});await page.locator('[data-track-row="villagers"][data-path="0"]').click();await page.locator('.slot-strip').hover();
 assert.equal(await page.locator('.workspace-actions,.rail-resources,.rail-research,.sidebar-objects,#detail-path').count(),0);assert.equal(await page.locator('.comparison-side #reset').count(),1);
 for(const theme of ['light','dark']){
  await page.locator('#theme').selectOption(theme,{force:true});
  for(const width of [1440,1920,390]){
   await page.setViewportSize({width,height:width===390?844:1000});await page.evaluate(()=>window.scrollTo(0,0));
   await page.waitForFunction(()=>{const h=document.querySelector('#overview-chart'),s=h.querySelector('svg');return Math.abs(s.viewBox.baseVal.width-Math.max(280,h.clientWidth))<2});
   await page.evaluate(()=>Promise.all(document.getAnimations().map(a=>a.finished.catch(()=>{}))));
   await page.screenshot({path:path.join(out,`workspace-${theme}-${width}.png`),fullPage:true});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
   if(width===390){const lastCluster=page.locator('.graph-event-cluster').last();await lastCluster.locator('summary').click();const menu=await lastCluster.locator('.event-cluster-menu').boundingBox();assert.ok(menu.x>=0&&menu.x+menu.width<=391,'Event dropdown stays within mobile viewport');assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);await lastCluster.locator('summary').click();}
   assert.equal(await page.locator('img').evaluateAll(imgs=>imgs.filter(i=>!i.complete||!i.naturalWidth).length),0);
   const scan=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();checks.push({theme,width,violations:scan.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))});
  }
 }
 const report={errors,checks};fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(report,null,2));await browser.close();console.log(JSON.stringify(report,null,2));assert.equal(errors.length,0);assert.equal(checks.flatMap(c=>c.violations).length,0);
})().catch(e=>{console.error(e);process.exit(1)});
