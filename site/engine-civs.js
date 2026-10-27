/* AoE4 multi-civilization theoretical engine: French, Mongols, Malians and Japanese on the installed 16.3.11308 rules.
   Same arithmetic as engine.js (1 s steps; gather C / (C/r + 2d/v + t_turn); construction T1 x 3/(n+2); greedy plan executor
   with deficit-weighted worker shares), driven by data/civ-engine-rules.json (compiled from data/civ-rules/*.json by
   scripts/build_civ_engine_rules.py) and a parameterised plan. No value is taken from recorded games.
   simulateCiv(params) -> run object with the engine.js contract plus army counts per line, unitCounts rows keyed by installed
   pbgid, passive income (in `algebra`, shown as passive income) and lineTechs, the upgrades of the done condition. */
(function (root) {
"use strict";
const R = ["food", "wood", "gold", "stone"];
const zero = () => ({ food: 0, wood: 0, gold: 0, stone: 0 });
const sum = c => R.reduce((s, r) => s + (c?.[r] || 0), 0);
const times = (c, f) => { const o = zero(); for (const r of R) o[r] = (c?.[r] || 0) * f; return o; };
const buildTime = (base, n) => base * 3 / (n + 2);
const POP_MAX = 200;
const AGE = { 1: "Dark Age", 2: "Feudal Age", 3: "Castle Age", 4: "Imperial Age" };
// Source classes that technology and civilization effects can target.
const CLASS = {
  sheep: ["food", "food_soft", "herd", "sheep"], pasture: ["food", "food_soft", "herd", "sheep", "pasture"], cattle: ["food", "food_soft", "herd", "cattle"],
  berries: ["food", "food_soft", "forage", "berries"], berriesFar: ["food", "food_soft", "forage", "berries"], farm: ["food", "food_soft", "farm"],
  deer: ["food", "hunt", "deer"], wood: ["wood"], gold: ["gold", "mine"], stone: ["stone", "mine"],
};
const GATHER_KEY = { pasture: "sheep", berriesFar: "berries" };
const NATURAL = ["sheep", "berries", "deer", "berriesFar"];
const DEFAULTS = {
  civilization: "french", lines: null, lineMix: null, vilTarget: 120, landmarks: {}, lmBuilders: { 2: 4, 3: 6, 4: 8 }, tcBuilders: 4,
  extraTCs: { 2: 1, 3: 0 }, producers: { 1: 0, 2: 1, 3: 3, 4: 5 }, maxProducers: 8, armyAge: 2, ecoTechs: { 1: [], 2: "all", 3: "all", 4: [] }, civTechs: {},
  milTechAge: { 2: true, 3: true, 4: true }, blacksmiths: 1, pauseForAge: false, window: 4, escortUnits: 10, woodFloor: 0.12, goldBias: 1,
  map: { sheep: [20, 200, 0], berries: [8, 350, 1.0], berriesFar: [2, 8, 350, 1.5], deer: [8, 350, 1.5], deerPacks: 1, wood_d: 1.5, gold_d: 1.0, stone_d: 1.0, tcDistances: { sheep: 0 } },
  t_turn: 0.3, t_sheep_group: 4.0, idle: 0.05, tmax: 3600, villagerLossPerMinute: 0, villagerLossStart: 300, lite: false, mech: {}, cattle: null,
};
const isObj = v => v && typeof v === "object" && !Array.isArray(v);
const merge = (a, b) => { const o = Object.assign({}, a); for (const [k, v] of Object.entries(b || {})) o[k] = isObj(v) && isObj(a[k]) ? merge(a[k], v) : v; return o; };

function rules() { return root.CIV_ENGINE_RULES || (typeof require === "function" ? require("../data/civ-engine-rules.json") : null); }
// Civilization mechanics modules: site/civ-mech/<civ>.js registers hooks in root.AoE4CivMechanics[<civ>] (build.py embeds
// them after this file; Node loads them on demand). Each hook receives the run context `ctx` built before the first step:
// init, step, villagers (return true when the module trains the villagers itself), passive(o, inc), farmRate(n),
// finishBuild(name, site), finishLandmark(job, L), finishTech(name, group), tryItem(name, site) / costOf(name) for plan
// items ["x", name, site], snapshot(row), result(out).
function civMech(key) {
  const reg = root.AoE4CivMechanics || (root.AoE4CivMechanics = {});
  if (!reg[key] && typeof require === "function") { try { require("./civ-mech/" + key + ".js"); } catch (e) { if (e.code !== "MODULE_NOT_FOUND" || !String(e.message).includes("civ-mech")) throw e; } }
  return reg[key] || null;
}

function simulateCiv(user) {
  const RULES = rules(); const spec = RULES && RULES.civs && RULES.civs[(user || {}).civilization || DEFAULTS.civilization];
  if (!spec) throw new RangeError(`No engine rules for civilization ${(user || {}).civilization}`);
  const P = merge(merge(DEFAULTS, spec.defaults || {}), user || {});
  if (!Number.isFinite(P.villagerLossPerMinute) || P.villagerLossPerMinute < 0 || P.villagerLossPerMinute > 10) throw new RangeError("villagerLossPerMinute must be between 0 and 10");
  if (!Number.isInteger(P.villagerLossStart) || P.villagerLossStart < 0 || P.villagerLossStart > 86400) throw new RangeError("villagerLossStart must be an integer between 0 and 86400 seconds");
  for (const [source, distance] of Object.entries(P.map.tcDistances || {})) if (!Number.isFinite(distance) || distance < 0) throw new RangeError(`Invalid Town Center distance for ${source}`);
  const vt = () => Number.isFinite(P.vilTarget2At) && Number.isFinite(P.vilTarget2) && S.t >= P.vilTarget2At ? P.vilTarget2 : P.vilTarget;
  const X = civMech(spec.key) || {}; let ctx = null; const hook = (name, ...a) => (X[name] && ctx ? X[name](ctx, ...a) : undefined);
  const M = spec.mech || {}, B = spec.buildings, T = spec.techs, lineKeys = (P.lines && P.lines.length ? P.lines : spec.defaultLines).filter(k => spec.lines[k]);
  const lines = lineKeys.map(k => ({ key: k, ...spec.lines[k] }));
  const mix = P.lineMix || Object.fromEntries(lineKeys.map(k => [k, 1 / lineKeys.length]));
  const role = Object.assign({ berries: "mill", deer: "mill", berriesFar: "mill", wood: "lumber-camp", gold: "mining-camp", stone: "mining-camp" }, spec.roles || {});
  const canGather = r => r === "food" || !!spec.villager.gather[r]?.rate;
  const startUnits = (spec.start.units || []).reduce((s, u) => s + (u.pop || 0) * (u.count || 0), 0);
  const S = {
    t: 0, res: Object.assign(zero(), spec.start.res), V: spec.start.villagers, builders: 0, age: 1, techs: new Set(), bld: { "town-center": 1 }, farms: 0, freeFarms: 0, houses: 0,
    popcap: M.noHouses ? POP_MAX : spec.start.popCap, tcTimer: [0], tcBatch: [0], prod: [], research: [], jobs: [], landmarks: [], others: startUnits,
    stock: { sheep: P.map.sheep[0] * P.map.sheep[1], berries: P.map.berries[0] * P.map.berries[1], deer: P.map.deer[0] * P.map.deer[1] * P.map.deerPacks, berriesFar: P.map.berriesFar[0] * P.map.berriesFar[1] * P.map.berriesFar[2] },
    dropoffs: { sheep: true }, farMills: 0, army: Object.fromEntries(lineKeys.map(k => [k, { count: 0, training: 0, produced: 0 }])), tier: Object.fromEntries(lineKeys.map(k => [k, 0])),
    milestones: {}, spent: zero(), spentCat: { villagers: 0, units: 0, buildings_eco: 0, buildings_prod: 0, techs_eco: 0, techs_mil: 0, ages: 0 }, events: [], minutes: [], techRec: {},
    gathered: zero(), passiveGot: zero(), lastInc: zero(), farmNeed: 0, pastures: 0, pastureNeed: 0, cattle: { herd: 0, ranched: 0, training: 0, bought: 0, eaten: 0 }, cattleTimers: [], ranches: 0, pitMines: 0,
    ovoo: 0, ovooStone: M.ovoo ? (P.map.stoneDeposits || M.ovoo.deposits || []).reduce((a, b) => a + b, 0) : 0, yori: null, kuraNext: null, aura: 1,
    villagersLost: 0, lossAttempts: 0, vMark: 0, aMark: 0, unitsProduced: 0, producedAtMinute: 0, mods: [], modsVersion: 0, ecoTracked: [], allocationKey: "",
  };
  // ----- effects: civilization start effects, then landmark and technology effects as they complete
  const cache = { v: -1, by: {} };
  const addEffects = (effects, source) => { for (const e of effects || []) S.mods.push(Object.assign({ source }, e)); S.modsVersion++; };
  const modsOf = kind => { if (cache.v !== S.modsVersion) { cache.v = S.modsVersion; cache.by = {}; for (const m of S.mods) (cache.by[m.kind] = cache.by[m.kind] || []).push(m); } return cache.by[kind] || []; };
  const hits = (m, targets) => m.target === "all" || targets.includes(m.target);
  const mulOf = (kind, targets) => { let f = 1; for (const m of modsOf(kind)) if (hits(m, targets) && m.op !== "add" && m.op !== "set") f *= m.value; return f; };
  const addOf = (kind, targets) => { let a = 0; for (const m of modsOf(kind)) if (hits(m, targets) && m.op === "add") a += m.value; return a; };
  addEffects(spec.startEffects, "civilization");

  const tierOf = l => l.tiers[Math.min(S.tier[l.key], l.tiers.length - 1)];
  const pop = () => S.V + S.others + lines.reduce((s, l) => s + (S.army[l.key].count + S.army[l.key].training) * tierOf(l).pop, 0);
  const trainees = () => S.tcTimer.reduce((s, t, i) => s + (t > 0 ? S.tcBatch[i] : 0), 0);
  const completedV = () => S.V - trainees();
  const armyDone = () => lines.reduce((s, l) => s + S.army[l.key].count, 0);
  const armyPopDone = () => lines.reduce((s, l) => s + S.army[l.key].count * tierOf(l).pop, 0);
  const can = c => R.every(r => S.res[r] >= (c[r] || 0) - 1e-9);
  const pay = (c, cat) => { for (const r of R) { S.res[r] -= c[r] || 0; S.spent[r] += c[r] || 0; } if (cat) S.spentCat[cat] += sum(c); };
  const priced = (c, kind, key) => times(c, mulOf("cost", [kind, kind + ":" + key]));
  const mark = k => { if (!(k in S.milestones)) S.milestones[k] = S.t; };
  const workerState = a => { a = a || allocate(); return { split: { food: a.sheep + a.berries + a.deer + a.berriesFar + a.farm + a.pasture + a.cattle, wood: a.wood, gold: a.gold, stone: a.stone, builders: S.builders, idle: a.idle || 0 }, sources: { sheep: a.sheep, berries: a.berries, deer: a.deer, farBerries: a.berriesFar, farm: a.farm, pasture: a.pasture, cattle: a.cattle } }; };
  const ev = (kind, cat, label, trigger, effect, c, detail = {}) => {
    if (P.lite && !detail.keep) return;
    const phase = kind === "done" ? "complete" : ["build", "tech", "age", "train", "farm"].includes(kind) ? "start" : kind === "assign" ? "allocation" : "milestone";
    S.events.push({ t: S.t, kind, cat, label, trigger, effect, phase, cost: c ? Object.fromEntries(R.filter(r => c[r]).map(r => [r, +c[r].toFixed(2)])) : {},
      stockBefore: Object.fromEntries(R.map(r => [r, Math.round(S.res[r] + (c?.[r] || 0))])), stock: Object.fromEntries(R.map(r => [r, Math.round(S.res[r])])),
      vil: completedV(), army: armyDone(), pop: pop(), age: S.age, ...workerState(), ...detail });
  };
  const hasDropoff = source => S.dropoffs[source] || Number.isFinite((P.map.tcDistances || {})[source]);
  const sourceDistance = source => S.dropoffs[source] ? (source === "berriesFar" ? P.map.berriesFar[3] : ["wood", "gold", "stone"].includes(source) ? P.map[source + "_d"] : P.map[source]?.[2] || 0) : P.map.tcDistances[source];

  // ----- gather model (engine.js rEff with civilization rates and active effects)
  function rEff(source, d) {
    const g = spec.villager.gather[source] || spec.villager.gather[GATHER_KEY[source]]; if (!g || !g.rate) return 0;
    const cls = CLASS[source] || [source];
    const r = g.rate * mulOf("gather_rate", cls), cap = g.carry + addOf("carry", cls), v = spec.villager.speed * mulOf("speed", ["villager"]);
    return cap / (cap / r + 2 * d / v + P.t_turn);
  }
  const pastureD = () => M.pasture?.distance ?? 1;
  const sheepGroupRate = k => { const f = P.map.sheep[1], r = rEff("sheep", 0); return f / (f / (k * r) + P.t_sheep_group); };
  const gm = () => (1 - P.idle);
  // Japanese Daimyo aura: the highest completed tier sets the farm rate for the farms inside one Town Center's aura.
  const farmNear = () => { if (S.aura === 1 || !S.farms) return 1; const inside = Math.min(S.farms, P.mech.farmsPerTC ?? 12); return 1 + (S.aura - 1) * inside / S.farms; };
  const pastureCapacity = () => M.pasture ? M.pasture.sheepFood / M.pasture.interval : 0;

  // ----- plan: drop-offs, landmark per age, extra Town Centers, producers, economy and line technologies
  const lmByKey = key => { for (const a of [2, 3, 4]) { const f = (spec.landmarks[a] || []).find(o => o.key === key); if (f) return f; } return null; };
  const lm = age => { const opts = spec.landmarks[age] || []; return opts.find(o => o.key === P.landmarks[age]) || opts[0]; };
  const lineTechs = [...new Set(lines.flatMap(l => l.techs || []))].filter(k => T[k]);
  const ecoAt = age => { const want = P.ecoTechs[age]; const all = Object.keys(T).filter(k => T[k].cat === "economy" && T[k].age === age && !T[k].groupOf && T[k].effects && T[k].effects.length); return want === "all" ? all : (Array.isArray(want) ? want : []).filter(k => T[k]); };
  const producerKeys = [...new Set(lines.flatMap(l => l.producers))];
  const mainProducer = producerKeys.find(k => B[k]) || producerKeys[0];
  // With a plan line mix (P.lineMix), producers are built in proportion to it: each line's share goes to its first buildable
  // producer, and the next producer is the building furthest below its share (Sam, 2026-10-28: Tacksmen need Archery Ranges).
  // Without a line mix every producer is the main one, as before.
  const prodShare = {};
  if (P.lineMix) for (const l of lines) { const b = l.producers.find(k => B[k]); if (b && (mix[l.key] || 0) > 0) prodShare[b] = (prodShare[b] || 0) + mix[l.key] * (l.tiers[l.tiers.length - 1].time || 20); }
  { const tot = Object.values(prodShare).reduce((x, y) => x + y, 0); for (const k in prodShare) prodShare[k] /= tot || 1; } // unit share x train time: slower units need more buildings
  const pickProducer = counts => { const keys = Object.keys(prodShare); if (keys.length < 2) return keys[0] || mainProducer; const total = keys.reduce((s, k) => s + (counts[k] || 0), 0) + 1;
    return keys.sort((a, b) => ((counts[a] || 0) / total - prodShare[a]) - ((counts[b] || 0) / total - prodShare[b]))[0]; };
  const plan = [];
  const push = (...items) => plan.push(...items);
  const planProducer = () => { const c = {}; for (const x of plan) if (x[0] === "b" && producerKeys.includes(x[1])) c[x[1]] = (c[x[1]] || 0) + 1; return pickProducer(c); };
  push(["b", role.berries, "berries"], ["b", role.wood, "wood"]);
  if (canGather("gold")) push(["b", role.gold, "gold"]);
  if (role.deer && P.map.deer[0] > 0) push(["b", role.deer, "deer"]);
  for (const k of spec.planExtras?.[1] || []) push(k);
  for (const k of ecoAt(1)) push(["t", k]);
  const civAt = age => Object.entries(P.civTechs || {}).filter(([k, a]) => T[k] && a === age).map(([k]) => ["t", k]);
  push(...civAt(1));
  if ((P.producers[1] || 0) > 0 && P.armyAge <= 1) for (let i = 0; i < P.producers[1]; i++) push(["b", planProducer()]);
  push(["age", lm(2).key]);
  for (let age = 2; age <= 4; age++) {
    for (let i = 0; i < (P.extraTCs[age] || 0); i++) push(["b", "town-center"]);
    if (age >= P.armyAge) { const have = plan.filter(x => x[0] === "b" && producerKeys.includes(x[1])).length; for (let i = have; i < (P.producers[age] || 0); i++) push(["b", planProducer()]); }
    for (const k of spec.planExtras?.[age] || []) push(k);
    if (P.blacksmiths && spec.blacksmith && B[spec.blacksmith] && !plan.some(x => x[1] === spec.blacksmith) && lineTechs.some(k => T[k].building === spec.blacksmith && T[k].age <= age)) for (let i = 0; i < P.blacksmiths; i++) push(["b", spec.blacksmith]);
    for (const k of ecoAt(age)) push(["t", k]);
    push(...civAt(age));
    if (P.milTechAge[age]) for (const k of lineTechs.filter(k => T[k].age === age)) push(["t", k]);
    if (age < 4) push(["age", lm(age + 1).key]);
  }
  for (const k of lineTechs.filter(k => !plan.some(x => x[1] === k))) push(["t", k]);
  const costOf = ([kind, name]) => (kind === "b" ? B[name]?.cost : kind === "t" ? T[name]?.cost : kind === "x" ? hook("costOf", name) : lmByKey(name)?.cost) || {};
  // A stone drop-off before the first planned item that costs stone (extra Town Centers, Daimyo upgrades) when villagers mine stone.
  { const first = plan.findIndex(x => costOf(x).stone > 0);
    if (first >= 0 && canGather("stone") && role.stone && B[role.stone] && !plan.some(x => x[0] === "b" && x[2] === "stone")) { const ai = plan.findIndex(x => x[0] === "age"); plan.splice(Math.min(first, ai >= 0 ? ai : first), 0, ["b", role.stone, "stone"]); } }
  // technology buildings the plan needs (University for Biology, Arsenal, Madrasa...)
  for (const [kind, k] of [...plan]) if (kind === "t" && T[k] && T[k].building && B[T[k].building] && !plan.some(x => x[0] === "b" && x[1] === T[k].building) && T[k].building !== "town-center" && !Object.values(role).includes(T[k].building) && !producerKeys.includes(T[k].building) && T[k].building !== spec.house) {
    const idx = plan.findIndex(x => x[1] === k); plan.splice(idx, 0, ["b", T[k].building]);
  }
  const removePlan = (k, n) => { const i = plan.findIndex(x => x[0] === k && x[1] === n); if (i >= 0) plan.splice(i, 1); };
  for (const fb of spec.start.freeBuildings || []) { S.bld[fb.key] = (S.bld[fb.key] || 0) + 1; if (fb.site) { S.dropoffs[fb.site] = true; const i = plan.findIndex(x => x[0] === "b" && x[1] === fb.key && x[2] === fb.site); if (i >= 0) plan.splice(i, 1); } }
  for (const k in T) S.techRec[k] = { name: k, label: T[k].name, pbgid: T[k].pbgid, cat: T[k].cat, building: T[k].building, buildingName: T[k].buildingName, age: T[k].age, baseCost: sum(T[k].cost), available: null, start: null, end: null, payback: null, planned: plan.some(x => x[0] === "t" && x[1] === k), lineTech: lineTechs.includes(k) };

  // ----- allocation and income
  const DARK = { food: 0.7, wood: 0.15, gold: 0.15, stone: 0 };
  const producing = l => S.age >= Math.max(P.armyAge, l.tiers[0].age);
  function longRun() {
    const o = zero();
    if (S.V < vt()) o.food += sum(villagerCost()) * S.tcTimer.length / villagerTime();
    for (const l of lines) if (producing(l)) { const c = tierOf(l).cost, n = S.prod.filter(p => p.lines.includes(l.key)).length * (mix[l.key] || 0); for (const r of R) o[r] += (c[r] || 0) * n / unitTime(l); }
    if (!canGather("stone")) o.stone = 0;
    const tot = sum(o); if (tot < 1e-9) return { food: 0.55, wood: 0.15, gold: 0.30, stone: 0 };
    for (const r of R) o[r] /= tot; o.wood = Math.max(o.wood, P.woodFloor); o.gold *= P.goldBias; const n = sum(o); for (const r of R) o[r] /= n; return o;
  }
  function targets() {
    const tgt = zero(); let seenB = false;
    for (let i = 0; i < Math.min(P.window, plan.length); i++) {
      const [kind] = plan[i]; if (kind === "b") seenB = true; if (kind === "age" && seenB) break;
      const c = costOf(plan[i]); for (const r of R) tgt[r] += (c[r] || 0) / (i + 1);
      if (kind === "age") break;
    }
    if (S.V < vt()) tgt.food += sum(villagerCost()) / villagerTime() * S.tcTimer.length * 60;
    if (pop() < POP_MAX) for (const l of lines) if (producing(l)) { const c = tierOf(l).cost, n = S.prod.filter(p => p.lines.includes(l.key)).length * (mix[l.key] || 0); for (const r of R) tgt[r] += (c[r] || 0) / unitTime(l) * n * 60; }
    if (B.farm) tgt.wood += S.farmNeed * B.farm.cost.wood + 50;
    if (M.pasture) tgt.wood += S.pastureNeed * (B.pasture.cost.wood || 0);
    if (M.cattle && P.cattle) tgt.gold += cattleDemand() * M.cattle.cost.gold;
    // producerWood: while every producer is busy and more are allowed, gather the wood the next production building needs
    // (otherwise food can bank while wood never reaches the auto-production threshold below).
    if (P.producerWood && mainProducer && B[mainProducer] && S.age >= P.armyAge && pop() + 10 < POP_MAX && S.prod.length && S.prod.every(x => x.timer > 0)
      && S.prod.filter(p => !p.name.startsWith("landmark")).length < P.maxProducers) tgt.wood += (B[mainProducer].cost.wood || 0) + 100;
    return tgt;
  }
  function shares() {
    const tgt = targets(); const def = {}; let tot = 0;
    for (const r of R) { def[r] = canGather(r) ? Math.max(0, tgt[r] - S.res[r]) : 0; tot += def[r]; }
    const lr = S.age === 1 ? DARK : longRun(); if (!canGather("stone")) lr.stone = 0;
    if (tot < 1) { const n = sum(lr); return Object.fromEntries(R.map(r => [r, lr[r] / n])); }
    const sh = {}; let n = 0; for (const r of R) { sh[r] = 0.8 * def[r] / tot + 0.2 * lr[r]; n += sh[r]; } for (const r of R) sh[r] /= n; return sh;
  }
  // Flow first: villagers that keep continuous production running (Town Center queues below the villager target, every
  // producing military building) are placed before the plan-window deficits share the rest (engine.js shares).
  function foodRate() {
    for (const src of NATURAL) if (S.stock[src] > 0 && hasDropoff(src) && (src !== "berriesFar" || armyDone() >= P.escortUnits)) return src === "sheep" ? sheepGroupRate(8) / 8 : rEff(src, sourceDistance(src));
    if (M.cattle && S.cattle.herd > 0) return rEff("cattle", M.cattle.distance ?? 0.5);
    return M.pasture ? rEff("pasture", pastureD()) : rEff("farm", 0.33) * farmNear();
  }
  function flowNeed() {
    const o = zero();
    if (S.V < vt() && pop() < S.popcap) { const c = villagerCost(); for (const r of R) o[r] += (c[r] || 0) * S.tcTimer.length / villagerTime(); }
    if (!savingForAge() && pop() < POP_MAX) for (const l of lines) if (producing(l)) { const c = tierOf(l).cost, n = S.prod.filter(p => p.lines.includes(l.key)).length * (mix[l.key] || 0); for (const r of R) o[r] += (c[r] || 0) * n / unitTime(l); }
    return o;
  }
  function allocate() {
    const g = Math.max(0, completedV() - S.builders), flow = flowNeed(), pas = S.lastPassive || zero(), g0 = gm();
    // bankAware (seconds, opt-in): a resource whose bank already covers that many seconds of its production flow needs fewer
    // flow workers (linear taper to none), so a banked resource stops drawing villagers from the scarce ones.
    if (P.bankAware > 0) for (const r of R) if (flow[r] > 0) flow[r] *= Math.max(0, 1 - S.res[r] / (flow[r] * P.bankAware));
    const rate = { food: foodRate() * g0, wood: rEff("wood", sourceDistance("wood") ?? P.map.wood_d) * g0, gold: rEff("gold", sourceDistance("gold") ?? P.map.gold_d) * g0, stone: rEff("stone", sourceDistance("stone") ?? P.map.stone_d) * g0 };
    const need = R.map(r => canGather(r) && (r === "food" || hasDropoff(r)) && rate[r] > 0 ? Math.max(0, flow[r] - pas[r]) / rate[r] : 0);
    const needTot = need.reduce((a, b) => a + b, 0), f = needTot > g ? g / needTot : 1, fixed = need.map(n => n * f), rest = g - fixed.reduce((a, b) => a + b, 0);
    const sh = shares(), raw = R.map((r, i) => fixed[i] + rest * sh[r]), k = raw.map(Math.floor);
    if (P.debugAlloc) P.debugAlloc({ t: S.t, g, flow, need, sh, raw, rate });
    let left0 = g - k.reduce((a, b) => a + b, 0); const order = R.map((r, i) => i).sort((a, b) => (raw[b] - k[b]) - (raw[a] - k[a]));
    for (const i of order) { if (left0 <= 0) break; k[i]++; left0--; }
    const [kf, kw, kg, ks] = k;
    const a = { sheep: 0, berries: 0, deer: 0, berriesFar: 0, farm: 0, pasture: 0, cattle: 0, wood: kw, gold: kg, stone: ks, spare: 0, kf, idle: 0 };
    let left = kf;
    const capOf = { sheep: 24, berries: 16, deer: 8 * P.map.deerPacks, berriesFar: 8 * P.map.berriesFar[0] };
    for (const src of NATURAL) { if (left <= 0 || S.stock[src] <= 0 || !hasDropoff(src)) continue; if (src === "berriesFar" && armyDone() < P.escortUnits) continue; const n = Math.min(left, capOf[src]); a[src] = n; left -= n; }
    if (left > 0 && M.cattle && S.cattle.herd > 0) { const n = Math.min(left, S.cattle.herd * 4); a.cattle = n; left -= n; }
    if (left > 0 && M.pasture) { const r = rEff("pasture", pastureD()) * gm(); const fit = Math.floor(S.pastures * pastureCapacity() / Math.max(r, 1e-9) + 1e-9); a.pasture = Math.min(left, fit); left -= a.pasture; a.spare = left; }
    else if (left > 0) { a.farm = Math.min(left, S.farms); a.spare = left - a.farm; }
    if (a.spare) a.wood += a.spare;
    for (const resource of ["wood", "gold", "stone"]) if (!hasDropoff(resource) || !canGather(resource)) { a.idle += a[resource]; a[resource] = 0; }
    return a;
  }
  function rates(a) {
    const g = gm(), inc = zero();
    if (a.sheep) inc.food += sheepGroupRate(Math.min(a.sheep, 8)) * (a.sheep / Math.min(a.sheep, 8)) * g;
    if (a.berries) inc.food += a.berries * rEff("berries", sourceDistance("berries")) * g;
    if (a.deer) inc.food += a.deer * rEff("deer", sourceDistance("deer")) * g;
    if (a.berriesFar) inc.food += a.berriesFar * rEff("berriesFar", sourceDistance("berriesFar")) * g;
    if (a.farm) inc.food += (hook("farmRate", a.farm) ?? a.farm * rEff("farm", 0.33) * farmNear()) * g;
    if (a.pasture) inc.food += Math.min(a.pasture * rEff("pasture", pastureD()) * g, S.pastures * pastureCapacity());
    if (a.cattle) inc.food += a.cattle * rEff("cattle", M.cattle?.distance ?? 0.5) * g;
    for (const r of ["wood", "gold", "stone"]) if (a[r]) inc[r] += a[r] * rEff(r, sourceDistance(r)) * g;
    return inc;
  }
  function passive(inc) {
    const o = zero();
    for (const m of modsOf("passive_income")) if (m.op === "add" && R.includes(m.target)) o[m.target] += m.value;
    if (M.pitMine && S.pitMines) { const n = Math.min(S.houses + (S.bld["mining-camp"] || 0), P.mech.pitHouses ?? 8); o.gold += S.pitMines * M.pitMine.goldPerSecond * (1 + M.pitMine.perHouse * n); }
    if (M.ranch && S.cattle.ranched) o.food += S.cattle.ranched * M.ranch.foodPerSecond * mulOf("gather_rate", ["food", "food_soft", "ranch"]);
    if (M.corral && S.corralBuilt) o.food += (S.cattle.ranched + S.cattle.herd) * M.corral.foodPerSecond;
    if (M.ovoo && S.ovoo && S.ovooStone > 0) { const r = Math.min(S.ovooStone, M.ovoo.stonePerSecondByAge[S.age] || 0); o.stone += r; S.ovooStone -= r; }
    if (S.yori) { const y = M.yorishiro; o.food += S.yori.farmhouse * y.farmhouseFood; o.wood += S.yori.lumber * y.lumberWood; o.gold += S.yori.forge * y.forgeGold; }
    if (M.silverMining && inc) { o.stone += inc.gold * M.silverMining.fraction; o.gold += inc.stone * M.silverMining.fraction; }
    hook("passive", o, inc);
    return o;
  }
  function income(a) {
    a = a || allocate(); S.lastAlloc = a; S.farmNeed = B.farm ? a.spare : 0;
    S.pastureNeed = M.pasture ? Math.ceil(a.spare * rEff("pasture", pastureD()) * gm() / Math.max(pastureCapacity(), 1e-9)) : 0;
    const inc = rates(a), g = gm();
    for (const src of NATURAL) { if (!a[src]) continue; let rate = src === "sheep" ? sheepGroupRate(Math.min(a.sheep, 8)) * (a.sheep / Math.min(a.sheep, 8)) : a[src] * rEff(src, sourceDistance(src)); rate *= g; const take = Math.min(rate, S.stock[src]); S.stock[src] -= take; if (take < rate) inc.food -= rate - take; }
    if (a.cattle) { const rate = a.cattle * rEff("cattle", M.cattle?.distance ?? 0.5) * g, avail = S.cattle.herd * M.cattle.food - S.cattle.eaten; const take = Math.min(rate, Math.max(0, avail)); S.cattle.eaten += take; while (S.cattle.eaten >= M.cattle.food - 1e-9 && S.cattle.herd > 0) { S.cattle.eaten -= M.cattle.food; S.cattle.herd--; } if (take < rate) inc.food -= rate - take; }
    if (!P.lite && S.ecoTracked.length) { const tot = sum(inc); for (const k of S.ecoTracked) { const rec = S.techRec[k]; if (!rec || rec.payback != null) continue; const without = withoutTech(k, () => sum(rates(a))); rec.gain = (rec.gain || 0) + (tot - without); if (rec.gain >= rec.paid) rec.payback = S.t; } }
    return inc;
  }
  function withoutTech(k, fn) { const keep = S.mods; S.mods = S.mods.filter(m => m.source !== "tech:" + k); S.modsVersion++; const v = fn(); S.mods = keep; S.modsVersion++; return v; }

  // ----- costs and times with active effects
  const villagerCost = () => priced(spec.villager.cost, "villager", "villager");
  const tcYori = () => S.yori && S.yori.tc ? 1 + (M.yorishiro.tcProduction - 1) * Math.min(1, S.yori.tc / S.tcTimer.length) : 1;
  const villagerTime = () => spec.villager.time / ((spec.tc.prodByAge?.[S.age] || 1) * mulOf("production_speed", ["town-center"]) * tcYori());
  const unitTime = l => tierOf(l).time / mulOf("production_speed", [...l.producers, "military", "line:" + l.key]);
  const stoneMult = () => mulOf("cost", ["double-stone"]);
  const doubleCost = c => { const o = Object.assign(zero(), c); o.stone *= stoneMult(); return o; };

  // ----- actions
  function startBuild(name, builders, why, site) {
    const b = B[name]; if (!b) return false;
    const pc = priced(b.cost, "building", name);
    if (b.age && S.age < b.age) return false;
    if (!can(pc) || completedV() - S.builders < builders) return false;
    pay(pc, b.eco ? "buildings_eco" : "buildings_prod"); S.builders += builders;
    S.jobs.push({ name, left: buildTime(b.time, builders) / mulOf("build_speed", ["all", name]), builders, site, start: S.t });
    ev("build", "building", site ? `${b.name} at ${site}` : b.name, why, `start, ${builders} builder(s)`, pc, { entity: name, source: site, pbgid: b.pbgid });
    return true;
  }
  function finishBuild(name, site) {
    const b = B[name];
    if (site === "berriesFar") { S.farMills++; S.dropoffs[site] = S.farMills >= P.map.berriesFar[0]; } else if (site) S.dropoffs[site] = true;
    if (name === "farm") S.farms++; else S.bld[name] = (S.bld[name] || 0) + 1;
    if (name === "pasture") S.pastures++;
    if (name === "pit-mine") S.pitMines++;
    if (name === "cattle-ranch") S.ranches++;
    if (name === "ovoo") S.ovoo++;
    if (name === "town-center") { S.tcTimer.push(0); S.tcBatch.push(0); S.popcap = Math.min(POP_MAX, S.popcap + (M.noHouses ? 0 : spec.tc.pop)); mark("tc" + S.bld[name]); }
    if (b.pop && !M.noHouses) { if (b.house) S.houses++; S.popcap = Math.min(POP_MAX, S.popcap + b.pop); }
    if (producerKeys.includes(name)) S.prod.push({ name, idx: S.prod.filter(p => p.name === name).length, timer: 0, line: null, batch: 0, lines: lines.filter(l => l.producers.includes(name)).map(l => l.key) });
    ev("done", "building", site ? `${b.name} at ${site}` : b.name, "build complete", b.note || "", null, { entity: name, source: site, pbgid: b.pbgid });
    hook("finishBuild", name, site);
  }
  function startLandmark(key) {
    const L = lmByKey(key); const pc = priced(L.cost, "age", key), n = P.lmBuilders[S.age + 1] || 4;
    if (!can(pc) || completedV() - S.builders < n) return false;
    pay(pc, "ages"); S.builders += n;
    S.jobs.push({ name: "landmark", key, left: buildTime(L.time, n) / mulOf("build_speed", ["all", "landmark"]), builders: n, start: S.t, age: S.age + 1 });
    ev("age", "age", `${AGE[S.age + 1]} via ${L.name}`, "landmark cost reached", `start, ${n} builder(s)`, pc, { entity: key, pbgid: L.pbgid });
    return true;
  }
  function grant(k, why) {
    if (!T[k] || S.techs.has(k)) return;
    S.techs.add(k); Object.assign(S.techRec[k], { start: S.t, end: S.t, paid: 0, costPaid: zero(), duration: 0, free: true }); addEffects(T[k].effects, "tech:" + k); removePlan("t", k); mark(k);
    if (T[k].tierOf && S.tier[T[k].tierOf] != null) S.tier[T[k].tierOf] = Math.max(S.tier[T[k].tierOf], T[k].tierIndex);
    ev("done", T[k].cat, T[k].name, why, "", null, { pbgid: T[k].pbgid, tech: k, free: true });
  }
  function finishLandmark(job) {
    const L = lmByKey(job.key); S.age = job.age; S.landmarks.push(job.key); mark("age" + S.age);
    addEffects(L.effects, "landmark:" + job.key);
    for (const k of (spec.ageUpGrants?.[S.age] || [])) grant(k, `granted on reaching ${AGE[S.age]}`);
    if (L.producer) S.prod.push({ name: "landmark:" + job.key, idx: 0, timer: 0, line: null, batch: 0, lines: lines.filter(l => (L.producer.lines || []).includes(l.key)).map(l => l.key) });
    if (L.corral) S.corralBuilt = true;
    if (L.yorishiro && M.yorishiro) { S.yori = { n: 0, next: S.t, farmhouse: 0, lumber: 0, forge: 0, tc: 0 }; }
    if (L.kura && M.kura) S.kuraNext = S.t + M.kura.farmInterval;
    hook("finishLandmark", job, L);
    ev("done", "age", AGE[S.age], `${L.name} complete`, L.note || "", null, { entity: job.key, pbgid: L.pbgid, keep: true });
  }
  function techBuildingCount(b) { if (!b) return 1; if (b.startsWith("landmark:")) return S.landmarks.includes(b.slice(9)) ? 1 : 0; if (b === "town-center") return S.tcTimer.length; return (S.bld[b] || 0); }
  // The researchable copy of a technology: the landmark copy once its landmark stands (cheaper, ignores age), the Improved
  // copy when the plan asks for Improved technologies and an Ovoo stands, otherwise the technology itself.
  function variantFor(name) {
    const t = T[name], opts = [];
    for (const v of t.variants || []) { const x = T[v]; if (x.landmark && S.landmarks.includes(x.landmark)) opts.push(v); else if (x.improved && P.mech.improved && S.ovoo) opts.unshift(v); }
    opts.push(name);
    return opts.find(k => S.age >= T[k].age && techBuildingCount(T[k].building) > 0) || null;
  }
  function tryItem(kind, name, site) {
    if (kind === "b") { if (name === "town-center" && S.age < 2) return false; return startBuild(name, name === "town-center" ? P.tcBuilders : 1, "next plan item affordable", site); }
    if (kind === "age") return !S.jobs.some(j => j.name === "landmark") && startLandmark(name);
    if (kind === "x") return !!hook("tryItem", name, site);
    const base = T[name]; if (!base || S.techs.has(name)) { removePlan("t", name); return false; }
    if ((base.requires || []).some(q => !S.techs.has(q))) return false;
    const k = variantFor(name); if (!k) return false;
    const t = T[k];
    if (S.research.filter(r => r.building === t.building).length >= techBuildingCount(t.building)) return false;
    const pc = priced(t.cost, "tech", k); if (!can(pc)) return false;
    const dur = t.time / mulOf("research_speed", ["all", t.building]);
    pay(pc, t.cat === "economy" || t.cat === "civ-economy" ? "techs_eco" : "techs_mil"); S.research.push({ building: t.building, name: k, group: name, left: dur, start: S.t });
    for (const id of new Set([k, name])) Object.assign(S.techRec[id], { start: S.t, paid: sum(pc), costPaid: pc, duration: dur, via: k !== name ? k : undefined });
    ev("tech", t.cat, t.name, "building free and cost reached", `research start (${Math.round(dur)} s)`, pc, { pbgid: t.pbgid, tech: name });
    return true;
  }
  function tryPlan() {
    const ai = plan.findIndex(x => x[0] === "age");
    if (ai >= 0 && !plan.slice(0, ai).some(x => x[0] === "b") && tryItem("age", plan[ai][1])) { plan.splice(ai, 1); return; }
    for (const [kind, name, site] of plan.slice(0, P.window)) { if (kind === "age") break; if (tryItem(kind, name, site)) { const i = plan.findIndex(x => x[0] === kind && x[1] === name && x[2] === site); if (i >= 0) plan.splice(i, 1); return; } }
  }
  // Army production pauses to save for the next landmark when the plan's next item is that landmark (pauseForAge), or from a
  // chosen time per age (pauseFrom: {3: seconds}) until the landmark is started.
  const savingForAge = () => {
    if (S.jobs.some(j => j.name === "landmark") || S.age >= 4) return false;
    if (P.pauseForAge && plan.length && plan[0][0] === "age") return true;
    const from = P.pauseFrom?.[S.age + 1]; return Number.isFinite(from) && S.t >= from && plan.some(x => x[0] === "age");
  };

  // ----- civilization mechanics that run every second
  function cattleDemand() { if (!M.cattle || !P.cattle) return 0; const slots = S.ranches * (M.ranch?.slots || 3); return Math.max(0, slots - S.cattle.ranched - S.cattle.training) + Math.max(0, (P.cattle.herdTarget || 0) - S.cattle.herd); }
  function cattleStep() {
    if (!M.cattle || !P.cattle) return;
    const producers = (M.cattle.producers || ["mill"]).reduce((s, k) => s + (S.bld[k] || 0), 0);
    while (S.cattleTimers.length < producers) S.cattleTimers.push(0);
    const live = () => S.cattle.herd + S.cattle.ranched + S.cattle.training;
    for (let i = 0; i < S.cattleTimers.length; i++) {
      if (S.cattleTimers[i] > 0) { S.cattleTimers[i]--; if (S.cattleTimers[i] <= 0) { S.cattle.training--; S.cattle.bought++; const slots = S.ranches * (M.ranch?.slots || 3); const toRanch = S.cattle.ranched < slots && P.cattle.ranch !== false; if (toRanch) S.cattle.ranched++; else S.cattle.herd++; ev("done", "unit", M.cattle.name || "Cattle", "training complete", toRanch ? "garrisoned in a Cattle Ranch" : "herded for villagers", null, { pbgid: M.cattle.pbgid, producer: "cattle", queue: i, count: 1 }); } continue; }
      if (S.age < (P.cattle.age || 1) || S.t < (P.cattle.from || 0) || live() >= (M.cattle.cap || 20)) continue;
      if (cattleDemand() <= 0) continue;
      const c = priced(M.cattle.cost, "unit", "cattle"); if (!can(c)) continue;
      pay(c, "units"); S.cattleTimers[i] = M.cattle.time; S.cattle.training++;
      ev("train", "unit", M.cattle.name || "Cattle", "ranch slot or herd target open", "training started", c, { pbgid: M.cattle.pbgid, producer: "cattle", queue: i, count: 1, duration: Math.ceil(S.cattleTimers[i]), readyAt: S.t + Math.ceil(S.cattleTimers[i]) });
    }
    const want = isObj(P.cattle.ranches) ? (P.cattle.ranches[S.age] || 0) : (P.cattle.ranches || 0);
    if (B["cattle-ranch"] && S.ranches + S.jobs.filter(j => j.name === "cattle-ranch").length < want && S.age >= (B["cattle-ranch"].age || 1)) startBuild("cattle-ranch", 1, "ranch target");
  }
  function pitMineStep() {
    if (!M.pitMine || !B["pit-mine"]) return;
    const want = isObj(P.mech.pitMines) ? (P.mech.pitMines[S.age] || 0) : (P.mech.pitMines ?? 0);
    if (S.pitMines + S.jobs.filter(j => j.name === "pit-mine").length < Math.min(want, M.pitMine.limit || 99)) startBuild("pit-mine", 1, "pit mine target");
  }
  function yoriStep() {
    if (!S.yori) return;
    const y = M.yorishiro, cap = y.cap + (S.techs.has(y.bunrei) ? y.bunreiAdd : 0);
    if (S.yori.n >= cap || S.t < S.yori.next) return;
    const order = P.mech.yorishiro || ["farmhouse", "lumber", "forge", "tc"];
    const room = { farmhouse: S.bld[spec.house] || 0, lumber: S.bld["lumber-camp"] || 0, forge: S.bld.forge || 0, tc: S.tcTimer.length };
    const target = order.find((k, i) => order.slice(0, i + 1).filter(x => x === k).length > S.yori[k] && S.yori[k] < room[k]);
    if (!target) return;
    S.yori[target]++; S.yori.n++; S.yori.next = S.t + y.interval;
    ev("done", "economy", "Yorishiro", `Shinto Priest from the Floating Gate placed in a ${target === "tc" ? "Town Center" : target === "lumber" ? "Lumber Camp" : target === "forge" ? "Forge" : "Farmhouse"}`, "", null, { entity: "yorishiro" });
  }
  function kuraStep() { if (S.kuraNext == null || S.t < S.kuraNext || S.freeFarms >= (P.mech.kuraFarms ?? 8)) return; S.farms++; S.freeFarms++; S.kuraNext = S.t + M.kura.farmInterval; ev("done", "building", "Farm", "free farm from the Kura Storehouse", "", null, { entity: "farm", pbgid: B.farm?.pbgid }); }

  // ----- step
  function applyVillagerLosses() {
    if (!P.villagerLossPerMinute || S.t <= P.villagerLossStart) return;
    const due = Math.floor((S.t - P.villagerLossStart) * P.villagerLossPerMinute / 60 + 1e-9), attempts = due - S.lossAttempts; S.lossAttempts = due;
    const eligible = Math.max(0, S.V - S.builders - trainees());
    for (let i = 0; i < Math.min(attempts, eligible); i++) { S.V--; S.villagersLost++; ev("loss", "unit", "Villager lost", "assumed economic attrition", "worker removed; replacement uses normal Town Center production", null, { count: 1, villagersLost: S.villagersLost, pbgid: spec.villager.pbgid }); }
  }
  function step() {
    applyVillagerLosses();
    if (!hasDropoff("berriesFar") && S.stock.sheep <= 0 && S.stock.berries <= 0 && armyDone() >= P.escortUnits && !S.jobs.some(j => j.site === "berriesFar") && B[role.berriesFar]) startBuild(role.berriesFar, 1, "prepare remote berry drop-off", "berriesFar");
    const a0 = allocate();
    if (!P.lite) { const allocation = workerState(a0), key = JSON.stringify(allocation); if (key !== S.allocationKey) { S.allocationKey = key; ev("assign", "economy", "Worker reassignment", "resource targets and available workers changed", "Expected worker allocation", null, allocation); } }
    const inc = income(a0), pas = passive(inc); S.lastInc = inc; S.lastPassive = pas;
    for (const r of R) { S.res[r] += inc[r] + pas[r]; S.gathered[r] += inc[r]; S.passiveGot[r] += pas[r]; }
    if (!M.noHouses && spec.house && S.popcap < POP_MAX) {
      const pending = S.jobs.filter(j => j.name === spec.house).length, growth = 3 * S.tcTimer.length + 2 * S.prod.length;
      if (pop() + growth >= S.popcap + pending * B[spec.house].pop && pending < 3) startBuild(spec.house, 1, "pop cap within reach of production");
    }
    tryPlan();
    cattleStep(); pitMineStep(); yoriStep(); kuraStep(); hook("step");
    // auto production: income outruns the producers
    const autoProd = P.lineMix ? (() => { const c = {}; for (const q of S.prod) if (!q.name.startsWith("landmark")) c[q.name] = (c[q.name] || 0) + 1; for (const jb of S.jobs) if (producerKeys.includes(jb.name)) c[jb.name] = (c[jb.name] || 0) + 1; return pickProducer(c); })() : mainProducer;
    if (autoProd && B[autoProd] && S.age >= P.armyAge && S.prod.length >= (P.producers[S.age] || 0) && S.prod.length && S.prod.filter(p => !p.name.startsWith("landmark")).length < P.maxProducers && !S.jobs.some(j => j.name === autoProd) && !plan.some(x => x[1] === autoProd)
      && S.prod.every(x => x.timer > 0) && lines.every(l => can(times(tierOf(l).cost, 3))) && S.res.wood >= B[autoProd].cost.wood + 100 && pop() + 10 < POP_MAX) startBuild(autoProd, 1, "resources banking while every producer is busy");
    if (B.farm) { let need = S.farmNeed - S.jobs.filter(j => j.name === "farm").length; while (need-- > 0 && startBuild("farm", 1, "food workers need a completed farm")) { /* each plot reserves a builder */ } }
    if (M.pasture) { let need = S.pastureNeed - S.jobs.filter(j => j.name === "pasture").length; while (need-- > 0 && startBuild("pasture", 1, "food workers need pasture sheep")) { /* each pasture reserves a builder */ } }
    // villagers (Mongol Town Centers inside Ovoo influence can train two at once for stone)
    const vc = villagerCost(), dv = P.mech.doubleVillagers && S.ovoo && M.double?.villager ? doubleCost(M.double.villager) : null;
    const ownVillagers = hook("villagers");
    for (let i = 0; !ownVillagers && i < S.tcTimer.length; i++) {
      if (S.tcTimer[i] > 0) { S.tcTimer[i] = Math.max(0, S.tcTimer[i] - 1); if (!S.tcTimer[i]) { ev("done", "unit", "Villager", "training complete", "worker available", null, { producer: "town-center", queue: i, count: S.tcBatch[i], pbgid: spec.villager.pbgid }); S.tcBatch[i] = 0; } continue; }
      if (S.V >= vt() || pop() >= S.popcap) continue;
      const two = dv && S.V + 2 <= vt() && pop() + 2 <= S.popcap && can(dv);
      const c = two ? dv : vc; if (!can(c)) continue;
      pay(c, "villagers"); S.tcTimer[i] = villagerTime(); S.tcBatch[i] = two ? 2 : 1; S.V += S.tcBatch[i];
      ev("train", "unit", "Villager", two ? "Town Center queue free; double production inside the Ovoo influence" : "Town Center queue free and food available", "training started", c, { producer: "town-center", queue: i, count: S.tcBatch[i], duration: Math.ceil(S.tcTimer[i]), readyAt: S.t + Math.ceil(S.tcTimer[i]), pbgid: spec.villager.pbgid });
    }
    // army
    const busy = {}; for (const r of S.research) busy[r.building] = (busy[r.building] || 0) + 1;
    for (const p of S.prod) {
      if (p.timer > 0) { p.timer = Math.max(0, p.timer - 1); if (!p.timer) { const l = lines.find(x => x.key === p.line), a = S.army[p.line]; a.training -= p.batch; a.count += p.batch; a.produced += p.batch; S.unitsProduced += p.batch; ev("done", "unit", tierOf(l).name, "training complete", "unit available", null, { producer: p.name, queue: p.idx, count: p.batch, pbgid: tierOf(l).pbgid, line: l.key }); if (a.produced <= p.batch) mark("first_" + l.key); mark("first_unit"); p.batch = 0; } continue; }
      if (busy[p.name] > 0) { busy[p.name]--; continue; }
      if (savingForAge()) continue;
      // A line with no share in the plan's mix is never trained (e.g. Border Reivers that only come from a muster).
      const cands = p.lines.map(k => lines.find(l => l.key === k)).filter(l => producing(l) && (mix[l.key] || 0) > 0);
      if (!cands.length) continue;
      const totalArmy = cands.reduce((s, l) => s + S.army[l.key].count + S.army[l.key].training, 0) + 1;
      const l = cands.sort((x, y) => ((S.army[x.key].count + S.army[x.key].training) / totalArmy - (mix[x.key] || 0)) - ((S.army[y.key].count + S.army[y.key].training) / totalArmy - (mix[y.key] || 0)))[0];
      const u = tierOf(l), single = priced(u.cost, "unit", l.key), pair = P.mech.doubleArmy && S.ovoo && u.doubleCost ? doubleCost(u.doubleCost) : null;
      const room = Math.min(POP_MAX, S.popcap) - pop();
      const two = pair && room >= 2 * u.pop && can(pair);
      if (!two && !(room >= u.pop && can(single))) continue;
      const c = two ? pair : single; pay(c, "units"); p.timer = unitTime(l) / (p.mult || 1); p.line = l.key; p.batch = two ? 2 : 1; S.army[l.key].training += p.batch;
      ev("train", "unit", u.name, two ? "producer free; double production inside the Ovoo influence" : "producer free and resources available", "training started", c, { producer: p.name, queue: p.idx, count: p.batch, duration: Math.ceil(p.timer), readyAt: S.t + Math.ceil(p.timer), pbgid: u.pbgid, line: l.key });
    }
    // timers
    for (const j of [...S.jobs]) { if (j.start === S.t) continue; j.left--; if (j.left <= 0) { S.jobs.splice(S.jobs.indexOf(j), 1); S.builders -= j.builders; if (j.name === "landmark") finishLandmark(j); else finishBuild(j.name, j.site); } }
    for (const r of [...S.research]) { if (r.start === S.t) continue; r.left--; if (r.left <= 0) { S.research.splice(S.research.indexOf(r), 1); finishTech(r.name, r.group); } }
    updateAvailability();
    if (completedV() >= S.vMark + 20) { S.vMark = Math.floor(completedV() / 20) * 20; ev("vil", "production", `${completedV()} villagers`, "continuous TC production", `${S.tcTimer.length} TCs`); }
    if (armyDone() >= S.aMark + 20) { S.aMark = Math.floor(armyDone() / 20) * 20; ev("army", "production", `${armyDone()} ${lines.map(l => tierOf(l).name).join(" and ")}`, "continuous production", `${S.prod.length} producers`); }
    S.t++;
    if (S.t % 60 === 0) snapshot();
  }
  function finishTech(name, group) {
    const t = T[name];
    for (const id of new Set([name, group || name])) { S.techs.add(id); S.techRec[id].end = S.t; mark(id); }
    addEffects(t.effects, "tech:" + name);
    for (const e of t.effects || []) if (e.kind === "farm_aura") S.aura = Math.max(S.aura, e.value);
    if (t.freeVillagers && pop() + t.freeVillagers <= POP_MAX) { S.V += t.freeVillagers; ev("done", "unit", "Villager", `free villager from ${t.name}`, "worker available", null, { producer: "town-center", count: t.freeVillagers, pbgid: spec.villager.pbgid }); }
    const tg = T[group || name];
    if (tg.tierOf && S.tier[tg.tierOf] != null) S.tier[tg.tierOf] = Math.max(S.tier[tg.tierOf], tg.tierIndex);
    if (t.cat === "economy" || t.cat === "civ-economy") S.ecoTracked.push(name);
    hook("finishTech", name, group);
    ev("done", t.cat, t.name, "research complete", t.note || "", null, { pbgid: t.pbgid, tech: group || name });
  }
  function updateAvailability() { for (const k in T) { const rec = S.techRec[k]; if (rec.available != null) continue; const t = T[k]; if (S.age >= t.age && techBuildingCount(t.building) > 0) rec.available = S.t; } }
  function unitRows() {
    const rows = [{ pbgid: spec.villager.pbgid, name: "Villager", balance: completedV(), produced: completedV() + S.villagersLost - spec.start.villagers, lost: S.villagersLost }];
    for (const l of lines) { const a = S.army[l.key]; if (a.count > 0) rows.push({ pbgid: tierOf(l).pbgid, name: tierOf(l).name, balance: a.count, produced: a.produced, lost: 0, line: l.key }); }
    for (const u of spec.start.units || []) rows.push({ pbgid: u.pbgid, name: u.name, balance: u.count, produced: 0, lost: 0 });
    return rows;
  }
  // Army strength (Sam, 2026-10-28): unit value scaled by the age of the unit's current tier (x1 Dark/Feudal, x1.5 Castle, x2 Imperial) plus
  // completed military technologies at cost with the same age scale; veterancy (unit-tier) upgrades are excluded.
  const ageScale = a => a >= 4 ? 2 : a >= 3 ? 1.5 : 1;
  const armyStrength = () => lines.reduce((s, l) => s + S.army[l.key].count * sum(tierOf(l).cost) * ageScale(tierOf(l).age), 0)
    + [...S.techs].filter(k => T[k] && T[k].cat === "military").reduce((s, k) => s + sum(T[k].cost) * ageScale(T[k].age), 0);
  function snapshot() {
    const a = allocate(), g = gm(), ws = workerState(a);
    const perVil = { farm: rEff("farm", 0.33) * g * farmNear(), berries: rEff("berries", P.map.berries[2]) * g, sheep: rEff("sheep", 0) * g, wood: rEff("wood", P.map.wood_d) * g, gold: rEff("gold", P.map.gold_d) * g };
    if (M.pasture) perVil.pasture = rEff("pasture", pastureD()) * g; if (M.cattle) perVil.cattle = rEff("cattle", M.cattle.distance ?? 0.5) * g;
    S.minutes.push({ t: S.t, vil: completedV(), villagersLost: S.villagersLost, army: armyDone(), armyByLine: Object.fromEntries(lines.map(l => [l.key, S.army[l.key].count])), pop: pop(), farms: S.farms, pastures: S.pastures, houses: S.houses, age: S.age, tcs: S.tcTimer.length, stables: S.prod.length, producers: S.prod.length, blacksmiths: S.bld[spec.blacksmith] || 0, builders: S.builders,
      split: ws.split, sources: ws.sources, produced: S.unitsProduced - S.producedAtMinute, stockLeft: { sheep: Math.round(S.stock.sheep), berries: Math.round(S.stock.berries), deer: Math.round(S.stock.deer), farBerries: Math.round(S.stock.berriesFar) },
      income: Object.fromEntries(R.map(r => [r, Math.round(S.gathered[r])])), algebra: Object.fromEntries(R.map(r => [r, Math.round(S.passiveGot[r])])),
      stock: Object.fromEntries(R.map(r => [r, Math.round(S.res[r])])), spent: Object.fromEntries(R.map(r => [r, Math.round(S.spent[r])])), spentCat: Object.fromEntries(Object.entries(S.spentCat).map(([k, v]) => [k, Math.round(v)])),
      perVil: Object.fromEntries(Object.entries(perVil).map(([k, v]) => [k, +(60 * v).toFixed(1)])), gatherMult: +g.toFixed(3), techs: [...S.techs].filter(k => !T[k]?.groupOf).length, unitsProduced: S.unitsProduced,
      armyValue: lines.reduce((s, l) => s + S.army[l.key].count * sum(tierOf(l).cost), 0), armyStrength: Math.round(armyStrength()), unitCounts: unitRows(),
      cattle: M.cattle ? { herd: S.cattle.herd, ranched: S.cattle.ranched, bought: S.cattle.bought } : undefined, ranches: M.cattle ? S.ranches : undefined, pitMines: M.pitMine ? S.pitMines : undefined,
      yorishiro: S.yori ? S.yori.n : undefined, ovooStone: M.ovoo ? Math.round(S.ovooStone) : undefined, landmarks: [...S.landmarks] });
    hook("snapshot", S.minutes[S.minutes.length - 1]);
    S.gathered = zero(); S.passiveGot = zero(); S.producedAtMinute = S.unitsProduced;
    if (!P.lite) for (const n in S.techRec) { const r = S.techRec[n]; if (r.start != null) { r.gainAt = r.gainAt || {}; r.gainAt[S.t] = Math.round(r.gain || 0); } }
  }
  ctx = { S, P, spec, M, B, T, R, AGE, POP_MAX, lines, lineKeys, mix, plan, role, zero, sum, times, buildTime, can, pay, priced, ev, mark, addEffects, mulOf, addOf, rEff, gm,
    pop, trainees, completedV, armyDone, armyPopDone, tierOf, villagerCost, villagerTime, unitTime, startBuild, grant, removePlan, lmByKey, lm, savingForAge, producing, hasDropoff,
    sourceDistance, techBuildingCount, costOf, allocate, vt };
  hook("init");
  snapshot();
  while (S.t < P.tmax) {
    step();
    const allTech = lineTechs.every(k => S.techs.has(k)); if (allTech) mark("all_line_techs");
    if (pop() >= 150) mark("pop150");
    if (pop() >= POP_MAX) mark("pop200");
    if (allTech && completedV() + armyPopDone() + S.others >= POP_MAX) { mark("DONE"); if (S.t % 60) { const last = S.minutes[S.minutes.length - 1], scale = 60 / (S.t - (last ? last.t : 0)); snapshot(); const f = S.minutes[S.minutes.length - 1]; for (const r of R) { f.income[r] = Math.round(f.income[r] * scale); f.algebra[r] = Math.round(f.algebra[r] * scale); } f.partial = true; } break; }
  }
  for (const n in S.techRec) { const r = S.techRec[n]; if (r.gain != null) r.gain = Math.round(r.gain); }
  const techs = Object.values(S.techRec).filter(r => (r.planned || r.start != null || r.lineTech) && !T[r.name].groupOf);
  const out = { engine: "civ", civilization: spec.key, patch: spec.patch, params: P, milestones: S.milestones, done: S.milestones.DONE, events: S.events, minutes: S.minutes, techs, lineTechs,
    lines: lines.map(l => ({ key: l.key, name: l.name, tiers: l.tiers, producers: l.producers })), remainingPlan: plan, assumptions: spec.assumptions, unmodeled: spec.unmodeled,
    summary: { villagers: completedV(), villagersLost: S.villagersLost, army: armyDone(), armyByLine: Object.fromEntries(lines.map(l => [l.key, S.army[l.key].count])), farms: S.farms, pastures: S.pastures, houses: S.houses, buildings: S.bld, spent: S.spent, spentCat: S.spentCat, banked: S.res, landmarks: S.landmarks } };
  hook("result", out);
  return out;
}
const api = { simulateCiv, DEFAULTS, POP_MAX, rules };
if (typeof module !== "undefined" && module.exports) module.exports = api; else root.AoE4CivEngine = api;
})(typeof window !== "undefined" ? window : globalThis);
