# AMAS-DRM evaluation report
Generated 2026-11-12 12:43. **Routing and latency used a SYNTHETIC grid: these two sections only prove the code works, they are not thesis numbers.**

---

## Triage evaluation (rules parser, online geocoding: False)
117 labelled messages; 0 parse failures.

### Severity
Accuracy **69.2%**, macro precision 72.8%, macro recall 71.2%, macro F1 64.7%.

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| CRITICAL | 81.2% | 81.2% | 81.2% | 48 |
| HIGH | 76.7% | 60.5% | 67.6% | 38 |
| MODERATE | 100.0% | 42.9% | 60.0% | 21 |
| LOW | 33.3% | 100.0% | 50.0% | 10 |

Safety view: **CRITICAL recall 81.2%** (9 of 48 critical messages ranked lower). Under-triaged (less urgent than truth): 22; over-triaged: 14.

Confusion matrix (rows = truth, columns = predicted):

| truth \ pred | CRITICAL | HIGH | MODERATE | LOW |
|---|---|---|---|---|
| CRITICAL | 39 | 2 | 0 | 7 |
| HIGH | 7 | 23 | 0 | 8 |
| MODERATE | 2 | 5 | 9 | 5 |
| LOW | 0 | 0 | 0 | 10 |

### Casualty count and requested resources
Casualties: exact match 77.8%, within +-1 88.0%, mean absolute error 0.87. Resource items: precision 86.7%, recall 65.0%, F1 74.3%.

### Location
| Outcome | Count |
|---|---|
| coords_ok | 6 |
| correct | 87 |
| correct_unresolved | 11 |
| missed | 1 |
| other_unresolved | 12 |

- Message names a gazetteer place: **correct 98.9%**, wrong pin 0.0%, missed 1.1%.
- No place named or outside Guwahati: **false-pin rate 0.0%** (target 0%).
- Coordinates in the message: exact (<50 m) 100.0%.
- Places not in the gazetteer: 0 of 12 resolved (online geocoder off, so unresolved is expected).
- Reported uncertainty when correct: median +-800 m.

### Latency per message (parse + locate): median 0.10 ms, p95 0.17 ms.

### Error analysis (36 messages with a severity or location error)
- #25 gold CRITICAL / predicted LOW; location: correct. "Stuck in car near Maligaon, water entering the car, 4 inside. HELP"
- #26 gold CRITICAL / predicted HIGH; location: correct. "Rajgarh: gas leak and flooded street, 3 unconscious people on the floor."
- #33 gold HIGH / predicted LOW; location: correct. "A boy has a deep cut on his leg after falling in Khanapara market, bleeding but stable. Ne"
- #34 gold HIGH / predicted CRITICAL; location: correct. "Three people with minor injuries from a wall collapse at Chandmari, others are safe. Pleas"
- #37 gold HIGH / predicted CRITICAL; location: correct. "Five injured in a bus collision on the flooded road at Dispur, all awake and talking."
- #39 gold HIGH / predicted LOW; location: correct. "River bank erosion is damaging houses near Jalukbari, families moved to the school, need f"
- #41 gold HIGH / predicted CRITICAL; location: correct. "Boundary wall collapsed at Rajgarh school, 2 students have fractures, teachers are with th"
- #42 gold HIGH / predicted CRITICAL; location: correct. "Floodwater has cut off our lane at Six Mile, 30 families have no food or clean water."
- #44 gold HIGH / predicted LOW; location: correct. "Electric transformer exploded near Paltan Bazaar, area dark, two people got burns."
- #48 gold HIGH / predicted CRITICAL; location: correct. "Landslide near Zoo Road narrowly missed a house, cracks in the walls, family is staying ou"
- #52 gold HIGH / predicted CRITICAL; location: correct. "Wall of the drain collapsed near Rajgarh Road, water entering shops, no one hurt."
- #53 gold HIGH / predicted LOW; location: correct. "Need first aid kits at the relief camp in Khanapara, one person has a broken arm."
- #56 gold MODERATE / predicted HIGH; location: correct. "Waterlogging at Ganeshguri since morning, shops flooded, traffic completely jammed."
- #60 gold MODERATE / predicted CRITICAL; location: correct. "Landslide debris blocking the Six Mile road, vehicles cannot pass, no injuries reported."
- #62 gold MODERATE / predicted HIGH; location: correct. "Drain overflow near Paltan Bazaar, dirty water on the road."
- #63 gold MODERATE / predicted LOW; location: correct. "Streetlights are not working on Zoo Road after the storm."
- #65 gold MODERATE / predicted HIGH; location: correct. "Mobile network is down in Khanapara after the floods, people cannot call for help."
- #66 gold MODERATE / predicted LOW; location: correct. "Water supply has stopped in Maligaon for two days."
- #71 gold MODERATE / predicted HIGH; location: correct. "Waterlogging near Six Mile bus stop, buses running late."
- #83 gold HIGH / predicted CRITICAL; location: other_unresolved. "Landslide at Narengi, 2 houses damaged, no one hurt."
- #84 gold MODERATE / predicted LOW; location: other_unresolved. "Water logging at Bhangagarh since morning."
- #86 gold MODERATE / predicted HIGH; location: other_unresolved. "Hatigaon main road flooded, two-wheelers cannot pass."
- #87 gold CRITICAL / predicted LOW; location: other_unresolved. "Uzanbazar ghat: man swept away by the river, search needed."
- #88 gold CRITICAL / predicted HIGH; location: other_unresolved. "Fire at a warehouse in Garchuk, people inside, send help."
- #89 gold MODERATE / predicted LOW; location: other_unresolved. "Noonmati refinery road waterlogged."
- ... and 11 more in the JSON file.

