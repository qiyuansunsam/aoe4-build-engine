const assert = require('node:assert/strict');
const E = require('../site/engine.js');

// Drop-off/production corrections deliberately change historical outputs.
// Zero loss must still exactly match the default; do not freeze buggy old timelines.
for (const params of [{}, { wings: ['economic', 'admin', 'military'] }, { tmax: 600, vilTarget: 40 }]) {
  assert.deepEqual(E.simulate({ ...params, villagerLossPerMinute: 0 }), E.simulate(params));
}

function freeze(value) {
  for (const child of Object.values(value)) if (child && typeof child === 'object') freeze(child);
  return Object.freeze(value);
}
const params = freeze({ tmax: 600, villagerLossPerMinute: 2, villagerLossStart: 300,
  wings: ['economic', 'culture', 'admin'], map: { wood_d: 1.5 } });
const original = JSON.stringify(params);
const losses = E.simulate(params), baseline = E.simulate({ tmax: 600 });
assert.equal(JSON.stringify(params), original);
assert.equal(losses.summary.villagersLost, 9);
assert.equal(losses.events.find(e => e.kind === 'loss').t, 330);
assert.ok(losses.summary.villagers < baseline.summary.villagers);
const totalIncome = r => r.minutes.reduce((total, m) => total + Object.values(m.income).reduce((a, b) => a + b, 0), 0);
assert.ok(totalIncome(losses) < totalIncome(baseline));
const replacement = E.simulate({ tmax: 600, vilTarget: 20, villagerLossPerMinute: 2 });
assert.ok(replacement.summary.spentCat.villagers > E.simulate({ tmax: 600, vilTarget: 20 }).summary.spentCat.villagers);
assert.equal(replacement.summary.villagers, 20);
// Severe early pressure exhausts eligible workers; never kills trainees/builders,
// creates negative workers, or banks missed losses for a later burst.
for (const rate of [0.1, 2, 10]) {
  const run = E.simulate({ tmax: 1200, villagerLossPerMinute: rate, villagerLossStart: 0 });
  const events = run.events.filter(e => e.kind === 'loss');
  assert.equal(events.reduce((sum, e) => sum + e.count, 0), run.summary.villagersLost);
  assert.ok(events.every((e, i) => e.villagersLost === i + 1 && e.vil >= 0 && e.pop >= 0));
  for (const m of run.minutes) {
    assert.ok(m.vil >= m.builders && m.pop >= 0);
    assert.ok(Object.values(m.split).every(v => v >= 0));
    assert.equal(m.villagersLost, events.filter(e => e.t < m.t).length);
  }
}
for (const value of [-1, 11, NaN, Infinity, '2', null]) assert.throws(() => E.simulate({ villagerLossPerMinute: value }), RangeError);
for (const value of [-1, 86401, 0.5, NaN, Infinity, '300', null]) assert.throws(() => E.simulate({ villagerLossStart: value }), RangeError);
console.log('Villager attrition: zero-loss parity, actual losses, replacement spending, input purity and bounds passed.');
