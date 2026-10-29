import tempfile
import unittest
from pathlib import Path

from store_manager.core import FieldValue, ProductInput, SECURITY_CONFIRM_KEYS, ValueMode, apply_fixed_rules, file_sha256, fields_for, run_queue, validate_product
from store_manager.ollama import apply_answer, prepare_prompt
from store_manager.partner_center import build_dry_plan, simulate_overview_start
from store_manager.submission_routes import ROUTE_LABELS, ROUTE_TEMPLATES, default_route_for_product_type, route_display, route_id_from_label, route_template


def ready_fields(product):
    for definition in fields_for(product.product_type):
        values={
            "product_type": product.product_type,
            "submission_kind": "update",
            "pricing_model": "free",
            "visibility": "discoverable",
            "free_trial": "none",
            "publish_hold": "manual_publish",
            "primary_category": "Productivity",
            "game_genres": ["Strategy"],
            "violence": "no",
            "gambling": "no",
            "sexual_content": "no",
            "drugs_alcohol_tobacco": "no",
            "strong_language": "no",
        }
        value=values.get(definition.key, "no")
        product.fields[definition.key]=FieldValue(
            definition.key, ValueMode.MANUAL, value, "test", 1.0, "test",
            definition.key in SECURITY_CONFIRM_KEYS,
        )
    product.fields["description"]=FieldValue("description",ValueMode.MANUAL,"Description","test")


class SubmissionRouteTests(unittest.TestCase):
    def test_partner_center_labels_match_four_visible_product_types(self):
        self.assertEqual(
            ROUTE_LABELS,
            ("MSIX or PWA app","EXE or MSI app","GDK game","MSIX or PWA game"),
        )

    def test_route_label_round_trip(self):
        for route_id, template in ROUTE_TEMPLATES.items():
            self.assertEqual(route_id_from_label(template.partner_center_label),route_id)
            self.assertEqual(route_template(route_id).partner_center_label,template.partner_center_label)

    def test_defaults_preserve_existing_app_game_behavior(self):
        self.assertEqual(default_route_for_product_type("app"),"msix_pwa_app")
        self.assertEqual(default_route_for_product_type("game"),"msix_pwa_game")

    def test_new_product_simulation_chooses_exact_partner_center_type(self):
        for route_id, template in ROUTE_TEMPLATES.items():
            sim=simulate_overview_start(
                "Example",
                "new",
                submission_route=route_id,
                product_type=template.product_type,
            )
            self.assertIn(f"choose_product_type_exact:{template.partner_center_label}",sim.actions)

    def test_route_product_type_mismatch_fails_closed(self):
        p=ProductInput("game","Bad","x",submission_route="msix_pwa_app")
        findings=validate_product(p)
        self.assertTrue(any(x.code=="SUBMISSION_ROUTE" for x in findings))

    def test_exe_msi_template_requires_url_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            exe=root/"setup.exe"; exe.write_bytes(b"exe")
            images=root/"images"; images.mkdir(); (images/"01.png").write_bytes(b"x")
            p=ProductInput("app","EXE App","x",package_path=str(exe),images_dir=str(images),submission_route="exe_msi_app",price_mode="free")
            ready_fields(p)
            p.security_package_sha256=file_sha256(exe)
            findings=validate_product(p)
            codes={x.code for x in findings}
            self.assertIn("INSTALLER_URL",codes)
            self.assertIn("INSTALLER_ARCH",codes)
            self.assertIn("INSTALLER_SILENT_ARGS",codes)
            self.assertIn("INSTALLER_LANGUAGE",codes)

    def test_gdk_template_requires_companion_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            pkg=root/"game.msixvc"; pkg.write_bytes(b"game")
            images=root/"images"; images.mkdir(); (images/"01.png").write_bytes(b"x")
            p=ProductInput("game","GDK","x",package_path=str(pkg),images_dir=str(images),submission_route="gdk_game",price_mode="free")
            ready_fields(p)
            p.security_package_sha256=file_sha256(pkg)
            findings=validate_product(p)
            self.assertGreaterEqual(sum(x.code=="GDK_EVIDENCE_MISSING" for x in findings),3)

    def test_msix_game_accepts_msix_not_exe(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            exe=root/"game.exe"; exe.write_bytes(b"x")
            images=root/"images"; images.mkdir(); (images/"01.png").write_bytes(b"x")
            p=ProductInput("game","Game","x",package_path=str(exe),images_dir=str(images),submission_route="msix_pwa_game",price_mode="free")
            ready_fields(p)
            p.security_package_sha256=file_sha256(exe)
            self.assertTrue(any(x.code=="SUBMISSION_ROUTE_PACKAGE_MISMATCH" for x in validate_product(p)))

    def test_all_route_package_mismatches_use_one_hold_code_and_never_rewrite_route(self):
        cases=(
            ("gdk_game","game","setup.exe","exe"),
            ("msix_pwa_app","app","game.msixvc","msixvc"),
            ("exe_msi_app","app","app.msix","msix"),
            ("msix_pwa_game","game","setup.exe","exe"),
        )
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); images=root/"images"; images.mkdir(); (images/"01.png").write_bytes(b"x")
            for route_id,product_type,filename,package_type in cases:
                package=root/filename; package.write_bytes(route_id.encode())
                p=ProductInput(product_type,"Mismatch","x",package_path=str(package),images_dir=str(images),submission_route=route_id,package_type=package_type)
                ready_fields(p); p.security_package_sha256=file_sha256(package)
                findings=validate_product(p)
                self.assertTrue(any(x.code=="SUBMISSION_ROUTE_PACKAGE_MISMATCH" for x in findings),route_id)
                self.assertEqual(p.submission_route,route_id)

    def test_handoff_route_source_and_legacy_default_are_explicit(self):
        upstream=ProductInput.from_dict({"product_type":"app","product_name":"A","app_summary":"x","submission_route":"exe_msi_app"})
        self.assertEqual(upstream.submission_route_source,"upstream")
        self.assertEqual(route_display(upstream.submission_route,upstream.product_type,upstream.submission_route_source),"EXE or MSI app [上流工程で確定済み]")
        legacy=ProductInput.from_dict({"product_type":"game","product_name":"G","app_summary":"x"})
        self.assertEqual((legacy.submission_route,legacy.submission_route_source),("msix_pwa_game","legacy_default"))

    def test_fixed_rules_ollama_and_dry_plan_preserve_upstream_route(self):
        p=ProductInput("app","Installer","x",submission_route="exe_msi_app",submission_route_source="upstream")
        apply_fixed_rules(p)
        apply_answer(p,{"text":{"description":{"value":"Example","confidence":.9}},"submission_route":"msix_pwa_app"})
        self.assertEqual(p.submission_route,"exe_msi_app")
        self.assertIn("Submission route (read-only): exe_msi_app",prepare_prompt(p,""))
        plan=build_dry_plan(p)
        self.assertIn("submission_route:exe_msi_app",plan)
        self.assertFalse(any(x.startswith("packages:upload") for x in plan))

    def test_mixed_route_queue_keeps_processing_and_reports_each_route(self):
        products=[
            ProductInput(ROUTE_TEMPLATES[route_id].product_type,route_id,"x",submission_route=route_id)
            for route_id in ROUTE_TEMPLATES
        ]
        report=run_queue(products,lambda product: build_dry_plan(product))
        self.assertEqual(len(report.results),4)
        self.assertFalse(report.stopped_early)
        self.assertEqual([item.details["submission_route"] for item in report.results],list(ROUTE_TEMPLATES))


if __name__=="__main__":
    unittest.main()
