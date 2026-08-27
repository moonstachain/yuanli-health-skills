import collections
import re
import unittest

from tests._full_support import CAPABILITIES, load_cases, walk_keys


class FullSuiteCaseTests(unittest.TestCase):
    def test_corpus_has_exact_capability_and_category_distribution(self):
        cases = load_cases()
        self.assertEqual(len(cases), 120)
        self.assertEqual(
            [case["case_id"] for case in cases],
            [f"SYN-FS-{index:03d}" for index in range(1, 121)],
        )
        by_capability = collections.Counter(case["capability_source_id"] for case in cases)
        self.assertEqual(by_capability, collections.Counter({source_id: 10 for source_id in CAPABILITIES}))
        by_category = collections.Counter(
            (case["capability_source_id"], case["category"]) for case in cases
        )
        for source_id in CAPABILITIES:
            self.assertEqual(by_category[(source_id, "gold")], 5)
            self.assertEqual(by_category[(source_id, "boundary")], 3)
            self.assertEqual(by_category[(source_id, "adversarial")], 2)

    def test_cases_are_strict_synthetic_inert_json_with_complete_oracles(self):
        required = {
            "schema", "case_id", "synthetic", "capability_source_id", "category",
            "coverage_tags", "request_type", "risk_flags", "artifacts",
            "declared_unknowns", "assumptions", "expected",
        }
        expected_required = {
            "schema", "candidate_state", "error_code", "error_path", "authority_gate",
            "transition_intent", "transition_executed", "output_artifact_keys", "canonical_write", "persistence",
            "registry_admission", "release_published", "health_outcome_claimed",
            "clinical_effectiveness_claimed", "runtime_observed",
        }
        allowed_artifacts = {
            "decision_candidate_id", "wpk_candidate_id", "act_candidate_id",
            "observation_reference", "out_candidate_id", "lrn_candidate_id",
            "task2_preload_receipt", "task2_use_receipt", "visit_questions",
            "draft_capability_id", "built_candidate_id", "review_candidate_id",
            "synthetic_case_count",
        }
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(set(case), required)
                self.assertEqual(case["schema"], "full-suite-synthetic-case-v1")
                self.assertIs(case["synthetic"], True)
                self.assertIn(case["category"], {"gold", "boundary", "adversarial"})
                self.assertTrue(set(case["artifacts"]).issubset(allowed_artifacts))
                self.assertEqual(set(case["expected"]), expected_required)
                for key in (
                    "canonical_write", "registry_admission", "release_published",
                    "health_outcome_claimed", "clinical_effectiveness_claimed",
                    "runtime_observed",
                ):
                    self.assertIs(case["expected"][key], False)
                self.assertEqual(case["expected"]["persistence"], "none")

    def test_every_case_oracle_has_a_closed_authority_gate_and_transition(self):
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                expected = case["expected"]
                transition = CAPABILITIES[case["capability_source_id"]][4]
                self.assertIn(expected["authority_gate"], {"GREEN", "YELLOW", "RED"})
                self.assertEqual(expected["transition_intent"], transition)
                self.assertIs(
                    expected["transition_executed"],
                    expected["schema"] == "full-suite-candidate-v1",
                )

    def test_fixture_contains_no_phi_shaped_fields_or_realistic_values(self):
        forbidden_keys = {
            "name", "date", "address", "device_id", "medical_record_id", "mrn",
            "transcript", "provider", "payment", "appointment_state",
        }
        realistic_measurement = re.compile(r"\b(?:bpm|mmhg|mg/dl|kg|lbs?)\b", re.I)
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                self.assertTrue(forbidden_keys.isdisjoint(set(walk_keys(case))))
                self.assertIsNone(realistic_measurement.search(repr(case)))


if __name__ == "__main__":
    unittest.main()
