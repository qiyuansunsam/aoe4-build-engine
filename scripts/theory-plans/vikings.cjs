/* Vikings theory builds (17.0 preview rules). Crafted by the engine alone: no recorded games exist for this civilization.
   mech.lh = Longhouses allowed per age (built when spare villager capacity falls to mech.lhLead), mech.attach = attachment
   priority list for the completed Longhouses (bee = Bee Skeps, farm = Farmstead, smithy = Smithy, loom = Pasture and Loom).
   Sam, 2026-10-28: two strategies compared, both on the two-Town-Center, six-Longhouse opening (the six with Bee Skeps):
   Feudal mixed melee aggression against Castle Jylland Knight aggression with the Valdemar Castle. Key metrics: the time to
   150 population and the time to 200 population, each with every upgrade of the army lines researched. */
"use strict";
const B6 = ["bee", "bee", "bee", "bee", "bee", "bee"];
// Six planned Longhouses (villager capacity), split over Dark, Feudal and Castle Age. The engine also raises Longhouses as
// houses when the population cap comes within reach of production; those carry the Smithy and the Pasture and Loom, the
// only source of the Vikings' damage and armor upgrades (each attachment auto-researches its three tiers).
const LH6 = [];
for (let a = 0; a <= 6; a++) for (let b = 0; a + b <= 6; b++) LH6.push({ 1: a, 2: b, 3: 6 - a - b, 4: 0 });
const ATTACH = [[...B6, "smithy", "loom"], [...B6, "loom", "smithy"], ["bee", "bee", "bee", "bee", "smithy", "loom", "bee", "bee"], ["bee", "bee", "smithy", "loom", "bee", "bee", "bee", "bee"], ["smithy", "loom", ...B6], ["bee", "bee", "bee", "bee", "bee", "smithy", "bee", "loom"]];
const sixBees = p => { const a = p.mech?.attach || []; return a.filter(k => k === "bee").length === 6 && a.includes("smithy") && a.includes("loom") && a.length === 8; };
const MELEE = ["bondi", "berserker", "hirdman"];
// Mixed melee: at least two of the three Feudal-available melee lines.
// Sam, 2026-10-28: properly mixed melee, balanced but skewed toward the Man-at-Arms line (Hirdman): all three lines, Hirdman
// the largest share, Bondi and Berserker sharing the rest equally.
const MELEE_MIX = [0.4, 0.45, 0.5, 0.55].map(h => ({ hirdman: h, bondi: +((1 - h) / 2).toFixed(4), berserker: +((1 - h) / 2).toFixed(4) }));
const hirdmanSkewed = mix => (mix?.hirdman || 0) > (mix?.bondi || 0) && (mix?.hirdman || 0) > (mix?.berserker || 0);
const AGE = { 2: "Feudal Age", 3: "Castle Age", 4: "Imperial Age" };
const at = (run, t) => run.minutes.filter(m => m.t <= t).at(-1) || run.minutes[0];
const armyAt = (run, ts) => Object.fromEntries(ts.map(t => { const m = at(run, t); return [t, { villagers: m.vil, army: m.army, byLine: m.armyByLine, pop: m.pop }]; }));

// Key metrics: the time to 150 population and the time to 200 population; both must be reached with every line upgrade (done).
const POP = (run, n) => run.milestones["pop" + n] ?? null;
// Realized army against the plan's mix: half the summed share differences over the trained lines at the end (0 = exact mix).
// A plan more than 10% off its mix ranks below every plan that holds it (Sam, 2026-10-28: armies properly mixed).
const mixGap = run => { const m = run.minutes.at(-1)?.armyByLine || {}, mix = run.params?.lineMix || {}, ks = Object.keys(mix).filter(k => mix[k] > 0);
  if (!ks.length) return 0;
  const tot = ks.reduce((s, k) => s + (m[k] || 0), 0); return tot ? ks.reduce((g, k) => g + Math.abs((m[k] || 0) / tot - mix[k]), 0) / 2 : 1; };
const keyRank = run => { const a = POP(run, 150) ?? 1e5, b = POP(run, 200) ?? 1e5, done = run.done ?? 1e5; return -(a + b) * 1e3 - done - Math.max(0, mixGap(run) - 0.1) * 1e9; };
const keyMetric = run => -((POP(run, 150) ?? 1e5) + (POP(run, 200) ?? 1e5));
const keyDescribe = run => { const v = run.vikings || {}; return { mixGap: +mixGap(run).toFixed(3), pop150: POP(run, 150), pop200: POP(run, 200), pop200Age: v.pop200Age ? AGE[v.pop200Age] : null,
  castle: run.milestones.age3 ?? null, imperial: run.milestones.age4 ?? null, firstUnit: run.milestones.first_unit ?? null,
  longhouses: v.longhouses, attachments: v.attachments, villagerCapacity: v.villagerCapacity, sagas: Object.keys(v.sagas || {}), groveBerserkers: v.groveBerserkers, shieldMaidens: v.shieldMaidens,
  armyAt: armyAt(run, [600, 900, 1200, 1500]) }; };
