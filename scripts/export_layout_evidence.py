"""Audit complete local native path-migration trials; preserve v0.1.0 evidence.

No model or image calls. Writes only evals/layout-evidence.json after validation.
JSON stdout; errors stderr; exit 0/1/2. Raw paths must be inside .eval-runs.
"""
import argparse
import json
import sys

import audit_evidence as audit
import check
import layout_migration as migration


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",required=True);parser.add_argument("--discovery",required=True)
    parser.add_argument("--tag",default="layout")
    args=parser.parse_args()
    if not args.tag.replace("-","").isalnum():parser.error("Invalid tag")
    try:
        current=audit.fingerprints();migration.legacy_context(audit.load(audit.PUBLIC),current)
        root=audit.bounded_run(args.run);discovery=audit.bounded_run(args.discovery)
        proof={"schema":1,"baseline_source":migration.SOURCE,"path_mapping":migration.PATHS,
               "legacy_evidence_sha256":migration.sha(migration.git_text("evals/evidence.json")),
               "current_fingerprints":current,"writing_metrics":check.skill_metrics(audit.runner.SKILL),
               "scope":"Path-only migration. Full v0.1.0 results reused as immutable history; only S01/B11/B12 x3 are freshly rerun with native discovery and offline image doubles.",
               "host_discovery":audit.load(discovery),"native_smoke":audit.export_batch(root,"native_layout",args.tag)}
        definitions={c["id"]:c for c in audit.load(audit.REPO/"evals/cases.json")["cases"]}
        migration.validate_native(proof,current,check.skill_metrics(audit.runner.SKILL),definitions)
        migration.PROOF.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
        audit.validate(audit.load(audit.PUBLIC))
        print(json.dumps({"passed":True,"native_runs":9,"legacy_evidence_preserved":True,"real_image_provider_calls":0}))
        return 0
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(f"FAIL: {error}",file=sys.stderr);return 1


if __name__=="__main__":raise SystemExit(main())
