import unittest
from store_manager.core import ProductInput, FieldValue, ValueMode, apply_fixed_rules, validate_product

class CommercialPricingContractTests(unittest.TestCase):
    def make(self):
        p=ProductInput("app","Folder Automation Engine","local file organizer")
        p.submission_route="msix_pwa_app"; p.submission_route_source="upstream"
        p.package_type="msix"; p.package_sha256="a"*64
        p.price_mode="paid"; p.price_value="LIVE_LOW_PRICE_TIER"
        p.commercial_approval_required=True
        p.price_confirmed=True; p.trial_confirmed=True
        p.commercial_approved_by="owner-confirmed"
        p.fields["free_trial"]=FieldValue("free_trial",ValueMode.MANUAL,"7_days","owner",1.0,"owner approved trial",True)
        return p

    def test_manual_7_day_trial_survives_fixed_defaults(self):
        p=self.make(); apply_fixed_rules(p)
        self.assertEqual(p.fields["free_trial"].value,"7_days")
        self.assertEqual(p.fields["free_trial"].mode,ValueMode.MANUAL)

    def test_paid_trial_needs_confirmation(self):
        p=self.make(); p.trial_confirmed=False
        codes={x.code for x in validate_product(p)}
        self.assertIn("COMMERCIAL_TRIAL_CONFIRM_REQUIRED",codes)

    def test_paid_price_needs_exact_live_tier(self):
        p=self.make(); p.price_value=""
        codes={x.code for x in validate_product(p)}
        self.assertIn("PAID_PRICE_VALUE_REQUIRED",codes)

    def test_trial_cannot_be_inferred(self):
        p=self.make(); p.fields["free_trial"].mode=ValueMode.FIXED
        codes={x.code for x in validate_product(p)}
        self.assertIn("COMMERCIAL_TRIAL_MUST_BE_MANUAL",codes)

if __name__=="__main__": unittest.main()
