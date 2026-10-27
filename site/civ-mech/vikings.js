/* Vikings mechanics for site/engine-civs.js (17.0 preview rules, data/civ-rules/vikings.json via scripts/civ_glue/vikings.py).
   Northern Migration: every Town Center recruits a free villager every 22 s (20 s after Falkr's Village) while villagers are
   below the villager capacity (10 + 10 per Longhouse). Longhouses (+25 population, +10 capacity) are built from plan items
   ["x","lh"] the module inserts when spare capacity falls to mech.lhLead, up to mech.lh[age] per age; each completed
   Longhouse takes one attachment from the priority list mech.attach (["x","att"]): Bee Skeps (50 gold/min), Farmstead (two
   vegetable fields at 1.5x the farm rate), Smithy / Pasture and Loom (auto-research one damage / armor tier per age, 270 s,
   earlier ages 60 s faster). Konungr Hall feasts and Call Shield Maidens, Baugr Fort (Barracks +25% work rate, Hardened on
   completion), Gullinn Temple Berserkers, Rikets Nyckel crossbowmen, Kongens Dor tithe, Bondi Forester wood and the sagas a
   plan completes by itself (Falkr, Ulfr, Jofurr, Dreki). mech.gullinnMinPop holds the Gullinn Temple until population
   (villagers + army, as the HUD counts it) reaches that number. */
