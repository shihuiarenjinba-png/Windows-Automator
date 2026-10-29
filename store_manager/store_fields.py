from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class StoreFieldSpec:
    key: str
    section: str
    label: str
    required: str
    source_policy: str
    ai_allowed: bool
    live_choice_required: bool = False
    notes: str = ""

# source_policy:
# fixed        = app/game preset or saved operator preset
# product      = product-specific operator input
# ai           = Ollama may draft, then validation applies
# security     = explicit security confirmation is mandatory
# package      = derive from selected MSIX/MSIXUPLOAD and validation output
# live         = read the current Partner Center question/options at runtime
# conditional  = required only when Microsoft/manifest state makes it applicable

FIELD_SPECS = (
    StoreFieldSpec("markets","pricing_availability","Markets","required","fixed",False,False,"Default preset may be all available markets; operator may override."),
    StoreFieldSpec("visibility","pricing_availability","Visibility / discoverability","required","fixed",False,True),
    StoreFieldSpec("pricing_model","pricing_availability","Base price mode","required","product",False,True),
    StoreFieldSpec("price_value","pricing_availability","Base price / tier","required_if_paid","product",False,True),
    StoreFieldSpec("free_trial","pricing_availability","Free trial","optional","fixed",False,True),
    StoreFieldSpec("schedule","pricing_availability","Availability schedule","optional","fixed",False,True),
    StoreFieldSpec("organizational_licensing","pricing_availability","Organizational licensing","optional","fixed",False,True),

    StoreFieldSpec("primary_category","properties","Primary category","required","ai",True,True),
    StoreFieldSpec("subcategory_or_genre","properties","Subcategory / genre","conditional","ai",True,True),
    StoreFieldSpec("secondary_category","properties","Secondary category","optional","ai",True,True),
    StoreFieldSpec("collects_personal_data","properties","Accesses, collects, or transmits personal information","required","security",False,True),
    StoreFieldSpec("privacy_policy_url","properties","Privacy policy","required_if_personal_data","security",False),
    StoreFieldSpec("website","properties","Website","optional","product",True),
    StoreFieldSpec("support_contact","properties","Support contact","conditional","product",True),
    StoreFieldSpec("game_settings","properties","Game settings","conditional","ai",True,True),
    StoreFieldSpec("product_declarations","properties","Product declarations","conditional","security",False,True),
    StoreFieldSpec("system_requirements","properties","System requirements","optional","ai",True),

    StoreFieldSpec("iarc_questionnaire","age_ratings","IARC age rating questionnaire","required","live",True,True,"Every currently displayed question must be answered accurately."),

    StoreFieldSpec("package_upload","packages","App package","required","package",False),
    StoreFieldSpec("device_family_availability","packages","Device family availability","optional","package",False,True),
    StoreFieldSpec("package_validation","packages","Microsoft package validation","required","package",False),

    StoreFieldSpec("description","store_listings","Description","required","ai",True),
    StoreFieldSpec("whats_new","store_listings","What's new","optional_update","ai",True),
    StoreFieldSpec("features","store_listings","Product features","optional","ai",True),
    StoreFieldSpec("screenshots","store_listings","Screenshots","required_min_1","product",False),
    StoreFieldSpec("store_logos","store_listings","Store logos","optional","product",False),
    StoreFieldSpec("trailers","store_listings","Trailers","optional","product",False),
    StoreFieldSpec("short_description","store_listings","Short description","optional","ai",True),
    StoreFieldSpec("keywords","store_listings","Keywords","optional","ai",True),

    StoreFieldSpec("publishing_hold","submission_options","Publishing hold","optional","fixed",False,True),
    StoreFieldSpec("certification_notes","submission_options","Notes for certification","optional","ai",True),
    StoreFieldSpec("restricted_capabilities","submission_options","Restricted capability explanation","conditional","conditional",True,False,"Required when restricted capabilities are detected in the package."),
)

SECTIONS=(
    "pricing_availability",
    "properties",
    "age_ratings",
    "packages",
    "store_listings",
    "submission_options",
)

def fields_for_section(section: str):
    return tuple(x for x in FIELD_SPECS if x.section == section)

def field_spec(key: str):
    for spec in FIELD_SPECS:
        if spec.key == key:
            return spec
    raise KeyError(key)

def automation_policy_summary():
    out={"fixed":[],"product":[],"ai":[],"security":[],"package":[],"live":[],"conditional":[]}
    for spec in FIELD_SPECS:
        out.setdefault(spec.source_policy,[]).append(spec.key)
    return out
