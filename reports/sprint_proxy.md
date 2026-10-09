# Sprint order as a stand-in for the race grid

29 sprint weekends, walk-forward (each forecast uses only earlier races). Winner log loss, lower is better; 95% bootstrap interval in brackets.

| Forecast | Log loss | Top pick right |
|---|---|---|
| Real race grid (after qualifying) | 1.557 [1.171, 1.978] | 41% |
| Sprint starting order as grid | 1.755 [1.307, 2.250] | 41% |
| Form only, no grid | 1.789 [1.400, 2.211] | 28% |

Paired differences in log loss (negative = first is better):

* sprint grid minus form only: -0.033 [-0.289, +0.261]
* sprint grid minus real grid: +0.198 [-0.094, +0.469]
