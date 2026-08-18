"""Run the pilot: replay each scripted dialogue against each model, twice.

Scoring is two-track and the tracks are kept separate in the output:
  - deterministic: parse the Vega-Lite spec from the probe reply and run the
    dialogue's checklist (scripts/checks.py). This is the primary metric.
  - judge: one call to a model that is NOT under test, asked the same questions.
    Its verbatim output is retained so the two tracks can be compared.

Records are written one JSON file per (model, dialogue, run), so an interrupted
run resumes without repeating work.
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import checks as C  # noqa: E402

# Models under test: one frontier proprietary, one smaller proprietary, one open-weights.
MODELS = [
    "google/gemini-3.1-pro-preview",
    "openai/gpt-5-mini",
    "meta-llama/llama-4-maverick",
]
# Not one of the systems under test, so no model scores its own output.
JUDGE_MODEL = "deepseek/deepseek-chat"

SYSTEM_PROMPT = (
    "You are a chart editing assistant. The user is iteratively editing a Vega-Lite "
    "chart across several turns.\n\n"
    "For any turn that asks for a change to the chart, reply with a one or two sentence "
    "explanation, then the complete updated Vega-Lite specification in a single fenced "
    "```json code block. Always output the whole specification, never a diff or a fragment.\n\n"
    "For a turn that only asks a question, answer it in prose; no code block is needed."
)

JUDGE_PROMPT = """You are grading one turn of a chart-editing conversation.

The user set a standing constraint earlier in the conversation:
  CONSTRAINT: {constraint}

The final user turn (the probe) was:
  PROBE: {probe}

The probe deliberately does not repeat the constraint.

Here is the assistant's reply to the probe:
---
{reply}
---

Answer two questions independently.

1. constraint_kept: does the chart produced by this reply still respect the standing
   constraint? Judge the specification the reply produces, not its prose promises.
2. task_done: does the reply carry out what the probe actually asked for?

