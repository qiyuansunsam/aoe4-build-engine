/* Vikings theory builds (17.0 preview rules). Crafted by the engine alone: no recorded games exist for this civilization.
   mech.lh = Longhouses allowed per age (built when spare villager capacity falls to mech.lhLead), mech.attach = attachment
   priority list for the completed Longhouses (bee = Bee Skeps, farm = Farmstead, smithy = Smithy, loom = Pasture and Loom). */
"use strict";
const B6 = ["bee", "bee", "bee", "bee", "bee", "bee"], F = n => Array(n).fill("farm");
// Fourteen Longhouses, the first six with Bee Skeps (Sam's boom), then Farmsteads and the two auto-research attachments.
const BOOM_ATTACH = [
  [...B6, "smithy", "loom", ...F(6)], [...B6, "loom", "smithy", ...F(6)], [...B6, "smithy", ...F(3), "loom", ...F(3)],
  [...B6, ...F(2), "smithy", "loom", ...F(4)], [...B6, ...F(6), "smithy", "loom"], [...B6, "farm", "smithy", "farm", "loom", ...F(4)],
];
const KNIGHT_ATTACH = [
  ...BOOM_ATTACH.slice(0, 4), ["smithy", "loom", ...B6, ...F(6)], ["bee", "bee", "bee", "smithy", "loom", "bee", "bee", "bee", ...F(6)],
  ["farm", "farm", "bee", "bee", "bee", "bee", "smithy", "loom", "bee", "bee", ...F(4)], ["bee", "bee", "farm", "farm", "smithy", "loom", "bee", "bee", "bee", "bee", ...F(4)],
  [...F(6), "smithy", "loom", ...B6], ["farm", "bee", "farm", "bee", "smithy", "loom", "farm", "bee", "farm", "bee", "farm", "bee", "farm", "bee"],
];
// Longhouses allowed per age: all fourteen by Castle Age for the boom (200 population before Imperial).
const BOOM_LH = [];
for (let a = 1; a <= 5; a++) for (let b = 2; a + b <= 14; b++) BOOM_LH.push({ 1: a, 2: b, 3: 14 - a - b, 4: 0 });
const KNIGHT_LH = [];
for (const t of [6, 8, 10, 12, 14]) for (let a = 1; a <= 4; a++) for (let b = 1; a + b <= t; b += 2) for (const d of [0, 2]) if (t - a - b - d >= 0) KNIGHT_LH.push({ 1: a, 2: b, 3: t - a - b - d, 4: d });
const INF_LINES = [["hirdman"], ["berserker"], ["bondi"], ["berserker", "hirdman"], ["bondi", "hirdman"], ["bondi", "berserker"], ["bondi", "berserker", "hirdman"]];

// The boom's measure: completed population reaches 200 before the Imperial landmark completes (Feudal or Castle Age).
// Sam's boom also has all fourteen Longhouses standing by then.
// minVil: the 150-villager variant also fills the whole villager capacity before 200 population.
const pop200 = (run, minVil = 0) => { const v = run.vikings || {}, p = v.pop200, a4 = run.milestones.age4; return p != null && (a4 == null || a4 > p) && (v.atPop200?.longhouses || 0) >= 14 && (v.atPop200?.villagers || 0) >= minVil ? p : null; };
const AGE = { 2: "Feudal Age", 3: "Castle Age", 4: "Imperial Age" };

