import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"scripts"))
import audit_evidence as audit
import layout_migration as migration
import check
import run_behavior_eval as runner


class LayoutMigrationTests(unittest.TestCase):
    def test_path_only_equivalence_and_history_are_pinned(self):
        current=audit.fingerprints();baseline=migration.verify_path_only(current)
        self.assertEqual(audit.load(audit.PUBLIC),baseline)
        relabeled=copy.deepcopy(baseline);relabeled["fingerprints"]=current
        with self.assertRaises(ValueError):audit.validate(relabeled)

    def test_business_mutation_cannot_hide_behind_path_mapping(self):
        current=audit.fingerprints()
        originals={p:migration.git_text(p) for p in ["evals/evidence.json",*audit.load(audit.PUBLIC)["fingerprints"]]}
        parent=REPO/".eval-runs/tmp";parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent,prefix="layout-") as temp:
            root=Path(temp)
            for name in current:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO/name,target)
            name=migration.PREFIX+"templates/design-record-template.md"
            path=root/name;path.write_text(path.read_text(encoding="utf-8")+"\nchanged business rule\n",encoding="utf-8")
            changed=dict(current);changed[name]=migration.sha(path.read_text(encoding="utf-8"))
            with patch.object(migration,"REPO",root),patch.object(migration,"git_text",side_effect=lambda p:originals[p]):
                with self.assertRaisesRegex(ValueError,"Not a path-only"):migration.verify_path_only(changed)

    def test_only_current_resource_directories_and_index_are_accepted(self):
        parent=REPO/".eval-runs/tmp";parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent,prefix="layout-package-") as temp:
            root=Path(temp)/runner.SKILL.name;shutil.copytree(runner.SKILL,root)
            self.assertFalse(check.check_layout(root))
            (root/"references").rename(root/"reference")
            self.assertTrue(check.check_layout(root))


if __name__=="__main__":unittest.main()
