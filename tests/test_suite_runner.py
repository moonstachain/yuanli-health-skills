import contextlib
import copy
import importlib
import io
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
