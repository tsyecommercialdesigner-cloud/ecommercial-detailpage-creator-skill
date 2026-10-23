import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import audit_evidence as audit
import security_check as security


class EvidenceSecurityTests(unittest.TestCase):
    def test_public_attestation_and_rejected_drift(self):
        original=audit.load(audit.PUBLIC)
        audit.validate(original)
        for change in ("fingerprint","duplicate","missing","routing","rubric"):
            value=copy.deepcopy(original)
            if change=="fingerprint": value["fingerprints"]["uv.lock"]="changed"
            elif change=="duplicate": value["batches"]["selection"]["trials"][1]=value["batches"]["selection"]["trials"][0]
            elif change=="missing": value["batches"]["behavior"]["trials"].pop()
            elif change=="routing": value["batches"]["selection"]["trials"][0]["selected_skill"]="clarify"
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


if __name__=="__main__": unittest.main()
