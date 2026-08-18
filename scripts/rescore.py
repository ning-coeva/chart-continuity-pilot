"""Recompute the deterministic verdicts from the saved probe specifications.

The model outputs in run_results/ are the raw record; scoring is a pure function
of them. Correcting a check therefore costs nothing and calls no API. Run:

    python scripts/rescore.py            # show what would change
    python scripts/rescore.py --write    # write the new verdicts back
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import checks as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    dialogues = {json.loads(l)["dialogue_id"]: json.loads(l) for l in
                 open(os.path.join(ROOT, "dialogues", "pilot_v1.jsonl"), encoding="utf-8")
                 if l.strip()}

    changed, total = [], 0
    for f in sorted(glob.glob(os.path.join(ROOT, "run_results", "*", "*_r*.json"))):
        if f.endswith(".judge.json"):
            continue
        rec = json.load(open(f, encoding="utf-8"))
        d = dialogues[rec["dialogue_id"]]
        total += 1

        spec = rec.get("probe_spec")
        con = C.run_checks(spec, d["checks"]["constraint"])
        tsk = C.run_checks(spec, d["checks"]["task"])
        new_kept = all(c["passed"] for c in con) if con else None
        old_kept = rec["deterministic"]["constraint_kept"]

        if new_kept != old_kept:
            changed.append((rec["dialogue_id"], rec["model"].split("/")[-1], rec["run_index"],
                            old_kept, new_kept,
                            next((c["reason"] for c in con if not c["passed"]),
                                 con[0]["reason"] if con else "")))
        rec["deterministic"] = {
            "constraint": con, "task": tsk,
            "constraint_kept": new_kept,
            "task_done": (all(c["passed"] for c in tsk) if tsk else None),
        }
        if args.write:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(rec, fh, ensure_ascii=False, indent=1)

    print("%d records scored, %d verdicts changed" % (total, len(changed)))
    for did, model, run, old, new, why in changed:
        print("  %-8s %-24s r%d  %s -> %s   %s" % (did, model, run, old, new, why[:110]))
    if not args.write:
        print("\n(dry run; pass --write to persist)")


if __name__ == "__main__":
    main()
