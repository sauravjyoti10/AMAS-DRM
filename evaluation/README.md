# Evaluation (proposal slide 8)

| Proposal metric | Script | What it measures |
|---|---|---|
| Triage accuracy (precision / recall on 100+ samples) | `eval_triage.py` | severity P/R/F1 and confusion matrix, CRITICAL recall, casualty error, requested resources, location correctness and false-pin rate |
| Routing safety (zero hazard intersections) | `eval_routing.py` | random hazards placed on the normal route; every returned path is re-checked independently |
| Allocation efficiency (MILP vs FCFS) | `eval_allocation.py` | fill rate, severity-weighted fill, CRITICAL fill, road km per unit, across scarcity levels |
| System latency | `eval_latency.py` | triage / allocation / routing / total per distress cycle |

## Run it
```bash
python -m evaluation.run_all                 # real OSM graph (run python -m scripts.download_map first)
python -m evaluation.run_all --online        # also let the triage/latency runs use OpenStreetMap geocoding
python -m evaluation.run_all --gemini        # also evaluate Gemini triage (needs GEMINI_API_KEY)
python -m evaluation.run_all --synthetic     # smoke test without the map; NOT thesis numbers
```
Results land in `evaluation/results/` (`report.md` is the combined report, `*.json` has every number and per-message detail).
All random choices use a fixed `--seed`, so runs are reproducible.

## Before you quote any number in the thesis
1. **The SOS dataset is author-written** (`dataset.py`), not collected from real victims. Add 30-50 real or public-dataset messages (for example a Kaggle disaster-tweet set) and have a **second person label all messages independently**; report Cohen's kappa for the severity labels.
2. **"Named-place accuracy" is not position accuracy.** The expected position for a named locality is the gazetteer's own point, so the metric checks that the right place was extracted and matched. For real error in metres, look up true positions on OpenStreetMap and fill `GOLD_COORDS` in `dataset.py`.
3. **The rule-based parser was written by the same person (and assistant) who wrote the dataset.** Its scores are optimistic. Report the Gemini run (`--mode gemini`) as the main triage result and the rule parser as the offline baseline.
4. **Routing and latency must be run on the real graph**, not `--synthetic`. A regular grid has many equally short alternatives, so detours look unrealistically small.
5. Hazards in the routing test are circles placed on the route. Add a run with real flood-prone areas (for example low-lying Bharalu basin streets) for realism.
6. Keep the severity rubric in `dataset.py` in the thesis appendix.
