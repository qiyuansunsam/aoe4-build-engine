"""AoE4 economy engine: resource generation from first principles (MODEL.md section 2).

Every constant carries a src tag. 'data' = read from game data (aoe4world/data JSON in ../data),
'wiki' = fandom gather table, 'fit' = fitted to one measurement (named), 'est' = estimate, replace by measurement.
"""
from dataclasses import dataclass, field

# Raw gather rates, res/s, current patch (wiki gather table, resource_api.json). Stone assumed = gold (table cut off).
RAW = {"sheep": 0.75, "farm": 0.75, "berries": 0.69, "deer": 0.825, "boar": 0.9, "fish_shore": 1.0,
       "wood": 0.75, "gold": 0.75, "stone": 0.75}
# Launch-patch raw rates (Nov 2021), used only to compare against 2021 measurements.
RAW_2021 = dict(RAW, farm=0.625, berries=0.66)

FOOD_SOFT = {"sheep", "farm", "berries"}      # food techs apply ("all food except hunted meat and fish")
HUNT = {"deer", "boar"}
MINE = {"gold", "stone"}

CARRY = 10            # data (wiki Villager page)
CARRY_HUNT = 25       # data
SPEED = 1.125         # data villager.json
T_TURN = 0.3          # fit: farm adjacent to TC, no techs, 36.8 food/min (DrAllurian 2021) vs raw 0.625
T_SHEEP_GROUP = 4.0   # fit: 8 vills on sheep under TC 40/min vs model 44/min; seconds lost per sheep switch per villager
SHEEP_FOOD = 200      # wiki
NODE = {"sheep": 200, "berries": 250, "deer": 350, "boar": 2400, "tree": 150,
        "gold_tiny": 1600, "gold_small": 4000, "gold_large": 8000, "stone_small": 1200, "stone_large": 2400}  # wiki

VILLAGER = {"food": 50, "time": 20}   # data (French 19, Golden Horde 37)
TC_FOOD_PER_S = VILLAGER["food"] / VILLAGER["time"]

# Generic eco techs: (age, costs, research s, effects). Values from tech_all.json; stacking multiplicative
# (consistency check: Mongol improved variants quote 1.15*1.17 = 1.35, see data/gather_rates.md).
TECHS = {
    "wheelbarrow":          (1, {"wood": 50, "gold": 150}, 90, {"carry": 5, "speed": 1.15}),
    "survival_techniques":  (1, {"wood": 25, "gold": 75}, 25, {"hunt": 1.15}),
    "horticulture":         (2, {"wood": 50, "gold": 100}, 45, {"food_soft": 1.10}),
    "double_broadax":       (2, {"food": 50, "gold": 100}, 45, {"wood": 1.15}),
    "specialized_pick":     (2, {"wood": 50, "gold": 100}, 45, {"mine": 1.15}),
    "fertilization":        (3, {"wood": 100, "gold": 250}, 60, {"food_soft": 1.10}),
    "lumber_preservation":  (3, {"food": 100, "gold": 250}, 60, {"wood": 1.15}),
    "shaft_mining":         (3, {"wood": 100, "gold": 250}, 60, {"mine": 1.15}),
    "precision_cross_breeding": (4, {"wood": 250, "gold": 500}, 75, {"food_soft": 1.10}),
    "crosscut_saw":         (4, {"food": 250, "gold": 500}, 75, {"wood": 1.15, "carry_wood": 5}),
    "cupellation":          (4, {"wood": 250, "gold": 500}, 75, {"mine": 1.15}),   # drop-off +15%: same effect as rate x1.15
}

