import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._adapter_support import PUBLIC_SCAN, copy_repository, generate, json_document, run_script


def git(repository: Path, *arguments: str):
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    )


def commit_all(repository: Path, message: str) -> None:
    git(repository, "add", "--all")
    git(
        repository,
        "-c", "user.name=Scanner Test",
        "-c", "user.email=" + "scanner-test" + "@" + "invalid.example",
        "commit", "-m", message,
    )


class PublicContentScanTests(unittest.TestCase):
    def test_redacted_finding_class_names_are_not_private_values(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q")
            artifact = repository / "diagnostic.txt"
            artifact.write_text("PHI_CURRENT:medical_record_identifier:example.json\n", encoding="utf-8")
            commit_all(repository, "redacted diagnostic")
            result = run_script(PUBLIC_SCAN, "--root", repository, "--check-current")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_current_scan_covers_source_generated_package_and_release_metadata_without_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = copy_repository(Path(directory))
            git(repository, "init", "-q")
            private_email = "private.person" + "@" + "example.com"
            instruction = repository / "capabilities/yuanli.health.kernel.ctx/instructions.md"
            instruction.write_text(instruction.read_text(encoding="utf-8") + f"\nPatient email: {private_email}\n", encoding="utf-8")
            package = repository / "dist/codex/yuanli-health"
            metadata = repository / "releases/v0.1.0/release-metadata.json"
            generate(package, root=repository, metadata=metadata)
            registry = package / "registry-map.json"
            registry_document = json_document(registry)
            registry_document["patient" + "_id"] = "SUBJECT-1234"
            registry.write_text(json.dumps(registry_document, indent=2) + "\n", encoding="utf-8")
            release_document = json_document(metadata)
            release_document["medical" + "_record_id"] = "RECORD-1234"
            metadata.write_text(json.dumps(release_document, indent=2) + "\n", encoding="utf-8")
            commit_all(repository, "candidate with private content")

            result = run_script(PUBLIC_SCAN, "--root", repository, "--check-current")
            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("PHI_CURRENT:email_address:capabilities/yuanli.health.kernel.ctx/instructions.md", output)
            self.assertIn("PHI_CURRENT:email_address:dist/codex/yuanli-health/references/yuanli.health.kernel.ctx.md", output)
            self.assertIn("PHI_CURRENT:patient_identifier:dist/codex/yuanli-health/registry-map.json", output)
            self.assertIn("PHI_CURRENT:medical_record_identifier:releases/v0.1.0/release-metadata.json", output)
            self.assertNotIn(private_email, output)
            self.assertNotIn("SUBJECT-1234", output)
            self.assertNotIn("RECORD-1234", output)

    def test_history_scan_finds_removed_private_content_with_commit_and_redacts_value(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q")
            private_email = "removed.person" + "@" + "example.com"
            artifact = repository / "history.md"
            artifact.write_text(f"Patient email: {private_email}\n", encoding="utf-8")
            commit_all(repository, "private predecessor")
            private_commit = git(repository, "rev-parse", "HEAD").stdout.strip()
            artifact.write_text("Synthetic placeholder only.\n", encoding="utf-8")
            commit_all(repository, "remove private content")

            current = run_script(PUBLIC_SCAN, "--root", repository, "--check-current")
            self.assertEqual(current.returncode, 0, current.stdout + current.stderr)
            history = run_script(PUBLIC_SCAN, "--root", repository, "--check-history")
            output = history.stdout + history.stderr
            self.assertNotEqual(history.returncode, 0, output)
            self.assertIn(f"PHI_HISTORY:email_address:{private_commit}:history.md", output)
            self.assertNotIn(private_email, output)

    def test_history_scan_applies_json_key_rules_after_same_blob_is_renamed(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q")
            key = "patient" + "_id"
            artifact = repository / "artifact.txt"
            artifact.write_text(json.dumps({key: "SUBJECT-1234"}) + "\n", encoding="utf-8")
            commit_all(repository, "text extension")
            artifact.rename(repository / "artifact.json")
            commit_all(repository, "json extension")
            json_commit = git(repository, "rev-parse", "HEAD").stdout.strip()

            result = run_script(PUBLIC_SCAN, "--root", repository, "--check-history")
            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn(f"PHI_HISTORY:patient_identifier:{json_commit}:artifact.json", output)
            self.assertNotIn("SUBJECT-1234", output)

    def test_contextual_phone_date_and_measurement_forms_are_detected_without_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q")
            private_phone = "+1 " + "415 555 0123"
            private_date = "1980" + "-04-15"
            private_measurement = "Blood pressure: " + "128/82 mmHg"
            private_name = "Alice" + " Example"
            private_address = "123" + " Example Street"
            artifact = repository / "public.md"
            artifact.write_text(
                f"Patient name: {private_name}\nHome address: {private_address}\n"
                f"Phone: {private_phone}\nDate of birth: {private_date}\n{private_measurement}\n",
                encoding="utf-8",
            )
            commit_all(repository, "contextual private forms")
            result = run_script(PUBLIC_SCAN, "--root", repository, "--check-current")
            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("PHI_CURRENT:phone_number:public.md", output)
            self.assertIn("PHI_CURRENT:iso_date:public.md", output)
            self.assertIn("PHI_CURRENT:date_of_birth:public.md", output)
            self.assertIn("PHI_CURRENT:health_measurement:public.md", output)
            self.assertIn("PHI_CURRENT:person_name:public.md", output)
            self.assertIn("PHI_CURRENT:postal_address:public.md", output)
            self.assertNotIn(private_phone, output)
            self.assertNotIn(private_date, output)
            self.assertNotIn(private_measurement, output)
            self.assertNotIn(private_name, output)
            self.assertNotIn(private_address, output)


if __name__ == "__main__":
    unittest.main()
