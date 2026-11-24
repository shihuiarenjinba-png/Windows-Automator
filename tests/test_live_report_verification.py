from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from store_manager.cli import verify_live_report_payload
from store_manager.core import ProductInput


class VerifyLiveReportPayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.package = Path(self.temp_dir.name) / "sample.msix"
        self.package.write_bytes(b"immutable-test-package")
        self.package_sha = hashlib.sha256(self.package.read_bytes()).hexdigest()
        self.product = ProductInput(
            product_type="app",
            product_name="Sample App",
            app_summary="Sample app for receipt verification",
            package_path=str(self.package),
            store_product_id="9P1234567890",
            draft_id="1152921505700000000",
            package_sha256=self.package_sha,
            security_package_sha256=self.package_sha,
            source_sha="a" * 40,
            source_branch="release/sample",
            submission_route="msix_pwa_app",
            identity_name="Example.Sample",
            identity_publisher="CN=EXAMPLE",
            package_version="1.2.3.0",
        )
        self.report = self.valid_report()

    def valid_report(self):
        return {
            "schema_version": 2,
            "stopped_early": False,
            "summary": {"mode": "single", "total": 1},
            "results": [
                {
                    "product_name": self.product.product_name,
                    "status": "DRAFT_SAVED",
                    "product_id": self.product.store_product_id,
                    "draft_id": self.product.draft_id,
                    "package_filename": self.package.name,
                    "package_sha256": self.package_sha,
                    "immutable_package_sha256": self.package_sha,
                    "source_sha": self.product.source_sha,
                    "source_branch": self.product.source_branch,
                    "submission_route": self.product.submission_route,
                    "identity": {
                        "name": self.product.identity_name,
                        "publisher": self.product.identity_publisher,
                        "version": self.product.package_version,
                    },
                    "package_uploaded": True,
                    "package_saved": True,
                    "save_verified_after_reload": True,
                    "created_or_reserved_product": False,
                    "submission_started": False,
                    "start_submission_clicked": False,
                    "start_update_clicked": False,
                    "pricing_changed": False,
                    "submitted": False,
                    "certified": False,
                    "published": False,
                }
            ],
        }

    def test_accepts_only_exact_single_product_draft_save_receipt(self):
        receipt = verify_live_report_payload(self.report, self.product)
        self.assertEqual(receipt["status"], "LIVE_DRAFT_RECEIPT_VERIFIED")
        self.assertEqual(receipt["result_status"], "DRAFT_SAVED")
        self.assertFalse(receipt["microsoft_independent_sha256_observed"])

    def test_rejects_nested_details_shape_instead_of_flattened_queue_report(self):
        result = self.report["results"][0]
        flags = (
            "package_uploaded",
            "package_saved",
            "save_verified_after_reload",
            "created_or_reserved_product",
            "submission_started",
            "start_submission_clicked",
            "start_update_clicked",
            "pricing_changed",
            "submitted",
            "certified",
            "published",
        )
        result["details"] = {key: result.pop(key) for key in flags}
        with self.assertRaisesRegex(ValueError, "package_uploaded=true"):
            verify_live_report_payload(self.report, self.product)

    def test_rejects_missing_or_true_prohibited_side_effect_flags(self):
        result = self.report["results"][0]
        del result["certified"]
        with self.assertRaisesRegex(ValueError, "certified=false"):
            verify_live_report_payload(self.report, self.product)
        result["certified"] = True
        with self.assertRaisesRegex(ValueError, "certified=false"):
            verify_live_report_payload(self.report, self.product)

    def test_rejects_product_draft_package_and_identity_mismatches(self):
        for field, value in (
            ("product_id", "9P0000000000"),
            ("draft_id", "1152921505700000001"),
            ("package_filename", "different.msix"),
            ("package_sha256", "0" * 64),
            ("immutable_package_sha256", "0" * 64),
            ("identity", {"name": "Other", "publisher": "CN=OTHER", "version": "1.0.0.0"}),
        ):
            with self.subTest(field=field):
                original = self.report["results"][0][field]
                self.report["results"][0][field] = value
                with self.assertRaises(ValueError):
                    verify_live_report_payload(self.report, self.product)
                self.report["results"][0][field] = original

    def test_rejects_local_package_changed_after_attempt(self):
        self.package.write_bytes(b"changed-package")
        with self.assertRaisesRegex(ValueError, "bytes changed"):
            verify_live_report_payload(self.report, self.product)

    def test_rejects_unknown_status_and_multi_item_report(self):
        self.report["results"][0]["status"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "not a verified Draft-save status"):
            verify_live_report_payload(self.report, self.product)
        self.report = self.valid_report()
        self.report["results"].append(dict(self.report["results"][0]))
        with self.assertRaisesRegex(ValueError, "exactly one result"):
            verify_live_report_payload(self.report, self.product)

    def test_rejects_missing_or_inconsistent_security_hash(self):
        self.product.security_package_sha256 = "0" * 64
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            verify_live_report_payload(self.report, self.product)


if __name__ == "__main__":
    unittest.main()
