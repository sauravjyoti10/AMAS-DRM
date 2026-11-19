## End-to-end latency (real OSM graph, offline geocoding)
81 cycles measured (19 skipped: location unresolved, a human pins those), 2 active hazards. Times in ms; human approval time is excluded.

| Stage | Median | Mean | p95 | Max |
|---|---|---|---|---|
| Triage + locate | 1307.4 | 1817.3 | 4418.1 | 5296.3 |
| Allocation (MILP) | 118.1 | 137.2 | 237.5 | 529.3 |
| Routing | 16.4 | 35.3 | 169.4 | 201.3 |
| **Total** | 1496.7 | 1989.8 | 4527.8 | 5647.6 |