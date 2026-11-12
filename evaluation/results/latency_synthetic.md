## End-to-end latency (SYNTHETIC grid, offline geocoding)
86 cycles measured (14 skipped: location unresolved, a human pins those), 2 active hazards. Times in ms; human approval time is excluded.

| Stage | Median | Mean | p95 | Max |
|---|---|---|---|---|
| Triage + locate | 0.3 | 0.3 | 0.4 | 2.2 |
| Allocation (MILP) | 18.0 | 27.1 | 88.7 | 174.7 |
| Routing | 5.9 | 14.1 | 76.7 | 87.6 |
| **Total** | 24.5 | 41.6 | 166.3 | 196.2 |