import unittest
from store_manager.store_fields import FIELD_SPECS, SECTIONS, automation_policy_summary, field_spec, fields_for_section

class StoreFieldMapTests(unittest.TestCase):
    def test_all_specs_have_known_section(self):
        self.assertTrue(FIELD_SPECS)
        self.assertTrue(all(x.section in SECTIONS for x in FIELD_SPECS))

    def test_required_store_listing_fields_are_mapped(self):
        keys={x.key for x in fields_for_section("store_listings")}
        self.assertIn("description",keys)
        self.assertIn("screenshots",keys)

    def test_security_and_live_policies_are_separate(self):
        policy=automation_policy_summary()
        self.assertIn("collects_personal_data",policy["security"])
        self.assertIn("iarc_questionnaire",policy["live"])

    def test_description_allows_ai(self):
        spec=field_spec("description")
        self.assertTrue(spec.ai_allowed)
        self.assertEqual(spec.source_policy,"ai")

    def test_package_upload_is_not_ai(self):
        spec=field_spec("package_upload")
        self.assertFalse(spec.ai_allowed)
        self.assertEqual(spec.source_policy,"package")

if __name__=="__main__":
    unittest.main()
