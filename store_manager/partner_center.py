from __future__ import annotations
from dataclasses import dataclass
from .core import ProductInput

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

def simulate_overview_start(product_name:str, submission_kind:str="update", visible_products:tuple[str,...]=()):
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
    if submission_kind=="new":
        actions += ["click:new_product", "choose:app_or_game", f"reserve_name:{name}"]
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
    start=simulate_overview_start(p.product_name, "update")
    return [
        *start.actions,
        "submission:start_or_update",
        "pricing_availability:fill_verified",
        "properties:fill_verified",
        "age_ratings:answer_visible_questions",
        f"packages:upload:{p.package_path}",
        "packages:wait_validation",
        "store_listings:fill_text_and_assets",
        "submission_options:fill_verified",
        "review:save_draft_only",
    ]

def dryrun_uploader(p):
    return build_dry_plan(p)
