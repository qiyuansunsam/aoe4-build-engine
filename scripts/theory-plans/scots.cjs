/* Scots theory builds (Update 17.0 preview rules, data/civ-rules/scots.json). Crafted by the engine search alone from game rules;
   no recorded games or guide build orders are inputs. Loaded by scripts/optimize_theory_builds.cjs.
   Sam, 2026-10-25: Stone of Destiny in Feudal with every building in its reach, Kirkmen working Fishponds (the pond buff does
   not stack), a much earlier Imperial Age for the Reiver build, and no Imperial (tier 3) economy technologies in any build. */
"use strict";
// "First units out" mark for the fast Castle infantry builds (seconds). Sam named the mark without a number; 5:00 is the working value.
const FIRST_UNIT_BY = 300;
// Stage 2 keeps the stage-1 age (Castle for the infantry builds, Imperial for the Reiver build) within this many seconds of the
// best, then finishes 200 population soonest.
const CASTLE_SLACK = 30, IMPERIAL_SLACK = 30;
// Map assumptions for relic gathering (named; see data/civ-rules/scots.json unresolved): relics this player collects, tiles from
// the Monastery to each relic (walked out and back at the Kirkman record speed), gold per relic per minute.
const RELICS = { relics: 3, relicDistanceTiles: 45, relicGoldPerMinute: 100 };
// "Mass" army at the 200 population line: the villager target stays at or below this, so at least ~80 population is army.
const VILLAGER_CAP = 120;
const STEW_PONDS = "upgrade_lowland_tier2_sco";

const INFANTRY = ["pikeman", "cateran", "man-at-arms", "gallowglass"];
// "Mixed" melee infantry: every combination of at least two of the four lines.
const SUBSETS = []; for (let m = 1; m < 16; m++) { const s = INFANTRY.filter((_, i) => m & (1 << i)); if (s.length >= 2) SUBSETS.push(s); }
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

function fcBuild(lib, { id, title, extra, tcRule, tcSpace }) {
  const { commonSpace, range } = lib;
  return { id, civilization: "scots", title,
    summary: `${extra} Stone of Destiny in Feudal Age with every building in its reach and Kirkmen on Fishponds. Stage 1: the earliest Castle Age with the first military unit out by ${FIRST_UNIT_BY / 60}:00. Stage 2: Castle Age within ${CASTLE_SLACK} s of that, Kirkmen gathering relics from Castle Age, and the fastest 200 population (at most ${VILLAGER_CAP} villagers) with every upgrade of its infantry lines, without Imperial economy technologies. The infantry mix (Pikeman, Cateran, Man-at-Arms, Gallowglass), musters, Castle and Imperial landmarks and timings come from the engine search.`,
    base: { lines: ["man-at-arms", "gallowglass"], landmarks: { 2: "stone-of-destiny" }, extraTCs: { 2: 0, 3: 0 }, vilTarget: 80, mech: Object.assign({ kirkmen: 2, fishponds: 1, musters: [], firstUnitBy: FIRST_UNIT_BY }, RELICS) },
    objective: { kind: "done", slack: CASTLE_SLACK, firstUnitBy: FIRST_UNIT_BY },
    constraint: p => tcRule(tcs(p)) && p.landmarks?.[2] === "stone-of-destiny" && (p.mech?.kirkmen || 0) >= 1 && (p.mech?.fishponds || 0) >= 1 && (p.lines || []).length >= 2,
    rank: run => { const first = run.milestones.first_unit ?? Infinity, castle = run.milestones.age3 ?? 1e5, done = run.done ?? 99999;
      return first <= FIRST_UNIT_BY ? 1e9 - castle * 1e3 - done / 1e3 : -first * 1e3 - castle; },
    metric: run => ((run.milestones.first_unit ?? Infinity) <= FIRST_UNIT_BY && run.milestones.age3 != null ? -run.milestones.age3 : -1e9),
    space: civ => { const s = Object.assign(commonSpace(civ, Object.assign({ prod1: [0, 1, 2], armyAge: [1, 2, 3], vilTarget: range(40, VILLAGER_CAP, 5) }, tcSpace)), cattleSpace(), pondSpace(), flowSpace(range), {
      lines: SUBSETS,
      "mech.musters": [[], ["pikemen"], ["cateran"], ["gallowglass"], ["pikemen", "gallowglass"], ["cateran", "gallowglass"], ["pikemen", "cateran", "gallowglass"], ["cateran", "pikemen", "gallowglass"]],
      "mech.snowdoun": ["pikeman", "cateran", "man-at-arms"], "mech.hallAge": [2, 3], "mech.kirkmen": [1, 2, 3] }); delete s["landmarks.2"]; return s; },
    describe: run => ({ firstUnitBy: FIRST_UNIT_BY, firstUnit: run.milestones.first_unit ?? null, castle: run.milestones.age3 ?? null, imperial: run.milestones.age4 ?? null,
      relicsStart: run.milestones.relics_start ?? null, firstRelic: run.milestones.first_relic ?? null, relicsPlaced: run.scots?.relicsPlaced, musters: run.scots?.musters || [],
      ...ecoDescribe(run), armyAt: armyAt(run, [600, 900, 1200]) }) };
}

