// Library buildings page: Landmarks first (top left), Dark Age top right, Feudal Age under Landmarks; Town Center is
// Feudal (installed requirement_ext) for every civ including the 17.0 preview civs; same-name variants are one row;
// Mongol landmarks (wonder_age1-3 ids) count as Landmarks; back navigation restores the scroll position.
// Needs the server on 127.0.0.1:8765 and a fresh build (python -X utf8 site/build.py).
const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{const b=await chromium.launch(),ctx=await b.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
const out=path.join(__dirname,'shots/library-layout');fs.mkdirSync(out,{recursive:true});
const columns=()=>p.locator('#catalog-results .catalog-age-groups>.masonry-col').evaluateAll(cs=>cs.map(c=>[...c.querySelectorAll(':scope>section')].map(s=>s.querySelector('h2 span').textContent)));
const sectionOf=name=>p.locator('#catalog-results .catalog-production-group').evaluateAll((gs,name)=>gs.filter(g=>[...g.querySelectorAll('.catalog-object-link span')].some(s=>s.textContent===name)).map(g=>g.querySelector('h2 span').textContent),name);
const names=()=>p.locator('#catalog-results .catalog-family-main>.catalog-object-link span').allTextContents();
const show=async(civ,kind)=>{await p.locator('#catalog-civ').selectOption(civ,{force:true});await p.locator('#catalog-kind').selectOption(kind,{force:true});await p.locator('#catalog-results .catalog-production-group').first().waitFor();};
await p.goto('http://127.0.0.1:8765/#database',{waitUntil:'networkidle'});await p.locator('#catalog-civ').waitFor({state:'attached'});
for(const civ of ['vikings','scots','english','french','mongol','japanese']){await show(civ,'buildings');
  const cols=await columns(),n=await names();
  assert.deepEqual(await sectionOf('Town Center'),['Feudal Age'],`${civ}: Town Center sits in Feudal Age only`);
  assert.equal(n.length,new Set(n).size,`${civ}: one row per building name: `+n.join(','));
  assert.equal(cols[0][0],'Landmarks',`${civ}: Landmarks top left: `+JSON.stringify(cols));
  assert.equal(cols[1][0],'Dark Age',`${civ}: Dark Age top right: `+JSON.stringify(cols));
  assert.equal(cols[0][1],'Feudal Age',`${civ}: Feudal Age under Landmarks: `+JSON.stringify(cols));
  console.log(civ,JSON.stringify(cols));}
await show('mongol','buildings');for(const lm of ['Deer Stones','Kurultai','The Silver Tree','Khaganate Palace'])assert.deepEqual(await sectionOf(lm),['Landmarks'],'Mongol '+lm+' is a Landmark');
await show('vikings','buildings');await p.screenshot({path:path.join(out,'vikings-buildings.png'),fullPage:true});
// back navigation keeps the list position
await show('','technologies');await p.evaluate(()=>window.scrollTo(0,1500));await p.waitForTimeout(150);
const y0=await p.evaluate(()=>window.scrollY);assert.ok(y0>1000,'list is long enough to scroll: '+y0);
const link=p.locator('#catalog-results .catalog-family-main>.catalog-object-link').nth(25);
await link.scrollIntoViewIfNeeded();await p.waitForTimeout(150);const y1=await p.evaluate(()=>window.scrollY);
await link.click();await p.locator('.database-record').waitFor();
assert.ok(await p.evaluate(()=>window.scrollY)<5,'record page opens at the top');
await p.goBack();await p.locator('#catalog-results .catalog-production-group').first().waitFor();await p.waitForTimeout(200);
const y2=await p.evaluate(()=>window.scrollY);assert.ok(Math.abs(y2-y1)<4,`browser back restores ${y1}, got ${y2}`);
await link.click();await p.locator('#catalog-back').click();await p.locator('#catalog-results .catalog-production-group').first().waitFor();await p.waitForTimeout(200);
const y3=await p.evaluate(()=>window.scrollY);assert.ok(Math.abs(y3-y1)<4,`‹ Library restores ${y1}, got ${y3}`);
assert.deepEqual(errors,[],'no page errors: '+errors.join(' | '));
console.log('library layout ok');await b.close();})().catch(e=>{console.error(e);process.exit(1);});
