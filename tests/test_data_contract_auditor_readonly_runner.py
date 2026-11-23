from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "scripts" / "run_data_contract_auditor_readonly.ps1").read_text(encoding="utf-8")
TEACHER = (ROOT / "scripts" / "run_group_c_store_teacher.ps1").read_text(encoding="utf-8")


class DataContractAuditorReadOnlyRunnerTests(unittest.TestCase):
    def test_exact_formal_candidate_is_pinned(self):
        for value in (
            "9PDL4ZWSB45P",
            "1152921505702212222",
            "5a09d81955e25664761ea25ecfb4ebf8d24cea6d",
            "4b373d2bc54ecbd3efa0a77a94005007777e66d641fa3908f523ac69fcd46984",
            "OkinawaDesktopTools.DataContractAuditor",
            "CN=46263F21-A700-41DB-8C9B-114C22FB82FC",
        ):
            self.assertIn(value, SCRIPT)

    def test_probe_is_read_only_only(self):
        self.assertIn('Mode = "ReadOnly"', SCRIPT)
        self.assertIn("upload_package = $false", SCRIPT)
        self.assertIn("submit_certification = $false", SCRIPT)
        self.assertIn("publish = $false", SCRIPT)
        self.assertNotIn("ConfirmLiveDraft", SCRIPT)

    def test_package_hash_is_rechecked_before_browser_probe(self):
        self.assertLess(SCRIPT.index("Get-FileHash"), SCRIPT.index("Invoke-RestMethod"))
        self.assertIn("HOLD_PACKAGE_SHA_MISMATCH", SCRIPT)

    def test_json_outputs_are_bom_free_and_python_accepts_utf8_sig(self):
        self.assertIn("System.Text.UTF8Encoding($false)", SCRIPT)
        core = (ROOT / "store_manager" / "core.py").read_text(encoding="utf-8")
        cli = (ROOT / "store_manager" / "cli.py").read_text(encoding="utf-8")
        self.assertIn('encoding="utf-8-sig"', core)
        self.assertIn('encoding="utf-8-sig"', cli)

    def test_identity_verifier_waits_for_exact_async_partner_values(self):
        live = (ROOT / "store_manager" / "live_draft.py").read_text(encoding="utf-8")
        self.assertIn('for selector in ("input", "textarea")', live)
        self.assertIn("node.input_value()", live)
        self.assertIn('self.page.locator("body").inner_text()', live)
        self.assertIn("wait_for_load_state", live)
        self.assertIn('getattr(self.page, "wait_for_timeout", None)', live)
        self.assertIn("timeout_ms: int = 15_000", live)

    def test_identity_verifier_uses_title_url_and_exact_visible_fields(self):
        live = (ROOT / "store_manager" / "live_draft.py").read_text(encoding="utf-8")
        self.assertIn("_verify_identity_page_context", live)
        self.assertNotIn("HOLD_PRODUCT_TITLE_MISMATCH", live)
        self.assertIn('expected_path = f"/products/{store_product_id}/identity"', live)
        self.assertIn("visible >= 1", live)
        self.assertIn("volatile document.title", live)

    def test_cli_reports_expired_partner_center_auth_cleanly(self):
        cli = (ROOT / "store_manager" / "cli.py").read_text(encoding="utf-8")
        self.assertIn("OWNER_SIGN_IN_REQUIRED_PARTNER_CENTER", cli)
        self.assertIn("except GlobalAuthError", cli)
        self.assertIn("HOLD_PARTNER_CENTER_IDENTITY_REVERIFY", cli)

    def test_teacher_supports_windows_powershell_51_and_explicit_python(self):
        self.assertIn('$env:OS -eq "Windows_NT"', TEACHER)
        self.assertIn('[string]$PythonExe = "python"', TEACHER)
        self.assertIn("& $PythonExe -m store_manager.cli", TEACHER)
        self.assertIn('[Alias("Input")][string]$ProductInput', TEACHER)
        self.assertIn("ProductInput = $ProductPath", SCRIPT)


if __name__ == "__main__":
    unittest.main()
