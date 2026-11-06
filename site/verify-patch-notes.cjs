// Patch notes section: every line of data/patch-notes.json is rendered, hotfix sections come first, every reference
// links to an existing Library record and opens it, the civilization filter shows that civilization's section plus the
// lines elsewhere that concern it (also for civilizations with no section of their own), search narrows the lines,
// the Chinese layer covers the page chrome, and nothing overflows at 390 px.
// Run with the server up: node site/verify-patch-notes.cjs [--shots]
const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const shots=process.argv.includes('--shots'),shotDir=path.join(__dirname,'shots'),BASE='http://127.0.0.1:8765/';
(async()=>{const b=await chromium.launch(),ctx=await b.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
if(shots)fs.mkdirSync(shotDir,{recursive:true});
await p.addInitScript(()=>{try{if(!sessionStorage.getItem('pn-verify')){localStorage.removeItem('aoe-crafter-lang');localStorage.removeItem('aoe-crafter-civ-notes-open');sessionStorage.setItem('pn-verify','1');}}catch{}});
await p.goto(BASE+'#notes',{waitUntil:'networkidle'});await p.waitForSelector('.pn-section');
const data=await p.evaluate(()=>PATCH_NOTES),ids=await p.evaluate(()=>[...GAME_CATALOG.units,...GAME_CATALOG.buildings,...GAME_CATALOG.technologies].map(r=>r.id));
const count=items=>items.reduce((n,i)=>n+1+count(i.children||[]),0),total=data.sections.reduce((n,s)=>n+s.groups.reduce((m,g)=>m+g.blocks.reduce((k,x)=>k+count(x.items||[]),0),0),0);
assert.equal(await p.title(),'Patch notes · Mathmatically Correct AoE 4');assert.equal(await p.locator('nav [data-page="notes"][aria-current="page"]').count(),1,'sidebar marks Patch notes');
assert.equal(await p.locator('.pn-body li').count(),total,'every line of the notes is rendered');assert.equal(total,data.counts.items);
const titles=await p.locator('.pn-section h2').allTextContents();assert.ok(/^Update 17\.0\.12260/.test(titles[0])&&/^Update 17\.0\.12182/.test(titles[1]),'hotfix sections first, newest on top: '+titles.slice(0,3).join(' | '));
assert.equal(titles.length,data.sections.length);
const refs=await p.evaluate(()=>[...document.querySelectorAll('.pn-ref')].map(a=>({id:decodeURIComponent(a.getAttribute('href').replace('#database/','')),icon:!!a.querySelector('img.game-icon'),text:a.textContent})));
assert.equal(refs.length,data.counts.references,'every reference is a link');const known=new Set(ids);for(const r of refs)assert.ok(known.has(r.id),`reference ${r.text} points at a catalog record (${r.id})`);
const withIcon=refs.filter(r=>r.icon).length;assert.ok(withIcon/refs.length>.8,`most references carry their game icon (${withIcon}/${refs.length})`);
assert.ok(await p.locator('.pn-change').count()>40,'numeric changes are set apart');
assert.equal(await p.locator('.pn-civ-group').count(),data.sections.flatMap(s=>s.groups).filter(g=>g.civ).length,'one block per civilization section');
if(shots)await p.screenshot({path:path.join(shotDir,'patch-notes-dark.png'),fullPage:true});
// a reference opens the record's Library page
const first=refs.find(r=>r.icon);await p.locator(`.pn-ref[href="#database/${first.id}"]`).first().click();await p.waitForSelector('.record-toolbar, .catalog-record, .catalog-section');
assert.ok((await p.evaluate(()=>location.hash)).startsWith('#database/'+first.id),'reference navigates to the record');await p.goBack();await p.waitForSelector('.pn-section');
// civilization filter: own section plus lines elsewhere that concern it
const concerns=(civ)=>{const walk=i=>(i.civs||[]).includes(civ)||(i.children||[]).some(walk);let own=0,other=0;for(const s of data.sections)for(const g of s.groups)for(const x of g.blocks)for(const i of x.items||[]){if(g.civ===civ)own+=1+count(i.children||[]);else if(walk(i))other+=1+count(i.children||[]);}return {own,other};};
for(const civ of ['byzantine_ha_mac','vikings']){await p.goto(BASE+'#notes/'+civ,{waitUntil:'networkidle'});await p.waitForSelector('.pn-section');const want=concerns(civ);
  assert.equal(await p.evaluate(()=>document.querySelector('#pn-civ').value),civ);assert.equal(await p.locator('.pn-body li').count(),want.own+want.other,`${civ}: own ${want.own} + elsewhere ${want.other} lines`);assert.ok(want.own+want.other>0,`${civ} has notes`);}
assert.equal(concerns('vikings').own,0,'Vikings have no section of their own in the notes');
if(shots)await p.screenshot({path:path.join(shotDir,'patch-notes-civ-dark.png'),fullPage:true});
// search
await p.goto(BASE+'#notes',{waitUntil:'networkidle'});await p.fill('#pn-search','longhouse');await p.waitForFunction(()=>document.querySelectorAll('.pn-body li').length<40);
const found=await p.locator('.pn-body>ul>li').allTextContents();assert.ok(found.length>3&&found.every(t=>/longhouse/i.test(t)),'search keeps matching lines only');
assert.equal(await p.evaluate(()=>document.activeElement.id),'pn-search','search keeps focus while typing');await p.fill('#pn-search','');
// the Library's overview links here with the civilization chosen (site/verify-patch-changes.cjs covers the overview)
await p.goto(BASE+'#database',{waitUntil:'networkidle'});await p.evaluate(()=>{const s=document.querySelector('#catalog-civ');s.value='byzantine_ha_mac';s.dispatchEvent(new Event('change',{bubbles:true}));});await p.waitForSelector('#lib-changes .pn-source');
assert.equal(await p.locator('#lib-changes .pn-source').getAttribute('href'),'#notes/byzantine_ha_mac','Library links to the civilization\'s patch notes');
// Chinese layer: page chrome translates, the article's own text stays as published
await p.goto(BASE+'#notes',{waitUntil:'networkidle'});await p.click('#lang-toggle');await p.waitForFunction(()=>document.querySelector('nav [data-page="games"]').textContent.includes('\u5bf9\u5c40'));await p.waitForSelector('.pn-section');
const zh=await p.evaluate(()=>[...document.querySelectorAll('nav [data-page="notes"],.pn-head h2,.pn-head .meta,.pn-source,.pn-filter label,.pn-count,.pn-civ-title a')].map(e=>(e.childNodes[0]?.nodeType===3?e.childNodes[0].data:e.textContent).trim()).filter(Boolean));
const latin=[...new Set(zh.filter(t=>/[A-Za-z]{3}/.test(t)))];assert.deepEqual(latin,[],'Patch notes chrome translated: '+latin.join(' | '));
assert.ok(/Town Center construction time increased/.test(await p.locator('#pn-content').textContent()),'article text is left as published');
if(shots)await p.screenshot({path:path.join(shotDir,'patch-notes-zh.png')});
await p.click('#lang-toggle');await p.waitForFunction(()=>document.documentElement.lang==='en');
// light theme and narrow screen
await p.evaluate(()=>{const s=document.querySelector('#theme');s.value='light';s.dispatchEvent(new Event('change',{bubbles:true}));});if(shots){await p.waitForTimeout(300);await p.screenshot({path:path.join(shotDir,'patch-notes-light.png')});}
await p.evaluate(()=>{const s=document.querySelector('#theme');s.value='dark';s.dispatchEvent(new Event('change',{bubbles:true}));});
await p.setViewportSize({width:390,height:844});await p.goto(BASE+'#notes',{waitUntil:'networkidle'});await p.waitForSelector('.pn-section');
assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'no horizontal overflow at 390 px');
if(shots)await p.screenshot({path:path.join(shotDir,'patch-notes-narrow.png')});
assert.deepEqual(errors,[],'no page errors');
console.log(JSON.stringify({lines:total,references:refs.length,withIcon,sections:titles.length},null,1));console.log('patch notes verified');await b.close();})().catch(e=>{console.error(e);process.exit(1);});
