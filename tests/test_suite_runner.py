import contextlib
import copy
import importlib
import io
import json
import os
import tempfile
import unittest

from tests._full_support import ROOT, case_by_id


class SuiteRunnerTests(unittest.TestCase):
    def setUp(self):
        try:
            self.runner = importlib.import_module("yuanli_health_skills.suite_runner")
            self.ephemeral = importlib.import_module("yuanli_health_skills.ephemeral")
        except ModuleNotFoundError as exc:
            self.fail(f"Task 3 ephemeral suite runner is missing: {exc}")

    def test_runner_routes_executes_silently_and_clears_context(self):
        context = self.ephemeral.EphemeralSessionContext()
        context.set("preexisting", "SYN-PREEXISTING")
        stdout, stderr = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            before = set(os.listdir(directory))
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = self.runner.run_full_suite(case_by_id("SYN-FS-041"), context=context)
            after = set(os.listdir(directory))
        self.assertEqual(result["candidate_state"], "experiment_candidate_ready")
        self.assertEqual(context.snapshot(), {})
        self.assertEqual(before, after)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_runner_returns_stable_errors_and_clears_context(self):
        context = self.ephemeral.EphemeralSessionContext()
        context.set("preexisting", "SYN-PREEXISTING")
        malformed = copy.deepcopy(case_by_id("SYN-FS-041"))
        malformed["artifacts"] = {}
        result = self.runner.run_full_suite(malformed, context=context)
        self.assertEqual(result["errors"][0]["code"], "MISSING_REQUIRED_ARTIFACT")
        self.assertEqual(context.snapshot(), {})

    def test_runner_is_total_for_json_container_source_ids(self):
        for source_id in ([], {}):
            with self.subTest(source_id=source_id):
                context = self.ephemeral.EphemeralSessionContext()
                malformed = copy.deepcopy(case_by_id("SYN-FS-041"))
                malformed["capability_source_id"] = source_id
                result = self.runner.run_full_suite(malformed, context=context)
                self.assertEqual(result["errors"], [{"code": "UNSUPPORTED_CAPABILITY", "path": "capability_source_id"}])
                self.assertEqual(context.snapshot(), {})

    def test_runner_rejects_kernel_and_meta_sources_at_the_route_boundary(self):
        for case_id in ("SYN-FS-001", "SYN-FS-091", "SYN-FS-101", "SYN-FS-111"):
            with self.subTest(case_id=case_id):
                context = self.ephemeral.EphemeralSessionContext()
                result = self.runner.run_full_suite(case_by_id(case_id), context=context)
                self.assertEqual(result["schema"], "full-suite-error-v1")
                self.assertEqual(result["errors"], [{"code": "NO_ROUTE", "path": "capability_source_id"}])
                self.assertEqual(result["output_artifacts"], {})
                self.assertIs(result["transition_executed"], False)
                self.assertEqual(context.snapshot(), {})

    def test_runner_rejects_known_facts_redeclared_as_unknown(self):
        probes = (
            ("SYN-FS-041", "decision_candidate_id", None, "UNKNOWN_KNOWN_OVERLAP"),
            ("SYN-FS-061", "visit_questions", 0, "UNKNOWN_KNOWN_OVERLAP"),
            ("SYN-FS-111", "synthetic_case_count", None, "NO_ROUTE"),
        )
        for case_id, artifact_key, item_index, code in probes:
            with self.subTest(case_id=case_id, artifact_key=artifact_key):
                malformed = case_by_id(case_id)
                value = malformed["artifacts"][artifact_key]
                fact = value[item_index] if item_index is not None else str(value)
                malformed["declared_unknowns"] = [fact]
                result = self.runner.run_full_suite(malformed)
                expected_path = "declared_unknowns[0]" if code == "UNKNOWN_KNOWN_OVERLAP" else "capability_source_id"
                self.assertEqual(result["errors"], [{"code": code, "path": expected_path}])
                self.assertIs(result["transition_executed"], False)

        for case_id in ("SYN-FS-041", "SYN-FS-061"):
            with self.subTest(disjoint_positive=case_id):
                self.assertEqual(self.runner.run_full_suite(case_by_id(case_id))["schema"], "full-suite-candidate-v1")

    def test_runner_returns_stable_error_and_clears_context_for_deep_inert_json(self):
        context = self.ephemeral.EphemeralSessionContext()
        context.set("preexisting", "SYN-PREEXISTING")
        malformed = case_by_id("SYN-FS-041")
        malformed["expected"] = json.loads("[" * 512 + "null" + "]" * 512)
        try:
            result = self.runner.run_full_suite(malformed, context=context)
        except RecursionError as exc:
            self.fail(f"runner boundary leaked RecursionError: {exc}")
        self.assertEqual(result["errors"], [{"code": "INERT_JSON_DEPTH_EXCEEDED", "path": "$"}])
        self.assertIs(result["transition_executed"], False)
        self.assertEqual(context.snapshot(), {})

        normal = case_by_id("SYN-FS-041")
        normal["expected"] = json.loads("[" * 32 + "null" + "]" * 32)
        self.assertEqual(self.runner.run_full_suite(normal)["schema"], "full-suite-candidate-v1")

    def test_runner_clinical_request_and_risk_matrix_is_durable(self):
        variants = (
            ("diagnosis", []),
            ("medication_change", []),
            ("emergency", []),
            ("non_clinical", ["clinical_escalation"]),
            ("non_clinical", ["emergency"]),
        )
        forbidden = {"diagnosis", "prescription", "medication_change", "appointment_state", "booking", "provider", "payment"}
        for case_id, doctor in (("SYN-FS-041", False), ("SYN-FS-061", True)):
            for request_type, risk_flags in variants:
                with self.subTest(case_id=case_id, request_type=request_type, risk_flags=risk_flags):
                    case = case_by_id(case_id)
                    case["request_type"] = request_type
                    case["risk_flags"] = risk_flags
                    result = self.runner.run_full_suite(case)
                    self.assertEqual(result["authority_gate"], "RED")
                    if doctor:
                        self.assertEqual(result["schema"], "full-suite-candidate-v1")
                        self.assertEqual(set(result["output_artifacts"]), {"visit_questions", "guardrails"})
                    else:
                        self.assertEqual(result["schema"], "full-suite-error-v1")
                        self.assertEqual(result["output_artifacts"], {})
                    self.assertTrue(forbidden.isdisjoint(result["output_artifacts"]))
                    serialized_output = json.dumps(result["output_artifacts"], ensure_ascii=False).lower()
                    self.assertTrue(
                        all(term not in serialized_output for term in forbidden),
                        serialized_output,
                    )

    def test_runner_clears_context_when_processor_raises(self):
        context = self.ephemeral.EphemeralSessionContext()
        context.set("preexisting", "SYN-PREEXISTING")
        original = self.runner.process_full_suite_case
        try:
            def raise_synthetic(_case):
                raise RuntimeError("synthetic processor failure")
            self.runner.process_full_suite_case = raise_synthetic
            with self.assertRaisesRegex(RuntimeError, "synthetic processor failure"):
                self.runner.run_full_suite(case_by_id("SYN-FS-041"), context=context)
        finally:
            self.runner.process_full_suite_case = original
        self.assertEqual(context.snapshot(), {})

    def test_results_are_recursively_isolated_across_runs(self):
        case = case_by_id("SYN-FS-061")
        first = self.runner.run_full_suite(case)
        first["output_artifacts"]["visit_questions"][0] = "CALLER-MUTATION"
        second = self.runner.run_full_suite(case)
        self.assertEqual(second["output_artifacts"]["visit_questions"], case["artifacts"]["visit_questions"])


if __name__ == "__main__":
    unittest.main()
