import tempfile,unittest
from pathlib import Path
from store_manager.core import *
from store_manager.partner_center import choose_exact_option,OptionMismatch,dryrun_uploader,simulate_overview_start,PARTNER_CENTER_APPS_GAMES_URL
from store_manager.ollama import apply_answer

def product(tmp,kind="app"):
    pkg=tmp/"x.msix"; pkg.write_bytes(b"PK"); d=tmp/"imgs"; d.mkdir(exist_ok=True); (d/"a.png").write_bytes(b"x")
    p=ProductInput(kind,"Sample","Offline utility",package_path=str(pkg),images_dir=str(d),price_mode="free")
    for f in fields_for(kind):
        if f.key=="product_type": val=kind
        elif f.key=="submission_kind": val="update"
        elif f.key=="pricing_model": val="free"
        elif f.key=="visibility": val="discoverable"
        elif f.key=="free_trial": val="none"
        elif f.key=="publish_hold": val="manual_publish"
        elif f.key=="primary_category": val="Productivity"
        elif f.key=="game_genres": val=["Strategy"]
        else: val="no"
        p.fields[f.key]=FieldValue(f.key,ValueMode.MANUAL,val,"test",1.0,"test",f.key in SECURITY_CONFIRM_KEYS)
    p.fields["description"]=FieldValue("description",ValueMode.MANUAL,"Description","test")
    p.security_package_sha256=file_sha256(str(pkg))
    return p
