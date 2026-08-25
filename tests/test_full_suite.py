import copy
import importlib
import json
import sys
import unittest

from tests._full_support import ROOT, case_by_id, load_cases, supplied_artifact_facts


sys.path.insert(0, str(ROOT / "src"))


class FullSuiteTests(unittest.TestCase):
    def setUp(self):
        try:
            self.full_suite = importlib.import_module("yuanli_health_skills.full_suite")
            self.validator = importlib.import_module("yuanli_health_skills.validator")
        except ModuleNotFoundError as exc:
            self.fail(f"Task 3 deterministic dispatcher is missing: {exc}")

    def test_all_cases_match_independent_expected_state_or_error(self):
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                result = self.full_suite.process_full_suite_case(case)
                expected = case["expected"]
                self.assertEqual(result["schema"], expected["schema"])
                for key in (
                    "candidate_state", "authority_gate", "transition_intent",
                    "transition_executed",
                    "canonical_write", "persistence", "registry_admission",
                    "release_published", "health_outcome_claimed",
                    "clinical_effectiveness_claimed", "runtime_observed",
                ):
                    self.assertEqual(result[key], expected[key])
                if expected["schema"] == "full-suite-error-v1":
                    self.assertEqual(
                        result["errors"],
                        [{"code": expected["error_code"], "path": expected["error_path"]}],
                    )
                else:
                    self.assertEqual(set(result["output_artifacts"]), set(expected["output_artifact_keys"]))
                    self.assertEqual(self.validator.validate_envelope(result["envelope"]).errors, ())

    def test_success_envelopes_preserve_all_and_only_supplied_facts_unknowns_and_assumptions(self):
        for case in load_cases():
            if case["expected"]["schema"] != "full-suite-candidate-v1":
                continue
            with self.subTest(case_id=case["case_id"]):
                result = self.full_suite.process_full_suite_case(case)
                envelope = result["envelope"]
                known = {entry["fact"] for entry in envelope["known"]}
                self.assertEqual(known, supplied_artifact_facts(case))
                self.assertEqual(envelope["unknown"], case["declared_unknowns"])
                self.assertEqual(envelope["assumption"], case["assumptions"])
                self.assertTrue(all(entry["evidence_reference"].startswith("artifact:") for entry in envelope["known"]))

    def test_declared_unknowns_cannot_overlap_scalar_question_or_count_facts(self):
        probes = (
            ("SYN-FS-001", "decision_candidate_id", None),
            ("SYN-FS-061", "visit_questions", 1),
            ("SYN-FS-111", "synthetic_case_count", None),
        )
        for case_id, artifact_key, item_index in probes:
            with self.subTest(case_id=case_id, artifact_key=artifact_key):
                malformed = case_by_id(case_id)
                value = malformed["artifacts"][artifact_key]
                fact = value[item_index] if item_index is not None else str(value)
                malformed["declared_unknowns"] = ["SYN-DISJOINT-UNKNOWN", fact, fact]
                result = self.full_suite.process_full_suite_case(malformed)
                self.assertEqual(result["schema"], "full-suite-error-v1")
                self.assertEqual(result["candidate_state"], None)
                self.assertEqual(result["output_artifacts"], {})
                self.assertIs(result["transition_executed"], False)
                self.assertEqual(
                    result["errors"],
                    [{"code": "UNKNOWN_KNOWN_OVERLAP", "path": "declared_unknowns[1]"}],
                )

        for case_id in ("SYN-FS-001", "SYN-FS-061", "SYN-FS-111"):
            with self.subTest(disjoint_positive=case_id):
                result = self.full_suite.process_full_suite_case(case_by_id(case_id))
                self.assertEqual(result["schema"], "full-suite-candidate-v1")

    def test_direct_boundary_returns_stable_error_for_json_parser_accepted_deep_input(self):
        deep_value = json.loads("[" * 512 + "null" + "]" * 512)
        malformed = case_by_id("SYN-FS-001")
        malformed["expected"] = deep_value
        try:
            first = self.full_suite.process_full_suite_case(malformed)
            second = self.full_suite.process_full_suite_case(malformed)
        except RecursionError as exc:
            self.fail(f"direct boundary leaked RecursionError: {exc}")
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], "full-suite-error-v1")
        self.assertEqual(first["errors"], [{"code": "INERT_JSON_DEPTH_EXCEEDED", "path": "$"}])
        self.assertIs(first["transition_executed"], False)

        normal = case_by_id("SYN-FS-001")
        normal["expected"] = json.loads("[" * 32 + "null" + "]" * 32)
        self.assertEqual(
            self.full_suite.process_full_suite_case(normal)["schema"],
            "full-suite-candidate-v1",
        )

    def test_expected_fixture_is_not_an_implementation_input(self):
        case = case_by_id("SYN-FS-001")
        baseline = self.full_suite.process_full_suite_case(case)
        hostile = copy.deepcopy(case)
        hostile["expected"] = {"schema": "hostile-oracle", "release_published": True}
        self.assertEqual(self.full_suite.process_full_suite_case(hostile), baseline)

    def test_state_machine_forbids_promotions_and_silent_downstream_outputs(self):
        for case_id in ("SYN-FS-010", "SYN-FS-020", "SYN-FS-030", "SYN-FS-040", "SYN-FS-050", "SYN-FS-060", "SYN-FS-080", "SYN-FS-090"):
            with self.subTest(case_id=case_id):
                result = self.full_suite.process_full_suite_case(case_by_id(case_id))
                self.assertEqual(result["schema"], "full-suite-error-v1")
                self.assertEqual(result["errors"][0]["code"], "MISSING_REQUIRED_ARTIFACT")

        weekly = self.full_suite.process_full_suite_case(case_by_id("SYN-FS-051"))
        outcome_review = self.full_suite.process_full_suite_case(case_by_id("SYN-FS-071"))
        experiment = self.full_suite.process_full_suite_case(case_by_id("SYN-FS-041"))
        self.assertNotIn("out_candidate_id", weekly["output_artifacts"])
        self.assertNotIn("lrn_candidate_id", outcome_review["output_artifacts"])
        self.assertEqual(list(experiment["output_artifacts"]), ["wpk_candidate_id", "act_candidate_id"])

    def test_clinical_and_appointment_boundaries_are_closed(self):
        for case in load_cases():
            if case["request_type"] != "diagnosis":
                continue
            with self.subTest(case_id=case["case_id"]):
                result = self.full_suite.process_full_suite_case(case)
                if case["capability_source_id"].endswith("doctor-visit-prep"):
                    self.assertEqual(result["authority_gate"], "RED")
                    self.assertEqual(result["output_artifacts"]["visit_questions"], case["artifacts"]["visit_questions"])
                    self.assertEqual(len(result["output_artifacts"]["guardrails"]), 2)
                else:
                    self.assertEqual(result["errors"][0]["code"], "CLINICAL_ESCALATION_REQUIRED")

        delegated = self.full_suite.process_full_suite_case(case_by_id("SYN-FS-070"))
        self.assertEqual(delegated["authority_gate"], "YELLOW")
        self.assertEqual(delegated["output_artifacts"]["delegation"], "yuanli-medical-appointment-operator")
        self.assertTrue({"booking", "provider", "payment", "appointment_state"}.isdisjoint(delegated["output_artifacts"]))

    def test_direct_clinical_request_and_risk_matrix_is_durable(self):
        variants = (
            ("diagnosis", []),
            ("medication_change", []),
            ("emergency", []),
            ("non_clinical", ["clinical_escalation"]),
            ("non_clinical", ["emergency"]),
        )
        forbidden = {"diagnosis", "prescription", "medication_change", "appointment_state", "booking", "provider", "payment"}
        for case_id, doctor in (("SYN-FS-001", False), ("SYN-FS-061", True)):
            for request_type, risk_flags in variants:
                with self.subTest(case_id=case_id, request_type=request_type, risk_flags=risk_flags):
                    case = case_by_id(case_id)
                    case["request_type"] = request_type
                    case["risk_flags"] = risk_flags
                    result = self.full_suite.process_full_suite_case(case)
                    self.assertEqual(result["authority_gate"], "RED")
                    if doctor:
                        self.assertEqual(result["schema"], "full-suite-candidate-v1")
                        self.assertEqual(set(result["output_artifacts"]), {"visit_questions", "guardrails"})
                    else:
                        self.assertEqual(result["schema"], "full-suite-error-v1")
                        self.assertEqual(result["output_artifacts"], {})
                        self.assertIs(result["transition_executed"], False)
                    self.assertTrue(forbidden.isdisjoint(result["output_artifacts"]))
                    serialized_output = json.dumps(result["output_artifacts"], ensure_ascii=False).lower()
                    self.assertTrue(
                        all(term not in serialized_output for term in forbidden),
                        serialized_output,
                    )

    def test_meta_outputs_never_promote_admit_release_or_claim_human_acceptance(self):
        for case in load_cases()[90:120]:
            result = self.full_suite.process_full_suite_case(case)
            if result["schema"] != "full-suite-candidate-v1":
                continue
            with self.subTest(case_id=case["case_id"]):
                self.assertIs(result["registry_admission"], False)
                self.assertIs(result["release_published"], False)
                self.assertNotIn("registry_capability_id", result["output_artifacts"])
                self.assertNotIn("human_accepted", result["output_artifacts"])

    def test_malformed_inputs_are_total_strict_and_stable(self):
        invalid = (
            (None, "INVALID_CASE", "$"),
            ([], "INVALID_CASE", "$"),
            ({}, "MISSING_REQUIRED_FIELD", "schema"),
        )
        for value, code, path in invalid:
            with self.subTest(value=repr(value)):
                first = self.full_suite.process_full_suite_case(value)
                second = self.full_suite.process_full_suite_case(value)
                self.assertEqual(first, second)
                self.assertEqual(first["schema"], "full-suite-error-v1")
                self.assertEqual(first["errors"][0], {"code": code, "path": path})

        base = case_by_id("SYN-FS-001")
        mutations = (
            ("request_type", "diagnostic", "INVALID_REQUEST_TYPE", "request_type"),
            ("request_type", "Appointment_Logistics", "INVALID_REQUEST_TYPE", "request_type"),
            ("risk_flags", ["clinical"], "INVALID_RISK_FLAG", "risk_flags[0]"),
            ("category", [], "INVALID_CATEGORY", "category"),
            ("category", {}, "INVALID_CATEGORY", "category"),
        )
        for field, value, code, path in mutations:
            malformed = copy.deepcopy(base)
            malformed[field] = value
            result = self.full_suite.process_full_suite_case(malformed)
            self.assertEqual(result["errors"], [{"code": code, "path": path}])


if __name__ == "__main__":
    unittest.main()
