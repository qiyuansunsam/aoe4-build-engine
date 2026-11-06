// Library change overview and record pages: the overview on top of the Library lists what the installed files changed
// (shared changes and a count per civilization with none chosen; the chosen civilization's changed records otherwise,
// brief first, all on request); every value equals data/patch-changes.json and the current value equals the catalog
// record the page shows; a changed record's page has a "Changed in" block, a new record says so, an unchanged record
// has no block; the old notes overlay is gone from record pages. zh and 390 px.
// Run with the server up: node site/verify-patch-changes.cjs [--shots]
const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const shots=process.argv.includes('--shots'),shotDir=path.join(__dirname,'shots'),BASE='http://127.0.0.1:8765/';
(async()=>{const b=await chromium.launch(),ctx=await b.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
if(shots)fs.mkdirSync(shotDir,{recursive:true});
await p.addInitScript(()=>{try{if(!sessionStorage.getItem('pc-verify')){localStorage.removeItem('aoe-crafter-lang');sessionStorage.setItem('pc-verify','1');}}catch{}});
await p.goto(BASE+'#database',{waitUntil:'networkidle'});await p.waitForSelector('#lib-changes');
const data=await p.evaluate(()=>PATCH_CHANGES),catalog=await p.evaluate(()=>Object.fromEntries([...GAME_CATALOG.units,...GAME_CATALOG.buildings,...GAME_CATALOG.technologies].map(r=>[r.id,{hp:r.hp,build:r.buildTimeSeconds,civ:r.civilization,name:r.name}])));
assert.equal(data.from.patch,'16.3.11308');assert.equal(data.to.patch,await p.evaluate(()=>GAME_CATALOG.provenance.patch),'changes end at the installed patch');
// ground truth: the "after" value of a health or build-time change is the value of the installed record
let checked=0;for(const [id,changes] of Object.entries(data.records))for(const c of changes){if(c.l==='Health'){assert.equal(c.n,catalog[id].hp,`${id} health is the installed value`);checked++;}if(c.l==='Build time (s)'){assert.equal(c.n,catalog[id].build,`${id} build time is the installed value`);checked++;}}
assert.ok(checked>60,'health and build-time changes checked against the catalog: '+checked);
for(const id of data.added)assert.ok(catalog[id],`new record ${id} is in the catalog`);
// no civilization chosen: shared changes and one button per civilization
const head=await p.locator('#lib-changes .pc-head').textContent();assert.ok(head.includes('Changes in 17.0')&&head.includes('16.3.11308 → '+data.to.patch),head);
assert.equal(await p.locator('#lib-changes .pc-row').count(),data.shared.length,'one row per shared change');
const tc=data.shared.find(s=>s.name==='Town Center');assert.ok(tc,'Town Center is a shared change');assert.ok((await p.locator('#lib-changes .pc-row',{hasText:'Town Center'}).textContent()).replace(/\s+/g,' ').includes('150 → 165'),'Town Center build time 150 → 165');
const civsWith=new Set([...data.families.map(f=>f.civ).filter(c=>c!=='common'),...Object.keys(data.newByCiv)]);assert.equal(await p.locator('.pc-civ').count(),civsWith.size,'one button per civilization with changes');
assert.ok(await p.evaluate(()=>document.querySelector('#lib-changes').compareDocumentPosition(document.querySelector('.catalog-browser'))&Node.DOCUMENT_POSITION_FOLLOWING),'overview sits above the roster');
if(shots)await p.screenshot({path:path.join(shotDir,'patch-changes-library-dark.png')});
// choosing a civilization from the overview
await p.click('[data-pc-civ="ottoman"]');await p.waitForFunction(()=>document.querySelector('#catalog-civ').value==='ottoman');
const fam=data.families.filter(f=>f.civ==='ottoman');assert.ok(fam.length>6);assert.equal(await p.locator('#lib-changes .pc-row').count(),6,'brief: six rows first');
await p.click('[data-pc-more]');assert.equal(await p.locator('#lib-changes .pc-row').count(),fam.length,'all rows on request');
const rows=await p.evaluate(()=>[...document.querySelectorAll('#lib-changes .pc-row')].map(a=>({id:decodeURIComponent(a.getAttribute('href').replace('#database/','')),name:a.querySelector('.pc-name b').textContent,chips:[...a.querySelectorAll('.pc-chip')].map(c=>c.textContent.replace(/\s+/g,' ').trim()),icon:!!a.querySelector('img.game-icon')})));
for(const [i,f] of fam.entries()){assert.equal(rows[i].id,f.id);assert.equal(rows[i].name,f.name);assert.equal(rows[i].chips.length,f.changes.length,`${f.name} chips`);for(const [j,c] of f.changes.entries())if(!c.t&&c.o!=null&&c.n!=null)assert.ok(rows[i].chips[j].includes(`${c.o} → ${c.n}`),`${f.name}: ${rows[i].chips[j]} shows ${c.o} → ${c.n}`);}
assert.ok(rows.filter(r=>r.icon).length>=rows.length-1,'rows carry game icons');
if(shots)await p.screenshot({path:path.join(shotDir,'patch-changes-civ-dark.png')});
// a new civilization
await p.evaluate(()=>{const s=document.querySelector('#catalog-civ');s.value='vikings';s.dispatchEvent(new Event('change',{bubbles:true}));});await p.waitForSelector('.pc-new');
const n=data.newByCiv.vikings;assert.ok((await p.locator('.pc-new').textContent()).includes(`${n.units} units, ${n.buildings} buildings, ${n.technologies} technologies`),'new civilization counts');
// record pages
const changed=fam.find(f=>f.kind==='building'&&f.changes.some(c=>c.l==='Cost · wood'));await p.goto(BASE+'#database/'+changed.id,{waitUntil:'networkidle'});await p.waitForSelector('.pc-record');
const block=(await p.locator('.pc-record').textContent()).replace(/\s+/g,' ');assert.ok(block.includes('Changed in 17.0'),block);for(const c of data.records[changed.id])if(!c.t&&c.o!=null&&c.n!=null)assert.ok(block.includes(`${c.o} → ${c.n}`),`${changed.id} block shows ${c.l} ${c.o} → ${c.n}`);
assert.equal(await p.locator('.catalog-patch-notes').count(),0,'the notes overlay block is gone from record pages');
if(shots)await p.screenshot({path:path.join(shotDir,'patch-changes-record-dark.png'),fullPage:true});
const unchanged=Object.keys(catalog).find(id=>!data.records[id]&&!data.added.includes(id)&&catalog[id].civ==='english'&&id.startsWith('unit_'));await p.goto(BASE+'#database/'+unchanged,{waitUntil:'networkidle'});await p.waitForSelector('.catalog-section, .record-toolbar');
assert.equal(await p.locator('.pc-record').count(),0,`unchanged record ${unchanged} has no change block`);assert.equal(await p.locator('.catalog-patch-notes').count(),0);
await p.goto(BASE+'#database/'+data.added.find(id=>id.startsWith('unit_')&&catalog[id].civ==='scots'),{waitUntil:'networkidle'});await p.waitForSelector('.pc-record');assert.ok((await p.locator('.pc-record').textContent()).includes('New in 17.0'),'new record says so');
// Chinese layer
await p.goto(BASE+'#database',{waitUntil:'networkidle'});await p.evaluate(()=>{const s=document.querySelector('#catalog-civ');s.value='ottoman';s.dispatchEvent(new Event('change',{bubbles:true}));});await p.waitForSelector('#lib-changes .pc-row');
await p.click('#lang-toggle');await p.waitForFunction(()=>document.querySelector('nav [data-page="games"]').textContent.includes('\u5bf9\u5c40'));await p.waitForSelector('#lib-changes .pc-row');
const zh=await p.evaluate(()=>[...document.querySelectorAll('#lib-changes .pc-head h2,#lib-changes .pc-head .meta,#lib-changes .pn-source,#lib-changes .pc-name b,#lib-changes .pc-chip i:not([data-i18n-skip]),#lib-changes .pc-more')].map(e=>e.textContent.trim()).filter(Boolean));
const latin=[...new Set(zh.filter(t=>/[A-Za-z]{3}/.test(t)))];assert.deepEqual(latin,[],'overview text translated: '+latin.join(' | '));
if(shots)await p.screenshot({path:path.join(shotDir,'patch-changes-zh.png')});
await p.click('#lang-toggle');await p.waitForFunction(()=>document.documentElement.lang==='en');
// narrow screen
await p.setViewportSize({width:390,height:844});await p.goto(BASE+'#database',{waitUntil:'networkidle'});await p.waitForSelector('#lib-changes');
assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'no horizontal overflow at 390 px');
if(shots)await p.screenshot({path:path.join(shotDir,'patch-changes-narrow.png')});
assert.deepEqual(errors,[],'no page errors');
console.log(JSON.stringify({recordsChanged:Object.keys(data.records).length,recordsAdded:data.added.length,families:data.families.length,shared:data.shared.length,valuesCheckedAgainstCatalog:checked},null,1));console.log('patch changes verified');await b.close();})().catch(e=>{console.error(e);process.exit(1);});
