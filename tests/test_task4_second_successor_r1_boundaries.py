import contextlib
import io
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._adapter_support import (
    GENERATOR,
    PUBLIC_SCAN,
    ROOT,
    VALIDATOR,
    SOURCE_IDS,
    copy_repository,
    generate,
    regular_files,
)
from tests.test_public_content_scan import commit_all, git


SOURCE_ID = "yuanli.health.kernel.ctx"


def _relations() -> tuple[tuple[str, str, str], ...]:
    return (
        ("Subject" + "Identifier", "opaque" + "-identifier", "patient_identifier"),
        ("medical" + "RecordNumber", "opaque" + "-record", "medical_record_identifier"),
        ("contact" + "Email", "opaque" + "-contact", "email_address"),
        ("contact" + "Phone", "opaque" + "-phone", "phone_number"),
        ("First" + "Name", "opaque" + "-name", "person_name"),
        ("Postal" + "Address", "opaque" + "-address", "postal_address"),
        ("Birth" + "Date", "opaque" + "-date", "date_of_birth"),
        ("Sp" + "O2", "opaque" + "-reading", "health_measurement"),
    )


def _quoted_probe(prefix: str, quote: str, label: str, value: str) -> str:
    return (
        f"template = {prefix}{quote}ordinary first physical line\n"
        f"{label}: {{placeholder}}\n"
        f"  raw: {value}{quote}"
    )


@contextlib.contextmanager
def _real_temporary_directory():
    real_base = Path(os.path.realpath(tempfile.gettempdir()))
    with tempfile.TemporaryDirectory(dir=real_base) as directory:
        yield Path(directory)


@contextlib.contextmanager
def _script_namespace(script: Path, run_name: str):
    sys.path.insert(0, str(script.parent))
    try:
        yield runpy.run_path(str(script), run_name=run_name)
    finally:
        sys.path.remove(str(script.parent))


def _call_main(main, arguments: list[str]) -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return main(arguments)


def _descriptor_count() -> int | None:
    for directory in (Path("/dev/fd"), Path("/proc/self/fd")):
        if directory.is_dir():
            return len(os.listdir(directory))
    return None


