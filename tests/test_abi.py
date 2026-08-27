import copy
import importlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
VALID = ROOT / "fixtures" / "abi" / "valid"
INVALID = ROOT / "fixtures" / "abi" / "invalid"


class AbiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.validator = importlib.import_module("yuanli_health_skills.validator")
            self.envelope = importlib.import_module("yuanli_health_skills.envelope")
        except ModuleNotFoundError as exc:
            self.fail(f"public ABI validator modules are not implemented: {exc}")

    def test_three_representative_contracts_are_valid(self):
        files = sorted(VALID.glob("*.json"))
        self.assertEqual([p.name for p in files], ["experience.json", "kernel.json", "meta.json"])
        for path in files:
            with self.subTest(path=path.name):
                result = self.validator.validate_contract(json.loads(path.read_text()))
                self.assertEqual(result.errors, ())

    def test_named_invalid_contracts_return_stable_codes(self):
        expected = {
            "ai-final-authority.json": "FINAL_AUTHORITY_FORBIDDEN",
            "clinical-overreach.json": "CLINICAL_OVERREACH",
            "direct-canon-write.json": "CANON_WRITE_FORBIDDEN",
            "lifecycle-released.json": "INVALID_LIFECYCLE",
            "multiple-transition-intents.json": "TRANSITION_INTENT_SINGLE_STRING",
            "registry-id-before-admission.json": "REGISTRY_ID_BEFORE_ADMISSION",
            "repository-phi-allowed.json": "REPOSITORY_PHI_FORBIDDEN",
            "runtime-logging-enabled.json": "RUNTIME_LOGGING_FORBIDDEN",
            "runtime-persistence-enabled.json": "RUNTIME_PERSISTENCE_FORBIDDEN",
            "unknown-domain-object.json": "UNKNOWN_DOMAIN_OBJECT",
            "unknown-health-clock.json": "UNKNOWN_HEALTH_CLOCK",
        }
        files = sorted(INVALID.glob("*.json"))
        self.assertEqual([p.name for p in files], sorted(expected))
        for path in files:
            with self.subTest(path=path.name):
                result = self.validator.validate_contract(json.loads(path.read_text()))
                self.assertIn(expected[path.name], [error.code for error in result.errors])

    def test_errors_are_deterministically_ordered(self):
        contract = json.loads((INVALID / "direct-canon-write.json").read_text())
        contract["registry_capability_id"] = "zk:capability:not-admitted"
        result = self.validator.validate_contract(contract)
        self.assertEqual(
            [error.code for error in result.errors],
            ["CANON_WRITE_FORBIDDEN", "REGISTRY_ID_BEFORE_ADMISSION"],
        )

    def test_contract_validator_rejects_nested_extension_fields(self):
        contract = json.loads((VALID / "kernel.json").read_text())
        contract["privacy"]["unreviewed_extension"] = True
        self.assertEqual(
            [error.code for error in self.validator.validate_contract(contract).errors],
            ["STRICT_SCHEMA_VIOLATION"],
        )

    def test_source_registry_validator_is_strict_at_suite_and_member_boundaries(self):
        registry = json.loads((ROOT / "registry" / "source-capabilities.json").read_text())
        registry["unreviewed_extension"] = True
        registry["members"][0]["unreviewed_extension"] = True
        self.assertEqual(
            [error.code for error in self.validator.validate_source_registry(registry).errors],
            ["STRICT_SCHEMA_VIOLATION", "STRICT_SCHEMA_VIOLATION"],
        )

    def test_candidate_envelope_keeps_unknowns_and_evidence_links_explicit(self):
        built = self.envelope.build_candidate_envelope(
            source_capability_id="yuanli.health.kernel.ctx",
            known=[{"fact": "synthetic preference recorded", "evidence_reference": "evd:synthetic:001"}],
            unknown=["current clinical state"],
            assumptions=["subject may prefer morning review"],
            authority_gate="YELLOW",
            escalation=["request_subject_review"],
            guardrail=["not_clinical_advice"],
        )
        self.assertEqual(built["unknown"], ["current clinical state"])
        self.assertEqual(built["known"][0]["evidence_reference"], "evd:synthetic:001")
        self.assertFalse(built["canonical_write"])
        self.assertEqual(built["persistence"], "none")
        self.assertEqual(self.validator.validate_envelope(built).errors, ())

    def test_known_without_evidence_is_rejected(self):
        envelope = {
            "schema": "typed-candidate-envelope-v1",
            "source_capability_id": "yuanli.health.kernel.ctx",
            "known": [{"fact": "unsupported fact", "evidence_reference": ""}],
            "unknown": [],
            "assumption": [],
            "evidence_references": [],
            "authority_gate": "YELLOW",
            "candidate_state": "proposed",
            "canonical_write": False,
            "persistence": "none",
            "escalation": [],
            "guardrail": [],
        }
        self.assertEqual(
            [error.code for error in self.validator.validate_envelope(envelope).errors],
            ["KNOWN_EVIDENCE_REQUIRED"],
        )

    def test_synthetic_qualification_receipt_is_validated(self):
        receipt = {
            "schema": "qualification-receipt-v1",
            "source_capability_id": "yuanli.health.kernel.ctx",
            "qualification_basis": "synthetic_only",
            "claims": ["non_clinical", "non_release"],
            "candidate_state": "qualified",
            "canonical_write": False,
        }
        self.assertEqual(self.validator.validate_receipt(receipt).errors, ())
        invalid = copy.deepcopy(receipt)
        invalid["qualification_basis"] = "real_patient_data"
        self.assertEqual(
            [error.code for error in self.validator.validate_receipt(invalid).errors],
            ["SYNTHETIC_QUALIFICATION_REQUIRED"],
        )

    def test_cli_accepts_valid_fixtures_and_source_registry(self):
        command = [sys.executable, str(ROOT / "scripts" / "validate_capabilities.py")]
        completed = subprocess.run(
            command + [str(VALID), str(ROOT / "registry" / "source-capabilities.json")],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.count(":OK\n"), 4)

    def test_cli_rejects_fixture_with_its_stable_error_code(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "validate_capabilities.py"),
                str(INVALID / "unknown-health-clock.json"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn(":UNKNOWN_HEALTH_CLOCK:health_clock", completed.stderr)


if __name__ == "__main__":
    unittest.main()
