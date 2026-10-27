/* Invariants of the multi-civilization engine for every civilization in data/civ-engine-rules.json and every
   theory build in data/theory-builds.json: worker conservation, non-negative stock, cost accounting on every
   event, drop-off gating, training start/completion pairs, landmark ages, done condition and input purity. */
const assert = require('node:assert/strict');
const fs = require('fs'), path = require('path');
global.CIV_ENGINE_RULES = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/civ-engine-rules.json'), 'utf8'));
const E = require('../site/engine');
const builds = fs.existsSync(path.join(__dirname, '../data/theory-builds.json')) ? JSON.parse(fs.readFileSync(path.join(__dirname, '../data/theory-builds.json'), 'utf8')).builds : [];
const cases = [...Object.keys(global.CIV_ENGINE_RULES.civs).map(civ => ({ id: civ + ' defaults', civilization: civ })), ...builds];
for (const c of cases) {
  const input = JSON.parse(JSON.stringify(c)), before = JSON.stringify(input);
  const run = E.simulate(input);
  assert.equal(JSON.stringify(input), before, `${c.id}: input unchanged`);
  assert.equal(run.engine, 'civ');
  assert.equal(run.minutes[0].t, 0, `${c.id}: starts with a t=0 snapshot`);
  for (const e of run.events) {
    assert.equal(Object.values(e.split).reduce((a, b) => a + b, 0), e.vil, `${c.id}: worker conservation at ${e.t}`);
    assert.ok(Object.values(e.stock).every(v => Number.isFinite(v) && v >= 0), `${c.id}: stock non-negative at ${e.t} ${JSON.stringify(e.stock)}`);
    for (const r of ['food', 'wood', 'gold', 'stone']) assert.ok(Math.abs(e.stockBefore[r] - e.stock[r] - (e.cost[r] || 0)) <= 1, `${c.id}: ${e.label} pays its cost`);
  }
  for (const m of run.minutes) assert.equal(Object.values(m.split).reduce((a, b) => a + b, 0), m.vil, `${c.id}: snapshot worker conservation ${m.t}`);
  const free = (global.CIV_ENGINE_RULES.civs[run.civilization].start.freeBuildings || []).map(f => f.site);
  for (const source of ['wood', 'gold'].filter(s => !free.includes(s))) {
    const ready = run.events.find(e => e.kind === 'done' && e.source === source);
    for (const e of run.events.filter(e => !ready || e.t < ready.t)) assert.equal(e.split[source], 0, `${c.id}: ${source} before its drop-off at ${e.t}`);
  }
  for (const start of run.events.filter(e => e.kind === 'train')) {
    const end = run.events.find(e => e.kind === 'done' && e.cat === 'unit' && e.producer === start.producer && e.queue === start.queue && e.t >= start.readyAt - 1 && e.t <= start.readyAt);
    assert.ok(end, `${c.id}: training completion ${start.label} ${start.t}`);
  }
  const ages = [2, 3, 4].map(a => run.milestones['age' + a]);
  for (let i = 1; i < ages.length; i++) if (ages[i] != null) assert.ok(ages[i - 1] != null && ages[i] > ages[i - 1], `${c.id}: ages in order`);
  if (run.done != null) { assert.ok(run.lineTechs.every(k => run.milestones[k] != null && run.milestones[k] <= run.done), `${c.id}: line techs before done`); const last = run.minutes.at(-1); assert.ok(last.pop >= 200 || last.vil + last.army >= 190, `${c.id}: population at done`); }
  console.log(`${c.id}: ${run.events.length} events, ages ${ages.map(a => a == null ? '—' : Math.round(a)).join('/')}, done ${run.done ?? '—'}`);
}
console.log(`Civ engine invariants passed for ${cases.length} runs.`);
