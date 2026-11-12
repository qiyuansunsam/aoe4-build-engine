-- Ceiling test: the recorder keeps only its heartbeat (no entity sampling, no event handlers).
function RR_SampleBody() print("R|T|" .. RR_Time()) end
local n = 0
for _, f in ipairs({ RR_OnKill, RR_OnUpgrade, RR_OnConstruction, RR_OnUpgradeQueued, RR_OnUpgradeCancelled, RR_OnConstructionStart,
  RR_OnConstructionWorker, RR_OnConstructionCancelled, RR_OnStrategicPoint, RR_OnHit, RR_OnFired, RR_OnLanded, RR_OnIncome, RR_OnBuilt }) do
  if pcall(Rule_RemoveGlobalEvent, f) then n = n + 1 end
end
print("R|PROBE|light removed " .. n)
