# Gather rate as a function of distance (model output, not pulled data)

Inputs that are game data: raw rate r (per resource, from the gather table), carry C = 10 (25 hunt), speed v = 1.125 tiles/s (aoe4world villager.json), Wheelbarrow C +5 and v x1.15 (tech_all.json), tech multipliers (tech_all.json).
Input that is a model estimate: t_turn = 0.8 s (derived from two observed effective rates, single observer). Everything below is computed from MODEL.md 2.1.

## Closed form

    r_eff(d) = r / (1 + w),   w = r * (2d/v + t_turn) / C

w is the dimensionless walk factor: seconds spent walking and turning per trip divided by seconds spent gathering per trip. Loss fraction = w / (1 + w). Techs that multiply r raise w too, so a +15% rate tech yields less than 15% at distance; techs that raise C or v lower w, so they yield more at distance.

## Table, r = 0.75, one-way distance d in tiles

| d | base r_eff | w | Wheelbarrow r_eff | WB gain | WB payback, 12 vill (s) | real gain of a +15% rate tech |
|---|---|---|---|---|---|---|
| 0 | 0.708 | 0.06 | 0.721 | 1.9% | 1225 | 14.0% |
| 0.5 | 0.666 | 0.13 | 0.695 | 4.5% | 562 | 13.1% |
| 1 | 0.628 | 0.19 | 0.671 | 6.8% | 390 | 12.3% |
| 2 | 0.565 | 0.33 | 0.628 | 11.1% | 267 | 10.9% |
| 3 | 0.514 | 0.46 | 0.590 | 14.8% | 219 | 9.8% |
| 4 | 0.471 | 0.59 | 0.556 | 18.1% | 196 | 8.9% |
| 6 | 0.403 | 0.86 | 0.499 | 23.7% | 174 | 7.5% |
| 8 | 0.353 | 1.13 | 0.452 | 28.2% | 167 | 6.5% |
| 12 | 0.282 | 1.66 | 0.381 | 35.2% | 168 | 5.2% |
| 20 | 0.201 | 2.73 | 0.290 | 44.1% | 188 | 3.6% |

Wheelbarrow gain is bounded: 1.5 x 1.15 - 1 = 72.5% as d goes to infinity, about 2% at d = 0. Payback (200 res cost, 12 gatherers) is 3 to 4 minutes at d >= 3 and never better than about 165 s because r_eff itself collapses at long range. For d < 1 Wheelbarrow is a weak buy on rate alone (its value there is the speed for building and fleeing).

## What is still assumed, and how to replace it with measurement

1. t_turn (deposit + turnaround) is estimated, not read from data. Two-distance experiment: time k villagers at d1 and d2 for N trips, two equations in (r, t_turn) with v known; solve both. A third distance checks linearity in d (acceleration would make it nonlinear).
2. Gathering may be granted in discrete animation ticks; if so C/r rounds up to whole ticks and r_eff is a step function of C (Wheelbarrow +5 could be worth more or less than the continuous model says).
3. Drop-off position: d is measured to the building edge, not centre; a TC is 6x6 so "at the TC" still has d of about 0.5 to 1.
4. Villager acceleration and path blocking (bumping at a mill) add distance-independent overhead that lands in t_turn.
