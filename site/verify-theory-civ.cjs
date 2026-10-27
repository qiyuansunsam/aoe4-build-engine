// Non-Abbasid theory plans: each opens beside its reference game (Vikings/Scots 17.0-preview plans have none and open beside
// the other plan of their civilization), every comparison metric and detail panel renders from the engine-civs.js run, and
// the build page lists its actions. Run with the server up: node site/verify-theory-civ.cjs
const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
(async()=>{const b=await chromium.launch(),ctx=await b.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.addInitScript(()=>{try{localStorage.removeItem('aoe-crafter-v2');localStorage.removeItem('aoe-crafter-lang');}catch{}});
await p.goto('http://127.0.0.1:8765/#builds',{waitUntil:'networkidle'});
const plans=await p.evaluate(()=>theory.filter(t=>t.engine==='civ').map(t=>({id:t.id,civ:t.civilization,ref:!!t.reference?.buildId}))),ids=plans.map(x=>x.id),withRef=plans.filter(x=>x.ref).length;
assert.ok(ids.length>=5,'civilization theory plans');for(const civ of ['vikings','scots'])assert.ok(plans.filter(x=>x.civ===civ).length>=2,`${civ} plans`);
assert.equal(await p.locator('[data-compare-reference]').count(),withRef,'each plan with a reference game offers its comparison');
const report=[];
for(const {id,civ,ref} of plans){const pair=ref?null:plans.find(x=>x.civ===civ&&x.id!==id).id;await p.evaluate(async ([id,pair])=>{if(!pair){await compareWithReference(id);return;}state.slots=[{kind:'theory',id},{kind:'theory',id:pair}];selection=null;recalculate();location.hash='workspace';},[id,pair]);await p.waitForSelector('#object-detail');const r=await p.evaluate(async id=>{state.time=Math.min(900,maxTime());drawWorkspace();const a=runs[0],o=runs[1],ma=snapshot(a),mo=snapshot(o);
  const vals=k=>[metrics[k].get(a,ma),metrics[k].get(o,mo)];const out={id,engine:a.engine,ref:o.kind,end:runEndCondition(a).label,metrics:Object.fromEntries(['population','villagers','army','income','bank','gathered','spent','technologies','military'].map(k=>[k,vals(k)]))};
  const panels={};for(const mode of ['units','army','resources','research']){detailMode=mode;selection=null;drawDetail();panels[mode]=document.querySelector('#object-detail')?.textContent.length||0;}
  const tech=a.events.find(e=>e.kind==='done'&&e.tech);if(tech){state.time=Math.max(state.time,tech.t);detailMode='selection';selection={type:'tech',name:tech.tech,path:0,event:tech};drawDetail();panels.tech=document.querySelector('#object-detail')?.textContent||'';}
  return {...out,panels,techTitle:tech?.label};},id);
  for(const k of ['population','villagers','army','income','technologies'])assert.ok(Number.isFinite(r.metrics[k][0]),`${id} theory ${k}`);
  for(const mode of ['units','army','resources','research'])assert.ok(r.panels[mode]>40,`${id} ${mode} panel`);
  assert.ok(r.panels.tech&&r.panels.tech.includes('Research starts'),`${id} technology detail`);
  assert.equal(r.engine,'civ');assert.equal(r.ref,ref?'observed':'theory');report.push({...r,panels:{...r.panels,tech:r.techTitle}});}
await p.evaluate(()=>{state.time=900;drawWorkspace();});await p.screenshot({path:'site/shots/theory-civ-comparison.png'});
for(const id of ids){await p.goto('http://127.0.0.1:8765/#builds/'+id,{waitUntil:'networkidle'});await p.waitForSelector('#build-order-list');const rows=await p.locator('#build-order-list > *').count();assert.ok(rows>3,`${id} build page actions`);}
await p.screenshot({path:'site/shots/theory-civ-build-page.png'});
fs.writeFileSync('site/shots/theory-civ-report.json',JSON.stringify({errors,report},null,1));
assert.deepEqual(errors,[]);console.log('Theory civilization plans verified:',report.map(r=>`${r.id} pop ${r.metrics.population.join('/')} army ${r.metrics.army.join('/')}`).join('; '));await b.close();})().catch(e=>{console.error(e);process.exit(1);});
