import collections
import unittest

from tests._gold_support import load_cases, walk_keys


class GoldCaseCorpusTests(unittest.TestCase):
    def test_corpus_has_exactly_six_five_case_families(self):
        cases = load_cases()
        self.assertEqual(len(cases), 30)
        self.assertEqual(
            [case["case_id"] for case in cases],
            [f"SYN-GS-{number:03d}" for number in range(1, 31)],
        )
        self.assertEqual(
            collections.Counter(case["family"] for case in cases),
            {
                "insufficient_evidence": 5,
                "contradictory_evidence": 5,
                "multiple_candidates": 5,
                "clinical_escalation": 5,
                "forbidden_downstream_claim": 5,
                "normal_and_boundaries": 5,
            },
        )

    def test_every_case_is_explicitly_synthetic_and_machine_assertable(self):
        required_expected = {
            "authority_gate",
            "primary_candidate_id",
            "dependency_blocker_ids",
            "blocker_maximum",
            "required_state",
            "canonical_write",
            "persistence",
            "formal_wpk_generated",
            "formal_act_generated",
            "out_generated",
            "lrn_generated",
            "reuse_claimed",
        }
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                self.assertIs(case["synthetic"], True)
                self.assertEqual(case["jtbd"], "first_health_session")
                self.assertTrue(case["coverage_tags"])
                self.assertEqual(set(case["expected"]), required_expected)

    def test_corpus_omits_phi_shaped_fields_and_realistic_measurements(self):
        forbidden_keys = {
            "name",
            "date",
            "address",
            "device_id",
            "medical_record_id",
            "transcript",
            "measurement",
            "measurement_value",
        }
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                self.assertTrue(forbidden_keys.isdisjoint(set(walk_keys(case))))
                self.assertNotIn("@", str(case))

    def test_every_candidate_declares_machine_checkable_non_clinical_scope(self):
        for case in load_cases():
            for candidate in case["candidates"]:
                with self.subTest(
                    case_id=case["case_id"], candidate_id=candidate["candidate_id"]
                ):
                    self.assertEqual(candidate.get("candidate_kind"), "non_clinical")


if __name__ == "__main__":
    unittest.main()
