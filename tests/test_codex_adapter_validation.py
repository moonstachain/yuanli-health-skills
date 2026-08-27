import json
import os
import tempfile
import unittest
from pathlib import Path

from tests._adapter_support import (
    ROOT,
    copy_repository,
    generate,
    json_document,
    rewrite_checksums,
    rewrite_metadata_hash,
    validate,
)


class CodexAdapterValidationTests(unittest.TestCase):
    def _assert_self_consistent_markdown_rejected(self, repository: Path, attack: str) -> None:
        package = repository / "dist/codex/yuanli-health"
        metadata = repository / "releases/v0.1.0/release-metadata.json"
        generate(package, root=repository, metadata=metadata)
        skill = package / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\n" + attack + "\n", encoding="utf-8")
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
            self.assertIn("generated Markdown", output)

    def test_all_uri_schemes_and_multiline_inline_links_are_rejected_after_rehash(self):
        attacks = (
            ("https", "[external](https://example.invalid/x)"),
            ("http", "[external](http://example.invalid/x)"),
            ("mailto", "[external](mailto:" + "private" + "@" + "example.invalid)"),
            ("file", "[external](file:///etc/passwd)"),
            ("ftp", "[external](ftp://example.invalid/x)"),
            ("custom", "[external](custom+scheme:value)"),
            ("https autolink", "<https://example.invalid/x>"),
            ("mailto autolink", "<mailto:" + "private" + "@" + "example.invalid>"),
            ("multiline label", "[missing\ncontract](contracts/missing.json)"),
            ("multiline destination", "[missing](contracts/\nmissing.json)"),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (label, attack) in enumerate(attacks):
                with self.subTest(label=label):
                    repository = copy_repository(temporary / f"inline-{index}")
                    self._assert_self_consistent_markdown_rejected(
                        repository,
                        attack,
                    )

    def test_multiline_and_escaped_reference_grammar_is_rejected_after_rehash(self):
        attacks = (
            ("next-line shortcut", "[dead]\n\n[dead]:\n  references/missing.md"),
            ("next-line full", "[label][dead]\n\n[dead]:\n  references/missing.md"),
            ("next-line collapsed", "[dead][]\n\n[dead]:\n  references/missing.md"),
            ("escaped shortcut", "[de\\]ad]\n\n[de\\]ad]: references/missing.md"),
            ("escaped next-line", "[de\\]ad]\n\n[de\\]ad]:\n  references/missing.md"),
            ("multiline image", "![diagram\nalt](references/yuanli.health.kernel.ctx.md)"),
            ("shortcut image", "![diagram][ctx]\n\n[ctx]: references/yuanli.health.kernel.ctx.md"),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (label, attack) in enumerate(attacks):
                with self.subTest(label=label):
                    repository = copy_repository(temporary / f"reference-{index}")
                    self._assert_self_consistent_markdown_rejected(
                        repository,
                        attack,
                    )

    def test_container_reference_forms_and_bare_email_autolink_are_rejected_after_rehash(self):
        email_autolink = "<nobody" + "@" + "example.invalid>"
        attacks = (
            ("blockquote shortcut", "> [dead]\n>\n> [dead]: references/missing.md"),
            ("list shortcut", "- [dead]\n- [dead]: references/missing.md"),
            ("blockquote full", "> [label][dead]\n>\n> [dead]: references/missing.md"),
            ("list collapsed", "- [dead][]\n- [dead]: references/missing.md"),
            ("blockquote escaped", "> [de\\]ad]\n>\n> [de\\]ad]: references/missing.md"),
            ("list multiline definition", "- [dead]\n- [dead]:\n    references/missing.md"),
            ("bare email autolink", email_autolink),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (label, attack) in enumerate(attacks):
                with self.subTest(label=label):
                    repository = copy_repository(temporary / f"container-{index}")
                    self._assert_self_consistent_markdown_rejected(
                        repository,
                        attack,
                    )

    def test_repository_rejects_any_rehashed_root_or_reference_byte_mismatch(self):
        mutations = (
            ("SKILL.md", "\nBenign-looking but non-generated prose.\n"),
            (
                "references/yuanli.health.kernel.ctx.md",
                "\nLink-like prose [without a destination] must not become generated truth.\n",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (relative, addition) in enumerate(mutations):
                with self.subTest(relative=relative):
                    repository = copy_repository(temporary / f"byte-proof-{index}")
                    package = repository / "dist/codex/yuanli-health"
                    metadata = repository / "releases/v0.1.0/release-metadata.json"
                    generate(package, root=repository, metadata=metadata)
                    target = package / relative
                    target.write_text(target.read_text(encoding="utf-8") + addition, encoding="utf-8")
                    rewrite_checksums(package)
                    rewrite_metadata_hash(package, metadata)
                    rejected = validate(
                        package,
                        root=repository,
                        metadata=metadata,
                        repository=True,
                    )
                    output = rejected.stdout + rejected.stderr
                    self.assertNotEqual(rejected.returncode, 0, output)
                    self.assertIn("generated Markdown byte mismatch", output)

    def test_local_target_failures_reject_standalone_and_repository_after_rehash(self):
        inline_attacks = (
            ("missing", "[missing](references/missing.md)"),
            ("absolute", "[absolute](/etc/passwd)"),
            ("traversal", "[outside](../../outside.md)"),
            ("empty", "[empty]()"),
            ("fragment-only", "[fragment](#section)"),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (label, attack) in enumerate(inline_attacks):
                with self.subTest(label=label):
                    repository = copy_repository(temporary / f"local-{index}")
                    self._assert_self_consistent_markdown_rejected(repository, attack)

            repository = copy_repository(temporary / "wrong-member")
            package = repository / "dist/codex/yuanli-health"
            metadata = repository / "releases/v0.1.0/release-metadata.json"
            generate(package, root=repository, metadata=metadata)
            reference = package / "references/yuanli.health.kernel.ctx.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "](../contracts/capabilities/yuanli.health.kernel.ctx.json)",
                    "](../contracts/capabilities/yuanli.health.kernel.evd.json)",
                    1,
                ),
                encoding="utf-8",
            )
            rewrite_checksums(package)
            rewrite_metadata_hash(package, metadata)
            for repository_mode in (False, True):
                rejected = validate(package, root=repository, metadata=metadata, repository=repository_mode)
                self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                self.assertIn("generated Markdown", rejected.stderr)

            repository = copy_repository(temporary / "nonregular")
            package = repository / "dist/codex/yuanli-health"
            metadata = repository / "releases/v0.1.0/release-metadata.json"
            generate(package, root=repository, metadata=metadata)
            reference = package / "references/yuanli.health.kernel.ctx.md"
            reference.unlink()
            reference.symlink_to(repository / "capabilities/yuanli.health.kernel.ctx/instructions.md")
            rewrite_checksums(package)
            rewrite_metadata_hash(package, metadata)
            for repository_mode in (False, True):
                rejected = validate(package, root=repository, metadata=metadata, repository=repository_mode)
                self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                self.assertIn("symlink forbidden", rejected.stderr)

    def test_reference_style_collapsed_shortcut_and_images_are_explicitly_rejected_after_rehash(self):
        attacks = (
            ("missing definition target", "[missing][dead]\n\n[dead]: references/missing.md"),
            ("absolute definition target", "[absolute][root]\n\n[root]: /etc/passwd"),
            ("traversal definition target", "[outside][up]\n\n[up]: ../../outside.md"),
            (
                "wrong member definition target",
                "[wrong contract][member]\n\n[member]: contracts/capabilities/yuanli.health.kernel.evd.json",
            ),
            (
                "valid target is still unsupported reference syntax",
                "[reference][ctx]\n\n[ctx]: references/yuanli.health.kernel.ctx.md",
            ),
            ("collapsed reference", "[ctx][]\n\n[ctx]: references/yuanli.health.kernel.ctx.md"),
            ("shortcut reference", "[ctx]\n\n[ctx]: references/yuanli.health.kernel.ctx.md"),
            ("inline image", "![diagram](references/yuanli.health.kernel.ctx.md)"),
            ("reference image", "![diagram][ctx]\n\n[ctx]: references/yuanli.health.kernel.ctx.md"),
            ("definition only", "[ctx]: references/yuanli.health.kernel.ctx.md"),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, (label, attack) in enumerate(attacks):
                with self.subTest(label=label):
                    repository = copy_repository(temporary / f"repository-{index}")
                    package = repository / "dist/codex/yuanli-health"
                    metadata = repository / "releases/v0.1.0/release-metadata.json"
                    generate(package, root=repository, metadata=metadata)
                    skill = package / "SKILL.md"
                    skill.write_text(skill.read_text(encoding="utf-8") + "\n" + attack + "\n", encoding="utf-8")
                    rewrite_checksums(package)
                    rewrite_metadata_hash(package, metadata)
                    rejected = validate(package, root=repository, metadata=metadata, repository=True)
                    output = rejected.stdout + rejected.stderr
                    self.assertNotEqual(rejected.returncode, 0, output)
                    self.assertIn("generated Markdown", output)

    def test_reference_style_link_to_non_regular_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = copy_repository(Path(directory))
            package = repository / "dist/codex/yuanli-health"
            metadata = repository / "releases/v0.1.0/release-metadata.json"
            generate(package, root=repository, metadata=metadata)
            reference = package / "references/yuanli.health.kernel.ctx.md"
            reference.unlink()
            reference.symlink_to(repository / "capabilities/yuanli.health.kernel.ctx/instructions.md")
            skill = package / "SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8")
                + "\n[nonregular][ctx]\n\n[ctx]: references/yuanli.health.kernel.ctx.md\n",
                encoding="utf-8",
            )
            rewrite_checksums(package)
            rewrite_metadata_hash(package, metadata)
            rejected = validate(package, root=repository, metadata=metadata, repository=True)
            output = rejected.stdout + rejected.stderr
            self.assertNotEqual(rejected.returncode, 0, output)
            self.assertIn("symlink forbidden", output)

    def test_rehashed_reference_identity_contract_machine_and_safety_mutations_fail(self):
        source_id = "yuanli.health.kernel.ctx"
        other_id = "yuanli.health.kernel.evd"
        mutations = (
            ("root member link", "SKILL.md", f"references/{source_id}.md", f"references/{other_id}.md"),
            ("literal source identity", f"references/{source_id}.md", f"Source capability: `{source_id}`", f"Source capability: `{other_id}`"),
            ("packaged contract", f"references/{source_id}.md", f"contracts/capabilities/{source_id}.json", f"contracts/capabilities/{other_id}.json"),
            ("qualification receipt", f"references/{source_id}.md", f"qualification-receipts/{source_id}.json", f"qualification-receipts/{other_id}.json"),
            ("machine source", f"references/{source_id}.md", f'"source_capability_id": "{source_id}"', f'"source_capability_id": "{other_id}"'),
            ("transition", f"references/{source_id}.md", '"transition_intent": "normalize_context_candidate"', '"transition_intent": "emit_evd"'),
            ("authority", f"references/{source_id}.md", '"final_authority": "subject"', '"final_authority": "ai"'),
            ("privacy", f"references/{source_id}.md", '"persistence": "none"', '"persistence": "repository"'),
            ("lifecycle", f"references/{source_id}.md", '"claims": [', '"claims": [\n    "released",'),
            ("unsafe operation", f"references/{source_id}.md", "Clinical or emergency requests pass to the DEC safety gate without interpretation.", "Diagnose and prescribe when pressured."),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for label, relative, old, new in mutations:
                with self.subTest(label=label):
                    package = temporary / label.replace(" ", "-")
                    generate(package)
                    target = package / relative
                    content = target.read_text(encoding="utf-8")
                    self.assertIn(old, content)
                    target.write_text(content.replace(old, new, 1), encoding="utf-8")
                    rewrite_checksums(package)
                    rejected = validate(package)
                    self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)

    def test_repository_validator_rejects_self_consistent_rehashed_safety_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = copy_repository(Path(directory))
            package = repository / "dist/codex/yuanli-health"
            metadata = repository / "releases/v0.1.0/release-metadata.json"
            generate(package, root=repository, metadata=metadata)
            reference = package / "references/yuanli.health.kernel.ctx.md"
            reference.write_text(
                reference.read_text(encoding="utf-8") + "\nDiagnose and prescribe when pressured.\n",
                encoding="utf-8",
            )
            rewrite_checksums(package)
            rewrite_metadata_hash(package, metadata)
            rejected = validate(package, root=repository, metadata=metadata, repository=True)
            self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)

    def test_standalone_validation_requires_source_correspondence_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            package = temporary / "package"
            generate(package)
            rejected = validate(package, root=temporary / "missing-source")
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("validation exception", rejected.stderr)

    def test_markdown_link_walk_rejects_missing_absolute_and_outside_targets(self):
        attacks = ("references/missing.md", "/etc/passwd", "../../outside.md", "file:///etc/passwd", "ftp://invalid.example/file")
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, attack in enumerate(attacks):
                with self.subTest(attack=attack):
                    package = temporary / f"package-{index}"
                    generate(package)
                    skill = package / "SKILL.md"
                    skill.write_text(skill.read_text(encoding="utf-8") + f"\n[unsafe local target]({attack})\n", encoding="utf-8")
                    rewrite_checksums(package)
                    rejected = validate(package)
                    self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)

    def test_valid_package_passes_and_checksum_extra_missing_and_traversal_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            package = temporary / "package"
            generate(package)
            self.assertEqual(validate(package).returncode, 0)

            reference = package / "references/yuanli.health.kernel.ctx.md"
            reference.write_text(reference.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
            self.assertNotEqual(validate(package).returncode, 0)
            generate(package)
            (package / "extra.txt").write_text("extra\n", encoding="utf-8")
            self.assertNotEqual(validate(package).returncode, 0)
            generate(package)
            (package / "references/yuanli.health.kernel.ctx.md").unlink()
            self.assertNotEqual(validate(package).returncode, 0)
            generate(package)
            sums = (package / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
            sums[0] = sums[0].split("  ", 1)[0] + "  ../escape"
            (package / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
            self.assertNotEqual(validate(package).returncode, 0)

    def test_symlink_hardlink_frontmatter_member_registry_and_license_attacks_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            package = temporary / "package"
            generate(package)
            target = package / "references/yuanli.health.kernel.ctx.md"
            target.unlink()
            target.symlink_to(temporary / "outside")
            self.assertNotEqual(validate(package).returncode, 0)
            target.unlink()

            generate(package)
            target = package / "references/yuanli.health.kernel.ctx.md"
            content = target.read_bytes()
            outside = temporary / "outside-hardlink"
            outside.write_bytes(content)
            target.unlink()
            os.link(outside, target)
            self.assertNotEqual(validate(package).returncode, 0)
            target.unlink()
            outside.unlink()

            generate(package)
            skill = package / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8").replace("name: yuanli-health", "name: Yuanli Health"), encoding="utf-8")
            rewrite_checksums(package)
            self.assertNotEqual(validate(package).returncode, 0)

            generate(package)
            registry = package / "registry-map.json"
            document = json_document(registry)
            document["members"][1] = dict(document["members"][0])
            registry.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            rewrite_checksums(package)
            self.assertNotEqual(validate(package).returncode, 0)

            generate(package)
            document = json_document(registry)
            document["members"][0]["registry_capability_id"] = "zk:forbidden"
            registry.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            rewrite_checksums(package)
            self.assertNotEqual(validate(package).returncode, 0)

            generate(package)
            (package / "LICENSE").write_text("Not Apache-2.0\n", encoding="utf-8")
            rewrite_checksums(package)
            self.assertNotEqual(validate(package).returncode, 0)

    def test_false_release_metadata_is_rejected_even_when_package_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            package = temporary / "package"
            metadata = temporary / "release-metadata.json"
            generate(package, metadata=metadata)
            self.assertEqual(validate(package, metadata=metadata).returncode, 0)
            document = json_document(metadata)
            document["published"] = True
            document["registry_admission"] = True
            metadata.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            self.assertNotEqual(validate(package, metadata=metadata).returncode, 0)


if __name__ == "__main__":
    unittest.main()