(function (root) {
"use strict";
const INFANTRY = ["bondi", "berserker", "hirdman"];
const allowedLH = (P, age) => { let n = 0; for (let a = 1; a <= age; a++) n += +((P.mech.lh || {})[a] || 0); return n; };
const pendingLH = S => S.jobs.filter(j => j.name === "longhouse").length;
function nextAttach(ctx) {
  const { S, P, M } = ctx, V = S.vikings, used = Object.assign({}, V.att);
  for (const a of V.attaching) used[a.kind] = (used[a.kind] || 0) + 1;
  const seen = {};
  for (const k of P.mech.attach || []) {
    const a = M.attach[k]; if (!a) continue;
    seen[k] = (seen[k] || 0) + 1; if (seen[k] <= (used[k] || 0)) continue; // this slot of the list is already used
    if (S.age >= a.age && (used[k] || 0) < a.limit) return k;
  }
  return null;
}
const attachCost = (ctx, k) => ctx.times(ctx.M.attach[k].cost, ctx.S.vikings.sagas.falkr != null ? ctx.M.sagas.falkr.attachmentCost : 1);
const freeLH = S => (S.bld.longhouse || 0) - S.vikings.attTotal - S.vikings.attaching.length;
function vegRate(ctx) {
  const g = ctx.spec.villager.gather.farm, cls = ["food", "food_soft", "farm"];
  const r = g.rate * ctx.mulOf("gather_rate", cls) * ctx.M.attach.farm.fieldRate, cap = g.carry + ctx.addOf("carry", cls), v = ctx.spec.villager.speed * ctx.mulOf("speed", ["villager"]);
  return cap / (cap / r + 2 * 0.33 / v + ctx.P.t_turn);
}
function spawn(ctx, line, n, why, producer, pbgid, detail) {
  const { S } = ctx, room = Math.min(S.popcap, ctx.POP_MAX) - ctx.pop(); n = Math.max(0, Math.min(n, room)); if (!n && !detail) return 0;
  const l = ctx.lines.find(x => x.key === line);
  if (l) { const a = S.army[line]; a.count += n; a.produced += n; S.unitsProduced += n; if (a.produced <= n) ctx.mark("first_" + line); ctx.mark("first_unit"); }
  else S.others += n;
  ctx.ev("done", "unit", l ? ctx.tierOf(l).name : why.name, why.text, l ? "unit available" : "army population (not a planned line)", null, Object.assign({ producer, count: n, pbgid: l ? ctx.tierOf(l).pbgid : pbgid, line: l ? line : undefined }, detail || {}));
  return n;
}

const mod = {
  init(ctx) {
    const { S, P, M, plan } = ctx; P.mech = P.mech || {};
    S.vikings = { cap: M.migration.startCapacity, att: { bee: 0, farm: 0, smithy: 0, loom: 0 }, attTotal: 0, attaching: [], veg: 0, auto: { smithy: null, loom: null }, sagas: {},
      feastStart: null, kongensStart: null, gullinnNext: null, groveRate: 1, groves: [], volur: [], maidens: 0, maidensDue: null, maidensCalled: false, groveUnits: 0, skane: 0,
      deer0: S.stock.deer, gate: null, gullinnStartPop: null, pop200Age: null };
    for (const k of Object.keys(M.auto || {})) while (plan.some(x => x[0] === "t" && x[1] === k)) ctx.removePlan("t", k); // researched by the attachments, not bought
    if (P.mech.gullinnMinPop > 0 && ctx.lm(3)?.key === "gullinn-temple") { S.mods.push({ source: "vikings:gate", kind: "cost", target: "age:gullinn-temple", op: "mul", value: 1e9 }); S.modsVersion++; S.vikings.gate = P.mech.gullinnMinPop; }
    // Opening: the starting 200 wood pays the first Longhouse and the Lumber Camp.
    if (P.mech.openWood !== false && allowedLH(P, 1) > 0) {
      const li = plan.findIndex(x => x[0] === "b" && x[2] === "wood"); const lc = li >= 0 ? plan.splice(li, 1)[0] : null;
      plan.unshift(["x", "lh"]); if (lc) plan.splice(1, 0, lc);
    }
  },
  villagers(ctx) {
    const { S, M, spec } = ctx, V = S.vikings;
    const iv = (M.migration.interval - (V.sagas.falkr != null ? M.migration.falkrMinus : 0)) / ctx.mulOf("production_speed", ["town-center"]);
    for (let i = 0; i < S.tcTimer.length; i++) {
      if (S.tcTimer[i] > 0) { S.tcTimer[i] = Math.max(0, S.tcTimer[i] - 1); if (!S.tcTimer[i]) { ctx.ev("done", "unit", "Villager", "Northern Migration recruit complete", "worker available", null, { producer: "town-center", queue: i, count: S.tcBatch[i], pbgid: spec.villager.pbgid }); S.tcBatch[i] = 0; } continue; }
      if (S.V >= V.cap || S.V >= ctx.vt() || ctx.pop() >= S.popcap) continue;
      S.tcTimer[i] = iv; S.tcBatch[i] = 1; S.V += 1;
      ctx.ev("train", "unit", "Villager", "Northern Migration: spare villager capacity", "free recruit started", null, { producer: "town-center", queue: i, count: 1, duration: Math.ceil(iv), readyAt: S.t + Math.ceil(iv), pbgid: spec.villager.pbgid });
    }
    return true;
  },
  costOf(ctx, name) {
    if (name === "lh") return ctx.B.longhouse.cost;
    if (name === "att") { const k = nextAttach(ctx); return k ? attachCost(ctx, k) : {}; }
    if (name === "maidens") return ctx.M.maidens.cost;
    return {};
  },
  tryItem(ctx, name) {
    const { S, P, M, plan } = ctx, V = S.vikings, drop = () => { const i = plan.findIndex(x => x[0] === "x" && x[1] === name); if (i >= 0) plan.splice(i, 1); return false; };
    if (name === "lh") {
      if ((S.bld.longhouse || 0) + pendingLH(S) >= allowedLH(P, S.age)) return drop();
      return ctx.startBuild("longhouse", P.mech.lhBuilders || 1, "villager capacity within reach (Northern Migration)");
    }
    if (name === "att") {
      const k = nextAttach(ctx); if (!k || freeLH(S) <= 0) return drop();
      const c = attachCost(ctx, k); if (!ctx.can(c)) return false;
      ctx.pay(c, "techs_eco"); const a = M.attach[k]; V.attaching.push({ kind: k, left: a.time, start: S.t });
      ctx.ev("tech", "economy", `${a.name} (Longhouse attachment)`, "Longhouse without attachment and cost reached", `research start (${a.time} s)`, c, { entity: a.id, pbgid: a.id });
      return true;
    }
    if (name === "maidens") {
      if (V.maidensCalled || !S.landmarks.includes("konungr-hall")) return drop();
      const c = M.maidens.cost; if (!ctx.can(c)) return false;
      ctx.pay(c, "units"); V.maidensCalled = true; V.maidensDue = S.t + M.maidens.time;
      ctx.ev("train", "unit", "Call Shield Maidens", "Konungr Hall one-time call", `1 + 1 per Longhouse Shield Maidens in ${M.maidens.time} s`, c, { producer: "landmark:konungr-hall", queue: 0, count: 1, duration: M.maidens.time, readyAt: V.maidensDue, pbgid: M.maidens.pbgid });
      return true;
    }
    return false;
  },
  step(ctx) {
    const { S, P, M, T, plan } = ctx, V = S.vikings, pop = ctx.pop();
    // Gullinn Temple gate (Sam's assumption: population at least mech.gullinnMinPop before it is started)
    if (V.gate != null && pop >= V.gate) { S.mods = S.mods.filter(m => m.source !== "vikings:gate"); S.modsVersion++; V.gate = null; ctx.mark("gullinn_gate_open"); ctx.ev("milestone", "age", `Population ${pop}`, `Gullinn Temple allowed from ${P.mech.gullinnMinPop} population`, "", null); }
    if (V.gullinnStartPop == null) { const j = S.jobs.find(x => x.name === "landmark" && x.key === "gullinn-temple"); if (j) { V.gullinnStartPop = pop; ctx.mark("gullinn_start"); } }
    // Longhouses: villager capacity within reach (plan item), or the population cap within reach of production (house rule)
    const pend = pendingLH(S), built = S.bld.longhouse || 0, spare = V.cap + M.migration.perLonghouse * pend - S.V;
    if (!plan.some(x => x[0] === "x" && x[1] === "lh") && built + pend < allowedLH(P, S.age) && (spare <= (P.mech.lhLead ?? 4) || S.V >= ctx.vt())) plan.unshift(["x", "lh"]); // past the villager target the rest are for attachments
    if (S.popcap < ctx.POP_MAX && pend < 2 && pop + 3 * S.tcTimer.length + 2 * S.prod.length >= S.popcap + pend * M.longhouse.pop) ctx.startBuild("longhouse", 1, "population cap within reach of production");
    if (!plan.some(x => x[0] === "x" && x[1] === "att") && freeLH(S) > 0 && nextAttach(ctx)) { const i = plan.findIndex(x => x[0] === "x" && x[1] === "lh"); plan.splice(i + 1, 0, ["x", "att"]); }
    if (P.mech.callMaidens && !V.maidensCalled && S.landmarks.includes("konungr-hall") && built >= Math.min(P.mech.callMaidensAt ?? 14, allowedLH(P, 4)) && !plan.some(x => x[0] === "x" && x[1] === "maidens")) plan.unshift(["x", "maidens"]);
    // attachment research
    for (const a of [...V.attaching]) {
      if (a.start === S.t) continue; if (--a.left > 0) continue;
      V.attaching.splice(V.attaching.indexOf(a), 1); V.att[a.kind]++; V.attTotal++;
      const d = M.attach[a.kind];
      if (a.kind === "farm") { S.farms += d.fields; V.veg += d.fields; }
      if (a.kind === "smithy" || a.kind === "loom") S.bld["longhouse-" + a.kind] = 1;
      ctx.ev("done", "economy", `${d.name} (Longhouse attachment)`, "attachment complete", a.kind === "bee" ? "50 gold per minute" : a.kind === "farm" ? "food drop-off, 2 vegetable fields" : "automatic damage/armor research", null, { entity: d.id, pbgid: d.id });
      if (V.sagas.falkr == null && V.attTotal >= M.sagas.falkr.attachments) { V.sagas.falkr = S.t; ctx.mark("saga_falkr"); ctx.ev("done", "economy", "Falkr's Village saga", `${V.attTotal} Longhouse attachments`, "villagers recruited 2 s faster, attachments 20% cheaper", null, { keep: true }); }
    }
    // Smithy / Pasture and Loom: one tier at a time, the next tier whose age is reached
    for (const src of ["smithy", "loom"]) {
      if (!V.att[src]) continue;
      const cur = V.auto[src], d = M.attach[src];
      if (cur) { if (cur.start !== S.t && --cur.left <= 0) { V.auto[src] = null; ctx.grant(cur.k, `automatic research by the ${d.name} attachment`); Object.assign(S.techRec[cur.k], { start: cur.start, duration: S.t - cur.start }); } continue; }
      const k = d.techs.find(x => T[x] && !S.techs.has(x) && T[x].age <= S.age); if (!k) continue;
      const dur = d.researchSeconds - (T[k].age < S.age ? d.earlierAgeFaster : 0); V.auto[src] = { k, left: dur, start: S.t };
      ctx.ev("tech", "military", T[k].name, `automatic research by the ${d.name} attachment`, `research start (${dur} s, no cost)`, null, { pbgid: T[k].pbgid, tech: k });
    }
    // sagas a plan completes by itself
    if (V.sagas.ulfr == null) { const n = INFANTRY.reduce((s, k) => s + (S.army[k]?.produced || 0), 0) + V.groveUnits + V.maidens; if (n >= M.sagas.ulfr.infantry) { V.sagas.ulfr = S.t; ctx.mark("saga_ulfr"); ctx.ev("done", "military", "Ulfr's Forester saga", `${n} infantry recruited`, "+5 torch damage, +1 tile torch range", null, { keep: true }); } }
    if (V.sagas.jofurr == null && V.deer0 - S.stock.deer >= M.sagas.jofurr.food) { V.sagas.jofurr = S.t; ctx.mark("saga_jofurr"); ctx.addEffects([{ kind: "gather_rate", target: "all", op: "mul", value: M.sagas.jofurr.gather }, { kind: "carry", target: "all", op: "add", value: M.sagas.jofurr.carry }], "saga:jofurr"); ctx.ev("done", "economy", "Jofurr's Hunt saga", `${M.sagas.jofurr.food} food hunted`, "villagers gather 10% faster, carry +5", null, { keep: true }); }
    // Gullinn Temple and Sacred Grove Berserkers
    if (V.gullinnNext != null && S.t >= V.gullinnNext) { if (spawn(ctx, "berserker", 1, { name: "Berserker", text: "Gullinn Temple recruits a Berserker" }, "landmark:gullinn-temple", "unit_berserker_3_vik")) { V.groveUnits++; V.gullinnNext += M.grove.gullinn / V.groveRate; } }
    const want = Math.min(+(P.mech.groves || 0), M.grove.limit);
    if (S.age >= 2 && V.groves.length + V.volur.length < want) { const c = M.grove.volur.cost; if (ctx.can(c)) { ctx.pay(c, "units"); const q = V.groves.length + V.volur.length; V.volur.push({ due: S.t + M.grove.volur.time + 10, q }); ctx.ev("train", "unit", "Völur", "Sacred Grove on a relic (mech.groves)", "trained, then sacrificed to establish a Sacred Grove", c, { producer: "volur", queue: q, count: 1, duration: M.grove.volur.time + 10, readyAt: S.t + M.grove.volur.time + 10, pbgid: "unit_volva_2_vik" }); } }
    for (const v of [...V.volur]) if (S.t >= v.due) { const q = v.q; V.volur.splice(V.volur.indexOf(v), 1); V.groves.push(S.t + M.grove.grove / V.groveRate); ctx.ev("done", "unit", "Sacred Grove", "Völur sacrificed on a relic", "Berserkers every 100 s, +1 armor aura", null, { producer: "volur", queue: q, count: 1, pbgid: "building_sacred_grove_vik" }); }
    for (let i = 0; i < V.groves.length; i++) if (S.t >= V.groves[i] && spawn(ctx, "berserker", 1, { name: "Berserker", text: "Sacred Grove recruits a Berserker" }, "sacred-grove", "unit_berserker_2_vik")) { V.groveUnits++; V.groves[i] += M.grove.grove / V.groveRate; }
    // Call Shield Maidens arrive
    if (V.maidensDue != null && S.t >= V.maidensDue) { const n = spawn(ctx, "shield-maiden", M.maidens.base + M.maidens.perLonghouse * (S.bld.longhouse || 0), { name: "Shield Maiden", text: "Call Shield Maidens arrive" }, "landmark:konungr-hall", "unit_shield_maiden_konungr_vik", { queue: 0 }); V.maidens += n; V.maidensDue = null; }
    // Allocation: Longhouse wood is what keeps Northern Migration running (150 wood per 10 villagers, plus the next planned
    // attachment), so it is reserved like the food other civilizations reserve for continuous villager production. The
    // engine places flow workers from flow need minus passive income; this lowers next step's passive wood by that flow.
    const lhLeft = allowedLH(P, S.age) - (S.bld.longhouse || 0) - pendingLH(S);
    if (lhLeft > 0 && S.V < Math.min(ctx.vt(), V.cap + M.migration.perLonghouse * lhLeft) && P.mech.reserveWood !== false) {
      const k = nextAttach(ctx), perVil = ((ctx.B.longhouse.cost.wood || 0) + (k ? attachCost(ctx, k).wood || 0 : 0)) / M.migration.perLonghouse;
      const iv = M.migration.interval - (V.sagas.falkr != null ? M.migration.falkrMinus : 0);
      S.lastPassive = Object.assign({}, S.lastPassive || ctx.zero(), { wood: ((S.lastPassive || {}).wood || 0) - perVil * S.tcTimer.length / iv });
    }
    // 200 population of completed units
    if (S.milestones.vik_pop200 == null && ctx.completedV() + ctx.armyPopDone() + S.others >= ctx.POP_MAX) { ctx.mark("vik_pop200"); V.pop200Age = S.age; V.atPop200 = { longhouses: S.bld.longhouse || 0, villagers: ctx.completedV(), army: ctx.armyPopDone() + S.others }; }
  },
  passive(ctx, o) {
    const { S, P, M } = ctx, V = S.vikings; if (!V) return;
    o.gold += V.att.bee * M.attach.bee.goldPerSecond;
    if (V.feastStart != null && S.t > V.feastStart && (S.t - V.feastStart) % M.feast.interval === 0) o.food += M.feast.food + M.feast.perLonghouse * (S.bld.longhouse || 0);
    if (S.techs.has("upgrade_bondi_wood_gather_vik") && S.army.bondi) o.wood += Math.min(S.army.bondi.count * M.forester.perBondi, M.forester.max);
    if (V.kongensStart != null && S.t > V.kongensStart && (S.t - V.kongensStart) % M.kongens.interval === 0) o.gold += M.kongens.gold * Math.min(+(P.mech.kongensLonghouses || 0), S.bld.longhouse || 0);
  },
  farmRate(ctx, n) { const V = ctx.S.vikings; if (!V || !V.veg) return undefined; const veg = Math.min(n, V.veg); return veg * vegRate(ctx) + (n - veg) * ctx.rEff("farm", 0.33); },
  finishBuild(ctx, name) {
    const { S, P, M } = ctx, V = S.vikings;
    if (name === "longhouse") {
      V.cap += M.migration.perLonghouse;
      const i = S.prod.map(p => p.name).lastIndexOf("longhouse");
      if (i >= 0) { if (P.mech.longhouseBondi) S.prod[i].mult = M.longhouse.bondiRate; else S.prod.splice(i, 1); }
    }
    if (name === "barracks" && S.landmarks.includes("baugr-fort")) { const p = S.prod[S.prod.map(x => x.name).lastIndexOf("barracks")]; if (p) p.mult = M.baugr.rate; }
  },
  finishLandmark(ctx, job) {
    const { S, M } = ctx, V = S.vikings, key = job.key;
    if (key === "konungr-hall") V.feastStart = S.t;
    if (key === "baugr-fort") { for (const p of S.prod) if (p.name === "barracks" || p.name === "landmark:baugr-fort") p.mult = M.baugr.rate; for (const k of M.baugr.grants) ctx.grant(k, "Baugr Fort upgrades Bondi and Berserkers to Hardened"); }
    if (key === "gullinn-temple") { V.sagas.dreki = S.t; ctx.mark("saga_dreki"); V.groveRate = M.grove.dreki; V.gullinnNext = S.t + M.grove.gullinn / V.groveRate; for (let i = 0; i < V.groves.length; i++) V.groves[i] = S.t + M.grove.grove / V.groveRate; }
    if (key === "rikets-nyckel-castle") V.skane += spawn(ctx, "skane", M.rikets.units, { name: "Skåne Crossbowman", text: "Ríkets Nyckel Castle recruits 10 Skåne Crossbowmen" }, "landmark:rikets-nyckel-castle", M.rikets.pbgid);
    if (key === "kongens-dor-cathedral") V.kongensStart = S.t;
  },
  snapshot(ctx, row) {
    const { S } = ctx, V = S.vikings;
    row.vikings = { villagerCapacity: V.cap, longhouses: S.bld.longhouse || 0, attachments: Object.assign({}, V.att), vegetableFields: V.veg, sagas: Object.keys(V.sagas), groveBerserkers: V.groveUnits, shieldMaidens: V.maidens, skane: V.skane };
  },
  result(ctx, out) {
    const { S } = ctx, V = S.vikings;
    out.vikings = { gullinnStartPop: V.gullinnStartPop, gullinnStart: S.milestones.gullinn_start ?? null, pop200: S.milestones.vik_pop200 ?? null, pop200Age: V.pop200Age, atPop200: V.atPop200 || null, sagas: V.sagas,
      longhouses: S.bld.longhouse || 0, attachments: V.att, villagerCapacity: V.cap, groveBerserkers: V.groveUnits, shieldMaidens: V.maidens, skane: V.skane };
  },
};
(root.AoE4CivMechanics = root.AoE4CivMechanics || {}).vikings = mod;
})(typeof window !== "undefined" ? window : globalThis);
