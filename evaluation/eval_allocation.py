"""Allocation efficiency: the MILP of app/allocation.py against a First-Come-First-Served baseline.

    python -m evaluation.eval_allocation --scenarios 100 --seed 42

FCFS baseline: incidents are served in arrival order; each takes stock from the nearest depot that still
has some, then the next nearest, until its demand is met or all stock is gone. (This is how a manual
dispatch desk with a queue behaves.)

Scenarios vary scarcity = total demand / total depot stock (0.6 = plenty, 2.0 = half of what is needed),
because priority only matters when stock runs short.
"""
import argparse
import json
import math
import os
import random
from typing import Dict, List, Tuple

from app.allocation import PIPELINE_TRANSIT_PENALTY, Depot, IncidentDemand, optimize_allocation
from app.geo import haversine_m
from evaluation.metrics import md_table, pct, safe_div, summarize

RESULTS = os.path.join(os.path.dirname(__file__), "results")
WEIGHTS = {"LOW": 1.0, "MODERATE": 2.5, "HIGH": 5.0, "CRITICAL": 10.0}   # same as app/graph.py
SEV_PROBS = [("LOW", 0.2), ("MODERATE", 0.25), ("HIGH", 0.3), ("CRITICAL", 0.25)]
BBOX = (26.09, 91.62, 26.20, 91.86)  # south, west, north, east: the downloaded map area


def make_scenario(rng: random.Random, scarcity: float):
    depots = [Depot(id=f"D{i}", capacity=rng.randint(30, 80), lat=rng.uniform(BBOX[0], BBOX[2]),
                    lon=rng.uniform(BBOX[1], BBOX[3])) for i in range(rng.randint(2, 4))]
    stock = sum(d.capacity for d in depots)
    n = rng.randint(4, 10)
    raw = [rng.randint(5, 40) for _ in range(n)]
    scale = scarcity * stock / sum(raw)
    incs = []
    for i, r in enumerate(raw):
        sev = rng.choices([s for s, _ in SEV_PROBS], [p for _, p in SEV_PROBS])[0]
        incs.append((sev, IncidentDemand(id=f"I{i}", severity_score=WEIGHTS[sev], demand=max(1, round(r * scale)),
                                         lat=rng.uniform(BBOX[0], BBOX[2]), lon=rng.uniform(BBOX[1], BBOX[3]))))
    dist = {(inc.id, d.id): float(haversine_m(inc.lat, inc.lon, d.lat, d.lon)) * 1.3 / 1000.0 for _, inc in incs for d in depots}
    return depots, incs, dist


def fcfs(depots: List[Depot], incs, dist) -> Dict[str, Dict[str, int]]:
    left = {d.id: d.capacity for d in depots}
    plan: Dict[str, Dict[str, int]] = {}
    for _, inc in incs:                                   # arrival order
        need, plan[inc.id] = inc.demand, {}
        for d in sorted(depots, key=lambda d: dist[(inc.id, d.id)]):
            give = min(need, left[d.id])
            if give > 0:
                plan[inc.id][d.id] = give
                left[d.id] -= give
                need -= give
            if need == 0:
                break
    return plan


def score(plan, depots, incs, dist) -> Dict[str, float]:
    got = {inc.id: sum(plan.get(inc.id, {}).values()) for _, inc in incs}
    demand = sum(i.demand for _, i in incs)
    served = sum(got.values())
    w_num = sum(WEIGHTS[s] * got[i.id] for s, i in incs)
    w_den = sum(WEIGHTS[s] * i.demand for s, i in incs)
    crit = [(s, i) for s, i in incs if s == "CRITICAL"]
    c_den = sum(i.demand for _, i in crit)
    km_units = sum(q * dist[(iid, did)] for iid, row in plan.items() for did, q in row.items())
    return {
        "fill_rate": safe_div(served, demand),
        "weighted_fill": safe_div(w_num, w_den),
        "critical_fill": safe_div(sum(got[i.id] for _, i in crit), c_den) if c_den else float("nan"),
        "km_per_unit": safe_div(km_units, served),
        "stock_used": safe_div(served, sum(d.capacity for d in depots)),
    }


def run(scenarios: int, seed: int, lam: float):
    rng = random.Random(seed)
    out = {}
    for scarcity in (0.6, 1.0, 1.5, 2.0):
        rows = []
        for _ in range(scenarios):
            depots, incs, dist = make_scenario(rng, scarcity)
            milp = optimize_allocation([i for _, i in incs], depots, dist, lambda_penalty=lam)
            rows.append({"milp": score(milp, depots, incs, dist), "fcfs": score(fcfs(depots, incs, dist), depots, incs, dist)})
        out[scarcity] = rows
    return out


def mean(vals):
    vals = [v for v in vals if not math.isnan(v)]
    return sum(vals) / len(vals) if vals else float("nan")


def summarise(res, lam, scenarios, seed):
    table = {}
    for sc, rows in res.items():
        t = {}
        for metric in ("fill_rate", "weighted_fill", "critical_fill", "km_per_unit"):
            m = [r["milp"][metric] for r in rows]
            f = [r["fcfs"][metric] for r in rows]
            diff = [a - b for a, b in zip(m, f) if not (math.isnan(a) or math.isnan(b))]
            t[metric] = {"milp": mean(m), "fcfs": mean(f), "mean_diff": mean(diff),
                         "milp_not_worse": safe_div(sum(d >= -1e-9 for d in diff), len(diff))}
        table[str(sc)] = t
    return {"lambda": lam, "scenarios_per_level": scenarios, "seed": seed, "table": table}


def to_markdown(s) -> str:
    lines = [f"## Allocation: MILP vs First-Come-First-Served (lambda = {s['lambda']}, {s['scenarios_per_level']} random scenarios per scarcity level, seed {s['seed']})",
             "Scarcity = total demand / total stock. Values are means over scenarios.", ""]
    rows = []
    names = {"fill_rate": "Overall fill rate", "weighted_fill": "Severity-weighted fill", "critical_fill": "CRITICAL fill rate", "km_per_unit": "Road km per unit delivered"}
    for sc, t in s["table"].items():
        for metric, label in names.items():
            v = t[metric]
            fmt = (lambda x: f"{x:.1f}") if metric == "km_per_unit" else pct
            rows.append([sc if metric == "fill_rate" else "", label, fmt(v["milp"]), fmt(v["fcfs"]),
                         (f"{v['mean_diff']:+.1f}" if metric == "km_per_unit" else f"{100 * v['mean_diff']:+.1f} pts"),
                         pct(v["milp_not_worse"])])
    lines.append(md_table(["Scarcity", "Metric", "MILP", "FCFS", "MILP - FCFS", "MILP >= FCFS in"], rows))
    lines += ["", "Reading it: with plenty of stock (0.6) both policies serve everyone and differ only in distance. When stock runs short (1.5, 2.0), "
              "FCFS hands stock to whoever arrived first, the MILP gives it to the most severe incidents. The MILP can also leave a low-severity far-away "
              "incident unserved on purpose when the transit penalty outweighs its utility, which lowers its overall fill rate: report that trade-off honestly."]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--lam", type=float, default=PIPELINE_TRANSIT_PENALTY, help="transit penalty (pipeline value in app/allocation.py)")
    a = ap.parse_args()
    s = summarise(run(a.scenarios, a.seed, a.lam), a.lam, a.scenarios, a.seed)
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "allocation.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1)
    md = to_markdown(s)
    with open(os.path.join(RESULTS, "allocation.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)


if __name__ == "__main__":
    main()
