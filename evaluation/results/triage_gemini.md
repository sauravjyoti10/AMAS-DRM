## Triage evaluation (gemini parser, online geocoding: False)
18 labelled messages; 0 parse failures.

### Severity
Accuracy **88.9%**, macro precision 88.5%, macro recall 87.5%, macro F1 86.1%.

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| CRITICAL | 87.5% | 100.0% | 93.3% | 7 |
| HIGH | 100.0% | 83.3% | 90.9% | 6 |
| MODERATE | 100.0% | 66.7% | 80.0% | 3 |
| LOW | 66.7% | 100.0% | 80.0% | 2 |

Safety view: **CRITICAL recall 100.0%** (0 of 7 critical messages ranked lower). Under-triaged (less urgent than truth): 1; over-triaged: 1.

Confusion matrix (rows = truth, columns = predicted):

| truth \ pred | CRITICAL | HIGH | MODERATE | LOW |
|---|---|---|---|---|
| CRITICAL | 7 | 0 | 0 | 0 |
| HIGH | 1 | 5 | 0 | 0 |
| MODERATE | 0 | 0 | 2 | 1 |
| LOW | 0 | 0 | 0 | 2 |

### Casualty count and requested resources
Casualties: exact match 100.0%, within +-1 100.0%, mean absolute error 0.00. Resource items: precision 68.4%, recall 100.0%, F1 81.3%.

### Location
| Outcome | Count |
|---|---|
| correct | 11 |
| correct_unresolved | 2 |
| missed | 3 |
| other_unresolved | 2 |

- Message names a gazetteer place: **correct 78.6%**, wrong pin 0.0%, missed 21.4%.
- No place named or outside Guwahati: **false-pin rate 0.0%** (target 0%).
- Coordinates in the message: exact (<50 m) 0.0%.
- Places not in the gazetteer: 0 of 2 resolved (online geocoder off, so unresolved is expected).
- Reported uncertainty when correct: median +-700 m.

### Latency per message (parse + locate): median 5033.74 ms, p95 21959.56 ms.

### Error analysis (5 messages with a severity or location error)
- #8 gold CRITICAL / predicted CRITICAL; location: missed. "Six Mile flyover side: a house caved in, 3 children trapped inside. Help immediately."
- #9 gold CRITICAL / predicted CRITICAL; location: missed. "Maligaon railway colony flooded, water above waist level, 10 families stranded. Need boats"
- #63 gold MODERATE / predicted LOW; location: correct. "Streetlights are not working on Zoo Road after the storm."
- #75 gold LOW / predicted LOW; location: missed. "Stray dogs gathering near the Beltola relief point, no one hurt."
- #100 gold HIGH / predicted CRITICAL; location: correct_unresolved. "Help! Water is entering our house and the children are scared."