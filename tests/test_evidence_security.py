import copy
from pathlib import Path
import sys
import json
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import audit_evidence as audit
import security_check as security


class EvidenceSecurityTests(unittest.TestCase):
    def test_public_attestation_and_rejected_drift(self):
        original=audit.load(audit.PUBLIC)
        audit.validate(original)
        for change in ("fingerprint","duplicate","missing","routing","rubric","provenance"):
            value=copy.deepcopy(original)
            if change=="fingerprint": value["fingerprints"]["uv.lock"]="changed"
            elif change=="duplicate": value["batches"]["selection"]["trials"][1]=value["batches"]["selection"]["trials"][0]
            elif change=="missing": value["batches"]["behavior"]["trials"].pop()
            elif change=="routing": value["batches"]["selection"]["trials"][0]["selected_skill"]="clarify"
            elif change=="provenance": value["batches"]["native_implicit"]["execution_provenance"]["discovery"]="catalog"
            else: value["batches"]["behavior"]["trials"][0]["checks"]=[]
            with self.subTest(change=change),self.assertRaises(ValueError): audit.validate(value)

    def test_secret_patterns_and_safe_fixture(self):
        self.assertTrue(security.secret_findings(Path(".env"),b""))
        self.assertTrue(security.secret_findings(Path("file.txt"),b"gh"+b"p_"+b"x"*36))
        self.assertFalse(security.secret_findings(Path("cases.json"),b'{"simulated":true}'))

    def test_dependency_findings_fail_closed(self):
        packages=[{"name":"pillow","version":"13.0.0"}]
        self.assertEqual(security.dependency_findings(packages,{"results":[{}]}),[])
        self.assertTrue(security.dependency_findings(packages,{"results":[{"vulns":[{"id":"test-advisory"}]}]}))
        for response in [{},{"results":[]},{"results":[{"error":"unavailable"}]}]:
            with self.assertRaises(ValueError): security.dependency_findings(packages,response)

    def test_comparison_cannot_claim_a_different_sample_count(self):
        data=audit.load(audit.PUBLIC)
        comparison=audit.load(audit.REPO/"evals/comparison.json")
        audit.check_comparison(data,comparison)
        comparison["comparisons"]["behavior"]["candidate_n"]=0
        with self.assertRaises(ValueError):audit.check_comparison(data,comparison)

    def test_export_rejects_catalog_batch_relabeled_as_native_or_explicit(self):
        parent=audit.REPO/".eval-runs/tmp";parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent,prefix="provenance-") as tmp:
            root=Path(tmp)
            (root/"run.json").write_text(json.dumps({"mode":"implicit","discovery":"catalog"}),encoding="utf-8")
            for name in ["explicit","native_implicit","native_explicit"]:
                with self.assertRaisesRegex(ValueError,"provenance differs"):audit.export_batch(root,name,"calibrated")


if __name__=="__main__": unittest.main()
