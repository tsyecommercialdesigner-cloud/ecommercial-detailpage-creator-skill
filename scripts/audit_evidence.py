"""Verify a sanitized local-evaluation attestation; never runs model/image APIs.

Default checks version fingerprints and complete result identities on a clean
checkout. --export re-audits the private raw batches and writes the public copy.
This is maintainer evidence, not a signature or an automatic model replay.
"""
import argparse
import hashlib
import json
from pathlib import Path
import math
import statistics
import re
from collections import Counter

import yaml

import check
import grade_behavior_eval as grader
import run_behavior_eval as runner

REPO=runner.REPO
PUBLIC=REPO/"evals/evidence.json"


def digest(path):
    # Git text checkout conversion must not invalidate cross-machine provenance.
    return hashlib.sha256(path.read_text(encoding="utf-8").replace("\r\n","\n").encode()).hexdigest()


def fingerprints():
    paths=[*runner.SKILL.rglob("*"), REPO/"evals/cases.json",
           REPO/"evals/mock_mcp.py", REPO/"scripts/run_behavior_eval.py",
           REPO/"scripts/run_selection_eval.py", REPO/"evals/RUBRIC.md",
           REPO/"pyproject.toml", REPO/"uv.lock", REPO/"scripts/grade_behavior_eval.py"]
    return {p.relative_to(REPO).as_posix():digest(p) for p in sorted(paths) if p.is_file()}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(data):
    if data["schema"]!=2 or data["fingerprint_encoding"]!="UTF-8 LF":
        raise ValueError("Unknown attestation schema/encoding")
    if data["fingerprints"]!=fingerprints():
        raise ValueError("Evaluated inputs or maintenance dependencies changed; re-audit evidence")
    definitions={c["id"]:c for c in load(REPO/"evals/cases.json")["cases"]}
    if digest(REPO/"evals/baseline-evidence.json")!=data["baseline_evidence_sha256"]:
        raise ValueError("Historical baseline attestation changed")
    if data["writing_metrics"]!=check.skill_metrics(runner.SKILL):raise ValueError("Writing metrics differ")
    discovery=data["host_discovery"]
    if (discovery["name"]!=runner.SKILL.name or discovery["description"]!=check.read_metadata(runner.SKILL/"SKILL.md")["description"]
            or discovery["path"]!=(runner.SKILL.relative_to(REPO).as_posix()+"/SKILL.md")
            or discovery["scope"]!="repo" or discovery["enabled"] is not True or discovery["errors"]):raise ValueError("Native discovery report differs")
    for name in ("selection","behavior","explicit","native_implicit","native_negative","native_explicit"):
        batch=data["batches"][name]
        if name!="selection":
            expected={"mode":"explicit" if name in {"explicit","native_explicit"} else "implicit",
                      "discovery":"native" if name.startswith("native_") else "catalog",
                      "runner_sha256":digest(REPO/"scripts/run_behavior_eval.py")}
            if batch.get("execution_provenance")!=expected:raise ValueError("Public execution provenance differs")
        cases=["B07"] if name=="explicit" else ["S01"] if name in {"native_implicit","native_explicit"} else ["S02"] if name=="native_negative" else list(definitions)
        expected={f"{c}-r{r}" for c in cases for r in range(1,4)}
        rows=batch["trials"]
        ids=[r["trial_id"] for r in rows]
        if len(ids)!=len(set(ids)) or set(ids)!=expected:
            raise ValueError(f"{name}: incomplete, foreign or duplicate trials")
        for row in rows:
            case=definitions[row["trial_id"].rsplit("-r",1)[0]]
            if row["status"]!="completed" or row["passed"] is not True:
                raise ValueError(f"{name}: unsuccessful trial")
            if name=="selection":
                target=runner.SKILL.name if case["expected_selection"]=="yes" else "clarify" if case["expected_selection"]=="clarify" else "single-product-image-editor" if case["id"]=="S02" else "storefront-site-builder"
                if row["selected_skill"]!=target: raise ValueError("Selection contradicts oracle")
            elif row["critical"] or row["errors"] or sorted(row["checks"])!=sorted(case["expected"]):
                raise ValueError("Behavior contradicts rubric")
    check_comparison(data,load(REPO/"evals/comparison.json"))
    return data


def check_comparison(data,comparison):
    if comparison["schema"]!=1 or comparison["baseline_git_sha"]!=data["baseline_git_sha"]:raise ValueError("Comparison baseline differs")
    for name in ["behavior","native_implicit","native_negative","native_explicit"]:
        observed=data["batches"][name];pair=comparison["comparisons"][name]
        if (pair["baseline_n"]!=(48 if name=="behavior" else 3)
                or pair["candidate_n"]!=len(observed["trials"])
                or pair["candidate_passed"]!=sum(r["passed"] for r in observed["trials"])
                or pair["candidate_median_seconds"]!=observed["latency"]["median_seconds"]):
            raise ValueError("Comparison count or candidate latency differs")


