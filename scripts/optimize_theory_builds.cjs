#!/usr/bin/env node
/* Crafts the non-Abbasid theory builds from the engine alone: for each build, search the plan's decision variables
   (villager target, landmark per age and its builders, extra Town Centers, producers per age, economy and line
   technology timing, army lines, cattle/pit-mine/double-production/Yorishiro policy, worker-share bias) with seeded random
   sampling followed by coordinate hill-climbing, scoring each candidate run by the build's stated objective. Recorded games
   are not read here; each build only names the reference game it is compared with.
   Usage: node scripts/optimize_theory_builds.cjs --only <id> [--samples N] [--seed S]   (writes data/theory-builds/<id>.json)
          node scripts/optimize_theory_builds.cjs --merge                               (writes data/theory-builds.json) */
"use strict";
const fs = require("fs"), path = require("path");
const ROOT = path.join(__dirname, "..");
global.CIV_ENGINE_RULES = JSON.parse(fs.readFileSync(path.join(ROOT, "data/civ-engine-rules.json"), "utf8"));
const { simulateCiv } = require(path.join(ROOT, "site/engine-civs.js"));
const RULES = global.CIV_ENGINE_RULES;
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const SAMPLES = +arg("--samples", 1500), ONLY = arg("--only", null), STARTS = +arg("--starts", 5), ROUNDS = +arg("--rounds", 8);
let seed = +arg("--seed", 20261024);
const rand = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
const pick = a => a[Math.floor(rand() * a.length)];
const setPath = (o, p, v) => { const parts = p.split("."); let c = o; for (let i = 0; i < parts.length - 1; i++) { if (c[parts[i]] == null || typeof c[parts[i]] !== "object") c[parts[i]] = {}; c = c[parts[i]]; } c[parts.at(-1)] = v; };
const getPath = (o, p) => p.split(".").reduce((c, k) => c?.[k], o);
const range = (a, b, s = 1) => { const o = []; for (let v = a; v <= b + 1e-9; v += s) o.push(+v.toFixed(4)); return o; };
const landmarkKeys = (civ, age) => (RULES.civs[civ].landmarks[age] || []).map(l => l.key);
const ecoKeys = (civ, age) => Object.entries(RULES.civs[civ].techs).filter(([, t]) => t.cat === "economy" && t.age === age && !t.groupOf && t.effects?.length).map(([k]) => k);
const at = (run, t) => run.minutes.filter(m => m.t <= t).at(-1) || run.minutes[0];

// Objectives. lineAt: completed units of a line at time t (tie: villagers at t, then the done time).
// valueAt: completed army resource value at t. done: the time to 200 population with every upgrade of the lines.
// A build may rank runs itself (build.rank(run) -> higher is better; build.metric(run) -> the army/time measure its slack
// stage keeps), e.g. to impose run-time marks such as "first units out by" or "Castle Age by".
function score(run, obj, build) {
  const s = rawScore(run, obj, build);
  return run.done == null ? s - 1e12 : s; // a plan that never reaches the done condition loses to every plan that does
}
function rawScore(run, obj, build) {
  if (build?.rank) return build.rank(run);
  const m = at(run, obj.t || 900), done = run.done ?? 99999;
  if (obj.kind === "lineAt") return (m.armyByLine?.[obj.line] || 0) * 1e6 + m.vil * 1e3 - done / 10;
  if (obj.kind === "valueAt") return m.armyValue * 1e3 + m.vil - done / 1e4;
  if (obj.kind === "done") return -done * 1e3 + (at(run, 900).armyValue || 0) / 1e3;
  throw new Error("unknown objective " + obj.kind);
}
// The army measure of an army-at-a-time objective (completed line units, or completed army value, at obj.t).
const metric = (run, obj, build) => { if (build?.metric) return build.metric(run); const m = at(run, obj.t || 900); return obj.kind === "lineAt" ? (m.armyByLine?.[obj.line] || 0) : obj.kind === "valueAt" ? m.armyValue : 0; };
const describe = (run, obj) => { const m = at(run, obj.t || 900); return { done: run.done ?? null, at: obj.t || 900, line: obj.line ? m.armyByLine?.[obj.line] || 0 : undefined, army: m.army, armyValue: m.armyValue, villagers: m.vil, population: m.pop, age: m.age, ages: [2, 3, 4].map(a => run.milestones["age" + a] ?? null), firstUnit: run.milestones.first_unit ?? null, ...(BY_ID[run.params?.planId]?.describe?.(run) || {}) }; };

