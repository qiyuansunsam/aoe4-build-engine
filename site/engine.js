/* AoE4 Abbasid economy engine, JS port of engine/sim.py + engine/eco.py (patch 16.2.10604).
   Pure cost / rate / time arithmetic at 1 s steps. simulate(params) -> {milestones, events, minutes, techs, done}. */
(function (root) {
"use strict";
const R = ["food", "wood", "gold", "stone"];
const cost = (f = 0, w = 0, g = 0, s = 0) => ({ food: f, wood: w, gold: g, stone: s });

// ---------- game data ----------
const RAW = { sheep: 0.75, farm: 0.75, berries: 0.69, deer: 0.825, wood: 0.75, gold: 0.75, stone: 0.75 };
const FOOD_SOFT = new Set(["sheep", "farm", "berries"]), HUNT = new Set(["deer"]), MINE = new Set(["gold", "stone"]);
const ECO_TECH = { // name: {cls: mult} or carry/speed
  wheelbarrow: { carry: 5, speed: 1.15 }, horticulture: { food_soft: 1.10 }, "double-broadax": { wood: 1.15 }, "specialized-pick": { mine: 1.15 },
  fertilization: { food_soft: 1.10 }, "lumber-preservation": { wood: 1.15 }, "shaft-mining": { mine: 1.15 },
  "precision-cross-breeding": { food_soft: 1.10 }, "crosscut-saw": { wood: 1.15, carry_wood: 5 }, cupellation: { mine: 1.15 },
  "survival-techniques": { hunt: 1.15 },
};
const WING_COST = { 2: cost(400, 0, 200), 3: cost(1200, 0, 600), 4: cost(2400, 0, 1200) }, WING_TIME = 100;
const BLD = { "house-of-wisdom": [cost(0, 50), 30], mill: [cost(0, 50), 20], "lumber-camp": [cost(0, 50), 20], "mining-camp": [cost(0, 50), 20],
  house: [cost(0, 50), 15], "town-center": [cost(0, 400, 0, 300), 150], stable: [cost(0, 150), 30], blacksmith: [cost(0, 150), 25], madrasa: [cost(0, 450), 60], farm: [cost(0, 75), 6] };
const ECO_BLD = new Set(["mill", "lumber-camp", "mining-camp", "house", "farm"]);
const PROD_BLD = new Set(["town-center", "stable", "blacksmith", "madrasa", "house-of-wisdom"]);
// tech: [age, cost, time, building, wing, category]
const TECH = {
  "fresh-foodstuffs": [2, cost(50, 0, 75), 20, "mill", null, "economy"], "fertile-crescent": [2, cost(25, 0, 75), 30, "how", "economic", "wing"],
  wheelbarrow: [1, cost(0, 50, 150), 90, "mill", null, "economy"], horticulture: [2, cost(0, 50, 100), 45, "mill", null, "economy"],
  "double-broadax": [2, cost(50, 0, 100), 45, "lumber-camp", null, "economy"], "specialized-pick": [2, cost(0, 50, 100), 45, "mining-camp", null, "economy"],
  "preservation-of-knowledge": [2, cost(0, 25, 75), 30, "how", "culture", "wing"], "city-planning": [2, cost(0, 25, 75), 30, "how", "admin", "wing"],
  algebra: [3, cost(100, 0, 250), 60, "how", "culture", "wing"], agriculture: [3, cost(0, 75, 200), 45, "how", "economic", "wing"],
  "improved-processing": [4, cost(0, 300, 700), 90, "how", "economic", "wing"],
  bloomery: [2, cost(50, 0, 125), 60, "blacksmith", null, "blacksmith"], "fitted-leatherwork": [2, cost(50, 0, 125), 60, "blacksmith", null, "blacksmith"],
  "iron-undermesh": [2, cost(0, 50, 125), 60, "blacksmith", null, "blacksmith"], decarbonization: [3, cost(100, 0, 250), 60, "blacksmith", null, "blacksmith"],
  "insulated-helm": [3, cost(100, 0, 250), 60, "blacksmith", null, "blacksmith"], "wedge-rivets": [3, cost(0, 100, 250), 60, "blacksmith", null, "blacksmith"],
  "camel-handling": [3, cost(75, 0, 200), 30, "blacksmith", null, "camel"], "military-academy": [3, cost(0, 100, 250), 60, "blacksmith", null, "blacksmith"],
  "camel-rider-shields": [3, cost(75, 0, 200), 45, "stable", null, "camel"],
  fertilization: [3, cost(0, 100, 250), 60, "mill", null, "economy"], "lumber-preservation": [3, cost(100, 0, 250), 60, "lumber-camp", null, "economy"],
  "shaft-mining": [3, cost(0, 100, 250), 60, "mining-camp", null, "economy"],
  "damascus-steel": [4, cost(150, 0, 350), 60, "blacksmith", null, "blacksmith"], "master-smiths": [4, cost(150, 0, 350), 60, "blacksmith", null, "blacksmith"],
  "angled-surfaces": [4, cost(0, 150, 350), 60, "blacksmith", null, "blacksmith"],
  "camel-rider-barding": [4, cost(100, 0, 225), 45, "stable", null, "camel"], "elite-camel-riders": [4, cost(300, 0, 700), 60, "stable", null, "camel"],
  biology: [4, cost(500, 0, 1000), 90, "madrasa", null, "university"],
  "precision-cross-breeding": [4, cost(0, 250, 500), 75, "mill", null, "economy"], "crosscut-saw": [4, cost(250, 0, 500), 75, "lumber-camp", null, "economy"],
  cupellation: [4, cost(0, 250, 500), 75, "mining-camp", null, "economy"],
};
const CAMEL_TECHS = ["bloomery", "fitted-leatherwork", "iron-undermesh", "decarbonization", "insulated-helm", "wedge-rivets", "camel-handling",
  "camel-rider-shields", "damascus-steel", "master-smiths", "angled-surfaces", "camel-rider-barding", "elite-camel-riders", "biology"];
const MIL_TECHS = new Set([...CAMEL_TECHS, "military-academy"]);
const ECO_T2 = ["fertilization", "lumber-preservation", "shaft-mining"], ECO_T3 = ["precision-cross-breeding", "crosscut-saw", "cupellation"];
const GOLDEN_TIERS = [10, 20, 30, 50, 75];
const CAMEL = [cost(130, 45, 45), 35], VIL = [50, 20];
const POP_PER_HOUSE = 10, POP_PER_TC = 10, POP_MAX = 200;
const EFFECT = {
  mill: "food drop-off, orchards +100 food per bush", "lumber-camp": "wood drop-off", "mining-camp": "gold and stone drop-off",
  house: "pop cap +10", "town-center": "villager line +1 (20 s each), pop cap +10", stable: "camel line +1 (35 s each)",
  blacksmith: "research line for blacksmith techs", madrasa: "unlocks Biology", "house-of-wisdom": "age-ups, Golden Age influence",
  "fresh-foodstuffs": "villager 50 -> 30 food", "fertile-crescent": "eco buildings and houses -30%", wheelbarrow: "carry +5, speed +15%",
  horticulture: "food (not hunt) +10%", "double-broadax": "wood +15%", "specialized-pick": "gold/stone +15%",
  "preservation-of-knowledge": "techs and wings -20%", "city-planning": "+8% work rate per adjacent identical building",
  algebra: "HoW yields 3f 3w 2g per military tech / 20 s", agriculture: "farms +15%", "improved-processing": "drop-off +8%",
  bloomery: "melee +1", "fitted-leatherwork": "melee armour +1", "iron-undermesh": "ranged armour +1", decarbonization: "melee +1",
  "insulated-helm": "melee armour +1", "wedge-rivets": "ranged armour +1", "damascus-steel": "melee +1", "master-smiths": "melee armour +1",
  "angled-surfaces": "ranged armour +1", "camel-handling": "camel speed +15%", "camel-rider-shields": "camel melee armour +3",
  "camel-rider-barding": "camel armour +2", "elite-camel-riders": "Elite Camel Rider (320 hp, 16 dmg)", "military-academy": "production 33% faster",
  biology: "cavalry hp +25%", fertilization: "food (not hunt) +10%", "lumber-preservation": "wood +15%", "shaft-mining": "gold/stone +15%",
  "precision-cross-breeding": "food +10%", "crosscut-saw": "wood +15%, carry +5", cupellation: "gold/stone +15%",
  economic: "Economic wing: Fertile Crescent, Agriculture, Improved Processing", culture: "Culture wing: PoK, Algebra, Public Libraries",
  admin: "Administrative wing: Golden Age x1.5, City Planning", military: "Military wing: free units, Boot Camp, Composite Bows, Camel Support",
};
const AGE = { 2: "Feudal Age", 3: "Castle Age", 4: "Imperial Age" };

// ---------- gather model (eco.py) ----------
function rEff(res, d, techs, P, civ) {
  let r = P.raw[res], cap = HUNT.has(res) ? 25 : 10, v = 1.125;
  if (civ === "abbasid" && res === "berries") { r = 0.8625; cap += 3; }
  const cls = FOOD_SOFT.has(res) ? "food_soft" : HUNT.has(res) ? "hunt" : MINE.has(res) ? "mine" : res;
  for (const t of techs) { const e = ECO_TECH[t]; if (!e) continue; r *= e[cls] || 1; cap += (e.carry || 0) + (res === "wood" ? (e.carry_wood || 0) : 0); v *= e.speed || 1; }
  return cap / (cap / r + 2 * d / v + P.t_turn);
}
function sheepGroupRate(k, techs, P) { const r = rEff("sheep", 0, techs, P); const t = 200 / (k * r) + P.t_sheep_group; return 200 / t; }
const buildTime = (base, n) => base * 3 / (n + 2);

const DEFAULTS = {
  wings: ["economic", "culture", "admin"], vilTarget: 200, stables: 5, maxStables: 5, blacksmiths: 2, ecoMode: "skip3", ecoFeudal: "feudal",
  pauseForAge: false, cpFarmAdj: 0, cpStableAdj: 2.5, cpTcAdj: 2, cpBsAdj: 1, stackWalk: 0.25, escortCamels: 10, window: 4,
  map: { sheep: [20, 200, 0], berries: [8, 350, 1.0], berriesFar: [2, 8, 350, 1.5], deer: [8, 350, 1.5], deerPacks: 1, wood_d: 1.5, gold_d: 1.0, stone_d: 1.0, tcDistances: { sheep: 0 } },
  raw: Object.assign({}, RAW), t_turn: 0.3, t_sheep_group: 4.0, idle: 0.05, tmax: 3600,
  villagerLossPerMinute: 0, villagerLossStart: 300,
};

function simulate(user) {
  // Non-Abbasid civilizations run the multi-civilization engine on the installed 16.3 rules (engine-civs.js).
  if (user && user.civilization && user.civilization !== "abbasid") return civEngine().simulateCiv(user);
  const P = Object.assign({}, DEFAULTS, user || {}); P.map = Object.assign({}, DEFAULTS.map, (user && user.map) || {}); P.raw = Object.assign({}, DEFAULTS.raw, (user && user.raw) || {});
  if (!Number.isFinite(P.villagerLossPerMinute) || P.villagerLossPerMinute < 0 || P.villagerLossPerMinute > 10) throw new RangeError("villagerLossPerMinute must be between 0 and 10");
  if (!Number.isInteger(P.villagerLossStart) || P.villagerLossStart < 0 || P.villagerLossStart > 86400) throw new RangeError("villagerLossStart must be an integer between 0 and 86400 seconds");
  P.map.tcDistances = Object.assign({}, DEFAULTS.map.tcDistances, P.map.tcDistances || {});
  for (const [source, distance] of Object.entries(P.map.tcDistances)) if (!Number.isFinite(distance) || distance < 0) throw new RangeError(`Invalid Town Center distance for ${source}`);
  const [wf, wc, wi] = P.wings;
  const S = {
    t: 0, res: { food: 200, wood: 200, gold: 100, stone: 0 }, V: 6, builders: 0, age: 1, wings: [], techs: new Set(), camels: 0, freeUnits: 0,
    bld: { "town-center": 1 }, farms: 0, houses: 0, popcap: POP_PER_TC, tcTimer: [0], stableTimer: [], research: [], jobs: [],
    stock: { sheep: P.map.sheep[0] * P.map.sheep[1], berries: P.map.berries[0] * P.map.berries[1], deer: P.map.deer[0] * P.map.deer[1] * P.map.deerPacks, berriesFar: P.map.berriesFar[0] * P.map.berriesFar[1] * P.map.berriesFar[2] },
    dropoffs: { sheep: true }, farMills: 0, firstCamel: null, producedAtMinute: 0, villagersLost: 0, lossAttempts: 0,
    wingTimer: null, milestones: {}, spent: { food: 0, wood: 0, gold: 0, stone: 0 },
    spentCat: { villagers: 0, units: 0, buildings_eco: 0, buildings_prod: 0, techs_eco: 0, techs_mil: 0, ages: 0 },
    farmNeed: 0, foodVills: 0, events: [], minutes: [], techRec: {}, gathered: { food: 0, wood: 0, gold: 0, stone: 0 }, alg: { food: 0, wood: 0, gold: 0, stone: 0 },
    vMark: 0, cMark: 0, lastInc: null, lastAlloc: null, lastTrade: {}, unitsProduced: 0, savings: { "fresh-foodstuffs": 0, "fertile-crescent": 0, "preservation-of-knowledge": 0 },
  };
  const pop = () => S.V + S.camels + (S.others || 0);
  const golden = () => { const n = Object.values(S.bld).reduce((a, b) => a + b, 0) + S.farms + S.houses; return GOLDEN_TIERS.filter(th => n >= th).length; };
  const goldenK = () => S.wings.includes("admin") ? 1.5 : 1;
  const gatherMult = () => golden() >= 1 ? 1 + 0.15 * goldenK() : 1;
  const buildMult = () => golden() >= 2 ? 1 / (1 + 0.20 * goldenK()) : 1;
  const prodMult = () => { let m = S.techs.has("military-academy") ? 0.8 : 1; if (S.techs.has("city-planning")) m /= 1 + 0.08 * P.cpStableAdj; return m; };
  const farmMult = () => S.techs.has("city-planning") ? 1 + 0.08 * P.cpFarmAdj : 1;
  const price = (c, kind) => { let f = 1; if ((kind === "tech" || kind === "age") && S.techs.has("preservation-of-knowledge")) f *= 0.8; if (ECO_BLD.has(kind) && S.techs.has("fertile-crescent")) f *= 0.7; const o = {}; for (const r of R) o[r] = c[r] * f; return o; };
  const saveNote = (name, amount) => { const rec = S.techRec[name]; if (!rec || rec.end == null) return; S.savings[name] += amount; if (rec.payback == null && S.savings[name] >= rec.paid) rec.payback = S.t; rec.saved = Math.round(S.savings[name]); };
  const payPriced = (c, kind, cat) => { const pc = price(c, kind); const base = R.reduce((q, r) => q + c[r], 0), paid = R.reduce((q, r) => q + pc[r], 0); if (base > paid) saveNote((kind === "tech" || kind === "age") ? "preservation-of-knowledge" : "fertile-crescent", base - paid); pay(pc, cat); return pc; };
  const can = c => R.every(r => S.res[r] >= c[r]);
  const pay = (c, cat) => { for (const r of R) { S.res[r] -= c[r]; S.spent[r] += c[r]; } if (cat) S.spentCat[cat] += R.reduce((a, r) => a + c[r], 0); };
  const ecoTechs = () => [...S.techs].filter(t => ECO_TECH[t]);
  const mark = k => { if (!(k in S.milestones)) S.milestones[k] = S.t; };
  const completedV = () => S.V - S.tcTimer.filter(t => t > 0).length;
  const completedCamels = () => S.camels - S.stableTimer.filter(t => t > 0).length;
  const workerState = () => {
    const a = allocate();
    return { split: { food: a.sheep + a.berries + a.deer + a.berriesFar + a.farm, wood: a.wood, gold: a.gold, stone: a.stone, builders: S.builders, idle: a.idle || 0 },
      sources: { sheep: a.sheep, berries: a.berries, deer: a.deer, farBerries: a.berriesFar, farm: a.farm } };
  };
  const ev = (kind, cat, label, trigger, effect, c, detail = {}) => {
    const phase = kind === "done" ? "complete" : ["build", "tech", "age", "train", "farm"].includes(kind) ? "start" : kind === "assign" ? "allocation" : "milestone";
    S.events.push({ t: S.t, kind, cat, label, trigger, effect, phase,
      cost: c ? Object.fromEntries(R.filter(r => c[r]).map(r => [r, +c[r].toFixed(2)])) : {},
      stockBefore: Object.fromEntries(R.map(r => [r, Math.round(S.res[r] + (c?.[r] || 0))])),
      stock: Object.fromEntries(R.map(r => [r, Math.round(S.res[r])])),
      vil: completedV(), camels: completedCamels(), pop: pop(), age: S.age, ...workerState(), ...detail });
  };
  const hasDropoff = source => S.dropoffs[source] || Number.isFinite(P.map.tcDistances[source]);
  const sourceDistance = source => S.dropoffs[source] ? (source === "berriesFar" ? P.map.berriesFar[3] : ["wood", "gold", "stone"].includes(source) ? P.map[source + "_d"] : P.map[source]?.[2] || 0) : P.map.tcDistances[source];


  // ----- plan
  const wt = (w, age) => ({ "economic,2": ["fertile-crescent"], "economic,3": ["agriculture"], "economic,4": ["improved-processing"], "culture,2": ["preservation-of-knowledge"], "culture,3": ["algebra"], "admin,2": ["city-planning"] }[w + "," + age] || []).map(n => ["t", n]);
  let plan = [["b", "mill"], ["b", "lumber-camp"], ["b", "mining-camp", "gold"], ["b", "mining-camp", "stone"], ["b", "mill", "deer"], ["b", "house-of-wisdom"], ["age", wf]];
  const feco = [["t", "wheelbarrow"], ["t", "horticulture"], ["t", "double-broadax"], ["t", "specialized-pick"]];
  plan.push(["t", "fresh-foodstuffs"], ...wt(wf, 2), ["b", "town-center"], ...(P.ecoFeudal === "feudal" ? feco.slice(0, 1) : []), ["b", "town-center"]);
  plan.push(...(P.ecoFeudal === "feudal" ? feco.slice(1) : []), ["age", wc]);
  plan.push(...wt(wc, 2));
  if (P.ecoFeudal === "after_castle") { if (wc === "culture") plan.push(["gate", "preservation-of-knowledge"]); plan.push(...feco); }
  plan.push(...wt(wf, 3), ...wt(wc, 3));
  for (let i = 0; i < P.blacksmiths; i++) plan.push(["b", "blacksmith"]);
  plan.push(["b", "stable"], ["t", "bloomery"], ["t", "fitted-leatherwork"], ["t", "iron-undermesh"], ["t", "camel-rider-shields"], ["t", "camel-handling"], ["t", "military-academy"]);
  for (let i = 1; i < P.stables; i++) plan.push(["b", "stable"]);
  const t2 = ECO_T2.map(n => ["t", n]), castleMil = [["t", "decarbonization"], ["t", "insulated-helm"], ["t", "wedge-rivets"]];
  if (P.ecoMode === "late") plan.push(...castleMil, ["age", wi], ...t2); else plan.push(...t2, ...castleMil, ["age", wi]);
  plan.push(...wt(wi, 2), ...wt(wi, 3), ...wt(wf, 4), ...wt(wc, 4), ...wt(wi, 4));
  plan.push(["t", "elite-camel-riders"], ["t", "camel-rider-barding"], ["b", "madrasa"], ["t", "biology"], ["t", "damascus-steel"], ["t", "master-smiths"], ["t", "angled-surfaces"]);
  if (P.ecoMode === "asap") plan.push(...ECO_T3.map(n => ["t", n])); else plan = plan.filter(x => !(x[0] === "t" && x[1] === "improved-processing"));
  const planHas = (k, n) => plan.some(x => x[0] === k && x[1] === n);
  const removePlan = (k, n) => { const i = plan.findIndex(x => x[0] === k && x[1] === n); if (i >= 0) plan.splice(i, 1); };

  // ----- allocation and income
  const LONG = { food: 0.55, wood: 0.15, gold: 0.30, stone: 0 }, DARK = { food: 0.7, wood: 0.15, gold: 0.15, stone: 0 };
  function targets() {
    const tgt = { food: 0, wood: 0, gold: 0, stone: 0 }; let seenB = false;
    for (let i = 0; i < Math.min(P.window, plan.length); i++) {
      const [kind, name] = plan[i]; if (kind === "b") seenB = true; if (kind === "age" && seenB) break;
      if (kind === "gate") break;
      const c = kind === "age" ? WING_COST[S.age + 1] : kind === "t" ? TECH[name][1] : BLD[name][0];
      for (const r of R) tgt[r] += c[r] / (i + 1);
      if (kind === "age") break;
    }
    if (S.V < P.vilTarget) tgt.food += VIL[0] * (S.techs.has("fresh-foodstuffs") ? 0.6 : 1) / VIL[1] * S.tcTimer.length * 60;
    if (S.stableTimer.length && pop() < POP_MAX && S.age >= 3) for (const r of R) tgt[r] += CAMEL[0][r] / CAMEL[1] * S.stableTimer.length * 60;
    tgt.wood += S.farmNeed * price(BLD.farm[0], "farm").wood + 50;
    return tgt;
  }
  function shares() {
    const tgt = targets(); const def = {}; let tot = 0; for (const r of R) { def[r] = Math.max(0, tgt[r] - S.res[r]); tot += def[r]; }
    const lr = S.age === 1 ? DARK : LONG; if (tot < 1) return Object.assign({}, lr);
    const sh = {}; let n = 0; for (const r of R) { sh[r] = 0.8 * def[r] / tot + 0.2 * lr[r]; n += sh[r]; } for (const r of R) sh[r] /= n; return sh;
  }
  function allocate() {
    const g = Math.max(0, completedV() - S.builders), sh = shares();
    let kf = Math.round(g * sh.food), kw = Math.min(g - kf, Math.round(g * sh.wood)), kg = Math.min(g - kf - kw, Math.round(g * sh.gold)); let ks = Math.max(0, g - kf - kw - kg);
    const a = { sheep: 0, berries: 0, deer: 0, berriesFar: 0, farm: 0, wood: kw, gold: kg, stone: ks, spare: 0, kf };
    let left = kf;
    const capOf = { sheep: 24, berries: 16, deer: 8 * P.map.deerPacks, berriesFar: 8 * P.map.berriesFar[0] };
    for (const src of ["sheep", "berries", "deer", "berriesFar"]) { if (left <= 0 || S.stock[src] <= 0 || !hasDropoff(src)) continue; if (src === "berriesFar" && completedCamels() < P.escortCamels) continue; const k = Math.min(left, capOf[src]); a[src] = k; left -= k; }
    if (left > 0) { a.farm = Math.min(left, S.farms); a.spare = left - a.farm; a.wood += a.spare; }
    a.idle = 0;
    for (const resource of ["wood", "gold", "stone"]) if (!hasDropoff(resource)) { a.idle += a[resource]; a[resource] = 0; }
    return a;
  }
  const dx = () => S.techs.has("city-planning") ? P.stackWalk : 0;
  function rates(a, techs) { // income per second by resource for an allocation, no depletion
    const gm = gatherMult() * (1 - P.idle), inc = { food: 0, wood: 0, gold: 0, stone: 0 };
    if (a.sheep) inc.food += sheepGroupRate(Math.min(a.sheep, 8), techs, P) * (a.sheep / Math.min(a.sheep, 8)) * gm;
    if (a.berries) inc.food += a.berries * rEff("berries", sourceDistance("berries") + dx(), techs, P, "abbasid") * gm;
    if (a.deer) inc.food += a.deer * rEff("deer", sourceDistance("deer") + dx(), techs, P) * gm;
    if (a.berriesFar) inc.food += a.berriesFar * rEff("berries", sourceDistance("berriesFar") + dx(), techs, P, "abbasid") * gm;
    if (a.farm) inc.food += a.farm * rEff("farm", 0.33 + dx() / 2, techs, P) * gm * farmMult() * (techs.includes("agriculture") ? 1.15 : 1);
    if (a.wood) inc.wood += a.wood * rEff("wood", sourceDistance("wood") + dx(), techs, P) * gm;
    if (a.gold) inc.gold += a.gold * rEff("gold", sourceDistance("gold") + dx(), techs, P) * gm;
    if (a.stone) inc.stone += a.stone * rEff("stone", sourceDistance("stone") + dx(), techs, P) * gm;
    return inc;
  }
  function income() {
    const a = allocate(); S.lastAlloc = a; S.foodVills = a.kf; S.farmNeed = a.spare;
    const techs = ecoTechs().concat(S.techs.has("agriculture") ? ["agriculture"] : []);
    const inc = rates(a, techs);
    // deplete natural food in allocation order
    let foodNat = 0; const gm = gatherMult() * (1 - P.idle);
    for (const src of ["sheep", "berries", "deer", "berriesFar"]) { if (!a[src]) continue; let rate = src === "sheep" ? sheepGroupRate(Math.min(a.sheep, 8), techs, P) * (a.sheep / Math.min(a.sheep, 8)) : src === "berriesFar" ? a[src] * rEff("berries", sourceDistance("berriesFar"), techs, P, "abbasid") : a[src] * rEff(src, sourceDistance(src), techs, P, src === "berries" ? "abbasid" : undefined); rate *= gm; const take = Math.min(rate, S.stock[src]); S.stock[src] -= take; foodNat += take; if (take < rate) inc.food -= (rate - take); }

    // payback accumulation for eco techs
    const tot = R.reduce((q, r) => q + inc[r], 0);
    for (const t of techs) { if (!(ECO_TECH[t] || t === "agriculture")) continue; const rec = S.techRec[t]; if (!rec || rec.payback != null) continue; const without = rates(a, techs.filter(x => x !== t)); const gain = tot - R.reduce((q, r) => q + without[r], 0); rec.gain = (rec.gain || 0) + gain; if (rec.gain >= rec.paid) rec.payback = S.t; }
    return inc;
  }
  function algebraIncome() { if (!S.techs.has("algebra")) return {}; let n = 0; for (const t of S.techs) if (MIL_TECHS.has(t)) n++; const per = { food: 3 / 20, wood: 3 / 20, gold: 2 / 20 }, cap = { food: 58 / 20, wood: 58 / 20, gold: 38.67 / 20 }; const o = {}; for (const r in per) o[r] = Math.min(per[r] * n, cap[r]); return o; }

  // ----- actions
  function startBuild(name, builders, why, site) {
    site = site || ({ mill: "berries", "lumber-camp": "wood", "mining-camp": "gold" }[name]);
    const [c, t1] = BLD[name]; const pc = price(c, name);
    if (!can(pc) || completedV() - S.builders < builders) return false;
    payPriced(c, name, ECO_BLD.has(name) ? "buildings_eco" : "buildings_prod"); S.builders += builders;
    S.jobs.push([name, buildTime(t1, builders) * buildMult(), builders, site, S.t]);
    ev("build", "building", site ? `${name} at ${site}` : name, why, `start, ${builders} builder(s): ${EFFECT[name] || ""}`, pc, { entity: name, source: site }); return true;
  }
  function finishBuild(name, site) {
    if (site === "berries" && !S.dropoffs.berries) S.stock.berries += P.map.berries[0] * 100;
    if (site === "berriesFar") { S.stock.berriesFar += P.map.berriesFar[1] * 100; S.farMills++; S.dropoffs[site] = S.farMills >= P.map.berriesFar[0]; } else if (site) S.dropoffs[site] = true;
    if (name === "farm") S.farms++; else S.bld[name] = (S.bld[name] || 0) + 1;
    if (name === "town-center") { S.tcTimer.push(0); S.popcap += POP_PER_TC; mark("tc" + S.bld[name]); }
    if (name === "stable") S.stableTimer.push(0);
    if (name === "house") { S.houses++; S.popcap = Math.min(POP_MAX, S.popcap + POP_PER_HOUSE); }
    ev("done", "building", site ? `${name} at ${site}` : name, "build complete", EFFECT[name] || "", null, { entity: name, source: site });
  }
  function tryItem(kind, name, site) {
    if (kind === "b") { if (name === "town-center" && S.age < 2) return false; return startBuild(name, name === "town-center" ? 4 : 1, "next plan item affordable", site); }
    if (kind === "age") {
      if (S.wingTimer === null && S.bld["house-of-wisdom"] && can(price(WING_COST[S.age + 1], "age"))) { const pc = payPriced(WING_COST[S.age + 1], "age", "ages"); S.wingTimer = WING_TIME; S.wingStart = S.t; ev("age", "age", `${AGE[S.age + 1]} via ${name} wing`, "wing cost reached, planned TCs started", EFFECT[name], pc); return true; }
      return false;
    }
    const [age, c, tm, b, wing, cat] = TECH[name];
    if (S.age < age || (wing && !S.wings.includes(wing))) return false;
    const capN = b === "how" ? 1 : (S.bld[b] || 0);
    if (S.research.filter(r => r[0] === b).length >= capN) return false;
    const pc = price(c, "tech"); if (!can(pc)) return false;
    let rm = 1; if (b === "blacksmith" && S.techs.has("city-planning") && (S.bld.blacksmith || 0) >= 2) rm /= 1 + 0.08 * P.cpBsAdj;
    payPriced(c, "tech", MIL_TECHS.has(name) ? "techs_mil" : "techs_eco"); S.research.push([b, name, tm * rm, S.t]);
    S.techRec[name].start = S.t; S.techRec[name].paid = R.reduce((q, r) => q + pc[r], 0); S.techRec[name].costPaid = pc; S.techRec[name].duration = tm * rm;
    ev("tech", cat, name, "building free and cost reached", `research start (${Math.round(tm * rm)} s): ${EFFECT[name] || ""}`, pc); return true;
  }
  function tryPlan() {
    const ai = plan.findIndex(x => x[0] === "age");
    if (ai >= 0 && !plan.slice(0, ai).some(x => x[0] === "b") && tryItem("age", plan[ai][1])) { plan.splice(ai, 1); return; }
    for (const [kind, name, site] of plan.slice(0, P.window)) { if (kind === "age") break; if (kind === "gate") { if (S.techs.has(name)) { removePlan(kind, name); continue; } break; } if (tryItem(kind, name, site)) { removePlan(kind, name); return; } }
  }
  const savingForAge = () => plan.some(x => x[0] === "age") && S.age >= 3;

  // tech availability bookkeeping
  for (const n in TECH) S.techRec[n] = { name: n, cat: TECH[n][5], building: TECH[n][3], age: TECH[n][0], baseCost: R.reduce((q, r) => q + TECH[n][1][r], 0), available: null, start: null, end: null, payback: null, planned: planHas("t", n) };
  function updateAvailability() { for (const n in TECH) { const rec = S.techRec[n]; if (rec.available != null) continue; const [age, , , b, wing] = TECH[n]; if (S.age >= age && (!wing || S.wings.includes(wing)) && (b === "how" || S.bld[b])) rec.available = S.t; } }

  // ----- step
  function applyVillagerLosses() {
    if (!P.villagerLossPerMinute || S.t <= P.villagerLossStart) return;
    const due = Math.floor((S.t - P.villagerLossStart) * P.villagerLossPerMinute / 60 + 1e-9);
    const attempts = due - S.lossAttempts; S.lossAttempts = due;
    // V includes trainees. Protect them and workers attached to construction jobs.
    const eligible = Math.max(0, S.V - S.builders - S.tcTimer.filter(t => t > 0).length);
    for (let i = 0; i < Math.min(attempts, eligible); i++) {
      S.V--; S.villagersLost++;
      ev("loss", "unit", "Villager lost", "assumed economic attrition", "worker removed; replacement uses normal Town Center production");
      Object.assign(S.events[S.events.length - 1], { count: 1, villagersLost: S.villagersLost });
    }
  }
  function step() {
    applyVillagerLosses();
    if (!hasDropoff("berriesFar") && S.stock.sheep <= 0 && S.stock.berries <= 0 && completedCamels() >= P.escortCamels && !S.jobs.some(j => j[3] === "berriesFar")) startBuild("mill", 1, "prepare remote berry drop-off", "berriesFar");
    const allocation = workerState(), allocationKey = JSON.stringify(allocation);
    if (allocationKey !== S.allocationKey) { S.allocationKey = allocationKey; ev("assign", "economy", "Worker reassignment", "resource targets and available workers changed", "Expected worker allocation", null, allocation); }
    const inc = income(), tr = algebraIncome(); S.lastInc = inc; S.lastTrade = tr;
    for (const r of R) { S.res[r] += inc[r] + (tr[r] || 0); S.gathered[r] += inc[r]; S.alg[r] += tr[r] || 0; }
    if (S.popcap < POP_MAX && pop() + 3 * S.tcTimer.length + S.stableTimer.length >= S.popcap && !S.jobs.some(j => j[0] === "house")) startBuild("house", 1, "pop cap within reach of production");
    tryPlan();
    // auto production: income outruns the stables
    if (P.maxStables > P.stables && S.age >= 3 && S.stableTimer.length >= P.stables && (S.bld.stable || 0) < P.maxStables && !S.jobs.some(j => j[0] === "stable") && !plan.some(x => x[1] === "stable")
      && S.stableTimer.every(x => x > 0) && S.res.food >= 500 && S.res.gold >= 250 && S.res.wood >= 250 && pop() + 10 < POP_MAX) startBuild("stable", 1, "resources banking while every stable is busy");
    // farms
    { let need = S.farmNeed - S.jobs.filter(j => j[0] === "farm").length;
      while (need-- > 0 && startBuild("farm", 1, "food workers need a completed farm")) { /* each plot reserves a builder and construction time */ }
    }

    // villagers
    const vc = VIL[0] * (S.techs.has("fresh-foodstuffs") ? 0.6 : 1);
    for (let i = 0; i < S.tcTimer.length; i++) {
      if (S.tcTimer[i] > 0) { S.tcTimer[i] = Math.max(0, S.tcTimer[i] - 1); if (!S.tcTimer[i]) ev("done", "unit", "Villager", "training complete", "worker available", null, { producer: "town-center", queue: i, count: 1 }); continue; }
      if (S.V < P.vilTarget && pop() < S.popcap && S.res.food >= vc) { const tcm = S.techs.has("city-planning") ? 1 / (1 + 0.08 * P.cpTcAdj) : 1; S.res.food -= vc; S.spent.food += vc; S.spentCat.villagers += vc; S.tcTimer[i] = VIL[1] * tcm; S.V++; ev("train", "unit", "Villager", "Town Center queue free and food available", "training started", cost(vc), { producer: "town-center", queue: i, count: 1, duration: Math.ceil(S.tcTimer[i]), readyAt: S.t + Math.ceil(S.tcTimer[i]) }); if (vc < VIL[0]) saveNote("fresh-foodstuffs", VIL[0] - vc); }
    }
    // camels
    const busyStables = S.research.filter(r => r[0] === "stable").length;
    for (let i = 0; i < S.stableTimer.length; i++) {
      if (S.stableTimer[i] > 0) { S.stableTimer[i] = Math.max(0, S.stableTimer[i] - 1); if (!S.stableTimer[i]) { S.unitsProduced++; ev("done", "unit", "Camel Rider", "training complete", "unit available", null, { producer: "stable", queue: i, count: 1 }); } continue; }
      if (i < busyStables) continue; if (P.pauseForAge && savingForAge()) continue;
      if (S.age >= 3 && pop() < Math.min(POP_MAX, S.popcap) && can(CAMEL[0])) { pay(CAMEL[0], "units"); S.stableTimer[i] = CAMEL[1] * prodMult(); S.camels++; ev("train", "unit", "Camel Rider", "stable queue free and resources available", "training started", CAMEL[0], { producer: "stable", queue: i, count: 1, duration: Math.ceil(S.stableTimer[i]), readyAt: S.t + Math.ceil(S.stableTimer[i]) }); if (S.firstCamel == null) { S.firstCamel = S.t; mark("first_camel"); ev("army", "production", "first Camel Rider queued", "stable up, Castle Age, 220 res", `ready in ${Math.round(CAMEL[1] * prodMult())} s`); } }
    }
    // timers
    for (const j of [...S.jobs]) { if (j[4] === S.t) continue; j[1]--; if (j[1] <= 0) { S.jobs.splice(S.jobs.indexOf(j), 1); S.builders -= j[2]; finishBuild(j[0], j[3]); } }
    for (const r of [...S.research]) { if (r[3] === S.t) continue; r[2]--; if (r[2] <= 0) { S.research.splice(S.research.indexOf(r), 1); S.techs.add(r[1]); S.techRec[r[1]].end = S.t; mark(r[1]); ev("done", TECH[r[1]][5], r[1], "research complete", EFFECT[r[1]] || ""); } }
    if (S.wingTimer !== null && S.wingStart !== S.t) { S.wingTimer--; if (S.wingTimer <= 0) { S.wingTimer = null; S.age++; const w = P.wings[S.age - 2]; S.wings.push(w); if (w === "military" && S.age === 3) { S.camels += 2; S.freeUnits += 2; } if (w === "military" && S.age === 4) { S.others = (S.others || 0) + 3; S.freeUnits += 3; } if (w === "military" && S.age === 2) { S.others = (S.others || 0) + 4; S.freeUnits += 4; } mark("age" + S.age); ev("done", "age", AGE[S.age], "wing complete (100 s)", EFFECT[w]); } }
    const g = golden(); for (let k = 1; k <= 5; k++) if (g >= k && !("golden" + k in S.milestones)) { mark("golden" + k); ev("golden", "golden", `Golden Age tier ${k}`, `${Object.values(S.bld).reduce((a, b) => a + b, 0) + S.farms + S.houses} buildings in influence`, ["gather +15%", "build speed +20%", "camel damage +15%", "trader income +20%", "infantry +10%"][k - 1] + (S.wings.includes("admin") ? " (x1.5 Administrative)" : "")); }
    updateAvailability();
    if (completedV() >= S.vMark + 20) { S.vMark = Math.floor(completedV() / 20) * 20; ev("vil", "production", `${completedV()} villagers`, "continuous TC production", `${S.tcTimer.length} TCs`); }
    if (completedCamels() >= S.cMark + 20) { S.cMark = Math.floor(completedCamels() / 20) * 20; ev("army", "production", `${completedCamels()} camels`, "continuous stable production", `${S.stableTimer.length} stables`); }
    S.t++;
    if (S.t % 60 === 0) snapshot();
  }
  function snapshot() {
    { const g = golden();
      const a = allocate(), techs = ecoTechs(), gm = gatherMult();
      const perVil = { farm: rEff("farm", 0.33, techs, P) * gm * farmMult() * (S.techs.has("agriculture") ? 1.15 : 1), berries: rEff("berries", P.map.berries[2], techs, P, "abbasid") * gm, sheep: rEff("sheep", 0, techs, P) * gm, wood: rEff("wood", P.map.wood_d, techs, P) * gm, gold: rEff("gold", P.map.gold_d, techs, P) * gm };
      S.minutes.push({ t: S.t, vil: completedV(), villagersLost: S.villagersLost, camels: completedCamels(), pop: pop(), farms: S.farms, houses: S.houses, age: S.age, golden: g, tcs: S.tcTimer.length, stables: S.stableTimer.length, blacksmiths: S.bld.blacksmith || 0, builders: S.builders,
        split: workerState().split,
        sources: a ? { sheep: a.sheep, berries: a.berries, deer: a.deer, farBerries: a.berriesFar, farm: a.farm } : {},
        produced: S.unitsProduced - S.producedAtMinute, stockLeft: { sheep: Math.round(S.stock.sheep), berries: Math.round(S.stock.berries), deer: Math.round(S.stock.deer), farBerries: Math.round(S.stock.berriesFar) },
        income: Object.fromEntries(R.map(r => [r, Math.round(S.gathered[r])])), algebra: Object.fromEntries(R.map(r => [r, Math.round(S.alg[r])])),
        stock: Object.fromEntries(R.map(r => [r, Math.round(S.res[r])])), spent: Object.fromEntries(R.map(r => [r, Math.round(S.spent[r])])), spentCat: Object.fromEntries(Object.entries(S.spentCat).map(([k, v]) => [k, Math.round(v)])),
        perVil: Object.fromEntries(Object.entries(perVil).map(([k, v]) => [k, +(60 * v).toFixed(1)])), gatherMult: +gm.toFixed(3), techs: S.techs.size, unitsProduced: S.unitsProduced, armyValue: completedCamels() * 220 });
      S.gathered = { food: 0, wood: 0, gold: 0, stone: 0 }; S.alg = { food: 0, wood: 0, gold: 0, stone: 0 }; S.producedAtMinute = S.unitsProduced;
      for (const n in S.techRec) { const r = S.techRec[n]; if (r.start != null) { r.gainAt = r.gainAt || {}; r.gainAt[S.t] = Math.round(r.gain || S.savings[n] || 0); } }
    }
  }
  while (S.t < P.tmax) {
    step();
    const done = CAMEL_TECHS.every(t => S.techs.has(t)); if (done) mark("all_camel_techs");
    if (pop() >= POP_MAX) mark("pop200");
    if (done && completedV() + completedCamels() + (S.others || 0) >= POP_MAX) { mark("DONE"); if (S.t % 60) { const last = S.minutes[S.minutes.length - 1]; const scale = 60 / (S.t - last.t); snapshot(); const f = S.minutes[S.minutes.length - 1]; for (const r of R) { f.income[r] = Math.round(f.income[r] * scale); f.algebra[r] = Math.round(f.algebra[r] * scale); } f.partial = true; } break; }
  }
  // payback for savings-type techs
  const rec = S.techRec;
  for (const n in rec) { const r = rec[n]; if (r.cat !== "economy" && n !== "agriculture") r.payback = r.payback == null ? null : r.payback; if (r.gain != null) r.gain = Math.round(r.gain); }
  return { params: P, milestones: S.milestones, done: S.milestones.DONE, events: S.events, minutes: S.minutes, techs: Object.values(rec), summary: { villagers: completedV(), villagersLost: S.villagersLost, camels: completedCamels(), farms: S.farms, houses: S.houses, buildings: S.bld, spent: S.spent, spentCat: S.spentCat, banked: S.res, freeUnits: S.freeUnits } };
}
const UNIT = { villager: { hp: 50, speed: 1.125, carry: 10, carryHunt: 25, cost: "50 food (30 with Fresh Foodstuffs)", time: 20 },
  camel: { hp: [270, 320], dmg: [14, 16], period: 1.125, bonusCav: [14, 16], bonusSiege: 10, speed: 1.625, cost: "130 food 45 wood 45 gold", time: 35, pop: 1 } };
function civEngine() { const e = root.AoE4CivEngine || (typeof require === "function" ? require("./engine-civs.js") : null); if (!e) throw new Error("engine-civs.js is not loaded"); return e; }
const api = { simulate, DEFAULTS, TECH, CAMEL_TECHS, EFFECT, rEff, ECO_TECH, RAW, UNIT, sheepGroupRate, POP_MAX };
if (typeof module !== "undefined" && module.exports) module.exports = api; else root.AoE4Engine = api;
})(typeof window !== "undefined" ? window : globalThis);
