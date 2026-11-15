import json
import unittest
from pathlib import Path

from store_manager.live_draft import (
    GameRuntimeQaObservation,
    game_certification_review_state,
    game_runtime_qa_next_state,
)
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
            "RUNTIME_QA_REQUIRED",
        )
        us, jp = self.fixture["products"]
        self.assertEqual(us["certification_gate"], "RUNTIME_QA_REQUIRED_POLICY_BLOCK")
        self.assertEqual(jp["certification_gate"], "RUNTIME_QA_REQUIRED_POLICY_BLOCK")
        self.assertEqual(
            route["product_certification_gates"][jp["store_id"]],
            "RUNTIME_QA_REQUIRED_POLICY_BLOCK",
        )

    def test_game_route_requires_runtime_state_transitions_before_review(self):
        blocked = GameRuntimeQaObservation(
            exact_package_source_provenance=True,
            runtime_policy_blocked=True,
            legacy_save_source="development_qa",
        )
        state = game_runtime_qa_next_state(blocked)
        self.assertEqual(state, "RUNTIME_QA_REQUIRED_POLICY_BLOCK")
        self.assertEqual(
            game_certification_review_state(
                draft_state="STORE_DRAFT_COMPLETE",
                runtime_qa_state=state,
                package_decision="UNDECIDED",
                certification_executed=False,
                publish_executed=False,
            ),
            "RUNTIME_QA_REQUIRED_POLICY_BLOCK",
        )

    def test_game_route_promotes_only_full_e2e_plus_package_keep(self):
        passed = GameRuntimeQaObservation(
            exact_package_source_provenance=True,
            clean_launch=True,
            start=True,
            gameplay_progress=True,
            major_controls=True,
            save=True,
            relaunch=True,
            restore=True,
            continue_gameplay=True,
            normal_exit=True,
            store_listing_matches_runtime=True,
            legacy_save_source="development_qa",
        )
        state = game_runtime_qa_next_state(passed)
        self.assertEqual(state, "RUNTIME_FUNCTIONAL_QA_PASS")
        self.assertEqual(
            game_certification_review_state(
                draft_state="STORE_DRAFT_COMPLETE",
                runtime_qa_state=state,
                package_decision="PACKAGE_KEEP",
                certification_executed=False,
                publish_executed=False,
            ),
            "READY_FOR_CERTIFICATION_REVIEW",
        )

    def test_public_legacy_save_incompatibility_requires_replacement(self):
        observation = GameRuntimeQaObservation(
            exact_package_source_provenance=True,
            legacy_save_source="public_release",
            legacy_save_compatible=False,
        )
        self.assertEqual(
            game_runtime_qa_next_state(observation),
            "PACKAGE_REPLACEMENT_REQUIRED",
        )

    def test_current_runtime_qa_fixture_is_fail_closed_without_claiming_replacement(self):
        runtime_fixture = json.loads(
            (
                self.root
                / "tests"
                / "fixtures"
                / "partner_center_msix_pwa_game_runtime_qa_20261115.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(runtime_fixture["outcome"]["current_packages_may_be_sold_now"])
        self.assertFalse(runtime_fixture["outcome"]["replacement_proven"])
        self.assertEqual(
            runtime_fixture["outcome"]["runtime_qa_state"],
            "RUNTIME_QA_REQUIRED_POLICY_BLOCK",
        )
        us, jp = runtime_fixture["products"]
        self.assertEqual(us["package"]["package_source_provenance"], "PASS")
        self.assertEqual(jp["legacy_save"]["classification"], "LEGACY_DEV_SAVE_NONBLOCKING")
        self.assertFalse(jp["legacy_save"]["public_release_exposure"])


if __name__ == "__main__":
    unittest.main()