# Civ modifiers on the villager loop (wiki Villager page rows). Scots: none published (release 2026-10-29).
CIV = {
    "generic":   {},
    "english":   {"dropoff_bonus": 2},            # +2 per drop-off: rate x (C+2)/C with unchanged trip time
    "lancaster": {"dropoff_bonus": 2, "raw": {"sheep": 0.9}},
    "abbasid":   {"raw": {"berries": 0.8625}, "carry_bonus": {"berries": 3}},
    "delhi":     {"raw": {"berries": 0.8625}, "carry_bonus": {"berries": 3}},
    "hre":       {"carry_mult": 1.4},
    "rus":       {"food_mult": 1.10},             # bounty tier 1 (1.15, 1.20 higher)
    "scots":     {},                              # placeholder until 17.0 notes
}


def _class(res):
    if res in FOOD_SOFT: return "food_soft"
    if res in HUNT: return "hunt"
    if res in MINE: return "mine"
    return res


def r_eff(res, d, techs=(), civ="generic", raw=RAW, t_turn=T_TURN):
    """Effective gather rate (res/s) for one villager at one-way distance d (tiles) from its drop-off.
    r_eff = C / (C/r + 2d/v + t_turn)   (MODEL.md 2.1)"""
    c = CIV[civ]
    r = c.get("raw", {}).get(res, raw[res])
    if res in FOOD_SOFT or res in HUNT: r *= c.get("food_mult", 1.0)
    cap = CARRY_HUNT if res in HUNT else CARRY
    cap += c.get("carry_bonus", {}).get(res, 0)
    v = SPEED
    cls = _class(res)
    for t in techs:
        e = TECHS[t][3]
        r *= e.get(cls, 1.0)
        cap += e.get("carry", 0) + (e.get("carry_wood", 0) if res == "wood" else 0)
        v *= e.get("speed", 1.0)
    cap = int(cap * c.get("carry_mult", 1.0))
    trip = cap / r + 2 * d / v + t_turn
    return (cap + c.get("dropoff_bonus", 0)) / trip


def walk_factor(res, d, techs=()):
    """w = r (2d/v + t_turn) / C ; r_eff = r / (1 + w)."""
    r = r_eff(res, 0, techs, t_turn=0)
    return r / r_eff(res, d, techs) - 1


def sheep_group_rate(k, techs=(), civ="generic", d=0.0, t_group=T_SHEEP_GROUP):
    """k villagers on sheep delivered to the drop-off: kill animation and crowding at each sheep switch cost
    every villager t_group seconds per sheep (fit). Returns food/s for the group."""
    r = r_eff("sheep", d, techs, civ)
    t_sheep = SHEEP_FOOD / (k * r) + t_group
    return SHEEP_FOOD / t_sheep


def node_group_rate(res, k, d, amount, d_next, techs=(), civ="generic"):
    """k villagers depleting nodes of `amount` at distance d, then walking d_next tiles to the next node."""
    r = r_eff(res, d, techs, civ)
    v = SPEED * (1.15 if "wheelbarrow" in techs else 1.0)
    t_node = amount / (k * r) + d_next / v
    return amount / t_node


BUILD_FORMULA_NOTE = "T(n) = T1 * 3/(n+2): community formula, unverified against official data (see PARAMS.md)"


def build_time(base, n):
    return base * 3.0 / (n + 2)


@dataclass
class Allocation:
    """villagers per task: {res: (count, distance)}"""
    tasks: dict = field(default_factory=dict)
    techs: tuple = ()
    civ: str = "generic"

    def income(self):
        out = {}
        for res, (k, d) in self.tasks.items():
            if res == "sheep":
                out["food"] = out.get("food", 0) + sheep_group_rate(k, self.techs, self.civ, d)
            else:
                key = "food" if res in FOOD_SOFT or res in HUNT or res == "fish_shore" else res
                out[key] = out.get(key, 0) + k * r_eff(res, d, self.techs, self.civ)
        return out


if __name__ == "__main__":
    for d in (0, 1, 2, 4):
        print(d, round(r_eff("wood", d), 3), round(r_eff("wood", d, ("wheelbarrow",)), 3), round(walk_factor("wood", d), 2))
