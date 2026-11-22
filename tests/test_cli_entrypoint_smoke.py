from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CliEntrypointSmokeTests(unittest.TestCase):
    def test_cli_help_executes_as_module(self):
        result = subprocess.run(
            [sys.executable, "-m", "store_manager.cli", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("verify-existing-identity", result.stdout)
        self.assertIn("inspect-existing-submission-state", result.stdout)
        self.assertIn("night-run", result.stdout)

    def test_validate_command_fails_closed_for_unfrozen_product(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "product.json"
            payload = {
                "product_type": "app",
                "product_name": "CLI Smoke",
                "app_summary": "Offline utility",
                "submission_route": "msix_pwa_app",
                "submission_route_source": "manual",
                "store_product_id": "9P1234567890",
                "source_sha": "a" * 40,
                "source_branch": "codex/example",
                "identity_name": "Example.Identity",
                "identity_publisher": "CN=EXAMPLE",
                "package_version": "1.0.0.0",
                "checker_status": "READY_CANDIDATE_NOT_CERTIFIED",
                "human_local_qa_pass": True
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "store_manager.cli",
                    "validate",
                    "--input",
                    str(path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("PACKAGE_MISSING", result.stdout)


if __name__ == "__main__":
    unittest.main()
