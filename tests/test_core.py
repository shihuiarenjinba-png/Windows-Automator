import tempfile,unittest
from pathlib import Path
from store_manager.core import *
from store_manager.partner_center import choose_exact_option,OptionMismatch,dryrun_uploader
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
        p.fields[f.key]=FieldValue(f.key,ValueMode.MANUAL,val,"test")
    p.fields["description"]=FieldValue("description",ValueMode.MANUAL,"Description","test"); return p
class T(unittest.TestCase):
    def test_catalogs(self): self.assertIn("Productivity",APP_CATEGORIES); self.assertIn("Strategy",GAME_GENRES)
    def test_options_are_tuples(self):
        for f in fields_for("game"): self.assertIsInstance(f.choices,tuple)
    def test_fixed_offline(self):
        p=ProductInput("app","A","Offline",price_mode="free"); apply_fixed_rules(p); self.assertEqual(p.fields["requires_internet"].value,"no")
    def test_invalid_choice_from_ollama(self):
        p=ProductInput("app","A","x"); apply_answer(p,{"choices":{"contains_ads":{"value":"maybe","confidence":.99}}}); self.assertEqual(p.fields["contains_ads"].mode,ValueMode.REVIEW)
    def test_sensitive_confidence(self):
        p=ProductInput("game","G","x"); apply_answer(p,{"choices":{"violence":{"value":"no","confidence":.8}}}); self.assertEqual(p.fields["violence"].mode,ValueMode.REVIEW)
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
    def test_auth_stops(self):
        with tempfile.TemporaryDirectory() as d:
            p=product(Path(d))
            def up(_): raise GlobalAuthError("expired")
            r=run_queue([p,p],up); self.assertTrue(r.stopped_early); self.assertEqual(len(r.results),1)
    def test_ambiguous_continues(self):
        with tempfile.TemporaryDirectory() as d:
            t=Path(d); a=product(t); b=product(t); b.product_name="B"; n={"i":0}
            def up(_):
                n["i"]+=1
                if n["i"]==1: raise AmbiguousWriteError("unknown")
                return ["ok"]
            r=run_queue([a,b],up); self.assertEqual([x.status for x in r.results],["UNKNOWN","DONE"])
    def test_dry_plan_has_package(self):
        with tempfile.TemporaryDirectory() as d: self.assertTrue(any(x.startswith("packages:upload") for x in dryrun_uploader(product(Path(d)))))
    def test_report(self):
        r=QueueReport([ProductResult("A","DONE"),ProductResult("B","HOLD")]); s=render_markdown(r); self.assertIn("| DONE | 1 |",s); self.assertIn("| HOLD | 1 |",s)
if __name__=="__main__": unittest.main()
