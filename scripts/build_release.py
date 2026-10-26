"""Build an immutable four-file Skill ZIP from Git objects, never workspace files.

Developer-only; Python standard library. New output directory under .eval-runs.
stdout JSON; exit 0 success, 1 failure, 2 invalid CLI. No publishing or installing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

REPO=Path(__file__).resolve().parents[1]
NAME="ecommerce-detailpage-creator"
PREFIX=f".agents/skills/{NAME}/"
FILES=["SKILL.md","templates/design-record-template.md","references/deliverables.md","references/workflow.md"]


def git(*args):
    return subprocess.check_output(["git",*args],cwd=REPO,timeout=30)


def sha(data):return hashlib.sha256(data).hexdigest()


def build(commit,version,output):
    if not re.fullmatch(r"[0-9a-f]{40}",commit):raise ValueError("Use a full lowercase commit SHA")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+",version):raise ValueError("Use vMAJOR.MINOR.PATCH")
    if git("rev-parse",f"{commit}^{{commit}}").decode().strip()!=commit:raise ValueError("Commit differs")
    output=output.resolve();area=(REPO/".eval-runs").resolve()
    if output==area or not output.is_relative_to(area):raise ValueError("Output must be a new .eval-runs child")
    listed=git("ls-tree","-r","--name-only",commit,"--",PREFIX).decode().splitlines()
    if set(listed)!={PREFIX+f for f in FILES}:raise ValueError("Git Skill inventory differs from reviewed release allowlist")
    modes=git("ls-tree","-r",commit,"--",PREFIX).decode().splitlines()
    if any(not row.startswith("100644 blob ") for row in modes):raise ValueError("Only regular non-executable Skill files are released")
    data={f:git("show",f"{commit}:{PREFIX}{f}") for f in FILES}
    installer=git("show",f"{commit}:delivery/Manage-Skill.ps1")
    output.mkdir(parents=True,exist_ok=False)
    bundle=output/f"{NAME}-{version}.zip"
    with zipfile.ZipFile(bundle,"x",compression=zipfile.ZIP_DEFLATED) as archive:
        for name,content in data.items():
            info=zipfile.ZipInfo(f"{NAME}/{name}",date_time=(2026,1,1,0,0,0))
            info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,content)
    manifest={"schema":1,"name":NAME,"version":version,"source_commit":commit,"repository":"https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill",
              "zip":bundle.name,"zip_sha256":sha(bundle.read_bytes()),"files":{name:{"sha256":sha(content),"bytes":len(content)} for name,content in data.items()},
              "compatibility":"Windows; Codex CLI 0.163.0; mock image service only; other Hosts and real image providers unverified"}
    (output/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (output/"Manage-Skill.ps1").write_bytes(installer)
    assets=[bundle.name,"manifest.json","Manage-Skill.ps1"]
    sums="".join(f"{sha((output/name).read_bytes())}  {name}\n" for name in assets)
    (output/"SHA256SUMS.txt").write_text(sums,encoding="utf-8")
    (output/"release-notes.md").write_text(f"# {version}\n\n来源提交：`{commit}`。\n\n从本 Release 的 Assets 下载 ZIP、manifest.json、SHA256SUMS.txt、Manage-Skill.ps1；Source code 是开发源码。安装工具仅复制完整四文件包；普通成员无需 Python、uv 或 MCP Server。\n\nWindows / Codex CLI 0.163.0 已做原生发现及模拟业务验证。本次仅将 reference/ 调整为 references/、模板迁至 templates/；业务指令及资源内容经显式路径映射逐字比对不变。v0.1.0 的完整行为 48/48 与既有失败记录保持原样；本次原生 S01/B11/B12 各三次的目录回归另有独立证据，未冒称重新执行完整 48 条；未调用真实收费绘图，未认证其他 Host、商业视觉质量或成员生产环境。\n\n升级先保留旧完整包和版本，选择空的目标路径安装新包，验证发现与行为后切换；拒绝覆盖和静默修复。脚本不会修改宿主配置。MANUAL.md 将在发布后补充。\n\n下载后从这里取得可信摘要，先核对安装脚本，再执行它；摘要不能由待验证下载自行证明：\n\n```text\n{sums}```\n\nVerify/Install 需显式传入本页 manifest.json 的 SHA256。Check 检查漂移；Uninstall 仅删除完全匹配清单且无新增文件的 Skill。所有操作失败停止，保留已有用户文件。\n",encoding="utf-8")
    return {"version":version,"source_commit":commit,"files":4,"manifest_sha256":sha((output/"manifest.json").read_bytes()),"assets":[*assets,"SHA256SUMS.txt"]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha",required=True);parser.add_argument("--version",required=True);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    try:print(json.dumps(build(args.sha,args.version,args.output)));return 0
    except (OSError,ValueError,subprocess.SubprocessError,zipfile.BadZipFile) as error:print(f"FAIL: {error}",file=sys.stderr);return 1


if __name__=="__main__":raise SystemExit(main())
