from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
import yaml
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"scripts"))
import archive_evidence as archive
import ci_check
import run_behavior_eval as runner
import skill_snapshot
import security_check


class DeliveryChecks(unittest.TestCase):
    def setUp(self):
        parent=REPO/".eval-runs/tmp";parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent,prefix="delivery-check-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_archive_preserves_source_and_detects_tampering(self):
        source=self.root/"run 中文";source.mkdir()
        (source/"trace.txt").write_text("safe synthetic trace",encoding="utf-8")
        (source/".git").mkdir();(source/".git/config").write_text("local synthetic git",encoding="utf-8")
        bundle=self.root/"run.zip"
        self.assertEqual(archive.build(source,bundle)["files"],1)
        manifest=json.loads(bundle.with_suffix(".manifest.json").read_text(encoding="utf-8"))
        archive.verify(bundle,manifest)
        self.assertTrue((source/"trace.txt").exists())
        with self.assertRaises(ValueError):archive.build(source,bundle)
        with bundle.open("ab") as out:out.write(b"changed")
        with self.assertRaises(ValueError):archive.verify(bundle,manifest)
        self.assertTrue((source/"trace.txt").exists())

    def test_archive_rejects_output_in_source_and_outside_workspace(self):
        source=self.root/"run";source.mkdir();(source/"file.txt").write_text("test")
        with self.assertRaises(ValueError):archive.build(source,source/"bundle.zip")
        with self.assertRaises(ValueError):archive.owned(REPO.parent/"outside.zip")

    def test_archive_never_deletes_a_concurrent_partial_file(self):
        source=self.root/"run";source.mkdir();(source/"trace.txt").write_text("test")
        bundle=self.root/"run.zip";partial=bundle.with_suffix(".partial.zip")
        original=Path.open
        def racing_open(path,mode="r",*args,**kwargs):
            if path==partial and mode=="xb":
                with original(path,"wb") as stream:stream.write(b"another owner")
                raise FileExistsError("concurrent creator")
            return original(path,mode,*args,**kwargs)
        with patch.object(Path,"open",racing_open),self.assertRaises(FileExistsError):archive.build(source,bundle)
        self.assertEqual(partial.read_bytes(),b"another owner")

    def test_native_and_catalog_flags_preserve_image_isolation(self):
        for native in [False,True]:
            command=runner.command(self.root,self.root/"schema.json",self.root/"answer.json",native=native)
            self.assertIn("--ignore-user-config",command)
            self.assertIn("features.image_generation=false",command)
            self.assertIn("features.shell_tool=false",command)
            self.assertIn("features.skip_host_skill_discovery="+str(not native).lower(),command)

    def test_invalid_execution_inputs_fail_before_workspace_creation(self):
        target=self.root/"must-not-exist"
        result=subprocess.run([sys.executable,str(REPO/"scripts/run_behavior_eval.py"),"--output",str(target),"--timeout","0"],capture_output=True,timeout=10)
        self.assertEqual(result.returncode,2)
        self.assertFalse(target.exists())
        result=subprocess.run([sys.executable,str(REPO/"scripts/probe_host.py"),"--output",str(REPO/"outside-evidence")],capture_output=True,timeout=10)
        self.assertEqual(result.returncode,2)
        self.assertFalse((REPO/"outside-evidence").exists())

    def test_ci_summary_keeps_timeout_and_remains_single_json(self):
        output=io.StringIO()
        with patch.object(ci_check,"REPO",self.root),patch.object(ci_check.subprocess,"run",side_effect=[subprocess.TimeoutExpired("test",120),SimpleNamespace(returncode=0),SimpleNamespace(returncode=1),SimpleNamespace(returncode=0)]),redirect_stdout(output):
            self.assertEqual(ci_check.main(),1)
        summary=json.loads(output.getvalue())
        self.assertFalse(summary["passed"])
        self.assertEqual(summary["checks"][0]["status"],"timeout")
        self.assertEqual(summary["checks"][2]["exit_code"],1)
        self.assertEqual(summary["model_calls"],0)

    def test_gitignore_with_positive_negative_and_staging_evidence(self):
        repo=self.root/"ignore-repo";repo.mkdir()
        subprocess.run(["git","init","--quiet","--template=",str(repo)],check=True,timeout=10)
        (repo/".gitignore").write_bytes((REPO/".gitignore").read_bytes())
        ignored=[".env",".venv/data.txt",".eval-runs/raw.txt","image-evidence/private.png","sub/coverage/data.txt"]
        tracked=["evals/cases.json","tests/test_demo.py","uv.lock",".github/workflows/checks.yml",".agents/skills/demo/reference/workflow.md"]
        for name in ignored+tracked:
            path=repo/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text("synthetic",encoding="utf-8")
            result=subprocess.run(["git","-C",str(repo),"check-ignore","--no-index","-q","--",name],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0 if name in ignored else 1,name)
        subprocess.run(["git","-C",str(repo),"add","."],check=True,capture_output=True,timeout=10)
        names=subprocess.check_output(["git","-C",str(repo),"diff","--cached","--name-only"],text=True,timeout=10).splitlines()
        self.assertEqual(set(names),set(tracked+[".gitignore"]))

    def test_isolated_skill_copy_and_drift_are_read_only(self):
        target=self.root/"中文 space"/runner.SKILL.name
        shutil.copytree(runner.SKILL,target)
        manifest={"schema":1,"name":runner.SKILL.name,"source_git_baseline":"test-only","source_uncommitted":True,"files":skill_snapshot.inventory(target)}
        self.assertTrue(skill_snapshot.compare(target,manifest)["matches"])
        path=target/"assets/design-record-template.md"
        path.write_text(path.read_text(encoding="utf-8")+"\nlocal customization\n",encoding="utf-8")
        changed=path.read_bytes()
        with self.assertRaises(ValueError):skill_snapshot.compare(target,manifest)
        self.assertEqual(path.read_bytes(),changed)

    def test_security_scans_unstaged_rename_without_requiring_staging(self):
        repo=self.root/"rename-repo";repo.mkdir()
        subprocess.run(["git","init","--quiet","--template=",str(repo)],check=True,timeout=10)
        old=repo/"old.md";old.write_text("safe",encoding="utf-8")
        subprocess.run(["git","-C",str(repo),"add","old.md"],check=True,timeout=10)
        old.unlink();(repo/"new.md").write_text("safe",encoding="utf-8")
        self.assertEqual(security_check.intended_files(repo),["new.md"])
        old.write_text("new content",encoding="utf-8")
        self.assertEqual(security_check.intended_files(repo),["new.md","old.md"])

    def test_ci_archive_scope_cannot_include_private_model_traces(self):
        workflow=yaml.safe_load((REPO/".github/workflows/checks.yml").read_text(encoding="utf-8"))
        self.assertEqual(workflow["permissions"],{"contents":"read"})
        uploads=[s for s in workflow["jobs"]["repository-checks"]["steps"] if s.get("uses","").startswith("actions/upload-artifact@")]
        self.assertEqual(len(uploads),1)
        settings=uploads[0]["with"]
        self.assertTrue(settings["include-hidden-files"])
        allowed=(self.root/".eval-runs/ci").resolve()
        candidate=(self.root/settings["path"]).resolve()
        self.assertEqual(candidate,allowed)
        self.assertFalse((self.root/".eval-runs/private-model/trace.txt").is_relative_to(candidate))
        self.assertLessEqual(settings["retention-days"],7)
