import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from yuanli_health_skills import validator
from yuanli_health_skills import product_contracts

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:
    Draft202012Validator = None


DELETE = object()


def safe_bounded_prose(size):
    base = "Synthetic sleep pattern was stable"
    return base + (" " * (size - len(base) - 1)) + "."


def changed(document, dotted_path, value):
    result = copy.deepcopy(document)
    target = result
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    final = parts[-1]
    if value is DELETE:
        del target[final]
    elif isinstance(target, list):
        target[int(final)] = value
    else:
        target[final] = value
    return result


class ValidatorSchemaParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((ROOT / "fixtures/abi/valid/experience.json").read_text())
        cls.envelope = {
            "schema": "typed-candidate-envelope-v1",
            "source_capability_id": "yuanli.health.kernel.ctx",
            "known": [{"fact": "synthetic fact", "evidence_reference": "evd:synthetic:001"}],
            "unknown": ["synthetic unknown"],
            "assumption": ["synthetic assumption"],
            "evidence_references": ["evd:synthetic:001"],
            "authority_gate": "YELLOW",
            "candidate_state": "proposed",
            "canonical_write": False,
            "persistence": "none",
            "escalation": ["subject_review"],
            "guardrail": ["non_clinical"],
        }
        cls.receipt = {
            "schema": "qualification-receipt-v1",
            "source_capability_id": "yuanli.health.kernel.ctx",
            "qualification_basis": "synthetic_only",
            "claims": ["non_clinical", "non_release"],
            "candidate_state": "qualified",
            "canonical_write": False,
        }
        cls.registry = json.loads((ROOT / "registry/source-capabilities.json").read_text())

    def assert_schema_invalid_is_publicly_rejected(self, schema_name, validate, base, cases):
        schema = json.loads((ROOT / "contracts" / schema_name).read_text())
        schema_validator = Draft202012Validator(schema) if Draft202012Validator else None
        for name, dotted_path, value in cases:
            with self.subTest(schema=schema_name, case=name):
                document = changed(base, dotted_path, value)
                if schema_validator:
                    self.assertTrue(list(schema_validator.iter_errors(document)), "probe must be Schema-invalid")
                result = validate(document)
                self.assertFalse(result.ok, f"stdlib validator accepted Schema-invalid case: {name}")

    def test_contract_schema_keywords_match_stdlib_validator(self):
        cases = (
            ("missing required", "schema", DELETE),
            ("top additional", "unreviewed", True),
            ("schema const", "schema", "other"),
            ("source type", "source_capability_id", 7),
            ("source pattern", "source_capability_id", "yuanli.health."),
            ("registry null", "registry_capability_id", "zk:early"),
            ("class enum", "class", "service"),
            ("profile type", "profile_of", "CTX"),
            ("profile min items", "profile_of", []),
            ("profile unique", "profile_of", ["CTX", "CTX"]),
            ("profile item enum", "profile_of", ["PATIENT_RECORD"]),
            ("transition type", "transition_intent", 7),
            ("transition min length", "transition_intent", ""),
            ("mutates const", "mutates_canon", True),
            ("authority type", "authority", []),
            ("authority required", "authority.router", DELETE),
            ("authority additional", "authority.unreviewed", True),
            ("final authority enum", "authority.final_authority", "committee"),
            ("ai enum", "authority.ai", "unreviewed"),
            ("device enum", "authority.device", "unreviewed"),
            ("automation const", "authority.automation", "clinical_final"),
            ("router const", "authority.router", "clinical_final"),
            ("privacy type", "privacy", []),
            ("privacy required", "privacy.repository_phi", DELETE),
            ("privacy additional", "privacy.unreviewed", True),
            ("privacy const", "privacy.repository_phi", "allowed"),
            ("runtime type", "runtime_requirements", []),
            ("runtime required", "runtime_requirements.logs", DELETE),
            ("runtime additional", "runtime_requirements.unreviewed", True),
            ("runtime ephemeral const", "runtime_requirements.ephemeral", False),
            ("runtime persistence const", "runtime_requirements.persistence", "disk"),
            ("runtime logs const", "runtime_requirements.logs", "enabled"),
            ("lifecycle enum", "lifecycle", "released"),
            ("qualification type", "qualification", []),
            ("qualification required", "qualification.status", DELETE),
            ("qualification additional", "qualification.unreviewed", True),
            ("qualification basis const", "qualification.basis", "clinical"),
            ("qualification status enum", "qualification.status", "approved"),
            ("objects type", "objects", "CTX"),
            ("objects min items", "objects", []),
            ("objects unique", "objects", ["CTX", "CTX"]),
            ("objects item enum", "objects", ["PATIENT_RECORD"]),
            ("clock enum", "health_clock", "overnight"),
            ("claims type", "claims", "non_clinical"),
            ("claims unique", "claims", ["non_clinical", "non_clinical"]),
            ("claims item enum", "claims", ["prescription"]),
        )
        self.assert_schema_invalid_is_publicly_rejected(
            "health-skill-contract-v1.schema.json", validator.validate_contract, self.contract, cases
        )

    def test_envelope_schema_keywords_match_stdlib_validator(self):
        cases = (
            ("missing required", "schema", DELETE),
            ("top additional", "unreviewed", True),
            ("schema const", "schema", "other"),
            ("source type", "source_capability_id", 7),
            ("source pattern", "source_capability_id", "yuanli."),
            ("known type", "known", "fact"),
            ("known entry type", "known.0", "fact"),
            ("known required", "known.0.fact", DELETE),
            ("known additional", "known.0.unreviewed", True),
            ("known fact type", "known.0.fact", 7),
            ("known fact min length", "known.0.fact", ""),
            ("known evidence type", "known.0.evidence_reference", 7),
            ("known evidence min length", "known.0.evidence_reference", ""),
            ("unknown type", "unknown", "unknown"),
            ("unknown item type", "unknown.0", 7),
            ("unknown min length", "unknown.0", ""),
            ("assumption type", "assumption", "assumption"),
            ("assumption item type", "assumption.0", 7),
            ("assumption min length", "assumption.0", ""),
            ("evidence type", "evidence_references", "evd:1"),
            ("evidence item type", "evidence_references.0", 7),
            ("evidence min length", "evidence_references.0", ""),
            ("evidence unique", "evidence_references", ["evd:synthetic:001", "evd:synthetic:001"]),
            ("authority gate enum", "authority_gate", "BLUE"),
            ("candidate state enum", "candidate_state", "released"),
            ("canonical const", "canonical_write", True),
            ("persistence const", "persistence", "disk"),
            ("escalation type", "escalation", "review"),
            ("escalation item type", "escalation.0", 7),
            ("escalation min length", "escalation.0", ""),
            ("guardrail type", "guardrail", "guard"),
            ("guardrail item type", "guardrail.0", 7),
            ("guardrail min length", "guardrail.0", ""),
        )
        self.assert_schema_invalid_is_publicly_rejected(
            "typed-candidate-envelope-v1.schema.json", validator.validate_envelope, self.envelope, cases
        )

    def test_receipt_schema_keywords_match_stdlib_validator(self):
        cases = (
            ("missing required", "schema", DELETE),
            ("top additional", "unreviewed", True),
            ("schema const", "schema", "other"),
            ("source type", "source_capability_id", 7),
            ("source pattern", "source_capability_id", "yuanli."),
            ("basis const", "qualification_basis", "clinical"),
            ("claims type", "claims", "non_clinical"),
            ("claims unique", "claims", ["non_clinical", "non_clinical"]),
            ("claims item enum", "claims", ["prescription"]),
            ("state enum", "candidate_state", "released"),
            ("canonical const", "canonical_write", True),
        )
        self.assert_schema_invalid_is_publicly_rejected(
            "qualification-receipt-v1.schema.json", validator.validate_receipt, self.receipt, cases
        )

    def test_source_registry_schema_keywords_match_stdlib_validator(self):
        cases = (
            ("missing required", "schema", DELETE),
            ("top additional", "unreviewed", True),
            ("schema const", "schema", "other"),
            ("suite const", "source_suite_id", "other"),
            ("catalog const", "catalog_suite_id", "other"),
            ("name const", "name", "other"),
            ("version const", "version", "1.0.0"),
            ("count const", "member_count", 15),
            ("license const", "license", "other"),
            ("basis const", "release_basis", "other"),
            ("members type", "members", "members"),
            ("members min items", "members", self.registry["members"][:-1]),
            ("members max items", "members", self.registry["members"] + [self.registry["members"][0]]),
            ("member type", "members.0", "member"),
            ("member required", "members.0.registry_capability_id", DELETE),
            ("member additional", "members.0.unreviewed", True),
            ("member source const", "members.0.source_capability_id", "yuanli.health.kernel.evd"),
            ("member registry null", "members.0.registry_capability_id", "zk:early"),
        )
        self.assert_schema_invalid_is_publicly_rejected(
            "suite-source-manifest-v1.schema.json", validator.validate_source_registry, self.registry, cases
        )


class ProductContractSchemaParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = (
            (
                "health-evidence-view-v1",
                "health-evidence-view.json",
                product_contracts.validate_health_evidence_view,
                product_contracts.build_health_evidence_view,
            ),
            (
                "recovery-compass-snapshot-v1",
                "recovery-compass-snapshot.json",
                product_contracts.validate_recovery_compass_snapshot,
                product_contracts.build_recovery_compass_snapshot,
            ),
            (
                "quarter-health-campaign-v1",
                "quarter-health-campaign.json",
                product_contracts.validate_quarter_health_campaign,
                product_contracts.build_quarter_health_campaign,
            ),
            (
                "weekly-experiment-v1",
                "weekly-experiment.json",
                product_contracts.validate_weekly_experiment,
                product_contracts.build_weekly_experiment,
            ),
            (
                "professional-escalation-v1",
                "professional-escalation.json",
                product_contracts.validate_professional_escalation,
                product_contracts.build_professional_escalation,
            ),
        )
        cls.fixtures = {
            filename: json.loads((ROOT / "fixtures/product-contracts/valid" / filename).read_text())
            for _, filename, _, _ in cls.cases
        }

    def assert_schema_invalid_is_product_rejected(self, schema_name, validate, base, cases):
        schema = json.loads((ROOT / "contracts" / f"{schema_name}.schema.json").read_text())
        schema_validator = Draft202012Validator(schema) if Draft202012Validator else None
        for name, dotted_path, value in cases:
            with self.subTest(schema=schema_name, case=name):
                document = changed(base, dotted_path, value)
                if schema_validator:
                    self.assertTrue(list(schema_validator.iter_errors(document)), "probe must be Schema-invalid")
                self.assertFalse(validate(document).ok, f"runtime accepted Schema-invalid case: {name}")

    def test_product_runtime_matches_schema_boolean_length_enum_and_cardinality_boundaries(self):
        matrices = {
            "health-evidence-view-v1": (
                ("synthetic exact boolean", "synthetic", 1),
                ("fact exact string", "fact", True),
                ("fact max length", "fact", "x" * 281),
                ("unknown item max length", "unknowns", ["x" * 281]),
                ("source enum", "source_type", "record"),
                ("unknowns array", "unknowns", "unknown"),
                ("unknowns unique", "unknowns", ["same", "same"]),
            ),
            "recovery-compass-snapshot-v1": (
                ("directions array", "directions", True),
                ("trend enum", "directions.0.trend", "unknown"),
                ("direction min cardinality", "directions", self.fixtures["recovery-compass-snapshot.json"]["directions"][:-1]),
                ("direction max cardinality", "directions", self.fixtures["recovery-compass-snapshot.json"]["directions"] + [self.fixtures["recovery-compass-snapshot.json"]["directions"][0]]),
                ("rationale max length", "season_focus.rationale", "x" * 281),
                ("unknown item max length", "unknowns", ["x" * 281]),
                ("focus object", "season_focus", True),
                ("supported trend evidence", "directions.0.evidence_references", []),
            ),
            "quarter-health-campaign-v1": (
                ("nested phase exact integer", "phases.0.phase", True),
                ("phase label exact string", "phases.0.label", True),
                ("active phase exact integer", "active_phase", True),
                ("active phase enum", "active_phase", 4),
                ("phase min cardinality", "phases", self.fixtures["quarter-health-campaign.json"]["phases"][:-1]),
                ("phase max cardinality", "phases", self.fixtures["quarter-health-campaign.json"]["phases"] + [self.fixtures["quarter-health-campaign.json"]["phases"][0]]),
                ("unknown item max length", "unknowns", ["x" * 281]),
                ("claims const", "claims", ["non_clinical"]),
            ),
            "weekly-experiment-v1": (
                ("action object", "action_candidate", True),
                ("description max length", "action_candidate.description", "x" * 281),
                ("unknown item max length", "unknowns", ["x" * 281]),
                ("stop min cardinality", "stop_conditions", []),
                ("stop enum", "stop_conditions", ["continue"]),
                ("escalation min cardinality", "escalation_conditions", []),
                ("expected evidence min cardinality", "expected_evidence_references", []),
                ("authority enum", "authority_gate.level", "RED"),
            ),
            "professional-escalation-v1": (
                ("guidance object", "guidance", True),
                ("guidance exact string", "guidance.en", True),
                ("guidance max length", "guidance.en", "x" * 161),
                ("unknown item max length", "unknowns", ["x" * 281]),
                ("level enum", "level", "review"),
                ("evidence min cardinality", "evidence_references", []),
                ("conditional authority", "final_authority", "subject"),
            ),
        }
        for schema_name, filename, validate, _ in self.cases:
            self.assert_schema_invalid_is_product_rejected(
                schema_name,
                validate,
                self.fixtures[filename],
                matrices[schema_name],
            )

    def test_every_successful_product_builder_result_validates_against_its_schema(self):
        boundary_fields = {"schema", "synthetic", "canonical_write", "persistence"}
        for schema_name, filename, _, build in self.cases:
            schema = json.loads((ROOT / "contracts" / f"{schema_name}.schema.json").read_text())
            schema_validator = Draft202012Validator(schema) if Draft202012Validator else None
            for text_size in (0, 280):
                with self.subTest(schema=schema_name, unknown_size=text_size):
                    document = copy.deepcopy(self.fixtures[filename])
                    document["unknowns"] = [] if text_size == 0 else [safe_bounded_prose(text_size)]
                    payload = {
                        key: copy.deepcopy(value)
                        for key, value in document.items()
                        if key not in boundary_fields
                    }
                    result = build(payload)
                    self.assertTrue(result.ok, result.errors)
                    if schema_validator:
                        self.assertEqual(list(schema_validator.iter_errors(result.value)), [])

    def test_product_schemas_and_runtime_share_structural_prose_boundaries(self):
        unsafe_cases = (
            ("health-evidence-view-v1", "health-evidence-view.json", product_contracts.validate_health_evidence_view, "fact", "MRN 12345678"),
            ("recovery-compass-snapshot-v1", "recovery-compass-snapshot.json", product_contracts.validate_recovery_compass_snapshot, "season_focus.rationale", "Dr. Smith advised this candidate."),
            ("quarter-health-campaign-v1", "quarter-health-campaign.json", product_contracts.validate_quarter_health_campaign, "unknowns", ["每天吃一片药。"]),
            ("weekly-experiment-v1", "weekly-experiment.json", product_contracts.validate_weekly_experiment, "action_candidate.description", "Take one tablet daily."),
            ("weekly-experiment-v1", "weekly-experiment.json", product_contracts.validate_weekly_experiment, "action_candidate.description", "Synthetic sleep pattern was stable."),
            ("weekly-experiment-v1", "weekly-experiment.json", product_contracts.validate_weekly_experiment, "unknowns", ["Use a synthetic sleep routine candidate."]),
            ("professional-escalation-v1", "professional-escalation.json", product_contracts.validate_professional_escalation, "guidance.en", "Schedule a visit with Dr. Smith."),
            ("professional-escalation-v1", "professional-escalation.json", product_contracts.validate_professional_escalation, "unknowns", ["Contact 13800000000."]),
        )
        for schema_name, filename, validate, path, value in unsafe_cases:
            with self.subTest(schema=schema_name, path=path):
                document = changed(self.fixtures[filename], path, value)
                schema = json.loads((ROOT / "contracts" / f"{schema_name}.schema.json").read_text())
                if Draft202012Validator:
                    self.assertTrue(list(Draft202012Validator(schema).iter_errors(document)))
                self.assertFalse(validate(document).ok)

        safe = changed(
            self.fixtures["health-evidence-view.json"],
            "fact",
            "Synthetic sleep/recovery ratio was 1/2.",
        )
        schema = json.loads((ROOT / "contracts/health-evidence-view-v1.schema.json").read_text())
        if Draft202012Validator:
            self.assertEqual(list(Draft202012Validator(schema).iter_errors(safe)), [])
        self.assertTrue(product_contracts.validate_health_evidence_view(safe).ok)

    def test_all_source_and_packaged_schemas_reject_prefixed_unsafe_vocabulary(self):
        if Draft202012Validator is None:
            self.skipTest("jsonschema is required for direct Draft 2020-12 parity probes")

        unsafe_bodies = (
            ("diagnosis", "diagnosis was confirmed"),
            ("aspirin", "aspirin was reported"),
            ("medication", "medication was reported"),
            ("treatment", "treatment was reported"),
            ("provider", "provider was reported"),
            ("booking", "booking was reported"),
            ("payment", "payment was reported"),
            ("identifier", "MRN 12345678 was reported"),
            ("path", "path synthetic/files/report.txt was reported"),
        )
        prose_slots = {
            "health-evidence-view-v1": ("fact", False),
            "recovery-compass-snapshot-v1": ("season_focus.rationale", False),
            "quarter-health-campaign-v1": ("unknowns", False),
            "weekly-experiment-v1": ("action_candidate.description", True),
            "professional-escalation-v1": ("unknowns", False),
        }
        for schema_name, filename, validate, _ in self.cases:
            path, is_action = prose_slots[schema_name]
            for label, body in unsafe_bodies:
                prose = f"Use a synthetic {body}." if is_action else f"Synthetic {body}."
                value = [prose] if path == "unknowns" else prose
                document = changed(self.fixtures[filename], path, value)
                with self.subTest(schema=schema_name, category=label):
                    for schema_path in (
                        ROOT / "contracts" / f"{schema_name}.schema.json",
                        ROOT / "dist/codex/yuanli-health/contracts/product-contracts" / f"{schema_name}.schema.json",
                    ):
                        schema = json.loads(schema_path.read_text(encoding="utf-8"))
                        self.assertTrue(
                            list(Draft202012Validator(schema).iter_errors(document)),
                            f"{schema_path} accepted prefixed unsafe {label} prose",
                        )
                    self.assertFalse(validate(document).ok, "runtime must retain its conservative content gate")

    def test_source_and_packaged_schemas_retain_safe_slash_ratio_and_guidance_controls(self):
        if Draft202012Validator is None:
            self.skipTest("jsonschema is required for direct Draft 2020-12 parity probes")

        controls = (
            (
                "health-evidence-view-v1",
                "health-evidence-view.json",
                product_contracts.validate_health_evidence_view,
                "fact",
                "Synthetic sleep/recovery ratio was 1/2.",
            ),
            (
                "professional-escalation-v1",
                "professional-escalation.json",
                product_contracts.validate_professional_escalation,
                "guidance.en",
                "Bring the evidence summary for clinician review.",
            ),
            (
                "professional-escalation-v1",
                "professional-escalation.json",
                product_contracts.validate_professional_escalation,
                "guidance.zh",
                "请携带证据摘要，由临床专业人员评估。",
            ),
        )
        for schema_name, filename, validate, path, value in controls:
            document = changed(self.fixtures[filename], path, value)
            with self.subTest(schema=schema_name, path=path):
                for schema_path in (
                    ROOT / "contracts" / f"{schema_name}.schema.json",
                    ROOT / "dist/codex/yuanli-health/contracts/product-contracts" / f"{schema_name}.schema.json",
                ):
                    schema = json.loads(schema_path.read_text(encoding="utf-8"))
                    self.assertEqual(list(Draft202012Validator(schema).iter_errors(document)), [])
                self.assertTrue(validate(document).ok)


if __name__ == "__main__":
    unittest.main()
