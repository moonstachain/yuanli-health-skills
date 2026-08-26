import copy
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from tests._adapter_support import (
    GENERATOR,
    ROOT,
    SOURCE_IDS,
    copy_repository,
    expected_package_paths,
    generate,
    json_document,
    regular_files,
    run_script,
)


class CodexAdapterGenerationTests(unittest.TestCase):
    def test_generated_package_has_exact_members_contracts_receipts_and_checksums(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "yuanli-health"
            generate(package)
            files = regular_files(package)
            self.assertEqual(set(files), expected_package_paths())
            self.assertEqual(len(files), 59)
            for relative, content in files.items():
                with self.subTest(relative=relative):
                    self.assertNotRegex(content.decode("utf-8"), r"(?m)[ \t]+$")

            manifest = json_document(package / "contracts/suite-source-manifest.json")
            registry_map = json_document(package / "registry-map.json")
            self.assertEqual(tuple(member["source_capability_id"] for member in manifest["members"]), SOURCE_IDS)
            self.assertEqual(tuple(member["source_capability_id"] for member in registry_map["members"]), SOURCE_IDS)
            self.assertTrue(all(member["registry_capability_id"] is None for member in registry_map["members"]))

            for source_id in SOURCE_IDS:
                with self.subTest(source_id=source_id):
                    generated_contract = json_document(package / "contracts/capabilities" / f"{source_id}.json")
                    source_contract = json_document(ROOT / "capabilities" / source_id / "contract.json")
                    self.assertEqual(generated_contract, source_contract)
                    receipt = json_document(package / "contracts/qualification-receipts" / f"{source_id}.json")
                    self.assertEqual(
                        receipt,
                        {
                            "schema": "qualification-receipt-v1",
                            "source_capability_id": source_id,
                            "qualification_basis": "synthetic_only",
                            "claims": ["non_clinical", "non_release"],
                            "candidate_state": "qualified",
                            "canonical_write": False,
                        },
                    )
                    reference_path = package / "references" / f"{source_id}.md"
                    links = re.findall(r"\[[^]]*\]\(([^) ]+)\)", reference_path.read_text(encoding="utf-8"))
                    packaged_contract = f"../contracts/capabilities/{source_id}.json"
                    self.assertEqual(links.count(packaged_contract), 1)
                    self.assertNotIn("contract.json", links)

            markdown_files = [package / "SKILL.md", *(package / "references").glob("*.md")]
            for markdown in markdown_files:
                for target in re.findall(r"\[[^]]*\]\(([^) ]+)\)", markdown.read_text(encoding="utf-8")):
                    with self.subTest(markdown=markdown.name, target=target):
                        resolved = (markdown.parent / target).resolve()
                        resolved.relative_to(package.resolve())
                        self.assertTrue(resolved.is_file())
                        self.assertFalse(resolved.is_symlink())

            expected_lines = [
                f"{hashlib.sha256(content).hexdigest()}  {relative}\n"
                for relative, content in sorted(files.items())
                if relative != "SHA256SUMS"
            ]
            self.assertEqual(files["SHA256SUMS"].decode("utf-8"), "".join(expected_lines))

    def test_generation_is_cwd_locale_timezone_and_repeat_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            outputs = [temporary / name for name in ("a", "b", "c")]
            first = run_script(
                GENERATOR, "--root", ROOT, "--output", outputs[0],
                cwd=ROOT, env={"LC_ALL": "C", "TZ": "UTC"},
            )
            second = run_script(
                GENERATOR, "--root", ROOT, "--output", outputs[1],
                cwd=temporary, env={"LC_ALL": "C", "TZ": "Pacific/Honolulu"},
            )
            third = run_script(GENERATOR, "--root", ROOT, "--output", outputs[2], cwd=temporary)
            self.assertEqual((first.returncode, second.returncode, third.returncode), (0, 0, 0))
            self.assertEqual(regular_files(outputs[0]), regular_files(outputs[1]))
            self.assertEqual(regular_files(outputs[0]), regular_files(outputs[2]))

            checked = run_script(GENERATOR, "--root", ROOT, "--output", outputs[0], "--check")
            self.assertEqual(checked.returncode, 0, checked.stderr)
            (outputs[0] / "stale.txt").write_text("stale\n", encoding="utf-8")
            failed_check = run_script(GENERATOR, "--root", ROOT, "--output", outputs[0], "--check")
            self.assertNotEqual(failed_check.returncode, 0)
            generate(outputs[0])
            self.assertNotIn("stale.txt", regular_files(outputs[0]))

    def test_only_matching_source_outputs_change_and_forbidden_inputs_never_enter(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            baseline = temporary / "baseline"
            generate(baseline)
            repository = copy_repository(temporary)
            source_id = "yuanli.health.kernel.ctx"
            instruction = repository / "capabilities" / source_id / "instructions.md"
            instruction.write_text(instruction.read_text(encoding="utf-8") + "\nSynthetic adapter test note.\n", encoding="utf-8")
            contract_path = repository / "capabilities" / source_id / "contract.json"
            contract = json_document(contract_path)
            contract["authority"]["ai"] = "non_final"
            contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (repository / "capabilities" / source_id / "FORBIDDEN.txt").write_text("must not enter package\n", encoding="utf-8")
            (repository / "unrelated-secret.txt").write_text("must not enter package\n", encoding="utf-8")

            changed = temporary / "changed"
            generate(changed, root=repository)
            differing = {
                relative
                for relative in expected_package_paths()
                if regular_files(baseline)[relative] != regular_files(changed)[relative]
            }
            self.assertEqual(
                differing,
                {
                    f"references/{source_id}.md",
                    f"contracts/capabilities/{source_id}.json",
                    "SHA256SUMS",
                },
            )
            joined = b"\n".join(regular_files(changed).values())
            self.assertNotIn(b"FORBIDDEN", joined)
            self.assertNotIn(b"unrelated-secret", joined)

            malformed = copy.deepcopy(contract)
            malformed["registry_capability_id"] = "zk:forbidden"
            contract_path.write_text(json.dumps(malformed, indent=2) + "\n", encoding="utf-8")
            rejected = run_script(GENERATOR, "--root", repository, "--output", temporary / "invalid")
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse((temporary / "invalid").exists())

    def test_generation_rejects_source_markdown_outside_the_single_contract_link_policy(self):
        attacks = (
            "\n[external](https://example.invalid/source)\n",
            "\n[second contract](contract.json)\n",
            "\n[shortcut]\n\n[shortcut]: contract.json\n",
            "\n<https://example.invalid/source>\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for index, attack in enumerate(attacks):
                with self.subTest(attack=index):
                    repository = copy_repository(temporary / f"source-policy-{index}")
                    source_id = "yuanli.health.kernel.ctx"
                    instruction = repository / "capabilities" / source_id / "instructions.md"
                    instruction.write_text(
                        instruction.read_text(encoding="utf-8") + attack,
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

    def test_generation_requires_the_exact_contract_link_destination_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repository = copy_repository(temporary)
            source_id = "yuanli.health.kernel.ctx"
            instruction = repository / "capabilities" / source_id / "instructions.md"
            content = instruction.read_text(encoding="utf-8")
            self.assertEqual(content.count("](contract.json)"), 1)
            instruction.write_text(
                content.replace("](contract.json)", "]( contract.json )", 1),
                encoding="utf-8",
            )
            rejected = run_script(
                GENERATOR,
                "--root",
                repository,
                "--output",
                temporary / "rejected-spaced-target",
            )
            self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
            self.assertIn("source Markdown link policy", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
