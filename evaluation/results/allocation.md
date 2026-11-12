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