module.exports = lib => {
  const { commonSpace, phaseSpace, range } = lib;
  const boom = (id, minVil, title, summary) => ({ id, civilization: "vikings", title, summary,
      base: { lines: ["hirdman"], extraTCs: { 2: 1, 3: 0 }, landmarks: { 2: "baugr-fort", 3: "gullinn-temple" }, mech: { gullinnMinPop: 150, groves: 0, kongensLonghouses: 0, callMaidens: false } },
      objective: { kind: "pop200", t: 900, slack: 30 },
      constraint: p => Object.values(p.mech?.lh || {}).reduce((a, b) => a + (+b || 0), 0) === 14 && (p.mech?.attach || []).slice(0, 6).every(k => k === "bee") && p.extraTCs?.[2] === 1 && !p.extraTCs?.[3],
      space: civ => Object.assign(commonSpace(civ, { tc2: [1], tc3: [0], armyAge: [1, 2, 3], prod1: [0, 1], vilTarget: minVil ? [150] : range(100, 150, 5) }), {
        lines: INF_LINES, "landmarks.2": ["baugr-fort"], "landmarks.3": ["gullinn-temple"],
        "mech.lh": BOOM_LH, "mech.attach": BOOM_ATTACH, "mech.lhLead": [1, 2, 3, 4, 6, 8, 12, 99], "mech.lhBuilders": [1, 2, 3], "mech.longhouseBondi": [false, true], "mech.openWood": [true, false], "mech.reserveWood": [true, false],
        "pauseFrom.3": [null, 600, 900, 1200], "pauseFrom.4": [null, 1200, 1500, 1800] }),
      rank: run => { const p = pop200(run, minVil); return p == null ? -1e9 - (run.done ?? 1e5) : -p * 1e3 - (run.done ?? 1e5) / 10; },
      metric: run => { const p = pop200(run, minVil); return p == null ? -1e9 : -p; },
      describe: run => { const v = run.vikings || {}; return { pop200: pop200(run, minVil), pop200Age: v.pop200Age ? AGE[v.pop200Age] : null, gullinnStart: v.gullinnStart, gullinnStartPop: v.gullinnStartPop,
        atPop200: v.atPop200, longhouses: v.longhouses, attachments: v.attachments, villagerCapacity: v.villagerCapacity, sagas: Object.keys(v.sagas || {}), groveBerserkers: v.groveBerserkers }; } });
  return [
    boom("vikings-longhouse-boom", 0, "Vikings two-TC Longhouse boom",
      "Two Town Centers and fourteen Longhouses, the first six with Bee Skeps: the soonest 200 population (villagers and army) reached in Feudal or Castle Age with all fourteen Longhouses standing, the Gullínn Temple started only once population is 150, then the soonest Imperial Age with every upgrade of the infantry it trains. Baugr Fort, Gullínn Temple; army, villager target and timings come from the engine search."),
    boom("vikings-longhouse-boom-150v", 150, "Vikings Longhouse boom, 150 villagers",
      "The same two-Town-Center, fourteen-Longhouse boom with the whole villager capacity filled: 150 villagers and 50 army population reached in Feudal or Castle Age as soon as possible, the Gullínn Temple started only once population is 150, then the soonest Imperial Age with every upgrade of the infantry it trains."),
    { id: "vikings-jylland-knights", civilization: "vikings",
      title: "Jylland Knights by 15:00",
      summary: "Jylland Knights by 15:00 within one knight of the most any searched plan completes, finishing soonest at 200 population with every Jylland Knight upgrade (Elite, Biology, Code of Jylland and the six Smithy and Pasture and Loom tiers). Landmarks, Town Centers, Longhouses and their attachments come from the engine search.",
      base: { lines: ["jylland-knight"], mech: { gullinnMinPop: 0, groves: 0, kongensLonghouses: 0 } },
      objective: { kind: "lineAt", line: "jylland-knight", t: 900, slack: 1 },
      space: civ => Object.assign(commonSpace(civ, { armyAge: [3] }), phaseSpace(900), {
        "mech.lh": KNIGHT_LH, "mech.attach": KNIGHT_ATTACH, "mech.lhLead": [1, 2, 3, 4, 6, 8, 12, 99], "mech.lhBuilders": [1, 2, 3], "mech.openWood": [true, false], "mech.reserveWood": [true, false],
        "mech.callMaidens": [false, true], "mech.callMaidensAt": [6, 8, 10, 12, 14] }),
      describe: run => { const v = run.vikings || {}; return { longhouses: v.longhouses, attachments: v.attachments, villagerCapacity: v.villagerCapacity, sagas: Object.keys(v.sagas || {}), shieldMaidens: v.shieldMaidens, groveBerserkers: v.groveBerserkers, pop200: run.vikings?.pop200 ?? null }; } },
  ];
};
