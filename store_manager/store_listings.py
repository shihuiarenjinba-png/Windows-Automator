from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import struct


VERSION4 = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
INTERNAL_DEVELOPER_MARKERS = (
    "use this only",
    "correct public developer",
    "internal",
    "todo",
    "placeholder",
)


class StoreListingValidationError(ValueError):
    """A Store listing is incomplete or contains non-public draft material."""


@dataclass(frozen=True)
class ListingLanguagePlan:
    package_languages: tuple[str, ...]
    additional_languages: tuple[str, ...]
    desired_languages: tuple[str, ...]
    add_additional: tuple[str, ...]
    remove_additional: tuple[str, ...]


@dataclass(frozen=True)
class StoreListingDraft:
    locale: str
    package_version: str
    source_version: str
    description: str
    features: tuple[str, ...]
    short_description: str
    keywords: tuple[str, ...]
    developed_by: str
    screenshots: tuple[str, ...]


@dataclass(frozen=True)
class StoreListingSaveObservation:
    """Signals required to advance a live Store listing after Save.

    A button click, redirect, or file-chooser completion is never sufficient on
    its own.  The route advances only after the exact listing is reloaded, all
    expected assets are retained, and every selected language is Complete.
    """

    save_requested: bool = False
    redirected_to_overview: bool = False
    overview_state: str = "Unknown"
    reload_completed: bool = False
    exact_fields_retained: bool = False
    expected_screenshot_count: int = 0
    reloaded_screenshot_count: int = 0
    language_states: tuple[str, ...] = ()
    dirty: bool = True
    product_breadcrumb_available: bool = False


def plan_listing_languages(
    package_languages: tuple[str, ...],
    additional_languages: tuple[str, ...],
    desired_languages: tuple[str, ...],
) -> ListingLanguagePlan:
    """Plan exact language changes without ever removing a package language."""

    package = tuple(dict.fromkeys(x.strip() for x in package_languages if x.strip()))
    additional = tuple(dict.fromkeys(x.strip() for x in additional_languages if x.strip()))
    desired = tuple(dict.fromkeys(x.strip() for x in desired_languages if x.strip()))
    missing_package = tuple(x for x in package if x not in desired)
    if missing_package:
        raise StoreListingValidationError(
            "desired listing languages cannot remove package languages: " + ", ".join(missing_package)
        )
    add = tuple(x for x in desired if x not in package and x not in additional)
    remove = tuple(x for x in additional if x not in desired)
    return ListingLanguagePlan(package, additional, desired, add, remove)


def png_dimensions(path: str | Path) -> tuple[int, int]:
    raw = Path(path).read_bytes()[:24]
    if len(raw) < 24 or raw[:8] != PNG_SIGNATURE or raw[12:16] != b"IHDR":
        raise StoreListingValidationError(f"screenshot is not a PNG: {path}")
    return struct.unpack(">II", raw[16:24])


def validate_store_listing(draft: StoreListingDraft) -> StoreListingDraft:
    if not draft.locale.strip():
        raise StoreListingValidationError("listing locale is required")
    if not VERSION4.fullmatch(draft.package_version) or not VERSION4.fullmatch(draft.source_version):
        raise StoreListingValidationError("package_version and source_version must be four-part versions")
    if draft.package_version != draft.source_version:
        raise StoreListingValidationError("Store screenshots must come from the submitted package version")
    if not draft.description.strip() or len(draft.description) > 10_000:
        raise StoreListingValidationError("description is required and must be at most 10000 characters")
    if not draft.short_description.strip() or len(draft.short_description) > 270:
        raise StoreListingValidationError("short description is required and must be at most 270 characters")
    if len(draft.features) > 20 or any(not item.strip() for item in draft.features):
        raise StoreListingValidationError("features must contain at most 20 non-empty items")
    if len(draft.keywords) > 7:
        raise StoreListingValidationError("keywords must contain at most 7 items")
    if any(not item.strip() or len(item) > 40 for item in draft.keywords):
        raise StoreListingValidationError("each keyword must contain 1 to 40 characters")
    if sum(len(item.split()) for item in draft.keywords) > 21:
        raise StoreListingValidationError("keywords must contain at most 21 separate words")
    developer = draft.developed_by.strip()
    if not developer:
        raise StoreListingValidationError("Developed by is required by the route template")
    if any(marker in developer.casefold() for marker in INTERNAL_DEVELOPER_MARKERS):
        raise StoreListingValidationError("Developed by contains internal review text")
    if not draft.screenshots:
        raise StoreListingValidationError("at least one Desktop screenshot is required")
    resolved = [Path(item).resolve() for item in draft.screenshots]
    if len(set(resolved)) != len(resolved):
        raise StoreListingValidationError("screenshot paths must be unique")
    for screenshot in resolved:
        if not screenshot.is_file():
            raise StoreListingValidationError(f"screenshot does not exist: {screenshot}")
        width, height = png_dimensions(screenshot)
        if width < 1366 or height < 768:
            raise StoreListingValidationError(
                f"Desktop screenshot must be at least 1366x768: {screenshot} ({width}x{height})"
            )
    return draft


