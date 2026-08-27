import tempfile
import time
import unittest
from pathlib import Path

from tests._adapter_support import (
    GENERATOR,
    PUBLIC_SCAN,
    copy_repository,
    generate,
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


def _relation_line(count: int) -> str:
    return "; ".join(f"ordinary_field_{index}: abstract_value_{index}" for index in range(count)) + "\n"


class Task4R5MarkdownGrammarTests(unittest.TestCase):
    def test_source_rejects_escaped_code_literal_and_container_only_contract_candidates(self):
        replacements = (
            ("escaped opener", "\\[`contract.json`](contract.json)"),
            ("code literal only", "`[contract.json](contract.json)`"),
            ("blockquote", "\n> " + CONTRACT_TOKEN),
            ("list", "\n- " + CONTRACT_TOKEN),
            ("indented code block", "\n    " + CONTRACT_TOKEN),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (label, replacement) in enumerate(replacements):
                with self.subTest(label=label):
                    repository = copy_repository(temporary / f"candidate-{index}")
                    instruction = _source_instruction(repository)
                    content = instruction.read_text(encoding="utf-8")
                    self.assertEqual(content.count(CONTRACT_TOKEN), 1)
                    instruction.write_text(
                        content.replace(CONTRACT_TOKEN, replacement, 1),
                        encoding="utf-8",
                    )
                    rejected = run_script(
                        GENERATOR,
                        "--root",
                        repository,
                        "--output",
                        temporary / f"package-{index}",
                    )
                    self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                    self.assertIn("source Markdown link policy", rejected.stderr)

    def test_source_rejects_every_nonclosed_literal_link_and_fence_form(self):
        attacks = (
            ("backslash escape", "\\*escaped emphasis candidate*"),
            ("unequal backtick runs", "``<https://example.invalid/x>```x`"),
            ("unterminated inline code", "`unterminated"),
            ("multiline inline code", "`first line\nsecond line`"),
            ("backtick fence", "```json\n{}\n```"),
            ("invalid info fence", "```json extra\n{}\n``` trailing"),
            ("tilde fence", "~~~text\nplain\n~~~"),
            ("URI autolink", "<https://example.invalid/x>"),
            ("email autolink", "<nobody" + "@" + "example.invalid>"),
            ("image", "![member](contract.json)"),
            ("reference block", "> [member]\n>\n> [member]: contract.json"),
            ("list reference", "- [member][]\n- [member]: contract.json"),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (label, attack) in enumerate(attacks):
                with self.subTest(label=label):
                    repository = copy_repository(temporary / f"attack-{index}")
                    instruction = _source_instruction(repository)
                    instruction.write_text(
                        instruction.read_text(encoding="utf-8") + "\n" + attack + "\n",
                        encoding="utf-8",
                    )
                    rejected = run_script(
                        GENERATOR,
                        "--root",
                        repository,
                        "--output",
                        temporary / f"rejected-{index}",
                    )
                    self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                    self.assertIn("source Markdown link policy", rejected.stderr)

    def test_source_promoted_invalid_literals_fail_standalone_and_repository_validation(self):
        attacks = (
            ("plain backslash", "\\*escaped candidate*"),
            ("unequal backticks", "``<https://example.invalid/x>```x`"),
            ("invalid opener", "```json extra\n{}\n``` trailing"),
            ("tilde fence", "~~~text\nplain\n~~~"),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (label, attack) in enumerate(attacks):
                with self.subTest(label=label):
                    repository = copy_repository(temporary / f"promotion-{index}")
                    package = repository / "dist/codex/yuanli-health"
                    metadata = repository / "releases/v0.1.0/release-metadata.json"
                    generate(package, root=repository, metadata=metadata)
                    instruction = _source_instruction(repository)
                    instruction.write_text(
                        instruction.read_text(encoding="utf-8") + "\n" + attack + "\n",
                        encoding="utf-8",
                    )
                    reference = package / "references" / f"{SOURCE_ID}.md"
                    reference.write_text(
                        reference.read_text(encoding="utf-8") + "\n" + attack + "\n",
                        encoding="utf-8",
                    )
                    rewrite_checksums(package)
                    rewrite_metadata_hash(package, metadata)
                    for repository_mode in (False, True):
                        rejected = validate(
                            package,
                            root=repository,
                            metadata=metadata,
                            repository=repository_mode,
                        )
                        output = rejected.stdout + rejected.stderr
                        self.assertNotEqual(rejected.returncode, 0, output)
                        self.assertIn("Markdown", output)


class Task4R5ScannerTests(unittest.TestCase):
    def test_multiline_sensitive_parents_cover_all_classes_and_source_projection(self):
        labels_and_shapes = (
            ("patient" + "_id", "  opaque-identifier", "patient_identifier"),
            ("medical" + "RecordNumber", "  raw: opaque-record", "medical_record_identifier"),
            ("Email" + "Address", "  - opaque-contact", "email_address"),
            ("phone" + "Number", "\n  # retained separator\n  value: opaque-phone", "phone_number"),
            ("Full" + "Name", "  person:\n    - opaque-name", "person_name"),
            ("Home" + "Address", "  mapping:\n    raw: opaque-address", "postal_address"),
            ("Date" + "OfBirth", "  parts:\n    - opaque-date", "date_of_birth"),
            ("Heart" + "Rate", "  measurement:\n    value: opaque-reading", "health_measurement"),
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = copy_repository(Path(directory))
            git(repository, "init", "-q")
            probe = "\n".join(label + ":\n" + shape for label, shape, _ in labels_and_shapes)
            instruction = _source_instruction(repository)
            instruction.write_text(
                instruction.read_text(encoding="utf-8") + "\n" + probe + "\n",
                encoding="utf-8",
            )
            package = repository / "dist/codex/yuanli-health"
            metadata = repository / "releases/v0.1.0/release-metadata.json"
            generate(package, root=repository, metadata=metadata)
            reference = package / "references" / f"{SOURCE_ID}.md"
            self.assertIn(probe, reference.read_text(encoding="utf-8"))
            commit_all(repository, "multiline source projection")
            commit = git(repository, "rev-parse", "HEAD").stdout.strip()
            identifier_finding = "patient" + "_identifier"

            for mode, prefix in (("--check-current", "PHI_CURRENT"), ("--check-history", "PHI_HISTORY")):
                result = run_script(PUBLIC_SCAN, "--root", repository, mode)
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, output)
                for _, _, finding_class in labels_and_shapes:
                    self.assertIn(finding_class, output)
                for relative in (
                    f"capabilities/{SOURCE_ID}/instructions.md",
                    f"dist/codex/yuanli-health/references/{SOURCE_ID}.md",
                ):
                    if prefix == "PHI_CURRENT":
                        self.assertIn(f"{prefix}:{identifier_finding}:{relative}", output)
                    else:
                        self.assertIn(f"{prefix}:{identifier_finding}:{commit}:{relative}", output)
                for private_fragment in ("opaque-identifier", "opaque-record", "opaque-contact", "opaque-reading"):
                    self.assertNotIn(private_fragment, output)

    def test_json_depth_boundary_malformed_and_deep_inputs_are_total_in_both_modes(self):
        maximum_depth = 128
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            accepted_repository = temporary / "accepted"
            accepted_repository.mkdir()
            git(accepted_repository, "init", "-q")
            (accepted_repository / "boundary.json").write_text(
                "[" * maximum_depth + "0" + "]" * maximum_depth + "\n",
                encoding="utf-8",
            )
            commit_all(accepted_repository, "accepted JSON depth")
            for mode in ("--check-current", "--check-history"):
                accepted = run_script(PUBLIC_SCAN, "--root", accepted_repository, mode)
                self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

            for label, content in (
                ("deep", "[" * (maximum_depth + 1) + "0" + "]" * (maximum_depth + 1) + "\n"),
                ("malformed", "{\"ordinary\": [1, 2}\n"),
            ):
                with self.subTest(label=label):
                    repository = temporary / label
                    repository.mkdir()
                    git(repository, "init", "-q")
                    (repository / f"{label}.json").write_text(content, encoding="utf-8")
                    commit_all(repository, label + " JSON")
                    for mode in ("--check-current", "--check-history"):
                        rejected = run_script(PUBLIC_SCAN, "--root", repository, mode)
                        output = rejected.stdout + rejected.stderr
                        self.assertNotEqual(rejected.returncode, 0, output)
                        self.assertIn("SCAN_ERROR:repository:", output)
                        self.assertNotIn("Traceback", output)
                        self.assertNotIn("ordinary", output)

    def test_relation_work_has_a_deterministic_limit_in_current_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q")
            (repository / "relations.txt").write_text(_relation_line(513), encoding="utf-8")
            commit_all(repository, "relation budget")
            for mode in ("--check-current", "--check-history"):
                rejected = run_script(PUBLIC_SCAN, "--root", repository, mode)
                output = rejected.stdout + rejected.stderr
                self.assertNotEqual(rejected.returncode, 0, output)
                self.assertIn("SCAN_ERROR:repository:ScanBudgetError", output)
                self.assertNotIn("abstract_value_512", output)

    def test_relation_classification_scales_linearly_below_the_budget(self):
        namespace: dict[str, object] = {"__name__": "scan_public_content_for_test"}
        source = PUBLIC_SCAN.read_text(encoding="utf-8")
        exec(compile(source, str(PUBLIC_SCAN), "exec"), namespace)  # noqa: S102 - real module under test
        finding_classes = namespace["finding_classes"]

        timings: dict[int, float] = {}
        for count in (100, 200, 400):
            content = _relation_line(count).encode("utf-8")
            samples = []
            for _ in range(2):
                started = time.perf_counter()
                self.assertEqual(finding_classes("relations.txt", content), ())
                samples.append(time.perf_counter() - started)
            timings[count] = min(samples)
        self.assertLessEqual(timings[400], timings[200] * 3.5 + 0.01, timings)


class Task4R5ChecksumManifestTests(unittest.TestCase):
    def test_noncanonical_checksum_bytes_fail_both_modes_after_metadata_rehash(self):
        def mutate(label: str, canonical: bytes) -> bytes:
            lines = canonical.splitlines(keepends=True)
            if label == "missing final LF":
                return canonical[:-1]
            if label == "CRLF":
                return canonical.replace(b"\n", b"\r\n")
            if label == "extra blank line":
                return canonical + b"\n"
            if label == "single separator space":
                return canonical.replace(b"  ", b" ", 1)
            if label == "uppercase digest":
                return lines[0][:64].upper() + lines[0][64:] + b"".join(lines[1:])
            if label == "reordered":
                return lines[1] + lines[0] + b"".join(lines[2:])
            if label == "duplicate":
                return lines[0] + canonical
            raise AssertionError(label)

        labels = (
            "missing final LF",
            "CRLF",
            "extra blank line",
            "single separator space",
            "uppercase digest",
            "reordered",
            "duplicate",
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, label in enumerate(labels):
                with self.subTest(label=label):
                    repository = copy_repository(temporary / f"manifest-{index}")
                    package = repository / "dist/codex/yuanli-health"
                    metadata = repository / "releases/v0.1.0/release-metadata.json"
                    generate(package, root=repository, metadata=metadata)
                    manifest = package / "SHA256SUMS"
                    manifest.write_bytes(mutate(label, manifest.read_bytes()))
                    rewrite_metadata_hash(package, metadata)
                    for repository_mode in (False, True):
                        rejected = validate(
                            package,
                            root=repository,
                            metadata=metadata,
                            repository=repository_mode,
                        )
                        output = rejected.stdout + rejected.stderr
                        self.assertNotEqual(rejected.returncode, 0, output)
                        self.assertIn("non-canonical SHA256SUMS", output)


if __name__ == "__main__":
    unittest.main()
