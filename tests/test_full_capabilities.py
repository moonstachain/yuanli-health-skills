import json
import unittest

from tests._full_support import CAPABILITIES, ROOT


class FullCapabilityTests(unittest.TestCase):
    def test_all_twelve_contracts_match_frozen_identities_and_validate(self):
        from yuanli_health_skills.validator import validate_contract

        for source_id, identity in CAPABILITIES.items():
            with self.subTest(source_id=source_id):
                directory = ROOT / "capabilities" / source_id
                contract = json.loads((directory / "contract.json").read_text(encoding="utf-8"))
                capability_class, profile_of, objects, clock, transition, authority = identity
                self.assertEqual(validate_contract(contract).errors, ())
                self.assertEqual(contract["source_capability_id"], source_id)
                self.assertEqual(contract["class"], capability_class)
                self.assertEqual(contract["profile_of"], profile_of)
                self.assertEqual(contract["objects"], objects)
                self.assertEqual(contract["health_clock"], clock)
                self.assertEqual(contract["transition_intent"], transition)
                self.assertEqual(contract["authority"]["final_authority"], authority)
                self.assertIsNone(contract["registry_capability_id"])
                self.assertIs(contract["mutates_canon"], False)
                self.assertEqual(contract["claims"], ["non_clinical", "non_release"])

    def test_all_twelve_instruction_documents_have_operational_boundaries(self):
        required_headings = (
            "## Purpose", "## Input contract", "## Output contract", "## Procedure",
            "## Authority and privacy boundaries", "## Stop and escalation rules",
            "## Anti-patterns",
        )
        forbidden = ("pip install", "brew install", "apt install", "publish release", "registry admission authorized")
        for source_id in CAPABILITIES:
            with self.subTest(source_id=source_id):
                text = (ROOT / "capabilities" / source_id / "instructions.md").read_text(encoding="utf-8")
                positions = [text.index(heading) for heading in required_headings]
                self.assertEqual(positions, sorted(positions))
                self.assertTrue(all(term not in text.lower() for term in forbidden))
                self.assertIn("typed-candidate-envelope-v1", text)
                self.assertIn("non-final", text.lower())
                self.assertIn("no persistence", text.lower())


if __name__ == "__main__":
    unittest.main()
