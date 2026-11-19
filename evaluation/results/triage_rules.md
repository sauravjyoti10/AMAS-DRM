## Triage evaluation (rules parser, online geocoding: False)
117 labelled messages; 0 parse failures.

### Severity
Accuracy **98.3%**, macro precision 98.1%, macro recall 98.8%, macro F1 98.4%.

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| CRITICAL | 100.0% | 98.0% | 99.0% | 51 |
| HIGH | 97.2% | 97.2% | 97.2% | 36 |
| MODERATE | 95.2% | 100.0% | 97.6% | 20 |
| LOW | 100.0% | 100.0% | 100.0% | 10 |

Safety view: **CRITICAL recall 98.0%** (1 of 51 critical messages ranked lower). Under-triaged (less urgent than truth): 2; over-triaged: 0.

Confusion matrix (rows = truth, columns = predicted):

| truth \ pred | CRITICAL | HIGH | MODERATE | LOW |
|---|---|---|---|---|
| CRITICAL | 50 | 1 | 0 | 0 |
| HIGH | 0 | 35 | 1 | 0 |
| MODERATE | 0 | 0 | 20 | 0 |
| LOW | 0 | 0 | 0 | 10 |

### Casualty count and requested resources
Casualties: exact match 80.3%, within +-1 91.5%, mean absolute error 0.79. Resource items: precision 86.7%, recall 65.0%, F1 74.3%.

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

### Latency per message (parse + locate): median 0.30 ms, p95 0.86 ms.

### Error analysis (3 messages with a severity or location error)
- #56 gold HIGH / predicted MODERATE; location: correct. "Waterlogging at Ganeshguri since morning, shops flooded, traffic completely jammed."
- #103 gold CRITICAL / predicted HIGH; location: correct_unresolved. "Flood flood flood please help"
- #110 gold CRITICAL / predicted CRITICAL; location: missed. "pls help khanapra me pani aa gaya 10 log fase hai"