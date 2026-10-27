/* Scots mechanics for site/engine-civs.js (Update 17.0 preview rules, spec.mech.scots from scripts/civ_glue/scots.py).
   Highland Cattle (Tower House production, grazing food at Berry Bushes), Mustering Hall (charges, Influence tiers, musters:
   5 s action then one warrior every 2 s), Snowdoun Gate free infantry, Abbey of the Isles relic production, Stone of Destiny
   gold rebate, Kirkmen with relics and Fishponds. Plan parameters live under params.mech (see spec.defaults.mech).
   Set-aside resources: the next muster's food, and from the start of the Castle landmark the Monastery's wood and the relic
   Kirkmen's gold, are held back from the plan and unit production (a player saving for them); they are shown as `held`. */
(function (root) {
"use strict";
const RS = ["food", "wood", "gold", "stone"];

function room(ctx) { const { S, POP_MAX } = ctx; return Math.min(POP_MAX, S.popcap) - ctx.pop(); }
// Houses ahead of a muster or a Snowdoun batch so its warriors fit (a player builds them before pressing the button).
function makeRoom(ctx, need, why) {
  const { S, B, spec } = ctx; if (!spec.house || S.popcap >= ctx.POP_MAX) return;
  const pending = S.jobs.filter(j => B[j.name] && B[j.name].pop).reduce((s, j) => s + B[j.name].pop, 0);
  if (room(ctx) + pending < need && S.jobs.filter(j => j.name === spec.house).length < 3) ctx.startBuild(spec.house, 1, why);
}
function lineName(ctx, key) { const l = ctx.lines.find(x => x.key === key); return l ? ctx.tierOf(l).name : key; }
function unitOut(ctx, line, n, producer, why, queue) {
  const { S } = ctx; const a = S.army[line]; const l = ctx.lines.find(x => x.key === line);
  a.training -= n; a.count += n; a.produced += n; S.unitsProduced += n;
  ctx.ev("done", "unit", ctx.tierOf(l).name, why, "unit available", null, { producer, queue, count: n, pbgid: ctx.tierOf(l).pbgid, line });
  if (a.produced <= n) ctx.mark("first_" + line);
  ctx.mark("first_unit");
}
// The next muster the plan wants (age, charge, line and tier conditions met).
function nextMuster(ctx) {
  const { S, P, M } = ctx; const X = M.scots, Z = S.scots, pm = P.mech || {};
  if (!(Z.hall || Z.lookout) || Z.jobs.some(j => j.left > 0)) return null;
  for (const key of pm.musters || []) {
    const m = X.musters[key]; if (!m || Z.done[key] || !m.line || !ctx.lineKeys.includes(m.line)) continue;
    if (S.age < Math.max(m.age, pm.musterAge?.[key] || 0) || S.t < (pm.musterFrom?.[key] || 0) || Z.maxTier < (m.requiresTier || 0) || Z.charges < 1) continue;
    const units = Math.ceil(m.units * (Z.lookout ? X.hall.lookoutMultiplier : 1) - 1e-9);
    if (ctx.POP_MAX - ctx.pop() < units) { Z.done[key] = "dropped"; Z.log.push({ key, name: m.name, dropped: S.t, units }); continue; }
    return { key, m, units, food: Math.round(m.food * (1 - (X.hall.reduction[Z.tier] || 0))) };
  }
  return null;
}
// Fishpond capacity: 1 per Lowland landmark (at most 4), +1 with Stew Ponds.
function pondCapacity(ctx) { const { S, M } = ctx; const F = M.scots.fishpond, Z = S.scots; return Math.min(F.capLandmarkMax ?? 4, F.capPerLowland * Z.lowland) + (Z.stew && F.stewPonds ? F.stewPonds.capAdd : 0); }
const relicWanted = ctx => { const { S, P } = ctx; const K = S.scots.kirk; return (P.mech?.kirkmen || 0) > 0 && K.relicsLeft + K.trips.length > 0; };
const castleStarted = ctx => ctx.S.age >= 3 || ctx.S.jobs.some(j => j.name === "landmark" && j.age === 3);

const scots = {
  init(ctx) {
    const { S, P, M, plan, lm } = ctx; const X = M.scots; const pm = P.mech || {};
    const cows = ctx.spec.start.cattle || X.cattle.start;
    S.scots = {
      cattle: { grazing: cows, training: 0, timers: [], bought: 0, cap: X.cattle.capStart, peak: cows },
      hall: false, structures: 0, tier: 0, maxTier: 0, charges: 0, done: {}, jobs: [], log: [], lookout: false, held: { food: 0, wood: 0, gold: 0, stone: 0 },
      snow: null, hallTechs: 0, highland: 0, lowland: 0, sod: false, skye: false, rebate: 0, abbeyPending: false, abbeyOn: null, monasteryStart: null,
      kirk: { kirkmen: 0, training: 0, timer: 0, relicsIn: 0, relicsLeft: (pm.kirkmen || 0) > 0 ? (pm.relics ?? 0) : 0, trips: [], ponds: 0, pondJobs: [], idle: 0, firstTrip: null, gold: 0 },
    };
    // Plan edits: Tower Houses per age and the Mustering Hall at the start of mech.hallAge. Items go to the front of their age in
    // insertion order: Dark Age items just before the Feudal landmark, later ones just after the landmark that opens their age.
    const ageIdx = a => plan.findIndex(x => x[0] === "age" && x[1] === lm(a).key), front = {};
    const insertAt = (age, item) => { if (age <= 1) { const i = ageIdx(2); plan.splice(i < 0 ? plan.length : i, 0, item); return; }
      const i = ageIdx(age); if (i < 0) { plan.push(item); return; } plan.splice(i + 1 + (front[age] || 0), 0, item); front[age] = (front[age] || 0) + 1; };
    const usesHall = (pm.musters || []).some(k => X.musters[k] && X.musters[k].line && ctx.lineKeys.includes(X.musters[k].line)) || plan.some(x => x[0] === "t" && ctx.T[x[1]]?.building === "mustering-hall");
    if (usesHall && Number.isFinite(pm.hallAge)) { ctx.removePlan("b", "mustering-hall"); insertAt(Math.max(2, pm.hallAge), ["b", "mustering-hall"]); }
    for (const age of [1, 2, 3]) for (let i = 0; i < (pm.towerHouses?.[age] || 0); i++) insertAt(age, ["b", "tower-house"]);
  },

  step(ctx) {
    const { S, P, M, B } = ctx; const X = M.scots, Z = S.scots, pm = P.mech || {};
    for (const r of RS) { S.res[r] += Z.held[r]; Z.held[r] = 0; }   // set-aside resources are spendable inside this hook
    // ----- Highland Cattle: one queue per Tower House (and the Tower of Skye)
    const C = Z.cattle, producers = (S.bld["tower-house"] || 0) + (Z.skye ? 1 : 0);
    while (C.timers.length < producers) C.timers.push(0);
    for (let i = 0; i < C.timers.length; i++) {
      if (C.timers[i] > 0) { C.timers[i]--; if (!C.timers[i]) { C.training--; C.grazing++; C.bought++; C.peak = Math.max(C.peak, C.grazing);
        ctx.ev("done", "unit", "Highland Cattle", "training complete", "grazing at Berry Bushes (30 food per minute)", null, { producer: "tower-house", queue: i, count: 1, pbgid: "highland_cattle_sco" }); } continue; }
      const want = Math.min(C.cap, pm.cattle?.[S.age] ?? 0);
      if (S.t < (pm.cattleFrom || 0) || C.grazing + C.training >= want) continue;
      const c = ctx.priced(X.cattle.cost, "unit", "highland-cattle"); if (!ctx.can(c)) continue;
      ctx.pay(c); C.timers[i] = X.cattle.time; C.training++;
      ctx.ev("train", "unit", "Highland Cattle", "Tower House free and below the cattle target", "training started", c, { producer: "tower-house", queue: i, count: 1, duration: X.cattle.time, readyAt: S.t + X.cattle.time, pbgid: "highland_cattle_sco" });
    }
    // ----- Mustering Hall Influence: tiers from military production buildings; a charge per tier reached
    if (Z.hall) {
      Z.structures = X.hall.structures.reduce((s, k) => s + (S.bld[k] || 0), 0);
      const tier = X.hall.tiers.filter(n => Z.structures >= n).length;
      if (tier > Z.maxTier) { Z.charges += tier - Z.maxTier; ctx.ev("done", "military", `Mustering Hall Influence tier ${tier}`, `${Z.structures} military buildings in its influence`, `+${tier - Z.maxTier} muster charge(s)${tier >= 2 ? `, musters ${Math.round(X.hall.reduction[tier] * 100)}% cheaper` : ""}`, null, {}); Z.maxTier = tier; }
      Z.tier = tier;
    }
    // ----- musters in progress: 5 s action, then one warrior every unitSeconds
    for (const j of Z.jobs) {
      if (j.left > 0) { j.left--; if (!j.left) { j.next = S.t + j.unitSeconds; ctx.ev("done", "military", j.name, "muster action complete", `${j.units} warriors come out one every ${j.unitSeconds} s`, null, { muster: j.key }); } continue; }
      if (j.spawned < j.units && S.t >= j.next) { j.spawned++; j.next += j.unitSeconds; unitOut(ctx, j.line, 1, "mustering-hall", `mustered (${j.name}, ${j.spawned}/${j.units})`, "muster");
        if (j.spawned === j.units) { ctx.mark("muster_" + j.key + "_out"); Z.log.find(x => x.key === j.key && x.start != null).allOut = S.t; } }
    }
    Z.jobs = Z.jobs.filter(j => j.left > 0 || j.spawned < j.units);
    const nm = nextMuster(ctx);
    if (nm) {
      const { key, m, units, food } = nm;
      if (room(ctx) < units) makeRoom(ctx, units, `room for ${units} mustered warriors`);
      if (room(ctx) >= units && S.res.food >= food) {
        const c = { food }; ctx.pay(c, "units"); Z.charges--; Z.done[key] = S.t; S.army[m.line].training += units;
        Z.jobs.push({ key, name: m.name, line: m.line, units, spawned: 0, left: m.action, unitSeconds: m.unitSeconds, next: null });
        Z.log.push({ key, name: m.name, start: S.t, units, food, tier: Z.tier, lookout: Z.lookout, actionDone: S.t + m.action, allOut: null });
        ctx.mark("muster_" + key);
        ctx.ev("tech", "military", m.name, `muster charge available (Influence tier ${Z.tier}, ${Z.charges + 1} charge(s))`, `${m.action} s action, then ${units} ${lineName(ctx, m.line)} one every ${m.unitSeconds} s`, c, { muster: key });
      }
    }
    // ----- Snowdoun Gate: 3 free infantry of the toggled type per cycle
    if (Z.snow) {
      const sn = Z.snow;
      if (sn.timer > 0) { sn.timer--; if (!sn.timer) { unitOut(ctx, sn.line, sn.batch, "landmark:snowdoun-gate", "free toggled infantry (Snowdoun Gate)", 0); sn.batch = 0; } }
      else {
        const n = X.snowdoun.batch;
        if (room(ctx) >= n) { const d = Math.ceil(X.snowdoun.cycle[sn.line] / (1 + X.snowdoun.perHallTech * Z.hallTechs));
          sn.timer = d; sn.batch = n; S.army[sn.line].training += n;
          ctx.ev("train", "unit", lineName(ctx, sn.line), "Snowdoun Gate toggle on (free)", "training started", null, { producer: "landmark:snowdoun-gate", queue: 0, count: n, duration: d, readyAt: S.t + d, line: sn.line }); }
        else makeRoom(ctx, n, "room for the next Snowdoun Gate batch");
      }
    }
    // ----- Monastery for relics as soon as Castle Age completes
    const K = Z.kirk;
    if (relicWanted(ctx) && S.age >= 3 && !(S.bld.monastery > 0) && !S.jobs.some(j => j.name === "monastery") && ctx.startBuild("monastery", 1, "Castle Age reached: Monastery to hold relics")) { Z.monasteryStart = S.t; ctx.removePlan("b", "monastery"); }
    // ----- Kirkmen: relics from Castle Age, then Fishponds (Kirkmen take population; it is reserved while they train)
    const pondCap = pondCapacity(ctx), wantK = (pm.kirkmen || 0) + Math.min(pm.fishponds || 0, pondCap);
    const kirkSite = (S.bld.monastery || 0) > 0 ? "monastery" : Z.sod && (pm.fishponds || 0) > 0 ? "landmark:stone-of-destiny" : null;
    if (K.timer > 0) { K.timer--; if (!K.timer) { K.training--; K.kirkmen++; K.idle++; ctx.ev("done", "unit", "Kirkman", "training complete", "religious unit available", null, { producer: K.site, queue: 0, count: 1, pbgid: "unit_monk_3_sco" }); } }
    else if (kirkSite && K.kirkmen + K.training < wantK && room(ctx) >= 1) {
      const c = ctx.priced(X.kirkman.cost, "unit", "kirkman");
      if (ctx.can(c)) { ctx.pay(c, "units"); K.timer = X.kirkman.time; K.training++; K.site = kirkSite; S.others++;
        ctx.ev("train", "unit", "Kirkman", K.relicsLeft > 0 ? "relics on the map" : "a Fishpond to work", "training started", c, { producer: kirkSite, queue: 0, count: 1, duration: X.kirkman.time, readyAt: S.t + X.kirkman.time, pbgid: "unit_monk_3_sco" }); }
    }
    for (const tr of K.trips) if (!tr.done && S.t >= tr.end) { tr.done = true; K.relicsIn++; K.idle++; ctx.ev("done", "economy", "Relic placed in the Monastery", "Kirkman returned with a relic", `${K.relicsIn} relic(s) generating gold`, null, { relics: K.relicsIn }); if (K.relicsIn === 1) ctx.mark("first_relic"); }
    K.trips = K.trips.filter(t => !t.done);
    for (const pj of K.pondJobs) if (!pj.done && S.t >= pj.end) { pj.done = true; K.ponds++; ctx.ev("done", "economy", "Fishpond worked by a Kirkman", "Fishpond built", "40 gold per minute and faster gathering nearby", null, {}); }
    K.pondJobs = K.pondJobs.filter(p => !p.done);
    while (K.idle > 0) {
      if (K.relicsLeft > 0 && S.age >= X.kirkman.relicAge && (S.bld.monastery || 0) > 0) {
        const walk = Math.ceil(2 * (pm.relicDistanceTiles ?? 0) / X.kirkman.speed); K.relicsLeft--; K.idle--; K.trips.push({ end: S.t + walk });
        if (K.firstTrip == null) { K.firstTrip = S.t; ctx.mark("relics_start"); }
        ctx.ev("done", "economy", "Kirkman sent for a relic", "relic on the map and a Monastery to hold it", `back in ${walk} s (${pm.relicDistanceTiles} tiles each way at ${X.kirkman.speed} tiles/s)`, null, {});
        continue;
      }
      if (K.ponds + K.pondJobs.length < Math.min(pm.fishponds || 0, pondCap)) { K.idle--; K.pondJobs.push({ end: S.t + X.fishpond.build }); continue; }
      break;
    }
    // ----- set aside for the next muster (food) and, from the start of the Castle landmark, the Monastery and relic Kirkmen
    const want = { food: 0, wood: 0, gold: 0, stone: 0 };
    const nm2 = nextMuster(ctx); if (nm2) want.food += nm2.food;
    if (relicWanted(ctx) && castleStarted(ctx)) {
      if (!(S.bld.monastery > 0) && !S.jobs.some(j => j.name === "monastery")) want.wood += ctx.sum(ctx.priced(B.monastery.cost, "building", "monastery"));
      want.gold += Math.max(0, (pm.kirkmen || 0) - K.kirkmen - K.training) * ctx.sum(ctx.priced(X.kirkman.cost, "unit", "kirkman"));
    }
    const keepFood = ctx.completedV() < ctx.vt() ? ctx.sum(ctx.villagerCost()) * S.tcTimer.length : 0;
    for (const r of RS) { const mv = Math.max(0, Math.min(want[r], S.res[r] - (r === "food" ? keepFood : 0))); S.res[r] -= mv; Z.held[r] = mv; }
  },

  passive(ctx, o, inc) {
    const { S, P, M } = ctx; const X = M.scots, Z = S.scots; if (!Z) return; const pm = P.mech || {};
    // grazing cattle: one per Berry Bush that still stands (main patch plus far patches)
    const bushes = Math.ceil(S.stock.berries / P.map.berries[1] - 1e-9) + Math.ceil(S.stock.berriesFar / P.map.berriesFar[2] - 1e-9);
    o.food += Math.min(Z.cattle.grazing, bushes) * X.cattle.foodPerSecond * ctx.mulOf("gather_rate", ["highland-cattle"]);
    const K = Z.kirk;
    if (K.relicsIn) { const g = K.relicsIn * (pm.relicGoldPerMinute ?? 0) / 60; o.gold += g; K.gold += g; }
    if (K.ponds) {
      o.gold += K.ponds * X.fishpond.goldPerSecond;
      // the buff does not stack: each pond reaches its own group of workers, and a worker counts once
      const workers = Math.max(1, ctx.completedV() - S.builders), share = Math.min(1, K.ponds * (pm.pondWorkers ?? 0) / workers);
      const aura = Z.stew && X.fishpond.stewPonds ? X.fishpond.stewPonds.aura : X.fishpond.aura;
      if (inc) for (const r of RS) o[r] += aura * share * (inc[r] || 0);
    }
  },

  finishBuild(ctx, name) {
    const { S, P, B, M } = ctx; const Z = S.scots, X = M.scots, pm = P.mech || {};
    if (name === "mustering-hall" && !Z.hall) { Z.hall = true; Z.charges += X.hall.defaultCharges; ctx.mark("mustering_hall"); }
    if (Z.sod && B[name] && (name !== "farm" || pm.rebateFarms)) {
      const g = X.rebate * ctx.sum(ctx.priced(B[name].cost, "building", name));
      if (g > 0) { S.res.gold += g; Z.rebate += g; ctx.ev("done", "economy", "Stone of Destiny rebate", `${B[name].name} built in reach`, `+${Math.round(g)} gold (30% of its cost)`, null, {}); }
    }
    if (Z.abbeyPending) placeRelic(ctx);
  },

  finishLandmark(ctx, job) {
    const { S, M, P } = ctx; const Z = S.scots, X = M.scots, pm = P.mech || {};
    if (X.highland.includes(job.key)) { Z.highland++; Z.cattle.cap += X.cattle.capPerHighland; }
    if (X.lowland.includes(job.key)) Z.lowland++;
    if (job.key === "stone-of-destiny") Z.sod = true;
    if (job.key === "tower-of-skye") Z.skye = true;
    if (job.key === "three-loch-lookout") { Z.lookout = true; Z.charges += X.hall.lookoutCharges; }
    if (job.key === "abbey-of-the-isles") { Z.abbeyPending = true; placeRelic(ctx); }
    if (job.key === "snowdoun-gate" && pm.snowdoun && ctx.lineKeys.includes(pm.snowdoun) && X.snowdoun.cycle[pm.snowdoun]) Z.snow = { line: pm.snowdoun, timer: 0, batch: 0 };
  },

  finishTech(ctx, name) {
    const { S, M } = ctx; const Z = S.scots, sp = M.scots.fishpond.stewPonds;
    if (ctx.T[name]?.building === "mustering-hall") Z.hallTechs++;
    // Stew Ponds: Fishpond capacity +1, pond buff 10% -> 20%, one free Kirkman (who works a pond)
    if (sp && name === sp.id && !Z.stew) { Z.stew = true; const n = sp.freeKirkmen || 0; Z.kirk.kirkmen += n; Z.kirk.idle += n; S.others += n;
      if (n) ctx.ev("done", "unit", "Kirkman", "free Kirkman from Stew Ponds", "religious unit available", null, { producer: "mustering-hall", queue: 0, count: n, pbgid: "unit_monk_3_sco" }); }
  },

  snapshot(ctx, row) {
    const Z = ctx.S.scots; if (!Z) return;
    row.scots = { held: Object.fromEntries(RS.map(r => [r, Math.round(Z.held[r])])), cattle: Z.cattle.grazing, cattleCap: Z.cattle.cap, charges: Z.charges, hallTier: Z.tier, hallStructures: Z.structures,
      musters: Z.log.filter(m => m.start != null).length, kirkmen: Z.kirk.kirkmen, relics: Z.kirk.relicsIn, fishponds: Z.kirk.ponds, rebate: Math.round(Z.rebate) };
  },

  result(ctx, out) {
    const Z = ctx.S.scots; if (!Z) return;
    out.scots = { musters: Z.log, cattlePeak: Z.cattle.peak, cattleBought: Z.cattle.bought, cattleCap: Z.cattle.cap, hallTier: Z.maxTier, chargesLeft: Z.charges,
      monasteryStart: Z.monasteryStart, kirkmen: Z.kirk.kirkmen, stewPonds: !!Z.stew, relicsPlaced: Z.kirk.relicsIn, relicGold: Math.round(Z.kirk.gold), relicsStart: Z.kirk.firstTrip, fishponds: Z.kirk.ponds,
      rebateGold: Math.round(Z.rebate), abbeyRelicIn: Z.abbeyOn, held: Z.held };
    out.summary.scots = { cattle: Z.cattle.grazing, musters: Z.log.filter(m => m.start != null).map(m => m.key), relics: Z.kirk.relicsIn };
  },
};
// Abbey of the Isles: the Saint's Relic goes into the first production building of the build's lines (x2.35 production).
function placeRelic(ctx) {
  const { S, M } = ctx; const Z = S.scots; const p = S.prod.find(x => !x.name.startsWith("landmark:"));
  if (!p) return;
  p.mult = (p.mult || 1) * M.scots.abbeyMultiplier; Z.abbeyPending = false; Z.abbeyOn = p.name;
  ctx.ev("done", "military", "Saint's Relic moved", `Abbey of the Isles relic placed in ${ctx.B[p.name]?.name || p.name}`, `production x${M.scots.abbeyMultiplier} there`, null, {});
}
(root.AoE4CivMechanics = root.AoE4CivMechanics || {}).scots = scots;
})(typeof window !== "undefined" ? window : globalThis);
