"""Emit viewer.html: a self-contained page showing every dialogue turn by turn
next to the verdict for that run. Same inspection idea as the ContinuityBench
Explorer: aggregate -> run -> turn -> the reason a check passed or failed.
"""
import glob
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MODEL_LABEL = {
    "google/gemini-3.1-pro-preview": "Gemini 3.1 Pro Preview",
    "openai/gpt-5-mini": "GPT-5-mini",
    "meta-llama/llama-4-maverick": "Llama 4 Maverick",
}

CSS = """
:root{--bg:#f4f5f7;--surface:#fff;--surface2:#f8f9fb;--text:#14162a;--muted:#585e74;
--faint:#8b90a3;--border:#e1e3ea;--accent:#3730a3;--accent-soft:#ecebfa;
--pass:#0f6b3f;--pass-bg:#e6f4ea;--fail:#a3312a;--fail-bg:#fdeeee;--radius:6px;
--mono:ui-monospace,SFMono-Regular,Consolas,monospace}
*{margin:0;padding:0;box-sizing:border-box}
body{font:13px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--text)}
header{background:var(--surface);border-bottom:1px solid var(--border);padding:14px 20px}
h1{font-size:18px;font-weight:800;letter-spacing:-.3px}
.sub{font-size:12.5px;color:var(--muted);margin-top:4px}
.caveat{font-size:11.5px;color:var(--faint);font-style:italic;margin-top:3px}
.wrap{display:grid;grid-template-columns:392px 1fr;align-items:start}
.list{border-right:1px solid var(--border);background:var(--surface);height:calc(100vh - 96px);
overflow-y:auto;padding:8px}
.filters{display:flex;flex-wrap:wrap;gap:4px;padding:4px 4px 8px;border-bottom:1px solid var(--border);
margin-bottom:6px}
.filters select{font:inherit;font-size:11px;border:1px solid var(--border);border-radius:4px;padding:3px 4px;background:var(--surface)}
.item{border:1px solid var(--border);border-radius:var(--radius);padding:7px 9px;margin-bottom:5px;cursor:pointer;background:var(--surface2)}
.item:hover{border-color:var(--accent)}
.item.sel{border-color:var(--accent);background:var(--accent-soft)}
.item-top{display:flex;align-items:center;gap:6px;margin-bottom:3px}
.did{font-family:var(--mono);font-size:11px;font-weight:700}
.tag{font-size:9px;font-weight:700;padding:1px 5px;border-radius:9px;background:var(--surface);
border:1px solid var(--border);color:var(--muted);white-space:nowrap}
.verdicts{display:flex;gap:3px;margin-left:auto}
.v{width:16px;height:16px;border-radius:3px;font-size:9px;font-weight:800;display:flex;
align-items:center;justify-content:center}
.v.pass{background:var(--pass-bg);color:var(--pass);border:1px solid #b7dfca}
.v.fail{background:var(--fail-bg);color:var(--fail);border:1px solid #f3cccb}
.v.na{background:#eceef2;color:var(--faint);border:1px dashed var(--border)}
.item-meta{font-size:10.5px;color:var(--faint)}
.detail{padding:14px 18px 40px;height:calc(100vh - 96px);overflow-y:auto}
.dtitle{font-size:15px;font-weight:800}
.dsub{font-size:11.5px;color:var(--muted);margin:2px 0 10px}
.runtabs{display:flex;gap:4px;margin-bottom:10px;flex-wrap:wrap}
.rt{border:1px solid var(--border);background:var(--surface);border-radius:4px;padding:3px 9px;
font-size:11px;font-weight:700;cursor:pointer;color:var(--muted)}
.rt.on{background:var(--accent);border-color:var(--accent);color:#fff}
.box{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
padding:9px 11px;margin-bottom:10px}
.box h3{font-size:10.5px;text-transform:uppercase;letter-spacing:.3px;color:var(--muted);margin-bottom:6px}
.chk{font-size:11.5px;padding:5px 7px;border-radius:4px;margin-bottom:4px;border:1px solid var(--border)}
.chk.pass{background:var(--pass-bg);border-color:#b7dfca}
.chk.fail{background:var(--fail-bg);border-color:#f3cccb}
.chk .why{color:var(--muted);font-family:var(--mono);font-size:10.5px;margin-top:2px;word-break:break-word}
.turn{border:1px solid var(--border);border-radius:var(--radius);margin-bottom:7px;background:var(--surface)}
.turn.probe{border-color:var(--accent);box-shadow:inset 3px 0 0 var(--accent)}
.turn-h{display:flex;align-items:center;gap:6px;padding:6px 10px;border-bottom:1px solid var(--border);
background:var(--surface2);border-radius:var(--radius) var(--radius) 0 0}
.ph{font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.3px;padding:1px 5px;border-radius:8px}
.ph.establish{background:#eef2fb;color:#24447a}.ph.stress{background:#fdf4e3;color:#7a5a12}
.ph.probe{background:#fdeeee;color:#8a2c28}
.tn{font-size:10px;color:var(--faint);font-weight:700}
.msg{padding:7px 10px;font-size:11.5px;line-height:1.55;white-space:pre-wrap;word-break:break-word}
.msg.user{background:#f7f9fd;border-bottom:1px dashed var(--border)}
.role{font-size:9px;font-weight:800;text-transform:uppercase;color:var(--faint);display:block;margin-bottom:3px}
.msg pre{font-family:var(--mono);font-size:10.5px;background:var(--surface2);border:1px solid var(--border);
border-radius:4px;padding:6px;overflow-x:auto;white-space:pre;margin-top:4px}
.judge{font-size:11.5px}
.judge .jr{font-family:var(--mono);font-size:10.5px;color:var(--muted);margin-top:3px}
.note{font-size:11px;color:var(--muted);background:#fdf8ef;border:1px solid #ecdfc4;
border-radius:4px;padding:7px 9px;margin-bottom:10px;line-height:1.5}
@media(max-width:980px){.wrap{grid-template-columns:1fr}.list,.detail{height:auto;border-right:none}}
"""

