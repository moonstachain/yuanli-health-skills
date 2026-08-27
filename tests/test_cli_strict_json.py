import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT / "scripts/validate_capabilities.py")]


class StrictJsonCliTests(unittest.TestCase):
    def test_explicit_empty_directory_fails_as_zero_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(CLI + [directory], check=False, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("NO_DOCUMENTS", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_empty_directory_fails_even_when_another_input_is_valid(self):
        registry = ROOT / "registry/source-capabilities.json"
        with tempfile.TemporaryDirectory() as directory:
            command = CLI + [directory, str(registry)]
            first = subprocess.run(command, check=False, capture_output=True, text=True)
            second = subprocess.run(command, check=False, capture_output=True, text=True)
            expected_diagnostic = f"{directory}:NO_DOCUMENTS:$"
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first.stderr, second.stderr)
        self.assertEqual(first.returncode, 1)
        self.assertEqual(second.returncode, 1)
        self.assertIn("source-capabilities.json:OK", first.stdout)
        self.assertIn(expected_diagnostic, first.stderr)
        self.assertNotIn("Traceback", first.stderr)

    def test_non_finite_json_constants_are_rejected_stably(self):
        template = (
            '{"schema":"typed-candidate-envelope-v1",'
            '"source_capability_id":"yuanli.health.kernel.ctx",'
            '"known":[],"unknown":[%s],"assumption":[],"evidence_references":[],'
            '"authority_gate":"YELLOW","candidate_state":"proposed",'
            '"canonical_write":false,"persistence":"none","escalation":[],"guardrail":[]}'
        )
        with tempfile.TemporaryDirectory() as directory:
            for constant in ("NaN", "Infinity", "-Infinity"):
                with self.subTest(constant=constant):
                    input_file = Path(directory) / f"{constant.replace('-', 'negative-')}.json"
                    input_file.write_text(template % constant)
                    completed = subprocess.run(CLI + [str(input_file)], check=False, capture_output=True, text=True)
                    self.assertEqual(completed.returncode, 1)
                    self.assertIn(":INVALID_JSON:$:", completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)

    def test_duplicate_json_keys_are_rejected_stably(self):
        raw = (
            '{"schema":"qualification-receipt-v1",'
            '"schema":"qualification-receipt-v1",'
            '"source_capability_id":"yuanli.health.kernel.ctx",'
            '"qualification_basis":"synthetic_only","claims":[],'
            '"candidate_state":"qualified","canonical_write":false}'
        )
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "duplicate.json"
            input_file.write_text(raw)
            first = subprocess.run(CLI + [str(input_file)], check=False, capture_output=True, text=True)
            second = subprocess.run(CLI + [str(input_file)], check=False, capture_output=True, text=True)
        self.assertEqual(first.returncode, 1)
        self.assertEqual(first.stderr, second.stderr)
        self.assertIn(":DUPLICATE_JSON_KEY:$:", first.stderr)
        self.assertNotIn("Traceback", first.stderr)

    def test_manifest_catalog_strings_are_data_and_never_executed(self):
        registry = json.loads((ROOT / "registry/source-capabilities.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "executed"
            hostile = copy.deepcopy(registry)
            hostile["catalog_suite_id"] = f"$(touch {marker})"
            input_file = Path(directory) / "hostile-manifest.json"
            input_file.write_text(json.dumps(hostile))
            completed = subprocess.run(CLI + [str(input_file)], check=False, capture_output=True, text=True)
            self.assertFalse(marker.exists())
        self.assertEqual(completed.returncode, 1)
        self.assertIn("SOURCE_SUITE_IDENTITY_MISMATCH", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()
