import contextlib
import copy
import importlib
import io
import os
import sys
import tempfile
import unittest

from tests._gold_support import ROOT, case_by_id, load_cases


sys.path.insert(0, str(ROOT / "src"))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        try:
            self.runner = importlib.import_module("yuanli_health_skills.runner")
            self.ephemeral = importlib.import_module("yuanli_health_skills.ephemeral")
            self.validator = importlib.import_module("yuanli_health_skills.validator")
        except ModuleNotFoundError as exc:
            self.fail(f"host-neutral Gold Slice runner is not implemented: {exc}")

    def test_runner_is_silent_file_free_and_clears_supplied_context_on_success(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        context = self.ephemeral.EphemeralSessionContext()
        context.set("preexisting", {"synthetic": True})
        with tempfile.TemporaryDirectory() as directory:
            before = set(os.listdir(directory))
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = self.runner.run_first_health_session(case_by_id("SYN-GS-026"), context=context)
            after = set(os.listdir(directory))
        self.assertEqual(result["experience_state"], "decision_candidate_ready")
        self.assertEqual(context.snapshot(), {})
        self.assertEqual(before, after)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_runner_clears_context_and_returns_error_on_failure(self):
        context = self.ephemeral.EphemeralSessionContext()
        context.set("preexisting", "synthetic")
        result = self.runner.run_first_health_session(
            {"synthetic": True, "case_id": "SYN-GS-BAD"},
            context=context,
        )
        self.assertEqual(result["schema"], "gold-slice-error-v1")
        self.assertEqual(result["errors"][0]["code"], "MISSING_REQUIRED_FIELD")
        self.assertEqual(context.snapshot(), {})

    def test_runner_rejects_non_json_input_without_executing_object_protocols(self):
        class HostileInput:
            calls = 0

            def __deepcopy__(self, memo):
                type(self).calls += 1
                raise AssertionError("hostile protocol executed")

        context = self.ephemeral.EphemeralSessionContext()
        result = self.runner.run_first_health_session(HostileInput(), context=context)
        self.assertEqual(result["errors"][0]["code"], "INVALID_INERT_JSON")
        self.assertEqual(HostileInput.calls, 0)
        self.assertEqual(context.snapshot(), {})

    def test_returned_bundles_are_recursively_isolated_across_runs(self):
        case = case_by_id("SYN-GS-026")
        first = self.runner.run_first_health_session(case)
        first["evidence_catalog"][0]["fact"] = "caller_mutation"
        first["learner_view"]["reason"] = "caller_mutation"
        second = self.runner.run_first_health_session(case)
        self.assertEqual(second["evidence_catalog"][0]["fact"], "abstract_evidence_supported_alpha")
        self.assertNotEqual(second["learner_view"]["reason"], "caller_mutation")

    def test_runner_rejects_assumptions_that_overlap_any_known_fact_source(self):
        base = case_by_id("SYN-GS-026")
        overlap_facts = {
            "goal": base["goal"],
            "constraint": base["constraints"][0],
            "supported_evidence": base["evidence"][0]["fact"],
        }
        for label, fact in overlap_facts.items():
            with self.subTest(overlap=label):
                malformed = copy.deepcopy(base)
                malformed["assumptions"].append(fact)
                result = self.runner.run_first_health_session(malformed)
                self.assertEqual(result["schema"], "gold-slice-error-v1")
                self.assertEqual(
                    result["errors"],
                    [
                        {
                            "code": "ASSUMPTION_KNOWN_OVERLAP",
                            "path": "assumptions[1]",
                        }
                    ],
                )

    def test_every_successful_runner_bundle_has_three_valid_stage_envelopes(self):
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                result = self.runner.run_first_health_session(case)
                self.assertEqual(result["schema"], "first-health-session-bundle-v1")
                self.assertEqual(set(result["stage_envelopes"]), {"ctx", "evd", "dec"})
                for envelope in result["stage_envelopes"].values():
                    self.assertEqual(self.validator.validate_envelope(envelope).errors, ())

    def test_runner_rejects_unknown_or_alias_request_and_risk_vocabulary(self):
        base = case_by_id("SYN-GS-026")
        invalid_inputs = (
            ("request_type", "diagnostic", "INVALID_REQUEST_TYPE", "request_type"),
            ("request_type", "medication-change", "INVALID_REQUEST_TYPE", "request_type"),
            ("request_type", "urgent_request", "INVALID_REQUEST_TYPE", "request_type"),
            ("risk_flags", ["clinical"], "INVALID_RISK_FLAG", "risk_flags[0]"),
            ("risk_flags", ["urgent"], "INVALID_RISK_FLAG", "risk_flags[0]"),
            ("risk_flags", ["guardrail"], "INVALID_RISK_FLAG", "risk_flags[0]"),
        )
        for field, value, code, path in invalid_inputs:
            with self.subTest(field=field, value=value):
                malformed = copy.deepcopy(base)
                malformed[field] = value
                result = self.runner.run_first_health_session(malformed)
                self.assertEqual(result["schema"], "gold-slice-error-v1")
                self.assertEqual(result["errors"], [{"code": code, "path": path}])

    def test_runner_rejects_clinical_candidate_scope_and_identity_injection(self):
        base = case_by_id("SYN-GS-026")
        variants = (
            (
                "missing_kind",
                ("candidate_kind", None),
                "INVALID_CANDIDATE_KIND",
                "candidates[0].candidate_kind",
            ),
            (
                "clinical_kind",
                ("candidate_kind", "clinical"),
                "INVALID_CANDIDATE_KIND",
                "candidates[0].candidate_kind",
            ),
            (
                "diagnosis_id",
                ("candidate_id", "diagnosis_candidate"),
                "INVALID_CANDIDATE_ID",
                "candidates[0].candidate_id",
            ),
            (
                "medication_label",
                ("label", "abstract_candidate_medication"),
                "INVALID_CANDIDATE_LABEL",
                "candidates[0].label",
            ),
            (
                "emergency_label",
                ("label", "abstract_candidate_emergency"),
                "INVALID_CANDIDATE_LABEL",
                "candidates[0].label",
            ),
        )
        for label, mutation, code, path in variants:
            with self.subTest(injection=label):
                malformed = copy.deepcopy(base)
                field, value = mutation
                if field == "candidate_kind" and value is None:
                    malformed["candidates"][0].pop(field, None)
                else:
                    malformed["candidates"][0][field] = value
                result = self.runner.run_first_health_session(malformed)
                self.assertEqual(result["schema"], "gold-slice-error-v1")
                self.assertEqual(result["errors"], [{"code": code, "path": path}])


if __name__ == "__main__":
    unittest.main()
