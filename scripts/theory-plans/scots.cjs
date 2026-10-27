/* Scots theory builds (Update 17.0 preview rules, data/civ-rules/scots.json). Crafted by the engine search alone from game rules;
   no recorded games or guide build orders are inputs. Loaded by scripts/optimize_theory_builds.cjs.
   Sam, 2026-10-25: Stone of Destiny in Feudal with every building in its reach, Kirkmen working Fishponds (the pond buff does
   not stack), and no Imperial (tier 3) economy technologies in any build.
   Sam, 2026-10-28: a muster can only be triggered once, so the mass Border Reiver plan is gone. Two strategies are compared on
   the same key metrics, the time to 150 population and the time to 200 population (every upgrade of the army lines researched):
   Imperial aggression with the one muster fired in Imperial Age, against Castle aggression without a Mustering Hall. */
"use strict";
// Villager ceiling at the 200 population line: at least ~80 population is army.
const VILLAGER_CAP = 120;
const STEW_PONDS = "upgrade_lowland_tier2_sco";
// Map assumptions for relic gathering (named; see data/civ-rules/scots.json unresolved): relics this player collects, tiles from
// the Monastery to each relic (walked out and back at the Kirkman record speed), gold per relic per minute.
const RELICS = { relics: 3, relicDistanceTiles: 45, relicGoldPerMinute: 100 };

const LINES = ["pikeman", "cateran", "man-at-arms", "gallowglass", "border-reiver"];
// Army: one to three of the five lines.
const LINE_SETS = []; for (let m = 1; m < 32; m++) { const s = LINES.filter((_, i) => m & (1 << i)); if (s.length <= 3) LINE_SETS.push(s); }
// Musters that put out a trainable line (the Mustering Hall records); each is a one-time trigger.
const MUSTER_LINE = { pikemen: "pikeman", cateran: "cateran", gallowglass: "gallowglass", reivers: "border-reiver" };
const at = (run, t) => run.minutes.filter(m => m.t <= t).at(-1) || run.minutes[0];
const armyAt = (run, ts) => Object.fromEntries(ts.map(t => { const m = at(run, t); return [t, { villagers: m.vil, army: m.army, byLine: m.armyByLine, pop: m.pop }]; }));
const cattleSpace = () => ({
  "mech.towerHouses.1": [0, 1, 2], "mech.towerHouses.2": [0, 1, 2, 3], "mech.towerHouses.3": [0, 1, 2],
  "mech.cattle.1": [1, 3, 5, 7, 9], "mech.cattle.2": [5, 9, 13], "mech.cattle.3": [9, 13, 17], "mech.cattle.4": [13, 17, 21], "mech.cattleFrom": [0, 60, 120, 240],
});
// Kirkmen from the Stone of Destiny work Fishponds (capacity 1 per Lowland landmark, +1 with Stew Ponds).
const pondSpace = () => ({ "mech.fishponds": [1, 2], [`civTechs.${STEW_PONDS}`]: [3, null] });
const ecoDescribe = run => ({ fishponds: run.scots?.fishponds, stewPonds: run.scots?.stewPonds, rebateGold: run.scots?.rebateGold, kirkmen: run.scots?.kirkmen });
const tcs = p => (p.extraTCs?.[2] || 0) + (p.extraTCs?.[3] || 0);
// Food banked while wood starved the extra production buildings, and the upgrade chains queued behind one Blacksmith
// (2026-10-25 runs): a wider wood floor, wood aimed at the next producer, up to three Blacksmiths, and flow workers that
// taper off once the bank covers bankAware seconds of production.
const flowSpace = range => ({ woodFloor: range(0.05, 0.7, 0.05), producerWood: [false, true], blacksmiths: [0, 1, 2, 3], bankAware: [null, 60, 120, 240] });

// Key metrics: the time to 150 population and the time to 200 population; both must be reached with every line upgrade (done).
const POP = (run, n) => run.milestones["pop" + n] ?? null;
const keyRank = run => { const a = POP(run, 150) ?? 1e5, b = POP(run, 200) ?? 1e5, done = run.done ?? 1e5; return -(a + b) * 1e3 - done; };
const keyMetric = run => -((POP(run, 150) ?? 1e5) + (POP(run, 200) ?? 1e5));
const keyDescribe = run => ({ pop150: POP(run, 150), pop200: POP(run, 200), castle: run.milestones.age3 ?? null, imperial: run.milestones.age4 ?? null,
  firstUnit: run.milestones.first_unit ?? null, relicsStart: run.milestones.relics_start ?? null, firstRelic: run.milestones.first_relic ?? null,
  musters: run.scots?.musters || [], hallTier: run.scots?.hallTier, cattlePeak: run.scots?.cattlePeak, ...ecoDescribe(run), armyAt: armyAt(run, [600, 900, 1200, 1500]) });
