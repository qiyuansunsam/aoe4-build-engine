"""Compare model predictions with every independent measurement found (data/*.json forum dumps).
Rows marked FIT were used to set a parameter; every other row is a prediction."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import eco
from eco import r_eff, sheep_group_rate, RAW_2021, build_time

WB = ("wheelbarrow",)
rows = []
def row(src, what, measured, predicted, note=""):
    err = (predicted - measured) / measured * 100
    rows.append((src, what, measured, predicted, err, note))

# DrAllurian, forums.ageofempires.com t/181731, 2021-11-08, 8 villagers, ~3 min trials, food/min/villager, launch patch
m = lambda x: 60 * x
row("DrAllurian 2021", "farm adjacent TC, no techs", 36.8, m(r_eff("farm", 0, raw=RAW_2021)), "FIT t_turn")
row("DrAllurian 2021", "farm adjacent TC + Wheelbarrow", 37.0, m(r_eff("farm", 0, WB, raw=RAW_2021)))
row("DrAllurian 2021", "farm diagonal (d=0.33), no techs", 35.5, m(r_eff("farm", 0.33, raw=RAW_2021)), "FIT d_diag")
row("DrAllurian 2021", "farm diagonal + Wheelbarrow", 36.0, m(r_eff("farm", 0.33, WB, raw=RAW_2021)))
row("DrAllurian 2021", "8 vills sheep under TC, no techs", 40.0, m(sheep_group_rate(8) / 8), "FIT t_sheep_group")
row("DrAllurian 2021", "8 vills sheep naive (d~2.6), no techs", 33.0, m(sheep_group_rate(8, d=2.6) / 8), "d from 'about a tile' path round TC, est")
row("DrAllurian 2021", "8 vills sheep naive + Wheelbarrow", 40.0, m(sheep_group_rate(8, WB, d=2.6) / 8), "model under-predicts; noisy 3-min trial")
row("DrAllurian 2021", "Horticulture multiplier", 1.10, r_eff("farm", 0, ("horticulture",), raw=RAW_2021) / r_eff("farm", 0, raw=RAW_2021))

# Sonnenbank, Steam discussion 2021-11-19, 10 min recording, f/s. Values equal raw attributes within 2%.
for res, meas in (("sheep", 0.75), ("berries", 0.66), ("farm", 0.625), ("deer", 0.827)):
    row("Sonnenbank 2021", f"{res} in place (d=0)", meas, r_eff(res, 0, raw=RAW_2021), "reads as raw rate; model is in-place effective")

# Community rule of thumb, forums t/205270 (2022): Wheelbarrow +7-8% on walking resources, +2-3% in place
row("forum 205270 2022", "Wheelbarrow gain in place (d=0), %", 2.5, 100 * (r_eff("gold", 0, WB) / r_eff("gold", 0) - 1), "measured given as 2-3%")
row("forum 205270 2022", "Wheelbarrow gain walking (d=1), %", 7.5, 100 * (r_eff("wood", 1, WB) / r_eff("wood", 1) - 1), "measured given as 7-8%")
row("forum 205270 2022", "sheep 1 tile away, no WB, f/s (their arithmetic)", 0.66, r_eff("sheep", 1, t_turn=0), "same formula, t_turn=0")

# Build time: base from buildings_all.json; formula 3/(n+2) is community, unverified
row("formula check", "TC 150 s base, 6 builders, s", 56.0, build_time(150, 6), "no measurement found; placeholder")

print(f"{'source':20} {'quantity':44} {'meas':>8} {'model':>8} {'err%':>6}  note")
for s, w, me, pr, er, n in rows:
    print(f"{s:20} {w:44} {me:8.3f} {pr:8.3f} {er:6.1f}  {n}")
