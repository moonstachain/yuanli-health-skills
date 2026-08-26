import runpy
import tempfile
import unittest
from pathlib import Path

from tests._adapter_support import (
    GENERATOR,
    PUBLIC_SCAN,
    copy_repository,
    generate,
    regular_files,
    rewrite_checksums,
    rewrite_metadata_hash,
    run_script,
    validate,
)
from tests.test_public_content_scan import commit_all, git


CONTRACT_TOKEN = "[`contract.json`](contract.json)"
SOURCE_ID = "yuanli.health.kernel.ctx"


def _source_instruction(repository: Path) -> Path:
    return repository / "capabilities" / SOURCE_ID / "instructions.md"


def _move_contract_token(instruction: Path, attack: str, *, title: bool = False) -> None:
    content = instruction.read_text(encoding="utf-8")
    if content.count(CONTRACT_TOKEN) != 1:
        raise AssertionError("fixture requires one source contract token")
    content = content.replace(CONTRACT_TOKEN, "`contract.json`", 1)
    if title:
        first, remainder = content.split("\n", 1)
        content = first + " " + attack + "\n" + remainder
    else:
        content = content + "\n" + attack + "\n"
    instruction.write_text(content, encoding="utf-8", newline="\n")


def _multiline_relations() -> tuple[tuple[str, str, str], ...]:
    return (
        ("Subject" + "Identifier", "opaque" + "-identifier", "patient_identifier"),
        ("medical" + "_record_identifier", "opaque" + "-record", "medical_record_identifier"),
        ("contact" + "Email", "opaque" + "-contact", "email_address"),
        ("contact" + "Phone", "opaque" + "-phone", "phone_number"),
        ("First" + "Name", "opaque" + "-name", "person_name"),
        ("Postal" + "Address", "opaque" + "-address", "postal_address"),
        ("Birth" + "Date", "opaque" + "-date", "date_of_birth"),
        ("Sp" + "O2", "opaque" + "-reading", "health_measurement"),
    )