---

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

---

## Allocation: MILP vs First-Come-First-Served (lambda = 0.01, 100 random scenarios per scarcity level, seed 42)
Scarcity = total demand / total stock. Values are means over scenarios.

| Scarcity | Metric | MILP | FCFS | MILP - FCFS | MILP >= FCFS in |
|---|---|---|---|---|---|
| 0.6 | Overall fill rate | 100.0% | 100.0% | +0.0 pts | 100.0% |
|  | Severity-weighted fill | 100.0% | 100.0% | +0.0 pts | 100.0% |
|  | CRITICAL fill rate | 100.0% | 100.0% | +0.0 pts | 100.0% |
|  | Road km per unit delivered | 7.6 | 7.9 | -0.3 | 50.0% |
| 1.0 | Overall fill rate | 99.9% | 99.9% | +0.0 pts | 100.0% |
|  | Severity-weighted fill | 100.0% | 99.9% | +0.1 pts | 100.0% |
|  | CRITICAL fill rate | 100.0% | 100.0% | +0.0 pts | 100.0% |
|  | Road km per unit delivered | 9.4 | 10.3 | -0.9 | 6.0% |
| 1.5 | Overall fill rate | 66.7% | 66.7% | +0.0 pts | 100.0% |
|  | Severity-weighted fill | 86.0% | 66.0% | +20.1 pts | 100.0% |
|  | CRITICAL fill rate | 99.9% | 68.0% | +31.9 pts | 100.0% |
|  | Road km per unit delivered | 8.8 | 10.5 | -1.7 | 19.0% |
| 2.0 | Overall fill rate | 50.0% | 50.0% | +0.0 pts | 100.0% |
|  | Severity-weighted fill | 74.0% | 50.3% | +23.7 pts | 100.0% |
|  | CRITICAL fill rate | 98.0% | 49.1% | +49.0 pts | 100.0% |
|  | Road km per unit delivered | 9.1 | 10.8 | -1.7 | 24.0% |

Reading it: with plenty of stock (0.6) both policies serve everyone and differ only in distance. When stock runs short (1.5, 2.0), FCFS hands stock to whoever arrived first, the MILP gives it to the most severe incidents. The MILP can also leave a low-severity far-away incident unserved on purpose when the transit penalty outweighs its utility, which lowers its overall fill rate: report that trade-off honestly.

---

## End-to-end latency (SYNTHETIC grid, offline geocoding)
86 cycles measured (14 skipped: location unresolved, a human pins those), 2 active hazards. Times in ms; human approval time is excluded.

| Stage | Median | Mean | p95 | Max |
|---|---|---|---|---|
| Triage + locate | 0.3 | 0.3 | 0.4 | 2.2 |
| Allocation (MILP) | 18.0 | 27.1 | 88.7 | 174.7 |
| Routing | 5.9 | 14.1 | 76.7 | 87.6 |
| **Total** | 24.5 | 41.6 | 166.3 | 196.2 |