JS = """
const $=s=>document.querySelector(s);
let sel=DATA.dialogues[0].dialogue_id, selModel=null, selRun=1;

function runsFor(did){return DATA.runs.filter(r=>r.dialogue_id===did);}
function verdictClass(v){return v===true?'pass':v===false?'fail':'na';}
function verdictChar(v){return v===true?'\\u2713':v===false?'\\u2715':'\\u2013';}

function renderList(){
  const fc=$('#fConstraint').value, fs=$('#fStressor').value, fm=$('#fModel').value;
  let html='';
  for(const d of DATA.dialogues){
    if(fc&&d.constraint_type!==fc)continue;
    if(fs&&d.stressor_type!==fs)continue;
    const rs=runsFor(d.dialogue_id).filter(r=>!fm||r.model===fm);
    html+=`<div class="item ${d.dialogue_id===sel?'sel':''}" data-did="${d.dialogue_id}">
      <div class="item-top"><span class="did">${d.dialogue_id}</span>
      <span class="tag">${d.chart_type}</span>
      <span class="verdicts">${rs.map(r=>`<span class="v ${verdictClass(r.constraint_kept)}"
        title="${MODELS[r.model]||r.model} run ${r.run_index}">${verdictChar(r.constraint_kept)}</span>`).join('')}</span></div>
      <div class="item-meta">${CLABEL[d.constraint_type]} &middot; ${SLABEL[d.stressor_type]}</div></div>`;
  }
  $('#list').innerHTML=html||'<div class="item-meta" style="padding:8px">No dialogue matches this filter.</div>';
  document.querySelectorAll('.item').forEach(el=>el.onclick=()=>{sel=el.dataset.did;selModel=null;renderAll();});
}

function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function fmtMsg(t){
  // render fenced code blocks as <pre>
  return esc(t).replace(/```(?:json|vega-?lite)?\\n([\\s\\S]*?)```/g,(m,p)=>'<pre>'+p.trim()+'</pre>');
}

function renderDetail(){
  const d=DATA.dialogues.find(x=>x.dialogue_id===sel);
  const rs=runsFor(sel);
  if(!selModel&&rs.length)selModel=rs[0].model;
  const run=rs.find(r=>r.model===selModel&&r.run_index===selRun)||rs.find(r=>r.model===selModel)||rs[0];
  let h=`<div class="dtitle">${d.dialogue_id} &middot; ${CLABEL[d.constraint_type]}</div>
  <div class="dsub">${SLABEL[d.stressor_type]} &middot; ${d.chart_type} &middot; seed <code>${d.seed_spec_file}</code>
   &middot; ${d.n_turns} turns</div>`;
  h+=`<div class="note"><b>Standing constraint:</b> ${esc(d.constraint_text)}<br>
      <b>What the probe tests:</b> ${esc(d.probe_expectation)}<br>
      <b>Stressor design:</b> ${esc(d.stress_note)}</div>`;
  h+='<div class="runtabs">';
  for(const r of rs){
    h+=`<button class="rt ${r===run?'on':''}" data-m="${r.model}" data-r="${r.run_index}">
      ${MODELS[r.model]||r.model} &middot; run ${r.run_index}
      <span class="v ${verdictClass(r.constraint_kept)}" style="display:inline-flex;vertical-align:middle;margin-left:4px">${verdictChar(r.constraint_kept)}</span></button>`;
  }
  h+='</div>';
  if(run){
    h+='<div class="box"><h3>Deterministic checklist (probe turn)</h3>';
    for(const c of run.constraint_checks)
      h+=`<div class="chk ${c.passed?'pass':'fail'}"><b>${c.passed?'PASS':'FAIL'}</b> &mdash; ${esc(c.description)}
          <div class="why">${esc(c.reason)}</div></div>`;
    for(const c of run.task_checks)
      h+=`<div class="chk ${c.passed?'pass':'fail'}"><b>${c.passed?'PASS':'FAIL'}</b> (task) &mdash; ${esc(c.description)}
          <div class="why">${esc(c.reason)}</div></div>`;
    if(!run.spec_parsed)h+=`<div class="chk fail"><b>No spec parsed</b><div class="why">${esc(run.spec_note)}</div></div>`;
    h+='</div>';
    if(run.judge)
      h+=`<div class="box judge"><h3>Independent judge (${esc(DATA.judge_model)}) &mdash; not used in the reported metric</h3>
        <div><b>constraint kept:</b> ${run.judge.constraint_kept} <div class="jr">${esc(run.judge.constraint_reason||'')}</div></div>
        <div style="margin-top:5px"><b>probe task done:</b> ${run.judge.task_done} <div class="jr">${esc(run.judge.task_reason||'')}</div></div></div>`;
    h+='<div class="box"><h3>Conversation</h3>';
    for(const t of run.transcript){
      h+=`<div class="turn ${t.phase}"><div class="turn-h"><span class="ph ${t.phase}">${t.phase}</span>
        <span class="tn">Turn ${t.turn_id}</span></div>
        <div class="msg user"><span class="role">user</span>${fmtMsg(t.user)}</div>
        <div class="msg"><span class="role">assistant</span>${fmtMsg(t.assistant)||'<i>(empty)</i>'}</div></div>`;
    }
    h+='</div>';
  }
  $('#detail').innerHTML=h;
  document.querySelectorAll('.rt').forEach(b=>b.onclick=()=>{selModel=b.dataset.m;selRun=+b.dataset.r;renderDetail();
    document.querySelectorAll('.rt').forEach(x=>x.classList.remove('on'));b.classList.add('on');});
}
function renderAll(){renderList();renderDetail();}
['fConstraint','fStressor','fModel'].forEach(id=>$('#'+id).onchange=renderAll);
renderAll();
"""


