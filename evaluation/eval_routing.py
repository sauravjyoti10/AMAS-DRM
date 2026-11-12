"""Routing safety evaluation (PPT metric: zero intersections of the chosen path with any hazard polygon).

    python -m evaluation.eval_routing                       # real OSM graph (needs data/guwahati_roads.graphml)
    python -m evaluation.eval_routing --synthetic           # synthetic grid, no download needed
    python -m evaluation.eval_routing --trials 500 --seed 7

Each trial: pick a random origin/destination 1.5-8 km apart, compute the normal fastest route, then drop
1-3 circular hazards (150-500 m) ON that route, so a hazard-unaware router is guaranteed to be unsafe.
We then ask the hazard-aware router for a new route and check it INDEPENDENTLY: the path is sampled every
~10 m and every sample is tested against the polygons with a different algorithm than the router used.
"""
import argparse
import json
import math
import os
import random
import time
from typing import List, Tuple

from app.config import get_settings
from app.geo import circle_polygon, haversine_m, point_in_polygon
from app.routing import NoRouteError, OutOfCoverageError, RoadNetwork
from app.schemas import HazardZone, LatLon
from evaluation.metrics import md_table, pct, safe_div, summarize

RESULTS = os.path.join(os.path.dirname(__file__), "results")


def densify(path: List[List[float]], step_m: float = 10.0) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    for (la1, lo1), (la2, lo2) in zip(path, path[1:]):
        d = float(haversine_m(la1, lo1, la2, lo2))
        k = max(1, int(math.ceil(d / step_m)))
        pts += [(la1 + (la2 - la1) * i / k, lo1 + (lo2 - lo1) * i / k) for i in range(k)]
    if path:
        pts.append(tuple(path[-1]))
    return pts


def touches(path, polys) -> bool:
    return any(point_in_polygon(la, lo, poly) for la, lo in densify(path) for poly in polys)


def make_hazard(center: Tuple[float, float], radius: float, name: str) -> HazardZone:
    ring = circle_polygon(center[0], center[1], radius)
    return HazardZone(name=name, polygon=[LatLon(lat=a, lon=b) for a, b in ring])


def run(net: RoadNetwork, trials: int, seed: int, max_snap_m: float):
    rng = random.Random(seed)
    ids = list(net.graph.nodes)
    rec = []
    attempts = 0
    while len(rec) < trials and attempts < trials * 20:
        attempts += 1
        o, d = rng.choice(ids), rng.choice(ids)
        no, nd = net.graph.nodes[o], net.graph.nodes[d]
        dist = float(haversine_m(no["y"], no["x"], nd["y"], nd["x"]))
        if not 1500 <= dist <= 8000:
            continue
        try:
            base = net.route(no["y"], no["x"], nd["y"], nd["x"], max_snap_m=max_snap_m)
        except (NoRouteError, OutOfCoverageError):
            continue
        path = base.path_coordinates
        if len(path) < 6:
            continue

        k = rng.randint(1, 3)
        hazards = []
        for i in range(k):
            lo, hi = int(len(path) * 0.15), int(len(path) * 0.85)
            c = path[rng.randint(lo, hi)]
            hazards.append(make_hazard((c[0], c[1]), rng.uniform(150, 500), f"H{i + 1}"))
        polys = [[(p.lat, p.lon) for p in h.polygon] for h in hazards]
        # skip trials where an endpoint itself is inside a hazard (the router refuses those by design)
        if any(point_in_polygon(no["y"], no["x"], p) or point_in_polygon(nd["y"], nd["x"], p) for p in polys):
            continue

        t0 = time.perf_counter()
        try:
            res = net.route(no["y"], no["x"], nd["y"], nd["x"], hazards=hazards, max_snap_m=max_snap_m)
            ms = (time.perf_counter() - t0) * 1000
            rec.append({"k": k, "found": True, "naive_unsafe": touches(path, polys),
                        "intersects": touches(res.path_coordinates, polys), "router_says_safe": res.hazard_safe,
                        "dist_ratio": res.distance_m / base.distance_m, "time_ratio": res.travel_time_s / base.travel_time_s,
                        "blocked_edges": res.blocked_edges, "ms": ms})
        except NoRouteError:
            rec.append({"k": k, "found": False, "naive_unsafe": touches(path, polys), "ms": (time.perf_counter() - t0) * 1000})
        except OutOfCoverageError:
            continue
    return rec


