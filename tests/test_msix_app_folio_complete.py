import json
import unittest
from pathlib import Path

from store_manager.live_draft import (
    StoreDraftRuntimeObservation,
    certification_review_state,
    store_draft_next_state,
)


class FolioCompleteTeacherDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parents[1]
        cls.fixture = json.loads(
            (
                cls.root
                / "tests"
                / "fixtures"
                / "partner_center_msix_pwa_app_folio_complete.json"
            ).read_text(encoding="utf-8")
        )
        cls.mapping = json.loads(
            (cls.root / "docs" / "PARTNER_CENTER_MAP.json").read_text(
                encoding="utf-8"
            )
        )

    def test_product_specific_values_stay_in_the_fixture(self):
        product = self.fixture["product_profile"]
        self.assertEqual(product["pricing"]["retail_price"], 780)
        self.assertEqual(product["package"]["version"], "1.0.3.0")
        self.assertEqual(product["listing_locales"], ["en-US", "ja-JP"])
        self.assertEqual(product["screenshot_count_per_listing"], 5)

    def test_iarc_owner_save_and_reload_are_observed(self):
        iarc = self.fixture["route_observation"]["iarc"]
        self.assertEqual(iarc["legal_attestation"], "PERFORMED_BY_PRODUCT_OWNER")
        self.assertEqual(iarc["overview"], "Complete")
        self.assertTrue(iarc["reload_retained"])
        self.assertEqual(iarc["iarc_version"], "10.4")
        self.assertEqual(iarc["ratings"]["IARC"], "3+")

    def test_iarc_answers_are_not_route_level_training_values(self):
        rule = self.fixture["iarc_teacher_rule"]
        self.assertTrue(rule["legal_attestation_must_not_be_inferred"])
        self.assertIn("questionnaire answers", rule["product_specific_do_not_copy"])
        self.assertIn("summary reload verification", rule["route_reuse"])

    def test_all_required_sections_are_complete_after_reload(self):
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
        self.assertTrue(overview["reloaded_after_iarc"])

    def test_route_state_machine_reaches_review_boundary(self):
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

    def test_missing_human_attestation_and_failed_reconcile_stop_closed(self):
        base = dict(
            package_saved=True,
            pricing_saved=True,
            properties_saved=True,
            iarc_questionnaire_complete=True,
        )
        self.assertEqual(
            store_draft_next_state(StoreDraftRuntimeObservation(**base)),
            "IARC_LEGAL_ATTESTATION_REQUIRED",
        )
        self.assertEqual(
            store_draft_next_state(
                StoreDraftRuntimeObservation(
                    **base,
                    iarc_legal_attestation_confirmed=True,
                    iarc_saved=True,
                    listing_saved=True,
                    submission_options_saved=True,
                    overview_reconciled=True,
                    retained_after_reload=False,
                )
            ),
            "DRAFT_RECONCILING",
        )

    def test_certification_and_publish_remain_unexecuted(self):
        safety = self.fixture["safety"]
        self.assertFalse(safety["submit_for_certification"])
        self.assertFalse(safety["publish"])
        self.assertEqual(self.fixture["outcome"]["status"], "READY_FOR_CERTIFICATION_REVIEW")
        self.assertEqual(
            self.fixture["outcome"]["teacher_data_status"],
            "FOLIO_MSIX_APP_TEACHER_DATA_PERSISTED",
        )
        self.assertEqual(
            store_draft_next_state(
                StoreDraftRuntimeObservation(certification_executed=True)
            ),
            "HOLD_PROHIBITED_ACTION_EXECUTED",
        )
        self.assertEqual(
            certification_review_state(
                draft_state="STORE_DRAFT_COMPLETE",
                certification_executed=False,
                publish_executed=True,
            ),
            "HOLD_PROHIBITED_ACTION_EXECUTED",
        )

    def test_route_map_records_two_products_without_enabling_certification(self):
        route = self.mapping["routes"]["msix_pwa_app"]
        self.assertEqual(route["observation_scope"]["observed_product_count"], 2)
        self.assertEqual(
            route["observation_scope"]["mode"],
            "TWO_PRODUCT_FULL_STORE_DRAFT_SAVE_RELOAD_VERIFIED",
        )
        self.assertEqual(
            route["store_draft_write_supported"],
            "VERIFIED_2_PRODUCT_PROFILE_GATED",
        )
        self.assertFalse(route["live_write_supported"])
        self.assertFalse(route["certification_write_supported"])
        self.assertFalse(route["publish_write_supported"])
        for section in (
            "pricing_availability",
            "properties",
            "age_ratings",
            "store_listings",
            "submission_options",
        ):
            self.assertIn("VERIFIED", route["section_verification"][section])

    def test_route_map_keeps_owner_attestation_and_reload_fail_closed(self):
        selectors = self.mapping["routes"]["msix_pwa_app"]["selectors"]
        attestation = selectors["age_ratings_legal_attestation"]
        self.assertTrue(attestation["verified"])
        self.assertTrue(attestation["requires_product_owner"])
        self.assertTrue(selectors["age_ratings_save_success"]["verified"])
        self.assertEqual(
            selectors["age_ratings_save_success"]["strategy"],
            "composite_overview_summary_reload",
        )


if __name__ == "__main__":
    unittest.main()
