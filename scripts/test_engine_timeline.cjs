const assert = require('node:assert/strict');
const E = require('../site/engine');
const run = E.simulate();
assert.ok(run.done && run.done < 3600);
for (const source of ['wood', 'gold', 'stone', 'berries', 'deer', 'berriesFar']) {
  const completed = run.events.filter(e => e.kind === 'done' && e.source === source);
  assert.ok(completed.length, `${source} has a completed dropoff`);
  const ready = completed.at(-1).t;
  for (const e of run.events.filter(e => e.t < ready)) {
    const assigned = ['wood','gold','stone'].includes(source) ? e.split[source] : e.sources[source === 'berriesFar' ? 'farBerries' : source];
    assert.equal(assigned, 0, `${source} before completed dropoff at ${e.t}`);
  }
}
assert.equal(run.summary.buildings['mining-camp'], 2);
for (const event of run.events) {
  assert.equal(Object.values(event.split).reduce((a,b)=>a+b,0), event.vil, `worker conservation ${event.t}`);
  assert.ok(Object.values(event.stock).every(v=>Number.isFinite(v) && v>=0));
  assert.ok(Object.values(event.split).every(v=>v>=0));
  for (const r of ['food','wood','gold','stone']) assert.ok(Math.abs(event.stockBefore[r] - event.stock[r] - (event.cost[r] || 0)) <= 1);
}
for (const start of run.events.filter(e => e.kind === 'train')) {
  const end = run.events.find(e=>e.kind==='done' && e.cat==='unit' && e.producer===start.producer && e.queue===start.queue && e.t===start.readyAt);
  assert.ok(end, `training completion ${start.label} ${start.t}`);
  assert.equal(end.t-start.t,start.duration);
}
assert.equal(run.events.find(e=>e.kind==='train').vil,6, 'trainee cannot gather');
assert.equal(run.events.find(e=>e.kind==='done'&&e.label==='Villager').t,20);
assert.ok(run.events.some(e=>e.kind==='build'&&e.entity==='farm'));
assert.ok(run.events.some(e=>e.kind==='done'&&e.entity==='farm'));
for (const m of run.minutes) assert.equal(Object.values(m.split).reduce((a,b)=>a+b,0),m.vil);
const tc = E.simulate({tmax:20,map:{tcDistances:{gold:8,stone:8,wood:8,berries:8,deer:8}}});
assert.ok(tc.events.some(e=>e.t<20&&e.split.gold>0), 'explicit TC dropoff permits early mining');
assert.throws(()=>E.simulate({map:{tcDistances:{gold:-1}}}),RangeError);
const losses=E.simulate({tmax:600,villagerLossPerMinute:2,villagerLossStart:300});
assert.equal(losses.summary.villagersLost,9);
assert.equal(losses.events.find(e=>e.kind==='loss').t,330);
const input={tmax:60,map:{tcDistances:{gold:10}}}; const before=JSON.stringify(input); E.simulate(input); assert.equal(JSON.stringify(input),before);
console.log(`Dropoffs, worker conservation, training completions, construction events, costs, TC fallback, attrition and input purity passed (${run.events.length} events, done ${run.done}s).`);
