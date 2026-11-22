from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_group_c_store_teacher.ps1"


class GroupCStoreTeacherRunnerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_read_only_is_default(self):
        self.assertIn('[ValidateSet("ReadOnly","LiveDraft")][string]$Mode = "ReadOnly"', self.text)

    def test_live_requires_explicit_action_time_confirmation(self):
        self.assertIn("LiveDraft mode requires -ConfirmLiveDraft at action time.", self.text)
        self.assertIn("--confirm-live-draft", self.text)

    def test_identity_and_submission_state_are_checked_before_live_write(self):
        self.assertLess(self.text.index("verify-existing-identity"), self.text.index("inspect-existing-submission-state"))
        self.assertLess(self.text.index("inspect-existing-submission-state"), self.text.index("night-run"))

    def test_existing_draft_is_required_for_this_runner(self):
        self.assertIn('EXISTING_PRODUCT_DRAFT_PRESENT', self.text)
        self.assertIn('HOLD_EXISTING_DRAFT_REQUIRED', self.text)
        self.assertLess(self.text.index('HOLD_EXISTING_DRAFT_REQUIRED'), self.text.index('GROUP_C_TEACHER_PROBE_PASS'))

    def test_read_only_probe_binds_exact_product_identity_source_package_and_draft(self):
        for hold_code in (
            "HOLD_STORE_ID_MISMATCH",
            "HOLD_IDENTITY_NAME_MISMATCH",
            "HOLD_PUBLISHER_MISMATCH",
            "HOLD_SOURCE_SHA_MISMATCH",
            "HOLD_PACKAGE_SHA_MISMATCH",
            "HOLD_EXACT_DRAFT_ID_REQUIRED",
            "HOLD_DRAFT_ID_MISMATCH",
        ):
            self.assertIn(hold_code, self.text)
        self.assertIn("$product.draft_id", self.text)
        self.assertIn("$state.draft_id", self.text)
        self.assertIn("$identity.store_id", self.text)
        self.assertIn("$identity.identity_name", self.text)
        self.assertIn("$identity.publisher", self.text)

    def test_formal_input_validate_precedes_live_draft(self):
        self.assertLess(self.text.index("cli validate"), self.text.index("night-run"))
        self.assertIn("HOLD_FORMAL_PRODUCT_INPUT_VALIDATION", self.text)

    def test_certification_and_publish_side_effects_are_prohibited(self):
        self.assertIn("PROHIBITED_CERTIFICATION_OR_PUBLISH_SIDE_EFFECT", self.text)
        self.assertIn("$result.details.submitted", self.text)
        self.assertIn("$result.details.published", self.text)

    def test_live_success_accepts_package_saved_or_complete_draft(self):
        self.assertIn('"PACKAGE_SAVED_STORE_DRAFT_REMAINING_SECTIONS_REQUIRED"', self.text)
        self.assertIn('"DRAFT_SAVED"', self.text)
        self.assertIn("GROUP_C_PACKAGE_SAVED_REMAINING_SECTIONS", self.text)
        self.assertIn("GROUP_C_LIVE_DRAFT_PASS", self.text)


if __name__ == "__main__":
    unittest.main()