def main():
    dialogues = [json.loads(l) for l in
                 open(os.path.join(ROOT, "dialogues", "pilot_v1.jsonl"), encoding="utf-8") if l.strip()]
    runs = []
    judge_model = None
    for f in sorted(glob.glob(os.path.join(ROOT, "run_results", "*", "*_r*.json"))):
        if f.endswith(".judge.json"):
            continue
        r = json.load(open(f, encoding="utf-8"))
        jf = f[:-5] + ".judge.json"
        j = json.load(open(jf, encoding="utf-8")) if os.path.exists(jf) else None
        if j:
            judge_model = j.get("judge_model")
        runs.append({
            "dialogue_id": r["dialogue_id"], "model": r["model"], "run_index": r["run_index"],
            "constraint_kept": r["deterministic"]["constraint_kept"],
            "constraint_checks": [{"description": c["description"], "passed": c["passed"],
                                   "reason": c["reason"]} for c in r["deterministic"]["constraint"]],
            "task_checks": [{"description": c["description"], "passed": c["passed"],
                             "reason": c["reason"]} for c in r["deterministic"]["task"]],
            "spec_parsed": r["probe_spec_parsed"], "spec_note": r["probe_spec_note"],
            "transcript": r["transcript"],
            "judge": (j or {}).get("judge_parsed"),
        })

    slim = [{k: d[k] for k in ("dialogue_id", "seed_spec_file", "chart_type", "constraint_type",
                               "constraint_text", "stressor_type", "stress_note", "n_turns",
                               "probe_expectation")} for d in dialogues]
    data = {"dialogues": slim, "runs": runs, "judge_model": judge_model or "n/a"}

    page = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ChartContinuity Pilot &mdash; dialogue viewer</title>
