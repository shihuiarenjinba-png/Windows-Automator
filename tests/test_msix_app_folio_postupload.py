import json
import unittest
from pathlib import Path

from store_manager.live_draft import PackageRuntimeObservation, package_next_action
from store_manager.restricted_capabilities import RUNFULLTRUST_PACKAGE_WARNING


class FolioMsixAppPostuploadTeacherDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parents[1]
        cls.fixture = json.loads(
            (
                cls.root
                / "tests"
                / "fixtures"
                / "partner_center_msix_pwa_app_folio_postupload_presave.json"
            ).read_text(encoding="utf-8")
        )

    def test_exact_candidate_and_raw_warning_are_retained(self):
        candidate = self.fixture["candidate"]
        self.assertEqual(candidate["version"], "1.0.3.0")
        self.assertEqual(candidate["architecture"], "X64")
        self.assertEqual(
            candidate["sha256"],
            "AEECFA80D79FFD9AFE2B290DCEF8E390FC0CA9433CC73335368B1164D9F4E459",
        )
        validation = self.fixture["validation"]
        self.assertEqual(validation["raw_state"], "WARNING")
        self.assertEqual(validation["warning"], RUNFULLTRUST_PACKAGE_WARNING)
        self.assertEqual(validation["error"], "")

    def test_analysis_auto_selected_only_desktop(self):
        families = self.fixture["device_families"]
        self.assertFalse(families["desktop_before_upload"])
        self.assertTrue(families["desktop_after_analysis"])
        self.assertEqual(
            families["desktop_transition"],
            "AUTO_SELECTED_BY_PARTNER_CENTER",
        )
        for key in ("mobile", "xbox", "team", "mixed_reality"):
            self.assertFalse(families[key], key)

    def test_observed_state_requires_save_not_reupload(self):
        action = package_next_action(
            PackageRuntimeObservation(
                package_present=True,
                validation="WARNING",
                warning=self.fixture["validation"]["warning"],
                desktop_checked=True,
            )
        )
        self.assertEqual(action, "PACKAGE_SAVE_REQUIRED")
        self.assertEqual(self.fixture["outcome"]["status"], action)
        self.assertFalse(self.fixture["save"]["clicked"])
        self.assertFalse(self.fixture["save"]["reload_verified"])

    def test_timeout_recovery_did_not_duplicate_upload(self):
        recovery = self.fixture["failure_recovery"]
        self.assertEqual(recovery["prior_state"], "FILE_CHOOSER_TIMEOUT")
        self.assertFalse(recovery["reconcile_package_present"])
        self.assertFalse(recovery["duplicate_write_detected"])
        self.assertEqual(recovery["next_state"], "SAFE_RETRY_ALLOWED")


if __name__ == "__main__":
    unittest.main()
