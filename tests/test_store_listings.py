from __future__ import annotations

import json
from pathlib import Path
import struct
import tempfile
import unittest

from store_manager.store_listings import (
    StoreListingDraft,
    StoreListingValidationError,
    plan_listing_languages,
    screenshot_upload_next_action,
    store_listing_save_succeeded,
    validate_store_listing,
)


def write_png_header(path: Path, width: int = 1426, height: int = 923) -> None:
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + struct.pack(">II", width, height)
    )


def listing(path: Path, **overrides) -> StoreListingDraft:
    values = dict(
        locale="en-US",
        package_version="0.25.25.0",
        source_version="0.25.25.0",
        description="Offline fictional business strategy simulation.",
        features=("Quarterly decisions", "Local saves"),
        short_description="Run a fictional business offline.",
        keywords=("business strategy", "offline game"),
        developed_by="Okinawa Desktop Tools",
        screenshots=(str(path),),
    )
    values.update(overrides)
    return StoreListingDraft(**values)


class StoreListingTests(unittest.TestCase):
    def test_jp_language_plan_removes_only_unneeded_additional_languages(self):
        plan = plan_listing_languages(
            ("Japanese (Japan)",),
            ("English", "Japanese"),
            ("Japanese (Japan)",),
        )
        self.assertEqual(plan.add_additional, ())
        self.assertEqual(plan.remove_additional, ("English", "Japanese"))

    def test_package_languages_can_never_be_removed(self):
        with self.assertRaisesRegex(
            StoreListingValidationError, "cannot remove package languages"
        ):
            plan_listing_languages(
                ("English (United States)", "Japanese (Japan)"),
                (),
                ("English (United States)",),
            )

    def test_final_version_png_listing_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            screenshot = Path(directory) / "01_dashboard.png"
            write_png_header(screenshot)
            self.assertEqual(validate_store_listing(listing(screenshot)).locale, "en-US")

    def test_old_or_small_screenshots_and_internal_developer_note_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            screenshot = Path(directory) / "old.png"
            write_png_header(screenshot, 1024, 768)
            with self.assertRaisesRegex(
                StoreListingValidationError, "submitted package version"
            ):
                validate_store_listing(
                    listing(screenshot, source_version="0.25.21.0")
                )
            with self.assertRaisesRegex(
                StoreListingValidationError, "at least 1366x768"
            ):
                validate_store_listing(listing(screenshot))
            write_png_header(screenshot)
            with self.assertRaisesRegex(
                StoreListingValidationError, "internal review text"
            ):
                validate_store_listing(
                    listing(
                        screenshot,
                        developed_by=(
                            "Okinawa Desktop Tools — use this only if it is the "
                            "correct public developer name."
                        ),
                    )
                )

    def test_listing_save_requires_overview_reload_assets_and_pristine_state(self):
        values = dict(
            overview_state="Complete",
            reloaded_description="Customer-facing description",
            expected_description="Customer-facing description",
            reloaded_screenshot_count=5,
            expected_screenshot_count=5,
            dirty=False,
        )
        self.assertTrue(store_listing_save_succeeded(**values))
        for key, bad in (
            ("overview_state", "Incomplete"),
            ("reloaded_description", "Changed"),
            ("reloaded_screenshot_count", 4),
            ("dirty", True),
        ):
            changed = dict(values)
            changed[key] = bad
            with self.subTest(key=key):
                self.assertFalse(store_listing_save_succeeded(**changed))

    def test_single_file_screenshot_upload_waits_for_both_counters(self):
        self.assertEqual(
            screenshot_upload_next_action(
                previous_count=2,
                desktop_count=3,
                thumbnail_count=3,
            ),
            "SCREENSHOT_UPLOAD_CONFIRMED",
        )
        self.assertEqual(
            screenshot_upload_next_action(
                previous_count=2,
                desktop_count=2,
                thumbnail_count=2,
            ),
            "SCREENSHOT_RECONCILE_REQUIRED",
        )
        self.assertEqual(
            screenshot_upload_next_action(
                previous_count=2,
                desktop_count=2,
                thumbnail_count=2,
                explicit_error=True,
                reloaded=True,
            ),
            "SAFE_RETRY_ALLOWED",
        )
        self.assertEqual(
            screenshot_upload_next_action(
                previous_count=2,
                desktop_count=4,
                thumbnail_count=4,
            ),
            "HOLD_AMBIGUOUS_SCREENSHOT_UPLOAD",
        )

    def test_us_jp_live_fixture_has_public_text_and_version_bound_assets(self):
        fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "partner_center_msix_pwa_game_store_listings.json"
        )
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(fixture["route_id"], "msix_pwa_game")
        self.assertEqual(len(fixture["products"]), 2)
        us, jp = fixture["products"]
        self.assertEqual(us["package_version"], "0.25.25.0")
        for locale in ("en-US", "ja-JP"):
            product_listing = us["desired_listings"][locale]
            self.assertEqual(
                product_listing["developed_by"], "Okinawa Desktop Tools"
            )
            self.assertEqual(len(product_listing["screenshots"]), 5)
            self.assertEqual(
                len({asset[1] for asset in product_listing["screenshots"]}), 5
            )
        self.assertEqual(jp["package_version"], "0.1.24.0")
        self.assertEqual(
            jp["desired_additional_language_removals"], ["English", "Japanese"]
        )
        jp_listing = jp["desired_listings"]["ja-JP"]
        self.assertEqual(jp_listing["asset_state"], "FINAL_RUNTIME_CAPTURED")
        self.assertEqual(len(jp_listing["screenshots"]), 5)
        self.assertEqual(len({asset[1] for asset in jp_listing["screenshots"]}), 5)
        self.assertEqual(jp_listing["runtime_qa"]["clean_profile_start"], "PASS")
        self.assertTrue(
            jp_listing["runtime_qa"]["existing_profile_restore_guard"].startswith(
                "BLOCKED_"
            )
        )
        self.assertFalse(fixture["safety"]["submit_for_certification"])
        self.assertFalse(fixture["safety"]["publish"])


if __name__ == "__main__":
    unittest.main()