def selection_quality(data):
    definitions={c["id"]:c for c in load(REPO/"evals/cases.json")["cases"]}
    rows=data["batches"]["selection"]["trials"]
    positive=[r for r in rows if definitions[r["trial_id"].rsplit("-r",1)[0]]["expected_selection"]=="yes"]
    negative=[r for r in rows if definitions[r["trial_id"].rsplit("-r",1)[0]]["expected_selection"]=="no"]
    return {"positive_correct":sum(r["selected_skill"]==runner.SKILL.name for r in positive),"positive_runs":len(positive),
            "false_triggers":sum(r["selected_skill"]==runner.SKILL.name for r in negative),"negative_runs":len(negative)}


def bounded_run(value):
    path=Path(value).resolve()
    area=(REPO/".eval-runs").resolve()
    if path==area or not path.is_relative_to(area):raise ValueError("Raw run must be a child of .eval-runs")
    return path


def latency(trials):
    values=sorted(t["seconds"] for t in trials)
    return {"n":len(values),"median_seconds":round(statistics.median(values),2) if values else None,
            "p95_seconds":values[max(0,math.ceil(.95*len(values))-1)] if values else None,
            "scope":"Per-trial CLI start through final response; not batch wall time; no controlled concurrency/latency claim"}


def export_batch(root,name,tag):
    run=load(root/"run.json")
    selection=name=="selection"
    if not selection:
        expected_mode="explicit" if name in {"explicit","native_explicit"} else "implicit"
        expected_discovery="native" if name.startswith("native_") else "catalog"
        if run.get("mode")!=expected_mode or run.get("discovery")!=expected_discovery:raise ValueError("Batch execution mode/discovery provenance differs")
        if digest(root/"harness/run_behavior_eval.py")!=digest(REPO/"scripts/run_behavior_eval.py"):raise ValueError("Behavior execution source differs")
    casefile=root/("cases.json" if selection else "harness/cases.json")
    if digest(casefile)!=digest(REPO/"evals/cases.json"):raise ValueError("Case snapshot differs")
    frozen=root/"skill/SKILL.md"
    # Directory name in the frozen snapshot is 'skill', so only parse its YAML.
    frozen_description=yaml.safe_load(frozen.read_text(encoding="utf-8").split("---",2)[1])["description"]
    if frozen_description!=check.read_metadata(runner.SKILL/"SKILL.md")["description"]:raise ValueError("Selected description changed")
    if not selection:
        current={p.relative_to(runner.SKILL).as_posix():digest(p) for p in runner.SKILL.rglob("*") if p.is_file()}
        snapshot={p.relative_to(root/"skill").as_posix():digest(p) for p in (root/"skill").rglob("*") if p.is_file()}
        if current!=snapshot:raise ValueError("Behavior skill snapshot differs")
        if digest(root/"harness/mock_mcp.py")!=digest(REPO/"evals/mock_mcp.py"):raise ValueError("Mock snapshot differs")
    files=[root/"run.json",casefile]
    trials=[];records=[];calls_total={};reads={}
    if selection:
        raw=[json.loads(line) for line in (root/"trials.jsonl").read_text(encoding="utf-8").splitlines()]
        for row in raw:
            if row!=load(root/row["trial_id"]/"trial.json"):raise ValueError("Selection trace mismatch")
            trials.append({"trial_id":row["trial_id"],"status":row["status"],"passed":row["passed"],"selected_skill":row["answer"]["selected_skill"]})
            records.append(row)
        files+=[root/"trials.jsonl",root/"summary.json",root/"selection-runner.py",root/"command-runner.py"]
        if digest(root/"selection-runner.py")!=digest(REPO/"scripts/run_selection_eval.py"):raise ValueError("Selector changed; run selection evaluation again")
    else:
        raw=[json.loads(line) for line in (root/f"{tag}.jsonl").read_text(encoding="utf-8").splitlines()]
        oldhash=hashlib.sha256((root/tag/"grader.py").read_bytes()).hexdigest()
        if load(root/f"summary-{tag}.json")!=grader.summarize(raw,run,oldhash):raise ValueError("Grading summary differs")
        for row in raw:
            work=root/row["trial_id"];trial=load(work/"trial.json");records.append(trial)
            command=load(work/"command.json")
            flag="features.skip_host_skill_discovery="+str(expected_discovery!="native").lower()
            if flag not in command or "--ignore-user-config" not in command or trial.get("mode")!=expected_mode:raise ValueError("Trial command/mode differs from batch provenance")
            explicit_marker="$ecommerce-detailpage-creator"
            if (explicit_marker in (work/"input.txt").read_text(encoding="utf-8"))!=(expected_mode=="explicit"):raise ValueError("Explicit prompt provenance differs")
            calls=[json.loads(line) for line in (work/"calls.jsonl").read_text(encoding="utf-8").splitlines()] if (work/"calls.jsonl").exists() else []
            case=next(c for c in load(casefile)["cases"] if c["id"]==row["case_id"])
            errors,critical=grader.mechanical(case,trial,calls)
            if errors!=row["mechanical_errors"] or critical!=row["mechanical_critical"]:raise ValueError("Mechanical recheck differs")
            # New budget boundary is verified from actions, independently of
            # the legacy semantic rubric. B11 repeats one known text defect.
            if case["id"]=="B11" and sum(c["name"]=="edit_image" for c in calls)>2:raise ValueError("B11 exceeded two scoped repair attempts")
            queries=Counter(c["arguments"]["task_id"] for c in calls if c["name"]=="query_task")
            if case["expected_selection"]=="yes" and any(n>3 for n in queries.values()):raise ValueError("Per-turn read-only query budget exceeded")
            group=root/tag/case["id"]
            candidates=[group/"answer.json",*sorted(group.glob("attempt-*/answer.json"))]
            originals=[j for path in candidates if path.exists() for j in load(path).get("judgments",[]) if j["trial_id"]==row["trial_id"]]
            if not any(all(j[k]==row[k] for k in ["expected_checks","critical_violations","notes"]) for j in originals):raise ValueError("Original judge output differs")
            trials.append({"trial_id":row["trial_id"],"status":trial["status"],"passed":row["passed"],"checks":[c["requirement"] for c in row["expected_checks"] if c["pass"] is True],"critical":row["critical_violations"]+critical,"errors":errors})
            reads[row["trial_id"]]=[c["arguments"]["path"] for c in calls if c["name"]=="read_skill_resource" and not c.get("error")]
            for call in calls:calls_total[call["name"]]=calls_total.get(call["name"],0)+1
            files+=[work/"trial.json",work/"answer.json",work/"input.txt",work/"command.json"]
            if (work/"calls.jsonl").exists():files.append(work/"calls.jsonl")
        files+=[root/f"{tag}.jsonl",root/f"summary-{tag}.json",root/tag/"grader.py",root/"harness/run_behavior_eval.py",root/"harness/mock_mcp.py"]
    models=set()
    for record in records:
        header=(root/record["trial_id"]/"stderr.txt").read_text(encoding="utf-8",errors="replace")
        match=re.search(r"^model:\s*(.+)$",header,re.M)
        if match:models.add(match[1])
    return {"source":root.relative_to(REPO).as_posix(),"cli":run["cli"],"models_observed":sorted(models),
            "execution_provenance":None if selection else {"mode":expected_mode,"discovery":expected_discovery,"runner_sha256":digest(root/"harness/run_behavior_eval.py")},
            "trials":sorted(trials,key=lambda r:r["trial_id"]),"latency":latency(records),"resource_reads":reads,"tool_calls":calls_total,
            "budget_checks":"B11 at most two edits; applicable per-task queries at most three; actual traces checked" if not selection else "not applicable",
            "raw_sha256":{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}}


