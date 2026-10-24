const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const {AxeBuilder}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/@axe-core/playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.join(__dirname,'shots/v2');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch(),context=await browser.newContext({viewport:{width:1440,height:900}}),page=await context.newPage();
 const report={errors:[],requests:[],renders:[],accessibility:[],loadMs:0};
 page.on('pageerror',e=>report.errors.push(e.message));page.on('response',r=>{if(r.status()>=400)report.requests.push({url:r.url(),status:r.status()})});
 const start=Date.now();await page.goto('http://127.0.0.1:8765/#workspace',{waitUntil:'networkidle'});await page.locator('#overview-chart > svg').waitFor();report.loadMs=Date.now()-start;
 assert.equal(await page.locator('dialog[open]').count(),0,'Ordinary navigation must not use modal dialogs');
 for(const theme of ['light','dark']){
  await page.locator('#theme').selectOption(theme,{force:true});
  for(const route of ['workspace','builds','games','database','ai','model']){
   if(route==='database'){await page.evaluate(()=>location.hash='#database');}else await page.locator(`nav [data-page="${route}"]`).click();await page.waitForFunction(r=>location.hash==='#'+r&&document.querySelector('nav [aria-current="page"]')?.dataset.page===r&&document.title.startsWith(({workspace:'Comparison',builds:'Build library',games:'Games',database:'Library',ai:'Crafter',model:'Guide'})[r]),route);
   await page.screenshot({path:path.join(out,`${route}-${theme}-1440.png`),fullPage:true});
   await page.evaluate(()=>Promise.all(document.getAnimations().map(a=>a.finished.catch(()=>{}))));
   const a=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
   report.accessibility.push({route,theme,violations:a.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,`${route}/${theme} desktop overflow`);
  }
  await page.locator('nav [data-page="workspace"]').click();
  for(const [width,height] of [[1920,1080],[390,844]]){
   await page.setViewportSize({width,height});await page.waitForFunction(()=>{const h=document.querySelector('#overview-chart'),s=h?.querySelector('svg');return s&&Math.abs(s.viewBox.baseVal.width-Math.max(280,h.clientWidth))<2});
   await page.screenshot({path:path.join(out,`workspace-${theme}-${width}.png`),fullPage:true});
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);report.renders.push({theme,width,height,overflow});assert.equal(overflow,false);
  }
  await page.setViewportSize({width:1440,height:900});
 }
 await page.reload({waitUntil:'networkidle'});assert.equal(await page.locator('html').getAttribute('data-theme'),'dark','Theme persists after reload');
 fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));await browser.close();console.log(JSON.stringify(report,null,2));
 assert.equal(report.errors.length,0);assert.equal(report.requests.length,0);assert.equal(report.accessibility.flatMap(a=>a.violations).length,0);
})().catch(e=>{console.error(e);process.exit(1)});
