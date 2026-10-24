/* Recorded unit balances (upgrade tiers merged by ObservedDerived) valued at installed catalog base
 * resource costs. This is army value at base cost, not actual spending or combat strength. */
(function (root) {
  'use strict';
  const RESOURCES = ['food', 'wood', 'gold', 'stone'];
  const basis = 'Recorded unit balances, upgraded tiers merged, × installed base resource cost';
  function summarize(snapshot, byPbg) {
    const lookup = id => byPbg instanceof Map ? byPbg.get(String(id)) || byPbg.get(id) : byPbg && byPbg[String(id)];
    const units = [], unknownRecords = [], invalidCounts = [];
    const resourceValue = Object.fromEntries(RESOURCES.map(r => [r, 0]));
    const available = Array.isArray(snapshot && snapshot.unitCounts);
    let knownValue = 0, militaryCount = 0, valuedCount = 0;
    for (const row of available ? snapshot.unitCounts : []) {
      const reported = row && row.balance;
      const count = Number.isInteger(reported) ? reported : row && Number.isFinite(row.produced) && Number.isFinite(row.lost) ? row.produced - row.lost : reported;
      if (!Number.isInteger(count)) { invalidCounts.push(row && row.pbgid); continue; }
      // Negative net bookkeeping is not an additional unit and has no positive value.
      if (count <= 0) continue;
      const record = lookup(row.pbgid);
      if (!record) { unknownRecords.push({id:String(row.pbgid),name:row.name,count}); continue; }
      if (!Array.isArray(record.classes) || !record.classes.includes('military')) continue;
      militaryCount += count;
      const costKnown = record.cost && RESOURCES.every(r => Number.isFinite(record.cost[r]) && record.cost[r] >= 0);
      const cost = costKnown ? Object.fromEntries(RESOURCES.map(r => [r,record.cost[r]])) : null;
      const unitValue = costKnown ? RESOURCES.reduce((sum,r) => sum + cost[r],0) : null;
      const value = costKnown ? unitValue * count : null;
      if (costKnown) {
        valuedCount += count; knownValue += value;
        for (const r of RESOURCES) resourceValue[r] += cost[r] * count;
      }
      units.push({id:String(row.pbgid),name:record.name || row.name,count,cost,unitValue,value,costKnown:!!costKnown,record});
    }
    const unknownCostUnits = units.filter(u => !u.costKnown).map(u => u.id);
    const complete = available && !unknownRecords.length && !unknownCostUnits.length && !invalidCounts.length;
    return {units,totalValue:complete ? knownValue : null,knownValue,resourceValue,available,basis,
      coverage:{complete,militaryCount,valuedCount,unknownRecords,unknownCostUnits,invalidCounts},
      caveats:['Values use catalog base food, wood, gold and stone costs; discounts, free units and non-resource tokens are excluded.']};
  }
  const api = {summarize,RESOURCES};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.ObservedArmy = api;
})(typeof window !== 'undefined' ? window : typeof globalThis !== 'undefined' ? globalThis : null);