def export_raw(args):
    roots={name:bounded_run(getattr(args,name)) for name in ["selection","behavior","explicit","native_implicit","native_negative","native_explicit"]}
    discovery_path=bounded_run(args.discovery_report)
    data={"schema":2,"fingerprint_encoding":"UTF-8 LF","scope":"Local mock-image model evidence; native CLI discovery is tested separately from catalog-only routing. CI checks consistency, not model replay.",
          "baseline_git_sha":"262f4772f140a60ef9e61ac6f5bcc7385d1eafbc","baseline_evidence_sha256":digest(REPO/"evals/baseline-evidence.json"),
          "fingerprints":fingerprints(),"batches":{name:export_batch(root,name,args.grade_tag) for name,root in roots.items()},
          "token_usage":{"input":None,"output":None,"cached_input":None,"reason":"Legacy text CLI logs do not provide a verified per-category usage contract; no token-saving claim"},
          "writing_metrics":check.skill_metrics(runner.SKILL),"host_discovery":load(discovery_path)}
    validate(data)
    PUBLIC.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export",action="store_true",help="Audit private fixed raw batches and write evals/evidence.json")
    parser.add_argument("--grade-tag",default="grades",help="Shared completed grading tag for behavior/native batches")
    parser.add_argument("--discovery-report",help="Target-only native skills/list report; required with --export")
    for name in ["selection","behavior","explicit","native-implicit","native-negative","native-explicit"]:
        parser.add_argument("--"+name,help="Private complete run directory; required with --export")
    args=parser.parse_args()
    if not args.grade_tag.replace("-","").isalnum():parser.error("Invalid grading tag")
    try:
        if args.export:
            if any(getattr(args,name) is None for name in ["selection","behavior","explicit","native_implicit","native_negative","native_explicit","discovery_report"]):parser.error("--export requires six raw runs and --discovery-report")
            export_raw(args)
        data=validate(load(PUBLIC))
        print("PASS: "+"; ".join(f"{name} {sum(r['passed'] for r in batch['trials'])}/{len(batch['trials'])}" for name,batch in data["batches"].items())+"; fingerprints match")
        print(json.dumps(selection_quality(data)))
        print("Scope: evidence consistency, not a CI model replay")
        return 0
    except (OSError,ValueError,KeyError,TypeError,StopIteration) as error:
        print(f"FAIL: {error}")
        return 1


if __name__=="__main__":
    raise SystemExit(main())
