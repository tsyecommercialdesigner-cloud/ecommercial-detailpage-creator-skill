"""Read-only GitHub release gate. Uses existing gh authentication; no mutations.

Require exact main/dev refs, passing branch push runs and automated review.
No model calls. JSON stdout, errors stderr; exits 0/1/2.
"""
import argparse
import json
import re
import subprocess
import sys

REPOSITORY="tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill"


def api(path):
    return json.loads(subprocess.check_output(["gh","api",f"repos/{REPOSITORY}/{path}"],text=True,encoding="utf-8",timeout=30))


def check(commit,version=None):
    if not re.fullmatch("[0-9a-f]{40}",commit):raise ValueError("Full SHA required")
    for branch in ("main","dev"):
        if api(f"git/ref/heads/{branch}")["object"]["sha"]!=commit:raise ValueError(f"{branch} differs")
        runs=api(f"actions/workflows/checks.yml/runs?branch={branch}&event=push&head_sha={commit}&per_page=100")["workflow_runs"]
        latest=max(runs,key=lambda row:row["id"]) if runs else None
        if not latest or latest["head_sha"]!=commit or latest["conclusion"]!="success":raise ValueError(f"Latest {branch} push CI not successful")
    statuses=api(f"commits/{commit}/status")["statuses"]
    reviews=[s for s in statuses if s["context"]=="automated-review"]
    if not reviews or reviews[0]["state"]!="success":raise ValueError("Automated review not successful")
    if version is not None:
        if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+",version):raise ValueError("Invalid version")
        if any(row["ref"]==f"refs/tags/{version}" for row in api(f"git/matching-refs/tags/{version}")):raise ValueError("Version tag already exists")
        page=1
        while True:
            releases=api(f"releases?per_page=100&page={page}")
            if any(row["tag_name"]==version for row in releases):raise ValueError("Version release already exists; recover by release ID")
            if len(releases)<100:break
            page+=1
    return {"passed":True,"source_commit":commit,"branches":["main","dev"],"checks":["repository-checks","automated-review"]}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--sha",required=True);parser.add_argument("--version");args=parser.parse_args()
    try:print(json.dumps(check(args.sha,args.version)));return 0
    except (ValueError,KeyError,OSError,subprocess.SubprocessError) as error:print(f"FAIL: {error}",file=sys.stderr);return 1


if __name__=="__main__":raise SystemExit(main())
