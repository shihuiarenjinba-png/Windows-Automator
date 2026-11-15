import json
import unittest
from pathlib import Path

from store_manager.live_draft import (
    iarc_completion_next_action,
    store_field_resolution_next_action,
)


class FolioOwnerInputBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parents[1]
        cls.fixture = json.loads(
            (
                cls.root
                / "tests"
                / "fixtures"
                / "partner_center_msix_pwa_app_folio_owner_input.json"
            ).read_text(encoding="utf-8")
        )

    def test_packages_are_complete_before_owner_input(self):
        self.assertEqual(self.fixture["completed"]["packages"], "PACKAGE_SAVED")
        self.assertEqual(
            self.fixture["completed"]["overview_packages_state"],
            "Complete",
        )

    def test_price_is_exactly_780_yen_and_retained(self):
        pricing = self.fixture["pricing_decision"]
        self.assertEqual(pricing["currency"], "JPY")
        self.assertEqual(pricing["exact_retail_price"], 780)
        self.assertTrue(pricing["exact_match_available"])
        self.assertFalse(pricing["fallback_used"])
        retained = self.fixture["saved_and_reloaded"]["pricing_and_availability"]
        self.assertEqual(retained["reload_postcondition"]["retail_price"], 780)

    def test_current_market_state_is_preserved_without_owner_question(self):
        markets = self.fixture["current_value_preserved"]["pricing_and_availability"]
        self.assertEqual(markets["resolution"], "CURRENT_VALUE_PRESERVE")
        self.assertEqual(markets["markets"], "All worldwide markets")
        self.assertTrue(markets["future_markets"])

    def test_repo_evidence_resolves_properties_iarc_and_capability(self):
        resolved = self.fixture["evidence_value_ready"]
        self.assertEqual(resolved["properties"]["primary_category"], "Productivity")
        self.assertEqual(resolved["properties"]["privacy_delivery_mode"], "partner_center_inline_text")
        self.assertTrue(resolved["properties"]["generative_ai_declared"])
        self.assertEqual(resolved["age_ratings"]["app_type"], "All Other App Types")
        self.assertEqual(resolved["submission_options"]["restricted_capability"], "runFullTrust")
        self.assertEqual(resolved["submission_options"]["resolution"], "EVIDENCE_VALUE_APPLY")

    def test_listing_assets_are_recorded_as_five_shared_japanese_ui_images(self):
        listings = self.fixture["evidence_value_ready"]["store_listings"]
        self.assertEqual(listings["languages"], ["en-us", "ja-jp"])
        self.assertEqual(listings["screenshot_asset_count"], 5)
        self.assertEqual(listings["screenshot_ui_language"], "ja-JP")
        self.assertEqual(listings["screenshot_reuse"], "same_verified_assets_for_both_listings")
        self.assertEqual(listings["en_us_status"], "Complete")
        self.assertEqual(listings["ja_jp_status"], "Complete")

    def test_file_chooser_timeout_requires_reconcile_before_retry(self):
        teacher = self.fixture["screenshot_upload_teacher_data"]
        self.assertIn("Desktop count", teacher["timeout_reconcile"])
        self.assertIn("prevented duplicate", teacher["observed_timeout_result"])

    def test_resolution_state_machine_avoids_blanket_owner_input(self):
        self.assertEqual(
            store_field_resolution_next_action(
                current_value_present=True,
                evidence_value_present=False,
                new_business_or_legal_decision=False,
            ),
            "CURRENT_VALUE_PRESERVE",
        )
        self.assertEqual(
            store_field_resolution_next_action(
                current_value_present=False,
                evidence_value_present=True,
                new_business_or_legal_decision=False,
            ),
            "EVIDENCE_VALUE_APPLY",
        )
        self.assertEqual(
            store_field_resolution_next_action(
                current_value_present=False,
                evidence_value_present=False,
                new_business_or_legal_decision=True,
            ),
            "OWNER_INPUT_REQUIRED",
        )

    def test_only_iarc_legal_attestation_remains(self):
        safety = self.fixture["safety"]
        self.assertTrue(safety["pricing_changed"])
        self.assertTrue(safety["properties_saved"])
        self.assertTrue(safety["listings_saved"])
        self.assertTrue(safety["submission_options_saved"])
        self.assertFalse(safety["iarc_saved"])
        self.assertFalse(safety["submitted"])
        self.assertFalse(safety["published"])
        self.assertTrue(
            self.fixture["owner_input_required"]["iarc_legal_attestation"][
                "script_must_not_infer"
            ]
        )
        self.assertEqual(
            self.fixture["outcome"]["status"],
            "OWNER_INPUT_REQUIRED_IARC_LEGAL_ATTESTATION",
        )

    def test_iarc_state_machine_stops_before_personal_attestation(self):
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
            iarc_completion_next_action(
                questionnaire_complete=True,
                preview_generated=True,
                legal_attestation_confirmed=True,
                save_completed=False,
                retained_after_reload=False,
            ),
            "IARC_SAVE_REQUIRED",
        )


if __name__ == "__main__":
    unittest.main()