def store_listing_save_succeeded(
    *,
    overview_state: str,
    reloaded_description: str,
    expected_description: str,
    reloaded_screenshot_count: int,
    expected_screenshot_count: int,
    dirty: bool,
) -> bool:
    """Require Overview, reload text, assets, and pristine state as one success signal."""

    return (
        overview_state == "Complete"
        and reloaded_description.strip() == expected_description.strip()
        and reloaded_screenshot_count == expected_screenshot_count
        and expected_screenshot_count > 0
        and dirty is False
    )


def screenshot_upload_next_action(
    *,
    previous_count: int,
    desktop_count: int,
    thumbnail_count: int,
    upload_pending: bool = False,
    explicit_error: bool = False,
    reloaded: bool = False,
) -> str:
    """Reconcile one single-file Partner Center screenshot upload.

    The chooser completing is not proof that Partner Center accepted the file.
    Counts can update several seconds after ``setFiles`` returns, and the button
    order changes after the first thumbnail appears.  Callers must therefore
    wait for both counters, and must not click an unscoped first/last button as
    a retry shortcut.
    """

    if min(previous_count, desktop_count, thumbnail_count) < 0:
        return "HOLD_INVALID_SCREENSHOT_COUNT"
    if desktop_count == previous_count + 1 and thumbnail_count == desktop_count:
        return "SCREENSHOT_UPLOAD_CONFIRMED"
    if desktop_count > previous_count + 1 or thumbnail_count > previous_count + 1:
        return "HOLD_AMBIGUOUS_SCREENSHOT_UPLOAD"
    if desktop_count != thumbnail_count:
        return "SCREENSHOT_RECONCILE_REQUIRED"
    if upload_pending:
        return "SCREENSHOT_UPLOAD_IN_PROGRESS"
    if desktop_count == previous_count:
        if explicit_error and reloaded:
            return "SAFE_RETRY_ALLOWED"
        return "SCREENSHOT_RECONCILE_REQUIRED"
    return "HOLD_AMBIGUOUS_SCREENSHOT_UPLOAD"


def store_listing_next_action(observation: StoreListingSaveObservation) -> str:
    """Return the deterministic next action for the listing Save/reload flow."""

    if not observation.save_requested:
        return "SAVE_LISTING"
    if not observation.redirected_to_overview:
        if observation.product_breadcrumb_available:
            return "CLICK_EXACT_PRODUCT_BREADCRUMB"
        return "OVERVIEW_RECONCILE_REQUIRED"
    if observation.overview_state == "Incomplete":
        return "HOLD_STORE_LISTING_INCOMPLETE"
    if observation.overview_state != "Complete":
        return "HOLD_UNKNOWN_STORE_LISTING_STATE"
    if not observation.reload_completed:
        return "REOPEN_AND_RELOAD_LISTING"
    if observation.expected_screenshot_count <= 0:
        return "HOLD_INVALID_SCREENSHOT_COUNT"
    if observation.reloaded_screenshot_count != observation.expected_screenshot_count:
        return "HOLD_STORE_LISTING_RECONCILE_FAILED"
    if not observation.exact_fields_retained or observation.dirty:
        return "HOLD_STORE_LISTING_RECONCILE_FAILED"
    if not observation.language_states or any(
        state != "Complete" for state in observation.language_states
    ):
        return "HOLD_STORE_LISTING_LANGUAGE_INCOMPLETE"
    return "LISTING_SAVED"