<style>%s</style></head><body>
<header>
  <h1>ChartContinuity Pilot &mdash; dialogue viewer</h1>
  <p class="sub">20 scripted chart-editing dialogues &middot; establish &rarr; stress &rarr; probe &middot;
     %d conversations across %d models, 2 runs each. Verdicts come from the deterministic
     checklist; the judge column is shown for comparison only.</p>
  <p class="caveat">A pilot probe set, not a benchmark. n=20 supports directional observations only.</p>
</header>
<div class="wrap">
  <div class="list">
    <div class="filters">
      <select id="fConstraint"><option value="">all constraints</option>
        <option value="encoding">encoding</option><option value="filter">filter</option>
        <option value="expression">expression</option></select>
      <select id="fStressor"><option value="">all stressors</option>
        <option value="goal_interruption">goal interruption</option>
        <option value="domain_switch">domain switch</option>
        <option value="stance_erosion">stance erosion</option></select>
      <select id="fModel"><option value="">all models</option>%s</select>
    </div>
    <div id="list"></div>
  </div>
  <div class="detail" id="detail"></div>
</div>
<script>
const DATA=%s;
const MODELS=%s;
const CLABEL={"encoding":"Encoding (colour-blind-safe palette)","filter":"Filter (exclude 2020)","expression":"Expression (y from zero)"};
const SLABEL={"goal_interruption":"Goal Interruption","domain_switch":"Domain Switch","stance_erosion":"Stance Erosion"};
%s
</script></body></html>""" % (
        CSS, len(runs), len({r["model"] for r in runs}),
        "".join('<option value="%s">%s</option>' % (html.escape(m), html.escape(MODEL_LABEL.get(m, m)))
                for m in sorted({r["model"] for r in runs})),
        json.dumps(data, ensure_ascii=False),
        json.dumps(MODEL_LABEL, ensure_ascii=False),
        JS)

    out = os.path.join(ROOT, "viewer.html")
    open(out, "w", encoding="utf-8").write(page)
    print("wrote %s (%.1f MB, %d runs)" % (out, os.path.getsize(out) / 1e6, len(runs)))


if __name__ == "__main__":
    main()
