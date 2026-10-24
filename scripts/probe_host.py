"""Codex CLI native skills/list probe; no model call, login or user config edit.

Writes a minimal target-only report in a NEW .eval-runs child. Temporary app
server home is owned by this call and removed even on failure. JSON stdout;
diagnostics stderr; exit 0 success, 1 failure, 2 invalid CLI arguments.
"""
import argparse
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import check


def probe(area):
    executable=shutil.which("codex")
    if executable is None:raise ValueError("Codex CLI unavailable; no automatic installation")
    started=time.monotonic()
    with tempfile.TemporaryDirectory(dir=area,prefix="host-home-") as home,(area/"stderr.txt").open("w",encoding="utf-8") as error_log:
        process=subprocess.Popen([executable,"app-server"],cwd=check.REPO,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=error_log,
                                 text=True,encoding="utf-8",env={**os.environ,"CODEX_HOME":home,"PYTHONUTF8":"1"})
        events=queue.Queue()
        def read():
            try:
                for line in process.stdout:events.put(json.loads(line))
            except (ValueError,OSError) as error:events.put({"reader_error":str(error)})
        reader=threading.Thread(target=read,daemon=True);reader.start()
        def send(value):
            process.stdin.write(json.dumps(value)+"\n");process.stdin.flush()
        def receive(identifier):
            while True:
                remaining=30-(time.monotonic()-started)
                if remaining<=0:raise TimeoutError("Native discovery exceeded 30 seconds")
                event=events.get(timeout=remaining)
                if "reader_error" in event:raise ValueError("Invalid app-server JSON output")
                if event.get("id")==identifier:
                    if "error" in event:raise ValueError(f"skills/list protocol error: {event['error'].get('code')}")
                    return event["result"]
        try:
            send({"id":1,"method":"initialize","params":{"clientInfo":{"name":"detailpage_native_probe","version":"1"},"capabilities":{"experimentalApi":True}}});receive(1)
            send({"method":"initialized","params":{}})
            send({"id":2,"method":"skills/list","params":{"cwds":[str(check.REPO)],"forceReload":True}})
            data=receive(2)["data"]
            matches=[skill for row in data for skill in row["skills"] if skill["name"]==check.SKILL.name]
            if len(matches)!=1:raise ValueError("Expected exactly one native target skill")
            entry=matches[0]
            if not entry.get("enabled") or Path(entry["path"]).resolve()!=check.SKILL.joinpath("SKILL.md").resolve():raise ValueError("Native source differs or is disabled")
            if entry["description"]!=check.read_metadata(check.SKILL/"SKILL.md")["description"]:raise ValueError("Native description differs")
            if any(row.get("errors") for row in data):raise ValueError("Native discovery reported parse errors; inspect local stderr")
            result={"host":subprocess.check_output([executable,"--version"],text=True,timeout=10).strip(),"name":entry["name"],
                    "description":entry["description"],"path":check.SKILL.relative_to(check.REPO).as_posix()+"/SKILL.md",
                    "scope":entry.get("scope"),"enabled":True,"errors":[],"method":"skills/list; forceReload=true; isolated CODEX_HOME; no model call"}
            (area/"discovery.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            return result
        finally:
            try:process.stdin.close()
            except OSError:pass
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            reader.join(timeout=2)
            process.stdout.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    area=args.output.resolve();boundary=(check.REPO/".eval-runs").resolve()
    if area==boundary or not area.is_relative_to(boundary):parser.error("Output must be a new child of .eval-runs")
    try:
        area.mkdir(parents=True,exist_ok=False)
        print(json.dumps(probe(area),ensure_ascii=False))
        return 0
    except (OSError,ValueError,KeyError,queue.Empty,subprocess.SubprocessError) as error:
        print(f"FAIL: native discovery: {error}; partial evidence: {area}",file=sys.stderr)
        return 1


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8");sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