// Shared decision space; each build adds its civilization's choices.
function commonSpace(civ, opts = {}) {
  const ecoOpt = age => { const all = ecoKeys(civ, age); return [[], all, ...all.map(k => [k])]; };
  return {
    vilTarget: opts.vilTarget || range(25, 170, 5),
    "landmarks.2": landmarkKeys(civ, 2), "landmarks.3": landmarkKeys(civ, 3), "landmarks.4": landmarkKeys(civ, 4),
    "lmBuilders.2": range(1, 10), "lmBuilders.3": range(1, 12), "lmBuilders.4": range(1, 14),
    "extraTCs.2": opts.tc2 || [0, 1, 2], "extraTCs.3": opts.tc3 || [0, 1, 2], tcBuilders: range(2, 10, 2),
    "producers.1": opts.prod1 || [0], "producers.2": opts.prod2 || range(0, 6), "producers.3": range(1, 8), "producers.4": range(2, 10), maxProducers: range(4, 14),
    // Imperial (tier 3) economy technologies are never researched (Sam, 2026-10-25).
    "ecoTechs.1": ecoOpt(1), "ecoTechs.2": ["all", ...ecoOpt(2)], "ecoTechs.3": ["all", []], "ecoTechs.4": [[]],
    "milTechAge.2": [true, false], "milTechAge.3": [true, false], blacksmiths: [0, 1, 2], pauseForAge: [false, true],
    window: [3, 4, 5, 6], woodFloor: range(0.05, 0.3, 0.05), goldBias: range(0.6, 1.6, 0.2), armyAge: opts.armyAge || [2, 3],
  };
}
// After an army-at-a-time objective: when to stop massing and save for Castle/Imperial, and a second villager target.
const phaseSpace = T => ({ "pauseFrom.3": [null, T - 60, T, T + 60, T + 120, T + 240, T + 360], "pauseFrom.4": [null, T + 300, T + 600, T + 900],
  vilTarget2: [null, 60, 80, 100, 120, 140], vilTarget2At: [T - 180, T - 120, T - 60, T, T + 60] });
