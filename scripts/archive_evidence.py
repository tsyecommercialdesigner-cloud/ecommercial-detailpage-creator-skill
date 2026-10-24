"""Archive one closed evaluation directory, verify every byte, then report JSON.

No deletion of the original directory. --verify checks an existing bundle and
its manifest. Inputs/outputs must remain inside .eval-runs. This is local
evidence storage, not a Skill release or a permission to publish raw traces.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

REPO=Path(__file__).resolve().parents[1]


def sha(path):
    with path.open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()


def owned(path):
    resolved=path.resolve();area=(REPO/".eval-runs").resolve()
    if resolved==area or not resolved.is_relative_to(area):raise ValueError("Path must be a child of workspace .eval-runs")
    return resolved


def snapshot(root):
    files={}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or getattr(path,"is_junction",lambda:False)():raise ValueError("Linked evidence is not archived")
        relative=path.relative_to(root)
        if any(part in {".git","__pycache__",".venv"} for part in relative.parts):continue
        if path.is_file():files[relative.as_posix()]={"sha256":sha(path),"bytes":path.stat().st_size}
    if not files:raise ValueError("No evidence files")
    return files


def verify(bundle,manifest):
    if sha(bundle)!=manifest["bundle_sha256"]:raise ValueError("Archive SHA256 differs")
    with zipfile.ZipFile(bundle) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)) or set(names)!=set(manifest["files"]):raise ValueError("Archive members differ")
        for name,expected in manifest["files"].items():
            if Path(name).is_absolute() or Path(name).drive or ":" in name or ".." in Path(name).parts or "\\" in name:raise ValueError("Unsafe archive member")
            with archive.open(name) as stream:
                if hashlib.file_digest(stream,"sha256").hexdigest()!=expected["sha256"]:raise ValueError("Archived content differs")
            if archive.getinfo(name).file_size!=expected["bytes"]:raise ValueError("Archived size differs")
    return {"files":len(names),"verified":True,"bundle_sha256":manifest["bundle_sha256"]}


def build(root,bundle):
    root=owned(root);bundle=owned(bundle)
    if bundle.is_relative_to(root):raise ValueError("Archive output must be outside its input directory")
    manifest_path=bundle.with_suffix(".manifest.json");partial=bundle.with_suffix(".partial.zip")
    if any(p.exists() for p in [bundle,manifest_path,partial]):raise ValueError("Archive output already exists; never overwrite")
    files=snapshot(root)
    bundle.parent.mkdir(parents=True,exist_ok=True)
    partial_owned=False
    try:
        stream=partial.open("xb")
        partial_owned=True
        with stream,zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_DEFLATED) as archive:
            for name in files:archive.write(root/name,arcname=name)
        manifest={"schema":1,"source_directory":root.relative_to(REPO).as_posix(),"files":files,"bundle_sha256":sha(partial),"excluded":[".git","__pycache__",".venv"]}
        result=verify(partial,manifest)
        if snapshot(root)!=files:raise ValueError("Evidence changed during archiving; stop writers before retry")
        # Windows same-volume rename refuses an existing destination.
        partial.rename(bundle)
        with manifest_path.open("x",encoding="utf-8",newline="\n") as out:json.dump(manifest,out,ensure_ascii=False,indent=2)
        return result
    finally:
        if partial_owned and partial.exists():partial.unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--verify",action="store_true")
    args=parser.parse_args()
    if args.verify==bool(args.run):parser.error("Use either --run or --verify")
    try:
        bundle=owned(args.output)
        result=verify(bundle,json.loads(bundle.with_suffix(".manifest.json").read_text(encoding="utf-8"))) if args.verify else build(args.run,bundle)
        print(json.dumps(result))
        return 0
    except (OSError,ValueError,KeyError,zipfile.BadZipFile) as error:
        print(f"FAIL: {error}; source directory was not removed",file=sys.stderr)
        return 1


if __name__=="__main__":raise SystemExit(main())
