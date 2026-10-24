import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"scripts"))
import build_release
import release_gate


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        root=REPO/".eval-runs/tmp";root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root,prefix="release-");self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/"source";self.repo.mkdir()
        def git(*args):return subprocess.check_output(["git","-C",str(self.repo),*args],stderr=subprocess.PIPE,timeout=15)
        self.git=git;git("init","--quiet","--template=")
        shutil.copytree(REPO/".agents/skills"/build_release.NAME,self.repo/build_release.PREFIX)
        (self.repo/"delivery").mkdir();shutil.copyfile(REPO/"delivery/Manage-Skill.ps1",self.repo/"delivery/Manage-Skill.ps1")
        git("add",".");git("-c","user.name=Synthetic test","-c","user.email=test@example.invalid","-c","commit.gpgsign=false","commit","-qm","fixture")
        self.sha=git("rev-parse","HEAD").decode().strip()
        self.out=self.repo/".eval-runs/release"
        with patch.object(build_release,"REPO",self.repo):self.result=build_release.build(self.sha,"v0.1.0",self.out)
        self.parent=self.root/"成员 中文 space";self.parent.mkdir()

    def invoke(self,action,expected=0,**kwargs):
        cmd=[shutil.which("pwsh"),"-NoProfile","-File",str(self.out/"Manage-Skill.ps1"),"-Action",action,"-BundleDir",str(self.out),"-ExpectedManifestSha256",kwargs.get("digest",self.result["manifest_sha256"]),"-SkillsDir",str(self.parent)]
        proc=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",timeout=20)
        self.assertEqual(proc.returncode,expected,proc.stdout+proc.stderr)
        if expected:self.assertEqual(proc.stdout.strip(),"")
        else:self.assertTrue(json.loads(proc.stdout)["passed"])
        return proc

    def test_git_objects_are_reproducible_and_output_is_exclusive(self):
        path=self.repo/build_release.PREFIX/"SKILL.md";path.write_text("unreviewed changed workspace",encoding="utf-8")
        second=self.repo/".eval-runs/second"
        with patch.object(build_release,"REPO",self.repo):
            build_release.build(self.sha,"v0.1.0",second)
            with self.assertRaises(FileExistsError):build_release.build(self.sha,"v0.1.0",second)
        self.assertEqual((self.out/"manifest.json").read_bytes(),(second/"manifest.json").read_bytes())
        self.assertEqual(next(self.out.glob("*.zip")).read_bytes(),next(second.glob("*.zip")).read_bytes())
        with zipfile.ZipFile(next(self.out.glob("*.zip"))) as z:self.assertEqual(len(z.namelist()),4)

    def test_install_check_uninstall_and_rollback_preserve_unrelated_content(self):
        unrelated=self.parent/"member-data.txt";unrelated.write_text("keep")
        self.invoke("Verify");self.invoke("Install");self.invoke("Check")
        self.invoke("Install",1);self.invoke("Check")
        self.invoke("Uninstall");self.assertEqual(unrelated.read_text(),"keep")
        self.assertFalse((self.parent/build_release.NAME).exists())
        self.invoke("Install");self.invoke("Check");self.invoke("Uninstall")

    def test_drift_and_extra_directory_stop_check_and_uninstall(self):
        self.invoke("Install");target=self.parent/build_release.NAME
        path=target/"SKILL.md";original=path.read_bytes();path.write_bytes(original+b"\ncustom")
        self.invoke("Check",1);self.invoke("Uninstall",1);self.assertTrue(path.exists())
        path.write_bytes(original);(target/"custom-empty").mkdir()
        self.invoke("Uninstall",1);self.assertTrue((target/"custom-empty").exists())

    def test_tampered_manifest_and_zip_fail_before_install(self):
        self.invoke("Verify",1,digest="0"*64)
        bundle=next(self.out.glob("*.zip"));bundle.write_bytes(bundle.read_bytes()+b"changed")
        self.invoke("Install",1);self.assertFalse((self.parent/build_release.NAME).exists())

    def test_duplicate_and_traversal_zip_entries_rejected_even_with_recomputed_hashes(self):
        bundle=next(self.out.glob("*.zip"));manifest_path=self.out/"manifest.json"
        original=bundle.read_bytes()
        for extra in [f"{build_release.NAME}/SKILL.md",f"{build_release.NAME}/../outside"]:
            bundle.write_bytes(original)
            with zipfile.ZipFile(bundle,"a") as z:z.writestr(extra,b"synthetic")
            manifest=json.loads(manifest_path.read_text());manifest["zip_sha256"]=hashlib.sha256(bundle.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest));digest=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            self.invoke("Install",1,digest=digest)
            self.assertFalse((self.parent/build_release.NAME).exists())

    def test_release_gate_requires_latest_exact_branch_push_and_review(self):
        def api(path):
            if path.startswith("git/ref/"):return {"object":{"sha":self.sha}}
            if path.startswith("actions/"):return {"workflow_runs":[{"id":1,"head_sha":self.sha,"conclusion":"success"}]}
            return {"statuses":[{"context":"automated-review","state":"success"}]}
        with patch.object(release_gate,"api",side_effect=api):self.assertTrue(release_gate.check(self.sha)["passed"])
        def failed(path):
            if "branch=dev" in path:return {"workflow_runs":[{"id":1,"head_sha":self.sha,"conclusion":"success"},{"id":2,"head_sha":self.sha,"conclusion":None}]}
            return api(path)
        with patch.object(release_gate,"api",side_effect=failed),self.assertRaises(ValueError):release_gate.check(self.sha)
        def existing_tag(path):
            if path.startswith("git/matching-refs/"):return [{"ref":"refs/tags/v0.1.0","object":{"sha":"0"*40}}]
            return api(path)
        with patch.object(release_gate,"api",side_effect=existing_tag),self.assertRaisesRegex(ValueError,"tag already exists"):release_gate.check(self.sha,"v0.1.0")


if __name__=="__main__":unittest.main()
