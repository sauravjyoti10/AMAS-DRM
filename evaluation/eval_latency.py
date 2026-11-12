"""End-to-end latency of one distress cycle: triage -> allocation -> routing (human approval time excluded).

    python -m evaluation.eval_latency --synthetic                # synthetic grid, offline
    python -m evaluation.eval_latency                            # real OSM graph
    python -m evaluation.eval_latency --online                   # include OpenStreetMap geocoding
With GEMINI_API_KEY set, the triage stage uses Gemini, so its network time is included automatically.
"""
import argparse
import json
import os
import random
import sys
import time
from unittest.mock import patch

if "--online" not in sys.argv:
    os.environ["GEOCODE_ONLINE"] = "false"          # must be set before app.config is first used

from app.config import get_settings  # noqa: E402
from app import graph as g  # noqa: E402
from app.hazards import HazardStore  # noqa: E402
from app.routing import RoadNetwork  # noqa: E402
from app.schemas import HazardCreate  # noqa: E402
from evaluation.dataset import load  # noqa: E402
from evaluation.metrics import md_table, summarize  # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "results")


def run(net, runs: int, n_hazards: int, seed: int):
    rng = random.Random(seed)
    store = HazardStore()
    s = get_settings()
    for i in range(n_hazards):
        store.add(HazardCreate(name=f"H{i}", center={"lat": rng.uniform(s.bbox_south + 0.05, s.bbox_north - 0.1),
                                                     "lon": rng.uniform(s.bbox_west + 0.1, s.bbox_east - 0.1)}, radius_m=300))
    texts = [m.text for m in load()]
    t_tri, t_alloc, t_route, t_total, skipped = [], [], [], [], 0
    with patch("app.graph.get_hazard_store", return_value=store):
        for i in range(runs):
            state = {"raw_sos": texts[i % len(texts)], "status": "pending", "warnings": []}
            t0 = time.perf_counter()
            state.update(g.triage_node(state))
            t1 = time.perf_counter()
            inc = state.get("incident") or {}
            if inc.get("latitude") is None:
                skipped += 1
                continue
            state.update(g.allocation_node(state))
            t2 = time.perf_counter()
            state.update(g.routing_node(state))
            t3 = time.perf_counter()
            t_tri.append((t1 - t0) * 1000)
            t_alloc.append((t2 - t1) * 1000)
            t_route.append((t3 - t2) * 1000)
            t_total.append((t3 - t0) * 1000)
    return {"runs": runs, "completed": len(t_total), "skipped_unresolved_location": skipped, "hazards": n_hazards,
            "triage_ms": summarize(t_tri), "allocation_ms": summarize(t_alloc), "routing_ms": summarize(t_route), "total_ms": summarize(t_total)}


def to_markdown(r, label) -> str:
    rows = [[n, f"{r[k]['median']:.1f}", f"{r[k]['mean']:.1f}", f"{r[k]['p95']:.1f}", f"{r[k]['max']:.1f}"]
            for n, k in (("Triage + locate", "triage_ms"), ("Allocation (MILP)", "allocation_ms"), ("Routing", "routing_ms"), ("**Total**", "total_ms"))]
    return "\n".join([f"## End-to-end latency ({label})",
                      f"{r['completed']} cycles measured ({r['skipped_unresolved_location']} skipped: location unresolved, a human pins those), {r['hazards']} active hazards. Times in ms; human approval time is excluded.", "",
                      md_table(["Stage", "Median", "Mean", "p95", "Max"], rows)])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--hazards", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    settings = get_settings()
    if a.synthetic:
        from evaluation.synthetic import build_grid
        net, label = build_grid(), "SYNTHETIC grid, offline geocoding"
        with patch("app.graph.RoadNetwork.from_graphml", return_value=net):
            r = run(net, a.runs, a.hazards, a.seed)
    else:
        net = RoadNetwork.from_graphml(settings.graph_path)
        label = f"real OSM graph, {'online' if a.online else 'offline'} geocoding"
        r = run(net, a.runs, a.hazards, a.seed)
    os.makedirs(RESULTS, exist_ok=True)
    tag = "latency_synthetic" if a.synthetic else "latency"
    with open(os.path.join(RESULTS, tag + ".json"), "w", encoding="utf-8") as f:
        json.dump(r, f, indent=1)
    md = to_markdown(r, label)
    with open(os.path.join(RESULTS, tag + ".md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)


if __name__ == "__main__":
    main()
