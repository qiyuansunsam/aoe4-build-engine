#!/usr/bin/env node
/* Theory plan versus its reference game at fixed times: villagers, population, army line count, army value and age
   timings. The theory side is a fresh engine run; the reference side is the recorded perspective derived exactly as the
   comparison page derives it (site/observed-derived.js + site/observed-army.js). Writes data/theory-builds-comparison.json. */
"use strict";
const fs = require("fs"), path = require("path");
const ROOT = path.join(__dirname, "..");
const read = f => JSON.parse(fs.readFileSync(path.join(ROOT, f), "utf8"));
global.CIV_ENGINE_RULES = read("data/civ-engine-rules.json");
const E = require(path.join(ROOT, "site/engine.js"));
const ObservedDerived = require(path.join(ROOT, "site/observed-derived.js"));
const ObservedArmy = require(path.join(ROOT, "site/observed-army.js"));
const catalog = read("data/game-catalog.json"), records = [...catalog.units, ...catalog.buildings, ...catalog.technologies];
const byPbg = new Map(records.flatMap(r => [[String(r.source?.pbgid), r], [String(r.entitySource?.pbgid), r]]).filter(([k]) => k !== "undefined"));
const library = read("data/build-library.json").builds, games = read("data/game-library.json").games, theory = read("data/theory-builds.json").builds;
const TIMES = [300, 600, 900, 1200];
const at = (minutes, t) => minutes.filter(m => m.t <= t).at(-1) || null;
const mm = t => t == null ? "—" : `${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, "0")}`;
const out = { generatedAt: new Date().toISOString(), times: TIMES, builds: [] };
for (const b of theory) {
  const run = E.simulate(b), ref = library.find(x => x.id === b.reference?.buildId), game = ref && games.find(g => g.id === ref.sourceGameId);
  if (game) ObservedDerived.derive(game, byPbg);
  const names = new Set(run.lines.flatMap(l => l.tiers.map(t => t.name)));
  const theoryRow = t => { const m = at(run.minutes, t); return m && { villagers: m.vil, population: m.pop, line: m.army, armyValue: m.armyValue, age: m.age }; };
  const refRow = t => { const m = game && at(game.snapshots || [], t); if (!m) return null; const army = ObservedArmy.summarize(m, byPbg); const line = (m.unitCounts || []).filter(u => names.has(byPbg.get(String(u.pbgid))?.name || u.name)).reduce((s, u) => s + Math.max(0, u.balance || 0), 0); const v = (m.unitCounts || []).filter(u => /\bvillagers?\b/i.test(u.name || "")).reduce((s, u) => s + (u.balance || 0), 0); return { villagers: Number.isFinite(m.villagersObservedBalance) ? m.villagersObservedBalance : v, population: m.population ?? null, line, armyValue: army.totalValue ?? army.knownValue, age: null }; };
  const refAges = game ? [2, 3, 4].map(a => { const e = (game.events || []).find(e => new RegExp(["", "", "Feudal", "Castle", "Imperial"][a] + " Age", "i").test(e.label || "")); return e ? e.t : null; }) : [];
  const row = { id: b.id, title: b.title, civilization: b.civilization, objective: b.objective, reference: ref ? { id: ref.id, title: ref.title, gameId: ref.sourceGameId, duration: game?.duration ?? null } : null,
    theory: { ages: [2, 3, 4].map(a => run.milestones["age" + a] ?? null), done: run.done ?? null, at: Object.fromEntries(TIMES.map(t => [t, theoryRow(t)])) },
    referenceGame: { ages: refAges, at: Object.fromEntries(TIMES.map(t => [t, refRow(t)])) } };
  out.builds.push(row);
  console.log(`\n${b.title} (${b.civilization}) vs ${ref?.title || "no reference"}  — ages theory ${row.theory.ages.map(mm).join(" / ")}, reference ${refAges.map(mm).join(" / ")}, done ${mm(run.done)}`);
  console.log("time   | villagers T/R | pop T/R  | " + run.lines.map(l => l.name).join("+") + " T/R | army value T/R");
  for (const t of TIMES) { const a = row.theory.at[t], r = row.referenceGame.at[t]; console.log(`${mm(t).padEnd(6)} | ${String(a?.villagers ?? "—").padStart(4)} / ${String(r?.villagers ?? "—").padEnd(4)} | ${String(a?.population ?? "—").padStart(3)} / ${String(r?.population ?? "—").padEnd(4)} | ${String(a?.line ?? "—").padStart(4)} / ${String(r?.line ?? "—").padEnd(4)} | ${String(a?.armyValue ?? "—").padStart(6)} / ${r?.armyValue ?? "—"}`); }
}
fs.writeFileSync(path.join(ROOT, "data/theory-builds-comparison.json"), JSON.stringify(out, null, 1));
