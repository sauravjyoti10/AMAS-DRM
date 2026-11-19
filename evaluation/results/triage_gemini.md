## Triage evaluation (gemini parser, online geocoding: False)
18 labelled messages; 0 parse failures.

### Severity
Accuracy **83.3%**, macro precision 76.0%, macro recall 80.4%, macro F1 76.7%.

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| CRITICAL | 87.5% | 100.0% | 93.3% | 7 |
| HIGH | 100.0% | 71.4% | 83.3% | 7 |
| MODERATE | 50.0% | 50.0% | 50.0% | 2 |
| LOW | 66.7% | 100.0% | 80.0% | 2 |

Safety view: **CRITICAL recall 100.0%** (0 of 7 critical messages ranked lower). Under-triaged (less urgent than truth): 2; over-triaged: 1.

Confusion matrix (rows = truth, columns = predicted):

| truth \ pred | CRITICAL | HIGH | MODERATE | LOW |
|---|---|---|---|---|
| CRITICAL | 7 | 0 | 0 | 0 |
| HIGH | 1 | 5 | 1 | 0 |
| MODERATE | 0 | 0 | 1 | 1 |
| LOW | 0 | 0 | 0 | 2 |

### Casualty count and requested resources
Casualties: exact match 100.0%, within +-1 100.0%, mean absolute error 0.00. Resource items: precision 68.4%, recall 100.0%, F1 81.3%.

### Location
| Outcome | Count |
|---|---|
| correct | 14 |
| correct_unresolved | 2 |
| other_unresolved | 2 |

- Message names a gazetteer place: **correct 100.0%**, wrong pin 0.0%, missed 0.0%.
- No place named or outside Guwahati: **false-pin rate 0.0%** (target 0%).
- Coordinates in the message: exact (<50 m) 0.0%.
- Places not in the gazetteer: 0 of 2 resolved (online geocoder off, so unresolved is expected).
- Reported uncertainty when correct: median +-800 m.

### Latency per message (parse + locate): median 0.20 ms, p95 0.88 ms.

### Error analysis (3 messages with a severity or location error)
- #56 gold HIGH / predicted MODERATE; location: correct. "Waterlogging at Ganeshguri since morning, shops flooded, traffic completely jammed."
- #63 gold MODERATE / predicted LOW; location: correct. "Streetlights are not working on Zoo Road after the storm."
- #100 gold HIGH / predicted CRITICAL; location: correct_unresolved. "Help! Water is entering our house and the children are scared."