def summarise(rec, graph_label: str, seed: int):
    found = [r for r in rec if r["found"]]
    by_k = {}
    for k in (1, 2, 3):
        sub = [r for r in rec if r["k"] == k]
        f = [r for r in sub if r["found"]]
        by_k[k] = {"trials": len(sub), "found_rate": safe_div(len(f), len(sub)),
                   "median_dist_ratio": summarize([r["dist_ratio"] for r in f])["median"]}
    return {
        "graph": graph_label, "seed": seed, "trials": len(rec),
        "naive_router_unsafe_rate": safe_div(sum(r["naive_unsafe"] for r in rec), len(rec)),
        "route_found": len(found), "route_found_rate": safe_div(len(found), len(rec)),
        "no_safe_route": len(rec) - len(found),
        "hazard_intersections": sum(r["intersects"] for r in found),
        "router_self_check_disagreements": sum(r["intersects"] != (not r["router_says_safe"]) for r in found),
        "dist_ratio": summarize([r["dist_ratio"] for r in found]), "time_ratio": summarize([r["time_ratio"] for r in found]),
        "route_ms": summarize([r["ms"] for r in rec]), "by_hazard_count": by_k,
    }


def to_markdown(s) -> str:
    return "\n".join([
        f"## Routing safety evaluation ({s['graph']}, seed {s['seed']})",
        f"{s['trials']} trials, 1-3 circular hazards (150-500 m) placed on the normal route each time.", "",
        md_table(["Metric", "Result"], [
            ["Hazard-unaware router crossing a hazard", pct(s["naive_router_unsafe_rate"]) + " (by construction)"],
            ["**AMAS paths intersecting a hazard**", f"**{s['hazard_intersections']} of {s['route_found']}** (target 0)"],
            ["Safe route found", f"{pct(s['route_found_rate'])} ({s['route_found']} of {s['trials']})"],
            ["No safe route (hazards cut the network)", s["no_safe_route"]],
            ["Independent check disagrees with router's own flag", s["router_self_check_disagreements"]],
            ["Distance vs normal route (median / p95)", f"x{s['dist_ratio']['median']:.2f} / x{s['dist_ratio']['p95']:.2f}"],
            ["Travel time vs normal route (median / p95)", f"x{s['time_ratio']['median']:.2f} / x{s['time_ratio']['p95']:.2f}"],
            ["Routing time per query (median / p95)", f"{s['route_ms']['median']:.0f} ms / {s['route_ms']['p95']:.0f} ms"],
        ]), "",
        md_table(["Hazards on route", "Trials", "Safe route found", "Median distance ratio"],
                 [[k, v["trials"], pct(v["found_rate"]), f"x{v['median_dist_ratio']:.2f}"] for k, v in s["by_hazard_count"].items()]), "",
        "Reading it: zero intersections means every returned path stayed out of every hazard. A trial with no route is a correct refusal, "
        "not a failure: the router will not drive through a hazard to produce an answer."])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    settings = get_settings()
    if a.synthetic:
        from evaluation.synthetic import build_grid
        net, label = build_grid(), "SYNTHETIC grid (not real roads)"
    else:
        net, label = RoadNetwork.from_graphml(settings.graph_path), f"real OSM graph {settings.graph_path}"
    rec = run(net, a.trials, a.seed, settings.max_snap_m)
    s = summarise(rec, label, a.seed)
    os.makedirs(RESULTS, exist_ok=True)
    tag = "routing_synthetic" if a.synthetic else "routing"
    with open(os.path.join(RESULTS, tag + ".json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1)
    md = to_markdown(s)
    with open(os.path.join(RESULTS, tag + ".md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)


if __name__ == "__main__":
    main()
