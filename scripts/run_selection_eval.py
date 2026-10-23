"""Catalog-only fresh model trials: no skill body, MCP, images or execution tools."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import yaml
import run_behavior_eval as runner

TARGET="ecommerce-detailpage-creator"
SCHEMA={"type":"object","properties":{"selected_skill":{"type":"string","enum":[TARGET,"single-product-image-editor","storefront-site-builder","clarify"]},"reason":{"type":"string"}},"required":["selected_skill","reason"],"additionalProperties":False}


def trial(root,case,repeat,description,timeout):
    work=root/f"{case['id']}-r{repeat}"
    work.mkdir()
    catalog=[{"name":TARGET,"description":description},{"name":"single-product-image-editor","description":"编辑单张商品主图、SKU白底图、背景或独立图片的局部修复。"},{"name":"storefront-site-builder","description":"开发商品详情、购物车等电商网站页面，交付可运行代码。"}]
    catalog=catalog[repeat%3:]+catalog[:repeat%3]
    prompt="""仅做技能路由，不能执行用户任务。本轮没有任何工具，也不提供技能正文。根据下列技能名称和描述，选择最适合当前任务的技能；若用户用途尚不明确、不能判断单图还是多屏，则选择clarify。
选择只表达能力范围，不表达执行是否阻塞：缺参数、资料冲突、无工具或需要用户确认，不等同于技能不适用。完整多屏详情页的局部返修属于其上下文任务；独立单图编辑按单图能力路由。
不要假定目录中技能已经安装或可执行，只给选择与简短理由。
技能目录：
"""+json.dumps(catalog,ensure_ascii=False)+"\n用户已有的任务上下文：\n"+case.get("selection_context","无额外历史上下文")+"\n用户请求：\n"+case["request"]
    (work/"input.txt").write_text(prompt,encoding="utf-8")
    (work/"schema.json").write_text(json.dumps(SCHEMA),encoding="utf-8")
    cmd=runner.command(work,work/"schema.json",work/"answer.json")
    (work/"command.json").write_text(json.dumps(cmd,ensure_ascii=False,indent=2),encoding="utf-8")
    started=time.time()
    with (work/"stdout.txt").open("w",encoding="utf-8") as out,(work/"stderr.txt").open("w",encoding="utf-8") as err:
        try:
            result=subprocess.run(cmd,input=prompt,text=True,encoding="utf-8",stdout=out,stderr=err,timeout=timeout,env={**os.environ,"PYTHONUTF8":"1"})
            status="completed" if result.returncode==0 and (work/"answer.json").exists() else "infrastructure_error"
        except subprocess.TimeoutExpired:
            status="timeout"
    answer=json.loads((work/"answer.json").read_text(encoding="utf-8")) if status=="completed" else {}
    expected=TARGET if case["expected_selection"]=="yes" else "clarify" if case["expected_selection"]=="clarify" else "single-product-image-editor" if case["id"]=="S02" else "storefront-site-builder"
    row={"trial_id":work.name,"case_id":case["id"],"repeat":repeat,"status":status,"expected":expected,"answer":answer,"passed":status=="completed" and answer["selected_skill"]==expected,"seconds":round(time.time()-started,2),"mcp_servers_loaded":0,"skill_bodies_exposed":0}
    (work/"trial.json").write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding="utf-8")
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--workers",type=int,default=4)
    parser.add_argument("--timeout",type=int,default=180)
    args=parser.parse_args()
    root=args.output.resolve()
    if not root.is_relative_to((runner.REPO/".eval-runs").resolve()) or root==(runner.REPO/".eval-runs").resolve(): parser.error("Output must be a new child of .eval-runs")
    if not 1<=args.workers<=4: parser.error("workers must be 1..4")
    root.mkdir(parents=True,exist_ok=False)
    shutil.copytree(runner.SKILL,root/"skill")
    text=(root/"skill/SKILL.md").read_text(encoding="utf-8")
    description=yaml.safe_load(text.split("---",2)[1])["description"]
    shutil.copyfile(runner.REPO/"evals/cases.json",root/"cases.json")
    shutil.copyfile(Path(__file__),root/"selection-runner.py")
    shutil.copyfile(runner.REPO/"scripts/run_behavior_eval.py",root/"command-runner.py")
    cases=json.loads((root/"cases.json").read_text(encoding="utf-8"))["cases"]
    metadata={"kind":"catalog-only-selection","cases":[c["id"] for c in cases],"repeats":3,"cli":subprocess.check_output([shutil.which("codex"),"--version"],text=True).strip(),"model_selection":"CLI default, no override","body_exposed":False,"mcp_servers":[],"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (root/"run.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    rows=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(trial,root,case,repeat,description,args.timeout) for repeat in range(1,4) for case in cases]
        for future in as_completed(futures):
            row=future.result()
            rows.append(row)
            with (root/"trials.jsonl").open("a",encoding="utf-8") as out: out.write(json.dumps(row,ensure_ascii=False)+"\n")
            print(json.dumps({k:row[k] for k in ["trial_id","status","passed"]}),flush=True)
    summary={"expected":len(cases)*3,"completed":len(rows),"passed":sum(r["passed"] for r in rows),"infrastructure_errors":sum(r["status"]!="completed" for r in rows),"per_case":{c["id"]:sum(r["passed"] for r in rows if r["case_id"]==c["id"]) for c in cases}}
    (root/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return int(summary["passed"]!=summary["expected"])


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
