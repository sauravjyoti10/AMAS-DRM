## Routing safety evaluation (SYNTHETIC grid (not real roads), seed 42)
200 trials, 1-3 circular hazards (150-500 m) placed on the normal route each time.

| Metric | Result |
|---|---|
| Hazard-unaware router crossing a hazard | 100.0% (by construction) |
| **AMAS paths intersecting a hazard** | **0 of 200** (target 0) |
| Safe route found | 100.0% (200 of 200) |
| No safe route (hazards cut the network) | 0 |
| Independent check disagrees with router's own flag | 0 |
| Distance vs normal route (median / p95) | x1.00 / x1.13 |
| Travel time vs normal route (median / p95) | x1.02 / x1.15 |
| Routing time per query (median / p95) | 13 ms / 23 ms |

| Hazards on route | Trials | Safe route found | Median distance ratio |
|---|---|---|---|
| 1 | 61 | 100.0% | x1.00 |
| 2 | 68 | 100.0% | x1.00 |
| 3 | 71 | 100.0% | x1.00 |

Reading it: zero intersections means every returned path stayed out of every hazard. A trial with no route is a correct refusal, not a failure: the router will not drive through a hazard to produce an answer.