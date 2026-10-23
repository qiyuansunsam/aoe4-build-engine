"""Deterministic build-order timeline (1 s steps) on top of eco.py. No game simulation: every number is
cost / rate / time arithmetic from the parameter tables. Scenario: Abbasid 3 TC, Economic wing Feudal,
Culture or Military wing Castle, the other at Imperial; target = all Camel Rider techs + 200 pop.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import eco

R = ("food", "wood", "gold", "stone")

def cost(f=0, w=0, g=0, s=0): return {"food": f, "wood": w, "gold": g, "stone": s}

# --- Abbasid data (data/tech_all.json, buildings_all.json, units_all.json, civ_abbasid.json) ---
WING_COST = {2: cost(400, 0, 200), 3: cost(1200, 0, 600), 4: cost(2400, 0, 1200)}
WING_TIME = 100                       # wings build without villagers (civ overview)
HOW = ("house-of-wisdom", cost(0, 50), 30)
BLD = {"mill": (cost(0, 50), 20), "lumber-camp": (cost(0, 50), 20), "mining-camp": (cost(0, 50), 20),
       "house": (cost(0, 50), 15), "town-center": (cost(0, 400, 0, 300), 150), "stable": (cost(0, 150), 30),
       "blacksmith": (cost(0, 150), 25), "madrasa": (cost(0, 450), 60), "farm": (cost(0, 75), 6)}
ECO_BLD = {"mill", "lumber-camp", "mining-camp", "house", "farm"}   # Fertile Crescent -30%
# tech: (age, cost, time, building, wing requirement)
TECH = {
    "fresh-foodstuffs": (2, cost(50, 0, 75), 20, "mill", None), "fertile-crescent": (2, cost(25, 0, 75), 30, "how", "economic"),
    "wheelbarrow": (1, cost(0, 50, 150), 90, "mill", None), "horticulture": (2, cost(0, 50, 100), 45, "mill", None),
    "double-broadax": (2, cost(50, 0, 100), 45, "lumber-camp", None), "specialized-pick": (2, cost(0, 50, 100), 45, "mining-camp", None),
    "preservation-of-knowledge": (2, cost(0, 25, 75), 30, "how", "culture"),
    "bloomery": (2, cost(50, 0, 125), 60, "blacksmith", None), "fitted-leatherwork": (2, cost(50, 0, 125), 60, "blacksmith", None),
    "iron-undermesh": (2, cost(0, 50, 125), 60, "blacksmith", None),
    "decarbonization": (3, cost(100, 0, 250), 60, "blacksmith", None), "insulated-helm": (3, cost(100, 0, 250), 60, "blacksmith", None),
    "wedge-rivets": (3, cost(0, 100, 250), 60, "blacksmith", None), "camel-handling": (3, cost(75, 0, 200), 30, "blacksmith", None),
    "military-academy": (3, cost(0, 100, 250), 60, "blacksmith", None),
    "camel-rider-shields": (3, cost(75, 0, 200), 45, "stable", None),
    "fertilization": (3, cost(0, 100, 250), 60, "mill", None), "lumber-preservation": (3, cost(100, 0, 250), 60, "lumber-camp", None),
    "shaft-mining": (3, cost(0, 100, 250), 60, "mining-camp", None), "agriculture": (3, cost(0, 75, 200), 45, "how", "economic"),
    "damascus-steel": (4, cost(150, 0, 350), 60, "blacksmith", None), "master-smiths": (4, cost(150, 0, 350), 60, "blacksmith", None),
    "angled-surfaces": (4, cost(0, 150, 350), 60, "blacksmith", None),
    "camel-rider-barding": (4, cost(100, 0, 225), 45, "stable", None), "elite-camel-riders": (4, cost(300, 0, 700), 60, "stable", None),
    "camel-support": (4, cost(300, 0, 700), 90, "how", "military"), "biology": (4, cost(500, 0, 1000), 90, "madrasa", None),
    "precision-cross-breeding": (4, cost(0, 250, 500), 75, "mill", None), "crosscut-saw": (4, cost(250, 0, 500), 75, "lumber-camp", None),
    "cupellation": (4, cost(0, 250, 500), 75, "mining-camp", None), "improved-processing": (4, cost(0, 300, 700), 90, "how", "economic"),
}
CAMEL_TECHS = {"bloomery", "fitted-leatherwork", "iron-undermesh", "decarbonization", "insulated-helm", "wedge-rivets",
               "camel-handling", "camel-rider-shields", "damascus-steel", "master-smiths", "angled-surfaces",
               "camel-rider-barding", "elite-camel-riders", "biology"}
ECO_T2 = ["fertilization", "lumber-preservation", "shaft-mining", "agriculture"]
ECO_T3 = ["precision-cross-breeding", "crosscut-saw", "cupellation", "improved-processing"]
TRADE = {"d": 80, "k_map": 1.3, "neutral": 1.2, "speed": 1.0, "turn": 4.0}   # grade C; g(d) = k*(0.0119 d^2 + 0.176 d) fitted to two forum points (large map)
TECH.update({"city-planning": (2, cost(0, 25, 75), 30, "how", "admin"), "algebra": (3, cost(100, 0, 250), 60, "how", "culture")})
MIL_TECHS = {"bloomery", "fitted-leatherwork", "iron-undermesh", "decarbonization", "insulated-helm", "wedge-rivets", "camel-handling",
             "camel-rider-shields", "damascus-steel", "master-smiths", "angled-surfaces", "camel-rider-barding", "elite-camel-riders",
             "military-academy", "biology"}
ALGEBRA_PER_TECH = {"food": 3 / 20, "wood": 3 / 20, "gold": 2 / 20}   # wiki Algebra: 3f 3w 2g per military tech every 20 s, cap 58/58/38.67
GOLDEN_TIERS = (10, 20, 30, 50, 75)                                     # patch 16.2: gather +15%, build speed +20%, camel dmg +15%, trader +20%, infantry +10%
CP_FARM_ADJ = 0.0      # City Planning: average identical neighbours per farm (0 = farms excluded; 3 = farm grid), unverified
CP_STABLE_ADJ = 1.6    # 5 stables in a row
CP_TC_ADJ = 4 / 3      # 3 TCs in a row (1, 2, 1 neighbours)
CP_BS_ADJ = 1.0        # 2 blacksmiths touching
CAMEL = (cost(130, 45, 45), 35)
VIL = (50, 20)
GOLDEN = {10: "t1", 30: "t2", 60: "t3"}        # civ overview thresholds
POP_PER_HOUSE, POP_PER_TC, POP_MAX = 10, 10, 200   # TC pop value: parameter, unconfirmed

# --- Map model (MODEL.md section 4, grade C) ---
MAP = {"sheep": (16, 200, 0.0), "berries": (8, 350, 1.0), "deer": (8, 350, 1.5),   # (nodes, food each, d); orchard +100
       "wood_d": 1.5, "gold_d": 1.0, "stone_d": 1.0}
TECH_TO_ECO = {"wheelbarrow": "wheelbarrow", "horticulture": "horticulture", "double-broadax": "double_broadax",
               "specialized-pick": "specialized_pick", "fertilization": "fertilization", "lumber-preservation": "lumber_preservation",
               "shaft-mining": "shaft_mining", "precision-cross-breeding": "precision_cross_breeding", "crosscut-saw": "crosscut_saw",
               "cupellation": "cupellation"}


class Sim:
    def __init__(self, wings=("economic", "culture", "admin"), vil_target=120, stables=5, blacksmiths=1, pause_for_age=False, window=4, eco="minimal", eco_feudal="feudal", log=False):
        self.n_bs, self.pause_for_age, self.window, self.eco_mode, self.eco_feudal = blacksmiths, pause_for_age, window, eco, eco_feudal
        self.order = tuple(wings); self.castle_wing, self.imperial_wing = wings[1], wings[2]
        self.traders = 0
        self.vil_target, self.n_stables, self.log = vil_target, stables, log
        self.t = 0; self.res = {"food": 200, "wood": 200, "gold": 100, "stone": 0}
        self.V = 6; self.builders = 0; self.age = 1; self.wings = []; self.techs = set(); self.camels = 0
        self.bld = {"town-center": 1}; self.farms = 0; self.houses = 0; self.popcap = POP_PER_TC
        self.tc_timer = [0]; self.stable_timer = []; self.research = []   # [building, tech, remaining]
        self.jobs = []          # (name, remaining, builders)
        self.stock = {"sheep": MAP["sheep"][0] * MAP["sheep"][1], "berries": MAP["berries"][0] * (MAP["berries"][1] + 100), "deer": MAP["deer"][0] * MAP["deer"][1]}
        self.wing_timer = None; self.milestones = {}; self.spent = {r: 0 for r in R}
        self.plan = self.make_plan()

    # ---------- plan ----------
    def make_plan(self):
        f, c, i = self.order
        def wt(w, age):
            return {("economic", 2): [("t", "fertile-crescent")], ("economic", 3): [("t", "agriculture")], ("economic", 4): [("t", "improved-processing")],
                    ("culture", 2): [("t", "preservation-of-knowledge")], ("culture", 3): [("t", "algebra")], ("admin", 2): [("t", "city-planning")]}.get((w, age), [])
        p = [("b", "mill"), ("b", "lumber-camp"), ("b", "mining-camp"), ("b", "house-of-wisdom"), ("age", f)]
        feco = [("t", "wheelbarrow"), ("t", "horticulture"), ("t", "double-broadax"), ("t", "specialized-pick")]
        p += [("t", "fresh-foodstuffs")] + wt(f, 2) + [("b", "town-center")] + (feco[:1] if self.eco_feudal == "feudal" else []) + [("b", "town-center")]
        p += (feco[1:] if self.eco_feudal == "feudal" else []) + [("age", c)]
        p += wt(c, 2) + (feco if self.eco_feudal == "after_castle" else []) + wt(f, 3) + wt(c, 3)
        p += [("b", "blacksmith")] * self.n_bs + [("b", "stable"), ("t", "bloomery"), ("t", "fitted-leatherwork"), ("t", "iron-undermesh"),
              ("t", "camel-rider-shields"), ("t", "camel-handling"), ("t", "military-academy")]
        p += [("b", "stable")] * (self.n_stables - 1)
        t2 = [("t", x) for x in ECO_T2 if x != "agriculture"]
        castle_mil = [("t", "decarbonization"), ("t", "insulated-helm"), ("t", "wedge-rivets")]
        if self.eco_mode == "asap": p += t2 + castle_mil + [("age", i)]
        else: p += castle_mil + [("age", i)] + (t2 if self.eco_mode == "late" else [])
        p += wt(i, 2) + wt(i, 3) + wt(f, 4) + wt(c, 4) + wt(i, 4)
        p += [("t", "elite-camel-riders"), ("t", "camel-rider-barding"), ("b", "madrasa"), ("t", "biology"),
              ("t", "damascus-steel"), ("t", "master-smiths"), ("t", "angled-surfaces")]
        if self.eco_mode != "minimal": p += [("t", x) for x in ECO_T3 if x != "improved-processing"]
        else: p = [x for x in p if x != ("t", "improved-processing")]
        return p

    # ---------- helpers ----------
    def golden(self):
        n = sum(self.bld.values()) + self.farms + self.houses
        return sum(1 for th in GOLDEN_TIERS if n >= th)
    def golden_k(self): return 1.5 if "admin" in self.wings else 1.0
    def gather_mult(self):
        return 1 + 0.15 * self.golden_k() if self.golden() >= 1 else 1.0
    def build_mult(self):
        return 1 / (1 + 0.20 * self.golden_k()) if self.golden() >= 2 else 1.0
    def research_mult(self): return 1.0
    def prod_mult(self):
        m = 0.8 if "military-academy" in self.techs else 1.0
        if "city-planning" in self.techs: m /= 1 + 0.08 * CP_STABLE_ADJ
        return m
    def farm_mult(self):
        return 1 + 0.08 * CP_FARM_ADJ if "city-planning" in self.techs else 1.0
    def price(self, c, kind):
        f = 1.0
        if kind in ("tech", "age") and "preservation-of-knowledge" in self.techs: f *= 0.8
        if kind in ECO_BLD and "fertile-crescent" in self.techs: f *= 0.7
        return {r: c[r] * f for r in R}
    def can(self, c): return all(self.res[r] >= c[r] for r in R)
    def pay(self, c):
        for r in R: self.res[r] -= c[r]; self.spent[r] += c[r]
    def eco_techs(self): return tuple(TECH_TO_ECO[t] for t in self.techs if t in TECH_TO_ECO)
    def mark(self, k):
        if k not in self.milestones: self.milestones[k] = self.t

    # ---------- income ----------
    LONG_RUN = {"food": 0.55, "wood": 0.15, "gold": 0.30, "stone": 0.0}   # fallback: camel cost ratio plus farms

    def targets(self):
        """resources wanted within the next ~60 s: window plan items + standing production."""
        tgt = {r: 0.0 for r in R}
        seen_b = False
        for i, (kind, name) in enumerate(self.plan[:self.window]):
            if kind == "b": seen_b = True
            if kind == "age" and seen_b: break
            c = WING_COST[self.age + 1] if kind == "age" else TECH[name][1] if kind == "t" else (HOW[1] if name == "house-of-wisdom" else BLD[name][0])
            for r in R: tgt[r] += c[r] / (i + 1)
            if kind == "age": break            # nothing past an age-up is buyable yet
        if self.V < self.vil_target:
            tgt["food"] += VIL[0] * (0.6 if "fresh-foodstuffs" in self.techs else 1) / VIL[1] * len(self.tc_timer) * 60
        if self.stable_timer and self.pop() < POP_MAX and self.age >= 3:
            for r in R: tgt[r] += CAMEL[0][r] / CAMEL[1] * len(self.stable_timer) * 60
        tgt["wood"] += self.farm_wood_need() + 50
        return tgt

    farm_need = 0

    def farm_wood_need(self):
        return self.farm_need * self.price(BLD["farm"][0], "farm")["wood"]

    def food_exhausted(self): return all(self.stock[k] <= 0 for k in ("sheep", "berries", "deer"))

    def demand_shares(self):
        tgt = self.targets()
        deficit = {r: max(0.0, tgt[r] - self.res[r]) for r in R}
        tot = sum(deficit.values())
        lr = {"food": 0.7, "wood": 0.15, "gold": 0.15, "stone": 0.0} if self.age == 1 else self.LONG_RUN
        if tot < 1: return dict(lr)
        sh = {r: 0.8 * deficit[r] / tot + 0.2 * lr[r] for r in R}
        n = sum(sh.values()); return {r: sh[r] / n for r in R}

    food_vills = 0

    def income(self):
        gatherers = self.V - self.builders
        sh = self.demand_shares(); techs = self.eco_techs(); gm = self.gather_mult()
        inc = {r: 0.0 for r in R}
        kf = round(gatherers * sh["food"]); kw = round(gatherers * sh["wood"]); kg = round(gatherers * sh["gold"])
        ks = max(0, gatherers - kf - kw - kg)
        left = kf
        for src in ("sheep", "berries", "deer"):
            if left <= 0 or self.stock[src] <= 0: continue
            k = min(left, 24 if src == "sheep" else 16 if src == "berries" else 8)
            if src == "sheep": rate = eco.sheep_group_rate(min(k, 8), techs) * (k / min(k, 8))
            else: rate = k * eco.r_eff(src, MAP[src][2], techs, civ="abbasid" if src == "berries" else "generic")
            rate *= gm; take = min(rate, self.stock[src]); self.stock[src] -= take; inc["food"] += take; left -= k
        self.food_vills = kf
        if left > 0:
            k = min(left, self.farms); inc["food"] += k * eco.r_eff("farm", 0.33, techs) * gm * self.farm_mult()
            spare = left - k                      # no farm yet: gather wood instead of idling
            kw += spare; self.farm_need = spare
        else: self.farm_need = 0
        inc["wood"] += kw * eco.r_eff("wood", MAP["wood_d"], techs) * gm
        inc["gold"] += kg * eco.r_eff("gold", MAP["gold_d"], techs) * gm
        inc["stone"] += ks * eco.r_eff("stone", MAP["stone_d"], techs) * gm
        return inc

    def buy_farms(self):
        need = self.farm_need
        fc = self.price(BLD["farm"][0], "farm")
        while need > 0 and self.can(fc): self.pay(fc); self.farms += 1; need -= 1

    def pop(self): return self.V + self.camels + self.traders

    def trade_income(self):
        if "algebra" not in self.techs: return {}
        n = len(MIL_TECHS & self.techs)
        return {r: min(v * n, {"food": 58, "wood": 58, "gold": 38.67}[r] / 20) for r, v in ALGEBRA_PER_TECH.items()}

    # ---------- actions ----------
    def start_build(self, name, builders):
        c, t1 = (HOW[1], HOW[2]) if name == "house-of-wisdom" else BLD[name]
        pc = self.price(c, name)
        if not self.can(pc) or self.V - self.builders < builders: return False
        self.pay(pc); self.builders += builders
        self.jobs.append([name, eco.build_time(t1, builders) * self.build_mult(), builders]); return True

    def finish_build(self, name):
        self.bld[name] = self.bld.get(name, 0) + 1
        if name == "town-center": self.tc_timer.append(0); self.popcap += POP_PER_TC; self.mark(f"tc{self.bld[name]}")
        if name == "stable": self.stable_timer.append(0)
        if name == "house": self.houses += 1; self.popcap = min(POP_MAX, self.popcap + POP_PER_HOUSE)

    def head_cost(self):
        kind, name = self.plan[0]
        if kind == "age": return self.price(WING_COST[self.age + 1], "age")
        if kind == "t": return self.price(TECH[name][1], "tech")
        return self.price(HOW[1] if name == "house-of-wisdom" else BLD[name][0], name)

    def try_item(self, kind, name):
        if kind == "b":
            if name == "town-center" and self.age < 2: return False
            return self.start_build(name, 4 if name == "town-center" else 1)
        if kind == "age":
            if self.wing_timer is None and self.bld.get("house-of-wisdom") and self.can(self.price(WING_COST[self.age + 1], "age")):
                self.pay(self.price(WING_COST[self.age + 1], "age")); self.wing_timer = WING_TIME; return True
            return False
        age, c, tm, b, wing = TECH[name]
        if self.age < age or (wing and wing not in self.wings): return False
        cap = 1 if b == "how" else self.bld.get(b, 0)
        if sum(1 for r in self.research if r[0] == b) >= cap: return False
        pc = self.price(c, "tech")
        if not self.can(pc): return False
        rm = self.research_mult()
        if b == "blacksmith" and "city-planning" in self.techs and self.bld.get("blacksmith", 0) >= 2: rm /= 1 + 0.08 * CP_BS_ADJ
        self.pay(pc); self.research.append([b, name, tm * rm]); return True

    def saving_for_age(self): return any(k == "age" for k, _ in self.plan) and self.age >= 3

    def try_plan(self):
        ages = [(k, n) for k, n in self.plan if k == "age"]
        if ages:
            idx = self.plan.index(ages[0])
            if not any(k == "b" for k, _ in self.plan[:idx]) and self.try_item(*ages[0]): self.plan.remove(ages[0]); return
        for kind, name in list(self.plan[:self.window]):
            if kind == "age": break                  # nothing past an age-up is attempted early
            if self.try_item(kind, name):
                self.plan.remove((kind, name)); return

    def step(self):
        inc = self.income(); tr = self.trade_income()
        self.last_inc = dict(inc); self.last_trade = dict(tr)
        for r, v in tr.items(): inc[r] += v
        for r in R: self.res[r] += inc[r]
        # houses
        if self.popcap < POP_MAX and self.pop() + 3 * len(self.tc_timer) + len(self.stable_timer) >= self.popcap and not any(j[0] == "house" for j in self.jobs):
            self.start_build("house", 1)
        self.try_plan()
        self.buy_farms()
        # villagers
        vc = VIL[0] * (0.6 if "fresh-foodstuffs" in self.techs else 1)
        for i in range(len(self.tc_timer)):
            if self.tc_timer[i] > 0: self.tc_timer[i] -= 1; continue
            if self.V < self.vil_target and self.pop() < self.popcap and self.res["food"] >= vc:
                tcm = 1 / (1 + 0.08 * CP_TC_ADJ) if "city-planning" in self.techs else 1.0
                self.res["food"] -= vc; self.spent["food"] += vc; self.tc_timer[i] = VIL[1] * tcm; self.V += 1
        # camels
        for i in range(len(self.stable_timer)):
            if self.stable_timer[i] > 0: self.stable_timer[i] -= 1; continue
            if i < sum(1 for r in self.research if r[0] == "stable"): continue
            if self.pause_for_age and self.saving_for_age(): continue
            if self.pop() < min(POP_MAX, self.popcap) and self.can(CAMEL[0]):
                self.pay(CAMEL[0]); self.stable_timer[i] = CAMEL[1] * self.prod_mult(); self.camels += 1
        # timers
        for j in list(self.jobs):
            j[1] -= 1
            if j[1] <= 0: self.jobs.remove(j); self.builders -= j[2]; self.finish_build(j[0])
        for r in list(self.research):
            r[2] -= 1
            if r[2] <= 0: self.research.remove(r); self.techs.add(r[1]); self.mark(r[1])
        if self.wing_timer is not None:
            self.wing_timer -= 1
            if self.wing_timer <= 0:
                self.wing_timer = None; self.age += 1
                wing = self.order[self.age - 2]; self.wings.append(wing)
                if wing == "military" and self.age == 3: self.camels += 2
                if wing == "admin": self.mark("admin")

                self.mark(f"age{self.age}")
        g = self.golden()
        for k in (1, 2, 3, 4, 5):
            if g >= k: self.mark(f"golden{k}")
        self.t += 1

    def run(self, tmax=60 * 60):
        while self.t < tmax:
            self.step()
            done_techs = CAMEL_TECHS <= self.techs
            if done_techs: self.mark("all_camel_techs")
            if self.pop() >= POP_MAX: self.mark("pop200")
            if done_techs and self.pop() >= POP_MAX: self.mark("DONE"); break
        return self


def mmss(s): return f"{int(s)//60}:{int(s)%60:02d}"

if __name__ == "__main__":
    import itertools, csv
    WINGS = ("economic", "culture", "admin", "military")
    rows = []
    import sim as _self
    for order in itertools.permutations(WINGS, 3):
        for vt, mode, cp, bs in itertools.product((120, 140), ("asap", "late", "minimal"), (0.0, 3.0), (1, 2)):
            if cp and "admin" not in order: continue
            _self.CP_FARM_ADJ = cp; globals()["CP_FARM_ADJ"] = cp
            s = Sim(order, vt, eco=mode, blacksmiths=bs).run(); m = s.milestones
            rows.append(dict(feudal=order[0], castle=order[1], imperial=order[2], vil=vt, eco=mode, cp_farms=cp, bs=bs,
                             done=m.get("DONE", 9999), techs=m.get("all_camel_techs", 9999), pop200=m.get("pop200", 9999),
                             age2=m.get("age2", 0), tc3=m.get("tc3", 0), age3=m.get("age3", 0), age4=m.get("age4", 0),
                             g1=m.get("golden1", 0), g2=m.get("golden2", 0), g3=m.get("golden3", 0), spent=int(sum(s.spent.values()))))
    rows.sort(key=lambda r: r["done"])
    with open("results_wings_grid.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print("feudal   castle   imperial vil eco     DONE  techs pop200 | feudal tc3  castle imp  | golden1/2/3       | spent")
    for r in rows[:15]:
        print(f"{r['feudal']:8} {r['castle']:8} {r['imperial']:8} {r['vil']:3} {r['eco']:7} cp{r['cp_farms']} {mmss(r['done'])} {mmss(r['techs'])} {mmss(r['pop200'])} | {mmss(r['age2'])} {mmss(r['tc3'])} {mmss(r['age3'])} {mmss(r['age4'])} | {mmss(r['g1'])} {mmss(r['g2'])} {mmss(r['g3'])} | {r['spent']}")
    print()
    print("best per (feudal, castle):")
    seen = {}
    for r in rows:
        k = (r["feudal"], r["castle"])
        if k not in seen:
            seen[k] = r
            print(f"  {k[0]:8} {k[1]:8} -> imperial {r['imperial']:8} vil {r['vil']} eco {r['eco']:7} DONE {mmss(r['done'])} techs {mmss(r['techs'])} pop200 {mmss(r['pop200'])}")
