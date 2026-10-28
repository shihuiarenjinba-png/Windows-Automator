import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from store_manager.core import (
    AmbiguousWriteError,
    FieldValue,
    ProductInput,
    ProductHoldError,
    ValueMode,
    file_sha256,
    fields_for,
    run_queue,
    SECURITY_CONFIRM_KEYS,
)
from store_manager.live_draft import (
    DraftContext,
    LiveDraftWorkflow,
    LiveGateError,
    PackageState,
    PackageValidationError,
    REQUIRED_SECTIONS,
    SelectorMap,
)


def live_product(root: Path) -> ProductInput:
    package = root / "Example.msix"
    manifest = b'''<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10">
  <Identity Name="Example.Identity" Publisher="CN=EXAMPLE" Version="1.2.3.4" ProcessorArchitecture="x64" />
</Package>'''
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("AppxManifest.xml", manifest)
    images = root / "images"
    images.mkdir()
    (images / "01-main.png").write_bytes(b"PNG")
    product = ProductInput(
        "app",
        "Example",
        "Offline utility",
        package_path=str(package),
        images_dir=str(images),
        store_product_id="9EXAMPLE",
        price_mode="free",
        source_sha="a" * 40,
        source_branch="codex/example",
        identity_name="Example.Identity",
        identity_publisher="CN=EXAMPLE",
        package_version="1.2.3.4",
        checker_status="READY_CANDIDATE_NOT_CERTIFIED",
        human_local_qa_pass=True,
        draft_id="12345",
    )
    for definition in fields_for("app"):
        values = {
            "product_type": "app",
            "submission_kind": "update",
            "pricing_model": "free",
            "visibility": "discoverable",
            "free_trial": "none",
            "publish_hold": "manual_publish",
            "primary_category": "Productivity",
        }
        value = values.get(definition.key, "no")
        product.fields[definition.key] = FieldValue(
            definition.key,
            ValueMode.MANUAL,
            value,
            "test",
            1.0,
            "test",
            definition.key in SECURITY_CONFIRM_KEYS,
        )
    product.fields["description"] = FieldValue("description", ValueMode.MANUAL, "Description", "test")
    product.security_package_sha256 = file_sha256(package)
    return product


class FakePort:
    def __init__(self):
        self.uploaded = PackageState("VALID", "COMPLETE")
        self.reloaded = PackageState("VALID", "COMPLETE")
        self.sections = {name: "SAVED" for name in REQUIRED_SECTIONS}
        self.evidence = [{"kind": "screenshot", "path": "C:/evidence/proof.png"}]
        self.saved = False

    def verify_product_and_draft(self, product):
        return DraftContext(product.store_product_id, "12345", "https://partner.microsoft.com/draft/12345")

    def upload_package(self, product, context):
        return self.uploaded

    def save_packages(self, product, context):
        self.saved = True

    def reload_and_verify_package(self, product, context):
        return self.reloaded

    def verify_required_sections(self, product, context):
        return self.sections

    def capture_evidence(self, product, context):
        return self.evidence


class LiveDraftTests(unittest.TestCase):
    def test_success_requires_reload_and_emits_explicit_live_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            port = FakePort()
            outcome = LiveDraftWorkflow(port)(product)
            self.assertEqual(outcome.status, "DRAFT_SAVED")
            self.assertTrue(port.saved)
            self.assertEqual(outcome.details["execution_mode"], "live")
            self.assertTrue(outcome.details["save_verified_after_reload"])
            self.assertEqual(outcome.details["package_sha256"], product.security_package_sha256)
            self.assertFalse(outcome.details["submitted"])
            self.assertFalse(outcome.details["certified"])
            self.assertFalse(outcome.details["published"])

    def test_live_gate_rejects_missing_source_sha_before_browser_port(self):
        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            product.source_sha = ""
            with self.assertRaises(LiveGateError):
                LiveDraftWorkflow(FakePort())(product)

    def test_live_gate_rejects_checker_or_human_qa_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            product.checker_status = "NEEDS_REVIEW"
            with self.assertRaises(LiveGateError):
                LiveDraftWorkflow(FakePort())(product)
            product.checker_status = "READY_CANDIDATE_NOT_CERTIFIED"
            product.human_local_qa_pass = False
            with self.assertRaises(LiveGateError):
                LiveDraftWorkflow(FakePort())(product)

    def test_live_gate_reads_identity_from_the_actual_package(self):
        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            product.identity_name = "Other.Identity"
            with self.assertRaises(LiveGateError):
                LiveDraftWorkflow(FakePort())(product)

    def test_warning_validation_is_hold_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            port = FakePort()
            port.uploaded = PackageState("WARNING", "COMPLETE", warning="manual review")
            with self.assertRaises(LiveGateError):
                LiveDraftWorkflow(port)(product)
            self.assertFalse(port.saved)

    def test_non_msix_app_routes_cannot_enter_current_live_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            for route_id in ("exe_msi_app", "gdk_game", "msix_pwa_game"):
                product.submission_route = route_id
                product.product_type = "game" if "game" in route_id else "app"
                with self.subTest(route=route_id), self.assertRaises(LiveGateError):
                    LiveDraftWorkflow(FakePort())(product)

    def test_validation_error_is_hold_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            port = FakePort()
            port.uploaded = PackageState("ERROR", "INCOMPLETE", error="bad package")
            with self.assertRaises(PackageValidationError):
                LiveDraftWorkflow(port)(product)
            self.assertFalse(port.saved)

    def test_unknown_upload_or_reload_is_never_retried_or_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            port = FakePort()
            port.uploaded = PackageState("UNKNOWN", "UNKNOWN")
            with self.assertRaises(AmbiguousWriteError):
                LiveDraftWorkflow(port)(product)
            self.assertFalse(port.saved)

            port = FakePort()
            port.reloaded = PackageState("UNKNOWN", "UNKNOWN")
            with self.assertRaises(AmbiguousWriteError):
                LiveDraftWorkflow(port)(product)

    def test_incomplete_required_section_cannot_claim_draft_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            port = FakePort()
            port.sections["store_listings"] = "INCOMPLETE"
            with self.assertRaises(LiveGateError):
                LiveDraftWorkflow(port)(product)

    def test_queue_maps_live_gate_to_hold_and_ambiguous_to_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            product.source_sha = ""
            report = run_queue([product], LiveDraftWorkflow(FakePort()))
            self.assertEqual(report.results[0].status, "HOLD")

        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            port = FakePort()
            port.uploaded = PackageState("UNKNOWN", "UNKNOWN")
            report = run_queue([product], LiveDraftWorkflow(port))
            self.assertEqual(report.results[0].status, "UNKNOWN")

    def test_unverified_selector_map_fails_closed(self):
        with self.assertRaises(LiveGateError):
            SelectorMap({"schema_version": 2, "write_enabled": False})

    def test_write_enabled_map_must_be_complete_before_any_upload(self):
        with self.assertRaises(LiveGateError) as ctx:
            SelectorMap({"schema_version": 2, "write_enabled": True, "selectors": {}})
        self.assertIn("incomplete before upload", str(ctx.exception))

    def test_report_contains_live_fields_at_top_level(self):
        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            report = run_queue([product], LiveDraftWorkflow(FakePort())).to_dict()
            self.assertEqual(report["schema_version"], 2)
            item = report["results"][0]
            self.assertEqual(item["status"], "DRAFT_SAVED")
            self.assertTrue(item["draft_saved"])
            self.assertEqual(item["product_id"], "9EXAMPLE")


if __name__ == "__main__":
    unittest.main()
