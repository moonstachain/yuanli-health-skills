import copy
import importlib
import json
import sys
import unittest

from tests._gold_support import ROOT, load_cases, supplied_facts, walk_keys


sys.path.insert(0, str(ROOT / "src"))


class GoldSliceTests(unittest.TestCase):
    def setUp(self):
        try:
            self.gold_slice = importlib.import_module("yuanli_health_skills.gold_slice")
            self.validator = importlib.import_module("yuanli_health_skills.validator")
        except ModuleNotFoundError as exc:
            self.fail(f"Gold Slice behavior is not implemented: {exc}")

    def test_every_case_produces_three_valid_traceable_stage_envelopes(self):
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                bundle = self.gold_slice.process_first_health_session(case)
                self.assertNotIn("errors", bundle)
                self.assertEqual(bundle["stage_order"], ["ctx", "evd", "dec"])
                self.assertEqual(set(bundle["stage_envelopes"]), {"ctx", "evd", "dec"})
                allowed_facts = supplied_facts(case)
                for envelope in bundle["stage_envelopes"].values():
                    self.assertEqual(self.validator.validate_envelope(envelope).errors, ())
                    self.assertTrue(envelope["canonical_write"] is False)
                    self.assertEqual(envelope["persistence"], "none")
                    self.assertTrue(
                        all(entry["fact"] in allowed_facts for entry in envelope["known"])
                    )
                    self.assertTrue(
                        all(entry["fact"] not in case["assumptions"] for entry in envelope["known"])
                    )

    def test_ctx_preserves_declared_unknowns_without_making_decisions(self):
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                ctx = self.gold_slice.process_first_health_session(case)["stage_envelopes"]["ctx"]
                self.assertTrue(set(case["declared_unknowns"]).issubset(set(ctx["unknown"])))
                self.assertEqual(ctx["assumption"], case["assumptions"])
                self.assertTrue(
                    {"priority", "rank", "primary_bottleneck"}.isdisjoint(set(walk_keys(ctx)))
                )

    def test_evd_preserves_evidence_order_and_makes_no_selection(self):
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                bundle = self.gold_slice.process_first_health_session(case)
                self.assertEqual(bundle["evidence_catalog"], case["evidence"])
                evd = bundle["stage_envelopes"]["evd"]
                self.assertTrue(
                    {"priority", "rank", "primary_bottleneck"}.isdisjoint(set(walk_keys(evd)))
                )

    def test_decision_and_non_claim_fields_match_all_machine_expectations(self):
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                bundle = self.gold_slice.process_first_health_session(case)
                expected = case["expected"]
                decision = bundle["decision_candidate"]
                self.assertEqual(bundle["authority_gate"], expected["authority_gate"])
                self.assertEqual(decision["primary_bottleneck"], expected["primary_candidate_id"])
                self.assertEqual(decision["dependency_blockers"], expected["dependency_blocker_ids"])
                self.assertLessEqual(len(decision["dependency_blockers"]), expected["blocker_maximum"])
                for field in (
                    "canonical_write",
                    "persistence",
                    "formal_wpk_generated",
                    "formal_act_generated",
                    "out_generated",
                    "lrn_generated",
                    "reuse_claimed",
                ):
                    self.assertEqual(bundle[field], expected[field])
                self.assertEqual(bundle["experience_state"], expected["required_state"])

    def test_learner_view_is_complete_non_clinical_and_red_is_bilingual(self):
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                bundle = self.gold_slice.process_first_health_session(case)
                learner_view = bundle["learner_view"]
                self.assertEqual(
                    set(learner_view),
                    {"conclusion", "reason", "action_candidate", "guardrail", "evidence_entry"},
                )
                self.assertTrue(all(isinstance(value, str) and value for value in learner_view.values()))
                self.assertNotIn("diagnosis", learner_view["conclusion"].lower())
                self.assertNotIn("treatment plan", learner_view["action_candidate"].lower())
                if bundle["authority_gate"] == "RED":
                    self.assertIn(" / ", learner_view["guardrail"])

    def test_clinician_and_emergency_escalations_cannot_be_bypassed(self):
        expected = {
            "SYN-GS-006": "consult_clinician",
            "SYN-GS-010": "consult_clinician",
            "SYN-GS-016": "consult_clinician",
            "SYN-GS-017": "seek_emergency_help",
            "SYN-GS-018": "consult_clinician",
            "SYN-GS-019": "consult_clinician",
            "SYN-GS-020": "seek_emergency_help",
        }
        for case in load_cases():
            if case["case_id"] not in expected:
                continue
            with self.subTest(case_id=case["case_id"]):
                bundle = self.gold_slice.process_first_health_session(case)
                dec = bundle["stage_envelopes"]["dec"]
                self.assertEqual(bundle["authority_gate"], "RED")
                self.assertIn(expected[case["case_id"]], dec["escalation"])
                self.assertIsNone(bundle["decision_candidate"]["primary_bottleneck"])

    def test_four_capability_contracts_validate_and_match_frozen_identities(self):
        expected = {
            "yuanli.health.kernel.ctx": ("kernel", ["CTX"], "immediate", "normalize_context_candidate", "subject"),
            "yuanli.health.kernel.evd": ("kernel", ["CTX", "EVD"], "immediate", "emit_evd", "system_contract"),
            "yuanli.health.kernel.dec": ("kernel", ["EVD", "DEC"], "behavioral", "emit_decision_candidate", "subject"),
            "yuanli.health.experience.first-health-session": (
                "experience",
                ["CTX", "EVD", "DEC"],
                "behavioral",
                "orchestrate_decision_candidate",
                "subject",
            ),
        }
        for source_id, frozen in expected.items():
            with self.subTest(source_id=source_id):
                path = ROOT / "capabilities" / source_id / "contract.json"
                contract = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(self.validator.validate_contract(contract).errors, ())
                self.assertEqual(
                    (
                        contract["class"],
                        contract["profile_of"],
                        contract["health_clock"],
                        contract["transition_intent"],
                        contract["authority"]["final_authority"],
                    ),
                    frozen,
                )

    def test_malformed_cases_return_stable_errors_instead_of_tracebacks(self):
        malformed = {"synthetic": True, "case_id": "SYN-GS-BAD"}
        result = self.gold_slice.process_first_health_session(malformed)
        self.assertEqual(result["schema"], "gold-slice-error-v1")
        self.assertEqual(result["errors"][0]["code"], "MISSING_REQUIRED_FIELD")

    def test_nested_json_containers_in_scalar_slots_return_stable_errors(self):
        malformed = copy.deepcopy(load_cases()[0])
        malformed["evidence"] = [
            {"reference": [], "fact": {}, "source": [], "status": {}}
        ]
        malformed["candidates"] = [
            {
                "candidate_id": [],
                "label": {},
                "evidence_references": [[]],
                "dependency_blockers": [{}],
            }
        ]
        result = self.gold_slice.process_first_health_session(malformed)
        self.assertEqual(result["schema"], "gold-slice-error-v1")
        self.assertEqual(result["errors"][0]["code"], "INVALID_EVIDENCE")

    def test_non_string_object_keys_return_stable_errors(self):
        malformed = copy.deepcopy(load_cases()[0])
        malformed[7] = "not_an_inert_json_key"
        result = self.gold_slice.process_first_health_session(malformed)
        self.assertEqual(result["schema"], "gold-slice-error-v1")
        self.assertEqual(result["errors"][0]["code"], "INVALID_INERT_JSON_KEY")


if __name__ == "__main__":
    unittest.main()
