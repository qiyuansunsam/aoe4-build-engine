// Library: Vikings and Scots 17.0 preview records appear only in the Next view, with evidence on the record page.
// Needs the server on 127.0.0.1:8765 and a fresh build (python -X utf8 site/build.py).
const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{const b=await chromium.launch(),ctx=await b.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
const out=path.join(__dirname,'shots/library-preview');fs.mkdirSync(out,{recursive:true});
const civOptions=()=>p.locator('#catalog-civ option').evaluateAll(o=>o.map(x=>x.value));
await p.goto('http://127.0.0.1:8765/#database',{waitUntil:'networkidle'});
await p.locator('#catalog-civ').waitFor({state:'attached'});
assert.equal(await p.locator('[data-catalog-patch="preview"]').first().getAttribute('aria-pressed'),'true','Library opens in Next');
assert.ok((await civOptions()).includes('vikings'),'Next (default) lists Vikings');
await p.locator('[data-catalog-patch="current"]').first().click();await p.locator('#catalog-civ').waitFor({state:'attached'});
assert.ok(!(await civOptions()).includes('vikings'),'Current view must not list Vikings');
await p.locator('[data-catalog-patch="preview"]').first().click();
await p.locator('#catalog-civ').waitFor({state:'attached'});
const opts=await civOptions();assert.ok(opts.includes('vikings')&&opts.includes('scots'),'Next view lists Vikings and Scots');
// Scots units sit under their production building: infantry Barracks, ranged Archery Range, siege Siege Workshop
await p.locator('#catalog-kind').selectOption('units',{force:true});await p.locator('#catalog-civ').selectOption('scots',{force:true});await p.locator('#catalog-kind').selectOption('units',{force:true});
await p.locator('#catalog-results .catalog-production-group').first().waitFor();
const groups=await p.locator('#catalog-results .catalog-production-group').evaluateAll(gs=>Object.fromEntries(gs.map(g=>[g.querySelector('h2 span').textContent,[...g.querySelectorAll('.catalog-object-link span')].map(s=>s.textContent)])));
for(const [bld,unit] of [['Barracks','Gallowglass'],['Barracks','Cateran'],['Barracks','Pikeman'],['Archery Range','Highland Archer'],['Archery Range','Tacksman'],['Siege Workshop','Siege Tower'],['Siege Workshop','Mangonel']])assert.ok((groups[bld]||[]).includes(unit),`${unit} under ${bld}: `+JSON.stringify(groups[bld]));
assert.ok(!groups['Other units'],'no Scots unit left in Other units: '+JSON.stringify(groups['Other units']));
await p.screenshot({path:path.join(out,'scots-units.png'),fullPage:true});
for(const [kind,must] of [['buildings',['Dark Age','Feudal Age','Landmarks']],['technologies',['Feudal Age','Castle Age','Imperial Age']]]){await p.locator('#catalog-kind').selectOption(kind,{force:true});await p.locator('#catalog-results .catalog-production-group').first().waitFor();
  const heads=await p.locator('#catalog-results .catalog-production-group h2 span').allTextContents();for(const h of must)assert.ok(heads.includes(h),`${kind} grouped by ${h}: `+heads.join(','));}
await p.screenshot({path:path.join(out,'scots-technologies.png'),fullPage:true});
await p.locator('#catalog-civ').selectOption('vikings',{force:true});
await p.locator('#catalog-kind').selectOption('units',{force:true});
await p.locator('#catalog-results .catalog-object-link').first().waitFor();
const vikText=await p.locator('#catalog-results').innerText();for(const n of ['Berserker','Bondi','Shield Maiden','Jylland Knight','Völur'])assert.ok(vikText.includes(n),'Vikings list shows '+n);
await p.screenshot({path:path.join(out,'vikings-units.png')});
await p.locator('#catalog-kind').selectOption('civilizations',{force:true});await p.locator('#catalog-civ').selectOption('',{force:true});
await p.locator('[data-civ-open="scots"]').waitFor();assert.match(await p.locator('[data-civ-open="scots"]').innerText(),/17\.0 preview/);
await p.goto('http://127.0.0.1:8765/#database/unit_berserker_1_vik',{waitUntil:'networkidle'});await p.reload({waitUntil:'networkidle'});
const rec=await p.locator('#page').innerText();
assert.match(rec,/Berserker/);assert.match(rec,/preview evidence/i);assert.match(rec,/Attack interval/);assert.match(rec,/Barracks/);assert.match(rec,/90/);
await p.screenshot({path:path.join(out,'berserker-record.png'),fullPage:true});
await p.goto('http://127.0.0.1:8765/#database/unit_gallowglass_3_sco',{waitUntil:'networkidle'});await p.reload({waitUntil:'networkidle'});
const gg=await p.locator('#page').innerText();for(const n of ['Bloomery','Damascus Steel','Fitted Leatherwork','Elite Army Tactics','Clan Traditions',"Lion's Duty","Wallace's Rally",'Upgrade to Elite Gallowglass'])assert.ok(gg.includes(n),'Gallowglass upgrades include '+n);
assert.ok(!gg.includes('Snaphance Locks'),'gunpowder tech must not attach to Gallowglass');
assert.ok(await p.locator('.catalog-upgrade-desc').count()>=10,'upgrades carry their descriptions');
await p.screenshot({path:path.join(out,'gallowglass-record.png'),fullPage:true});
await p.goto('http://127.0.0.1:8765/#database/building_unit_infantry_control_sco',{waitUntil:'networkidle'});await p.reload({waitUntil:'networkidle'});
assert.match(await p.locator('#page').innerText(),/Pikeman/);
await p.goto('http://127.0.0.1:8765/#database',{waitUntil:'networkidle'});await p.reload({waitUntil:'networkidle'});
await p.locator('[data-catalog-patch="current"]').first().click();
assert.ok(!(await civOptions()).includes('vikings'),'switching back to Current hides Vikings');
assert.deepEqual(errors,[],'no page errors: '+errors.join(' | '));
console.log('library preview ok',{vikingsShown:vikText.split('\n').length});await b.close();})().catch(e=>{console.error(e);process.exit(1);});