module.exports = lib => {
  const { commonSpace, range } = lib;
  return [
    { id: "scots-skye-reivers", civilization: "scots",
      title: "Scots two Town Centers fast Imperial, Stone of Destiny, Tower of Skye, mass Border Reivers",
      summary: `Two Town Centers, Stone of Destiny in Feudal Age with every building in its reach and Kirkmen on Fishponds, the Tower of Skye in Castle Age. Stage 1: the earliest Imperial Age. Stage 2: Imperial Age within ${IMPERIAL_SLACK} s of that, then the fastest 200 population with every Border Reiver upgrade (Archery Range Reivers plus one Muster Border Reivers), at most ${VILLAGER_CAP} villagers, without Imperial economy technologies. The Imperial landmark, the muster timing, Archery Ranges, Highland Cattle, Tower Houses and every other timing come from the engine search.`,
      base: { lines: ["border-reiver"], landmarks: { 2: "stone-of-destiny", 3: "tower-of-skye" }, armyAge: 4, extraTCs: { 2: 1, 3: 0 }, vilTarget: 100, mech: { musters: ["reivers"], kirkmen: 0, fishponds: 1 } },
      objective: { kind: "done", slack: IMPERIAL_SLACK },
      constraint: p => tcs(p) === 1 && p.landmarks?.[2] === "stone-of-destiny" && p.landmarks?.[3] === "tower-of-skye" && (p.mech?.fishponds || 0) >= 1,
      rank: run => { const imp = run.milestones.age4 ?? 1e5, done = run.done ?? 99999; return 1e9 - imp * 1e3 - done / 1e3; },
      metric: run => (run.milestones.age4 != null ? -run.milestones.age4 : -1e9),
      space: civ => { const s = Object.assign(commonSpace(civ, { tc2: [0, 1], tc3: [0, 1], armyAge: [2, 3, 4], prod2: range(0, 6), vilTarget: range(60, VILLAGER_CAP, 5) }), cattleSpace(), pondSpace(), flowSpace(range), {
        "producers.4": range(4, 16), maxProducers: range(8, 20), "mech.kirkmen": [0, 1, 2], "mech.hallAge": [2, 3], "mech.musterAge.reivers": [3, 4] });
        delete s["landmarks.2"]; delete s["landmarks.3"]; return s; },
      describe: run => ({ castle: run.milestones.age3 ?? null, imperial: run.milestones.age4 ?? null, muster: run.scots?.musters || [], cattlePeak: run.scots?.cattlePeak,
        hallTier: run.scots?.hallTier, ...ecoDescribe(run), armyAt: armyAt(run, [900, 1200, 1500]) }) },

    fcBuild(lib, { id: "scots-fc-infantry", title: "Scots one Town Center fast Castle, mixed melee infantry", extra: "One Town Center.", tcRule: n => n === 0, tcSpace: { tc2: [0], tc3: [0] } }),
    // Sam asked whether the one Town Center is production-blocked: the same marks with extra Town Centers allowed.
    fcBuild(lib, { id: "scots-fc-infantry-2tc", title: "Scots fast Castle, mixed melee infantry, extra Town Center", extra: "One or two extra Town Centers (Feudal or Castle Age).",
      tcRule: n => n >= 1, tcSpace: { tc2: [0, 1], tc3: [0, 1, 2] } }),
  ];
};
