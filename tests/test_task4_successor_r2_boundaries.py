import runpy
import sys
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


def _image_forms(token: str) -> tuple[tuple[str, str], ...]:
    return (
        ("direct image", "!" + token),
        ("whitespace before image", " \t!" + token),
        ("escaped prefix before image", "\\\\!" + token),
    )


def _replace_exact_token(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    if content.count(old) != 1:
        raise AssertionError("fixture requires one exact contract token")
    path.write_text(content.replace(old, new, 1), encoding="utf-8", newline="\n")


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


def _prefixed_relation(prefix: str, quote: str, label: str, value: str, index: int) -> str:
    return (
        f"template_{index} = {prefix}{quote}{label}: {{placeholder}}\n"
        f"  raw: {value}{quote}"
    )


class Task4SuccessorR2LinkTests(unittest.TestCase):
    def test_source_purpose_requires_an_active_inline_link_in_every_cli_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (label, replacement) in enumerate(_image_forms(CONTRACT_TOKEN)):
                with self.subTest(label=label, boundary="generation"):
                    repository = copy_repository(temporary / f"generation-{index}")
                    _replace_exact_token(
                        _source_instruction(repository),
                        CONTRACT_TOKEN,
                        replacement,
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

            for index, (label, replacement) in enumerate(_image_forms(CONTRACT_TOKEN)):
                with self.subTest(label=label, boundary="repository source"):
                    repository = copy_repository(temporary / f"repository-source-{index}")
                    package = repository / "dist/codex/yuanli-health"
                    metadata = repository / "releases/v0.1.0/release-metadata.json"
                    generate(package, root=repository, metadata=metadata)
                    reference = package / "references" / f"{SOURCE_ID}.md"
                    packaged_token = (
                        f"[`contract.json`](../contracts/capabilities/{SOURCE_ID}.json)"
                    )
                    _replace_exact_token(
                        _source_instruction(repository),
                        CONTRACT_TOKEN,
                        replacement,
                    )
                    _replace_exact_token(
                        reference,
                        packaged_token,
                        replacement.replace(CONTRACT_TOKEN, packaged_token),
                    )
                    rewrite_checksums(package)
                    rewrite_metadata_hash(package, metadata)
                    rejected = validate(
                        package,
                        root=repository,
                        metadata=metadata,
                        repository=True,
                    )
                    self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                    self.assertIn("source Markdown", rejected.stderr)

    def test_emitted_member_requires_one_active_link_and_rehash_cannot_bless_an_image(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (label, source_replacement) in enumerate(_image_forms(CONTRACT_TOKEN)):
                repository = copy_repository(temporary / f"emitted-{index}")
                package = repository / "dist/codex/yuanli-health"
                metadata = repository / "releases/v0.1.0/release-metadata.json"
                generate(package, root=repository, metadata=metadata)
                reference = package / "references" / f"{SOURCE_ID}.md"
                packaged_token = (
                    f"[`contract.json`](../contracts/capabilities/{SOURCE_ID}.json)"
                )
                emitted_replacement = source_replacement.replace(CONTRACT_TOKEN, packaged_token)
                _replace_exact_token(reference, packaged_token, emitted_replacement)
                rewrite_checksums(package)
                rewrite_metadata_hash(package, metadata)

                for repository_mode in (False, True):
                    with self.subTest(label=label, repository=repository_mode):
                        rejected = validate(
                            package,
                            root=repository,
                            metadata=metadata,
                            repository=repository_mode,
                        )
                        self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                        self.assertIn("generated Markdown structure mismatch", rejected.stderr)

    def test_generated_members_have_one_literal_active_link_and_no_exact_token_image(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "package"
            generate(package)
            for reference in sorted((package / "references").glob("*.md")):
                source_id = reference.stem
                token = f"[`contract.json`](../contracts/capabilities/{source_id}.json)"
                content = reference.read_text(encoding="utf-8")
                with self.subTest(source_id=source_id):
                    self.assertEqual(content.count(token), 1)
                    self.assertNotIn("!" + token, content)


class Task4SuccessorR2QuoteTests(unittest.TestCase):
    @staticmethod
    def _finding_classes():
        return runpy.run_path(
            str(PUBLIC_SCAN),
            run_name="scan_public_content_successor_r2_test",
        )["finding_classes"]

    def test_every_identifier_prefix_preserves_single_and_double_multiline_relations(self):
        finding_classes = self._finding_classes()
        prefixes = ("x", "unknownPrefix", "_unknown9")
        quotes = ("'", '"')
        for relation_index, (label, value, finding_class) in enumerate(_relations()):
            for prefix in prefixes:
                for quote in quotes:
                    with self.subTest(
                        finding_class=finding_class,
                        prefix=prefix,
                        quote=quote,
                    ):
                        content = (
                            _prefixed_relation(prefix, quote, label, value, relation_index)
                            + "\n"
                        ).encode("utf-8")
                        self.assertIn(finding_class, finding_classes("prefix.txt", content))

    def test_prefixed_multiline_relations_cover_all_classes_current_history_and_projection(self):
        prefix_quote_matrix = (
            ("x", "'"),
            ("unknownPrefix", "'"),
            ("x", '"'),
            ("_unknown9", '"'),
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = copy_repository(Path(directory))
            git(repository, "init", "-q")
            probe = "\n".join(
                _prefixed_relation(
                    *prefix_quote_matrix[index % len(prefix_quote_matrix)],
                    label,
                    value,
                    index,
                )
                for index, (label, value, _finding_class) in enumerate(_relations())
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
            commit_all(repository, "identifier-prefixed quote matrix")
            commit = git(repository, "rev-parse", "HEAD").stdout.strip()

            for mode, diagnostic in (
                ("--check-current", "PHI_CURRENT"),
                ("--check-history", "PHI_HISTORY"),
            ):
                result = run_script(PUBLIC_SCAN, "--root", repository, mode)
                output = result.stdout + result.stderr
                with self.subTest(mode=mode):
                    self.assertNotEqual(result.returncode, 0, output)
                    for _label, value, finding_class in _relations():
                        self.assertIn(finding_class, output)
                        self.assertNotIn(value, output)
                    for relative in (
                        f"capabilities/{SOURCE_ID}/instructions.md",
                        f"dist/codex/yuanli-health/references/{SOURCE_ID}.md",
                    ):
                        expected = f"{diagnostic}:patient_identifier:"
                        if diagnostic == "PHI_HISTORY":
                            expected += commit + ":"
                        self.assertIn(expected + relative, output)

    def test_complete_inert_prefixed_quotes_and_ordinary_apostrophes_remain_negative(self):
        finding_classes = self._finding_classes()
        label = "Subject" + "Identifier"
        for prefix in ("x", "unknownPrefix", "_unknown9"):
            for quote in ("'", '"'):
                with self.subTest(prefix=prefix, quote=quote):
                    inert = (
                        f"template = {prefix}{quote}{label}: {{placeholder}}\n"
                        f"{quote}\n"
                    ).encode("utf-8")
                    self.assertEqual(finding_classes("inert.txt", inert), ())

        measurement_label = "Blood" + " pressure"
        ordinary = (
            "don't change ordinary apostrophes or contractions\n"
            "rendered = f'ordinary {value}'\n"
            + 'observed = "'
            + measurement_label
            + ': " + "value"\n'
        ).encode("utf-8")
        self.assertEqual(finding_classes("ordinary.py", ordinary), ())


class Task4SuccessorR2NoFollowTests(unittest.TestCase):
    def test_every_external_symlink_ancestor_depth_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repository = copy_repository(temporary / "source")
            for depth in (1, 2, 3):
                real_anchor = temporary / f"real-{depth}"
                suffix = tuple(f"level-{index}" for index in range(depth - 1))
                real_package = real_anchor.joinpath(*suffix, "package")
                metadata = temporary / f"metadata-{depth}.json"
                generate(real_package, root=repository, metadata=metadata)

                lexical_anchor = temporary / f"lexical-{depth}"
                lexical_anchor.symlink_to(real_anchor, target_is_directory=True)
                selected = lexical_anchor.joinpath(*suffix, "package")
                commands = (
                    (
                        "generator check",
                        run_script(
                            GENERATOR,
                            "--root",
                            repository,
                            "--output",
                            selected,
                            "--check",
                        ),
                    ),
                    ("standalone validator", validate(selected, root=repository, metadata=metadata)),
                    (
                        "repository validator",
                        validate(
                            selected,
                            root=repository,
                            metadata=metadata,
                            repository=True,
                        ),
                    ),
                )
                for boundary, result in commands:
                    with self.subTest(depth=depth, boundary=boundary):
                        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertIn("root must be a real directory", result.stderr)

                sentinel = real_package / "sentinel.txt"
                sentinel.write_text(f"depth-{depth}-must-remain\n", encoding="utf-8")
                before = regular_files(real_package)
                write_result = run_script(
                    GENERATOR,
                    "--root",
                    repository,
                    "--output",
                    selected,
                )
                with self.subTest(depth=depth, boundary="generator write"):
                    self.assertNotEqual(
                        write_result.returncode,
                        0,
                        write_result.stdout + write_result.stderr,
                    )
                    self.assertIn("root must be a real directory", write_result.stderr)
                with self.subTest(depth=depth, boundary="target snapshot"):
                    self.assertEqual(regular_files(real_package), before)

    def test_ancestor_substitution_after_initial_check_is_rejected_at_write_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repository = copy_repository(temporary / "source")
            safe_anchor = temporary / "safe-anchor"
            safe_package = safe_anchor / "package"
            generate(safe_package, root=repository)
            safe_before = regular_files(safe_package)

            attacker_anchor = temporary / "attacker-anchor"
            attacker_package = attacker_anchor / "package"
            generate(attacker_package, root=repository)
            sentinel = attacker_package / "sentinel.txt"
            sentinel.write_text("attacker-target-must-remain\n", encoding="utf-8")
            attacker_before = regular_files(attacker_package)
            parked_anchor = temporary / "parked-safe-anchor"

            sys.path.insert(0, str(GENERATOR.parent))
            try:
                namespace = runpy.run_path(
                    str(GENERATOR),
                    run_name="generate_codex_adapter_substitution_test",
                )
                main = namespace["main"]
                globals_namespace = main.__globals__
                build_package = globals_namespace["build_package"]

                def substituting_build(root: Path):
                    files, registry = build_package(root)
                    safe_anchor.rename(parked_anchor)
                    safe_anchor.symlink_to(attacker_anchor, target_is_directory=True)
                    return files, registry

                globals_namespace["build_package"] = substituting_build
                result = main(
                    [
                        "--root",
                        str(repository),
                        "--output",
                        str(safe_package),
                    ]
                )
            finally:
                sys.path.remove(str(GENERATOR.parent))

            self.assertNotEqual(result, 0)
            self.assertEqual(regular_files(attacker_package), attacker_before)
            self.assertEqual(regular_files(parked_anchor / "package"), safe_before)


if __name__ == "__main__":
    unittest.main()
