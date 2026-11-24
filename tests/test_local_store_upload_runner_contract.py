from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LocalStoreUploadRunnerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / "scripts" / "run_local_store_upload.ps1").read_text(encoding="utf-8")

    def test_output_paths_are_scoped_to_a_unique_attempt_directory(self):
        for name in (
            "identity-reverify.json",
            "submission-state.json",
            "live-report.json",
            "live-report.md",
            "live-report-verification.json",
            "single-product-queue.json",
            "attempt-manifest.json",
        ):
            self.assertIn(name, self.text)
        self.assertIn("[guid]::NewGuid()", self.text)
        self.assertIn("$runDir = Join-Path $outRoot $runId", self.text)
        self.assertIn("RUN_DIRECTORY_COLLISION", self.text)
        self.assertIn("ATTEMPT_MANIFEST_ALREADY_EXISTS", self.text)

    def test_one_item_queue_is_serialized_as_an_array_and_read_back(self):
        self.assertIn("ConvertTo-Json -InputObject @($product) -Depth 40", self.text)
        self.assertIn('$normalizedQueueText.StartsWith("[")', self.text)
        self.assertIn('$normalizedQueueText.EndsWith("]")', self.text)
        self.assertIn("$queueData = @(ConvertFrom-Json -InputObject $normalizedQueueText", self.text)
        self.assertIn("$queueData.Count -ne 1", self.text)
        self.assertIn("QUEUE_PRODUCT_BINDING_MISMATCH", self.text)
        self.assertNotIn("@($product) | ConvertTo-Json", self.text)

    def test_package_is_hashed_and_identity_binding_is_checked_before_live_call(self):
        self.assertIn("Get-FileHash", self.text)
        self.assertIn("PACKAGE_SHA256_MISMATCH", self.text)
        self.assertIn("HOLD_IDENTITY_OR_PACKAGE_BINDING_MISMATCH", self.text)
        self.assertLess(self.text.index("IDENTITY_REVERIFY"), self.text.index("LIVE_DRAFT_SAVE"))
        self.assertLess(self.text.index("EXISTING_DRAFT_RECONCILE"), self.text.index("LIVE_DRAFT_SAVE"))

    def test_read_only_is_default_and_live_requires_action_time_switch(self):
        self.assertIn('[string]$Mode = "ReadOnly"', self.text)
        self.assertIn("LiveDraft mode requires -ConfirmLiveDraft at action time.", self.text)
        self.assertIn('if ($Mode -eq "ReadOnly")', self.text)

    def test_final_report_must_pass_python_binding_and_safety_verifier(self):
        self.assertIn("verify-live-report --report $liveJson --input $inputPath --output $verificationJson", self.text)
        self.assertIn("HOLD_LIVE_REPORT_VERIFICATION_FAILED", self.text)
        self.assertNotIn("$result.details.submitted", self.text)
        self.assertNotIn("$result.details.certified", self.text)
        self.assertNotIn("$result.details.published", self.text)

    def test_secrets_are_not_written_to_attempt_manifest_or_console(self):
        self.assertNotIn("CdpUrl =", self.text)
        self.assertNotIn("cdp_url =", self.text)
        self.assertNotIn("Write-Host $CdpUrl", self.text)

    def test_certification_and_publish_are_never_invoked_or_reported_as_done(self):
        self.assertNotIn("Submit for certification", self.text)
        self.assertNotIn("Publish now", self.text)
        self.assertIn("verify-live-report", self.text)


if __name__ == "__main__":
    unittest.main()
