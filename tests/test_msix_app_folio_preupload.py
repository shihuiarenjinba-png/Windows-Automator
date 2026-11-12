import json
import unittest
from pathlib import Path


class FolioMsixAppPreuploadTeacherDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parents[1]
        cls.fixture = json.loads(
            (
                cls.root
                / "tests"
                / "fixtures"
                / "partner_center_msix_pwa_app_folio_preupload.json"
            ).read_text(encoding="utf-8")
        )
        cls.mapping = json.loads(
            (cls.root / "docs" / "PARTNER_CENTER_MAP.json").read_text(encoding="utf-8")
        )

    def test_exact_product_draft_route_and_identity_are_fixed(self):
        self.assertEqual(self.fixture["route_id"], "msix_pwa_app")
        self.assertEqual(self.fixture["product"]["name"], "Folio AI")
        self.assertEqual(self.fixture["product"]["store_id"], "9P0VNLJ5FPF5")
        self.assertEqual(self.fixture["product"]["draft_id"], "1152921505702219486")
        self.assertEqual(self.fixture["identity"]["name"], "OkinawaDesktopTools.FolioAI")
        self.assertEqual(
            self.fixture["identity"]["publisher"],
            "CN=46263F21-A700-41DB-8C9B-114C22FB82FC",
        )

    def test_immutable_candidate_contract_is_exact(self):
        candidate = self.fixture["candidate"]
        self.assertEqual(candidate["version"], "1.0.3.0")
        self.assertEqual(candidate["architecture"], "x64")
        self.assertEqual(
            candidate["sha256"],
            "AEECFA80D79FFD9AFE2B290DCEF8E390FC0CA9433CC73335368B1164D9F4E459",
        )
        self.assertEqual(
            candidate["source_sha"],
            "cbb9de223c0eac79563651ba2d0ae22e43653d68",
        )

    def test_preupload_observation_did_not_write_partner_center(self):
        safety = self.fixture["safety"]
        self.assertFalse(any(safety.values()))
        self.assertEqual(self.fixture["mode"], "READ_ONLY_PREUPLOAD_NO_SAVE")
        self.assertEqual(self.fixture["outcome"]["status"], "HOLD_PRE_UPLOAD_CONFIRMATION")

    def test_observed_upload_and_warning_selectors_are_verified(self):
        app_route = self.mapping["routes"]["msix_pwa_app"]
        self.assertFalse(app_route["live_write_supported"])
        for key in (
            "packages_upload_status",
            "packages_warning_alert",
            "packages_package_row",
            "packages_desktop_checkbox",
            "packages_validation_state",
        ):
            self.assertTrue(app_route["selectors"][key]["verified"], key)

    def test_later_observed_states_do_not_enable_unattended_live_route(self):
        app_route = self.mapping["routes"]["msix_pwa_app"]
        for key in (
            "overview_section_states",
            "submission_options_restricted_capability_container",
            "submission_options_restricted_capability_textarea",
            "submission_options_save_success",
        ):
            self.assertTrue(app_route["selectors"][key]["verified"], key)
        self.assertEqual(
            app_route["observation_scope"]["mode"],
            "FULL_STORE_DRAFT_SAVE_RELOAD_VERIFIED",
        )
        self.assertFalse(app_route["live_write_supported"])
        self.assertFalse(app_route["certification_write_supported"])
        self.assertFalse(app_route["publish_write_supported"])

    def test_packages_save_and_overview_recovery_are_verified_but_route_remains_disabled(self):
        app_route = self.mapping["routes"]["msix_pwa_app"]
        for key in (
            "packages_section_state",
            "packages_save_success",
            "product_breadcrumb_overview_recovery",
            "product_overview_recovery_success",
        ):
            self.assertTrue(app_route["selectors"][key]["verified"], key)
        self.assertFalse(app_route["live_write_supported"])

    def test_observed_initial_values_are_not_promoted_to_owner_decisions(self):
        sections = self.fixture["observed_sections"]
        self.assertFalse(sections["pricing_availability"]["base_price_configured"])
        self.assertEqual(sections["properties"]["primary_category"], "Pick a category")
        self.assertFalse(sections["age_ratings"]["app_type_selected"])
        self.assertFalse(sections["packages"]["desktop_checked"])
        self.assertFalse(sections["submission_options"]["restricted_capability_section_visible"])


if __name__ == "__main__":
    unittest.main()
