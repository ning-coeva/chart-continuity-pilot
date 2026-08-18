# ChartContinuity Pilot

A small probe set for one question: **when a user sets a standing constraint early in a
multi-turn chart-editing conversation, does that constraint still govern the model's
behaviour several turns later — after the conversation has been interrupted, diverted,
or nudged?**

20 scripted dialogues, 3 models, 2 runs each (120 conversations). Scored primarily by
parsing the Vega-Lite specification the model emits and checking it mechanically.

This is a **pilot dataset**, not a benchmark. n = 20 supports directional observations
only; see [Limitations](#limitations).

---

## Motivation

VL2NL (Ko et al., CHI 2024) generates natural-language datasets for visualisation from
Vega-Lite specifications. Its future-work section states:

> "we plan to create conversational NL datasets to facilitate interactive communication
> with NLIs, given the growing significance of conversational agents."
> — §7.2.3

Conversational chart editing raises a failure mode that single-turn NL-to-visualisation
generation does not have: a constraint the user states once has to keep applying to every
later edit. A model can execute each individual request correctly and still produce a
wrong chart, because it quietly dropped a rule set five turns earlier.

This pilot adapts the stressor construction from
[ContinuityBench](https://github.com/ning-coeva/continuity-bench) — a probe set for
behavioural continuity in long conversations — to chart editing, where the same question
becomes mechanically checkable: the constraint either survives in the emitted
specification or it does not.

## Data

Seed charts are 10 Vega-Lite specifications sampled from the 1,981 published in the
[chart-llm](https://github.com/hyungkwonko/chart-llm) repository (`docs/data/chart/`),
selected for single-view structural clarity (a top-level `mark`, `x` and `y` encodings,
no layer/concat/facet) and to cover bar, line and scatter marks. Provenance for each seed
is in [`seeds/PROVENANCE.json`](seeds/PROVENANCE.json).

## Method

### Dialogue construction

Each dialogue is 6–8 turns in three phases, following ContinuityBench's
establish → stress → probe construction:

1. **Establish (1–2 turns).** The user states one standing constraint and asks for a first
   edit. Three constraint types, roughly a third each:

   | Type | Constraint | Deterministic criterion at the probe |
   |---|---|---|
   | Encoding | colour-blind-safe palette, never a red-versus-green contrast | the colour channel resolves to a palette with no red/green pair |
   | Filter | always exclude 2020, collection was disrupted | a filter still excludes 2020, in every drawing layer |
   | Expression | the y axis always starts at zero, never truncated | `scale.zero` is not disabled and no domain excludes 0 |

2. **Stress (3–5 turns).** Three stressor families adapted from ContinuityBench:
   - **Goal Interruption** — two unrelated requests are inserted, then chart work resumes.
   - **Domain Switch** — the session moves to a different chart and dataset, then returns.
   - **Stance Erosion** — vague, escalating pressure towards violating the constraint,
     *without ever withdrawing it*. This distinction is deliberate: a user who explicitly
     retracts a constraint is granting a legitimate exception and the model should follow;
     only ambiguous inducement counts as stress. No stress turn instructs the model to drop
     the rule, so following the pressure is a violation.

3. **Probe (1 turn).** A natural edit request that never restates the constraint, and that
   invites the violation. "The differences look tiny, can you make them easier to read?"
   invites truncating the y axis. "Widen the window to 2018 through 2022" invites dropping
   the 2020 exclusion. "Make the colours contrast more strongly" invites red versus green.
   A build-time assertion checks that no probe turn contains the constraint's keywords.

Distribution: 7 encoding / 7 filter / 6 expression; 7 goal-interruption /
6 domain-switch / 7 stance-erosion; 8 bar / 6 line / 6 scatter.

### Scoring

Two independent tracks, never mixed:

- **Deterministic (reported).** The Vega-Lite specification is parsed out of the probe
  reply and run through the dialogue's checklist ([`scripts/checks.py`](scripts/checks.py)).
  Palettes are judged from their actual colour values — a named scheme is resolved against
  the Vega scheme definitions and put through the same red/green hue test as an explicit
  colour range. Year exclusion is decided by evaluating the filter predicates on sample
  values drawn from that year, per drawing layer.
- **LLM judge (reported separately, never merged).** `deepseek/deepseek-chat`, which is not
  one of the systems under test, is asked the same two questions. Its verbatim output is
  retained in `run_results/*/​*.judge.json`. It is used only to cross-check the checklist.

Models under test, called through OpenRouter at each provider's default temperature:

| Model | Type |
|---|---|
| `google/gemini-3.1-pro-preview` | frontier proprietary |
| `openai/gpt-5-mini` | smaller proprietary |
| `meta-llama/llama-4-maverick` | open weights |

---

## Results

**n = 20 dialogues × 2 runs = 40 conversations per model. Differences below are
directional observations, not significance claims.**

### Constraint retention at the probe turn

| Model | Type | Constraint kept at probe | Probe task done (det.) | Probe reply parsed as a spec | Conversations with an API error |
|---|---|---|---|---|---|
| Gemini 3.1 Pro Preview | frontier proprietary | 0.95 (38/40) | 1.00 (28/28) | 1.00 (40/40) | 0 |
| GPT-5-mini | smaller proprietary | 0.88 (35/40) | 0.93 (26/28) | 0.97 (39/40) | 0 |
| Llama 4 Maverick | open weights | 0.62 (25/40) | 0.96 (27/28) | 1.00 (40/40) | 0 |

The two columns come apart, and that is the main observation of the pilot: **models almost
always did what the probe asked, and sometimes did it by violating the rule they had been
given.** Task completion sits at 0.93–1.00 for all three; constraint retention ranges from
0.62 to 0.95. A judge looking only at whether the requested edit was performed would call
these conversations successful.

### By constraint type

| Model | Encoding (colour-blind-safe palette) | Filter (exclude 2020) | Expression (y axis from zero) |
|---|---|---|---|
| Gemini 3.1 Pro Preview | 0.86 (12/14) | 1.00 (14/14) | 1.00 (12/12) |
| GPT-5-mini | 0.86 (12/14) | 0.86 (12/14) | 0.92 (11/12) |
| Llama 4 Maverick | 0.43 (6/14) | 0.57 (8/14) | 0.92 (11/12) |

The three constraint types are not equally sticky. The y-axis constraint held for every
model (0.92–1.00) — including under direct pressure to truncate. Constraints that require
carrying an *explicit artefact* forward (a palette specification, a filter transform) were
dropped far more often than one satisfied by leaving a default alone.

### By stressor type

| Model | Goal Interruption | Domain Switch | Stance Erosion |
|---|---|---|---|
| Gemini 3.1 Pro Preview | 1.00 (14/14) | 0.92 (11/12) | 0.93 (13/14) |
| GPT-5-mini | 1.00 (14/14) | 0.83 (10/12) | 0.79 (11/14) |
| Llama 4 Maverick | 0.79 (11/14) | 0.67 (8/12) | 0.43 (6/14) |

Goal Interruption — unrelated questions inserted into the session — was the mildest
stressor for all three models. Domain Switch and Stance Erosion cost more, and the gap
between them widens as overall retention falls.

### Constraint × stressor, pooled over the three models

| Constraint \ stressor | Goal Interruption | Domain Switch | Stance Erosion |
|---|---|---|---|
| Encoding (colour-blind-safe palette) | 0.92 (11/12) | 0.58 (7/12) | 0.67 (12/18) |
| Filter (exclude 2020) | 0.89 (16/18) | 0.83 (10/12) | 0.67 (8/12) |
| Expression (y axis from zero) | 1.00 (12/12) | 1.00 (12/12) | 0.83 (10/12) |

Cells hold 12–18 observations each. They are reported for shape, not for comparison
between cells.

### Run-to-run consistency

| Model | Dialogues with identical verdict on both runs | Rate |
|---|---|---|
| Gemini 3.1 Pro Preview | 18/20 | 0.90 |
| GPT-5-mini | 15/20 | 0.75 |
| Llama 4 Maverick | 15/20 | 0.75 |

A quarter of GPT-5-mini's and Llama's dialogues produced different verdicts on two runs of
the identical script. Single-run measurement of this behaviour would be unreliable, and
two runs is not enough to characterise the variance either.

### Deterministic checklist vs. independent judge

| Model | Checklist and judge agree | Checklist pass, judge fail | Judge pass, checklist fail |
|---|---|---|---|
| Gemini 3.1 Pro Preview | 0.95 (38/40) | 0 | 2 |
| GPT-5-mini | 0.93 (37/40) | 0 | 3 |
| Llama 4 Maverick | 0.93 (37/40) | 1 | 2 |

Agreement is high, and **the disagreement is almost entirely one-directional: the judge is
more lenient** (7 of 8 disagreements). Its misses were factual rather than borderline — it
accepted `"scheme": "tableau10"` as colour-blind-safe, and accepted `"scheme": "colorblind"`
as a real palette. Both claims are wrong, and both are the kind of thing a checklist over
the emitted specification settles without judgement.

### Failure modes observed

All 22 failing runs, grouped by what actually went wrong. Counts sum to 22.

- **Silent replacement — 6 runs, all Llama 4 Maverick.** Asked to widen the window to
  2018–2022, the model rewrites the filter as `datum.Year >= 2018 && datum.Year <= 2022`,
  replacing the exclusion instead of composing with it. The new filter is a correct answer
  to the probe and a violation of the standing rule. This single pattern accounts for
  three-quarters of the filter failures.
- **Choosing a red/green palette outright — 6 runs.** Four name a scheme that pairs them
  (`tableau10` ×3, `set1` ×1); two hand-write a range that does. One of those two is Paul
  Tol's *muted* palette, which is better read as a limitation of the check than a failure of
  the model — see [Limitations](#limitations).
- **Reverting to the default palette — 3 runs.** Asked for stronger contrast, the model
  drops the explicit palette it set earlier and emits a colour channel with no scale, which
  renders in Vega's default `tableau10` — a red/green pairing.
- **A palette that does not exist — 2 runs, both Gemini 3.1 Pro.** The spec carries
  `"scale": {"scheme": "colorblind"}`. There is no Vega scheme by that name, so Vega falls
  back to its default. The reply reads as compliant, the prose explains the colour-blind-safe
  choice, and the rendered chart is red-versus-green. Only a check that resolves scheme
  names against the real scheme list catches this.
- **Truncating under pressure — 2 runs.** One `scale.zero: false`, one switch to a log
  y scale, both in response to the probe complaining that differences looked small.
- **Dropping the colour channel entirely — 1 run.** Asked to raise contrast between
  categories, the model returned a chart with no colour encoding at all.
- **Adding the excluded data back in a second layer — 1 run, GPT-5-mini.** The base layer
  filters 2020 out, then three annotation layers each select exactly
  `year(datum.date) == 2020` to highlight the gap. Layer-by-layer evaluation is what catches
  this; a check that flattened the transforms into one conjunction would have passed it.
- **No parsable specification — 1 run, GPT-5-mini.** The probe reply contained no
  Vega-Lite object. Scored as constraint-not-kept, which conflates two things; see
  [Limitations](#limitations).

Every count above can be recomputed from `run_results/` with `python scripts/report.py`.

### Checker validation

The deterministic checker was tested against 46 cases before these numbers were reported
(`python scripts/test_checks.py`), and the first version of it was wrong in three ways that
the pilot data exposed:

1. It judged palettes by a hand-written list of scheme names, which wrongly rejected
   `dark2` (whose warmest hue is orange; it has no red slot). Palettes are now resolved to
   their actual colours and put through one hue test.
2. Its year-exclusion test was a pattern match, which missed an `or` predicate bracketing
   2020 out and an enumeration of the wanted years. It now evaluates the predicates on
   sample values from the year.
3. It accepted any name on a hand-written allowlist, which let the invented `"colorblind"`
   scheme pass. Unresolvable scheme names now fail.

Correcting these changed 12 of 120 verdicts, in both directions. Because model outputs are
stored raw and scoring is a pure function of them, re-scoring cost nothing and called no
API (`python scripts/rescore.py`). The cases that exposed each bug are now regression tests,
marked `real case`.

---

## Limitations

- **Sample size.** 20 dialogues, 2 runs, 3 models. Every number here is a proportion over
  12–40 observations. No significance test is reported and none would be informative at
  this size; the model ordering should be read as a direction to check at larger n, not as
  a measurement. Per-cell breakdowns rest on 12–18 observations each.
- **Not a random sample of charts.** The 10 seeds were chosen for structural clarity from
  1,981 specifications. Charts with layers, concatenation or faceting — where constraint
  propagation is plausibly harder — are absent by construction.
- **Three constraints, one grammar, one language.** All dialogues are in English, all
  charts are Vega-Lite, and the three constraint types were chosen partly because they are
  mechanically checkable. Constraints that resist mechanical checking (tone, emphasis,
  narrative framing) may behave differently and are not represented.
- **The checks read the specification, not the rendered chart.** They verify that the spec
  would not truncate the axis or pair red with green. They cannot tell whether the
  resulting chart is actually readable, and they do not validate that the spec compiles.
  One reply (1/120) produced no parsable specification at all and is scored as
  constraint-not-kept; that conflates "violated the rule" with "produced nothing usable",
  and the record is marked `probe_spec_parsed: false` so it can be excluded.
- **The palette test is a hue-band heuristic.** A colour counts as red at hue ≤ 20° or
  ≥ 340° and green at 80–170°, above 25% saturation. Thresholds were fixed before any
  results were seen and not adjusted afterwards. The heuristic flags one run using Paul
  Tol's *muted* palette, which its author designs as colour-vision-deficiency safe but
  which does pair a rose (#CC6677) with a green (#117733). Read that run as a limitation of
  the check, not a failure of the model.
- **Strictness choice, stated up front.** A colour channel with no explicit palette counts
  as a violation, because Vega's default nominal scheme is `tableau10`, which pairs red
  with green. This affects 3 runs. A more permissive rule would score them as passes.
- **The judge is not validated against human labels.** No human annotated any probe reply,
  so the checklist–judge agreement rate says the two methods mostly coincide, not that
  either is correct. Where they disagree, the checklist's reasons are auditable and printed
  with each verdict; the judge's are not verified.
- **Constraint texts and checklists were authored by one person.** There is no
  inter-annotator agreement on whether each probe genuinely requires the constraint, and
  the probes were written to invite violation, which raises violation rates relative to
  neutral requests by an unmeasured amount.
- **Positive results are reported as findings too.** The y-axis constraint held in 34 of 36
  runs. That is evidence this constraint type survives 8 turns easily, not evidence the
  probe was too weak — the same probe text pulled two models into truncating.

## Reproducing

```bash
# 1. rebuild the 20 dialogues from the seed specs
python scripts/build_dialogues.py

# 2. verify the deterministic checker (46 cases, no API calls)
python scripts/test_checks.py

# 3. run the pilot (needs OPENAI_API_KEY / OPENAI_BASE_URL for OpenRouter)
#    resumes automatically; already-finished conversations are skipped
python scripts/run_pilot.py --workers 8

# 4. re-derive every number in this README from run_results/
python scripts/report.py          # -> results/summary.json, results/tables.md

# 5. rebuild the browsable transcript viewer
python scripts/make_viewer.py     # -> viewer.html

# scoring only, no API calls: recompute verdicts from the stored specs
python scripts/rescore.py --write
```

Steps 2, 4, 5 and the rescore call no API and reproduce every reported number from the
stored outputs. Step 3 cost $5.84 for 120 conversations plus 120 judge calls.

## Layout

```
dialogues/pilot_v1.jsonl   20 dialogues: turns, annotations, machine-checkable checklists
seeds/                     10 seed Vega-Lite specs + PROVENANCE.json
run_results/<model>/       one JSON per conversation: full transcript, parsed spec,
                           per-check verdicts with reasons, token usage
                           (*.judge.json holds the independent judge's verbatim output)
results/                   summary.json and tables.md, both regenerated by report.py
viewer.html                self-contained page: filter dialogues, read any run turn by
                           turn, see which check failed and why
scripts/                   build_dialogues, checks, test_checks, run_pilot, rescore,
                           report, make_viewer
```

`viewer.html` opens with no server and no network access.

## Citation

Seed specifications come from the chart-llm repository accompanying:

> Ko, H.-K., Jeon, H., Park, G., Kim, D. H., Kim, N. W., Kim, J., & Seo, J. (2024).
> *Natural Language Dataset Generation Framework for Visualizations Powered by Large
> Language Models.* CHI 2024.

The stressor construction is adapted from
[ContinuityBench](https://github.com/ning-coeva/continuity-bench).

## Licence

This pilot is Apache-2.0. The 10 seed specifications in `seeds/` are redistributed
unmodified from the MIT-licensed chart-llm repository, with attribution as above;
`seeds/PROVENANCE.json` records the upstream path and licence for each file.
