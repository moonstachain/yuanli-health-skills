import contextlib
import importlib
import io
import os
import sys
import tempfile
import unittest

from tests._gold_support import ROOT, case_by_id


sys.path.insert(0, str(ROOT / "src"))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        try:
            self.runner = importlib.import_module("yuanli_health_skills.runner")
            self.ephemeral = importlib.import_module("yuanli_health_skills.ephemeral")
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


if __name__ == "__main__":
    unittest.main()
