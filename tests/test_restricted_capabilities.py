import tempfile
import unittest
import zipfile
from pathlib import Path

from store_manager.core import FieldValue, ProductInput, SECURITY_CONFIRM_KEYS, ValueMode, apply_fixed_rules, file_sha256, fields_for, run_queue, validate_product
from store_manager.partner_center import dryrun_uploader
from store_manager.restricted_capabilities import (
    RUNFULLTRUST_PACKAGE_WARNING,
    RestrictedCapabilityJustification,
    build_package_justifications,
    build_restricted_capability_justification,
    classify_package_warning,
    exact_capability_match,
    restricted_capabilities_from_package,
)


def package_with_runfulltrust(root: Path) -> Path:
    package = root / "FullTrust.msix"
    manifest = b'''<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities">
  <Identity Name="Example.FullTrust" Publisher="CN=EXAMPLE" Version="1.0.0.0" ProcessorArchitecture="x64" />
  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
</Package>'''
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("AppxManifest.xml", manifest)
    return package


def ready_game(root: Path) -> ProductInput:
    package = package_with_runfulltrust(root)
    images = root / "images"; images.mkdir(); (images / "01.png").write_bytes(b"x")
    p = ProductInput(
        "game","Example Game","Desktop strategy game",
        package_path=str(package),images_dir=str(images),price_mode="free",
        submission_route="msix_pwa_game",
    )
    for definition in fields_for("game"):
        values={
            "product_type":"game","submission_kind":"update","pricing_model":"free",
            "visibility":"discoverable","free_trial":"none","publish_hold":"manual_publish",
            "game_genres":["Strategy"],"violence":"no","gambling":"no","sexual_content":"no",
            "drugs_alcohol_tobacco":"no","strong_language":"no",
            "security_restricted_capabilities":"yes",
        }
        value=values.get(definition.key,"no")
        p.fields[definition.key]=FieldValue(
            definition.key,ValueMode.MANUAL,value,"test",1.0,"test",
            definition.key in SECURITY_CONFIRM_KEYS,
        )
    p.fields["description"]=FieldValue("description",ValueMode.MANUAL,"Description","test")
    p.security_package_sha256=file_sha256(package)
    return p


