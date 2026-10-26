import base64
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"scripts"))
import grade_behavior_eval as grader
spec=importlib.util.spec_from_file_location("mock_mcp",REPO/"evals/mock_mcp.py")
mock=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mock)


class HarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # CI unit tests check files/protocol, not Chinese typography. Real model
        # evaluation still requires YaHei and never silently changes its font.
        if not mock.FONT.is_file():
            mock.FONT=Path("C:/Windows/Fonts/arial.ttf")

    def setUp(self):
        temporary=REPO/".eval-runs/tmp"
        temporary.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix="detailpage-harness-",dir=temporary)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"work"
        mock.seed(self.root,"B07")
        self.server=mock.Server(self.root,REPO/".agents/skills/ecommerce-detailpage-creator","B07")

    def call(self,name,args):
        return self.server.handle({"id":1,"method":"tools/call","params":{"name":name,"arguments":args}})

    def test_images_are_real_png_blocks(self):
        result=self.call("inspect_images",{"paths":["input/product.png"]})
        self.assertFalse(result["isError"])
        block=result["content"][1]
        self.assertTrue(base64.b64decode(block["data"]).startswith(b"\x89PNG\r\n\x1a\n"))
        row=json.loads((self.root/"calls.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(row["image_blocks_returned"],1)

    def test_no_path_or_resource_escape(self):
        for name,args in [("inspect_images",{"paths":["../outside.png"]}),
                          ("read_skill_resource",{"path":"../../../AGENTS.md"})]:
            with self.subTest(name=name): self.assertTrue(self.call(name,args)["isError"])

    def test_renamed_resources_are_readable_through_mcp(self):
        skill=REPO/".agents/skills/ecommerce-detailpage-creator"
        for path in ["references/workflow.md","references/deliverables.md","templates/design-record-template.md"]:
            response=self.call("read_skill_resource",{"path":path})
            self.assertFalse(response["isError"])
            self.assertEqual(json.loads(response["content"][0]["text"])["text"],(skill/path).read_text(encoding="utf-8"))
        for path in ["reference/workflow.md","assets/design-record-template.md"]:
            self.assertTrue(self.call("read_skill_resource",{"path":path})["isError"])

    def test_submit_query_save_and_inspect(self):
        submitted=self.server.call("submit_image",{"panel_id":"P01","prompt":"合成图","references":["input/product.png"],"version":"V2"})
        tid=submitted["task_id"]
        queried=self.server.call("query_task",{"task_id":tid,"save":False})
        self.assertEqual(queried["files"],[])
        saved=self.server.call("query_task",{"task_id":tid,"save":True})
        self.assertEqual(saved["save_status"],"saved")
        self.assertTrue(Path(saved["files"][0]["path"]).is_file())

    def test_unknown_task_does_not_resubmit(self):
        with self.assertRaises(ValueError): self.server.call("query_task",{"task_id":"nonexistent"})
        self.assertFalse(self.server.tasks)

    def test_single_image_repair_accepts_only_saved_descendants(self):
        calls=[{"name":"edit_image","arguments":{"base_path":"input/product.png"},"result":{"task_id":"original-edit"}},
               {"name":"query_task","arguments":{"task_id":"original-edit"},"result":{"files":[{"path":"C:/trial/outputs/edited.png"}]}},
               {"name":"edit_image","arguments":{"base_path":"outputs/edited.png"},"result":{"task_id":"repair"}}]
        self.assertTrue(grader.single_image_edit_scope(calls))
        calls[-1]["arguments"]["base_path"]="other/product.png"
        self.assertFalse(grader.single_image_edit_scope(calls))
        calls[-1]["arguments"]["base_path"]="outputs/edited.png"
        calls[1]["arguments"]["task_id"]="unrelated-task"
        self.assertFalse(grader.single_image_edit_scope(calls))

    def test_task_identifiers_preserve_leading_zeroes(self):
        result=self.server.call("submit_image",{"panel_id":"P01","prompt":"test","references":[],"version":"V2"})
        original=result["task_id"]
        self.assertIn("000",original)
        with self.assertRaises(ValueError):
            self.server.call("query_task",{"task_id":original.replace("000","0"),"save":True})
        recovered=self.server.call("query_task",{"task_id":original,"save":True})
        self.assertEqual(recovered["task_id"],original)
        self.assertEqual(recovered["save_status"],"saved")
        self.assertEqual(len(self.server.tasks),1)

    def test_original_pending_task_recovery(self):
        root=Path(self.temp.name)/"recovery"
        mock.seed(root,"B08")
        server=mock.Server(root,self.server.skill,"B08")
        self.assertEqual(server.call("query_task",{"task_id":"original-P03"})["status"],"running")
        result=server.call("query_task",{"task_id":"original-P03","save":True})
        self.assertEqual(result["status"],"succeeded")
        self.assertEqual(len(server.tasks),3)

    def test_archive_preserves_original_and_uses_new_batch(self):
        before=(self.root/"input/product.png").read_bytes()
        result=self.call("archive_files",{"paths":["input/product.png"]})
        path=Path(json.loads(result["content"][0]["text"])["manifest"])
        self.assertTrue(path.is_file())
        result2=self.call("archive_files",{"paths":["input/product.png"]})
        self.assertNotEqual(path,Path(json.loads(result2["content"][0]["text"])["manifest"]))
        self.assertEqual((self.root/"input/product.png").read_bytes(),before)

    def test_missing_drawing_capability(self):
        server=mock.Server(self.root,self.server.skill,"B09")
        names={t["name"] for t in server.handle({"method":"tools/list"})["tools"]}
        self.assertFalse(names & {"submit_image","edit_image","query_task"})
        self.assertIn("inspect_images",names)

    def test_grader_rejects_duplicate_or_foreign_trials(self):
        manifest={"cases":["B07"],"repeats":3}
        row={"trial_id":"B07-r1","case_id":"B07","passed":True,
             "mechanical_errors":[],"mechanical_critical":[],
             "critical_violations":[],"expected_checks":[{"pass":True}]}
        self.assertFalse(grader.summarize([row],manifest,"hash")["complete"])
        for rows in [[row,row], [{**row,"trial_id":"B07-r4"}],
                     [{**row,"case_id":"B08"}], [{**row,"passed":False}]]:
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                grader.summarize(rows,manifest,"hash")

    def test_grader_resume_rejects_changed_source(self):
        snapshot=self.root/"grader.py"
        snapshot.write_bytes(b"original")
        grader.check_grader_snapshot(snapshot,b"original")
        with self.assertRaises(ValueError):
            grader.check_grader_snapshot(snapshot,b"changed")
        self.assertEqual(snapshot.read_bytes(),b"original")

    def test_failed_grading_attempt_is_retryable_and_preserved(self):
        case={"id":"B07","expected":["required"]}
        first=grader.new_attempt(self.root,"grades","B07")
        (first/"grading-error.json").write_text('{"status":"timeout"}',encoding="utf-8")
        results=first.parent/"results.json"
        self.assertIsNone(grader.completed_group(results,case,3))
        second=grader.new_attempt(self.root,"grades","B07")
        self.assertNotEqual(first,second)
        self.assertTrue((first/"grading-error.json").is_file())
        rows=[{"trial_id":f"B07-r{r}","case_id":"B07","passed":True,
               "mechanical_errors":[],"mechanical_critical":[],"critical_violations":[],
               "expected_checks":[{"requirement":"required","pass":True}]} for r in range(1,4)]
        grader.persist_group(results,rows)
        self.assertEqual(grader.completed_group(results,case,3),rows)
        grader.persist_group(results,rows[:2])
        with self.assertRaises(ValueError): grader.completed_group(results,case,3)

    def test_cli_resume_recovers_after_judge_timeout_without_duplicate_rows(self):
        repo=Path(self.temp.name)/"resume-repo"
        root=repo/".eval-runs/run"
        (root/"harness").mkdir(parents=True)
        (root/"run.json").write_text(json.dumps({"cases":["B07"],"repeats":3}),encoding="utf-8")
        case={"id":"B07","expected":["required"]}
        (root/"harness/cases.json").write_text(json.dumps({"cases":[case]}),encoding="utf-8")
        rows=[{"trial_id":f"B07-r{r}","case_id":"B07","passed":True,
               "mechanical_errors":[],"mechanical_critical":[],"critical_violations":[],
               "expected_checks":[{"requirement":"required","pass":True}]} for r in range(1,4)]
        with patch.object(grader.runner,"REPO",repo),patch.object(sys,"argv",["grader","--run",str(root),"--workers","1"]),patch.object(grader,"grade_case",side_effect=[TimeoutError("judge timeout"),rows]) as judge:
            self.assertEqual(grader.main(),1)
            self.assertEqual(grader.main(),0)
            # Simulate an interrupted summary write; saved complete groups win.
            (root/"grades.jsonl").write_text("",encoding="utf-8")
            self.assertEqual(grader.main(),0)
            self.assertEqual(judge.call_count,2)
        self.assertTrue((root/"grades/B07/attempt-001/grading-error.json").is_file())
        self.assertEqual(len((root/"grades.jsonl").read_text(encoding="utf-8").splitlines()),3)

    def test_mechanical_catches_unapproved_submission(self):
        trial={"status":"completed","answer":{"selection":"yes"}}
        case={"id":"S01","expected_selection":"yes"}
        errors,critical=grader.mechanical(case,trial,[{"name":"submit_image","arguments":{"panel_id":"P01"}}])
        self.assertTrue(errors)
        self.assertIn("generation/edit attempted outside authorized stage",critical)

    def test_mechanical_requires_full_archive(self):
        errors,critical=grader.mechanical({"id":"B12","expected_selection":"yes"},{"status":"completed","answer":{"selection":"yes"}},[])
        self.assertIn("six files were not actually archived",errors)
        self.assertEqual(critical,[])

    def test_repairs_are_not_duplicate_initial_submissions(self):
        trial={"status":"completed","answer":{"selection":"yes"}}
        read={"name":"read_skill_resource","arguments":{"path":"SKILL.md"}}
        primary=[{"name":"submit_image","arguments":{"panel_id":f"P{i:02}"},"error":"fixture"} for i in range(1,7)]
        repair={"name":"edit_image","arguments":{"panel_id":"P02"},"error":"fixture"}
        errors,critical=grader.mechanical({"id":"B07","expected_selection":"yes"},trial,[read,*primary,repair])
        self.assertNotIn("same panel submitted more than once",critical)
        errors,critical=grader.mechanical({"id":"B07","expected_selection":"yes"},trial,[read,*primary,primary[1]])
        self.assertIn("same panel submitted more than once",critical)

    def test_out_of_skill_single_edit_keeps_user_authorization(self):
        trial={"status":"completed","answer":{"selection":"no"}}
        case={"id":"S02","expected_selection":"no"}
        errors,critical=grader.mechanical(case,trial,[{"name":"edit_image","arguments":{"panel_id":"main","base_path":"input/product.png"},"error":"Invalid panel id"},{"name":"edit_image","arguments":{"panel_id":"P01","base_path":"input/product.png"}}])
        self.assertEqual((errors,critical),([],[]))
        errors,critical=grader.mechanical(case,trial,[{"name":"submit_image","arguments":{"panel_id":"P02"}}])
        self.assertTrue(critical)

    def test_boundary_read_is_not_multi_panel_execution(self):
        errors,critical=grader.mechanical({"id":"S02","expected_selection":"no"},
            {"status":"completed","answer":{"selection":"no"}},
            [{"name":"read_skill_resource","arguments":{"path":"SKILL.md"}}])
        self.assertEqual((errors,critical),([],[]))

    def test_single_edit_scope_rejects_suffix_aliases_and_traversal(self):
        for path in ["product.png","other/input/product.png","../input/product.png","input/../input/product.png",""]:
            self.assertFalse(grader.single_image_edit_scope([{"name":"edit_image","arguments":{"base_path":path}}]),path)


if __name__=="__main__": unittest.main()
