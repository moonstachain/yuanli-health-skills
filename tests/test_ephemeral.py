import contextlib
import importlib
import io
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class HostileDeepcopy:
    calls = 0

    def __deepcopy__(self, memo):
        type(self).calls += 1
        print("DEEPCOPY_HOOK_EXECUTED")
        return self


class HostileReduce:
    calls = 0

    def __reduce__(self):
        type(self).calls += 1
        print("REDUCE_HOOK_EXECUTED")
        return (dict, ())


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

    def test_context_accepts_and_recursively_clones_only_inert_json_values(self):
        value = {
            "null": None,
            "bool": True,
            "int": 7,
            "float": 1.25,
            "string": "synthetic",
            "list": [None, False, 3, 2.5, "value", {"nested": ["item"]}],
        }
        context = self.ephemeral.EphemeralSessionContext()
        context.set("json", value)
        value["list"][-1]["nested"].append("outside")
        observed = context.get("json")
        observed["list"][-1]["nested"].append("returned")
        self.assertEqual(context.get("json")["list"][-1]["nested"], ["item"])

    def test_context_rejects_non_json_values_without_executing_object_hooks(self):
        HostileDeepcopy.calls = 0
        HostileReduce.calls = 0
        stdout = io.StringIO()
        stderr = io.StringIO()
        context = self.ephemeral.EphemeralSessionContext()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            for value in (HostileDeepcopy(), {"nested": HostileReduce()}):
                with self.subTest(value=type(value).__name__):
                    with self.assertRaises(TypeError):
                        context.set("hostile", value)
            with self.assertRaises(TypeError):
                context.get("missing", HostileDeepcopy())
        self.assertEqual(HostileDeepcopy.calls, 0)
        self.assertEqual(HostileReduce.calls, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_context_rejects_non_string_keys_and_non_finite_numbers(self):
        context = self.ephemeral.EphemeralSessionContext()
        with self.assertRaises(TypeError):
            context.set("bad-key", {1: "value"})
        with self.assertRaises(TypeError):
            context.set(7, "value")
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    context.set("number", value)


if __name__ == "__main__":
    unittest.main()