class RestrictedCapabilityTests(unittest.TestCase):
    def test_exact_partner_center_warning_routes_only_runfulltrust(self):
        code, capabilities = classify_package_warning(RUNFULLTRUST_PACKAGE_WARNING)
        self.assertEqual(code, "RESTRICTED_CAPABILITY_REVIEW_REQUIRED")
        self.assertEqual(capabilities, ("runFullTrust",))
        duplicate = f"{RUNFULLTRUST_PACKAGE_WARNING} | {RUNFULLTRUST_PACKAGE_WARNING}"
        self.assertEqual(classify_package_warning(duplicate), (code, capabilities))

    def test_unknown_warning_remains_generic_hold(self):
        code, capabilities = classify_package_warning("Some other warning")
        self.assertEqual(code, "PACKAGE_VALIDATION_WARNING")
        self.assertEqual(capabilities, ())

    def test_runfulltrust_is_detected_from_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            package=package_with_runfulltrust(Path(d))
            self.assertEqual(restricted_capabilities_from_package(package),("runFullTrust",))

    def test_runfulltrust_gets_evidence_based_explanation(self):
        with tempfile.TemporaryDirectory() as d:
            package=package_with_runfulltrust(Path(d))
            explanations, unresolved=build_package_justifications(package,"game")
            self.assertEqual(unresolved,())
            text=explanations["runFullTrust"].text
            self.assertIn("Windows desktop game",text)
            self.assertIn("medium integrity",text)
            self.assertIn("not used to request administrator elevation",text)

    def test_template_uses_product_name_and_switches_app_game_wording(self):
        game=build_restricted_capability_justification("runFullTrust","game","Chess Lab")
        app=build_restricted_capability_justification("runFullTrust","app","Notes Lab")
        self.assertTrue(game.startswith("Chess Lab is a packaged Windows desktop game"))
        self.assertTrue(app.startswith("Notes Lab is a packaged Windows desktop application"))
        self.assertIsNone(build_restricted_capability_justification("unknownCapability","app","Notes Lab"))

    def test_jp_observed_text_is_exact_fixed_template_output(self):
        root=Path(__file__).parents[1]
        import json
        fixture=json.loads((root/"tests"/"fixtures"/"partner_center_msix_pwa_game_jp_submission_options.json").read_text(encoding="utf-8"))
        generated=build_restricted_capability_justification("runFullTrust","game",fixture["product"]["name"])
        self.assertEqual(generated,fixture["restricted_capability"]["explanation"])

    def test_fixed_rules_attach_runfulltrust_explanation(self):
        with tempfile.TemporaryDirectory() as d:
            p=ready_game(Path(d))
            apply_fixed_rules(p)
            self.assertIn("runFullTrust",p.restricted_capability_justifications)
            explanation=p.restricted_capability_justifications["runFullTrust"]
            self.assertEqual(explanation.source,"fixed_template")
            self.assertFalse(explanation.confirmed)
            self.assertEqual(explanation.package_sha256,file_sha256(p.package_path))

    def test_package_sha_change_resets_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            p=ready_game(root)
            apply_fixed_rules(p)
            explanation=p.restricted_capability_justifications["runFullTrust"]
            explanation.confirmed=True
            p.restricted_capability_explanation_saved["runFullTrust"]=True
            with zipfile.ZipFile(p.package_path,"a") as archive:
                archive.writestr("changed.txt",b"changed")
            apply_fixed_rules(p)
            changed=p.restricted_capability_justifications["runFullTrust"]
            self.assertFalse(changed.confirmed)
            self.assertEqual(changed.package_sha256,file_sha256(p.package_path))
            self.assertFalse(p.restricted_capability_explanation_saved["runFullTrust"])

    def test_dry_plan_includes_submission_options_explanation(self):
        with tempfile.TemporaryDirectory() as d:
            p=ready_game(Path(d))
            apply_fixed_rules(p)
            p.restricted_capability_justifications["runFullTrust"].confirmed=True
            plan=dryrun_uploader(p)
            self.assertIn("submission_options:restricted_capability:runFullTrust:fill_confirmed_justification_exact_match",plan)
            self.assertIn("submission_options:save",plan)
            self.assertIn("submission_options:reload_and_verify_exact_text",plan)

    def test_known_runfulltrust_requires_confirmation_before_live_write(self):
        with tempfile.TemporaryDirectory() as d:
            p=ready_game(Path(d))
            apply_fixed_rules(p)
            findings=validate_product(p)
            self.assertFalse(any(x.code=="RESTRICTED_CAPABILITY_JUSTIFICATION_REQUIRED" for x in findings))
            self.assertTrue(any(x.code=="RESTRICTED_CAPABILITY_CONFIRMATION_REQUIRED" for x in findings))
            p.restricted_capability_justifications["runFullTrust"].confirmed=True
            findings=validate_product(p)
            self.assertFalse(any(x.code=="RESTRICTED_CAPABILITY_CONFIRMATION_REQUIRED" for x in findings))

    def test_unknown_capability_is_owner_input_hold(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            package=root/"Unknown.msix"
            manifest=b'''<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
 xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities">
 <Identity Name="Unknown" Publisher="CN=EXAMPLE" Version="1.0.0.0" ProcessorArchitecture="x64" />
 <Capabilities><rescap:Capability Name="unknownRestrictedCapability" /></Capabilities>
</Package>'''
            with zipfile.ZipFile(package,"w") as archive:
                archive.writestr("AppxManifest.xml",manifest)
            images=root/"images"; images.mkdir(); (images/"01.png").write_bytes(b"x")
            p=ProductInput("app","Unknown App","x",package_path=str(package),images_dir=str(images),price_mode="free")
            apply_fixed_rules(p)
            record=p.restricted_capability_justifications["unknownRestrictedCapability"]
            self.assertEqual(record.source,"owner_required")
            self.assertFalse(record.confirmed)
            self.assertTrue(any(x.code=="RESTRICTED_CAPABILITY_NEEDS_OWNER_INPUT" for x in validate_product(p)))

    def test_partner_center_capability_match_is_exact_and_unique(self):
        self.assertTrue(exact_capability_match(("runFullTrust",),("runFullTrust",)))
        self.assertFalse(exact_capability_match(("runFullTrust",),("runFullTrust","runFullTrust")))
        self.assertFalse(exact_capability_match(("runFullTrust",),("other",)))

    def test_structured_justification_round_trip_and_legacy_text_is_unconfirmed(self):
        p=ProductInput("app","A","x",restricted_capability_justifications={
            "runFullTrust": RestrictedCapabilityJustification("text","owner_input",True,"a"*64)
        })
        restored=ProductInput.from_dict(p.to_dict())
        self.assertTrue(restored.restricted_capability_justifications["runFullTrust"].confirmed)
        legacy=ProductInput.from_dict({"product_type":"app","product_name":"A","app_summary":"x","restricted_capability_justifications":{"runFullTrust":"legacy"}})
        self.assertFalse(legacy.restricted_capability_justifications["runFullTrust"].confirmed)

    def test_queue_result_exposes_central_dashboard_capability_fields(self):
        with tempfile.TemporaryDirectory() as d:
            p=ready_game(Path(d))
            apply_fixed_rules(p)
            p.restricted_capability_justifications["runFullTrust"].confirmed=True
            p.restricted_capability_explanation_saved["runFullTrust"]=False
            p.certification_gate="HOLD_JP_START_FLOW_UNRESOLVED"
            item=run_queue([p],dryrun_uploader).to_dict()["results"][0]
            self.assertEqual(item["restricted_capability"],["runFullTrust"])
            self.assertTrue(item["restricted_capability_explanation_confirmed"])
            self.assertFalse(item["restricted_capability_explanation_saved"])
            self.assertEqual(item["certification_gate"],"HOLD_JP_START_FLOW_UNRESOLVED")


if __name__=="__main__":
    unittest.main()
