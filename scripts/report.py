"""Aggregate run_results/ into summary.json and the tables used in README.md.

The deterministic checklist is the reported metric. The judge pass is reported
only as an independent second opinion, with its agreement rate against the
checklist, and is never mixed into the headline numbers.
"""
import glob
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "run_results")

MODEL_LABEL = {
    "google/gemini-3.1-pro-preview": "Gemini 3.1 Pro Preview",
    "openai/gpt-5-mini": "GPT-5-mini",
    "meta-llama/llama-4-maverick": "Llama 4 Maverick",
}
MODEL_KIND = {
    "google/gemini-3.1-pro-preview": "frontier proprietary",
    "openai/gpt-5-mini": "smaller proprietary",
    "meta-llama/llama-4-maverick": "open weights",
}
CONSTRAINT_LABEL = {
    "encoding": "Encoding (colour-blind-safe palette)",
    "filter": "Filter (exclude 2020)",
    "expression": "Expression (y axis from zero)",
}
STRESSOR_LABEL = {
    "goal_interruption": "Goal Interruption",
    "domain_switch": "Domain Switch",
    "stance_erosion": "Stance Erosion",
}


def load():
    recs = []
    for f in sorted(glob.glob(os.path.join(RESULTS, "*", "*_r*.json"))):
        if f.endswith(".judge.json"):
            continue
        r = json.load(open(f, encoding="utf-8"))
        jf = f[:-5] + ".judge.json"
        r["judge"] = json.load(open(jf, encoding="utf-8")) if os.path.exists(jf) else None
        recs.append(r)
    return recs