const sixLonghouses = p => Object.values(p.mech?.lh || {}).reduce((a, b) => a + (+b || 0), 0) === 6 && sixBees(p) && p.extraTCs?.[2] === 1 && !p.extraTCs?.[3];

module.exports = lib => {
  const { commonSpace, range } = lib;
  const shared = (civ, opts) => Object.assign(commonSpace(civ, Object.assign({ tc2: [1], tc3: [0], prod1: [0, 1, 2], vilTarget: range(40, 150, 5) }, opts)), {
    "mech.lh": LH6, "mech.attach": ATTACH, "mech.lhLead": [1, 2, 3, 4, 6, 8, 12, 99], "mech.lhBuilders": [1, 2, 3], "mech.longhouseBondi": [false, true], "mech.openWood": [true, false], "mech.reserveWood": [true, false],
    "mech.callMaidens": [false, true], "mech.callMaidensAt": [4, 6, 8, 10, 12, 14] });
  return [
    { id: "vikings-feudal-melee", civilization: "vikings",
      title: "Vikings Feudal mixed melee aggression, two Town Centers, six Longhouses",
      summary: "Two Town Centers and six Longhouses with Bee Skeps (the Smithy and the Pasture and Loom sit on the Longhouses raised as houses), then all three melee infantry lines from Feudal Age, balanced with Hirdman the largest share and Bondi and Berserker sharing the rest. Key metrics: the time to 150 population and the time to 200 population, each with every upgrade of the infantry lines. The Hirdman share, landmarks, Longhouse timing and every other choice come from the engine search; no Imperial economy technologies.",
      base: { lines: MELEE, lineMix: MELEE_MIX[1], extraTCs: { 2: 1, 3: 0 }, armyAge: 2, mech: { lh: { 1: 2, 2: 3, 3: 1, 4: 0 }, attach: ATTACH[0], gullinnMinPop: 0, groves: 0, kongensLonghouses: 0, callMaidens: false } },
      objective: { kind: "done" },
      constraint: p => sixLonghouses(p) && p.armyAge === 2 && (p.lines || []).length === 3 && MELEE.every(l => (p.lines || []).includes(l)) && hirdmanSkewed(p.lineMix) && !p.mech?.longhouseBondi,
      rank: keyRank, metric: keyMetric,
      space: civ => Object.assign(shared(civ, { armyAge: [2] }), { lines: [MELEE], lineMix: MELEE_MIX, "mech.longhouseBondi": [false] }), // Longhouse Bondi production would ignore the mix
      describe: keyDescribe },

    { id: "vikings-valdemar-knights", civilization: "vikings",
      title: "Vikings Castle Jylland Knight aggression with the Valdemar Castle, two Town Centers, six Longhouses",
      summary: "Two Town Centers and six Longhouses with Bee Skeps (the Smithy and the Pasture and Loom sit on the Longhouses raised as houses), the Valdemar Castle in Castle Age, then Jylland Knights from Castle Age. Key metrics: the time to 150 population and the time to 200 population, each with every Jylland Knight upgrade. The Feudal and Imperial landmarks, Longhouse timing and every other choice come from the engine search; no Imperial economy technologies.",
      base: { lines: ["jylland-knight"], extraTCs: { 2: 1, 3: 0 }, armyAge: 3, landmarks: { 3: "valdemar-castle" }, mech: { lh: { 1: 2, 2: 3, 3: 1, 4: 0 }, attach: ATTACH[0], gullinnMinPop: 0, groves: 0, kongensLonghouses: 0, callMaidens: false } },
      objective: { kind: "done" },
      constraint: p => sixLonghouses(p) && p.armyAge === 3 && p.landmarks?.[3] === "valdemar-castle" && (p.lines || []).length === 1 && p.lines[0] === "jylland-knight",
      rank: keyRank, metric: keyMetric,
      space: civ => { const s = Object.assign(shared(civ, { armyAge: [3] }), { lines: [["jylland-knight"]], "landmarks.3": ["valdemar-castle"] }); return s; },
      describe: keyDescribe },
  ];
};
