from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from store_manager.cli import _load_queue, _nonblank_path


class NightRunQueueInputTests(unittest.TestCase):
    def valid_product(self, **overrides):
        value = {
            "product_type": "app",
            "product_name": "Example",
            "app_summary": "Example app",
            "store_product_id": "9P1234567890",
            "draft_id": "1152921505700000000",
            "package_path": "example.msix",
        }
        value.update(overrides)
        return value

    def test_empty_path_fails_with_runner_hint(self):
        with self.assertRaisesRegex(ValueError, "run_local_store_upload"):
            _load_queue("   ")

    def test_empty_argument_is_rejected_by_argparse_type(self):
        with self.assertRaisesRegex(Exception, "path is empty"):
            _nonblank_path("")

    def test_missing_file_and_invalid_json_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "does not exist"):
                _load_queue(str(Path(tmp) / "missing.json"))
            bad = Path(tmp) / "bad.json"
            bad.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid JSON"):
                _load_queue(str(bad))

    def test_queue_must_be_nonempty_list_of_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "queue.json"
            for raw in ([], {}, ["bad"]):
                p.write_text(json.dumps(raw), encoding="utf-8")
                with self.assertRaises(ValueError):
                    _load_queue(str(p))

    def test_queue_requires_existing_draft_and_unique_product_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "queue.json"
            p.write_text(json.dumps([self.valid_product(draft_id="")]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Draft ID"):
                _load_queue(str(p))
            p.write_text(json.dumps([self.valid_product(), self.valid_product()]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate Store Product ID"):
                _load_queue(str(p))

    def test_invalid_product_fields_report_queue_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "queue.json"
            p.write_text(json.dumps([self.valid_product(unexpected_field=True)]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid ProductInput"):
                _load_queue(str(p))

    def test_single_product_queue_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "queue.json"
            p.write_text(json.dumps([self.valid_product()]), encoding="utf-8")
            products = _load_queue(str(p))
            self.assertEqual(len(products), 1)
            self.assertEqual(products[0].draft_id, "1152921505700000000")


if __name__ == "__main__":
    unittest.main()
