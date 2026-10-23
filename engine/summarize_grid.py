import csv, sys
rows = list(csv.DictReader(open('results_wings_grid.csv')))
def mm(s): s = int(float(s)); return f"{s//60}:{s%60:02d}"
def best(pred): return min((x for x in rows if pred(x)), key=lambda x: int(x['done']))
def line(r): return f"{r['feudal']:8} {r['castle']:8} {r['imperial']:8} vil {r['vil']} eco {r['eco']:7} cp{r.get('cp_farms','-')} bs{r.get('bs','-')} DONE {mm(r['done'])} techs {mm(r['techs'])} pop200 {mm(r['pop200'])} | feudal {mm(r['age2'])} tc3 {mm(r['tc3'])} castle {mm(r['age3'])} imp {mm(r['age4'])} | GA {mm(r['g1'])}/{mm(r['g2'])}/{mm(r['g3'])} | spent {r['spent']}"
print("== top 8 overall:")
for r in rows[:8]: print("  " + line(r))
for cp in ("0.0", "3.0"):
    print(f"== City Planning farms adjacency {cp}: best per feudal wing")
    for f in ("economic", "culture", "admin", "military"):
        try: print("  " + line(best(lambda x: x['feudal'] == f and x.get('cp_farms', '0.0') in (cp, '0.0') and (x['feudal'] != 'admin' and x['castle'] != 'admin' and x['imperial'] != 'admin' or x['cp_farms'] == cp))))
        except ValueError: pass
print("== castle wing with economic feudal (cp 0 unless admin):")
for c in ("culture", "admin", "military"):
    for cp in ("0.0", "3.0"):
        try: print(f"  cp{cp} " + line(best(lambda x: x['feudal'] == 'economic' and x['castle'] == c and x['cp_farms'] == cp)))
        except ValueError: pass
print("== eco timing (economic/culture/admin, 120, cp0):")
for eco in ("asap", "late", "minimal"):
    for r in rows:
        if r['eco'] == eco and (r['feudal'], r['castle'], r['imperial']) == ('economic', 'culture', 'admin') and r['vil'] == '120' and r['cp_farms'] == '0.0': print("  " + line(r))
print("== villagers (best per):")
for v in ("120", "140"): print("  " + line(best(lambda x: x['vil'] == v)))
print("== spread: fastest", mm(rows[0]['done']), "slowest", mm(rows[-1]['done']), "median", mm(rows[len(rows)//2]['done']), "runs", len(rows))