const BY_ID = {};
const BUILDS = [
  { id: "french-knights-10", civilization: "french", reference: "french-observed-4v4", base: { lines: ["royal-knight"] },
    title: "Royal Knights by 10:00", summary: "Royal Knights by 10:00 within one knight of the most any searched plan completes, finishing soonest at 200 population with every Royal Knight upgrade.",
    objective: { kind: "lineAt", line: "royal-knight", t: 600, slack: 1 }, space: civ => Object.assign(commonSpace(civ, { armyAge: [2] }), phaseSpace(600)) },
  { id: "french-knights-15", civilization: "french", reference: "french-knights-observed-4v4", base: { lines: ["royal-knight"] },
    title: "Royal Knights by 15:00", summary: "Royal Knights by 15:00 within one knight of the most any searched plan completes, finishing soonest at 200 population with every Royal Knight upgrade.",
    objective: { kind: "lineAt", line: "royal-knight", t: 900, slack: 1 }, space: civ => Object.assign(commonSpace(civ, { armyAge: [2, 3] }), phaseSpace(900)) },
  { id: "mongol-cavalry-10", civilization: "mongol", reference: "mongols-observed-4v4", base: { lines: ["keshik"] },
    title: "Mongol cavalry by 10:00", summary: "Stable cavalry value at 10:00 within one unit of the most any searched plan completes (Ovoo double production and Improved technologies chosen by the search), finishing soonest at 200 population with every upgrade of its line.",
    objective: { kind: "valueAt", t: 600, slack: 250 }, space: civ => Object.assign(commonSpace(civ, { armyAge: [1, 2], prod1: [0, 1, 2] }), {
      ...phaseSpace(600), lines: [["keshik"], ["horseman"], ["keshik", "horseman"]], "mech.doubleVillagers": [true, false], "mech.doubleArmy": [true, false], "mech.improved": [false, true] }) },
  { id: "malian-cattle-boom", civilization: "malian", reference: "malians-observed-4v4", base: { lines: ["sofa"] },
    title: "Malian cattle boom", summary: "The fastest 200 population with every Sofa upgrade, built on cattle ranches and a Pit Mine; ranch count, cattle timing and every other choice come from the engine search.",
    objective: { kind: "done" }, constraint: p => (p.cattle?.ranches?.[2] || 0) >= 1, space: civ => Object.assign(commonSpace(civ, { armyAge: [2, 3] }), {
      "cattle.ranches.2": range(1, 6), "cattle.ranches.3": range(1, 8), "cattle.ranches.4": range(1, 8), "cattle.herdTarget": [0, 1, 2, 4], "cattle.age": [1, 2], "mech.pitMines": [0, 1] }) },
  { id: "japanese-two-tc", civilization: "japanese", reference: "japanese-observed-4v4", base: { lines: ["samurai", "onna-bugeisha"] },
    title: "Japanese Town Center boom", summary: "The fastest 200 population with every upgrade of its infantry lines from at least two Town Centers; Daimyo upgrades, landmarks, Yorishiro placement and timings come from the engine search.",
    objective: { kind: "done" }, constraint: p => (p.extraTCs?.[2] || 0) + (p.extraTCs?.[3] || 0) >= 1, space: civ => Object.assign(commonSpace(civ, { tc2: [1, 2], armyAge: [2, 3] }), {
      lines: [["samurai"], ["samurai", "onna-bugeisha"], ["onna-bugeisha"]],
      "civTechs.upgrade_capital_tier_1_jpn": [1, 2, 3, null], "civTechs.upgrade_capital_tier_2_jpn": [2, 3, 4, null], "civTechs.upgrade_capital_tier_3_jpn": [3, 4, null],
      "mech.yorishiro": [["farmhouse", "farmhouse", "lumber", "tc", "farmhouse", "lumber"], ["tc", "tc", "farmhouse", "farmhouse", "lumber", "lumber"], ["farmhouse", "farmhouse", "farmhouse", "farmhouse", "lumber", "lumber"], ["lumber", "lumber", "farmhouse", "farmhouse", "forge", "forge"]] }) },
];
// Per-civilization plan files: scripts/theory-plans/<civ>.cjs exports (lib) => [build, ...] with the same fields as above.
{ const dir = path.join(__dirname, "theory-plans");
  if (fs.existsSync(dir)) for (const f of fs.readdirSync(dir).filter(f => f.endsWith(".cjs")).sort()) BUILDS.push(...require(path.join(dir, f))({ commonSpace, phaseSpace, range, landmarkKeys, ecoKeys, at, RULES }));
  for (const b of BUILDS) { BY_ID[b.id] = b; b.base = Object.assign({ planId: b.id }, b.base || {}); } }

