import json
import os
import tempfile
import unittest
from pathlib import Path

from tests._adapter_support import generate, json_document, rewrite_checksums, validate


class CodexAdapterValidationTests(unittest.TestCase):
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
