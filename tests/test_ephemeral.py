import contextlib
import importlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class EphemeralTests(unittest.TestCase):
    def setUp(self):
        try:
            self.ephemeral = importlib.import_module("yuanli_health_skills.ephemeral")
        except ModuleNotFoundError as exc:
            self.fail(f"ephemeral session context is not implemented: {exc}")

    def test_context_is_isolated_and_does_not_persist_or_print(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            before = set(os.listdir(directory))
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                first = self.ephemeral.EphemeralSessionContext()
                second = self.ephemeral.EphemeralSessionContext()
                first.set("synthetic", {"status": "candidate"})
                observed = first.get("synthetic")
                absent = second.get("synthetic")
                first.clear()
            after = set(os.listdir(directory))
        self.assertEqual(observed, {"status": "candidate"})
        self.assertIsNone(absent)
        self.assertEqual(first.snapshot(), {})
        self.assertEqual(before, after)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_context_copies_values_at_its_boundary(self):
        source = {"items": ["synthetic"]}
        context = self.ephemeral.EphemeralSessionContext()
        context.set("candidate", source)
        source["items"].append("mutated-outside")
        observed = context.get("candidate")
        observed["items"].append("mutated-return")
        self.assertEqual(context.get("candidate"), {"items": ["synthetic"]})


if __name__ == "__main__":
    unittest.main()
