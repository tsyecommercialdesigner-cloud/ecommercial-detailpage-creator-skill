"""Run fresh model trials with offline MCP; no real drawing tools are exposed."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[1]
SKILL=REPO/".agents/skills/ecommerce-detailpage-creator"
DISABLED=["apps","plugins","hooks","image_generation","browser_use","browser_use_external","computer_use","shell_tool","unified_exec","multi_agent","memories","code_mode","workspace_dependencies","in_app_browser","skill_mcp_dependency_install"]
SCHEMA={"type":"object","properties":{"selection":{"type":"string","enum":["yes","no","clarify"]},"reply":{"type":"string"},"record":{"type":"string"}},"required":["selection","reply","record"],"additionalProperties":False}


def command(work, schema, answer):
    cmd=[shutil.which("codex") or "codex","exec","--ignore-user-config","--ephemeral","--skip-git-repo-check","--sandbox","read-only","-C",str(work),"--color","never","--output-schema",str(schema),"-o",str(answer)]
    for feature in DISABLED: cmd += ["-c",f"features.{feature}=false"]
    return cmd+["-c","features.skip_host_skill_discovery=true","-c",'web_search="disabled"',"-"]


def load_mock(path):
    spec=importlib.util.spec_from_file_location("detailpage_mock",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_trial(root,case,repeat,timeout,mode):
    trial_id=f"{case['id']}-r{repeat}"
    work=root/trial_id
    work.mkdir(exist_ok=False)
    mock=load_mock(root/"harness/mock_mcp.py")
    mock.seed(work,case["id"])
    (work/"schema.json").write_text(json.dumps(SCHEMA),encoding="utf-8")
    body=(root/"skill/SKILL.md").read_text(encoding="utf-8")
    description=re.search(r"^description: (.*)$",body,re.M)[1]
    catalog=[{"name":"single-product-image-editor","description":"编辑单张商品主图、SKU白底图、背景或局部修图。"},{"name":"ecommerce-detailpage-creator","description":description},{"name":"storefront-site-builder","description":"开发有商品详情、购物车等页面的购物网站，交付可运行代码。"}]
    # Rotate the catalog without changing the requested task or giving the oracle.
    catalog=catalog[repeat%3:]+catalog[:repeat%3]
    prompt="""你正在处理隔离模拟宿主中的用户任务。唯一可用工具为eval_lab本地替身，无网络、无收费；图像是合成测试资料，不能称真实供应商作品。不要调用外部工具或尝试安装能力。
按目录判断适用技能；适用时通过read_skill_resource读取SKILL.md并按条件读取引用资料。相邻技能只有目录描述，用于路由，本轮不要求实现相邻任务。目标不清时可澄清。不要把执行目标不明等同于某技能必定不适用。
read_input可取得用户附件、参数、已确认历史方案及任务台账；图片可以用inspect_images实际查看。工具参数的相对路径从本试验工作区解析。需要留存过程时使用save_record。若本轮资料和授权足够，实际调用可执行的模拟工具；需要用户补充则交付当前能完成的具体内容后提出问题。最终JSON的reply是给用户的完整答复，record是本次实际保存或交付的事实/映射/方案/状态，不要只复述规则。
可用技能目录：
"""+json.dumps(catalog,ensure_ascii=False)
    if mode=="explicit": prompt+="\n用户显式指定使用 $ecommerce-detailpage-creator。"
    prompt+="\n用户当前请求：\n"+case["request"]
    (work/"input.txt").write_text(prompt,encoding="utf-8")
    cmd=command(work,work/"schema.json",work/"answer.json")
    overrides=[]
    for key,value in {"command":sys.executable,"args":[str(root/"harness/mock_mcp.py"),str(work),str(root/"skill"),case["id"]],"startup_timeout_sec":25,"tool_timeout_sec":30,"default_tools_approval_mode":"approve"}.items():
        overrides += ["-c",f"mcp_servers.eval_lab.{key}="+json.dumps(value)]
    cmd[-1:-1]=overrides
    (work/"command.json").write_text(json.dumps(cmd,ensure_ascii=False,indent=2),encoding="utf-8")
    started=time.time()
    with (work/"stdout.txt").open("w",encoding="utf-8") as out,(work/"stderr.txt").open("w",encoding="utf-8") as err:
        try:
            result=subprocess.run(cmd,input=prompt,text=True,encoding="utf-8",stdout=out,stderr=err,timeout=timeout,env={**os.environ,"PYTHONUTF8":"1","PYTHONDONTWRITEBYTECODE":"1"})
            status="completed" if result.returncode==0 and (work/"answer.json").exists() else "infrastructure_error"
            exit_code=result.returncode
        except subprocess.TimeoutExpired:
            status="timeout"
            exit_code=None
    header=(work/"stderr.txt").read_text(encoding="utf-8",errors="replace")
    model=re.search(r"^model:\s*(.+)$",header,re.M)
    row={"trial_id":trial_id,"case_id":case["id"],"repeat":repeat,"mode":mode,"status":status,"exit_code":exit_code,"seconds":round(time.time()-started,2),"model":model[1] if model else "unavailable","real_image_provider_calls":0}
    if status=="completed":
        try: row["answer"]=json.loads((work/"answer.json").read_text(encoding="utf-8"))
        except ValueError: row["status"]="invalid_answer"
    (work/"trial.json").write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding="utf-8")
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--cases",default="all")
    parser.add_argument("--repeats",type=int,default=3)
    parser.add_argument("--workers",type=int,default=3)
    parser.add_argument("--timeout",type=int,default=240)
    parser.add_argument("--mode",choices=["implicit","explicit"],default="implicit")
    args=parser.parse_args()
    root=args.output.resolve()
    if not root.is_relative_to((REPO/".eval-runs").resolve()) or root==(REPO/".eval-runs").resolve(): parser.error("Output must be a NEW child of .eval-runs")
    if args.repeats<1 or not 1<=args.workers<=4: parser.error("Invalid repeats/workers")
    cases=json.loads((REPO/"evals/cases.json").read_text(encoding="utf-8"))["cases"]
    if args.cases!="all":
        requested=set(args.cases.split(","))
        cases=[c for c in cases if c["id"] in requested]
        if len(cases)!=len(requested): parser.error("Unknown case")
    root.mkdir(parents=True,exist_ok=False)
    shutil.copytree(SKILL,root/"skill")
    (root/"harness").mkdir()
    for source in [REPO/"evals/mock_mcp.py",REPO/"evals/cases.json",Path(__file__)]: shutil.copyfile(source,root/"harness"/source.name)
    manifest={str(p.relative_to(root/"skill")).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/"skill").rglob("*")) if p.is_file()}
    (root/"skill-manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    info={"rubric_version":"1","cases":[c["id"] for c in cases],"repeats":args.repeats,"mode":args.mode,"python":sys.version,"cli":subprocess.check_output([shutil.which("codex"),"--version"],text=True).strip(),"model_selection":"CLI default; no model override","disabled":DISABLED,"networked_image_tools_loaded":False,"harness_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/"harness").iterdir()}}
    (root/"run.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf-8")
    rows=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending=[pool.submit(run_trial,root,case,r,args.timeout,args.mode) for r in range(1,args.repeats+1) for case in cases]
        for future in as_completed(pending):
            row=future.result()
            rows.append(row)
            with (root/"trials.jsonl").open("a",encoding="utf-8") as output: output.write(json.dumps(row,ensure_ascii=False)+"\n")
            print(json.dumps({k:row[k] for k in ["trial_id","status","seconds","model"]},ensure_ascii=False),flush=True)
    return int(any(row["status"]!="completed" for row in rows))


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
