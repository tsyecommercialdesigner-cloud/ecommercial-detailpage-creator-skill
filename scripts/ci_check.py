"""Run bounded deterministic checks and preserve safe logs under .eval-runs/ci.

No model or image-provider calls. OSV receives public locked package versions.
stdout is one JSON summary; child logs are files. Exit 0 pass, 1 fail.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[1]
COMMANDS={"structure":["scripts/check.py"],"unit":["-m","unittest","discover","-s","tests","-v"],
          "evidence":["scripts/audit_evidence.py"],"security":["scripts/security_check.py"]}


def main():
    folder=REPO/".eval-runs/ci";folder.mkdir(parents=True,exist_ok=True)
    rows=[]
    for name,args in COMMANDS.items():
        started=time.monotonic();command=[sys.executable,"-X","utf8",*args]
        with (folder/f"{name}.txt").open("w",encoding="utf-8") as log:
            try:
                code=subprocess.run(command,cwd=REPO,stdout=log,stderr=subprocess.STDOUT,timeout=120).returncode
                status="passed" if code==0 else "failed"
            except subprocess.TimeoutExpired:code=None;status="timeout"
            except OSError as error:code=None;status="launch_error";log.write(str(error))
        rows.append({"check":name,"status":status,"exit_code":code,"seconds":round(time.monotonic()-started,2),"log":f"{name}.txt"})
    result={"schema":1,"passed":all(r["status"]=="passed" for r in rows),"checks":rows,"model_calls":0,"image_provider_calls":0}
    (folder/"summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result))
    return int(not result["passed"])


if __name__=="__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    raise SystemExit(main())
