## Triage evaluation (rules parser, online geocoding: False)
117 labelled messages; 0 parse failures.

### Severity
Accuracy **65.8%**, macro precision 67.5%, macro recall 68.0%, macro F1 61.1%.

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| CRITICAL | 81.2% | 76.5% | 78.8% | 51 |
| HIGH | 66.7% | 55.6% | 60.6% | 36 |
| MODERATE | 88.9% | 40.0% | 55.2% | 20 |
| LOW | 33.3% | 100.0% | 50.0% | 10 |

Safety view: **CRITICAL recall 76.5%** (12 of 51 critical messages ranked lower). Under-triaged (less urgent than truth): 26; over-triaged: 14.

Confusion matrix (rows = truth, columns = predicted):

| truth \ pred | CRITICAL | HIGH | MODERATE | LOW |
|---|---|---|---|---|
| CRITICAL | 39 | 5 | 0 | 7 |
| HIGH | 7 | 20 | 1 | 8 |
| MODERATE | 2 | 5 | 8 | 5 |
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

### Latency per message (parse + locate): median 0.12 ms, p95 0.20 ms.

### Error analysis (40 messages with a severity or location error)
- #25 gold CRITICAL / predicted LOW; location: correct. "Stuck in car near Maligaon, water entering the car, 4 inside. HELP"
- #26 gold CRITICAL / predicted HIGH; location: correct. "Rajgarh: gas leak and flooded street, 3 unconscious people on the floor."
- #33 gold HIGH / predicted LOW; location: correct. "A boy has a deep cut on his leg after falling in Khanapara market, bleeding but stable. Ne"
- #34 gold HIGH / predicted CRITICAL; location: correct. "Three people with minor injuries from a wall collapse at Chandmari, others are safe. Pleas"
- #37 gold HIGH / predicted CRITICAL; location: correct. "Five injured in a bus collision on the flooded road at Dispur, all awake and talking."
- #38 gold CRITICAL / predicted HIGH; location: correct. "Elderly man with diabetes needs insulin, cannot leave the house because of flood near Zoo "
- #39 gold HIGH / predicted LOW; location: correct. "River bank erosion is damaging houses near Jalukbari, families moved to the school, need f"
- #41 gold HIGH / predicted CRITICAL; location: correct. "Boundary wall collapsed at Rajgarh school, 2 students have fractures, teachers are with th"
- #42 gold HIGH / predicted CRITICAL; location: correct. "Floodwater has cut off our lane at Six Mile, 30 families have no food or clean water."
- #43 gold CRITICAL / predicted HIGH; location: correct. "Pregnant woman in labour at Ganeshguri, ambulance stuck in the flood, we need help reachin"
- #44 gold HIGH / predicted LOW; location: correct. "Electric transformer exploded near Paltan Bazaar, area dark, two people got burns."
- #48 gold HIGH / predicted CRITICAL; location: correct. "Landslide near Zoo Road narrowly missed a house, cracks in the walls, family is staying ou"
- #49 gold MODERATE / predicted HIGH; location: correct. "Flooded street in Dispur, two children have fever and cough, need medicine."
- #52 gold HIGH / predicted CRITICAL; location: correct. "Wall of the drain collapsed near Rajgarh Road, water entering shops, no one hurt."
- #53 gold HIGH / predicted LOW; location: correct. "Need first aid kits at the relief camp in Khanapara, one person has a broken arm."
- #58 gold HIGH / predicted MODERATE; location: correct. "Electricity pole fell across the road at Chandmari, wires are live, people avoiding the ar"
- #60 gold MODERATE / predicted CRITICAL; location: correct. "Landslide debris blocking the Six Mile road, vehicles cannot pass, no injuries reported."
- #62 gold MODERATE / predicted HIGH; location: correct. "Drain overflow near Paltan Bazaar, dirty water on the road."
- #63 gold MODERATE / predicted LOW; location: correct. "Streetlights are not working on Zoo Road after the storm."
- #65 gold MODERATE / predicted HIGH; location: correct. "Mobile network is down in Khanapara after the floods, people cannot call for help."
- #66 gold MODERATE / predicted LOW; location: correct. "Water supply has stopped in Maligaon for two days."
- #71 gold MODERATE / predicted HIGH; location: correct. "Waterlogging near Six Mile bus stop, buses running late."
- #83 gold HIGH / predicted CRITICAL; location: other_unresolved. "Landslide at Narengi, 2 houses damaged, no one hurt."
- #84 gold MODERATE / predicted LOW; location: other_unresolved. "Water logging at Bhangagarh since morning."
- #86 gold MODERATE / predicted HIGH; location: other_unresolved. "Hatigaon main road flooded, two-wheelers cannot pass."
- ... and 15 more in the JSON file.