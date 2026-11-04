import tempfile
import unittest
import zipfile
from pathlib import Path

from store_manager.core import FieldValue, ProductInput, SECURITY_CONFIRM_KEYS, ValueMode, apply_fixed_rules, file_sha256, fields_for, validate_product
from store_manager.partner_center import dryrun_uploader
from store_manager.restricted_capabilities import build_package_justifications, restricted_capabilities_from_package


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
    def test_runfulltrust_is_detected_from_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            package=package_with_runfulltrust(Path(d))
            self.assertEqual(restricted_capabilities_from_package(package),("runFullTrust",))

    def test_runfulltrust_gets_evidence_based_explanation(self):
        with tempfile.TemporaryDirectory() as d:
            package=package_with_runfulltrust(Path(d))
            explanations, unresolved=build_package_justifications(package,"game")
            self.assertEqual(unresolved,())
            text=explanations["runFullTrust"]
            self.assertIn("Windows desktop game",text)
            self.assertIn("medium integrity",text)
            self.assertIn("not used to request administrator elevation",text)

    def test_fixed_rules_attach_runfulltrust_explanation(self):
        with tempfile.TemporaryDirectory() as d:
            p=ready_game(Path(d))
            apply_fixed_rules(p)
            self.assertIn("runFullTrust",p.restricted_capability_justifications)

    def test_dry_plan_includes_submission_options_explanation(self):
        with tempfile.TemporaryDirectory() as d:
            p=ready_game(Path(d))
            apply_fixed_rules(p)
            plan=dryrun_uploader(p)
            self.assertIn("submission_options:restricted_capability:runFullTrust:fill_justification",plan)

    def test_known_runfulltrust_does_not_create_unresolved_justification_hold(self):
        with tempfile.TemporaryDirectory() as d:
            p=ready_game(Path(d))
            apply_fixed_rules(p)
            findings=validate_product(p)
            self.assertFalse(any(x.code=="RESTRICTED_CAPABILITY_JUSTIFICATION_REQUIRED" for x in findings))


if __name__=="__main__":
    unittest.main()
