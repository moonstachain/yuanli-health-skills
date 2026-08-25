import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests._adapter_support import QUICK_VALIDATE, ROOT, copy_repository, generate, json_document, run_script, validate


class CodexAdapterRepositoryTests(unittest.TestCase):
    def test_release_metadata_is_unpublished_nonclaiming_and_matches_package(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            package = temporary / "package"
            metadata = temporary / "release-metadata.json"
            generate(package, metadata=metadata)
            document = json_document(metadata)
            sums = (package / "SHA256SUMS").read_bytes()
            self.assertEqual(document["version"], "0.1.0")
            self.assertEqual(document["source_suite_id"], "YL-SUITE-HEALTH-20260823-0001")
            self.assertEqual(document["catalog_suite_id"], "zk:suite:yuanli-health")
            self.assertEqual(document["state"], "qualified_source_candidate")
            self.assertIs(document["published"], False)
            self.assertIs(document["registry_admission"], False)
            self.assertEqual(document["deployment"], "none")
            self.assertEqual(document["release_basis"], "synthetic_qualification_only")
            self.assertIs(document["human_runtime_observed"], False)
            self.assertEqual(document["health_outcome"], "not_observed")
            self.assertEqual(document["clinical_effectiveness"], "not_claimed")
            self.assertEqual(document["n5_pilot"], "waived_by_human_owner")
            self.assertEqual(document["package_path"], "dist/codex/yuanli-health")
            self.assertEqual(document["package_content_sha256"], hashlib.sha256(sums).hexdigest())
            self.assertEqual(document["package_file_count"], 54)
            self.assertEqual(document["package_file_count_convention"], "all_regular_files_including_SHA256SUMS")
            self.assertIsNone(document["source_commit"])
            self.assertIsNone(document["source_tree"])
            self.assertIsNone(document["registry_commit"])
            self.assertIsNone(document["registry_capability_ids"])

    def test_repository_candidate_surfaces_and_zero_secret_workflow_validate(self):
        package = ROOT / "dist/codex/yuanli-health"
        metadata = ROOT / "releases/v0.1.0/release-metadata.json"
        result = validate(package, metadata=metadata, repository=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((ROOT / "LICENSE").read_bytes(), (package / "LICENSE").read_bytes())
        self.assertEqual((ROOT / "NOTICE").read_bytes(), (package / "NOTICE").read_bytes())

        with tempfile.TemporaryDirectory() as directory:
            repository = copy_repository(Path(directory))
            copied_package = repository / "dist/codex/yuanli-health"
            copied_metadata = repository / "releases/v0.1.0/release-metadata.json"
            generate(copied_package, root=repository, metadata=copied_metadata)
            workflow = repository / ".github/workflows/health-skills-ci.yml"
            workflow.write_text(workflow.read_text(encoding="utf-8") + "\n# ${{ secrets.TOKEN }}\n", encoding="utf-8")
            tampered = validate(
                copied_package,
                root=repository,
                metadata=copied_metadata,
                repository=True,
            )
            self.assertNotEqual(tampered.returncode, 0)
            self.assertIn("workflow secret", tampered.stderr)

    def test_bundled_quick_validator_accepts_generated_root_skill(self):
        if not QUICK_VALIDATE.is_file():
            self.skipTest("bundled Codex quick validator is not installed on this host")
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "package"
            generate(package)
            result = run_script(QUICK_VALIDATE, package)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Skill is valid", result.stdout)


if __name__ == "__main__":
    unittest.main()