class Task4SuccessorR1Boundaries(unittest.TestCase):
    def test_contract_token_is_rejected_outside_the_one_purpose_paragraph_position(self):
        attacks = (
            ("source title", CONTRACT_TOKEN, True),
            ("two-space unordered continuation", "- outer\n  " + CONTRACT_TOKEN, False),
            ("four-space unordered continuation", "- outer\n    " + CONTRACT_TOKEN, False),
            ("lazy unordered continuation", "- outer\n" + CONTRACT_TOKEN, False),
            ("nested unordered continuation", "- outer\n  - inner\n    " + CONTRACT_TOKEN, False),
            ("ordered continuation", "1. outer\n   " + CONTRACT_TOKEN, False),
            ("nested ordered lazy continuation", "1. outer\n   1. inner\n" + CONTRACT_TOKEN, False),
            ("blockquote", "> " + CONTRACT_TOKEN, False),
            ("inline code", "`" + CONTRACT_TOKEN + "`", False),
            ("fenced code", "```text\n" + CONTRACT_TOKEN + "\n```", False),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (label, attack, title) in enumerate(attacks):
                with self.subTest(label=label):
                    repository = copy_repository(temporary / f"location-{index}")
                    _move_contract_token(_source_instruction(repository), attack, title=title)
                    rejected = run_script(
                        GENERATOR,
                        "--root",
                        repository,
                        "--output",
                        temporary / f"rejected-{index}",
                    )
                    self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                    self.assertIn("source Markdown link policy", rejected.stderr)

    def test_generated_reference_has_one_fixed_link_and_rehash_cannot_bless_title_duplication(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = copy_repository(Path(directory))
            package = repository / "dist/codex/yuanli-health"
            metadata = repository / "releases/v0.1.0/release-metadata.json"
            generate(package, root=repository, metadata=metadata)
            reference = package / "references" / f"{SOURCE_ID}.md"
            packaged_token = f"[`contract.json`](../contracts/capabilities/{SOURCE_ID}.json)"
            self.assertEqual(reference.read_text(encoding="utf-8").count(packaged_token), 1)

            source = _source_instruction(repository)
            source_content = source.read_text(encoding="utf-8")
            source_title, source_remainder = source_content.split("\n", 1)
            source.write_text(
                source_title
                + " "
                + CONTRACT_TOKEN
                + "\n"
                + source_remainder.replace(CONTRACT_TOKEN, "`contract.json`", 1),
                encoding="utf-8",
                newline="\n",
            )

            content = reference.read_text(encoding="utf-8")
            marker = "## Platform-neutral operation\n\n"
            prefix, found, projection = content.partition(marker)
            self.assertEqual(found, marker)
            projection = projection.replace(packaged_token, "`contract.json`", 1)
            title = source_title.removeprefix("# ")
            if projection.startswith("# "):
                first, remainder = projection.split("\n", 1)
                projection = first + " " + packaged_token + "\n" + remainder
            else:
                projection = "# " + title + " " + packaged_token + "\n\n" + projection
            generated_title = "# " + title + "\n"
            prefix = prefix.replace(generated_title, "# " + title + " " + packaged_token + "\n", 1)
            reference.write_text(prefix + marker + projection, encoding="utf-8", newline="\n")
            self.assertEqual(reference.read_text(encoding="utf-8").count(packaged_token), 2)
            rewrite_checksums(package)
            rewrite_metadata_hash(package, metadata)

            for repository_mode in (False, True):
                with self.subTest(repository=repository_mode):
                    rejected = validate(
                        package,
                        root=repository,
                        metadata=metadata,
                        repository=repository_mode,
                    )
                    self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                    self.assertIn("Markdown", rejected.stderr)

    def test_source_bytes_are_exact_at_generation_and_repository_correspondence(self):
        mutations = (
            ("CRLF", lambda raw: raw.replace(b"\n", b"\r\n")),
            ("bare CR", lambda raw: raw.replace(b"\n", b"\r", 1)),
            ("NUL", lambda raw: raw[:-1] + b"\x00\n"),
            ("invalid UTF-8", lambda raw: raw[:-1] + b"\xff\n"),
            ("missing final LF", lambda raw: raw[:-1]),
            ("extra final blank line", lambda raw: raw + b"\n"),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (label, mutate) in enumerate(mutations):
                repository = copy_repository(temporary / f"bytes-{index}")
                package = repository / "dist/codex/yuanli-health"
                metadata = repository / "releases/v0.1.0/release-metadata.json"
                generate(package, root=repository, metadata=metadata)
                instruction = _source_instruction(repository)
                instruction.write_bytes(mutate(instruction.read_bytes()))

                generation = run_script(
                    GENERATOR,
                    "--root",
                    repository,
                    "--output",
                    temporary / f"byte-output-{index}",
                )
                with self.subTest(label=label, boundary="generation"):
                    self.assertNotEqual(generation.returncode, 0, generation.stdout + generation.stderr)
                    self.assertNotIn("Traceback", generation.stderr)

                correspondence = validate(
                    package,
                    root=repository,
                    metadata=metadata,
                    repository=True,
                )
                with self.subTest(label=label, boundary="repository"):
                    self.assertNotEqual(
                        correspondence.returncode,
                        0,
                        correspondence.stdout + correspondence.stderr,
                    )
                    self.assertNotIn("Traceback", correspondence.stderr)

    def test_package_root_symlinks_are_rejected_without_target_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repository = copy_repository(temporary / "root-link")
            target = temporary / "valid-target"
            metadata = temporary / "release-metadata.json"
            generate(target, root=repository, metadata=metadata)
            package_link = temporary / "package-link"
            package_link.symlink_to(target, target_is_directory=True)

            commands = (
                (
                    "generator check",
                    run_script(
                        GENERATOR,
                        "--root",
                        repository,
                        "--output",
                        package_link,
                        "--check",
                    ),
                ),
                ("standalone validator", validate(package_link, root=repository, metadata=metadata)),
                (
                    "repository validator",
                    validate(
                        package_link,
                        root=repository,
                        metadata=metadata,
                        repository=True,
                    ),
                ),
            )
            for label, result in commands:
                with self.subTest(label=label):
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("root must be a real directory", result.stderr)

            explicit_target = temporary / "explicit-target"
            explicit_package = explicit_target / "package"
            explicit_metadata = explicit_target / "metadata.json"
            generate(explicit_package, root=repository, metadata=explicit_metadata)
            explicit_parent_link = temporary / "explicit-parent-link"
            explicit_parent_link.symlink_to(explicit_target, target_is_directory=True)
            escaped_package = explicit_parent_link / "package"
            escaped_metadata = explicit_parent_link / "metadata.json"
            ancestor_commands = (
                (
                    "explicit ancestor generator check",
                    run_script(
                        GENERATOR,
                        "--root",
                        repository,
                        "--output",
                        escaped_package,
                        "--check",
                    ),
                ),
                (
                    "explicit ancestor standalone validator",
                    validate(escaped_package, root=repository, metadata=escaped_metadata),
                ),
                (
                    "explicit ancestor repository validator",
                    validate(
                        escaped_package,
                        root=repository,
                        metadata=escaped_metadata,
                        repository=True,
                    ),
                ),
            )
            for label, result in ancestor_commands:
                with self.subTest(label=label):
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("root must be a real directory", result.stderr)

            write_target = temporary / "write-target"
            generate(write_target, root=repository)
            sentinel = write_target / "sentinel.txt"
            sentinel.write_text("must remain unchanged\n", encoding="utf-8")
            before = regular_files(write_target)
            write_link = temporary / "write-link"
            write_link.symlink_to(write_target, target_is_directory=True)
            write_result = run_script(
                GENERATOR,
                "--root",
                repository,
                "--output",
                write_link,
            )
            with self.subTest(label="generator write"):
                self.assertNotEqual(write_result.returncode, 0, write_result.stdout + write_result.stderr)
            with self.subTest(label="write target unchanged"):
                self.assertEqual(regular_files(write_target), before)

            ancestor_repository = copy_repository(temporary / "ancestor-link")
            external = temporary / "outside-output"
            external.mkdir()
            (ancestor_repository / "dist").symlink_to(external, target_is_directory=True)
            ancestor_result = run_script(GENERATOR, "--root", ancestor_repository)
            with self.subTest(label="unsafe ancestor"):
                self.assertNotEqual(
                    ancestor_result.returncode,
                    0,
                    ancestor_result.stdout + ancestor_result.stderr,
                )
            with self.subTest(label="ancestor target unchanged"):
                self.assertEqual(tuple(external.iterdir()), ())

    def test_structured_json_rejects_nul_and_invalid_utf8_in_current_and_history(self):
        malformed_bytes = (
            ("NUL", b'{"ordinary":"redaction-probe"' + b"\x00" + b"}\n"),
            ("invalid UTF-8", b'{"ordinary":"redaction-probe"' + b"\xff" + b"}\n"),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (label, content) in enumerate(malformed_bytes):
                repository = temporary / f"json-{index}"
                repository.mkdir()
                git(repository, "init", "-q")
                (repository / "malformed.json").write_bytes(content)
                commit_all(repository, label)
                for mode in ("--check-current", "--check-history"):
                    with self.subTest(label=label, mode=mode):
                        rejected = run_script(PUBLIC_SCAN, "--root", repository, mode)
                        output = rejected.stdout + rejected.stderr
                        self.assertNotEqual(rejected.returncode, 0, output)
                        self.assertIn("SCAN_ERROR:repository:ScanFormatError", output)
                        self.assertNotIn("redaction-probe", output)
                        self.assertNotIn("Traceback", output)

    def test_balanced_multiline_quotes_are_classified_in_both_modes_and_source_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = copy_repository(Path(directory))
            git(repository, "init", "-q")
            probe_lines = []
            for index, (label, value, _finding_class) in enumerate(_multiline_relations()):
                quote = "'" if index % 2 == 0 else '"'
                probe_lines.append(
                    f"template_{index}: {quote}{label}:\n  raw: {value}{quote}"
                )
            probe = "\n".join(probe_lines)
            instruction = _source_instruction(repository)
            instruction.write_text(
                instruction.read_text(encoding="utf-8") + "\n" + probe + "\n",
                encoding="utf-8",
                newline="\n",
            )
            package = repository / "dist/codex/yuanli-health"
            metadata = repository / "releases/v0.1.0/release-metadata.json"
            generate(package, root=repository, metadata=metadata)
            reference = package / "references" / f"{SOURCE_ID}.md"
            self.assertIn(probe, reference.read_text(encoding="utf-8"))
            commit_all(repository, "balanced multiline quote probes")
            commit = git(repository, "rev-parse", "HEAD").stdout.strip()

            for mode, prefix in (("--check-current", "PHI_CURRENT"), ("--check-history", "PHI_HISTORY")):
                result = run_script(PUBLIC_SCAN, "--root", repository, mode)
                output = result.stdout + result.stderr
                with self.subTest(mode=mode):
                    self.assertNotEqual(result.returncode, 0, output)
                    for _label, value, finding_class in _multiline_relations():
                        self.assertIn(finding_class, output)
                        self.assertNotIn(value, output)
                    for relative in (
                        f"capabilities/{SOURCE_ID}/instructions.md",
                        f"dist/codex/yuanli-health/references/{SOURCE_ID}.md",
                    ):
                        expected = f"{prefix}:patient_identifier:"
                        if prefix == "PHI_HISTORY":
                            expected += commit + ":"
                        self.assertIn(expected + relative, output)

    def test_label_window_below_at_and_above_is_total_for_all_classes_and_propagation(self):
        finding_classes = runpy.run_path(
            str(PUBLIC_SCAN),
            run_name="scan_public_content_successor_test",
        )["finding_classes"]
        for label, _value, finding_class in _multiline_relations():
            at_spaces = 256 - len(label)
            for boundary, spaces in (
                ("below", at_spaces - 1),
                ("at", at_spaces),
                ("above", at_spaces + 1),
            ):
                with self.subTest(finding_class=finding_class, boundary=boundary):
                    content = (label + " " * spaces + ": opaque_value\n").encode("utf-8")
                    try:
                        findings = finding_classes("boundary.txt", content)
                    except ValueError as exc:
                        self.assertEqual(type(exc).__name__, "ScanBudgetError")
                    else:
                        self.assertIn(finding_class, findings)

        with tempfile.TemporaryDirectory() as directory:
            repository = copy_repository(Path(directory))
            git(repository, "init", "-q")
            probe = "\n".join(
                label + " " * (257 - len(label)) + ": opaque_value"
                for label, _value, _finding_class in _multiline_relations()
            )
            instruction = _source_instruction(repository)
            instruction.write_text(
                instruction.read_text(encoding="utf-8") + "\n" + probe + "\n",
                encoding="utf-8",
                newline="\n",
            )
            package = repository / "dist/codex/yuanli-health"
            metadata = repository / "releases/v0.1.0/release-metadata.json"
            generate(package, root=repository, metadata=metadata)
            reference = package / "references" / f"{SOURCE_ID}.md"
            self.assertIn(probe, reference.read_text(encoding="utf-8"))
            commit_all(repository, "label boundary source projection")
            commit = git(repository, "rev-parse", "HEAD").stdout.strip()

            for mode, prefix in (("--check-current", "PHI_CURRENT"), ("--check-history", "PHI_HISTORY")):
                result = run_script(PUBLIC_SCAN, "--root", repository, mode)
                output = result.stdout + result.stderr
                with self.subTest(mode=mode):
                    self.assertNotEqual(result.returncode, 0, output)
                    if "ScanBudgetError" not in output:
                        for _label, _value, finding_class in _multiline_relations():
                            self.assertIn(finding_class, output)
                        for relative in (
                            f"capabilities/{SOURCE_ID}/instructions.md",
                            f"dist/codex/yuanli-health/references/{SOURCE_ID}.md",
                        ):
                            expected = f"{prefix}:patient_identifier:"
                            if prefix == "PHI_HISTORY":
                                expected += commit + ":"
                            self.assertIn(expected + relative, output)
                    else:
                        self.assertIn("SCAN_ERROR:repository:ScanBudgetError", output)

    def test_prefixed_python_quotes_do_not_leak_across_physical_lines(self):
        finding_classes = runpy.run_path(
            str(PUBLIC_SCAN),
            run_name="scan_public_content_prefixed_quote_test",
        )["finding_classes"]
        measurement_label = "Blood" + " pressure"
        content = (
            "rendered = f'ordinary {value}'\n"
            + 'observed = "'
            + measurement_label
            + ': " + "value"\n'
        ).encode("utf-8")
        self.assertEqual(finding_classes("prefixed-string.py", content), ())


if __name__ == "__main__":
    unittest.main()
