import unittest

from store_manager import gui
from store_manager.core import APP_CATEGORIES, GAME_GENRES, ValueMode
from store_manager.submission_routes import ROUTE_LABELS


class GuiContractTests(unittest.TestCase):
    def test_module_imports(self):
        self.assertTrue(callable(gui.main))

    def test_mode_labels_cover_all_modes(self):
        self.assertEqual(set(gui.MODE_LABELS), set(ValueMode))

    def test_microsoft_choice_catalogs_are_immutable_tuples(self):
        self.assertIsInstance(APP_CATEGORIES, tuple)
        self.assertIsInstance(GAME_GENRES, tuple)

    def test_four_partner_center_product_types_are_exposed(self):
        self.assertEqual(
            ROUTE_LABELS,
            ("MSIX or PWA app","EXE or MSI app","GDK game","MSIX or PWA game"),
        )

    def test_user_facing_text_labels_exist(self):
        self.assertIn("description", gui.TEXT_LABELS)
        self.assertIn("privacy_policy_url", gui.TEXT_LABELS)


if __name__ == "__main__":
    unittest.main()
