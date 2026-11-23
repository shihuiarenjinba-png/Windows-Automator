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

    def test_teacher_supports_windows_powershell_51_and_explicit_python(self):
        self.assertIn('$env:OS -eq "Windows_NT"', TEACHER)
        self.assertIn('[string]$PythonExe = "python"', TEACHER)
        self.assertIn("& $PythonExe -m store_manager.cli", TEACHER)


if __name__ == "__main__":
    unittest.main()