def rate(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, 0
    return sum(1 for v in vals if v) / len(vals), len(vals)


def fmt(r):
    v, n = r
    return "n/a" if v is None else "%.2f (%d/%d)" % (v, round(v * n), n)


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


def main():
    recs = load()
    if not recs:
        print("no results found in %s" % RESULTS)
        sys.exit(1)

    models = [m for m in MODEL_LABEL if any(r["model"] == m for r in recs)]
    by_model = defaultdict(list)
    for r in recs:
        by_model[r["model"]].append(r)

    summary = {
        "n_dialogues": len({r["dialogue_id"] for r in recs}),
        "n_runs_per_dialogue": max(r["run_index"] for r in recs),
        "n_conversations": len(recs),
        "judge_model": (recs[0]["judge"] or {}).get("judge_model"),
        "models": {},
    }

    # ---- headline: constraint retention at the probe turn
    rows = []
    for m in models:
        rs = by_model[m]
        keep = rate([r["deterministic"]["constraint_kept"] for r in rs])
        parse = rate([r["probe_spec_parsed"] for r in rs])
        task = rate([r["deterministic"]["task_done"] for r in rs])
        errs = sum(1 for r in rs if r["errors"])
        rows.append([MODEL_LABEL[m], MODEL_KIND[m], fmt(keep), fmt(task), fmt(parse), errs])
        summary["models"][m] = {
            "label": MODEL_LABEL[m], "kind": MODEL_KIND[m],
            "constraint_retention": keep[0], "n_scored": keep[1],
            "task_done_deterministic": task[0], "n_task_scored": task[1],
            "probe_spec_parse_rate": parse[0], "conversations_with_api_error": errs,
        }
    t_main = table(
        ["Model", "Type", "Constraint kept at probe", "Probe task done (det.)",
         "Probe reply parsed as a spec", "Conversations with an API error"], rows)

    # ---- by constraint type
    rows = []
    for m in models:
        rs = by_model[m]
        cells = [MODEL_LABEL[m]]
        for ct in ("encoding", "filter", "expression"):
            cells.append(fmt(rate([r["deterministic"]["constraint_kept"]
                                   for r in rs if r["constraint_type"] == ct])))
        rows.append(cells)
        summary["models"][m]["by_constraint_type"] = {
            ct: rate([r["deterministic"]["constraint_kept"]
                      for r in rs if r["constraint_type"] == ct])[0]
            for ct in ("encoding", "filter", "expression")}
    t_constraint = table(["Model"] + [CONSTRAINT_LABEL[c] for c in
                                      ("encoding", "filter", "expression")], rows)

    # ---- by stressor type
    rows = []
    for m in models:
        rs = by_model[m]
        cells = [MODEL_LABEL[m]]
        for st in ("goal_interruption", "domain_switch", "stance_erosion"):
            cells.append(fmt(rate([r["deterministic"]["constraint_kept"]
                                   for r in rs if r["stressor_type"] == st])))
        rows.append(cells)
        summary["models"][m]["by_stressor_type"] = {
            st: rate([r["deterministic"]["constraint_kept"]
                      for r in rs if r["stressor_type"] == st])[0]
            for st in ("goal_interruption", "domain_switch", "stance_erosion")}
    t_stressor = table(["Model"] + [STRESSOR_LABEL[s] for s in
                                    ("goal_interruption", "domain_switch", "stance_erosion")], rows)

    # ---- pooled cells: constraint x stressor across all models
    rows = []
    for ct in ("encoding", "filter", "expression"):
        cells = [CONSTRAINT_LABEL[ct]]
        for st in ("goal_interruption", "domain_switch", "stance_erosion"):
            cells.append(fmt(rate([r["deterministic"]["constraint_kept"] for r in recs
                                   if r["constraint_type"] == ct and r["stressor_type"] == st])))
        rows.append(cells)
    t_cells = table(["Constraint \\ stressor"] + [STRESSOR_LABEL[s] for s in
                                                  ("goal_interruption", "domain_switch", "stance_erosion")], rows)

    # ---- run-to-run consistency (same dialogue, same model, 2 runs)
    rows = []
    for m in models:
        by_d = defaultdict(list)
        for r in by_model[m]:
            by_d[r["dialogue_id"]].append(r["deterministic"]["constraint_kept"])
        pairs = [v for v in by_d.values() if len(v) >= 2 and all(x is not None for x in v)]
        same = sum(1 for v in pairs if len(set(v)) == 1)
        rows.append([MODEL_LABEL[m], "%d/%d" % (same, len(pairs)),
                     "%.2f" % (same / len(pairs)) if pairs else "n/a"])
        summary["models"][m]["run_to_run_identical"] = (same / len(pairs)) if pairs else None
    t_consistency = table(["Model", "Dialogues with identical verdict on both runs", "Rate"], rows)

    # ---- deterministic vs judge
    rows = []
    agree_all = []
    for m in models:
        pairs = []
        for r in by_model[m]:
            j = (r.get("judge") or {}).get("judge_parsed") or {}
            if "constraint_kept" in j and r["deterministic"]["constraint_kept"] is not None:
                pairs.append((bool(r["deterministic"]["constraint_kept"]), bool(j["constraint_kept"])))
        agree_all.extend(pairs)
        if pairs:
            a = sum(1 for d, jj in pairs if d == jj) / len(pairs)
            det_only = sum(1 for d, jj in pairs if d and not jj)
            jud_only = sum(1 for d, jj in pairs if jj and not d)
            rows.append([MODEL_LABEL[m], "%.2f (%d/%d)" % (a, round(a * len(pairs)), len(pairs)),
                         det_only, jud_only])
        else:
            rows.append([MODEL_LABEL[m], "n/a", "-", "-"])
    t_agree = table(["Model", "Checklist and judge agree",
                     "Checklist pass, judge fail", "Judge pass, checklist fail"], rows)
    summary["judge_agreement_overall"] = (
        sum(1 for d, j in agree_all if d == j) / len(agree_all)) if agree_all else None
    summary["judge_agreement_n"] = len(agree_all)

    # ---- failure reasons, for the write-up
    reasons = defaultdict(int)
    for r in recs:
        if r["deterministic"]["constraint_kept"] is False:
            for c in r["deterministic"]["constraint"]:
                if not c["passed"]:
                    key = c["reason"].split(":")[0][:80]
                    reasons[(r["constraint_type"], key)] += 1
    summary["failure_reasons"] = {"%s | %s" % k: v for k, v in
                                  sorted(reasons.items(), key=lambda kv: -kv[1])}

    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    json.dump(summary, open(os.path.join(ROOT, "results", "summary.json"), "w",
                            encoding="utf-8"), indent=2, ensure_ascii=False)

    md = "\n\n".join([
        "### Constraint retention at the probe turn", t_main,
        "### By constraint type", t_constraint,
        "### By stressor type", t_stressor,
        "### Constraint x stressor, pooled over the three models", t_cells,
        "### Run-to-run consistency", t_consistency,
        "### Deterministic checklist vs. independent judge", t_agree,
    ])
    open(os.path.join(ROOT, "results", "tables.md"), "w", encoding="utf-8").write(md + "\n")
    print(md)
    print("\nfailure reasons:")
    for k, v in summary["failure_reasons"].items():
        print("  %3d  %s" % (v, k))
    print("\nwrote results/summary.json and results/tables.md")


if __name__ == "__main__":
    main()
