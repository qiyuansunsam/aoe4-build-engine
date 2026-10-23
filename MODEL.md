# AoE4 Scots engine: theoretical model and data baseline

Status 2026-10-23: model only. No numbers in this file are game values. Every parameter below is a named slot to be filled from game data and then checked by the rule in section 0.

## 0. Acceptance rule for any number

A value enters the engine only when all three hold:

1. Dimensionally consistent (res/s, tiles/s, s, res) and the effect type is read from data (additive vs multiplicative, flat vs percent), never assumed.
2. It reproduces at least one independently known timing when plugged into the model (for example, 6 villagers on food must afford the first landmark at roughly the timing every civ reaches without bonuses).
3. The full model built from such values reproduces the known meta result for a reference civ that is not Scots (section 3.3). Guides and wikis are used only as these checks, never as inputs.

## 1. What the engine computes

State at time t: stockpile R(t) for food, wood, gold, stone; villagers by task; buildings with completion times; techs done; age; population used and cap; army composition.

Dynamics: dR/dt = sum over villagers of effective rate (task, techs, walk distance) + trade + passive income (relics, landmarks, civ bonuses), minus spending events.

Decisions (a build order): timed list of actions: train villager, move k villagers to task X, place building B with n builders, research tech, age up with landmark L, train unit U.

Constraints: stockpile never negative, one item per production building at a time, pop cap, prerequisites (age, building, tech), builders are villagers removed from gathering while building.

Objective: army strength A(T) at horizon T, reported for several T (6:00, 8:00, 10:00, 14:00, 20:00), optionally with a floor on villager count at T.

Form of the problem: villager production is capped by TC count, so eco grows piecewise-linearly, not exponentially. This makes the whole thing a deterministic scheduling problem. The continuous relaxation (fractional villagers, continuous time) is a linear program that gives an upper bound on A(T). Integer schedules found by search (beam or branch and bound over actions) give achievable orders. Gap between the two tells how close a build order is to optimal. No game simulation anywhere.

## 2. Economy model (derivations the data must support)

### 2.1 Effective gather rate with walking

Villager with carry capacity C, raw rate r (res/s), speed v (tiles/s), one-way distance d (tiles) node to drop-off, fixed turnaround overhead t_turn (s). Cycle time = C/r + 2d/v + t_turn. Effective rate:

    r_eff(d) = C / (C/r + 2d/v + t_turn)

Walking loss fraction = (2d/v + t_turn) / (C/r + 2d/v + t_turn). With C=10, r=0.6, v=1.1, d=4 the cycle is about 16.7 + 7.3 s, so r_eff is about 0.42, a 30% loss. Distance is therefore a first-class parameter and drop-off buildings are an eco decision the engine must make, not a given.

Closed form: r_eff = r / (1 + w) with w = r (2d/v + t_turn) / C, the walk factor (walk and turn seconds per trip over gather seconds per trip). Rate techs scale r and therefore w, so they under-deliver at distance; carry and speed techs shrink w, so they over-deliver at distance. Worked table: data/distance_scaling.md.

t_turn is identified by a two-distance measurement (k villagers, N trips at d1 and d2, v known), a third distance tests linearity. Gather may be tick-quantised; then C/r rounds up to whole ticks.

Data: C per resource (and every tech that changes it), r per resource type with every multiplier, v with every speed modifier, t_turn (measure if not in data).

### 2.2 Node depletion and relocation

Node has amount N and position. k villagers deplete it in N / (k r_eff) seconds, then walk delta tiles to the next node. Sheep are herded to the TC and gathered at d about 0 (sheep walk time is a one-off cost per sheep). Deer and boar are gathered in place; whether carcasses decay is a parameter to read from data. Berries: fixed cluster. Trees: each tree has amount N_tree and the forest edge recedes so d grows slowly with wood taken. Gold and stone: small and large mines with different N and d.

Data: N per node type, number of nodes per distance ring, decay rule, distances (section 4).

### 2.3 Farms

Farm costs c_farm, has a build time, is infinite, rate r_farm, placed around Mill or TC so d is about 1. Farm transition is a payback decision: the engine switches when integrated (r_farm_eff minus best alternative food r_eff) over the remaining horizon, priced in wood, exceeds c_farm. Farm techs change r_farm; their stacking rule is read from the effect type in data.

Data: c_farm, r_farm, farm build time, every farm tech (cost, time, age, effect, effect type).

### 2.4 Drop-off buildings

Mill, Lumber Camp, Mining Camp: cost, build time, accepted resources, any gather bonus they grant. Building one reduces d to about 1 for every villager on that node. Payback time = cost / (k * (r_eff(1) - r_eff(d))). The engine builds one when payback is shorter than the remaining time on that node group.

### 2.5 Build time with n builders

T(n) = T1 * f(n). The game applies diminishing returns; f is read from data or measured, never assumed linear. Critical for landmarks (age-up is the critical path) and for extra TCs.

