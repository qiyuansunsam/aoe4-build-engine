"""Run the two Castle-wing scenarios with full event logging and write site/timeline.json."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import sim
from sim import Sim, mmss, R, TECH, BLD, WING_COST, CAMEL, VIL

EFFECT = {
    "mill": "food drop-off, orchard +100 food per bush", "lumber-camp": "wood drop-off", "mining-camp": "gold and stone drop-off",
    "house": "pop cap +10", "town-center": "second production line: +1 villager / 20 s, pop cap +10", "stable": "camel production line (35 s each)",
    "blacksmith": "research line for 9 melee/armour techs", "madrasa": "unlocks Biology", "house-of-wisdom": "age-ups and Golden Age influence",
    "fresh-foodstuffs": "villager cost 50 -> 30 food", "fertile-crescent": "eco buildings and houses -30%", "wheelbarrow": "carry +5, speed +15%",
    "horticulture": "food (not hunt) +10%", "double-broadax": "wood +15%", "specialized-pick": "gold/stone +15%",
    "preservation-of-knowledge": "techs and wings -20%", "city-planning": "+8% work rate per adjacent identical building",
    "algebra": "HoW yields 3f 3w 2g per military tech / 20 s", "agriculture": "farms +15%",
    "bloomery": "melee +1", "fitted-leatherwork": "melee armour +1", "iron-undermesh": "ranged armour +1",
    "decarbonization": "melee +1", "insulated-helm": "melee armour +1", "wedge-rivets": "ranged armour +1",
    "damascus-steel": "melee +1", "master-smiths": "melee armour +1", "angled-surfaces": "ranged armour +1",
    "camel-handling": "camel speed +15%", "camel-rider-shields": "camel melee armour +3", "camel-rider-barding": "camel armour +2",
    "elite-camel-riders": "Elite Camel Rider (320 hp, 16 dmg)", "military-academy": "production 33% faster", "biology": "cavalry hp +25%",
    "fertilization": "food (not hunt) +10%", "lumber-preservation": "wood +15%", "shaft-mining": "gold/stone +15%",
    "economic": "Economic wing: Fertile Crescent, Agriculture, Improved Processing", "culture": "Culture wing: PoK, Algebra, Public Libraries",
    "admin": "Administrative wing: Golden Age x1.5, City Planning, Siege Directive", "military": "Military wing: free units, Boot Camp, Composite Bows, Camel Support",
}
AGE = {2: "Feudal Age", 3: "Castle Age", 4: "Imperial Age"}


class LoggedSim(Sim):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.events = []; self.minutes = []; self.gathered = {r: 0.0 for r in R}; self.alg = {r: 0.0 for r in R}
        self.last_split = {}; self._v_mark = 0; self._c_mark = 0

    def ev(self, kind, label, trigger, effect, cost=None):
        self.events.append(dict(t=self.t, kind=kind, label=label, trigger=trigger, effect=effect,
                                cost={r: round(v) for r, v in cost.items() if v} if cost else {},
                                stock={r: round(self.res[r]) for r in R}, vil=self.V, camels=self.camels, pop=self.pop(), age=self.age))

    # hooks
    def start_build(self, name, builders):
        before = dict(self.res); ok = super().start_build(name, builders)
        if ok:
            auto = name in ("house", "farm")
            self.ev("build", name, "pop cap within 3 villagers of limit" if name == "house" else "next plan item affordable",
                     f"start, {builders} builder(s), {EFFECT.get(name,'')}", {r: before[r] - self.res[r] for r in R})
        return ok
    def finish_build(self, name):
        super().finish_build(name)
        self.ev("done", name, "build complete", EFFECT.get(name, ""))
    def try_item(self, kind, name):
        before = dict(self.res); age0 = self.age; ok = super().try_item(kind, name)
        if ok and kind == "age":
            self.ev("age", f"{AGE[age0 + 1]} via {name} wing", "wing cost reached, all planned TCs started", EFFECT.get(name, ""), {r: before[r] - self.res[r] for r in R})
        if ok and kind == "t":
            self.ev("tech", name, "building free and cost reached", f"research start: {EFFECT.get(name,'')}", {r: before[r] - self.res[r] for r in R})
        return ok
    def buy_farms(self):
        f0 = self.farms; super().buy_farms()
        if self.farms > f0: self.ev("farm", f"+{self.farms - f0} farm(s) -> {self.farms}", "food villagers without a natural food source", "infinite food at d 0.33")
    def step(self):
        techs0 = set(self.techs); age0 = self.age; g0 = self.golden()
        super().step()
        for r in R: self.gathered[r] += self.last_inc[r]
        for r, v in self.last_trade.items(): self.alg[r] += v
        for tname in self.techs - techs0: self.ev("done", tname, "research complete", EFFECT.get(tname, ""))
        if self.age != age0: self.ev("done", AGE[self.age], "wing complete (100 s)", EFFECT.get(self.wings[-1], ""))
        if self.golden() != g0: self.ev("golden", f"Golden Age tier {self.golden()}", f"{sum(self.bld.values())+self.farms+self.houses} buildings in influence",
                                         {1: "gather +15%", 2: "build speed +20%", 3: "camel damage +15%", 4: "trader income +20%", 5: "infantry +10%"}[self.golden()] + (" (x1.5 Administrative)" if "admin" in self.wings else ""))
        if self.V >= self._v_mark + 20: self._v_mark = self.V // 20 * 20; self.ev("vil", f"{self.V} villagers", "continuous TC production", f"{len(self.tc_timer)} TCs")
        if self.camels >= self._c_mark + 20: self._c_mark = self.camels // 20 * 20; self.ev("army", f"{self.camels} camels", "continuous stable production", f"{len(self.stable_timer)} stables")
        if self.t % 60 == 0:
            sh = self.demand_shares(); g = self.V - self.builders
            self.minutes.append(dict(t=self.t, vil=self.V, camels=self.camels, pop=self.pop(), farms=self.farms, age=self.age, golden=self.golden(),
                                     tcs=len(self.tc_timer), stables=len(self.stable_timer), builders=self.builders,
                                     split={"food": round(g * sh["food"]), "wood": round(g * sh["wood"]), "gold": round(g * sh["gold"]), "stone": max(0, g - round(g*sh["food"]) - round(g*sh["wood"]) - round(g*sh["gold"]))},
                                     income={r: round(self.gathered[r]) for r in R}, algebra={r: round(self.alg[r]) for r in R},
                                     stock={r: round(self.res[r]) for r in R}, spent={r: round(self.spent[r]) for r in R},
                                     army_value=self.camels * sum(CAMEL[0].values()), techs=len(self.techs)))
            self.gathered = {r: 0.0 for r in R}; self.alg = {r: 0.0 for r in R}


def run(order, label, **kw):
    s = LoggedSim(order, 120, eco="minimal", **kw).run()
    m = s.milestones
    return dict(label=label, order=list(order), settings=kw, milestones={k: v for k, v in m.items()},
                done=m.get("DONE"), events=s.events, minutes=s.minutes)


if __name__ == "__main__":
    sim.CP_FARM_ADJ = 0.0
    a = run(("economic", "culture", "admin"), "Culture at Castle", blacksmiths=2, eco_feudal="feudal")
    sim.CP_FARM_ADJ = 3.0
    b = run(("economic", "admin", "military"), "Administrative at Castle", blacksmiths=2, eco_feudal="feudal")
    out = dict(patch="16.2.10604", generated="2026-10-23", civ="Abbasid Dynasty", target="all Camel Rider techs + 200 pop", scenarios=[a, b],
               notes=["120 villagers, 5 stables, 2 blacksmiths, 3 TCs before Castle, tier-3 eco techs skipped",
                      "B: 3 TCs, 5 stables, 2 blacksmiths and farms stacked for City Planning",
                      "map: 16 sheep at TC, 8 orchard bushes at 1 tile, 8 deer at 1.5, wood 1.5, gold/stone 1 tile (estimates)"])
    os.makedirs("site", exist_ok=True)
    json.dump(out, open("site/timeline.json", "w"), separators=(",", ":"))
    for sc in (a, b):
        print(sc["label"], mmss(sc["done"]), len(sc["events"]), "events", len(sc["minutes"]), "minutes")
        for e in sc["events"][:12]: print("  ", mmss(e["t"]), e["kind"], e["label"], "|", e["trigger"], "|", e["effect"][:50], e["cost"])
    mins = a["minutes"]
    print("income/min sample:", [(mmss(x["t"]), x["income"], x["split"]) for x in mins[3:16:4]])
