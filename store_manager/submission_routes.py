from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class SubmissionRouteTemplate:
    route_id: str
    partner_center_label: str
    product_type: str
    package_mode: str
    accepted_extensions: tuple[str, ...]
    accepted_package_types: tuple[str, ...]
    required_inputs: tuple[str, ...]
    required_sections: tuple[str, ...]
    ai_fillable_fields: tuple[str, ...]
    fixed_defaults: tuple[tuple[str, str], ...]
    live_adapter: str
    live_write_supported: bool
    notes: tuple[str, ...]

ROUTE_TEMPLATES = {
    "msix_pwa_app": SubmissionRouteTemplate(
        "msix_pwa_app",
        "MSIX or PWA app",
        "app",
        "store_binary_upload",
        (".msix", ".msixupload", ".msixbundle", ".appx", ".appxupload", ".appxbundle"),
        ("msix", "msixupload", "msixbundle", "appx", "appxupload", "appxbundle", "pwa"),
        ("package_path", "images_dir", "security_profile", "pricing"),
        ("pricing_availability", "properties", "age_ratings", "packages", "store_listings", "submission_options"),
        ("description", "features", "whats_new", "primary_category", "system_requirements", "certification_notes"),
        (("visibility", "discoverable"), ("free_trial", "none"), ("publish_hold", "manual_publish")),
        "msix_app",
        True,
        (
            "Current observed Partner Center mapping belongs to this route.",
            "Actual live write still requires selector_map write_enabled=true and verified write-state selectors.",
        ),
    ),
    "exe_msi_app": SubmissionRouteTemplate(
        "exe_msi_app",
        "EXE or MSI app",
        "app",
        "installer_url",
        (".exe", ".msi"),
        ("exe", "msi"),
        (
            "package_path",
            "installer_url",
            "installer_type",
            "installer_architecture",
            "silent_install_args",
            "installer_languages",
            "images_dir",
            "security_profile",
            "pricing",
        ),
        ("pricing_availability", "properties", "age_ratings", "installer", "store_listings", "submission_options"),
        ("description", "features", "whats_new", "primary_category", "system_requirements", "certification_notes"),
        (("visibility", "discoverable"), ("free_trial", "none"), ("publish_hold", "manual_publish")),
        "exe_msi_app",
        False,
        (
            "Partner Center uses a versioned HTTPS installer URL instead of Store binary hosting.",
            "Installer must support silent installation. Dedicated live mapping is not yet verified.",
        ),
    ),
    "gdk_game": SubmissionRouteTemplate(
        "gdk_game",
        "GDK game",
        "game",
        "gdk_msixvc",
        (".msixvc", ".msixvc2"),
        ("msixvc", "msixvc2"),
        (
            "package_path",
            "gdk_ekb_path",
            "gdk_symbols_path",
            "gdk_submission_validator_path",
            "images_dir",
            "security_profile",
            "pricing",
        ),
        ("game_setup", "packages", "properties", "age_ratings", "store_listings", "pricing_availability", "submission_options"),
        ("description", "features", "whats_new", "game_genres", "certification_notes"),
        (("visibility", "discoverable"), ("free_trial", "none"), ("publish_hold", "manual_publish")),
        "gdk_game",
        False,
        (
            "PC GDK packages use MSIXVC/MSIXVC2.",
            "Game setup/package branch semantics differ from MSIX app submissions.",
            "Dedicated GDK live mapping must be observed before Store write is enabled.",
        ),
    ),
    "msix_pwa_game": SubmissionRouteTemplate(
        "msix_pwa_game",
        "MSIX or PWA game",
        "game",
        "store_binary_upload",
        (".msix", ".msixupload", ".msixbundle", ".appx", ".appxupload", ".appxbundle"),
        ("msix", "msixupload", "msixbundle", "appx", "appxupload", "appxbundle", "pwa"),
        ("package_path", "images_dir", "security_profile", "pricing"),
        ("pricing_availability", "properties", "age_ratings", "packages", "store_listings", "submission_options"),
        ("description", "features", "whats_new", "game_genres", "certification_notes"),
        (("visibility", "discoverable"), ("free_trial", "none"), ("publish_hold", "manual_publish")),
        "msix_game",
        False,
        (
            "Use for existing UWP/MSIX games or PWA games.",
            "Dedicated game live mapping and save-state evidence are not yet verified.",
        ),
    ),
}

ROUTE_IDS = tuple(ROUTE_TEMPLATES)
ROUTE_LABELS = tuple(ROUTE_TEMPLATES[x].partner_center_label for x in ROUTE_IDS)
LABEL_TO_ROUTE_ID = {ROUTE_TEMPLATES[x].partner_center_label: x for x in ROUTE_IDS}
ROUTE_SOURCES = ("upstream", "legacy_default", "manual")

def default_route_for_product_type(product_type: str) -> str:
    if product_type == "app":
        return "msix_pwa_app"
    if product_type == "game":
        return "msix_pwa_game"
    raise ValueError("product_type must be app or game")

def route_template(route_id: str, product_type: str | None = None) -> SubmissionRouteTemplate:
    route_id = (route_id or "").strip()
    if not route_id:
        if not product_type:
            raise ValueError("submission_route or product_type is required")
        route_id = default_route_for_product_type(product_type)
    try:
        template = ROUTE_TEMPLATES[route_id]
    except KeyError as exc:
        raise ValueError(f"unsupported submission route: {route_id}") from exc
    if product_type and template.product_type != product_type:
        raise ValueError(f"submission route {route_id} requires product_type={template.product_type}")
    return template

def route_id_from_label(label: str) -> str:
    try:
        return LABEL_TO_ROUTE_ID[label]
    except KeyError as exc:
        raise ValueError(f"unknown Partner Center product type label: {label}") from exc

def route_label(route_id: str, product_type: str | None = None) -> str:
    return route_template(route_id, product_type).partner_center_label

def route_display(route_id: str, product_type: str | None = None, source: str = "manual") -> str:
    label = route_label(route_id, product_type)
    return f"{label} [上流工程で確定済み]" if source == "upstream" else label
