# Optional villager attrition assumption

The historical browser model accepts `villagerLossPerMinute` (0–10, default 0)
and `villagerLossStart` (integer seconds, 0–86400, default 300). These are
user-selected economic scenario assumptions, not measured game statistics or a
combat model. Zero disables losses and preserves all prior calculation results.

Losses follow a deterministic schedule. At 2 villagers/minute from 300 seconds,
the first loss occurs at 330, then 360, 390, and so on. Simulation steps cover
`[0, tmax)`, so an event exactly at `tmax` is outside the run. Fractional rates
are allowed. Each loss removes one completed worker before that step's gathering.
Workers assigned to ongoing construction and queued trainees are protected.
If none are eligible, that scheduled loss is skipped; it does not accumulate a
backlog. The model reallocates remaining workers using its existing policy.

Town Centers replace losses through their existing production rules, subject to
the villager target, available food, population cap and training time. Replacement
food is charged at the current villager price. No extra production capacity is
created. The historical model counts queued villagers in population and allocation;
this existing approximation remains, but queued villagers cannot be lost.

Snapshots and the summary include cumulative `villagersLost`. Each actual loss
adds an event with `kind: "loss"`, `cat: "unit"`, `count: 1`, and the cumulative
counter. Losses are not inferred from changes in total villagers, since concurrent
replacement can hide them. Losses may alter resource allocation and milestone
timing; individual resource income is not guaranteed to decrease monotonically.

This extension is browser-only. The Python reference does not yet model attrition,
so Python parity applies only to the existing zero-loss scenario. It does not
simulate fights, raids, attacks on builders or buildings, or targeted resource losses.

Run `node scripts/test_villager_attrition.cjs`. Tests compare zero-loss results with
pre-change hashes (excluding only new metadata), and check losses, replacement
spending, frozen input objects, input bounds and nonnegative worker allocations.
