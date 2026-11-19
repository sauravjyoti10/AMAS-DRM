## Routing safety evaluation (real OSM graph data/guwahati_roads.graphml, seed 42)
200 trials, 1-3 circular hazards (150-500 m) placed on the normal route each time.

| Metric | Result |
|---|---|
| Hazard-unaware router crossing a hazard | 100.0% (by construction) |
| **AMAS paths intersecting a hazard** | **0 of 193** (target 0) |
| Safe route found | 96.5% (193 of 200) |
| No safe route (hazards cut the network) | 7 |
| Independent check disagrees with router's own flag | 0 |
| Distance vs normal route (median / p95) | x1.08 / x1.57 |
| Travel time vs normal route (median / p95) | x1.11 / x1.99 |
| Routing time per query (median / p95) | 43 ms / 103 ms |

| Hazards on route | Trials | Safe route found | Median distance ratio |
|---|---|---|---|
| 1 | 67 | 100.0% | x1.06 |
| 2 | 69 | 97.1% | x1.06 |
| 3 | 64 | 92.2% | x1.10 |

Reading it: zero intersections means every returned path stayed out of every hazard. A trial with no route is a correct refusal, not a failure: the router will not drive through a hazard to produce an answer.