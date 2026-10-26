from __future__ import annotations
from dataclasses import dataclass
from .core import ProductInput
class SelectorNotVerified(RuntimeError): pass
class OptionMismatch(RuntimeError): pass
@dataclass(frozen=True)
class SelectorSpec:
    section:str; field:str; selector:str|None=None; verified:bool=False

def require_verified(s:SelectorSpec):
    if not s.verified or not s.selector: raise SelectorNotVerified(f"Selector not verified: {s.section}/{s.field}")
    return s.selector

def choose_exact_option(visible,desired):
    m=[x for x in visible if x==desired]
    if len(m)!=1: raise OptionMismatch(f"Expected exactly one option {desired!r}; got {m!r}")
    return m[0]

def build_dry_plan(p:ProductInput):
    return ["product:open_or_locate","pricing_availability:fill_verified","properties:fill_verified","age_ratings:answer_visible_questions",f"packages:upload:{p.package_path}","packages:wait_validation","store_listings:fill_text_and_assets","submission_options:fill_verified","review:save_draft_only"]
def dryrun_uploader(p): return build_dry_plan(p)
