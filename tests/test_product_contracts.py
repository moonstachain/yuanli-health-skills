import json
import copy
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class ProductContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.health_evidence = json.loads(
            (ROOT / "fixtures/product-contracts/valid/health-evidence-view.json").read_text(encoding="utf-8")
        )

    def load_valid(self, filename):
        return json.loads(
            (ROOT / "fixtures/product-contracts/valid" / filename).read_text(encoding="utf-8")
        )

    def test_health_evidence_view_accepts_a_hand_derived_synthetic_fixture(self):
        from yuanli_health_skills.product_contracts import validate_health_evidence_view

        fixture = json.loads(
            (ROOT / "fixtures/product-contracts/valid/health-evidence-view.json").read_text(encoding="utf-8")
        )

        self.assertEqual(validate_health_evidence_view(fixture).errors, ())

    def test_health_evidence_view_rejects_missing_and_extension_fields_in_stable_order(self):
        from yuanli_health_skills.product_contracts import validate_health_evidence_view

        malformed = copy.deepcopy(self.health_evidence)
        del malformed["fact"]
        malformed["unreviewed_extension"] = True

        self.assertEqual(
            [(error.code, error.path) for error in validate_health_evidence_view(malformed).errors],
            [
                ("MISSING_REQUIRED_FIELD", "fact"),
                ("STRICT_SCHEMA_VIOLATION", "unreviewed_extension"),
            ],
        )

    def test_all_five_product_contract_validators_are_public(self):
        from yuanli_health_skills import product_contracts

        names = (
            "validate_health_evidence_view",
            "validate_recovery_compass_snapshot",
            "validate_quarter_health_campaign",
            "validate_weekly_experiment",
            "validate_professional_escalation",
        )

        self.assertEqual(
            [name for name in names if not callable(getattr(product_contracts, name, None))],
            [],
        )

    def test_all_five_hand_derived_product_contract_fixtures_are_valid(self):
        from yuanli_health_skills import product_contracts

        cases = (
            ("health-evidence-view.json", product_contracts.validate_health_evidence_view),
            ("recovery-compass-snapshot.json", product_contracts.validate_recovery_compass_snapshot),
            ("quarter-health-campaign.json", product_contracts.validate_quarter_health_campaign),
            ("weekly-experiment.json", product_contracts.validate_weekly_experiment),
            ("professional-escalation.json", product_contracts.validate_professional_escalation),
        )
        for filename, validate in cases:
            with self.subTest(filename=filename):
                fixture = json.loads(
                    (ROOT / "fixtures/product-contracts/valid" / filename).read_text(encoding="utf-8")
                )
                self.assertEqual(validate(fixture).errors, ())

    def test_every_product_contract_enforces_the_fixed_skill_core_boundary(self):
        from yuanli_health_skills import product_contracts

        cases = (
            ("health-evidence-view.json", product_contracts.validate_health_evidence_view),
            ("recovery-compass-snapshot.json", product_contracts.validate_recovery_compass_snapshot),
            ("quarter-health-campaign.json", product_contracts.validate_quarter_health_campaign),
            ("weekly-experiment.json", product_contracts.validate_weekly_experiment),
            ("professional-escalation.json", product_contracts.validate_professional_escalation),
        )
        mutations = (
            ("synthetic", False, "SYNTHETIC_REQUIRED"),
            ("canonical_write", True, "CANON_WRITE_FORBIDDEN"),
            ("persistence", "local", "RUNTIME_PERSISTENCE_FORBIDDEN"),
            ("health_score", 91, "FORBIDDEN_AGGREGATE_SCORE"),
        )
        for filename, validate in cases:
            for field, bad_value, expected_code in mutations:
                with self.subTest(filename=filename, field=field):
                    malformed = self.load_valid(filename)
                    malformed[field] = bad_value
                    self.assertIn(expected_code, [error.code for error in validate(malformed).errors])

    def test_health_evidence_view_rejects_invalid_enums_tokens_types_and_duplicate_references(self):
        from yuanli_health_skills.product_contracts import validate_health_evidence_view

        mutations = (
            ("source_type", "medical_record", "INVALID_ENUM"),
            ("evidence_id", "real-person-001", "INVALID_OPAQUE_TOKEN"),
            ("fact", {"clinical_conclusion": "free form"}, "INVALID_STRING"),
            ("unknowns", "implicit", "INVALID_ARRAY"),
            (
                "conflicts_with",
                ["synthetic:evidence:002", "synthetic:evidence:002"],
                "DUPLICATE_REFERENCE",
            ),
        )
        for field, bad_value, expected_code in mutations:
            with self.subTest(field=field):
                malformed = copy.deepcopy(self.health_evidence)
                malformed[field] = bad_value
                self.assertIn(expected_code, [error.code for error in validate_health_evidence_view(malformed).errors])

    def test_recovery_compass_enforces_four_directions_evidence_one_focus_and_subject_authority(self):
        from yuanli_health_skills.product_contracts import validate_recovery_compass_snapshot

        fixture = self.load_valid("recovery-compass-snapshot.json")
        mutations = []
        wrong_order = copy.deepcopy(fixture)
        wrong_order["directions"].reverse()
        mutations.append((wrong_order, "INVALID_DIRECTIONS"))
        unsupported_trend = copy.deepcopy(fixture)
        unsupported_trend["directions"][0]["evidence_references"] = []
        mutations.append((unsupported_trend, "EVIDENCE_REQUIRED"))
        evidence_without_trend = copy.deepcopy(fixture)
        evidence_without_trend["directions"][1]["evidence_references"] = ["synthetic:evidence:099"]
        mutations.append((evidence_without_trend, "EVIDENCE_FOR_INSUFFICIENT_TREND"))
        multiple_focus = copy.deepcopy(fixture)
        multiple_focus["season_focus"] = [fixture["season_focus"], fixture["season_focus"]]
        mutations.append((multiple_focus, "MULTIPLE_ACTIVE_FOCUS"))
        wrong_authority = copy.deepcopy(fixture)
        wrong_authority["authority_gate"]["final_authority"] = "ai"
        mutations.append((wrong_authority, "WRONG_AUTHORITY"))
        nested_extension = copy.deepcopy(fixture)
        nested_extension["directions"][0]["extension"] = True
        mutations.append((nested_extension, "STRICT_SCHEMA_VIOLATION"))
        missing_guardrail = copy.deepcopy(fixture)
        missing_guardrail["guardrails"] = ["no_aggregate_score"]
        mutations.append((missing_guardrail, "REQUIRED_GUARDRAIL"))

        for malformed, expected_code in mutations:
            with self.subTest(expected_code=expected_code):
                self.assertIn(
                    expected_code,
                    [error.code for error in validate_recovery_compass_snapshot(malformed).errors],
                )

    def test_quarter_campaign_enforces_exact_phases_one_active_experiment_and_candidate_nonclaims(self):
        from yuanli_health_skills.product_contracts import validate_quarter_health_campaign

        fixture = self.load_valid("quarter-health-campaign.json")
        mutations = []
        wrong_phases = copy.deepcopy(fixture)
        wrong_phases["phases"][1]["label"] = "治疗与优化"
        mutations.append((wrong_phases, "INVALID_CAMPAIGN_PHASES"))
        wrong_active = copy.deepcopy(fixture)
        wrong_active["active_phase"] = True
        mutations.append((wrong_active, "INVALID_ACTIVE_PHASE"))
        multiple_experiments = copy.deepcopy(fixture)
        multiple_experiments["current_weekly_experiment_reference"] = [
            "synthetic:experiment:001",
            "synthetic:experiment:002",
        ]
        mutations.append((multiple_experiments, "MULTIPLE_ACTIVE_EXPERIMENT"))
        outcome_claim = copy.deepcopy(fixture)
        outcome_claim["claims"] = ["effective"]
        mutations.append((outcome_claim, "FORBIDDEN_OUTCOME_CLAIM"))
        wrong_authority = copy.deepcopy(fixture)
        wrong_authority["authority_gate"]["final_authority"] = "health_steward"
        mutations.append((wrong_authority, "WRONG_AUTHORITY"))

        for malformed, expected_code in mutations:
            with self.subTest(expected_code=expected_code):
                self.assertIn(
                    expected_code,
                    [error.code for error in validate_quarter_health_campaign(malformed).errors],
                )

    def test_weekly_experiment_enforces_one_action_evidence_stop_escalation_and_no_adjudication(self):
        from yuanli_health_skills.product_contracts import validate_weekly_experiment

        fixture = self.load_valid("weekly-experiment.json")
        mutations = []
        multiple_actions = copy.deepcopy(fixture)
        multiple_actions["action_candidate"] = [fixture["action_candidate"], fixture["action_candidate"]]
        mutations.append((multiple_actions, "MULTIPLE_ACTION_CANDIDATES"))
        no_expected_evidence = copy.deepcopy(fixture)
        no_expected_evidence["expected_evidence_references"] = []
        mutations.append((no_expected_evidence, "EVIDENCE_REQUIRED"))
        no_stop = copy.deepcopy(fixture)
        no_stop["stop_conditions"] = []
        mutations.append((no_stop, "STOP_CONDITION_REQUIRED"))
        no_escalation = copy.deepcopy(fixture)
        no_escalation["escalation_conditions"] = []
        mutations.append((no_escalation, "ESCALATION_CONDITION_REQUIRED"))
        invalid_condition = copy.deepcopy(fixture)
        invalid_condition["stop_conditions"] = ["optimize_performance"]
        mutations.append((invalid_condition, "INVALID_ENUM"))
        forbidden_outcome = copy.deepcopy(fixture)
        forbidden_outcome["effectiveness"] = "proven"
        mutations.append((forbidden_outcome, "FORBIDDEN_OUTCOME_ADJUDICATION"))
        forbidden_clinical = copy.deepcopy(fixture)
        forbidden_clinical["diagnosis"] = "synthetic conclusion"
        mutations.append((forbidden_clinical, "CLINICAL_OVERREACH"))
        forbidden_clinical_text = copy.deepcopy(fixture)
        forbidden_clinical_text["action_candidate"]["description"] = "Synthetic medication candidate."
        mutations.append((forbidden_clinical_text, "CLINICAL_OVERREACH"))
        forbidden_stage_text = copy.deepcopy(fixture)
        forbidden_stage_text["action_candidate"]["description"] = "Produce an OUT candidate."
        mutations.append((forbidden_stage_text, "FORBIDDEN_OUTCOME_ADJUDICATION"))
        wrong_authority = copy.deepcopy(fixture)
        wrong_authority["authority_gate"]["final_authority"] = "automation"
        mutations.append((wrong_authority, "WRONG_AUTHORITY"))

        for malformed, expected_code in mutations:
            with self.subTest(expected_code=expected_code):
                self.assertIn(
                    expected_code,
                    [error.code for error in validate_weekly_experiment(malformed).errors],
                )

    def test_professional_escalation_enforces_trigger_evidence_authority_guidance_and_scope(self):
        from yuanli_health_skills.product_contracts import validate_professional_escalation

        fixture = self.load_valid("professional-escalation.json")
        mutations = []
        invalid_trigger = copy.deepcopy(fixture)
        invalid_trigger["trigger_category"] = "performance_optimization"
        mutations.append((invalid_trigger, "INVALID_ENUM"))
        no_evidence = copy.deepcopy(fixture)
        no_evidence["evidence_references"] = []
        mutations.append((no_evidence, "EVIDENCE_REQUIRED"))
        wrong_authority = copy.deepcopy(fixture)
        wrong_authority["level"] = "emergency"
        mutations.append((wrong_authority, "WRONG_AUTHORITY"))
        wrong_language = copy.deepcopy(fixture)
        wrong_language["guidance"]["zh"] = "Bring evidence."
        mutations.append((wrong_language, "INVALID_GUIDANCE_LANGUAGE"))
        provider_selection = copy.deepcopy(fixture)
        provider_selection["provider_selection"] = "synthetic:provider:001"
        mutations.append((provider_selection, "FORBIDDEN_SERVICE_OPERATION"))
        treatment = copy.deepcopy(fixture)
        treatment["treatment_recommendation"] = "synthetic recommendation"
        mutations.append((treatment, "CLINICAL_OVERREACH"))

        for malformed, expected_code in mutations:
            with self.subTest(expected_code=expected_code):
                self.assertIn(
                    expected_code,
                    [error.code for error in validate_professional_escalation(malformed).errors],
                )

    def test_public_product_validators_totalize_deep_cyclic_and_non_json_values(self):
        from yuanli_health_skills import product_contracts

        validators = (
            product_contracts.validate_health_evidence_view,
            product_contracts.validate_recovery_compass_snapshot,
            product_contracts.validate_quarter_health_campaign,
            product_contracts.validate_weekly_experiment,
            product_contracts.validate_professional_escalation,
        )
        cyclic = {"schema": "unknown"}
        cyclic["cycle"] = cyclic
        deep = []
        cursor = deep
        for _ in range(40):
            child = []
            cursor.append(child)
            cursor = child
        adversarial = (
            ({"schema": "unknown", "value": {"not_json"}}, "NON_JSON_VALUE"),
            (cyclic, "CYCLIC_JSON"),
            ({"schema": "unknown", "value": deep}, "MAX_DEPTH_EXCEEDED"),
        )
        for validate in validators:
            for document, expected_code in adversarial:
                with self.subTest(validator=validate.__name__, expected_code=expected_code):
                    signatures = []
                    for _ in range(2):
                        try:
                            result = validate(document)
                        except Exception as exc:
                            self.fail(f"{validate.__name__} raised {type(exc).__name__}: {exc}")
                        signatures.append(tuple((error.code, error.path) for error in result.errors))
                    self.assertEqual(signatures[0], signatures[1])
                    self.assertIn(expected_code, [code for code, _ in signatures[0]])

    def test_json_arrays_and_objects_in_nested_enum_slots_return_errors_without_raising(self):
        from yuanli_health_skills import product_contracts

        cases = []
        health = self.load_valid("health-evidence-view.json")
        health["source_type"] = []
        cases.append((product_contracts.validate_health_evidence_view, health))
        compass_trend = self.load_valid("recovery-compass-snapshot.json")
        compass_trend["directions"][0]["trend"] = {}
        cases.append((product_contracts.validate_recovery_compass_snapshot, compass_trend))
        compass_focus = self.load_valid("recovery-compass-snapshot.json")
        compass_focus["season_focus"]["direction"] = []
        cases.append((product_contracts.validate_recovery_compass_snapshot, compass_focus))
        compass_authority = self.load_valid("recovery-compass-snapshot.json")
        compass_authority["authority_gate"]["level"] = {}
        cases.append((product_contracts.validate_recovery_compass_snapshot, compass_authority))
        escalation_level = self.load_valid("professional-escalation.json")
        escalation_level["level"] = []
        cases.append((product_contracts.validate_professional_escalation, escalation_level))
        escalation_trigger = self.load_valid("professional-escalation.json")
        escalation_trigger["trigger_category"] = {}
        cases.append((product_contracts.validate_professional_escalation, escalation_trigger))

        for validate, document in cases:
            with self.subTest(validator=validate.__name__):
                try:
                    result = validate(document)
                except Exception as exc:
                    self.fail(f"{validate.__name__} raised {type(exc).__name__}: {exc}")
                self.assertFalse(result.ok)

    def test_non_json_object_hooks_are_not_executed_by_public_boundaries(self):
        from yuanli_health_skills import build_health_evidence_view, validate_health_evidence_view

        class HostileKey:
            def __hash__(self):
                return hash("schema")

            def __eq__(self, other):
                raise AssertionError("object equality hook executed")

            def __str__(self):
                raise AssertionError("object string hook executed")

        class HostileDict(dict):
            def __iter__(self):
                raise AssertionError("mapping iterator hook executed")

        documents = ({HostileKey(): "value"}, HostileDict())
        for document in documents:
            for boundary in (validate_health_evidence_view, build_health_evidence_view):
                with self.subTest(document=type(document).__name__, boundary=boundary.__name__):
                    try:
                        result = boundary(document)
                    except Exception as exc:
                        self.fail(f"boundary executed object hook: {type(exc).__name__}: {exc}")
                    self.assertIn("NON_JSON_VALUE", [error.code for error in result.errors])

    def test_nested_scores_sensitive_fields_paths_and_unordered_arrays_are_rejected(self):
        from yuanli_health_skills.product_contracts import (
            validate_health_evidence_view,
            validate_weekly_experiment,
        )

        score = self.load_valid("weekly-experiment.json")
        score["action_candidate"]["score"] = 8
        camel_score = self.load_valid("weekly-experiment.json")
        camel_score["action_candidate"]["readinessScore"] = 8
        sensitive = self.load_valid("weekly-experiment.json")
        sensitive["action_candidate"]["raw_file"] = "synthetic"
        nested_outcome = self.load_valid("weekly-experiment.json")
        nested_outcome["action_candidate"]["effectiveness"] = "proven"
        nested_clinical = self.load_valid("weekly-experiment.json")
        nested_clinical["action_candidate"]["medication"] = "synthetic"
        path_value = copy.deepcopy(self.health_evidence)
        path_value["fact"] = "/private/synthetic-health.txt"
        clinical_conclusion = copy.deepcopy(self.health_evidence)
        clinical_conclusion["fact"] = "Synthetic diagnosis was confirmed."
        contact_value = copy.deepcopy(self.health_evidence)
        contact_value["fact"] = "Synthetic contact +" + "86 " + "138 " + "0000 " + "0000."
        unordered = copy.deepcopy(self.health_evidence)
        unordered["unknowns"] = ["z synthetic unknown", "a synthetic unknown"]
        cases = (
            (validate_weekly_experiment, score, "FORBIDDEN_AGGREGATE_SCORE"),
            (validate_weekly_experiment, camel_score, "FORBIDDEN_AGGREGATE_SCORE"),
            (validate_weekly_experiment, sensitive, "FORBIDDEN_SENSITIVE_FIELD"),
            (validate_weekly_experiment, nested_outcome, "FORBIDDEN_OUTCOME_ADJUDICATION"),
            (validate_weekly_experiment, nested_clinical, "CLINICAL_OVERREACH"),
            (validate_health_evidence_view, path_value, "FORBIDDEN_SENSITIVE_CONTENT"),
            (validate_health_evidence_view, clinical_conclusion, "CLINICAL_OVERREACH"),
            (validate_health_evidence_view, contact_value, "FORBIDDEN_SENSITIVE_CONTENT"),
            (validate_health_evidence_view, unordered, "NON_DETERMINISTIC_ORDER"),
        )
        for validate, malformed, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                self.assertIn(expected_code, [error.code for error in validate(malformed).errors])

    def test_multilingual_clinical_and_service_prose_is_rejected_in_valid_fields(self):
        from yuanli_health_skills import product_contracts

        cases = []
        chinese_diagnosis = self.load_valid("health-evidence-view.json")
        chinese_diagnosis["fact"] = "合成观察已确诊糖尿病。"
        cases.append((product_contracts.validate_health_evidence_view, chinese_diagnosis, "CLINICAL_OVERREACH"))
        english_conclusion = self.load_valid("health-evidence-view.json")
        english_conclusion["unknowns"] = ["Synthetic diagnosis was confirmed."]
        cases.append((product_contracts.validate_health_evidence_view, english_conclusion, "CLINICAL_OVERREACH"))
        chinese_treatment = self.load_valid("professional-escalation.json")
        chinese_treatment["guidance"]["zh"] = "建议服用阿司匹林治疗。"
        cases.append((product_contracts.validate_professional_escalation, chinese_treatment, "CLINICAL_OVERREACH"))
        english_treatment = self.load_valid("professional-escalation.json")
        english_treatment["guidance"]["en"] = "Take aspirin as treatment now."
        cases.append((product_contracts.validate_professional_escalation, english_treatment, "CLINICAL_OVERREACH"))
        english_service = self.load_valid("professional-escalation.json")
        english_service["guidance"]["en"] = "Book Dr. Smith and pay the provider now."
        cases.append((product_contracts.validate_professional_escalation, english_service, "FORBIDDEN_SERVICE_OPERATION"))
        chinese_service = self.load_valid("professional-escalation.json")
        chinese_service["guidance"]["zh"] = "请立即预约医生并支付挂号费用。"
        cases.append((product_contracts.validate_professional_escalation, chinese_service, "FORBIDDEN_SERVICE_OPERATION"))
        chinese_provider = self.load_valid("professional-escalation.json")
        chinese_provider["guidance"]["zh"] = "建议选择张医生处理。"
        cases.append((product_contracts.validate_professional_escalation, chinese_provider, "FORBIDDEN_SERVICE_OPERATION"))

        for validate, document, expected_code in cases:
            with self.subTest(validator=validate.__name__, expected_code=expected_code):
                self.assertIn(expected_code, [error.code for error in validate(document).errors])

    def test_relative_absolute_and_traversal_paths_are_rejected_from_prose(self):
        from yuanli_health_skills import validate_health_evidence_view

        paths = (
            "synthetic/files/report.txt",
            "/private/synthetic-health.txt",
            "../synthetic/report.txt",
            "./synthetic/report.txt",
            "synthetic\\files\\report.txt",
            "C:\\synthetic\\report.txt",
        )
        for path in paths:
            with self.subTest(path=path):
                document = copy.deepcopy(self.health_evidence)
                document["fact"] = path
                self.assertIn(
                    "FORBIDDEN_SENSITIVE_CONTENT",
                    [error.code for error in validate_health_evidence_view(document).errors],
                )

    def test_sensitive_content_is_rejected_from_every_prose_slot(self):
        from yuanli_health_skills import product_contracts

        cases = []
        health_fact = self.load_valid("health-evidence-view.json")
        health_fact["fact"] = "synthetic/files/report.txt"
        cases.append((product_contracts.validate_health_evidence_view, health_fact, "fact"))
        health_unknown = self.load_valid("health-evidence-view.json")
        health_unknown["unknowns"] = ["synthetic/files/report.txt"]
        cases.append((product_contracts.validate_health_evidence_view, health_unknown, "unknowns"))
        compass_rationale = self.load_valid("recovery-compass-snapshot.json")
        compass_rationale["season_focus"]["rationale"] = "synthetic/files/report.txt"
        cases.append((product_contracts.validate_recovery_compass_snapshot, compass_rationale, "rationale"))
        compass_unknown = self.load_valid("recovery-compass-snapshot.json")
        compass_unknown["unknowns"] = ["synthetic/files/report.txt"]
        cases.append((product_contracts.validate_recovery_compass_snapshot, compass_unknown, "unknowns"))
        campaign_unknown = self.load_valid("quarter-health-campaign.json")
        campaign_unknown["unknowns"] = ["synthetic/files/report.txt"]
        cases.append((product_contracts.validate_quarter_health_campaign, campaign_unknown, "unknowns"))
        weekly_description = self.load_valid("weekly-experiment.json")
        weekly_description["action_candidate"]["description"] = "synthetic/files/report.txt"
        cases.append((product_contracts.validate_weekly_experiment, weekly_description, "description"))
        weekly_unknown = self.load_valid("weekly-experiment.json")
        weekly_unknown["unknowns"] = ["synthetic/files/report.txt"]
        cases.append((product_contracts.validate_weekly_experiment, weekly_unknown, "unknowns"))
        guidance_zh = self.load_valid("professional-escalation.json")
        guidance_zh["guidance"]["zh"] = "合成路径 synthetic/files/report.txt"
        cases.append((product_contracts.validate_professional_escalation, guidance_zh, "guidance.zh"))
        guidance_en = self.load_valid("professional-escalation.json")
        guidance_en["guidance"]["en"] = "Synthetic path synthetic/files/report.txt"
        cases.append((product_contracts.validate_professional_escalation, guidance_en, "guidance.en"))
        escalation_unknown = self.load_valid("professional-escalation.json")
        escalation_unknown["unknowns"] = ["synthetic/files/report.txt"]
        cases.append((product_contracts.validate_professional_escalation, escalation_unknown, "unknowns"))

        for validate, document, slot in cases:
            with self.subTest(validator=validate.__name__, slot=slot):
                self.assertIn(
                    "FORBIDDEN_SENSITIVE_CONTENT",
                    [error.code for error in validate(document).errors],
                )

    def test_labelled_birth_record_name_and_contact_content_is_rejected(self):
        from yuanli_health_skills import validate_health_evidence_view

        labelled_values = (
            "D" + "OB: January 2, 1990",
            "medical " + "record ID: ABC-123",
            "Full " + "name: Synthetic Person",
            "出生日期：1990年1月2日",
            "病历号：ABC-123",
            "电话：13800000000",
        )
        for value in labelled_values:
            with self.subTest(value=value):
                document = copy.deepcopy(self.health_evidence)
                document["unknowns"] = [value]
                self.assertIn(
                    "FORBIDDEN_SENSITIVE_CONTENT",
                    [error.code for error in validate_health_evidence_view(document).errors],
                )

    def test_required_bilingual_escalation_guidance_remains_allowed(self):
        from yuanli_health_skills import validate_professional_escalation

        document = self.load_valid("professional-escalation.json")

        self.assertEqual(validate_professional_escalation(document).errors, ())

    def test_five_builders_and_validators_are_exported_by_the_public_package(self):
        import yuanli_health_skills

        names = (
            "build_health_evidence_view",
            "build_recovery_compass_snapshot",
            "build_quarter_health_campaign",
            "build_weekly_experiment",
            "build_professional_escalation",
            "validate_health_evidence_view",
            "validate_recovery_compass_snapshot",
            "validate_quarter_health_campaign",
            "validate_weekly_experiment",
            "validate_professional_escalation",
        )

        self.assertEqual(
            [name for name in names if not callable(getattr(yuanli_health_skills, name, None))],
            [],
        )

    def test_builders_add_fixed_boundaries_return_isolated_json_and_totalize_malformed_payloads(self):
        from yuanli_health_skills import product_contracts

        cases = (
            ("health-evidence-view.json", product_contracts.build_health_evidence_view),
            ("recovery-compass-snapshot.json", product_contracts.build_recovery_compass_snapshot),
            ("quarter-health-campaign.json", product_contracts.build_quarter_health_campaign),
            ("weekly-experiment.json", product_contracts.build_weekly_experiment),
            ("professional-escalation.json", product_contracts.build_professional_escalation),
        )
        boundary_fields = {"schema", "synthetic", "canonical_write", "persistence"}
        for filename, build in cases:
            with self.subTest(filename=filename):
                expected = self.load_valid(filename)
                payload = {key: copy.deepcopy(value) for key, value in expected.items() if key not in boundary_fields}
                built = build(payload)
                self.assertEqual(built.errors, ())
                self.assertEqual(getattr(built, "value", None), expected)
                payload.clear()
                self.assertEqual(built.value, expected)
                self.assertEqual(json.loads(json.dumps(built.value, ensure_ascii=False)), expected)

                malformed = build({"not_json": {"value"}})
                self.assertIsNone(getattr(malformed, "value", None))
                self.assertIn("NON_JSON_VALUE", [error.code for error in malformed.errors])

    def test_builder_serialization_is_repeatable_across_payload_order_and_results(self):
        from yuanli_health_skills import build_weekly_experiment

        expected = self.load_valid("weekly-experiment.json")
        boundary_fields = {"schema", "synthetic", "canonical_write", "persistence"}
        payload = {key: copy.deepcopy(value) for key, value in expected.items() if key not in boundary_fields}
        reversed_payload = dict(reversed(tuple(payload.items())))
        first = build_weekly_experiment(payload)
        second = build_weekly_experiment(reversed_payload)
        first_bytes = json.dumps(first.value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        second_bytes = json.dumps(second.value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        self.assertEqual(first_bytes, second_bytes)
        first.value["action_candidate"]["description"] = "mutated"
        self.assertEqual(second.value, expected)

    def test_nested_campaign_phase_booleans_are_rejected_by_validator_and_builder(self):
        from yuanli_health_skills import build_quarter_health_campaign, validate_quarter_health_campaign

        document = self.load_valid("quarter-health-campaign.json")
        document["phases"][0]["phase"] = True
        payload = {
            key: copy.deepcopy(value)
            for key, value in document.items()
            if key not in {"schema", "synthetic", "canonical_write", "persistence"}
        }

        self.assertIn(
            "INVALID_CAMPAIGN_PHASES",
            [error.code for error in validate_quarter_health_campaign(document).errors],
        )
        built = build_quarter_health_campaign(payload)
        self.assertFalse(built.ok)
        self.assertIsNone(built.value)

    def test_text_array_limit_matches_schema_for_all_validators_and_builders(self):
        from yuanli_health_skills import product_contracts

        cases = (
            ("health-evidence-view.json", product_contracts.validate_health_evidence_view, product_contracts.build_health_evidence_view),
            ("recovery-compass-snapshot.json", product_contracts.validate_recovery_compass_snapshot, product_contracts.build_recovery_compass_snapshot),
            ("quarter-health-campaign.json", product_contracts.validate_quarter_health_campaign, product_contracts.build_quarter_health_campaign),
            ("weekly-experiment.json", product_contracts.validate_weekly_experiment, product_contracts.build_weekly_experiment),
            ("professional-escalation.json", product_contracts.validate_professional_escalation, product_contracts.build_professional_escalation),
        )
        boundary_fields = {"schema", "synthetic", "canonical_write", "persistence"}
        for filename, validate, build in cases:
            for size, expected_ok in ((280, True), (281, False)):
                with self.subTest(filename=filename, size=size):
                    document = self.load_valid(filename)
                    document["unknowns"] = ["x" * size]
                    self.assertEqual(validate(document).ok, expected_ok)
                    payload = {
                        key: copy.deepcopy(value)
                        for key, value in document.items()
                        if key not in boundary_fields
                    }
                    result = build(payload)
                    self.assertEqual(result.ok, expected_ok)
                    self.assertEqual(result.value is not None, expected_ok)

    def test_five_source_json_schemas_are_closed_at_every_object_boundary(self):
        schema_names = (
            "health-evidence-view-v1",
            "recovery-compass-snapshot-v1",
            "quarter-health-campaign-v1",
            "weekly-experiment-v1",
            "professional-escalation-v1",
        )
        for schema_name in schema_names:
            with self.subTest(schema=schema_name):
                schema_path = ROOT / "contracts" / f"{schema_name}.schema.json"
                self.assertTrue(schema_path.is_file())
                document = json.loads(
                    schema_path.read_text(encoding="utf-8")
                )
                self.assertEqual(document["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertEqual(document["properties"]["schema"]["const"], schema_name)
                self.assertTrue(
                    {"schema", "synthetic", "canonical_write", "persistence"}.issubset(document["required"])
                )
                pending = [document]
                while pending:
                    node = pending.pop()
                    if isinstance(node, dict):
                        if node.get("type") == "object":
                            self.assertIs(node.get("additionalProperties"), False)
                        pending.extend(node.values())
                    elif isinstance(node, list):
                        pending.extend(node)

    def test_generator_packages_exact_product_schemas_and_checksums(self):
        from tests._adapter_support import generate, regular_files

        schema_names = (
            "health-evidence-view-v1",
            "recovery-compass-snapshot-v1",
            "quarter-health-campaign-v1",
            "weekly-experiment-v1",
            "professional-escalation-v1",
        )
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "yuanli-health"
            generate(package)
            files = regular_files(package)
        for schema_name in schema_names:
            relative = f"contracts/product-contracts/{schema_name}.schema.json"
            with self.subTest(schema=schema_name):
                self.assertIn(relative, files)
                self.assertEqual(files[relative], (ROOT / "contracts" / f"{schema_name}.schema.json").read_bytes())
                self.assertIn(f"  {relative}\n", files["SHA256SUMS"].decode("utf-8"))

    def test_stale_conflict_is_explicit_and_self_or_missing_conflict_references_are_rejected(self):
        from yuanli_health_skills.product_contracts import validate_health_evidence_view

        boundary = json.loads(
            (ROOT / "fixtures/product-contracts/boundary/stale-conflict.json").read_text(encoding="utf-8")
        )
        self.assertEqual(validate_health_evidence_view(boundary).errors, ())

        missing = copy.deepcopy(boundary)
        missing["conflicts_with"] = []
        self_reference = copy.deepcopy(boundary)
        self_reference["conflicts_with"] = [self_reference["evidence_id"]]
        self.assertIn(
            "CONFLICT_REFERENCE_REQUIRED",
            [error.code for error in validate_health_evidence_view(missing).errors],
        )
        self.assertIn(
            "SELF_REFERENCE",
            [error.code for error in validate_health_evidence_view(self_reference).errors],
        )

    def test_strict_json_cli_dispatches_all_five_product_contract_schemas(self):
        command = [
            sys.executable,
            str(ROOT / "scripts/validate_capabilities.py"),
            str(ROOT / "fixtures/product-contracts/valid"),
        ]

        completed = subprocess.run(command, check=False, capture_output=True, text=True)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.count(":OK\n"), 5)

    def test_hand_derived_adversarial_fixture_corpus_returns_named_codes(self):
        from yuanli_health_skills import product_contracts

        validators = {
            "health-evidence-view": product_contracts.validate_health_evidence_view,
            "recovery-compass-snapshot": product_contracts.validate_recovery_compass_snapshot,
            "quarter-health-campaign": product_contracts.validate_quarter_health_campaign,
            "weekly-experiment": product_contracts.validate_weekly_experiment,
            "professional-escalation": product_contracts.validate_professional_escalation,
        }
        cases = json.loads(
            (ROOT / "fixtures/product-contracts/adversarial/cases.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(cases), 11)
        for case in cases:
            with self.subTest(name=case["name"]):
                document = self.load_valid(case["base"])
                for field in case.get("remove", []):
                    del document[field]
                document.update(case.get("set", {}))
                if case.get("operation") == "duplicate_focus":
                    document["season_focus"] = [document["season_focus"], copy.deepcopy(document["season_focus"])]
                elif case.get("operation") == "duplicate_action":
                    document["action_candidate"] = [document["action_candidate"], copy.deepcopy(document["action_candidate"])]
                elif case.get("operation") == "deep_json":
                    nested = []
                    document["deep"] = nested
                    for _ in range(40):
                        child = []
                        nested.append(child)
                        nested = child
                elif case.get("operation") == "non_json_set":
                    document["non_json"] = {"value"}
                codes = [error.code for error in validators[case["contract"]](document).errors]
                for expected_code in case["expected_codes"]:
                    self.assertIn(expected_code, codes)


if __name__ == "__main__":
    unittest.main()
