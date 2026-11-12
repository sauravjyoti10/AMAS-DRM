"""Run every evaluation and combine the results into evaluation/results/report.md

    python -m evaluation.run_all                 # real OSM graph (after python -m scripts.download_map)
    python -m evaluation.run_all --synthetic     # no map download needed (pipeline check only, NOT thesis numbers)
    python -m evaluation.run_all --online        # also use OpenStreetMap geocoding in the triage and latency runs
    python -m evaluation.run_all --gemini        # also run the triage evaluation with Gemini
"""
import argparse
import datetime
import os
import subprocess
import sys

RESULTS = os.path.join(os.path.dirname(__file__), "results")


def run(*args: str) -> None:
    print("\n>>>", "python -m", " ".join(args), flush=True)
    subprocess.run([sys.executable, "-m", *args], check=True)


def read(name: str) -> str:
    with open(os.path.join(RESULTS, name), encoding="utf-8") as f:
        return f.read()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--gemini", action="store_true")
    a = ap.parse_args()
    syn = ["--synthetic"] if a.synthetic else []
    on = ["--online"] if a.online else []

    run("evaluation.eval_triage", *on)
    if a.gemini:
        run("evaluation.eval_triage", "--mode", "gemini", *on)
    run("evaluation.eval_routing", *syn)
    run("evaluation.eval_allocation")
    run("evaluation.eval_latency", *syn, *on)

    t = "triage_rules" + ("_online" if a.online else "")
    r = "routing_synthetic" if a.synthetic else "routing"
    l = "latency_synthetic" if a.synthetic else "latency"
    parts = [f"# AMAS-DRM evaluation report\nGenerated {datetime.datetime.now():%Y-%m-%d %H:%M}. "
             + ("**Routing and latency used a SYNTHETIC grid: these two sections only prove the code works, they are not thesis numbers.**" if a.synthetic
                else "Routing and latency used the real OSM road graph.")]
    parts += [read(t + ".md")]
    if a.gemini:
        parts.append(read("triage_gemini" + ("_online" if a.online else "") + ".md"))
    parts += [read(r + ".md"), read("allocation.md"), read(l + ".md")]
    with open(os.path.join(RESULTS, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(parts) + "\n")
    print("\nWrote evaluation/results/report.md")


if __name__ == "__main__":
    main()
