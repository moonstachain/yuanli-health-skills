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
    def test_diagnostic_prefix_does_not_exempt_an_actual_sensitive_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q")
            private_value = "SUBJECT" + "-9999"
            sensitive_alias = "patient" + "_id"
            (repository / "spoofed-diagnostic.txt").write_text(
                "PHI_CURRENT:" + sensitive_alias + ": " + private_value + "\n",
                encoding="utf-8",
            )
            commit_all(repository, "spoofed diagnostic")
            result = run_script(PUBLIC_SCAN, "--root", repository, "--check-current")
            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("PHI_CURRENT:patient_identifier:spoofed-diagnostic.txt", output)
            self.assertNotIn(private_value, output)

    def test_machine_labels_at_safe_text_boundaries_fail_current_and_history_without_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q")
            labels_and_values = (
                ("patient" + "_id", "SUBJECT" + "-4815", "patient_identifier"),
                ("subject" + "Id", "SUBJECT" + "-4816", "patient_identifier"),
                ("Person" + "Identifier", "PERSON" + "-4817", "patient_identifier"),
                ("member" + "-id", "MEMBER" + "-4818", "patient_identifier"),
                ("User" + " Identifier", "USER" + "-4819", "patient_identifier"),
                ("medical" + "RecordNumber", "RECORD" + "-4820", "medical_record_identifier"),
                ("Email" + "Address", "private.person" + "@" + "example.com", "email_address"),
                ("phone" + "-number", "+1 " + "415 555 0123", "phone_number"),
                ("Full" + " Name", "Alice" + " Example", "person_name"),
                ("Home" + "Address", "123" + " Example Street", "postal_address"),
                ("Date" + " Of Birth", "1980" + "-04-15", "date_of_birth"),
                ("heart" + "_rate", "88" + " bpm", "health_measurement"),
                ("Blood" + "Pressure", "128" + "/82 mmHg", "health_measurement"),
                ("blood" + "-glucose", "110" + " mg/dL", "health_measurement"),
            )
            multi_label_line = "; ".join(f"({label}: {value})" for label, value, _ in labels_and_values)
            first_label, first_value, _ = labels_and_values[0]
            prose_forms = (
                f"Collected {first_label}: {first_value}",
                f"({first_label}: {first_value})",
                f"> {first_label}: {first_value}",
                f"- Recorded {first_label}: {first_value}",
                f"| field | {first_label}: {first_value} |",
                multi_label_line,
            )
            (repository / "boundaries.md").write_text("\n".join(prose_forms) + "\n", encoding="utf-8")
            (repository / "nested.yaml").write_text(f"record:\n  note: ({first_label}: {first_value})\n", encoding="utf-8")
            (repository / "mapping.py").write_text(
                f'payload["{first_label}"] = "{first_value}"\n',
                encoding="utf-8",
            )
            commit_all(repository, "safe-boundary machine labels")
            commit = git(repository, "rev-parse", "HEAD").stdout.strip()

            current = run_script(PUBLIC_SCAN, "--root", repository, "--check-current")
            history = run_script(PUBLIC_SCAN, "--root", repository, "--check-history")
            current_output = current.stdout + current.stderr
            history_output = history.stdout + history.stderr
            self.assertNotEqual(current.returncode, 0, current_output)
            self.assertNotEqual(history.returncode, 0, history_output)
            for finding_class in {item[2] for item in labels_and_values}:
                self.assertIn(f"PHI_CURRENT:{finding_class}:boundaries.md", current_output)
                self.assertIn(f"PHI_HISTORY:{finding_class}:{commit}:boundaries.md", history_output)
            for relative in ("nested.yaml", "mapping.py"):
                self.assertIn(f"PHI_CURRENT:patient_identifier:{relative}", current_output)
                self.assertIn(f"PHI_HISTORY:patient_identifier:{commit}:{relative}", history_output)
            for _, private_value, _ in labels_and_values:
                self.assertNotIn(private_value, current_output)
                self.assertNotIn(private_value, history_output)

    def test_structured_json_key_variants_and_measurements_fail_current_and_history_without_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q")
            private_values = (
                "SUBJECT" + "-1234",
                "RECORD" + "-5678",
                "private.person" + "@" + "example.com",
                "+1 " + "415 555 0123",
                "Alice" + " Example",
                "123" + " Example Street",
                "1980" + "-04-15",
                "128" + "/82 mmHg",
                "110" + " mg/dL",
            )
            document = {
                "patient" + "Id": private_values[0],
                "Subject" + "Identifier": private_values[0],
                "person" + "-id": private_values[0],
                "member" + " id": private_values[0],
                "User" + "_Identifier": private_values[0],
                "medical" + "RecordNumber": private_values[1],
                "Email" + "Address": private_values[2],
                "phone" + "-number": private_values[3],
                "Full" + " Name": private_values[4],
                "Home" + "Address": private_values[5],
                "Date" + "OfBirth": private_values[6],
                "heart" + "_rate": 88,
                "Blood" + "Pressure": private_values[7],
                "blood" + "-glucose": private_values[8],
            }
            (repository / "variants.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            commit_all(repository, "structured variants")
            commit = git(repository, "rev-parse", "HEAD").stdout.strip()

            current = run_script(PUBLIC_SCAN, "--root", repository, "--check-current")
            history = run_script(PUBLIC_SCAN, "--root", repository, "--check-history")
            current_output = current.stdout + current.stderr
            history_output = history.stdout + history.stderr
            self.assertNotEqual(current.returncode, 0, current_output)
            self.assertNotEqual(history.returncode, 0, history_output)
            for finding_class in (
                "patient_identifier",
                "medical_record_identifier",
                "email_address",
                "phone_number",
                "person_name",
                "postal_address",
                "date_of_birth",
                "health_measurement",
            ):
                self.assertIn(f"PHI_CURRENT:{finding_class}:variants.json", current_output)
                self.assertIn(f"PHI_HISTORY:{finding_class}:{commit}:variants.json", history_output)
            for private_value in private_values:
                self.assertNotIn(private_value, current_output)
                self.assertNotIn(private_value, history_output)

    def test_machine_labels_in_markdown_yaml_and_python_fail_current_and_history_without_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q")
            labels_and_values = (
                ("patient" + "_id", "SUBJECT" + "-1234"),
                ("member" + "Identifier", "MEMBER" + "-5678"),
                ("Medical" + "RecordNumber", "RECORD" + "-9012"),
                ("phone" + "-number", "+1 " + "415 555 0123"),
                ("Heart" + " Rate", "88" + " bpm"),
            )
            for suffix, separator in (("md", ": "), ("yaml", ": "), ("py", " = ")):
                content = "\n".join(label + separator + repr(value) for label, value in labels_and_values) + "\n"
                (repository / f"probe.{suffix}").write_text(content, encoding="utf-8")
            commit_all(repository, "machine labels")
            commit = git(repository, "rev-parse", "HEAD").stdout.strip()

            current = run_script(PUBLIC_SCAN, "--root", repository, "--check-current")
            history = run_script(PUBLIC_SCAN, "--root", repository, "--check-history")
            current_output = current.stdout + current.stderr
            history_output = history.stdout + history.stderr
            self.assertNotEqual(current.returncode, 0, current_output)
            self.assertNotEqual(history.returncode, 0, history_output)
            for suffix in ("md", "yaml", "py"):
                for finding_class in (
                    "patient_identifier",
                    "medical_record_identifier",
                    "phone_number",
                    "health_measurement",
                ):
                    self.assertIn(f"PHI_CURRENT:{finding_class}:probe.{suffix}", current_output)
                    self.assertIn(f"PHI_HISTORY:{finding_class}:{commit}:probe.{suffix}", history_output)
            for _, private_value in labels_and_values:
                self.assertNotIn(private_value, current_output)
                self.assertNotIn(private_value, history_output)

    def test_source_machine_label_propagates_to_generated_reference_and_both_scan_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = copy_repository(Path(directory))
            git(repository, "init", "-q")
            private_identifier = "SUBJECT" + "-1234"
            private_measurement = "128" + "/82 mmHg"
            instruction = repository / "capabilities/yuanli.health.kernel.ctx/instructions.md"
            probe = (
                "Collected "
                + "patient"
                + "_id: "
                + private_identifier
                + "; ("
                + "Blood"
                + "Pressure: "
                + private_measurement
                + ")"
            )
            instruction.write_text(instruction.read_text(encoding="utf-8") + "\n" + probe + "\n", encoding="utf-8")
            package = repository / "dist/codex/yuanli-health"
            generate(package, root=repository, metadata=repository / "releases/v0.1.0/release-metadata.json")
            reference = package / "references/yuanli.health.kernel.ctx.md"
            self.assertIn(probe, reference.read_text(encoding="utf-8"))
            commit_all(repository, "source and generated machine labels")

            for mode in ("--check-current", "--check-history"):
                result = run_script(PUBLIC_SCAN, "--root", repository, mode)
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn("patient_identifier", output)
                self.assertIn("health_measurement", output)
                self.assertIn("capabilities/yuanli.health.kernel.ctx/instructions.md", output)
                self.assertIn("dist/codex/yuanli-health/references/yuanli.health.kernel.ctx.md", output)
                self.assertNotIn(private_identifier, output)
                self.assertNotIn(private_measurement, output)

    def test_closed_taxonomy_positive_controls_pass_current_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q")
            controls = {
                "suite_id": "YL-SUITE-HEALTH-20260823-0001",
                "sha256": "a" * 64,
                "version": "0.1.0",
                "license": "Apache-2.0",
                "synthetic_label": "abstract_candidate_alpha",
                "case_count": 120,
                "heart_rate_limit": 100,
            }
            (repository / "controls.json").write_text(json.dumps(controls, indent=2) + "\n", encoding="utf-8")
            empty_label = "patient" + "_id"
            (repository / "controls.md").write_text(
                "Suite YL-SUITE-HEALTH-20260823-0001 has 120 synthetic cases under Apache-2.0.\n"
                "Documentation mentions patient_id, medicalRecordId, and heart-rate labels without values.\n"
                "An unrelated patient_id mention is not a label/value pair.\n"
                + empty_label
                + ": \n",
                encoding="utf-8",
            )
            classifier_key = "patient" + "_id"
            classifier_value = "patient" + "_identifier"
            (repository / "scanner-taxonomy.py").write_text(
                f'    "{classifier_key}": "{classifier_value}",\n',
                encoding="utf-8",
            )
            template_email = "email"
            template_name = "Full" + " Name"
            template_address = "Address"
            (repository / "inert-templates.py").write_text(
                template_email
                + ' = " + "fixture"\n'
                + template_name
                + ": {private_name}\n"
                + template_address
                + ": private_values[2]\n",
                encoding="utf-8",
            )
            commit_all(repository, "positive controls")
            for mode in ("--check-current", "--check-history"):
                result = run_script(PUBLIC_SCAN, "--root", repository, mode)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
            registry_document["patient" + "Id"] = "SUBJECT-1234"
            registry_document["heart" + "Rate"] = 88
            registry.write_text(json.dumps(registry_document, indent=2) + "\n", encoding="utf-8")
            release_document = json_document(metadata)
            release_document["medical" + "RecordId"] = "RECORD-1234"
            metadata.write_text(json.dumps(release_document, indent=2) + "\n", encoding="utf-8")
            commit_all(repository, "candidate with private content")

            result = run_script(PUBLIC_SCAN, "--root", repository, "--check-current")
            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("PHI_CURRENT:email_address:capabilities/yuanli.health.kernel.ctx/instructions.md", output)
            self.assertIn("PHI_CURRENT:email_address:dist/codex/yuanli-health/references/yuanli.health.kernel.ctx.md", output)
            self.assertIn("PHI_CURRENT:patient_identifier:dist/codex/yuanli-health/registry-map.json", output)
            self.assertIn("PHI_CURRENT:health_measurement:dist/codex/yuanli-health/registry-map.json", output)
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