function candidate(base, space) { const p = structuredClone(base); for (const [k, vals] of Object.entries(space)) setPath(p, k, pick(vals)); return p; }
function evaluate(build, params) {
  if (build.constraint && !build.constraint(params)) return { s: -Infinity, err: "constraint" };
  try { const run = simulateCiv({ ...params, civilization: build.civilization, lite: true }); return { s: score(run, build.objective, build), m: metric(run, build.objective, build), d: run.done ?? null, run }; }
  catch (e) { return { s: -Infinity, err: e.message }; }
}
function optimize(build) {
  const civ = build.civilization, spec = RULES.civs[civ];
  const space = build.space(civ);
  for (const k of Object.keys(space)) if (!space[k] || !space[k].length) delete space[k];
  const base = structuredClone(build.base || {});
  const seen = new Map(); let evals = 0;
  const key = p => JSON.stringify(Object.keys(space).map(k => getPath(p, k)));
  const ev = p => { const k = key(p); if (seen.has(k)) return seen.get(k); const r = evaluate(build, p); evals++; const out = { p, s: r.s, m: r.m, d: r.d, err: r.err }; seen.set(k, out); return out; };
  // start from the civilization defaults too, so the search never reports something worse than the engine's own default plan
  const defaults = structuredClone(base); for (const k of Object.keys(space)) { const v = getPath(merged(spec), k); if (v !== undefined && space[k].some(x => JSON.stringify(x) === JSON.stringify(v))) setPath(defaults, k, v); }
  const pool = [ev(defaults)];
  for (let i = 0; i < SAMPLES; i++) pool.push(ev(candidate(base, space)));
  const ranked = pool.filter(x => Number.isFinite(x.s)).sort((a, b) => b.s - a.s);
  let best = ranked[0];
  for (const start of ranked.slice(0, STARTS)) {
    let cur = start, improved = true, rounds = 0;
    while (improved && rounds++ < ROUNDS) {
      improved = false;
      for (const [k, vals] of Object.entries(space)) for (const v of vals) {
        if (JSON.stringify(getPath(cur.p, k)) === JSON.stringify(v)) continue;
        const p = structuredClone(cur.p); setPath(p, k, v); const r = ev(p);
        if (r.s > cur.s + 1e-9) { cur = r; improved = true; }
      }
    }
    if (cur.s > best.s) best = cur;
  }
  // Stage 2 for army-at-a-time objectives: keep the army within `slack` of the best found, then finish the game soonest.
  // (A plan that gains one unit at the objective time by never leaving Feudal Age is not the better build.)
  const slack = build.objective.slack;
  if (slack != null) {
    const thr = best.m - slack, s2 = x => x.d != null && x.m >= thr && Number.isFinite(x.s) ? -x.d + x.m / 1e3 : -Infinity;
    const feasible = [...seen.values()].filter(x => Number.isFinite(s2(x))).sort((a, b) => s2(b) - s2(a));
    let best2 = feasible[0];
    for (const start of feasible.slice(0, STARTS)) {
      let cur = start, improved = true, rounds = 0;
      while (improved && rounds++ < ROUNDS) {
        improved = false;
        for (const [k, vals] of Object.entries(space)) for (const v of vals) {
          if (JSON.stringify(getPath(cur.p, k)) === JSON.stringify(v)) continue;
          const p = structuredClone(cur.p); setPath(p, k, v); const r = ev(p);
          if (s2(r) > s2(cur) + 1e-9) { cur = r; improved = true; }
        }
      }
      if (s2(cur) > s2(best2)) best2 = cur;
    }
    best = { ...best2, stage1: { metric: best.m, done: best.d } };
  }
  const all = [...seen.values()].filter(x => Number.isFinite(x.s)).sort((a, b) => b.s - a.s);
  return { best, evals, runners: all.slice(1, 6).map(x => ({ params: x.p, result: describe(simulateCiv({ ...x.p, civilization: civ, lite: true }), build.objective) })) };
}
function merged(spec) { const d = structuredClone(require(path.join(ROOT, "site/engine-civs.js")).DEFAULTS); const s = spec.defaults || {}; return Object.assign(d, s, { mech: Object.assign({}, d.mech, s.mech), cattle: s.cattle || d.cattle }); }