Reply with only a JSON object, no code fence:
{{"constraint_kept": true|false, "constraint_reason": "<one sentence>",
  "task_done": true|false, "task_reason": "<one sentence>"}}"""


def load_env(path):
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def make_client():
    import openai
    return openai.OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ.get("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
    )


def call(client, model, messages, max_retries=4, timeout=180):
    """One chat completion. Temperature is left at the provider default."""
    last = None
    for attempt in range(max_retries):
        try:
            r = client.chat.completions.create(
                model=model, messages=messages, timeout=timeout)
            if not r.choices:
                raise RuntimeError("no choices returned")
            usage = getattr(r, "usage", None)
            return {
                "content": r.choices[0].message.content or "",
                "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
                "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
            }
        except Exception as e:
            last = e
            if attempt == max_retries - 1:
                break
            time.sleep(2 ** attempt * 2)
    return {"content": "", "error": "%s: %s" % (type(last).__name__, last),
            "prompt_tokens": None, "completion_tokens": None}


def slug(model):
    return re.sub(r"[^a-z0-9]+", "_", model.lower()).strip("_")


def run_one(client, dialogue, model, run_idx, out_dir):
    """Replay one dialogue against one model once, then score the probe turn."""
    path = os.path.join(out_dir, "%s_r%d.json" % (dialogue["dialogue_id"], run_idx))
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            pass  # corrupt partial file, redo it

    seed_block = json.dumps(dialogue["seed_spec"], ensure_ascii=False, indent=2)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    transcript, usage_in, usage_out, errors = [], 0, 0, []

    for i, turn in enumerate(dialogue["turns"]):
        content = turn["content"]
        if i == 0:
            content = ("Here is the current specification:\n\n```json\n%s\n```\n\n%s"
                       % (seed_block, content))
        messages.append({"role": "user", "content": content})
        resp = call(client, model, messages)
        if resp.get("error"):
            errors.append({"turn": turn["turn_id"], "error": resp["error"]})
        usage_in += resp.get("prompt_tokens") or 0
        usage_out += resp.get("completion_tokens") or 0
        messages.append({"role": "assistant", "content": resp["content"]})
        transcript.append({
            "turn_id": turn["turn_id"], "phase": turn["phase"],
            "user": content, "assistant": resp["content"],
            "error": resp.get("error"),
        })

    probe_reply = transcript[-1]["assistant"]
    spec, note = C.extract_spec(probe_reply)
    det_constraint = C.run_checks(spec, dialogue["checks"]["constraint"])
    det_task = C.run_checks(spec, dialogue["checks"]["task"])

    rec = {
        "dialogue_id": dialogue["dialogue_id"],
        "model": model,
        "run_index": run_idx,
        "constraint_type": dialogue["constraint_type"],
        "stressor_type": dialogue["stressor_type"],
        "chart_type": dialogue["chart_type"],
        "seed_spec_file": dialogue["seed_spec_file"],
        "transcript": transcript,
        "probe_spec_parsed": spec is not None,
        "probe_spec_note": note,
        "probe_spec": spec,
        "deterministic": {
            "constraint": det_constraint,
            "task": det_task,
            "constraint_kept": all(c["passed"] for c in det_constraint) if det_constraint else None,
            "task_done": (all(c["passed"] for c in det_task) if det_task else None),
        },
        "usage": {"prompt_tokens": usage_in, "completion_tokens": usage_out},
        "errors": errors,
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    return rec


def judge_one(client, dialogue, rec, out_dir):
    """Second, independent scoring pass. Verbatim judge output is retained."""
    path = os.path.join(out_dir, "%s_r%d.judge.json"
                        % (rec["dialogue_id"], rec["run_index"]))
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            pass
    prompt = JUDGE_PROMPT.format(
        constraint=dialogue["constraint_text"],
        probe=dialogue["turns"][-1]["content"],
        reply=rec["transcript"][-1]["assistant"][:12000] or "(empty reply)",
    )
    resp = call(client, JUDGE_MODEL, [{"role": "user", "content": prompt}])
    raw = resp["content"]
    parsed, perr = None, None
    try:
        m = re.search(r"\{.*\}", raw, re.S)
        parsed = json.loads(m.group(0)) if m else None
    except Exception as e:
        perr = str(e)
    out = {
        "dialogue_id": rec["dialogue_id"], "model": rec["model"],
        "run_index": rec["run_index"], "judge_model": JUDGE_MODEL,
        "judge_raw": raw, "judge_parsed": parsed, "parse_error": perr,
        "error": resp.get("error"),
        "usage": {"prompt_tokens": resp.get("prompt_tokens"),
                  "completion_tokens": resp.get("completion_tokens")},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dialogues", default=os.path.join(ROOT, "dialogues", "pilot_v1.jsonl"))
    ap.add_argument("--out", default=os.path.join(ROOT, "run_results"))
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--models", nargs="*", default=MODELS)
    ap.add_argument("--limit", type=int, default=None, help="only the first N dialogues")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-judge", action="store_true")
    args = ap.parse_args()

    load_env(os.path.join(ROOT, ".env"))
    load_env(os.path.join(os.path.dirname(ROOT), "continuity-bench-main", ".env"))
    client = make_client()

    dialogues = [json.loads(l) for l in open(args.dialogues, encoding="utf-8") if l.strip()]
    if args.limit:
        dialogues = dialogues[:args.limit]

    jobs = [(d, m, r) for m in args.models for d in dialogues for r in range(1, args.runs + 1)]
    print("%d conversations (%d dialogues x %d models x %d runs)"
          % (len(jobs), len(dialogues), len(args.models), args.runs))

    done, t0 = 0, time.time()
    records = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_one, client, d, m, r,
                          os.path.join(args.out, slug(m))): (d, m, r) for d, m, r in jobs}
        for fut in cf.as_completed(futs):
            d, m, r = futs[fut]
            try:
                rec = fut.result()
                records.append((d, rec))
            except Exception as e:
                print("  FAILED %s %s r%d: %s" % (d["dialogue_id"], m, r, e))
            done += 1
            if done % 10 == 0 or done == len(jobs):
                print("  %d/%d conversations (%.0fs)" % (done, len(jobs), time.time() - t0))

    if not args.no_judge:
        print("judging %d probe replies with %s" % (len(records), JUDGE_MODEL))
        with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(judge_one, client, d, rec,
                              os.path.join(args.out, slug(rec["model"]))) for d, rec in records]
            for i, fut in enumerate(cf.as_completed(futs), 1):
                try:
                    fut.result()
                except Exception as e:
                    print("  judge failed: %s" % e)
                if i % 20 == 0 or i == len(futs):
                    print("  %d/%d judged" % (i, len(futs)))

    tin = sum(r["usage"]["prompt_tokens"] for _, r in records)
    tout = sum(r["usage"]["completion_tokens"] for _, r in records)
    print("done in %.0fs | target-model tokens: %s in / %s out" % (time.time() - t0, tin, tout))


if __name__ == "__main__":
    main()
