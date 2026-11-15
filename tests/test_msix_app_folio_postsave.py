import json
import unittest
from pathlib import Path

from store_manager.live_draft import session_expiry_recovery_next_action


class FolioMsixAppPostsaveTeacherDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parents[1]
        cls.fixture = json.loads(
            (
                cls.root
                / "tests"
                / "fixtures"
                / "partner_center_msix_pwa_app_folio_postsave.json"
            ).read_text(encoding="utf-8")
        )

    def test_save_success_uses_overview_and_reopen_not_button_state(self):
        save = self.fixture["save"]
        self.assertTrue(save["clicked_once"])
        self.assertTrue(save["same_draft"])
        self.assertEqual(save["overview_validation"], "Validated")
        self.assertEqual(save["overview_section_state"], "Complete")
        self.assertTrue(self.fixture["reopen_before_reload"]["package_retained"])

    def test_expired_section_page_recovers_through_product_breadcrumb(self):
        recovery = self.fixture["reload_recovery"]
        self.assertFalse(recovery["authentication_automated"])
        self.assertEqual(recovery["recovery_control"]["role"], "link")
        self.assertEqual(recovery["recovery_control"]["name"], "Folio AI")
        self.assertEqual(recovery["recovery_control"]["href"], "#")
        action = session_expiry_recovery_next_action(
            session_expired_dialog=True,
            product_breadcrumb_available=True,
            product_overview_visible=False,
            packages_complete=False,
        )
        self.assertEqual(action, "NAVIGATE_PRODUCT_OVERVIEW")
        self.assertEqual(recovery["overview_packages_status"], "Complete")
        self.assertEqual(recovery["overview_packages_validation"], "Validated")

    def test_package_is_retained_after_recovery_and_reopen(self):
        reopened = self.fixture["reopen_after_recovery"]
        self.assertTrue(reopened["package_retained"])
        self.assertEqual(reopened["version"], "v1.0.3.0")
        self.assertEqual(reopened["architecture"], "X64")
        self.assertTrue(reopened["desktop_checked"])
        self.assertEqual(reopened["raw_validation"], "WARNING")
        self.assertEqual(self.fixture["outcome"]["status"], "PACKAGE_SAVED")

    def test_certification_and_publish_remain_untouched(self):
        safety = self.fixture["safety"]
        self.assertFalse(safety["duplicate_upload"])
        self.assertFalse(safety["duplicate_save"])
        self.assertFalse(safety["submitted"])
        self.assertFalse(safety["published"])


if __name__ == "__main__":
    unittest.main()