const DIR = path.join(ROOT, "data/theory-builds");
// --polish: for an army-at-a-time build, take every plan any search wrote, fix the threshold at the best army measure any of
// them reaches minus the build's slack, and hill-climb (with random multi-coordinate mutations) for the soonest finish.
if (process.argv.includes("--polish")) {
  const build = BUILDS.find(b => b.id === ONLY); if (!build || build.objective.slack == null) throw new Error("--polish needs --only <army-at-a-time build>");
  const civ = build.civilization, space = build.space(civ); for (const k of Object.keys(space)) if (!space[k] || !space[k].length) delete space[k];
  const files = fs.readdirSync(DIR).filter(f => f.startsWith(build.id + ".") && f.endsWith(".json") && f !== build.id + ".polish.json" || f === build.id + ".json");
  const seeds = files.map(f => { const { result, objective, reference, title, summary, lineNames, id, engine, patch, ...params } = JSON.parse(fs.readFileSync(path.join(DIR, f), "utf8")).build; return params; });
  const seen = new Map(); let evals = 0; const t0 = Date.now();
  const key = p => JSON.stringify(Object.keys(space).map(k => getPath(p, k)).concat([p.lines]));
  const run1 = p => { const k = key(p); if (seen.has(k)) return seen.get(k); evals++; let o; try { const run = simulateCiv({ ...p, civilization: civ, lite: true }); o = { p, m: metric(run, build.objective, build), d: run.done ?? null }; } catch (e) { o = { p, m: -Infinity, d: null }; } seen.set(k, o); return o; };
  const base = seeds.map(run1); const thr = Math.max(...base.map(x => x.m)) - build.objective.slack;
  const s2 = x => x.d != null && x.m >= thr ? -x.d + x.m / 1e3 : -Infinity;
  const keys = Object.keys(space);
  for (const sd of base) for (let i = 0; i < SAMPLES; i++) { const p = structuredClone(sd.p); const n = 1 + Math.floor(rand() * 3); for (let j = 0; j < n; j++) { const k = pick(keys); setPath(p, k, pick(space[k])); } run1(p); }
  let best = [...seen.values()].filter(x => Number.isFinite(s2(x))).sort((a, b) => s2(b) - s2(a));
  let top = best[0];
  for (const start of best.slice(0, STARTS)) {
    let cur = start, improved = true, rounds = 0;
    while (improved && rounds++ < ROUNDS) { improved = false; for (const [k, vals] of Object.entries(space)) for (const v of vals) { if (JSON.stringify(getPath(cur.p, k)) === JSON.stringify(v)) continue; const p = structuredClone(cur.p); setPath(p, k, v); const r = run1(p); if (s2(r) > s2(cur) + 1e-9) { cur = r; improved = true; } } }
    if (s2(cur) > s2(top)) top = cur;
  }
  const full = simulateCiv({ ...top.p, civilization: civ }), res = describe(full, build.objective);
  const params = Object.fromEntries(Object.entries(top.p).filter(([k]) => !["lite", "debugAlloc", "civilization"].includes(k)));
  const out = { method: `Polish: threshold ${thr} (best army measure over ${files.length} searches minus slack ${build.objective.slack}); ${SAMPLES} random 1-3 coordinate mutations per searched plan, then hill-climbing from the best ${STARTS} for the soonest finish.`, score: s2(top),
    build: { id: build.id, title: build.title, summary: build.summary, civilization: civ, engine: "civ", patch: RULES.civs[civ].patch || RULES.patch, reference: build.reference ? { buildId: build.reference } : undefined, objective: build.objective, lineNames: full.lines.map(l => l.name).join(" and "), result: res, ...params, civilization: civ },
    ledger: { id: build.id, evaluations: evals, seconds: Math.round((Date.now() - t0) / 1000), seed: +arg("--seed", 20261024), objective: build.objective, threshold: thr, best: res, runnersUp: [] } };
  fs.writeFileSync(path.join(DIR, build.id + ".polish.json"), JSON.stringify(out, null, 1));
  console.log(`${build.id} polish: ${evals} runs in ${out.ledger.seconds} s, threshold ${thr} ->`, JSON.stringify(res));
} else if (process.argv.includes("--merge")) {
  const out = { schemaVersion: 1, generatedAt: new Date().toISOString(), engine: "site/engine-civs.js", rules: "data/civ-engine-rules.json", patch: RULES.patch, builds: [] }, ledger = { generatedAt: out.generatedAt, builds: [] };
  // Several seeded searches per build may exist (<id>.json, <id>.<tag>.json): the best objective score wins; all are kept in the ledger.
  for (const b of BUILDS) { const files = fs.readdirSync(DIR).filter(f => f === b.id + ".json" || (f.startsWith(b.id + ".") && f.endsWith(".json"))); if (!files.length) { console.error("missing", b.id); continue; }
    const rs = files.map(f => JSON.parse(fs.readFileSync(path.join(DIR, f), "utf8")));
    for (const x of rs) { const { result, objective, reference, title, summary, lineNames, ...params } = x.build; x.score = score(simulateCiv({ ...params, lite: true }), b.objective, b); } // re-scored with the current engine
    if (b.objective.slack != null) { for (const x of rs) { const { result, objective, reference, title, summary, lineNames, ...params } = x.build; const run = simulateCiv({ ...params, lite: true }); x.m = metric(run, b.objective, b); x.d = run.done ?? Infinity; }
      const thr = Math.max(...rs.map(x => x.m)) - b.objective.slack; for (const x of rs) x.score = x.m >= thr && Number.isFinite(x.d) ? -x.d + x.m / 1e3 : -Infinity; }
    rs.sort((x, y) => y.score - x.score); const r = rs[0];
    const { result: _r, objective: _o, ...plan } = r.build; const run = simulateCiv({ ...plan, lite: true });
    out.builds.push({ ...r.build, title: b.title, summary: b.summary, objective: b.objective, result: describe(run, b.objective) }); ledger.builds.push({ ...r.ledger, searches: rs.map(x => ({ seed: x.ledger.seed, evaluations: x.ledger.evaluations, score: x.score, best: x.ledger.best })) }); if (!out.method) out.method = r.method; console.log(b.id, "best of", rs.length, JSON.stringify(r.build.result)); }
  fs.writeFileSync(path.join(ROOT, "data/theory-builds.json"), JSON.stringify(out, null, 1));
  fs.writeFileSync(path.join(ROOT, "data/theory-builds-search.json"), JSON.stringify(ledger, null, 1));
  console.log("merged", out.builds.length, "builds");
} else {
  const build = BUILDS.find(b => b.id === ONLY); if (!build) throw new Error("--only <id> required: " + BUILDS.map(b => b.id).join(", "));
  const t0 = Date.now(), r = optimize(build), full = simulateCiv({ ...r.best.p, civilization: build.civilization }), res = describe(full, build.objective);
  const params = Object.fromEntries(Object.entries(r.best.p).filter(([k]) => !["lite", "debugAlloc"].includes(k)));
  const method = `Seeded random sampling (${SAMPLES} candidates plus the civilization defaults) then coordinate hill-climbing from the best ${STARTS}; every candidate is a full engine run scored by the build objective. Recorded games are not inputs.`;
  const out = { method, score: r.best.s, build: { id: build.id, title: build.title, summary: build.summary, civilization: build.civilization, engine: "civ", patch: RULES.civs[build.civilization].patch || RULES.patch, reference: build.reference ? { buildId: build.reference } : undefined,
    objective: build.objective, lineNames: full.lines.map(l => l.name).join(" and "), result: res, ...params, civilization: build.civilization },
    ledger: { id: build.id, evaluations: r.evals, seconds: Math.round((Date.now() - t0) / 1000), seed: +arg("--seed", 20261024), objective: build.objective, best: res, runnersUp: r.runners } };
  const tag = arg("--tag", null); fs.mkdirSync(DIR, { recursive: true }); fs.writeFileSync(path.join(DIR, build.id + (tag ? "." + tag : "") + ".json"), JSON.stringify(out, null, 1));
  console.log(`${build.id}: ${r.evals} runs in ${out.ledger.seconds} s ->`, JSON.stringify(res));
}
