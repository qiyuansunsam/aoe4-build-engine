/* Derived per-snapshot measures for recorded (observed) match perspectives.
 * Everything here is calculated from recorded completion/loss timestamps, recorded resource
 * series and recorded upgrade completions, combined with installed catalog facts and the
 * engine's gather-rate model. Each value carries an explicit basis; nothing here is a decoded
 * command stream or a validated executable build. */
(function (root) {
  'use strict';
  const RESOURCES = ['food', 'wood', 'gold', 'stone'];
  const VILLAGER = /\bvillagers?\b/i;
  const BASIS = {
    units: 'Recorded completions minus recorded losses; a completed tier upgrade moves the whole unit line to the new tier',
    population: 'Unit balances plus units in training (recorded completion − installed train time) × installed population cost',
    gathered: 'Recorded bank + recorded cumulative spending − starting bank',
    buildings: 'Recorded building completions minus recorded destructions',
    villagersLost: 'Recorded villager destructions',
    workers: 'Recorded income per resource ÷ per-villager gather rate (installed base rates × eco upgrades completed by this time; one villager per recorded farm); villagers left over are not gathering',
    starts: 'Recorded completion − installed base duration'
  };
  // Engine gather model inputs: drop-off distance in tiles per source (farm and sheep sit beside the drop site).
  const DISTANCE = { farm: 0.33, sheep: 0, wood: 1.5, gold: 1.0, stone: 1.0 };
  const countBefore = (times, t) => { let n = 0; for (const v of times || []) if (Number.isFinite(v) && v <= t) n++; return n; };
  const countTraining = (times, seconds, t) => { if (!(seconds > 0)) return 0; let n = 0; for (const v of times || []) if (Number.isFinite(v) && v > t && v - seconds <= t) n++; return n; };
  const slug = s => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  function lookup(byPbg, id) { return byPbg instanceof Map ? byPbg.get(String(id)) || byPbg.get(id) : byPbg && byPbg[String(id)]; }
  function records(byPbg) { return byPbg instanceof Map ? [...byPbg.values()] : Object.values(byPbg || {}); }
  function classify(record, row) {
    const name = (record && record.name) || (row && row.name) || '';
    return {
      villager: VILLAGER.test(name),
      tc: /town cent(er|re)/i.test(name),
      farm: /^farm$/i.test(name.trim()),
      house: /^house$/i.test(name.trim()),
      camel: /camel rider/i.test(name)
    };
  }
  /** Unit tier lines from catalog tierTransitions: member id → {roots:Set, tail:[id...], upgrades:[upgradeId...]}.
   * Roots that upgrade along the same tail (several base records reach the same Veteran/Elite) share one line. */
  const lineCache = new WeakMap();
  function tierLines(byPbg) {
    if (byPbg && typeof byPbg === 'object' && lineCache.has(byPbg)) return lineCache.get(byPbg);
    const all = records(byPbg), targets = new Set(), byKey = new Map(), lines = new Map();
    for (const r of all) for (const s of r && Array.isArray(r.tierTransitions) ? r.tierTransitions : []) if (s && s.entity) targets.add(s.entity);
    for (const r of all) {
      const steps = r && Array.isArray(r.tierTransitions) ? r.tierTransitions.filter(s => s && s.entity && s.upgrade) : [];
      if (!steps.length || targets.has(r.id)) continue;
      const key = steps.map(s => s.upgrade + '>' + s.entity).join('|');
      if (!byKey.has(key)) byKey.set(key, { roots: new Set(), tail: steps.map(s => s.entity), upgrades: steps.map(s => s.upgrade) });
      byKey.get(key).roots.add(r.id);
    }
    for (const line of byKey.values()) for (const id of [...line.roots, ...line.tail]) if (!lines.has(id)) lines.set(id, line);
    if (byPbg && typeof byPbg === 'object') lineCache.set(byPbg, lines);
    return lines;
  }
  const tierOf = (line, id) => line.roots.has(id) ? 0 : line.tail.indexOf(id) + 1;
  /** Moves each unit line's balance onto its current tier at time t. Rows keep recorded produced/lost. */
  function resolveTiers(unitRows, t, byPbg, upgradeTimes) {
    const lines = tierLines(byPbg), byId = new Map(records(byPbg).map(r => [r.id, r])), groups = new Map(), out = [];
    for (const row of unitRows) {
      const record = lookup(byPbg, row.pbgid), line = record && lines.get(record.id);
      if (!line) { out.push({ ...row }); continue; }
      if (!groups.has(line)) groups.set(line, []);
      groups.get(line).push({ ...row, tier: tierOf(line, record.id) });
    }
    for (const [line, rows] of groups) {
      let tier = 0;
      line.upgrades.forEach((u, i) => { const done = upgradeTimes.get(u); if (Number.isFinite(done) && done <= t) tier = Math.max(tier, i + 1); });
      for (const r of rows) if (r.produced > 0) tier = Math.max(tier, r.tier);
      const own = r => (r.produced || 0) - (r.lost || 0);
      if (tier === 0) { for (const r of rows) out.push({ pbgid: r.pbgid, name: r.name, produced: r.produced, lost: r.lost, balance: own(r) }); continue; }
      const total = rows.reduce((s, r) => s + own(r), 0);
      for (const r of rows) out.push({ pbgid: r.pbgid, name: r.name, produced: r.produced, lost: r.lost, balance: r.tier === tier ? Math.max(0, total) : 0 });
      if (!rows.some(r => r.tier === tier) && total > 0) {
        const record = byId.get(line.tail[tier - 1]);
        if (record && record.source && record.source.pbgid != null) out.push({ pbgid: record.source.pbgid, name: record.name, produced: 0, lost: 0, balance: total });
      }
    }
    return out;
  }
  /** Villagers per resource from recorded income and the engine's per-villager gather rate. */
  function workerSplit(m, villagers, techs, engine) {
    if (!engine || typeof engine.rEff !== 'function' || !engine.RAW || !(villagers > 0)) return null;
    if (!m.income || !RESOURCES.every(r => Number.isFinite(m.income[r]))) return null;
    const P = { raw: engine.RAW, t_turn: engine.DEFAULTS && Number.isFinite(engine.DEFAULTS.t_turn) ? engine.DEFAULTS.t_turn : 0.3 };
    const perMinute = res => engine.rEff(res, DISTANCE[res], techs, P) * 60;
    const income = Object.fromEntries(RESOURCES.map(r => [r, Math.max(0, m.income[r])]));
    const farms = Math.max(0, (m.buildingCounts && m.buildingCounts.farms) || 0);
    const farmFood = Math.min(income.food, farms * perMinute('farm'));
    const raw = {
      food: farmFood / perMinute('farm') + (income.food - farmFood) / perMinute('sheep'),
      wood: income.wood / perMinute('wood'),
      gold: income.gold / perMinute('gold'),
      stone: income.stone / perMinute('stone')
    };
    const sum = RESOURCES.reduce((s, r) => s + raw[r], 0);
    if (!(sum > 0)) return { food: 0, wood: 0, gold: 0, stone: 0, other: villagers };
    const target = Math.min(villagers, Math.round(sum)), scaled = RESOURCES.map(r => raw[r] * target / sum);
    const whole = scaled.map(Math.floor); let rem = target - whole.reduce((a, b) => a + b, 0);
    scaled.map((v, i) => [v - whole[i], i]).sort((a, b) => b[0] - a[0]).forEach(([, i]) => { if (rem > 0) { whole[i]++; rem--; } });
    return { ...Object.fromEntries(RESOURCES.map((r, i) => [r, whole[i]])), other: villagers - target };
  }
  /** Mutates game.snapshots in place, adding derived fields when they are null/missing. */
  function derive(game, byPbg, engine) {
    if (!game || !Array.isArray(game.snapshots) || game.derivedV2) return game;
    engine = engine || (root && root.AoE4Engine) || null;
    const rows = Array.isArray(game.completionRows) ? game.completionRows : null;
    const first = game.snapshots.find(m => m && m.stock) || null;
    const start = first ? Object.fromEntries(RESOURCES.map(r => [r, Number.isFinite(first.stock[r]) ? first.stock[r] : null])) : null;
    const startKnown = !!start && RESOURCES.every(r => start[r] != null) && first.t <= 60;
    const researched = (Array.isArray(game.events) ? game.events : []).filter(e => Number.isFinite(e.t) && /technology|tech|upgrade|research/.test(e.kind || ''));
    const upgradeTimes = new Map();
    for (const e of researched) { const record = lookup(byPbg, e.pbgid); if (record && !(upgradeTimes.get(record.id) <= e.t)) upgradeTimes.set(record.id, e.t); }
    const ecoNames = engine && engine.ECO_TECH ? researched.map(e => ({ t: e.t, key: slug(e.label || e.name || (lookup(byPbg, e.pbgid) || {}).name) })).filter(x => engine.ECO_TECH[x.key]) : [];
    for (const m of game.snapshots) {
      if (!m || !Number.isFinite(m.t)) continue;
      const t = m.t;
      let unitRows = [], training = [];
      if (rows) {
        const unitSource = rows.filter(r => r.sourceType === 'Unit' || r.type === 'Unit');
        unitRows = unitSource.map(r => {
          const produced = countBefore(r.finished, t), lost = countBefore(r.destroyed, t);
          return { pbgid: r.pbgid, name: r.name, produced, lost, balance: produced - lost };
        }).filter(r => r.produced || r.lost);
        training = unitSource.map(r => { const record = lookup(byPbg, r.pbgid); return { record, count: countTraining(r.finished, record && record.trainTimeSeconds, t) }; }).filter(x => x.count > 0);
        const buildingRows = rows.filter(r => r.sourceType === 'Building' || r.type === 'Building');
        const b = { tcs: 0, farms: 0, houses: 0, total: 0 };
        for (const r of buildingRows) {
          const done = countBefore(r.constructed && r.constructed.length ? r.constructed : r.finished, t) - countBefore(r.destroyed, t);
          if (done <= 0) continue;
          const c = classify(lookup(byPbg, r.pbgid), r);
          b.total += done; if (c.tc) b.tcs += done; if (c.farm) b.farms += done; if (c.house) b.houses += done;
        }
        m.buildingCounts = b;
      } else if (Array.isArray(m.unitCounts)) unitRows = m.unitCounts.map(r => ({ pbgid: r.pbgid, name: r.name, produced: r.produced, lost: r.lost, balance: Number.isFinite(r.produced) && Number.isFinite(r.lost) ? r.produced - r.lost : r.balance }));
      if (unitRows.length) {
        unitRows = resolveTiers(unitRows, t, byPbg, upgradeTimes);
        m.unitCounts = unitRows.filter(r => r.produced || r.lost || r.balance).map(r => ({ ...r, countMeaning: BASIS.units }));
      }
      // Population, villagers, villagers lost, camels
      let pop = 0, popKnown = unitRows.length > 0, vil = 0, vilLost = 0, camels = 0;
      for (const r of unitRows) {
        const record = lookup(byPbg, r.pbgid);
        const c = classify(record, r);
        if (c.villager) { vil += r.balance; vilLost += r.lost || 0; }
        if (c.camel) camels += Math.max(0, r.balance);
        if (r.balance <= 0) continue;
        const cost = record && Number.isFinite(record.population) ? record.population : null;
        if (cost == null) { if (record && record.classes && record.classes.includes('military')) popKnown = false; continue; }
        pop += cost * r.balance;
      }
      for (const x of training) if (x.record && Number.isFinite(x.record.population)) pop += x.record.population * x.count;
      if (m.population == null) m.population = popKnown ? pop : null;
      if (m.populationBasis == null) m.populationBasis = BASIS.population;
      if (unitRows.length) m.villagersObservedBalance = vil;
      if (m.villagersLost == null) m.villagersLost = unitRows.length ? vilLost : null;
      if (m.camels == null) m.camels = unitRows.length ? camels : null;
      // Gathered: bank + spending − starting bank (both series recorded by the provider)
      if (m.resourcesGathered == null && startKnown && m.stock && m.spent && RESOURCES.every(r => Number.isFinite(m.stock[r]) && Number.isFinite(m.spent[r]))) {
        m.resourcesGathered = RESOURCES.reduce((s, r) => s + m.stock[r] + m.spent[r] - start[r], 0);
        m.gatheredByResource = Object.fromEntries(RESOURCES.map(r => [r, m.stock[r] + m.spent[r] - start[r]]));
        m.resourcesGatheredBasis = BASIS.gathered;
      }
      // Worker split: recorded income ÷ per-villager gather rate with the eco upgrades completed by now
      if (!m.split) {
        const split = workerSplit(m, m.villagersObservedBalance, ecoNames.filter(x => x.t <= t).map(x => x.key), engine);
        if (split) { m.split = split; m.splitBasis = BASIS.workers; }
      }
    }
    // Start times for recorded completions (research/production/construction)
    if (Array.isArray(game.events)) for (const e of game.events) {
      if (e.start != null || !Number.isFinite(e.t) || e.pbgid == null) continue;
      const record = lookup(byPbg, e.pbgid);
      const d = record && (record.researchTimeSeconds ?? record.trainTimeSeconds ?? record.buildTimeSeconds);
      if (Number.isFinite(d) && d > 0) { e.start = Math.max(0, e.t - d); e.startBasis = BASIS.starts; }
    }
    game.derivedV2 = true;
    game.derivedBasis = BASIS;
    return game;
  }
  const api = { derive, BASIS, RESOURCES, resolveTiers, workerSplit };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.ObservedDerived = api;
})(typeof window !== 'undefined' ? window : typeof globalThis !== 'undefined' ? globalThis : null);