class T(unittest.TestCase):
    def test_catalogs(self): self.assertIn("Productivity",APP_CATEGORIES); self.assertIn("Strategy",GAME_GENRES)
    def test_options_are_tuples(self):
        for f in fields_for("game"): self.assertIsInstance(f.choices,tuple)
    def test_fixed_offline(self):
        p=ProductInput("app","A","Offline",price_mode="free"); apply_fixed_rules(p); self.assertEqual(p.fields["requires_internet"].value,"no")

    def test_app_type_selects_fixed_preset(self):
        p=ProductInput("app","A","x",price_mode="paid",submission_kind="update")
        apply_fixed_rules(p)
        self.assertEqual(p.fields["product_type"].value,"app")
        self.assertEqual(p.fields["visibility"].value,"discoverable")
        self.assertEqual(p.fields["free_trial"].value,"none")
        self.assertEqual(p.fields["publish_hold"].value,"manual_publish")
        self.assertEqual(p.fields["submission_kind"].value,"update")
        self.assertTrue(all(p.fields[k].mode==ValueMode.FIXED for k in ("product_type","visibility","free_trial","publish_hold","submission_kind")))

    def test_game_type_selects_game_fixed_preset(self):
        p=ProductInput("game","G","x",price_mode="paid",submission_kind="new")
        apply_fixed_rules(p)
        self.assertEqual(p.fields["product_type"].value,"game")
        self.assertEqual(p.fields["submission_kind"].value,"new")
        self.assertEqual(p.fields["visibility"].value,"discoverable")

    def test_security_fields_are_never_fixed_by_type_preset(self):
        p=ProductInput("app","A","x")
        apply_fixed_rules(p)
        self.assertTrue(all(k not in p.fields for k in SECURITY_CONFIRM_KEYS))
    def test_invalid_choice_from_ollama(self):
        p=ProductInput("app","A","x"); apply_answer(p,{"choices":{"contains_ads":{"value":"maybe","confidence":.99}}}); self.assertEqual(p.fields["contains_ads"].mode,ValueMode.REVIEW)
    def test_sensitive_confidence(self):
        p=ProductInput("game","G","x"); apply_answer(p,{"choices":{"violence":{"value":"no","confidence":.8}}}); self.assertEqual(p.fields["violence"].mode,ValueMode.REVIEW)

    def test_ai_security_answer_is_not_confirmed(self):
        p=ProductInput("app","A","x")
        for f in fields_for("app"):
            p.fields[f.key]=FieldValue(f.key,ValueMode.OLLAMA,"no","ollama",.99,"candidate")
        self.assertTrue(any(f.code=="SECURITY_CONFIRM_REQUIRED" for f in validate_product(p)))

    def test_package_change_invalidates_security_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); p=product(root)
            changed=root/"changed.msix"; changed.write_bytes(b"DIFFERENT")
            p.package_path=str(changed)
            self.assertTrue(any(f.code=="SECURITY_PACKAGE_CHANGED" for f in validate_product(p)))
    def test_exact_visible_option_only(self):
        self.assertEqual(choose_exact_option(["Yes","No"],"Yes"),"Yes"); self.assertRaises(OptionMismatch,choose_exact_option,["Yes always","No"],"Yes")
    def test_live_question_rejects_unknown(self):
        q=LiveQuestion("q","Q",("Yes","No")); a=validate_live_answer(q,{"selected":["Maybe"],"confidence":.99}); self.assertTrue(a.needs_review); self.assertEqual(a.selected,())
    def test_good_validation(self):
        with tempfile.TemporaryDirectory() as d: self.assertFalse(any(f.severity==Severity.HOLD for f in validate_product(product(Path(d)))))
    def test_missing_package_hold(self):
        with tempfile.TemporaryDirectory() as d:
            p=product(Path(d)); p.package_path=""; self.assertTrue(any(f.code=="PACKAGE_MISSING" for f in validate_product(p)))
    def test_privacy_hold(self):
        with tempfile.TemporaryDirectory() as d:
            p=product(Path(d)); p.fields["collects_personal_data"].value="yes"; self.assertTrue(any(f.code=="PRIVACY_POLICY" for f in validate_product(p)))
    def test_queue_continues_after_hold(self):
        with tempfile.TemporaryDirectory() as d:
            t=Path(d); a=product(t); a.package_path=""; b=product(t); b.product_name="B"; r=run_queue([a,b],dryrun_uploader); self.assertEqual([x.status for x in r.results],["HOLD","DONE"])

    def test_duplicate_product_is_held_and_queue_continues(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            a=product(root)
            b=ProductInput.from_dict(a.to_dict())
            c=product(root); c.product_name="Other"
            other_pkg=root/"other.msix"; other_pkg.write_bytes(b"OTHER")
            c.package_path=str(other_pkg); c.security_package_sha256=file_sha256(str(other_pkg))
            r=run_queue([a,b,c],dryrun_uploader)
            self.assertEqual([x.status for x in r.results],["DONE","HOLD","DONE"])
            self.assertTrue(any(f.code=="DUPLICATE_PRODUCT" for f in r.results[1].findings))

    def test_same_package_for_different_products_is_held(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            a=product(root)
            b=ProductInput.from_dict(a.to_dict()); b.product_name="Different"
            r=run_queue([a,b],dryrun_uploader)
            self.assertEqual([x.status for x in r.results],["DONE","HOLD"])
            self.assertTrue(any(f.code=="DUPLICATE_PACKAGE" for f in r.results[1].findings))
    def test_auth_stops(self):
        with tempfile.TemporaryDirectory() as d:
            p=product(Path(d))
            def up(_): raise GlobalAuthError("expired")
            r=run_queue([p,p],up); self.assertTrue(r.stopped_early); self.assertEqual(len(r.results),1)
    def test_ambiguous_continues(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            a=product(root)
            b=product(root); b.product_name="B"
            second=root/"b.msix"; second.write_bytes(b"B")
            b.package_path=str(second); b.security_package_sha256=file_sha256(str(second))
            n={"i":0}
            def up(_):
                n["i"]+=1
                if n["i"]==1: raise AmbiguousWriteError("unknown")
                return ["ok"]
            r=run_queue([a,b],up); self.assertEqual([x.status for x in r.results],["UNKNOWN","DONE"])
    def test_dry_plan_has_package(self):
        with tempfile.TemporaryDirectory() as d: self.assertTrue(any(x.startswith("packages:upload") for x in dryrun_uploader(product(Path(d)))))
    def test_report(self):
        r=QueueReport([ProductResult("A","DONE"),ProductResult("B","HOLD")]); s=render_markdown(r); self.assertIn("| DONE | 1 |",s); self.assertIn("| HOLD | 1 |",s)

    def test_single_result_summary(self):
        r=QueueReport([ProductResult("A","DONE")])
        s=r.summary()
        self.assertEqual(s["mode"],"single")
        self.assertEqual(s["label"],"成功")
        self.assertIn("## 成功",render_markdown(r))

    def test_batch_result_summary(self):
        r=QueueReport([
            ProductResult("A","DONE"),
            ProductResult("B","DONE"),
            ProductResult("C","HOLD"),
            ProductResult("D","ERROR"),
            ProductResult("E","UNKNOWN"),
        ])
        s=r.summary()
        self.assertEqual(s["mode"],"batch")
        self.assertEqual((s["total"],s["success"],s["hold"],s["failed"],s["unknown"]),(5,2,1,1,1))
        text=render_markdown(r)
        self.assertIn("総件数 5件",text)
        self.assertIn("成功 2件",text)

    def test_no_trailer_is_clean_and_not_uploaded(self):
        with tempfile.TemporaryDirectory() as d:
            p=product(Path(d))
            self.assertEqual(p.trailers,[])
            self.assertFalse(any(f.code.startswith("TRAILER_") for f in validate_product(p)))
            self.assertFalse(any("trailer:" in x for x in dryrun_uploader(p)))

    def test_optional_trailer_is_validated_only_when_present(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); p=product(root)
            video=root/"t.mp4"; video.write_bytes(b"x")
            thumb=root/"t.png"; thumb.write_bytes(b"x")
            p.trailers=[TrailerAsset(str(video),"Demo",str(thumb))]
            findings=validate_product(p)
            self.assertFalse(any(f.code in {"TRAILER_VIDEO_MISSING","TRAILER_TITLE_MISSING","TRAILER_THUMBNAIL_MISSING"} for f in findings))
            self.assertTrue(any("trailer:0:upload" in x for x in dryrun_uploader(p)))

    def test_game_trailer_requires_hero_art_but_no_video_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); p=product(root,"game")
            self.assertFalse(any(f.code=="TRAILER_HERO_ART_REQUIRED" for f in validate_product(p)))
            video=root/"t.mp4"; video.write_bytes(b"x")
            thumb=root/"t.png"; thumb.write_bytes(b"x")
            p.trailers=[TrailerAsset(str(video),"Demo",str(thumb))]
            self.assertTrue(any(f.code=="TRAILER_HERO_ART_REQUIRED" for f in validate_product(p)))

    def test_overview_update_simulation_exact_match(self):
        s=simulate_overview_start("Daymark AI","update",("Daymark AI","Other"))
        self.assertTrue(s.safe_to_continue)
        self.assertEqual(s.start_url,PARTNER_CENTER_APPS_GAMES_URL)
        self.assertIn("search_exact:Daymark AI",s.actions)
        self.assertIn("open_exact_product:Daymark AI",s.actions)

    def test_overview_update_simulation_rejects_missing_or_ambiguous_match(self):
        s=simulate_overview_start("Daymark AI","update",("Other",))
        self.assertFalse(s.safe_to_continue)
        self.assertEqual(s.hold_reason,"product_not_uniquely_matched")

    def test_overview_new_product_path(self):
        s=simulate_overview_start("New Product","new",())
        self.assertTrue(s.safe_to_continue)
        self.assertIn("click:new_product",s.actions)
        self.assertIn("reserve_name:New Product",s.actions)
if __name__=="__main__": unittest.main()