### 2.6 Villager production as the growth cap

TC trains one villager per t_vil at cost c_vil. V(t) <= V0 + TCs * floor(t / t_vil), minus idle time caused by food shortage. Continuous production needs c_vil / t_vil food per second per TC (50/20 = 2.5 food/s if those are the values), which at r_eff about 0.5 to 0.6 means 4 to 5 villagers on food per TC. First consistency check of the gather rates. Extra TC: cost, build time, age; Scots may differ.

### 2.7 Age-up

Landmark cost per age, build time under f(n), which villagers build it (removed from eco for that time), what it unlocks and any passive income it gives. The time at which an all-food 6-villager start affords the first landmark is a direct check of the food parameters against the timing every civ gets without bonuses.

### 2.8 Market and trade

Market: price per 100 as a function of cumulative buys and sells (slope, floor, ceiling, recovery). Trader: cost, speed, gold per trip as a function of market distance (formula, not a table). Needed to price the resource mix (gold-starved late game) and to allow sell-to-age-up orders.

### 2.9 Passive and civ-specific income

Relics, resource-generating landmarks, aura or influence mechanics, every Scots bonus. Each becomes: trigger condition, rate, cap, age, stacking rule. A bonus that cannot be written as one of these is not yet understood and stays out of the engine until it can be.

## 3. Military model

### 3.1 Data per unit, per civ

Cost vector, train time, pop, HP, melee armor, ranged armor, attack damage, damage type, attack period, range, move speed, bonus damage vs classes, abilities. Per production building: cost, build time, age, units. Upgrades: blacksmith tiers, veteran and elite upgrades (cost, time, stat deltas), civ techs.

### 3.2 Army strength metric

Two levels. (a) Resource value: total resources in the standing army; valid only for like-for-like compositions. (b) Combat value: for composition x against reference composition y, effective DPS of unit i on unit j = max(floor_dmg, dmg_i + bonus_ij - armor_j of the matching type) / period_i; side strength is Lanchester-style sqrt(sum HP_i * DPS_i against y). Evaluated against 3 or 4 fixed reference compositions (spear and archer, knights, siege with infantry, mixed). Counters come out of the damage formula, not out of guides.

### 3.3 The only test

Run the engine for reference civs (English, French, HRE, Rus at least) with the same data and check it reproduces their known meta timings and army sizes (English double TC, French Feudal cavalry, HRE fast Castle). Match means the data and model are calibrated and Scots results inherit that calibration. A miss identifies a missing or wrong parameter, and is fixed in the data, never patched in the result.

## 4. Map model (resource distances)

Per standard 1v1 map (Dry Arabia, Lipany, Altai, and the rest of the ranked pool): for each resource type, number of nodes in the start area and their distance from the TC in tiles, plus forest edge distance. Three ways to get it, best first:

1. Map generation scripts in the game files (resource ring distance constraints): exact. Needs the game installed.
2. Tile counts from in-game screenshots or replays at fixed zoom, averaged over 5 to 10 seeds per map: exact per instance.
3. Community estimates: fallback only.

Until measured, d is an explicit parameter per node class with a near, mid and far value, and every result is reported with its sensitivity to d, so no conclusion silently rests on a guessed distance.

## 5. Data inventory

| Parameter | Units | Primary source | Check |
|---|---|---|---|
| Villager cost, train time | food, s | game data (aoe4world/data JSON, parsed from game files) | 2.6 food/s sustain check |
| Carry capacity per resource, Wheelbarrow delta | res | game data, else measure | cycle time in 2.1 |
| Gather rate per resource type | res/s | game data attributes; if only percentages exist, measure res delta over 60 s at d about 0 | 2.7 first landmark timing |
| Villager speed and modifiers | tiles/s | game data | scout speed ratio |
| t_turn | s | measure | 2.1 |
| Node amounts, decay rule | res | game data | depletion time vs known sheep count at Feudal |
| Buildings: cost, build time, age, prerequisites, f(n) | | game data | landmark timing |
| Eco techs: cost, time, age, effect, effect type | | game data | stacking rule read, not assumed |
| Market formula | | game data, else measure | |
| Trade gold per distance | | measure | |
| Every unit, every civ: 3.1 fields | | game data unified plus per-civ files | damage type vs armor type consistency |
| Scots: every bonus, landmark, unique unit, building, tech | | game data; Explorer warns DLC civs can be incomplete, so fall back to game files or in-game tooltips | each bonus rewritten as a 2.9 slot |
| Map distances | tiles | section 4 | sensitivity report |
| Start state (villagers, scout, stockpile, sheep count) per civ | | game data | |

## 6. Non-goals for v1

No pathing, no micro, no villager idle time beyond one fixed efficiency factor (a parameter), no opponent interaction except through the reference compositions in 3.2.
