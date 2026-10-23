"""Verify a sanitized local-evaluation attestation; never runs model/image APIs.

Default checks version fingerprints and complete result identities on a clean
checkout. --export re-audits the private raw batches and writes the public copy.
This is maintainer evidence, not a signature or an automatic model replay.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

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
    paths=[*runner.SKILL.rglob("*.md"), REPO/"evals/cases.json",
           REPO/"evals/mock_mcp.py", REPO/"scripts/run_behavior_eval.py",
           REPO/"scripts/run_selection_eval.py", REPO/"evals/RUBRIC.md",
           REPO/"pyproject.toml", REPO/"uv.lock", REPO/"scripts/grade_behavior_eval.py"]
    return {p.relative_to(REPO).as_posix():digest(p) for p in sorted(paths)}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(data):
    if data["schema"]!=1 or data["fingerprint_encoding"]!="UTF-8 LF":
        raise ValueError("Unknown attestation schema/encoding")
    if data["fingerprints"]!=fingerprints():
        raise ValueError("Evaluated inputs or maintenance dependencies changed; re-audit evidence")
    definitions={c["id"]:c for c in load(REPO/"evals/cases.json")["cases"]}
    for name in ("selection","behavior","explicit"):
        batch=data["batches"][name]
        cases=["B07"] if name=="explicit" else list(definitions)
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
    return data


def export_raw():
    batches={}
    for name,folder in [("selection","selection-v2"),("behavior","final-v3"),("explicit","explicit-v3")]:
        root=REPO/".eval-runs"/folder
        run=load(root/"run.json")
        files=[root/"run.json"]
        for path in runner.SKILL.rglob("*.md"):
            frozen=root/"skill"/path.relative_to(runner.SKILL)
            if name=="selection":
                if path.name=="SKILL.md" and check.read_metadata(path)["description"]!=yaml.safe_load(frozen.read_text(encoding="utf-8").split("---",2)[1])["description"]:
                    raise ValueError("Selected description differs")
            elif digest(path)!=digest(frozen): raise ValueError("Behavior skill snapshot differs")
        casefile=root/("cases.json" if name=="selection" else "harness/cases.json")
        if digest(casefile)!=digest(REPO/"evals/cases.json"): raise ValueError("Case snapshot differs")
        sources={"selection-runner.py":"scripts/run_selection_eval.py","command-runner.py":"scripts/run_behavior_eval.py"} if name=="selection" else {"harness/mock_mcp.py":"evals/mock_mcp.py","harness/run_behavior_eval.py":"scripts/run_behavior_eval.py"}
        for frozen,current in sources.items():
            if digest(root/frozen)!=digest(REPO/current): raise ValueError("Subject harness differs")
        trials=[]
        if name=="selection":
            raw=[json.loads(line) for line in (root/"trials.jsonl").read_text(encoding="utf-8").splitlines()]
            for row in raw:
                if row!=load(root/row["trial_id"]/"trial.json"): raise ValueError("Selection trace mismatch")
                trials.append({"trial_id":row["trial_id"],"status":row["status"],"passed":row["passed"],"selected_skill":row["answer"]["selected_skill"]})
            files+=[root/"trials.jsonl",root/"summary.json"]
        else:
            raw=[json.loads(line) for line in (root/"grades.jsonl").read_text(encoding="utf-8").splitlines()]
            summary=load(root/"summary-grades.json")
            oldhash=hashlib.sha256((root/"grades/grader.py").read_bytes()).hexdigest()
            if summary!=grader.summarize(raw,run,oldhash): raise ValueError("Old grading summary mismatch")
            for row in raw:
                work=root/row["trial_id"]
                trial=load(work/"trial.json")
                calls=[json.loads(line) for line in (work/"calls.jsonl").read_text(encoding="utf-8").splitlines()] if (work/"calls.jsonl").exists() else []
                case=next(c for c in load(casefile)["cases"] if c["id"]==row["case_id"])
                errors,critical=grader.mechanical(case,trial,calls)
                if errors!=row["mechanical_errors"] or critical!=row["mechanical_critical"]: raise ValueError("Mechanical recheck differs")
                original=next(j for j in load(root/"grades"/case["id"]/"answer.json")["judgments"] if j["trial_id"]==row["trial_id"])
                if any(original[k]!=row[k] for k in ["expected_checks","critical_violations","notes"]): raise ValueError("Judge output mismatch")
                trials.append({"trial_id":row["trial_id"],"status":trial["status"],"passed":row["passed"],"checks":[c["requirement"] for c in row["expected_checks"] if c["pass"] is True],"critical":row["critical_violations"]+critical,"errors":errors})
            files+=[root/"grades.jsonl",root/"summary-grades.json",root/"grades/grader.py"]
        batches[name]={"source":folder,"cli":run["cli"],"model":"gpt-6.1-sol (CLI default)","trials":sorted(trials,key=lambda r:r["trial_id"]),"raw_sha256":{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    # Dependency update must preserve every seeded image seen by the subject.
    mock=runner.load_mock(REPO/"evals/mock_mcp.py")
    from PIL import Image, ImageChops
    count=0
    with tempfile.TemporaryDirectory(prefix="detailpage-equivalence-") as temp:
        for case in load(REPO/"evals/cases.json")["cases"]:
            work=Path(temp)/case["id"]
            mock.seed(work,case["id"])
            old=REPO/".eval-runs/final-v3"/f"{case['id']}-r1"
            for image in work.rglob("*.png"):
                with Image.open(image) as actual,Image.open(old/image.relative_to(work)) as expected:
                    if actual.size!=expected.size or ImageChops.difference(actual.convert("RGB"),expected.convert("RGB")).getbbox(): raise ValueError("Fixture pixels changed after dependency upgrade")
                count+=1
    data={"schema":1,"fingerprint_encoding":"UTF-8 LF","scope":"Maintainer attestation of local model trials with mock image tools; CI verifies consistency only, not model replay or commercial image quality.","fingerprints":fingerprints(),"original_environment":{"python":"3.14.7","PyYAML":"6.0.3","Pillow":"12.0.0","codex":"0.163.0"},"dependency_recheck":{"Pillow":"13.0.0","identical_seeded_images":count},"batches":batches}
    validate(data)
    PUBLIC.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export",action="store_true",help="Audit private fixed raw batches and write evals/evidence.json")
    args=parser.parse_args()
    try:
        if args.export: export_raw()
        data=validate(load(PUBLIC))
        print("PASS: attested selection 48/48, behavior 48/48, explicit 3/3; fingerprints match")
        print("Scope: evidence consistency, not a CI model replay")
        return 0
    except (OSError,ValueError,KeyError,TypeError,StopIteration) as error:
        print(f"FAIL: {error}")
        return 1


if __name__=="__main__":
    raise SystemExit(main())
