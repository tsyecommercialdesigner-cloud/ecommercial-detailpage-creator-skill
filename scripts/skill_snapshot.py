"""Record a candidate Skill snapshot or read-only verify an installed copy.

This never installs, overwrites, publishes or repairs a target. A matching
snapshot proves bytes/layout only, not CI, Host execution or release approval.
JSON stdout, diagnostics stderr; exit 0 pass, 1 failure, 2 invalid arguments.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import check


def inventory(root):
    if root.is_symlink() or getattr(root,"is_junction",lambda:False)():raise ValueError("Linked package root is not accepted by this copy verifier")
    check.read_metadata(root/"SKILL.md")
    errors=check.check_layout(root)
    for path in root.rglob("*.md"):errors.extend(check.check_links(path,root))
    if errors:raise ValueError("; ".join(errors))
    return {p.relative_to(root).as_posix():{"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"bytes":p.stat().st_size} for p in sorted(root.rglob("*")) if p.is_file()}


def compare(root,manifest):
    if manifest.get("schema")!=1 or manifest.get("name")!=check.SKILL.name:raise ValueError("Unsupported snapshot")
    if inventory(root)!=manifest["files"]:raise ValueError("Target drift detected; target was not changed")
    return {"matches":True,"files":len(manifest["files"]),"source_git_baseline":manifest["source_git_baseline"],"source_uncommitted":manifest["source_uncommitted"],"scope":"Bytes and layout only; no release/Host approval"}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--record",type=Path,help="Write NEW candidate manifest inside .eval-runs")
    actions.add_argument("--verify",type=Path,help="Read existing manifest")
    parser.add_argument("--target",type=Path,default=check.SKILL)
    args=parser.parse_args()
    try:
        if args.record:
            output=args.record.resolve();boundary=(check.REPO/".eval-runs").resolve()
            if output==boundary or not output.is_relative_to(boundary):parser.error("Manifest output must be in .eval-runs")
            if args.target.resolve()!=check.SKILL.resolve():parser.error("Record uses the repository Skill only")
            files=inventory(check.SKILL)
            dirty=subprocess.run(["git","diff","--quiet","HEAD","--",str(check.SKILL)],cwd=check.REPO,timeout=10).returncode
            if dirty not in {0,1}:raise ValueError("Cannot determine source Git state")
            untracked=subprocess.check_output(["git","ls-files","--others","--exclude-standard","--",str(check.SKILL)],cwd=check.REPO,timeout=10)
            manifest={"schema":1,"name":check.SKILL.name,"source_git_baseline":subprocess.check_output(["git","rev-parse","HEAD"],cwd=check.REPO,text=True,timeout=10).strip(),"source_uncommitted":bool(dirty or untracked),"files":files,"release_approval":"not_evaluated"}
            output.parent.mkdir(parents=True,exist_ok=True)
            with output.open("x",encoding="utf-8",newline="\n") as out:json.dump(manifest,out,indent=2)
        else:manifest=json.loads(args.verify.read_text(encoding="utf-8"))
        print(json.dumps(compare(args.target,manifest)))
        return 0
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        print(f"FAIL: {error}",file=sys.stderr);return 1


if __name__=="__main__":raise SystemExit(main())
