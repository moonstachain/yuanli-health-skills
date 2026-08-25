import copy
import hashlib
import importlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        try:
            self.projection = importlib.import_module("yuanli_health_skills.projection")
        except ModuleNotFoundError as exc:
            self.fail(f"frozen projection loader is not implemented: {exc}")

    def test_projection_exposes_frozen_domains_clocks_and_effects(self):
        self.assertEqual(
            cls_list := self.projection.allowed_domain_objects(),
            ("ACT", "CTX", "DEC", "EVD", "LRN", "OUT", "WPK"),
        )
        self.assertEqual(self.projection.allowed_health_clocks(), ("behavioral", "clinical", "experimental", "immediate"))
        self.assertEqual(
            self.projection.allowed_effects("immediate"),
            ("emit_evd", "emit_act", "request_review", "safe_degradation"),
        )
        self.assertIn("CTX", cls_list)

    def test_projection_exposes_non_final_authority_rules(self):
        rules = self.projection.authority_rules()
        self.assertEqual(rules["never_final_authority"], ("ai", "device", "automation", "router"))
        self.assertFalse(rules["ai_may_approve_clinical_state"])
        self.assertFalse(rules["device_may_approve_clinical_state"])

    def test_public_projection_mutations_cannot_change_frozen_accessors_or_validation(self):
        from yuanli_health_skills.validator import validate_contract

        snapshot_path = ROOT / "src/yuanli_health_skills/data/health-skill-public-projection-v1.json"
        expected_hash = "2700652ec1eea62bf98e0a303470162d32310b8859f3379ebeaa00396f951a40"
        contract = {
            "schema": "health-skill-contract-v1",
            "source_capability_id": "yuanli.health.kernel.ctx",
            "registry_capability_id": None,
            "class": "kernel",
            "profile_of": ["PATIENT_RECORD"],
            "transition_intent": "synthetic candidate",
            "mutates_canon": False,
            "authority": {"final_authority": "subject", "ai": "assistive", "device": "evidence_source", "automation": "non_final", "router": "non_final"},
            "privacy": {"repository_phi": "forbidden"},
            "runtime_requirements": {"ephemeral": True, "persistence": "none", "logs": "none"},
            "lifecycle": "proposed",
            "qualification": {"basis": "synthetic_only", "status": "pending"},
            "objects": ["PATIENT_RECORD"],
            "health_clock": "overnight",
            "claims": [],
        }
        before_codes = [error.code for error in validate_contract(copy.deepcopy(contract)).errors]
        public_projection = self.projection.load_projection()
        public_projection["domain_objects"]["PATIENT_RECORD"] = {"profile_id": "attacker"}
        public_projection["health_clock"]["overnight"] = {"allowed_effects": ["write_canon"]}
        public_projection["health_clock"]["immediate"]["allowed_effects"].append("write_canon")
        public_projection["authority_semantics"]["final_authority_by_gate"]["RED"].append("ai")
        public_rules = self.projection.authority_rules()
        public_rules["final_authority_by_gate"]["RED"].append("automation")

        after_codes = [error.code for error in validate_contract(copy.deepcopy(contract)).errors]
        reloaded = self.projection.load_projection()
        rules = self.projection.authority_rules()
        self.assertEqual(before_codes, after_codes)
        self.assertIn("UNKNOWN_DOMAIN_OBJECT", after_codes)
        self.assertIn("UNKNOWN_HEALTH_CLOCK", after_codes)
        self.assertNotIn("PATIENT_RECORD", self.projection.allowed_domain_objects())
        self.assertNotIn("overnight", self.projection.allowed_health_clocks())
        self.assertNotIn("write_canon", self.projection.allowed_effects("immediate"))
        self.assertNotIn("PATIENT_RECORD", reloaded["domain_objects"])
        self.assertNotIn("ai", rules["final_authority_by_gate"]["RED"])
        self.assertNotIn("automation", rules["final_authority_by_gate"]["RED"])
        self.assertEqual(rules["never_final_authority"], ("ai", "device", "automation", "router"))
        self.assertEqual(hashlib.sha256(snapshot_path.read_bytes()).hexdigest(), expected_hash)

    def test_unknown_clock_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown health clock"):
            self.projection.allowed_effects("overnight")


if __name__ == "__main__":
    unittest.main()
