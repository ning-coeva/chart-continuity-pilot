### Constraint retention at the probe turn

| Model | Type | Constraint kept at probe | Probe task done (det.) | Probe reply parsed as a spec | Conversations with an API error |
|---|---|---|---|---|---|
| Gemini 3.1 Pro Preview | frontier proprietary | 0.95 (38/40) | 1.00 (28/28) | 1.00 (40/40) | 0 |
| GPT-5-mini | smaller proprietary | 0.88 (35/40) | 0.93 (26/28) | 0.97 (39/40) | 0 |
| Llama 4 Maverick | open weights | 0.62 (25/40) | 0.96 (27/28) | 1.00 (40/40) | 0 |

### By constraint type

| Model | Encoding (colour-blind-safe palette) | Filter (exclude 2020) | Expression (y axis from zero) |
|---|---|---|---|
| Gemini 3.1 Pro Preview | 0.86 (12/14) | 1.00 (14/14) | 1.00 (12/12) |
| GPT-5-mini | 0.86 (12/14) | 0.86 (12/14) | 0.92 (11/12) |
| Llama 4 Maverick | 0.43 (6/14) | 0.57 (8/14) | 0.92 (11/12) |

### By stressor type

| Model | Goal Interruption | Domain Switch | Stance Erosion |
|---|---|---|---|
| Gemini 3.1 Pro Preview | 1.00 (14/14) | 0.92 (11/12) | 0.93 (13/14) |
| GPT-5-mini | 1.00 (14/14) | 0.83 (10/12) | 0.79 (11/14) |
| Llama 4 Maverick | 0.79 (11/14) | 0.67 (8/12) | 0.43 (6/14) |

### Constraint x stressor, pooled over the three models

| Constraint \ stressor | Goal Interruption | Domain Switch | Stance Erosion |
|---|---|---|---|
| Encoding (colour-blind-safe palette) | 0.92 (11/12) | 0.58 (7/12) | 0.67 (12/18) |
| Filter (exclude 2020) | 0.89 (16/18) | 0.83 (10/12) | 0.67 (8/12) |
| Expression (y axis from zero) | 1.00 (12/12) | 1.00 (12/12) | 0.83 (10/12) |

### Run-to-run consistency

| Model | Dialogues with identical verdict on both runs | Rate |
|---|---|---|
| Gemini 3.1 Pro Preview | 18/20 | 0.90 |
| GPT-5-mini | 15/20 | 0.75 |
| Llama 4 Maverick | 15/20 | 0.75 |

### Deterministic checklist vs. independent judge

| Model | Checklist and judge agree | Checklist pass, judge fail | Judge pass, checklist fail |
|---|---|---|---|
| Gemini 3.1 Pro Preview | 0.95 (38/40) | 0 | 2 |
| GPT-5-mini | 0.93 (37/40) | 0 | 3 |
| Llama 4 Maverick | 0.93 (37/40) | 1 | 2 |
