from __future__ import annotations
from dataclasses import dataclass
from .core import ProductInput
from .submission_routes import default_route_for_product_type, route_template

PARTNER_CENTER_APPS_GAMES_URL = "https://partner.microsoft.com/en-us/dashboard/apps-and-games/overview"

class SelectorNotVerified(RuntimeError):
    pass

class OptionMismatch(RuntimeError):
    pass

@dataclass(frozen=True)
class SelectorSpec:
    section:str
    field:str
    selector:str|None=None
    verified:bool=False

@dataclass(frozen=True)
class OverviewSimulation:
    start_url:str
    mode:str
    product_name:str
    actions:tuple[str,...]
    safe_to_continue:bool
    hold_reason:str=""

def require_verified(s:SelectorSpec):
    if not s.verified or not s.selector:
        raise SelectorNotVerified(f"Selector not verified: {s.section}/{s.field}")
    return s.selector

def choose_exact_option(visible,desired):
    m=[x for x in visible if x==desired]
    if len(m)!=1:
        raise OptionMismatch(f"Expected exactly one option {desired!r}; got {m!r}")
    return m[0]

def simulate_overview_start(product_name:str, submission_kind:str="update", visible_products:tuple[str,...]=(), submission_route:str="msix_pwa_app", product_type:str|None=None):
    name=(product_name or "").strip()
    if not name:
        return OverviewSimulation(
            PARTNER_CENTER_APPS_GAMES_URL,
            submission_kind,
            name,
            ("open:apps_and_games_overview",),
            False,
            "product_name_missing",
        )
    actions=["open:apps_and_games_overview"]
    route=route_template(submission_route or default_route_for_product_type(product_type or "app"), product_type)
    if submission_kind=="new":
        actions += ["click:new_product", f"choose_product_type_exact:{route.partner_center_label}", f"reserve_name:{name}"]
        return OverviewSimulation(
            PARTNER_CENTER_APPS_GAMES_URL,
            submission_kind,
            name,
            tuple(actions),
            True,
        )
    actions += [f"search_exact:{name}"]
    matches=[x for x in visible_products if x==name]
    if visible_products:
        if len(matches)!=1:
            return OverviewSimulation(
                PARTNER_CENTER_APPS_GAMES_URL,
                submission_kind,
                name,
                tuple(actions),
                False,
                "product_not_uniquely_matched",
            )
        actions += [f"open_exact_product:{name}"]
    else:
        actions += [f"open_exact_product_after_live_match:{name}"]
    return OverviewSimulation(
        PARTNER_CENTER_APPS_GAMES_URL,
        submission_kind,
        name,
        tuple(actions),
        True,
    )

def build_dry_plan(p:ProductInput):
    route=route_template(p.submission_route or default_route_for_product_type(p.product_type), p.product_type)
    start=simulate_overview_start(p.product_name, p.submission_kind, submission_route=route.route_id, product_type=p.product_type)
    plan=[
        *start.actions,
        f"submission_route:{route.route_id}",
        f"partner_center_product_type:{route.partner_center_label}",
        "submission:start_or_update",
        "security_profile:require_confirmed_for_selected_package",
    ]
    section_actions={
        "game_setup": ["game_setup:fill_verified_gdk_metadata"],
        "pricing_availability": ["pricing_availability:fill_verified"],
        "properties": ["properties:fill_verified"],
        "age_ratings": ["age_ratings:answer_visible_questions"],
        "packages": [f"packages:upload:{p.package_path}", "packages:wait_validation", "restricted_capabilities:compare_detected_to_confirmed_security_profile"],
        "installer": [f"installer:register_versioned_url:{p.installer_url}", f"installer:local_qa_artifact:{p.package_path}", "installer:verify_silent_install_metadata"],
        "store_listings": ["store_listings:fill_text_and_screenshots"],
        "submission_options": ["submission_options:fill_verified"],
    }
    for section in route.required_sections:
        plan.extend(section_actions[section])
    if p.trailers:
        for i,t in enumerate(p.trailers):
            plan.append(f"store_listings:trailer:{i}:upload:{t.video_path}")
            plan.append(f"store_listings:trailer:{i}:thumbnail:{t.thumbnail_path}")
            plan.append(f"store_listings:trailer:{i}:title:{t.title}")
        if p.product_type=="game":
            plan.append(f"store_listings:super_hero_art:{p.hero_art_path}")
    plan += ["review:save_draft_only"]
    return plan

def dryrun_uploader(p):
    return build_dry_plan(p)