const musterOf = p => (p.mech?.musters || [])[0];
// The one muster fires in Imperial Age whichever line it puts out.
const IMPERIAL_MUSTER = Object.fromEntries(Object.keys(MUSTER_LINE).map(k => [k, 4]));

module.exports = lib => {
  const { commonSpace, range } = lib;
  const shared = civ => Object.assign(commonSpace(civ, { tc2: [0, 1], tc3: [0, 1], prod1: [0, 1], prod2: range(0, 6), vilTarget: range(60, VILLAGER_CAP, 5) }), cattleSpace(), pondSpace(), flowSpace(range), {
    lines: LINE_SETS, "producers.4": range(4, 16), maxProducers: range(6, 20), "mech.kirkmen": [1, 2, 3], "mech.snowdoun": ["pikeman", "cateran", "man-at-arms"] });
  return [
    { id: "scots-imperial-muster", civilization: "scots",
      title: "Scots Imperial aggression with one muster",
      summary: "Stone of Destiny in Feudal Age with every building in its reach and Kirkmen on Fishponds, then the army only from Imperial Age with the single muster fired in Imperial Age (a muster is a one-time trigger). Key metrics: the time to 150 population and the time to 200 population, each with every upgrade of the army lines. Castle and Imperial landmarks, Town Centers, the army lines (one to three of Pikeman, Cateran, Man-at-Arms, Gallowglass, Border Reiver) and the mustered line, Highland Cattle, Tower Houses and every timing come from the engine search; no Imperial economy technologies.",
      base: { lines: ["gallowglass"], landmarks: { 2: "stone-of-destiny" }, armyAge: 4, extraTCs: { 2: 1, 3: 0 }, vilTarget: 100, mech: Object.assign({ musters: ["gallowglass"], musterAge: { gallowglass: 4 }, kirkmen: 2, fishponds: 1, hallAge: 3 }, RELICS) },
      objective: { kind: "done" },
      constraint: p => p.landmarks?.[2] === "stone-of-destiny" && (p.mech?.kirkmen || 0) >= 1 && (p.mech?.fishponds || 0) >= 1 && p.armyAge === 4
        && (p.mech?.musters || []).length === 1 && (p.lines || []).includes(MUSTER_LINE[musterOf(p)]) && (p.mech?.musterAge?.[musterOf(p)] || 0) === 4,
      rank: keyRank, metric: keyMetric,
      space: civ => { const s = Object.assign(shared(civ), { armyAge: [4], "mech.hallAge": [2, 3, 4],
        "mech.musters": Object.keys(MUSTER_LINE).map(k => [k]), "mech.musterAge": [IMPERIAL_MUSTER] });
        delete s["landmarks.2"]; return s; },
      describe: keyDescribe },

    { id: "scots-castle-aggression", civilization: "scots",
      title: "Scots Castle aggression",
      summary: "Stone of Destiny in Feudal Age with every building in its reach and Kirkmen on Fishponds, then the army from Castle Age without a Mustering Hall. Key metrics: the time to 150 population and the time to 200 population, each with every upgrade of the army lines. Castle and Imperial landmarks, Town Centers, the army lines (one to three of Pikeman, Cateran, Man-at-Arms, Gallowglass, Border Reiver), Highland Cattle, Tower Houses and every timing come from the engine search; no Imperial economy technologies.",
      base: { lines: ["man-at-arms", "gallowglass"], landmarks: { 2: "stone-of-destiny" }, armyAge: 3, extraTCs: { 2: 0, 3: 0 }, vilTarget: 90, mech: Object.assign({ musters: [], kirkmen: 2, fishponds: 1 }, RELICS) },
      objective: { kind: "done" },
      constraint: p => p.landmarks?.[2] === "stone-of-destiny" && (p.mech?.kirkmen || 0) >= 1 && (p.mech?.fishponds || 0) >= 1 && p.armyAge === 3 && !(p.mech?.musters || []).length,
      rank: keyRank, metric: keyMetric,
      space: civ => { const s = Object.assign(shared(civ), { armyAge: [3], "mech.musters": [[]] }); delete s["landmarks.2"]; return s; },
      describe: keyDescribe },
  ];
};
