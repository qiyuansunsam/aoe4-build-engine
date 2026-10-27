// Library unit pages: an upgrade's name opens that technology; one click elsewhere on its row applies it to the unit's
// stats (same rules as the Comparison unit panel). Grouped grids use two balanced columns: the column heights differ
// by no more than one group. Saga Pillars list the seven Sagas.
// Needs the server on 127.0.0.1:8765 and a fresh build (python -X utf8 site/build.py).
const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch(),ctx=await b.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
const stats=()=>p.locator('.catalog-base-stats').textContent(),num=(s,label)=>Number((s.match(new RegExp(label+'(-?[\\d.]+)'))||[])[1]);
const balanced=async where=>{const r=await p.evaluate(()=>[...document.querySelectorAll('.masonry:not(.single)')].map(m=>{const cols=[...m.querySelectorAll(':scope>.masonry-col')],h=cols.map(c=>c.getBoundingClientRect().height),tallest=Math.max(...cols.flatMap(c=>[...c.children].map(x=>x.getBoundingClientRect().height)));return {cls:m.className,h,tallest};}));
  for(const g of r)assert.ok(Math.abs(g.h[0]-g.h[1])<=g.tallest+1,`${where}: columns ${g.h.map(Math.round).join(' vs ')} differ by more than the tallest group (${Math.round(g.tallest)}) in ${g.cls}`);return r.length;};
const applyRow=async id=>{const row=p.locator(`.catalog-upgrade-row:has([data-catalog-apply="${id}"])`).first();await row.scrollIntoViewIfNeeded();const box=await row.boundingBox();await p.mouse.click(box.x+box.width-10,box.y+box.height/2);await p.locator(`[data-catalog-apply="${id}"][aria-pressed="true"]`).first().waitFor();};
// installed unit: French Royal Knight
await p.goto('http://127.0.0.1:8765/#database/unit_knight_2_fre',{waitUntil:'networkidle'});await p.locator('.database-record').waitFor();
let s=await stats();assert.equal(num(s,'Health'),190,'base health: '+s);
await applyRow('upgrade_unit_knight_4_fre');s=await stats();
assert.equal(num(s,'Health'),270,'Upgrade to Elite applies the elite record: '+s);assert.match(s,/\+80 from 190/);
await applyRow('upgrade_melee_armor_i');s=await stats();assert.equal(num(s,'Melee armor'),6,'Fitted Leatherwork adds +1 on top of elite 5: '+s);
assert.equal(new URL(p.url()).hash,'#database/unit_knight_2_fre','row clicks stay on the unit page');
assert.ok(await balanced('Royal Knight upgrades')>0,'upgrade groups use balanced columns');
await p.locator('[data-catalog-apply-reset]').click();s=await stats();assert.equal(num(s,'Health'),190,'Reset preview restores the base');
const title=p.locator('.catalog-upgrade-row:has([data-catalog-apply="upgrade_melee_armor_i"]) a.upgrade-title').first();
await title.click();await p.locator('.database-record').waitFor();assert.equal(new URL(p.url()).hash,'#database/upgrade_melee_armor_i','the name opens the technology page');
// preview unit: Vikings Jylland Knight, Longhouse armor upgrade
await p.goto('http://127.0.0.1:8765/#database/unit_knight_3_vik',{waitUntil:'networkidle'});await p.locator('.database-record').waitFor();
const armorTech=await p.evaluate(()=>[...document.querySelectorAll('[data-catalog-apply]:not([disabled])')].map(b=>b.dataset.catalogApply).find(id=>/loom_armor_1/.test(id)));
assert.ok(armorTech,'Jylland Knight lists a Longhouse armor upgrade that applies');
const before=num(await stats(),'Ranged armor');await applyRow(armorTech);assert.equal(num(await stats(),'Ranged armor'),before+1,'Heavy Tunics adds +1 ranged armor');
// Saga Pillars
await p.goto('http://127.0.0.1:8765/#database/building_saga_totems_vik',{waitUntil:'networkidle'});await p.locator('.database-record').waitFor();
const sagas=await p.locator('.catalog-saga strong').allTextContents();
assert.deepEqual(sagas.slice().sort(),["Björn's Forage","Dreki's Temple","Falkr's Village","Hrafn's Raid","Jofurr's Hunt","Jörmungandr's Trade","Ulfr's Forester"].sort(),'seven Sagas: '+sagas.join(', '));
assert.match(await p.locator('.catalog-sagas').textContent(),/Goal.*Recruiting 25 infantry.*Reward.*\+5 torch damage/s);
// grouped Library lists stay balanced
await p.goto('http://127.0.0.1:8765/#database',{waitUntil:'networkidle'});await p.locator('#catalog-civ').waitFor({state:'attached'});
for(const [civ,kind] of [['english','units'],['french','units'],['vikings','units'],['vikings','buildings'],['english','technologies'],['scots','technologies']]){await p.locator('#catalog-civ').selectOption(civ,{force:true});await p.locator('#catalog-kind').selectOption(kind,{force:true});await p.locator('#catalog-results .catalog-production-group').first().waitFor();assert.ok(await balanced(`${civ} ${kind}`)>=0);}
assert.deepEqual(errors,[],'no page errors: '+errors.join(' | '));
console.log('library apply + balanced groups + sagas ok');await b.close();})().catch(e=>{console.error(e);process.exit(1);});
