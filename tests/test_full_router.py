import unittest

from tests._full_support import CAPABILITIES
from yuanli_health_skills.router import route_jtbd


class FullRouterTests(unittest.TestCase):
    def test_all_six_experience_jtbds_route_exactly(self):
        routes = {
            "first_health_session": "yuanli.health.experience.first-health-session",
            "ninety_day_health_experiment": "yuanli.health.experience.ninety-day-health-experiment",
            "weekly_health_checkpoint": "yuanli.health.experience.weekly-health-checkpoint",
            "doctor_visit_prep": "yuanli.health.experience.doctor-visit-prep",
            "outcome_review": "yuanli.health.experience.outcome-review",
            "learning_reuse": "yuanli.health.experience.learning-reuse",
        }
        available = list(CAPABILITIES) + ["yuanli.health.experience.first-health-session"]
        for jtbd, source_id in routes.items():
            with self.subTest(jtbd=jtbd):
                result = route_jtbd(jtbd, available)
                self.assertEqual(result["route_state"], "selected")
                self.assertEqual(result["source_capability_id"], source_id)
                self.assertIs(result["health_priority_decided"], False)

    def test_router_never_falls_back_to_kernel_meta_or_another_experience(self):
        available = ["yuanli.health.kernel.wpk", "yuanli.health.meta.build", "yuanli.health.experience.learning-reuse"]
        result = route_jtbd("outcome_review", available)
        self.assertEqual(result["route_state"], "no_route")
        self.assertEqual(result["reason_code"], "EXPERIENCE_UNAVAILABLE")
        self.assertIsNone(result["source_capability_id"])


if __name__ == "__main__":
    unittest.main()
