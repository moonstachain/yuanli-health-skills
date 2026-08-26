import importlib
import sys
import unittest

from tests._gold_support import ROOT, walk_keys


sys.path.insert(0, str(ROOT / "src"))


class RouterTests(unittest.TestCase):
    def setUp(self):
        try:
            self.router = importlib.import_module("yuanli_health_skills.router")
        except ModuleNotFoundError as exc:
            self.fail(f"Experience-only Router is not implemented: {exc}")

    def test_first_session_routes_only_to_the_available_experience(self):
        result = self.router.route_jtbd(
            "first_health_session",
            [
                "yuanli.health.kernel.ctx",
                "yuanli.health.meta.build",
                "yuanli.health.experience.first-health-session",
            ],
        )
        self.assertEqual(result["route_state"], "selected")
        self.assertEqual(
            result["source_capability_id"],
            "yuanli.health.experience.first-health-session",
        )
        self.assertIs(result["health_priority_decided"], False)
        self.assertTrue(
            {"priority", "rank", "primary_bottleneck", "diagnosis", "clinical_decision"}.isdisjoint(
                set(walk_keys(result))
            )
        )

    def test_founder_ninety_day_launch_without_dec_routes_to_first_session(self):
        available = [
            "yuanli.health.experience.first-health-session",
            "yuanli.health.experience.ninety-day-health-experiment",
        ]

        launch = self.router.route_jtbd("90天起盘", available)

        self.assertEqual(
            launch["source_capability_id"],
            "yuanli.health.experience.first-health-session",
        )
        self.assertIs(launch["health_priority_decided"], False)
        self.assertTrue({"wpk_candidate_id", "act_candidate_id"}.isdisjoint(launch))

    def test_founder_ninety_day_launch_with_supplied_dec_routes_to_the_experiment(self):
        result = self.router.route_jtbd(
            "90天起盘",
            [
                "yuanli.health.experience.first-health-session",
                "yuanli.health.experience.ninety-day-health-experiment",
            ],
            decision_candidate_id="DEC-SUPPLIED-BY-SUBJECT",
        )

        self.assertEqual(
            result["source_capability_id"],
            "yuanli.health.experience.ninety-day-health-experiment",
        )
        self.assertIs(result["health_priority_decided"], False)

    def test_founder_ninety_day_launch_with_dec_never_falls_back_to_kickoff(self):
        result = self.router.route_jtbd(
            "90天起盘",
            ["yuanli.health.experience.first-health-session"],
            decision_candidate_id="DEC-SUPPLIED-BY-SUBJECT",
        )

        self.assertEqual(result["route_state"], "no_route")
        self.assertIsNone(result["source_capability_id"])
        self.assertEqual(result["reason_code"], "EXPERIENCE_UNAVAILABLE")
        self.assertIs(result["health_priority_decided"], False)

    def test_kernel_or_meta_availability_never_becomes_a_fallback_route(self):
        result = self.router.route_jtbd(
            "first_health_session",
            ["yuanli.health.kernel.ctx", "yuanli.health.meta.build"],
        )
        self.assertEqual(result["route_state"], "no_route")
        self.assertIsNone(result["source_capability_id"])
        self.assertIs(result["health_priority_decided"], False)

    def test_unsupported_or_malformed_jtbd_returns_a_stable_no_route(self):
        unsupported = self.router.route_jtbd(
            "unsupported_synthetic_jtbd",
            ["yuanli.health.experience.first-health-session"],
        )
        malformed = self.router.route_jtbd(None, [])
        self.assertEqual(unsupported["reason_code"], "UNSUPPORTED_JTBD")
        self.assertEqual(malformed["reason_code"], "INVALID_JTBD")
        self.assertEqual(unsupported["route_state"], "no_route")
        self.assertEqual(malformed["route_state"], "no_route")


if __name__ == "__main__":
    unittest.main()