class Task4SecondSuccessorR1PrivacyTests(unittest.TestCase):
    @staticmethod
    def _finding_classes():
        return runpy.run_path(
            str(PUBLIC_SCAN),
            run_name="scan_public_content_second_successor_r1_test",
        )["finding_classes"]

    def test_ordinary_first_line_cannot_hide_any_multiline_relation_for_either_quote(self):
        finding_classes = self._finding_classes()
        for label, value, expected_class in _relations():
            for quote in ("'", '"'):
                with self.subTest(expected_class=expected_class, quote=quote):
                    content = _quoted_probe(
                        "unknownPrefix_9",
                        quote,
                        label,
                        value,
                    ).encode("utf-8")
                    self.assertIn(expected_class, finding_classes("probe.txt", content))

    def test_later_populated_continuations_cover_source_reference_current_and_history(self):
        with _real_temporary_directory() as temporary:
            repository = copy_repository(temporary)
            git(repository, "init", "-q")
            expected_paths: dict[str, tuple[str, str]] = {}
            for index, (label, value, expected_class) in enumerate(_relations()):
                source_id = SOURCE_IDS[index]
                quote = "'" if index % 2 == 0 else '"'
                probe = _quoted_probe("identifierPrefix", quote, label, value)
                instruction = repository / "capabilities" / source_id / "instructions.md"
                instruction.write_text(
                    instruction.read_text(encoding="utf-8") + "\n" + probe + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
                expected_paths[expected_class] = (source_id, probe)

            package = repository / "dist/codex/yuanli-health"
            metadata = repository / "releases/v0.1.0/release-metadata.json"
            generate(package, root=repository, metadata=metadata)
            for expected_class, (source_id, probe) in expected_paths.items():
                reference = package / "references" / f"{source_id}.md"
                with self.subTest(expected_class=expected_class, boundary="projection"):
                    self.assertIn("ordinary first physical line", reference.read_text(encoding="utf-8"))
                    self.assertIn(probe, reference.read_text(encoding="utf-8"))

            commit_all(repository, "second successor multiline privacy matrix")
            commit = git(repository, "rev-parse", "HEAD").stdout.strip()
            for mode, diagnostic in (
                ("--check-current", "PHI_CURRENT"),
                ("--check-history", "PHI_HISTORY"),
            ):
                result = subprocess.run(
                    [sys.executable, str(PUBLIC_SCAN), "--root", str(repository), mode],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                output = result.stdout + result.stderr
                with self.subTest(mode=mode):
                    self.assertNotEqual(result.returncode, 0, output)
                    for expected_class, (source_id, _probe) in expected_paths.items():
                        self.assertIn(expected_class, output)
                        expected = f"{diagnostic}:{expected_class}:"
                        if diagnostic == "PHI_HISTORY":
                            expected += commit + ":"
                        self.assertIn(
                            expected + f"capabilities/{source_id}/instructions.md",
                            output,
                        )
                        self.assertIn(
                            expected + f"dist/codex/yuanli-health/references/{source_id}.md",
                            output,
                        )
                    for _label, value, _expected_class in _relations():
                        self.assertNotIn(value, output)

    def test_complete_inert_extents_and_apostrophe_controls_remain_negative(self):
        finding_classes = self._finding_classes()
        label = "Subject" + "Identifier"
        for quote in ("'", '"'):
            inert = (
                f"template = unknownPrefix{quote}ordinary first physical line\n"
                f"{label}: {{placeholder}}\n"
                f"{quote}\n"
            ).encode("utf-8")
            with self.subTest(quote=quote):
                self.assertEqual(finding_classes("inert.txt", inert), ())
        ordinary = (
            "don't classify a contraction\n"
            "rendered = f'ordinary {value}'\n"
            "plain = prefix'ordinary first and only line'\n"
        ).encode("utf-8")
        self.assertEqual(finding_classes("ordinary.py", ordinary), ())


class Task4SecondSuccessorR1AnchoredIoTests(unittest.TestCase):
    def test_generator_substitution_at_first_clear_cannot_touch_substitute(self):
        with _real_temporary_directory() as temporary:
            repository = copy_repository(temporary / "source")
            safe_anchor = temporary / "safe-anchor"
            safe_package = safe_anchor / "package"
            generate(safe_package, root=repository)
            attacker_anchor = temporary / "attacker-anchor"
            attacker_package = attacker_anchor / "package"
            generate(attacker_package, root=repository)
            sentinel = attacker_package / "sentinel.txt"
            sentinel.write_bytes(b"substitute sentinel must remain byte-identical\n")
            attacker_before = regular_files(attacker_package)
            parked_anchor = temporary / "parked-safe-anchor"

            with _script_namespace(GENERATOR, "generator_second_successor_substitution") as namespace:
                main = namespace["main"]
                globals_namespace = main.__globals__
                clear_output = globals_namespace["_clear_output"]
                substituted = False

                def substituting_clear(output):
                    nonlocal substituted
                    if not substituted:
                        safe_anchor.rename(parked_anchor)
                        safe_anchor.symlink_to(attacker_anchor, target_is_directory=True)
                        substituted = True
                    return clear_output(output)

                globals_namespace["_clear_output"] = substituting_clear
                before_descriptors = _descriptor_count()
                result = _call_main(
                    main,
                    ["--root", str(repository), "--output", str(safe_package)],
                )
                after_descriptors = _descriptor_count()

            self.assertTrue(substituted)
            self.assertIn(result, (0, 1))
            self.assertEqual(regular_files(attacker_package), attacker_before)
            self.assertEqual(sentinel.read_bytes(), attacker_before["sentinel.txt"])
            if before_descriptors is not None:
                self.assertEqual(after_descriptors, before_descriptors)

    def test_validator_substitution_at_first_traversal_reads_only_anchored_tree(self):
        for repository_mode in (False, True):
            with self.subTest(repository_mode=repository_mode):
                with _real_temporary_directory() as temporary:
                    repository = copy_repository(temporary / "source")
                    safe_anchor = temporary / "safe-anchor"
                    safe_package = safe_anchor / "package"
                    metadata = repository / "releases/v0.1.0/release-metadata.json"
                    generate(safe_package, root=repository, metadata=metadata)
                    attacker_anchor = temporary / "attacker-anchor"
                    attacker_package = attacker_anchor / "package"
                    generate(attacker_package, root=repository)
                    sentinel = attacker_package / "sentinel.txt"
                    sentinel.write_bytes(b"invalid substitute inventory must remain unchanged\n")
                    attacker_before = regular_files(attacker_package)
                    parked_anchor = temporary / "parked-safe-anchor"

                    with _script_namespace(VALIDATOR, f"validator_second_successor_{repository_mode}") as namespace:
                        main = namespace["main"]
                        globals_namespace = main.__globals__
                        inspect_package = globals_namespace["_inspect"]
                        substituted = False

                        def substituting_inspect(package):
                            nonlocal substituted
                            if not substituted:
                                safe_anchor.rename(parked_anchor)
                                safe_anchor.symlink_to(attacker_anchor, target_is_directory=True)
                                substituted = True
                            return inspect_package(package)

                        globals_namespace["_inspect"] = substituting_inspect
                        arguments = [
                            "--root",
                            str(repository),
                            "--package",
                            str(safe_package),
                        ]
                        if repository_mode:
                            arguments.extend(("--metadata", str(metadata), "--check-repository"))
                        before_descriptors = _descriptor_count()
                        result = _call_main(main, arguments)
                        after_descriptors = _descriptor_count()

                    self.assertTrue(substituted)
                    self.assertEqual(result, 0)
                    self.assertEqual(regular_files(attacker_package), attacker_before)
                    self.assertEqual(sentinel.read_bytes(), attacker_before["sentinel.txt"])
                    if before_descriptors is not None:
                        self.assertEqual(after_descriptors, before_descriptors)

    def test_success_and_rejected_link_boundaries_do_not_leak_descriptors(self):
        with _real_temporary_directory() as temporary:
            repository = copy_repository(temporary / "source")
            package = temporary / "package"
            generate(package, root=repository)
            package_link = temporary / "package-link"
            package_link.symlink_to(package, target_is_directory=True)
            baseline = _descriptor_count()
            if baseline is None:
                self.skipTest("platform does not expose a process descriptor directory")

            for index in range(8):
                with self.subTest(index=index, boundary="generator success"):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(GENERATOR),
                            "--root",
                            str(repository),
                            "--output",
                            str(package),
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                with self.subTest(index=index, boundary="validator rejected link"):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(VALIDATOR),
                            "--root",
                            str(repository),
                            "--package",
                            str(package_link),
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(_descriptor_count(), baseline)


class Task4SecondSuccessorR1TemporaryRootTests(unittest.TestCase):
    def test_child_fixture_uses_real_base_when_platform_default_is_a_symlink_alias(self):
        with _real_temporary_directory() as temporary:
            real_base = temporary / "real-base"
            real_base.mkdir()
            alias = temporary / "default-temp-alias"
            alias.symlink_to(real_base, target_is_directory=True)
            environment = os.environ.copy()
            environment.update({"TMPDIR": str(alias), "TMP": str(alias), "TEMP": str(alias)})
            child = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import tempfile; import tests; "
                        "fixture = tempfile.mkdtemp(prefix='fixture-'); print(fixture)"
                    ),
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
            fixture = Path(child.stdout.strip())
            try:
                self.assertEqual(fixture.parent.parent, real_base)
                self.assertTrue(fixture.parent.name.startswith("yuanli-health-tests-"))
                self.assertFalse(fixture.parent.is_symlink())
            finally:
                if fixture.is_dir():
                    fixture.rmdir()


if __name__ == "__main__":
    unittest.main()
