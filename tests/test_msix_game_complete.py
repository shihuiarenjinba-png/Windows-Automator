import json
import unittest
from pathlib import Path

from store_manager.store_listings import (
    StoreListingSaveObservation,
    store_listing_next_action,
)


class MsixGameCompleteTeacherDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parents[1]
        cls.fixture = json.loads(
            (
                cls.root
                / "tests"
                / "fixtures"
                / "partner_center_msix_pwa_game_complete.json"
            ).read_text(encoding="utf-8")
        )
        cls.mapping = json.loads(
            (cls.root / "docs" / "PARTNER_CENTER_MAP.json").read_text(
                encoding="utf-8"
            )
        )

    def test_two_independent_game_products_are_recorded(self):
        self.assertEqual(self.fixture["observed_products"], 2)
        us, jp = self.fixture["products"]
        self.assertEqual(us["store_id"], "9PJCWW6G6D42")
        self.assertEqual(us["draft_id"], "1152921505702134687")
        self.assertEqual(us["package"]["version"], "0.25.25.0")
        self.assertEqual(jp["store_id"], "9PM2R3N22JX8")
        self.assertEqual(jp["draft_id"], "1152921505702134539")
        self.assertEqual(jp["package"]["version"], "0.1.24.0")

    def test_all_six_sections_are_complete_after_reload(self):
        for product in self.fixture["products"]:
            overview = product["overview"]
            for section in (
                "pricing_and_availability",
                "properties",
                "age_ratings",
                "packages",
                "store_listings",
                "submission_options",
            ):
                self.assertEqual(overview[section], "Complete", (product["name"], section))
            self.assertTrue(overview["final_reload_retained"])
            self.assertTrue(all(state == "Complete" for state in product["language_states"].values()))

    def test_us_listing_observed_exact_increment_sequence(self):
        observation = self.fixture["store_listing_observation"]
        self.assertEqual(observation["desktop_upload_count_sequence"], [0, 1, 2, 3, 4, 5])
        self.assertTrue(observation["fields_retained_exactly"])
        self.assertTrue(observation["manage_languages_reload_verified"])
        self.assertTrue(observation["overview_reconciled"])

    def test_final_observation_advances_to_listing_saved(self):
        us = self.fixture["products"][0]
        observation = StoreListingSaveObservation(
            save_requested=True,
            redirected_to_overview=True,
            overview_state=us["overview"]["store_listings"],
            reload_completed=us["overview"]["final_reload_retained"],
            exact_fields_retained=self.fixture["store_listing_observation"]["fields_retained_exactly"],
            expected_screenshot_count=5,
            reloaded_screenshot_count=us["desktop_screenshot_count_per_locale"],
            language_states=tuple(us["language_states"].values()),
            dirty=False,
        )
        self.assertEqual(store_listing_next_action(observation), "LISTING_SAVED")

    def test_route_map_is_verified_but_certification_and_publish_stay_gated(self):
        route = self.mapping["routes"]["msix_pwa_game"]
        self.assertEqual(route["observation_scope"]["observed_product_count"], 2)
        self.assertEqual(
            route["store_draft_write_supported"],
            "VERIFIED_2_PRODUCT_PROFILE_GATED",
        )
        self.assertEqual(
            route["teacher_data_status"],
            "MULTI_PRODUCT_MSIX_GAME_ROUTE_VERIFIED",
        )
        self.assertFalse(route["certification_write_supported"])
        self.assertFalse(route["publish_write_supported"])
        self.assertFalse(self.fixture["safety"]["submit_for_certification"])
        self.assertFalse(self.fixture["safety"]["publish"])
        self.assertEqual(
            self.fixture["outcome"]["status"],
            "CERTIFICATION_REVIEW_GATES_PRESERVED",
        )
        us, jp = self.fixture["products"]
        self.assertEqual(us["certification_gate"], "READY_FOR_CERTIFICATION_REVIEW")
        self.assertEqual(jp["certification_gate"], "HOLD_EXISTING_SAVE_MIGRATION_REVIEW")
        self.assertEqual(
            route["product_certification_gates"][jp["store_id"]],
            "HOLD_EXISTING_SAVE_MIGRATION_REVIEW",
        )


if __name__ == "__main__":
    unittest.main()
