"""Verify the v0.1.0 -> references/templates path-only migration.

Historical evidence remains byte-for-byte in Git. It is reused only when every
evaluated input is unchanged after the explicit path substitutions below.
Fresh native smoke evidence is separate; CI never replays models or images.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import check

REPO=Path(__file__).resolve().parents[1]
SOURCE="533262ff2955702e1a646ed9d0b9df58dcfd5f1f"
PREFIX=".agents/skills/ecommerce-detailpage-creator/"
PATHS={"SKILL.md":"SKILL.md","reference/deliverables.md":"references/deliverables.md",
       "reference/workflow.md":"references/workflow.md","assets/design-record-template.md":"templates/design-record-template.md"}
PROOF=REPO/"evals/layout-evidence.json"


def normalized(text):return text.replace("\r\n","\n")
def sha(text):return hashlib.sha256(normalized(text).encode("utf-8")).hexdigest()
def git_text(path):
    return subprocess.check_output(["git","show",f"{SOURCE}:{path}"],cwd=REPO,text=True,encoding="utf-8",timeout=15)


def verify_path_only(current):
    baseline=json.loads(git_text("evals/evidence.json"))
    mapped={PREFIX+PATHS.get(key[len(PREFIX):],key[len(PREFIX):]) if key.startswith(PREFIX) else key for key in baseline["fingerprints"]}
    if set(current)!=mapped:raise ValueError("Migration evaluated-file inventory differs")
    for old,expected in baseline["fingerprints"].items():
        target=PREFIX+PATHS[old[len(PREFIX):]] if old.startswith(PREFIX) else old
        text=(REPO/target).read_text(encoding="utf-8")
        if sha(text)!=current[target]:raise ValueError("Current fingerprint differs from source")
        if old==PREFIX+"SKILL.md":
            for before,after in PATHS.items():
                if before!=after:text=text.replace(after,before)
        elif old=="evals/mock_mcp.py":
            text=text.replace("references/workflow.md","reference/workflow.md")
        original=git_text(old)
        if normalized(text)!=normalized(original) or sha(original)!=expected:
            raise ValueError(f"Not a path-only migration: {target}")
    return baseline


def legacy_context(data,current):
    baseline=verify_path_only(current)
    if data!=baseline:raise ValueError("Historical v0.1.0 evidence was modified")
    return baseline["fingerprints"],baseline["writing_metrics"]


def validate_native(proof,current,metrics,definitions):
    if proof.get("schema")!=1 or proof.get("baseline_source")!=SOURCE or proof.get("path_mapping")!=PATHS:
        raise ValueError("Unknown layout evidence identity")
    if proof.get("current_fingerprints")!=current or proof.get("writing_metrics")!=metrics:raise ValueError("Layout evidence source changed")
    if proof.get("legacy_evidence_sha256")!=sha(git_text("evals/evidence.json")):raise ValueError("Historical evidence identity differs")
    discovery=proof["host_discovery"]
    if (discovery["path"]!=PREFIX+"SKILL.md" or discovery["name"]!="ecommerce-detailpage-creator"
            or discovery["description"]!=check.read_metadata(REPO/PREFIX/"SKILL.md")["description"]
            or discovery["scope"]!="repo" or discovery["enabled"] is not True or discovery["errors"]):raise ValueError("Layout native discovery failed")
    batch=proof["native_smoke"]
    expected={f"{case}-r{r}" for case in ["S01","B11","B12"] for r in range(1,4)}
    rows=batch["trials"]
    if len(rows)!=9 or {r["trial_id"] for r in rows}!=expected:raise ValueError("Layout native smoke incomplete")
    if batch["execution_provenance"]!={"mode":"implicit","discovery":"native","runner_sha256":current["scripts/run_behavior_eval.py"]}:raise ValueError("Layout execution provenance differs")
    allowed={"SKILL.md",*PATHS.values()}
    for reads in batch["resource_reads"].values():
        if any(p not in allowed for p in reads):raise ValueError("Unexpected native resource read")
    for row in rows:
        case=definitions[row["trial_id"].rsplit("-r",1)[0]]
        if (row["status"]!="completed" or row["passed"] is not True or row["errors"] or row["critical"]
                or sorted(row["checks"])!=sorted(case["expected"])):raise ValueError("Layout native behavior failed")
    return True
