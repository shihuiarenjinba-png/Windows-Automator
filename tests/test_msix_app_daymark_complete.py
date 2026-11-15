import json
import unittest
from pathlib import Path

from store_manager.live_draft import (
    StoreDraftRuntimeObservation,
    certification_review_state,
    iarc_completion_next_action,
    store_draft_next_state,
)
from store_manager.store_listings import screenshot_upload_next_action


class DaymarkCompleteTeacherDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parents[1]
        cls.fixture = json.loads(
            (
                cls.root
                / "tests"
                / "fixtures"
                / "partner_center_msix_pwa_app_daymark_complete.json"
            ).read_text(encoding="utf-8")
        )
        cls.mapping = json.loads(
            (cls.root / "docs" / "PARTNER_CENTER_MAP.json").read_text(
                encoding="utf-8"
            )
        )

    def test_daymark_profile_is_not_folio_data(self):
        product = self.fixture["product_profile"]
        self.assertEqual(product["name"], "Daymark AI")
        self.assertEqual(product["store_id"], "9PKJ9KMJZBC0")
        self.assertEqual(product["identity"], "OkinawaDesktopTools.DaymarkAI")
        self.assertEqual(product["package"]["version"], "1.0.4.0")
        self.assertEqual(product["properties"]["category"], "Lifestyle")
        self.assertFalse(product["properties"]["ai_required"])

    def test_all_required_sections_are_complete_after_final_reload(self):
        overview = self.fixture["route_observation"]["overview"]
        for section in (
            "pricing_and_availability",
            "properties",
            "age_ratings",
            "packages",
            "store_listings",
            "submission_options",
        ):
            self.assertEqual(overview[section], "Complete", section)
        self.assertTrue(overview["final_reload_retained"])

    def test_generative_ai_takes_the_online_content_branch_only(self):
        iarc = self.fixture["route_observation"]["iarc"]
        self.assertTrue(iarc["answers"]["online_content"])
        for key in (
            "violence",
            "sexuality",
            "offensive_language",
            "controlled_substance",
            "user_content_sharing",
        ):
            self.assertFalse(iarc["answers"][key], key)
        self.assertEqual(iarc["legal_attestation"], "PERFORMED_BY_PRODUCT_OWNER")
        self.assertEqual(iarc["ratings"]["IARC"], "3+")

    def test_iarc_boundary_still_requires_one_owner_handoff(self):
        self.assertEqual(
            iarc_completion_next_action(
                questionnaire_complete=True,
                preview_generated=True,
                legal_attestation_confirmed=False,
                save_completed=False,
                retained_after_reload=False,
            ),
            "OWNER_INPUT_REQUIRED_IARC_LEGAL_ATTESTATION",
        )
        self.assertEqual(
            self.fixture["teacher_rules"]["iarc"]["owner_handoff_count"],
            1,
        )

    def test_screenshot_upload_never_trusts_setfiles_alone(self):
        self.assertEqual(
            screenshot_upload_next_action(
                previous_count=1,
                desktop_count=1,
                thumbnail_count=1,
            ),
            "SCREENSHOT_RECONCILE_REQUIRED",
        )
        self.assertEqual(
            screenshot_upload_next_action(
                previous_count=1,
                desktop_count=2,
                thumbnail_count=2,
            ),
            "SCREENSHOT_UPLOAD_CONFIRMED",
        )

    def test_runfulltrust_limit_and_manual_publish_are_retained(self):
        options = self.fixture["route_observation"]["submission_options"]
        self.assertLessEqual(
            options["run_full_trust_explanation_length"],
            options["run_full_trust_maxlength"],
        )
        self.assertTrue(options["manual_publish"])
        self.assertTrue(options["reload_retained"])

    def test_route_is_verified_on_two_independent_app_products(self):
        route = self.mapping["routes"]["msix_pwa_app"]
        self.assertEqual(self.fixture["observed_products"], 2)
        self.assertEqual(route["observation_scope"]["observed_product_count"], 2)
        self.assertEqual(len(route["observation_scope"]["products"]), 2)
        self.assertEqual(
            route["store_draft_write_supported"],
            "VERIFIED_2_PRODUCT_PROFILE_GATED",
        )
        self.assertFalse(route["certification_write_supported"])
        self.assertFalse(route["publish_write_supported"])

    def test_state_machine_stops_at_certification_review(self):
        observation = StoreDraftRuntimeObservation(
            package_saved=True,
            pricing_saved=True,
            properties_saved=True,
            iarc_questionnaire_complete=True,
            iarc_legal_attestation_confirmed=True,
            iarc_saved=True,
            listing_saved=True,
            submission_options_saved=True,
            overview_reconciled=True,
            retained_after_reload=True,
        )
        draft_state = store_draft_next_state(observation)
        self.assertEqual(draft_state, "STORE_DRAFT_COMPLETE")
        self.assertEqual(
            certification_review_state(
                draft_state=draft_state,
                certification_executed=False,
                publish_executed=False,
            ),
            "READY_FOR_CERTIFICATION_REVIEW",
        )


if __name__ == "__main__":
    unittest.main()
