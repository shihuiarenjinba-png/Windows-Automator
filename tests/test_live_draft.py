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
    normalize_partner_center_state,
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
        self.route_ready_calls = 0

    def ensure_route_ready(self, product):
        self.route_ready_calls += 1

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
            self.assertEqual(port.route_ready_calls, 1)
            self.assertEqual(outcome.details["execution_mode"], "live")
            self.assertTrue(outcome.details["save_verified_after_reload"])
            self.assertEqual(outcome.details["package_sha256"], product.security_package_sha256)
            self.assertEqual(outcome.details["submission_route"], "msix_pwa_app")
            self.assertEqual(outcome.details["live_adapter"], "msix_app")
            self.assertEqual(outcome.details["required_sections"], list(REQUIRED_SECTIONS))
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
            with self.assertRaisesRegex(LiveGateError, "PACKAGE_VALIDATION_WARNING: manual review"):
                LiveDraftWorkflow(port)(product)
            self.assertFalse(port.saved)

    def test_exact_runfulltrust_warning_has_dedicated_hold_code(self):
        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            port = FakePort()
            warning = (
                "Package acceptance validation warning: The following restricted capabilities "
                "require approval before you can use them in your app: runFullTrust."
            )
            port.uploaded = PackageState("WARNING", "COMPLETE", warning=warning)
            with self.assertRaisesRegex(LiveGateError, "RESTRICTED_CAPABILITY_REVIEW_REQUIRED"):
                LiveDraftWorkflow(port)(product)
            self.assertFalse(port.saved)

    def test_non_msix_app_routes_cannot_enter_current_live_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            product = live_product(Path(directory))
            for route_id in ("exe_msi_app", "gdk_game", "msix_pwa_game"):
                product.submission_route = route_id
                product.product_type = "game" if "game" in route_id else "app"
                port = FakePort()
                with self.subTest(route=route_id), self.assertRaisesRegex(LiveGateError, "LIVE_ROUTE_NOT_VERIFIED"):
                    LiveDraftWorkflow(port)(product)
                self.assertEqual(port.route_ready_calls, 0)

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
            SelectorMap({"schema_version": 3, "routes": {}}).activate("msix_pwa_app")

    def test_write_enabled_map_must_be_complete_before_any_upload(self):
        with self.assertRaises(LiveGateError) as ctx:
            SelectorMap({"schema_version": 3, "routes": {"msix_pwa_app": {"live_write_supported": True, "selectors": {}}}}).activate("msix_pwa_app")
        self.assertIn("incomplete before upload", str(ctx.exception))

    def test_checked_in_route_registry_is_valid_and_all_routes_fail_closed(self):
        mapping = SelectorMap.load(Path(__file__).parents[1] / "docs" / "PARTNER_CENTER_MAP.json")
        for route_id in ("msix_pwa_app", "exe_msi_app", "gdk_game", "msix_pwa_game"):
            with self.subTest(route=route_id), self.assertRaisesRegex(LiveGateError, "LIVE_ROUTE_NOT_VERIFIED"):
                mapping.activate(route_id)

    def test_observed_msix_game_warning_fixture_is_exact_and_fail_closed(self):
        root = Path(__file__).parents[1]
        fixture = json.loads(
            (root / "tests" / "fixtures" / "partner_center_msix_pwa_game_us_warning.json").read_text(encoding="utf-8")
        )
        self.assertEqual(fixture["route_id"], "msix_pwa_game")
        self.assertEqual(
            normalize_partner_center_state(fixture["observed_messages"]["upload"], fixture["exact_states"]),
            "ANALYZING",
        )
        self.assertEqual(
            normalize_partner_center_state(fixture["observed_messages"]["validation"], fixture["exact_states"]),
            "WARNING",
        )
        self.assertEqual(fixture["outcome"]["status"], "HOLD")
        self.assertFalse(fixture["outcome"]["save_clicked"])
        self.assertFalse(fixture["outcome"]["submitted"])

        mapping = json.loads((root / "docs" / "PARTNER_CENTER_MAP.json").read_text(encoding="utf-8"))
        game = mapping["routes"]["msix_pwa_game"]
        self.assertFalse(game["live_write_supported"])
        self.assertEqual(game["hold_code"], "RESTRICTED_CAPABILITY_REVIEW_REQUIRED")
        self.assertEqual(game["section_verification"]["packages_save"], "VERIFIED_MANUAL_SAVE")
        self.assertTrue(game["selectors"]["packages_warning_alert"]["verified"])
        self.assertFalse(game["selectors"]["packages_validation_state"]["verified"])

    def test_observed_submission_options_fixture_teaches_composite_save_success(self):
        root = Path(__file__).parents[1]
        fixture = json.loads(
            (root / "tests" / "fixtures" / "partner_center_msix_pwa_game_us_submission_options.json").read_text(encoding="utf-8")
        )
        self.assertEqual(fixture["restricted_capability"]["name"], "runFullTrust")
        self.assertEqual(fixture["restricted_capability"]["textarea_count"], 1)
        self.assertTrue(fixture["save_observation"]["reload_value_exact_match"])
        self.assertFalse(fixture["save_observation"]["save_button_enabled_is_success_signal"])
        self.assertEqual(fixture["outcome"]["certification_gate"], "HOLD")
        self.assertFalse(fixture["outcome"]["submitted"])

        mapping = json.loads((root / "docs" / "PARTNER_CENTER_MAP.json").read_text(encoding="utf-8"))
        game = mapping["routes"]["msix_pwa_game"]
        for key in (
            "submission_options_restricted_capability_container",
            "submission_options_restricted_capability_textarea",
            "submission_options_save_button",
            "submission_options_save_success",
        ):
            self.assertTrue(game["selectors"][key]["verified"], key)
        self.assertFalse(game["live_write_supported"])

    def test_conflicting_observed_package_states_are_unknown(self):
        exact = {"Analyzing package": "ANALYZING", "warning": "WARNING"}
        self.assertEqual(normalize_partner_center_state(["warning", "warning"], exact), "WARNING")
        self.assertEqual(normalize_partner_center_state(["Analyzing package", "warning"], exact), "UNKNOWN")

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
