// Comparison unit panel: an upgrade tile's name opens that technology's Library page; a click anywhere else on the tile
// applies the upgrade to the unit's stats (tier upgrades swap in the next tier's record, other upgrades add the stat
// changes their own description states). Builds: Saved and Drafts sections with Save / Move to draft; a plan links to
// its reference game and that game carries a Referenced build tag back to the plan; games have no crafting or review.
// Needs the server on 127.0.0.1:8765 and a fresh build (python -X utf8 site/build.py).
const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch(),ctx=await b.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.goto('http://127.0.0.1:8765/#workspace',{waitUntil:'networkidle'});
// description parser: unconditional stat changes only
const fx=await p.evaluate(()=>Object.fromEntries(['upgrade_landmark_siege_works','upgrade_long_spear_jpn','upgrade_marudo_armor_jpn','upgrade_shrine_rituals_jpn','upgrade_siege_works_improved_mon','upgrade_cavalry_chivalry_fre','upgrade_landmark_siege_chemistry','upgrade_smithy_damage_1_vik','upgrade_loom_armor_2_vik','upgrade_mameluke_damage_abb','upgrade_cavalry_bloodline_fre'].map(id=>{const t=catalog.find(x=>x.id===id);return [id,t?{text:observedTechDescription(t),fx:techStatEffects(observedTechDescription(t))}:null];})));
const eff=id=>fx[id].fx.map(e=>`${e.type}${e.channel?':'+e.channel:''}${e.value>0?'+':''}${e.value}${e.pct?'%':''}`).join(',');
assert.match(fx.upgrade_landmark_siege_works.text,/\+20% and their ranged armor by \+10\./,'template arguments filled: '+fx.upgrade_landmark_siege_works.text);
assert.equal(eff('upgrade_landmark_siege_works'),'health+20%,armor:Ranged+10');
assert.equal(eff('upgrade_long_spear_jpn'),'range+20%','damage against cavalry is conditional');
assert.equal(eff('upgrade_marudo_armor_jpn'),'','"while Deflective Armor is active" is conditional');
assert.equal(eff('upgrade_shrine_rituals_jpn'),'health+40,speed+15%');
assert.equal(eff('upgrade_siege_works_improved_mon'),'health+30%','the "If ... instead" sentence is skipped');
assert.equal(eff('upgrade_cavalry_chivalry_fre'),'');assert.equal(eff('upgrade_landmark_siege_chemistry'),'','bonus damage is not base damage');
assert.equal(eff('upgrade_smithy_damage_1_vik'),'damage+1');assert.equal(eff('upgrade_loom_armor_2_vik'),'armor:Melee+1,armor:Ranged+1');
assert.equal(eff('upgrade_mameluke_damage_abb'),'','attack speed has no base stat to change');assert.equal(eff('upgrade_cavalry_bloodline_fre'),'health+35%');
// Royal Knight in the recorded French game at 15:00
await p.evaluate(async()=>{await applyBuild('observed:french-observed-4v4',0);state.time=900;selectObject('metric','army',0);});
await p.locator('[data-army-unit]').filter({hasText:'Royal Knight'}).first().click();
const statsText=()=>p.locator('#army-unit-panel .stats').first().textContent(),num=(s,label)=>Number((s.match(new RegExp(label+'(-?[\\d.]+)'))||[])[1]);
const unitId=await p.locator('#army-unit-panel [data-observed-unit]').first().getAttribute('data-observed-unit');
const tiers=await p.evaluate(id=>{const r=catalog.find(x=>x.id===id),tr=(r.tierTransitions||[]).at(-1),e=tr&&catalog.find(x=>x.id===tr.squad);return {upgrade:tr?.upgrade,hp:[r.hp,e?.hp],melee:[r.armor.Melee,e?.armor.Melee]};},unitId);
assert.ok(tiers.upgrade,'recorded Royal Knight has a higher tier: '+unitId);
const before=await statsText(),hit=p.locator(`#army-unit-panel [data-observed-tech="${tiers.upgrade}"]`).first();
assert.equal(await hit.getAttribute('aria-pressed'),'false','tier upgrade not yet researched at 15:00');
const tile=p.locator(`#army-unit-panel .upgrade-tile:has([data-observed-tech="${tiers.upgrade}"])`).first();await tile.scrollIntoViewIfNeeded();const box=await tile.boundingBox(),title=await tile.locator('.upgrade-title').boundingBox();
await p.mouse.click(box.x+box.width-12,box.y+box.height-8);   // the tile's corner, away from the name
assert.equal(await hit.getAttribute('aria-pressed'),'true','one click on the tile applies the upgrade');
const after=await statsText();
assert.equal(num(after,'Health')-num(before,'Health'),tiers.hp[1]-tiers.hp[0],'tier upgrade swaps in the next tier health: '+after);
assert.equal(num(after,'Melee armor')-num(before,'Melee armor'),tiers.melee[1]-tiers.melee[0],'tier upgrade swaps in the next tier armor');
assert.equal(new URL(p.url()).hash,'#workspace','tile click stays on the comparison');
assert.ok(title.width<box.width,'title is a link inside the tile');
const link=tile.locator('.upgrade-title');assert.equal(await link.getAttribute('href'),'#database/'+tiers.upgrade);
await link.click();await p.locator('.database-record').waitFor();assert.equal(new URL(p.url()).hash,'#database/'+tiers.upgrade,'title opens the technology page');
// Builds: Saved and Drafts (pending review); engine-crafted plans start as drafts; Save / Move to draft persist
await p.goto('http://127.0.0.1:8765/#builds',{waitUntil:'networkidle'});await p.locator('#draft-results .build-item').first().waitFor();
const ids=await p.evaluate(()=>({civ:theory.filter(t=>t.engine==='civ').map(t=>t.id),other:theory.filter(t=>t.engine!=='civ').map(t=>t.id)}));
const section=sel=>p.locator(sel+' .build-item h2 a').evaluateAll(as=>as.map(a=>decodeURIComponent(a.getAttribute('href').replace('#builds/',''))));
assert.deepEqual((await section('#draft-results')).sort(),ids.civ.slice().sort(),'engine-crafted plans start in Drafts');
assert.deepEqual((await section('#build-results')).sort(),ids.other.slice().sort(),'Abbasid plans are Saved');
assert.equal(await p.locator('#build-filter').count(),0,'no Type filter');
assert.equal(await p.locator('#build-results .badge.build-status.saved').count(),ids.other.length,'Saved tags');
assert.equal(await p.locator('#draft-results .badge.build-status.draft').count(),ids.civ.length,'Draft tags');
assert.equal(await p.locator('#build-results, #draft-results').getByText('Theory plan',{exact:true}).count(),0,'no Theory plan tag');
const colors=await p.evaluate(()=>[getComputedStyle(document.querySelector('#build-results .build-status.saved')).color,getComputedStyle(document.querySelector('#draft-results .build-status.draft')).color]);
assert.notEqual(colors[0],colors[1],'Saved and Draft tags differ in colour: '+colors.join(' vs '));
assert.equal(await p.locator('[data-compare-reference]').count(),await p.evaluate(()=>theory.filter(t=>t.engine==='civ'&&t.reference?.buildId).length),'plans with a reference game keep Compare with reference (Vikings/Scots preview plans have none)');
const first=ids.civ[0];
await p.locator(`[data-build-status="${first}"]`).click();
assert.ok((await section('#build-results')).includes(first),'Save moves the draft to Saved');
await p.reload({waitUntil:'networkidle'});await p.locator('#build-results .build-item').first().waitFor();
assert.ok((await section('#build-results')).includes(first),'status persists across reloads');
await p.locator(`[data-build-status="${first}"]`).click();
assert.ok((await section('#draft-results')).includes(first),'Move to draft moves it back');
// plan -> its reference game -> Referenced build tag -> plan
const refLink=p.locator(`#draft-results .build-item:has(a[href="#builds/${first}"]) a.reference-note`);
assert.match(await refLink.getAttribute('href'),/^#games\//,'reference note links to the game');
await refLink.click();await p.locator('.game-detail-panel').waitFor();
const tag=p.locator(`.game-detail-teams a.referenced-build[href="#builds/${first}"]`);
await tag.first().waitFor();assert.equal(await tag.count(),1,'the referenced player carries a Referenced build tag');
assert.equal(await p.getByText('Analyze & craft').count(),0,'no crafting on game pages');
await tag.click();await p.locator('#build-order-list').waitFor();assert.equal(new URL(p.url()).hash,'#builds/'+first,'tag opens the build');
assert.equal(await p.locator('.record-identity .badge.build-status.draft').count(),1,'build page shows its Draft tag');
// Games list: Referenced by a build
await p.goto('http://127.0.0.1:8765/#games',{waitUntil:'networkidle'});await p.locator('#game-status').waitFor({state:'attached'});
const statusOptions=await p.locator('#game-status option').allTextContents();
assert.ok(statusOptions.includes('Referenced by a build')&&!statusOptions.some(o=>/Pending review|Build crafted/.test(o)),'status filter: '+statusOptions.join(','));
await p.locator('#game-status').selectOption('referenced',{force:true});await p.locator('#game-results .game-match').first().waitFor();
const refCards=await p.locator('#game-results .game-match').count(),refTags=await p.locator('#game-results a.referenced-build').count();
assert.ok(refCards>0&&refTags>=refCards,`referenced games carry tags (${refCards} games, ${refTags} tags)`);
assert.deepEqual(errors,[],'no page errors: '+errors.join(' | '));
console.log('unit upgrades + builds ok:',unitId,tiers.upgrade,'hp',tiers.hp.join('→'));await b.close();})().catch(e=>{console.error(e);process.exit(1);});
