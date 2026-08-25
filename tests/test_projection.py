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
        self.assertEqual(rules["never_final_authority"], ("ai", "device", "automation"))
        self.assertFalse(rules["ai_may_approve_clinical_state"])
        self.assertFalse(rules["device_may_approve_clinical_state"])

    def test_unknown_clock_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown health clock"):
            self.projection.allowed_effects("overnight")


if __name__ == "__main__":
    unittest.main()
