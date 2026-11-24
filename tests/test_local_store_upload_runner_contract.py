from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LocalStoreUploadRunnerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / "scripts" / "run_local_store_upload.ps1").read_text(encoding="utf-8")

    def test_output_paths_and_queue_are_initialized_by_the_runner(self):
        for name in ("live-report.json", "live-report.md", "single-product-queue.json"):
            self.assertIn(name, self.text)
        self.assertIn("@($product) | ConvertTo-Json", self.text)
        self.assertIn("--queue $queuePath", self.text)

    def test_package_is_hashed_and_identity_binding_is_checked_before_live_call(self):
        self.assertIn("Get-FileHash", self.text)
        self.assertIn("PACKAGE_SHA256_MISMATCH", self.text)
        self.assertIn("HOLD_IDENTITY_OR_PACKAGE_BINDING_MISMATCH", self.text)
        self.assertLess(self.text.index("IDENTITY_REVERIFY"), self.text.index("LIVE_DRAFT_SAVE"))
        self.assertLess(self.text.index("EXISTING_DRAFT_RECONCILE"), self.text.index("LIVE_DRAFT_SAVE"))

    def test_read_only_is_default_and_live_requires_action_time_switch(self):
        self.assertIn('[string]$Mode = "ReadOnly"', self.text)
        self.assertIn("LiveDraft mode requires -ConfirmLiveDraft at action time.", self.text)

    def test_certification_and_publish_are_never_invoked_or_reported_as_done(self):
        self.assertNotIn("Submit for certification", self.text)
        self.assertNotIn("Publish now", self.text)
        self.assertIn("PROHIBITED_CERTIFICATION_OR_PUBLISH_SIDE_EFFECT", self.text)


if __name__ == "__main__":
    unittest.main()
