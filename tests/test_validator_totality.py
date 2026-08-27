import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from yuanli_health_skills import validator


class ValidatorTotalityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((ROOT / "fixtures/abi/valid/kernel.json").read_text())
        cls.envelope = {
            "schema": "typed-candidate-envelope-v1",
            "source_capability_id": "yuanli.health.kernel.ctx",
            "known": [{"fact": "synthetic fact", "evidence_reference": "evd:synthetic:001"}],
            "unknown": ["synthetic unknown"],
            "assumption": ["synthetic assumption"],
            "evidence_references": ["evd:synthetic:001"],
            "authority_gate": "YELLOW",
            "candidate_state": "proposed",
            "canonical_write": False,
            "persistence": "none",
            "escalation": ["subject_review"],
            "guardrail": ["non_clinical"],
        }
        cls.receipt = {
            "schema": "qualification-receipt-v1",
            "source_capability_id": "yuanli.health.kernel.ctx",
            "qualification_basis": "synthetic_only",
            "claims": ["non_clinical"],
            "candidate_state": "qualified",
            "canonical_write": False,
        }
        cls.registry = json.loads((ROOT / "registry/source-capabilities.json").read_text())

    def assert_total_and_stable(self, validate, document, expected_code):
        signatures = []
        for _ in range(2):
            try:
                result = validate(copy.deepcopy(document))
            except Exception as exc:  # the public boundary must close all invalid JSON
                self.fail(f"validator raised {type(exc).__name__}: {exc}")
            self.assertIsInstance(result, validator.ValidationResult)
            self.assertFalse(result.ok)
            signatures.append(tuple((error.code, error.path) for error in result.errors))
        self.assertEqual(signatures[0], signatures[1])
        self.assertIn(expected_code, [code for code, _ in signatures[0]])

    def test_top_level_json_values_are_total_for_all_public_validators(self):
        validators = (
            validator.validate_contract,
            validator.validate_envelope,
            validator.validate_receipt,
            validator.validate_source_registry,
        )
        for validate in validators:
            for value in (None, False, 0, "", [], [1]):
                with self.subTest(validator=validate.__name__, value=value):
                    self.assert_total_and_stable(validate, value, "INVALID_DOCUMENT")

    def test_enum_positions_reject_json_containers_without_raising(self):
        cases = []
        for bad_value in ({}, []):
            contract_class = copy.deepcopy(self.contract)
            contract_class["class"] = bad_value
            cases.append((validator.validate_contract, contract_class, "INVALID_CLASS"))
            contract_authority = copy.deepcopy(self.contract)
            contract_authority["authority"]["router"] = bad_value
            cases.append((validator.validate_contract, contract_authority, "INVALID_AUTHORITY"))
            envelope = copy.deepcopy(self.envelope)
            envelope["authority_gate"] = bad_value
            cases.append((validator.validate_envelope, envelope, "INVALID_AUTHORITY_GATE"))
            receipt = copy.deepcopy(self.receipt)
            receipt["candidate_state"] = bad_value
            cases.append((validator.validate_receipt, receipt, "INVALID_LIFECYCLE"))
        for validate, document, expected_code in cases:
            with self.subTest(validator=validate.__name__, code=expected_code, value=document):
                self.assert_total_and_stable(validate, document, expected_code)

    def test_array_items_are_type_checked_before_comparison_or_membership(self):
        invalid_items = ({"nested": "object"}, ["nested-array"], 7, True, None, "")
        for item in invalid_items:
            contract = copy.deepcopy(self.contract)
            contract["claims"] = [item]
            envelope = copy.deepcopy(self.envelope)
            envelope["assumption"] = [item]
            receipt = copy.deepcopy(self.receipt)
            receipt["claims"] = [item]
            cases = (
                (validator.validate_contract, contract, "INVALID_CLAIMS"),
                (validator.validate_envelope, envelope, "INVALID_ARRAY_ITEM"),
                (validator.validate_receipt, receipt, "INVALID_QUALIFICATION_CLAIM"),
            )
            for validate, document, expected_code in cases:
                with self.subTest(validator=validate.__name__, item=item):
                    self.assert_total_and_stable(validate, document, expected_code)

    def test_cli_returns_stable_error_without_traceback_for_json_containers(self):
        contract = copy.deepcopy(self.contract)
        contract["class"] = {}
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "adversarial.json"
            input_file.write_text(json.dumps(contract))
            command = [sys.executable, str(ROOT / "scripts/validate_capabilities.py"), str(input_file)]
            first = subprocess.run(command, check=False, capture_output=True, text=True)
            second = subprocess.run(command, check=False, capture_output=True, text=True)
        self.assertEqual(first.returncode, 1)
        self.assertEqual(second.returncode, 1)
        self.assertEqual(first.stderr, second.stderr)
        self.assertIn(":INVALID_CLASS:class", first.stderr)
        self.assertNotIn("Traceback", first.stderr)


if __name__ == "__main__":
    unittest.main()
