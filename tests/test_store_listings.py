from __future__ import annotations

import json
from pathlib import Path
import struct

import pytest

from store_manager.store_listings import (
    StoreListingDraft,
    StoreListingValidationError,
    plan_listing_languages,
    store_listing_save_succeeded,
    validate_store_listing,
)


def write_png_header(path, width=1426, height=923):
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height))


def listing(path, **overrides):
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


def test_jp_language_plan_removes_only_unneeded_additional_languages():
    plan = plan_listing_languages(
        ("Japanese (Japan)",),
        ("English", "Japanese"),
        ("Japanese (Japan)",),
    )
    assert plan.add_additional == ()
    assert plan.remove_additional == ("English", "Japanese")


def test_package_languages_can_never_be_removed():
    with pytest.raises(StoreListingValidationError, match="cannot remove package languages"):
        plan_listing_languages(("English (United States)", "Japanese (Japan)"), (), ("English (United States)",))


def test_final_version_png_listing_is_valid(tmp_path):
    screenshot = tmp_path / "01_dashboard.png"
    write_png_header(screenshot)
    assert validate_store_listing(listing(screenshot)).locale == "en-US"


def test_old_or_small_screenshots_and_internal_developer_note_fail_closed(tmp_path):
    screenshot = tmp_path / "old.png"
    write_png_header(screenshot, 1024, 768)
    with pytest.raises(StoreListingValidationError, match="submitted package version"):
        validate_store_listing(listing(screenshot, source_version="0.25.21.0"))
    with pytest.raises(StoreListingValidationError, match="at least 1366x768"):
        validate_store_listing(listing(screenshot))
    write_png_header(screenshot)
    with pytest.raises(StoreListingValidationError, match="internal review text"):
        validate_store_listing(
            listing(screenshot, developed_by="Okinawa Desktop Tools — use this only if it is the correct public developer name.")
        )


def test_listing_save_requires_overview_reload_assets_and_pristine_state():
    values = dict(
        overview_state="Complete",
        reloaded_description="Customer-facing description",
        expected_description="Customer-facing description",
        reloaded_screenshot_count=5,
        expected_screenshot_count=5,
        dirty=False,
    )
    assert store_listing_save_succeeded(**values)
    for key, bad in (
        ("overview_state", "Incomplete"),
        ("reloaded_description", "Changed"),
        ("reloaded_screenshot_count", 4),
        ("dirty", True),
    ):
        changed = dict(values)
        changed[key] = bad
        assert not store_listing_save_succeeded(**changed), key


def test_us_jp_live_fixture_has_public_text_and_version_bound_assets():
    fixture_path = Path(__file__).parent / "fixtures" / "partner_center_msix_pwa_game_store_listings.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert fixture["route_id"] == "msix_pwa_game"
    assert len(fixture["products"]) == 2
    us, jp = fixture["products"]
    assert us["package_version"] == "0.25.25.0"
    for locale in ("en-US", "ja-JP"):
        listing = us["desired_listings"][locale]
        assert listing["developed_by"] == "Okinawa Desktop Tools"
        assert len(listing["screenshots"]) == 5
        assert len({asset[1] for asset in listing["screenshots"]}) == 5
    assert jp["package_version"] == "0.1.24.0"
    assert jp["desired_additional_language_removals"] == ["English", "Japanese"]
    jp_listing = jp["desired_listings"]["ja-JP"]
    assert jp_listing["asset_state"] == "FINAL_RUNTIME_CAPTURED"
    assert len(jp_listing["screenshots"]) == 5
    assert len({asset[1] for asset in jp_listing["screenshots"]}) == 5
    assert jp_listing["runtime_qa"]["clean_profile_start"] == "PASS"
    assert jp_listing["runtime_qa"]["existing_profile_restore_guard"].startswith("BLOCKED_")
    assert fixture["safety"]["submit_for_certification"] is False
    assert fixture["safety"]["publish"] is False
