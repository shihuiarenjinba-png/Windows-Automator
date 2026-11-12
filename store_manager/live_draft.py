from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from time import monotonic
from typing import Any, Protocol
import hashlib
import json
import re
import zipfile
from xml.etree import ElementTree

from .submission_routes import default_route_for_product_type, route_template
from .restricted_capabilities import (
    classify_package_warning,
    exact_capability_match,
    normalize_explanation_text,
    restricted_capabilities_from_package,
)

from .core import (
    AmbiguousWriteError,
    GlobalAuthError,
    ProductInput,
    ProductHoldError,
    UploadOutcome,
    file_sha256,
)


HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")
VERSION4 = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
PARTNER_HOST = "https://partner.microsoft.com/"
REQUIRED_LIVE_SELECTORS = (
    "overview_packages_link",
    "packages_file_input",
    "packages_save_button",
    "packages_validation_state",
    "packages_section_state",
    "packages_save_success",
    "overview_section_states",
)

REQUIRED_SECTIONS = route_template("msix_pwa_app").required_sections


class LiveGateError(ProductHoldError):
    """A fail-closed product or mapping gate prevented a Store write."""


class PackageValidationError(ProductHoldError):
    """Microsoft completed validation and rejected the uploaded package."""


@dataclass(frozen=True)
class DraftContext:
    product_id: str
    draft_id: str
    draft_url: str


@dataclass(frozen=True)
class PackageState:
    validation: str
    section_completion: str
    warning: str = ""
    error: str = ""


@dataclass(frozen=True)
class PackageRuntimeObservation:
    """Normalized live Packages state used by the deterministic conveyor."""

    package_present: bool = False
    upload_in_progress: bool = False
    analyzing: bool = False
    validation: str = "UNKNOWN"
    warning: str = ""
    error: str = ""
    desktop_checked: bool = False
    save_completed: bool = False
    retained_after_reload: bool = False


def package_next_action(observation: PackageRuntimeObservation) -> str:
    """Return one fail-closed next action for a normalized Packages state."""

    if not observation.package_present:
        return "PACKAGE_UPLOAD_REQUIRED"
    if observation.upload_in_progress:
        return "PACKAGE_UPLOAD_IN_PROGRESS"
    if observation.analyzing:
        return "PACKAGE_ANALYZING"
    if observation.validation == "ERROR":
        return "HOLD_PARTNER_CENTER_PACKAGE_VALIDATION"
    if observation.validation == "WARNING":
        code, capabilities = classify_package_warning(observation.warning)
        if code != "RESTRICTED_CAPABILITY_REVIEW_REQUIRED" or capabilities != ("runFullTrust",):
            return "HOLD_UNKNOWN_MICROSOFT_RESPONSE"
    elif observation.validation != "VALID":
        return "PACKAGE_RECONCILE_REQUIRED"
    if not observation.desktop_checked:
        return "DESKTOP_SELECTION_REQUIRED"
    if not observation.save_completed:
        return "PACKAGE_SAVE_REQUIRED"
    if not observation.retained_after_reload:
        return "PACKAGE_RELOAD_REQUIRED"
    return "PACKAGE_SAVED"


def reconcile_file_chooser_timeout(*, package_present: bool) -> str:
    """Never retry a timed-out chooser until the draft has been reconciled."""

    return "PACKAGE_RECONCILE_REQUIRED" if package_present else "SAFE_RETRY_ALLOWED"


def session_expiry_recovery_next_action(
    *,
    session_expired_dialog: bool,
    product_breadcrumb_available: bool,
    product_overview_visible: bool,
    packages_complete: bool,
) -> str:
    """Recover stale section pages without automating the sign-in dialog."""

    if product_overview_visible:
        return "OVERVIEW_RECOVERED" if packages_complete else "OVERVIEW_RECONCILE_REQUIRED"
    if session_expired_dialog and product_breadcrumb_available:
        return "NAVIGATE_PRODUCT_OVERVIEW"
    if session_expired_dialog:
        return "HUMAN_SIGN_IN_REQUIRED"
    return "NO_RECOVERY_REQUIRED"


def store_field_resolution_next_action(
    *,
    current_value_present: bool,
    evidence_value_present: bool,
    new_business_or_legal_decision: bool,
) -> str:
    """Classify Store fields without promoting every blank field to owner input.

    Existing Partner Center values are preserved unless the product profile asks
    for a change.  A blank value can be populated from immutable package, source,
    or checked documentation evidence.  Owner input is reserved for a genuinely
    new business/legal decision such as an unset price.
    """

    if current_value_present:
        return "CURRENT_VALUE_PRESERVE"
    if evidence_value_present:
        return "EVIDENCE_VALUE_APPLY"
    if new_business_or_legal_decision:
        return "OWNER_INPUT_REQUIRED"
    return "HOLD_INSUFFICIENT_EVIDENCE"


def iarc_completion_next_action(
    *,
    questionnaire_complete: bool,
    preview_generated: bool,
    legal_attestation_confirmed: bool,
    save_completed: bool,
    retained_after_reload: bool,
) -> str:
    """Return the next IARC action without inventing a legal attestation.

    The final IARC checkbox simultaneously accepts the IARC Terms of Use and
    attests that the signer is the age of majority in their jurisdiction.  A
    completed evidence-backed questionnaire does not authorize that personal
    declaration.
    """

    if not questionnaire_complete:
        return "IARC_QUESTIONNAIRE_REQUIRED"
    if not preview_generated:
        return "IARC_PREVIEW_REQUIRED"
    if not legal_attestation_confirmed:
        return "OWNER_INPUT_REQUIRED_IARC_LEGAL_ATTESTATION"
    if not save_completed:
        return "IARC_SAVE_REQUIRED"
    if not retained_after_reload:
        return "IARC_RELOAD_REQUIRED"
    return "IARC_SAVED"


@dataclass(frozen=True)
class StoreDraftRuntimeObservation:
    """Route-level Store Draft lifecycle with product values kept outside code."""

    package_saved: bool = False
    pricing_saved: bool = False
    properties_saved: bool = False
    iarc_questionnaire_complete: bool = False
    iarc_legal_attestation_confirmed: bool = False
    iarc_saved: bool = False
    listing_saved: bool = False
    submission_options_saved: bool = False
    overview_reconciled: bool = False
    retained_after_reload: bool = False
    certification_executed: bool = False
    publish_executed: bool = False


def store_draft_next_state(observation: StoreDraftRuntimeObservation) -> str:
    """Return the first unmet route state and stop at the certification boundary."""

    if observation.certification_executed or observation.publish_executed:
        return "HOLD_PROHIBITED_ACTION_EXECUTED"
    if not observation.package_saved:
        return "PACKAGE_UPLOAD_REQUIRED"
    if not observation.pricing_saved:
        return "PRICING_REQUIRED"
    if not observation.properties_saved:
        return "PROPERTIES_REQUIRED"
    if not observation.iarc_questionnaire_complete:
        return "IARC_REQUIRED"
    if not observation.iarc_legal_attestation_confirmed:
        return "IARC_LEGAL_ATTESTATION_REQUIRED"
    if not observation.iarc_saved:
        return "IARC_SAVE_REQUIRED"
    if not observation.listing_saved:
        return "LISTING_REQUIRED"
    if not observation.submission_options_saved:
        return "SUBMISSION_OPTIONS_REQUIRED"
    if not observation.overview_reconciled or not observation.retained_after_reload:
        return "DRAFT_RECONCILING"
    return "STORE_DRAFT_COMPLETE"


def certification_review_state(
    *,
    draft_state: str,
    certification_executed: bool,
    publish_executed: bool,
) -> str:
    """Promote only a completed draft to review; never press certification/publish."""

    if certification_executed or publish_executed:
        return "HOLD_PROHIBITED_ACTION_EXECUTED"
    if draft_state == "STORE_DRAFT_COMPLETE":
        return "READY_FOR_CERTIFICATION_REVIEW"
    return draft_state


@dataclass(frozen=True)
class PackageIdentity:
    name: str
    publisher: str
    version: str


def normalize_partner_center_state(texts: list[str], exact_states: dict[str, str]) -> str:
    """Map observed Partner Center text without fuzzy matching.

    Duplicate messages are common when an existing package and a newly uploaded
    package have the same warning.  They represent one state, while conflicting
    mapped states remain UNKNOWN and require a human to reconcile the target row.
    """

    states = {
        exact_states[text.strip()]
        for text in texts
        if text.strip() in exact_states
    }
    return next(iter(states)) if len(states) == 1 else "UNKNOWN"


def restricted_capability_text_retained(expected: str, reloaded: str) -> bool:
    """Compare persisted text while normalizing only CR/LF and edge whitespace."""

    return normalize_explanation_text(expected) == normalize_explanation_text(reloaded)


def submission_options_save_succeeded(
    *,
    draft_url: str,
    redirected_url: str,
    overview_state: str,
    expected_text: str,
    reloaded_text: str,
    textarea_dirty: bool,
) -> bool:
    """Normalize the US/JP composite success signal without trusting button state."""

    return (
        draft_url.rstrip("/") == redirected_url.rstrip("/")
        and overview_state == "Complete"
        and restricted_capability_text_retained(expected_text, reloaded_text)
        and textarea_dirty is False
    )


class PartnerCenterPort(Protocol):
    def ensure_route_ready(self, product: ProductInput) -> None: ...
    def verify_product_and_draft(self, product: ProductInput) -> DraftContext: ...
    def upload_package(self, product: ProductInput, context: DraftContext) -> PackageState: ...
    def save_packages(self, product: ProductInput, context: DraftContext) -> None: ...
    def reload_and_verify_package(self, product: ProductInput, context: DraftContext) -> PackageState: ...
    def verify_required_sections(self, product: ProductInput, context: DraftContext) -> dict[str, str]: ...
    def capture_evidence(self, product: ProductInput, context: DraftContext) -> list[dict[str, str]]: ...


class RestrictedCapabilitySubmissionPort(Protocol):
    """Narrow adapter contract for the verified Submission Options write."""

    def read_partner_capabilities(self, product: ProductInput, context: DraftContext) -> tuple[str, ...]: ...
    def fill_capability_explanation(self, capability: str, text: str) -> None: ...
    def save_submission_options(self, context: DraftContext) -> str: ...
    def read_submission_options_overview_state(self, product: ProductInput, context: DraftContext) -> str: ...
    def reload_capability_explanations(self, product: ProductInput, context: DraftContext) -> tuple[dict[str, str], dict[str, bool]]: ...


def save_restricted_capability_explanations(
    product: ProductInput,
    context: DraftContext,
    port: RestrictedCapabilitySubmissionPort,
) -> list[str]:
    """Write only confirmed, SHA-bound explanations and prove persistence after Save."""

    manifest_capabilities=restricted_capabilities_from_package(product.package_path)
    if not manifest_capabilities:
        return []
    partner_capabilities=port.read_partner_capabilities(product,context)
    if not exact_capability_match(manifest_capabilities,partner_capabilities):
        raise LiveGateError("RESTRICTED_CAPABILITY_EXACT_MATCH_REQUIRED")
    package_sha=file_sha256(product.package_path)
    for capability in manifest_capabilities:
        explanation=product.restricted_capability_justifications.get(capability)
        if not explanation or not explanation.text.strip():
            raise LiveGateError(f"RESTRICTED_CAPABILITY_JUSTIFICATION_REQUIRED: {capability}")
        if not explanation.confirmed or explanation.package_sha256.casefold()!=package_sha.casefold():
            raise LiveGateError(f"RESTRICTED_CAPABILITY_CONFIRMATION_REQUIRED: {capability}")
        port.fill_capability_explanation(capability,explanation.text)
    redirected_url=port.save_submission_options(context)
    overview_state=port.read_submission_options_overview_state(product,context)
    reloaded,dirty=port.reload_capability_explanations(product,context)
    for capability in manifest_capabilities:
        explanation=product.restricted_capability_justifications[capability]
        if not submission_options_save_succeeded(
            draft_url=context.draft_url,
            redirected_url=redirected_url,
            overview_state=overview_state,
            expected_text=explanation.text,
            reloaded_text=reloaded.get(capability,""),
            textarea_dirty=dirty.get(capability,True),
        ):
            raise AmbiguousWriteError(f"restricted capability explanation Save is unproven: {capability}")
        product.restricted_capability_explanation_saved[capability]=True
    return [
        *[f"submission_options:restricted_capability:{capability}:filled_exact_match" for capability in manifest_capabilities],
        "submission_options:saved",
        "submission_options:reload_verified",
    ]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _manifest_identity(raw: bytes) -> PackageIdentity:
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise LiveGateError("MSIX AppxManifest.xml is not valid XML") from exc
    identities = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "Identity"]
    if len(identities) != 1:
        raise LiveGateError("MSIX manifest must contain exactly one Identity")
    identity = identities[0]
    values = [identity.attrib.get(key, "").strip() for key in ("Name", "Publisher", "Version")]
    if any(not value for value in values):
        raise LiveGateError("MSIX manifest Identity is missing Name, Publisher, or Version")
    return PackageIdentity(*values)


def _identities_from_zip(raw: bytes | Path, depth: int = 0) -> list[PackageIdentity]:
    if depth > 3:
        raise LiveGateError("package nesting is deeper than the supported MSIX upload structure")
    try:
        archive = zipfile.ZipFile(raw)
    except (zipfile.BadZipFile, OSError) as exc:
        raise LiveGateError("package is not a readable MSIX/MSIXUPLOAD archive") from exc
    with archive:
        names = archive.namelist()
        manifests = [name for name in names if name.replace("\\", "/").casefold().endswith("appxmanifest.xml")]
        if manifests:
            if len(manifests) != 1:
                raise LiveGateError("package archive contains multiple AppxManifest.xml files")
            return [_manifest_identity(archive.read(manifests[0]))]
        nested = [
            name for name in names
            if Path(name).suffix.casefold() in {".msix", ".appx", ".msixbundle", ".appxbundle"}
        ]
        identities: list[PackageIdentity] = []
        for name in nested:
            identities.extend(_identities_from_zip(BytesIO(archive.read(name)), depth + 1))
        if not identities:
            raise LiveGateError("package archive does not contain an AppxManifest.xml")
        return identities


def read_package_identity(path: str | Path) -> PackageIdentity:
    identities = _identities_from_zip(Path(path))
    unique = set(identities)
    if len(unique) != 1:
        raise LiveGateError("bundled packages do not share one exact Name/Publisher/Version identity")
    return next(iter(unique))


def validate_live_gate(product: ProductInput) -> None:
    template = route_template(product.submission_route or default_route_for_product_type(product.product_type), product.product_type)
    product.submission_route = template.route_id
    if template.route_id != "msix_pwa_app" or not template.live_write_supported:
        raise LiveGateError(
            f"LIVE_ROUTE_NOT_VERIFIED: live Partner Center write is not verified for route {template.partner_center_label}; "
            "use dry run until a dedicated live mapping is observed"
        )
    if product.submission_route_source == "upstream":
        missing_handoff = [name for name in ("package_type", "package_sha256") if not str(getattr(product, name, "") or "").strip()]
        if missing_handoff:
            raise LiveGateError("UPSTREAM_HANDOFF_INCOMPLETE: " + ", ".join(missing_handoff))
    missing = []
    for field_name in (
        "store_product_id",
        "source_sha",
        "source_branch",
        "identity_name",
        "identity_publisher",
        "package_version",
    ):
        if not str(getattr(product, field_name, "") or "").strip():
            missing.append(field_name)
    if missing:
        raise LiveGateError("live evidence missing: " + ", ".join(missing))
    if not HEX40.fullmatch(product.source_sha):
        raise LiveGateError("source_sha must be an exact 40-character Git SHA")
    if not VERSION4.fullmatch(product.package_version):
        raise LiveGateError("package_version must be a four-part MSIX version")
    if product.checker_status != "READY_CANDIDATE_NOT_CERTIFIED":
        raise LiveGateError("Windows-checker did not return READY_CANDIDATE_NOT_CERTIFIED")
    if product.human_local_qa_pass is not True:
        raise LiveGateError("human local quick QA is not PASS")
    if not product.package_path or not Path(product.package_path).is_file():
        raise LiveGateError("local package is not present")
    package_sha = file_sha256(product.package_path)
    immutable_sha = str(product.package_sha256 or "")
    if immutable_sha and package_sha.lower() != immutable_sha.lower():
        raise LiveGateError("PACKAGE_SHA_MISMATCH: local package does not match immutable upstream package_sha256")
    if package_sha != product.security_package_sha256:
        raise LiveGateError("package SHA does not match the security-confirmed package")
    for capability in restricted_capabilities_from_package(product.package_path):
        explanation=product.restricted_capability_justifications.get(capability)
        if not explanation or not explanation.text.strip():
            raise LiveGateError(f"RESTRICTED_CAPABILITY_JUSTIFICATION_REQUIRED: {capability}")
        if not explanation.confirmed:
            raise LiveGateError(f"RESTRICTED_CAPABILITY_CONFIRMATION_REQUIRED: {capability}")
        if explanation.package_sha256.casefold()!=package_sha.casefold():
            raise LiveGateError(f"RESTRICTED_CAPABILITY_PACKAGE_CHANGED: {capability}")
    package_identity = read_package_identity(product.package_path)
    expected_identity = PackageIdentity(
        product.identity_name,
        product.identity_publisher,
        product.package_version,
    )
    if package_identity != expected_identity:
        raise LiveGateError("local package Identity/Publisher/Version does not match the immutable handoff")


class LiveDraftWorkflow:
    """Orchestrates one package write and proves it before claiming DRAFT_SAVED.

    This workflow has no certification or publication operation.  It treats a
    timeout after upload/save as UNKNOWN through AmbiguousWriteError so the
    queue cannot resend the same package automatically.
    """

    def __init__(self, port: PartnerCenterPort):
        self.port = port

    def __call__(self, product: ProductInput) -> UploadOutcome:
        validate_live_gate(product)
        self.port.ensure_route_ready(product)
        template = route_template(product.submission_route, product.product_type)
        package_sha = file_sha256(product.package_path)
        context = self.port.verify_product_and_draft(product)
        actions = [
            f"product:verified:{context.product_id}",
            f"draft:verified:{context.draft_id}",
            f"packages:upload:{product.package_path}",
        ]
        started_at = utc_now()
        state = self.port.upload_package(product, context)
        upload_completed_at = utc_now()
        if state.validation == "ERROR":
            raise PackageValidationError(state.error or "Microsoft package validation failed")
        if state.validation == "WARNING":
            detail = state.warning or "Microsoft package validation returned WARNING"
            warning_code, capabilities = classify_package_warning(detail)
            capability_detail = f" ({', '.join(capabilities)})" if capabilities else ""
            raise LiveGateError(f"{warning_code}{capability_detail}: {detail}; manual review is required")
        if state.validation != "VALID":
            raise AmbiguousWriteError(f"package validation is {state.validation}")
        if state.section_completion != "COMPLETE":
            raise LiveGateError(f"Packages section is {state.section_completion}")
        self.port.save_packages(product, context)
        actions.append("packages:save_draft")
        verified = self.port.reload_and_verify_package(product, context)
        if verified.validation != "VALID" or verified.section_completion != "COMPLETE":
            raise AmbiguousWriteError("saved package could not be proven VALID/COMPLETE after reload")
        sections = self.port.verify_required_sections(product, context)
        if tuple(sections) != template.required_sections:
            raise LiveGateError("required section evidence is incomplete or out of order")
        incomplete = [name for name, status in sections.items() if status not in {"SAVED", "NOT_REQUIRED"}]
        if incomplete:
            raise LiveGateError("required Store sections are not saved: " + ", ".join(incomplete))
        evidence = self.port.capture_evidence(product, context)
        if not evidence:
            raise AmbiguousWriteError("draft evidence capture is empty")
        completed_at = utc_now()
        details: dict[str, Any] = {
            "execution_mode": "live",
            "draft_saved": True,
            "save_verified_after_reload": True,
            "package_uploaded": True,
            "package_validation": verified.validation,
            "package_section_completion": verified.section_completion,
            "package_warning": verified.warning,
            "package_error": verified.error,
            "draft_id": context.draft_id,
            "product_id": context.product_id,
            "package_path": str(Path(product.package_path).resolve()),
            "package_filename": Path(product.package_path).name,
            "package_sha256": package_sha,
            "source_sha": product.source_sha.lower(),
            "source_branch": product.source_branch,
            "submission_route": product.submission_route,
            "submission_route_source": product.submission_route_source,
            "package_type": product.package_type or Path(product.package_path).suffix.lstrip(".").lower(),
            "immutable_package_sha256": product.package_sha256 or package_sha,
            "live_adapter": template.live_adapter,
            "required_sections": list(template.required_sections),
            "identity": {
                "name": product.identity_name,
                "publisher": product.identity_publisher,
                "version": product.package_version,
            },
            "sections": sections,
            "current_draft_url": context.draft_url,
            "upload_started_at_utc": started_at,
            "upload_completed_at_utc": upload_completed_at,
            "draft_saved_at_utc": completed_at,
            "evidence": evidence,
            "submitted": False,
            "certified": False,
            "published": False,
        }
        return UploadOutcome("DRAFT_SAVED", actions, details)


class SelectorMap:
    def __init__(self, data: dict[str, Any]):
        if data.get("schema_version") != 3:
            raise LiveGateError("Partner Center selector map schema_version must be 3")
        if not isinstance(data.get("routes"), dict):
            raise LiveGateError("Partner Center selector map routes registry is missing")
        self.data = data
        self.active_route: str | None = None

    def activate(self, route_id: str) -> None:
        route = self.data["routes"].get(route_id)
        if not isinstance(route, dict) or route.get("live_write_supported") is not True:
            raise LiveGateError(f"LIVE_ROUTE_NOT_VERIFIED: selector map is not enabled for {route_id}")
        selectors = route.get("selectors", {})
        missing = []
        for key in REQUIRED_LIVE_SELECTORS:
            value = selectors.get(key)
            if not isinstance(value, dict) or value.get("verified") is not True or not str(value.get("selector") or "").strip():
                missing.append(key)
        if missing:
            raise LiveGateError(
                "Partner Center write mapping is incomplete before upload: " + ", ".join(missing)
            )
        self.active_route = route_id

    @classmethod
    def load(cls, path: str | Path) -> "SelectorMap":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def exact(self, key: str) -> dict[str, Any]:
        if not self.active_route:
            raise LiveGateError("Partner Center selector route was not activated")
        value = self.data["routes"][self.active_route].get("selectors", {}).get(key)
        if not isinstance(value, dict) or value.get("verified") is not True:
            raise LiveGateError(f"selector is not verified: {key}")
        if not value.get("selector"):
            raise LiveGateError(f"selector is empty: {key}")
        return value


class PlaywrightPartnerCenterPort:
    """Playwright implementation for a previously authenticated Partner Center tab.

    Selector/state text comes from a versioned, explicitly verified map.  No
    coordinate, fuzzy text, or certification/publication selector exists here.
    """

    def __init__(self, page: Any, selector_map: SelectorMap, evidence_dir: str | Path, timeout_ms: int = 900_000):
        self.page = page
        self.map = selector_map
        self.evidence_dir = Path(evidence_dir)
        self.timeout_ms = timeout_ms

    def ensure_route_ready(self, product: ProductInput) -> None:
        self.map.activate(product.submission_route)

    def _goto(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        self._assert_authenticated()

    def _assert_authenticated(self) -> None:
        current = str(self.page.url)
        if not current.startswith(PARTNER_HOST):
            raise GlobalAuthError("Partner Center session is no longer authenticated")
        if "login" in current.casefold() or "signin" in current.casefold():
            raise GlobalAuthError("Partner Center login is required")
        if self.page.locator("input[type='password']").count():
            raise GlobalAuthError("Partner Center login is required")

    def _one(self, selector_key: str) -> Any:
        spec = self.map.exact(selector_key)
        strategy = spec.get("strategy", "css")
        if strategy == "css":
            locator = self.page.locator(spec["selector"])
        elif strategy == "role":
            locator = self.page.get_by_role(spec["selector"], name=spec.get("name", ""), exact=True)
        elif strategy == "text":
            locator = self.page.get_by_text(spec["selector"], exact=True)
        else:
            raise LiveGateError(f"unsupported selector strategy: {strategy}")
        if locator.count() != 1:
            raise LiveGateError(f"expected exactly one {selector_key}; got {locator.count()}")
        return locator

    def _exact_text_present(self, text: str) -> None:
        locator = self.page.get_by_text(text, exact=True)
        if locator.count() != 1:
            raise LiveGateError(f"expected exactly one visible text {text!r}; got {locator.count()}")

    def verify_product_and_draft(self, product: ProductInput) -> DraftContext:
        identity_url = f"{PARTNER_HOST}en-us/dashboard/products/{product.store_product_id}/identity"
        self._goto(identity_url)
        self._exact_text_present(product.product_name)
        self._exact_text_present(product.store_product_id)
        self._exact_text_present(product.identity_name)
        self._exact_text_present(product.identity_publisher)

        overview_url = f"{PARTNER_HOST}en-us/dashboard/products/{product.store_product_id}/overview"
        self._goto(overview_url)
        packages_link = self._one("overview_packages_link")
        href = packages_link.get_attribute("href") or ""
        match = re.search(r"/submissions/(\d+)/packages(?:$|[?#])", href)
        if not match:
            raise LiveGateError("an existing draft Packages URL was not found; Start update is not guessed")
        draft_id = match.group(1)
        if product.draft_id and product.draft_id != draft_id:
            raise LiveGateError("draft_id does not match the current Partner Center draft")
        draft_url = f"{PARTNER_HOST}en-us/dashboard/products/{product.store_product_id}/submissions/{draft_id}"
        return DraftContext(product.store_product_id, draft_id, draft_url)

    def _read_package_state(self) -> PackageState:
        validation_spec = self.map.exact("packages_validation_state")
        section_spec = self.map.exact("packages_section_state")
        validation_texts = self.page.locator(validation_spec["selector"]).all_text_contents()
        section_texts = self.page.locator(section_spec["selector"]).all_text_contents()
        validation_map = validation_spec.get("exact_states", {})
        section_map = section_spec.get("exact_states", {})
        validation = normalize_partner_center_state(validation_texts, validation_map)
        section = normalize_partner_center_state(section_texts, section_map)
        warning = "" if validation != "WARNING" else " | ".join(x.strip() for x in validation_texts)
        error = "" if validation != "ERROR" else " | ".join(x.strip() for x in validation_texts)
        return PackageState(validation, section, warning, error)

    def upload_package(self, product: ProductInput, context: DraftContext) -> PackageState:
        packages_url = context.draft_url + "/packages"
        self._goto(packages_url)
        uploader = self._one("packages_file_input")
        uploader.set_input_files(str(Path(product.package_path).resolve()))
        deadline = monotonic() + self.timeout_ms / 1000
        last = PackageState("UNKNOWN", "UNKNOWN")
        while monotonic() < deadline:
            self._assert_authenticated()
            last = self._read_package_state()
            if last.validation in {"VALID", "WARNING", "ERROR"}:
                return last
            self.page.wait_for_timeout(500)
        raise AmbiguousWriteError(f"package validation timed out ({last.validation}/{last.section_completion})")

    def save_packages(self, product: ProductInput, context: DraftContext) -> None:
        save = self._one("packages_save_button")
        if not save.is_enabled():
            raise LiveGateError("Packages Save button is disabled")
        try:
            save.click(timeout=30_000)
            self._assert_authenticated()
            success = self._one("packages_save_success")
            success.wait_for(state="visible", timeout=60_000)
        except GlobalAuthError:
            raise
        except Exception as exc:
            raise AmbiguousWriteError("Packages Save result is unknown") from exc

    def reload_and_verify_package(self, product: ProductInput, context: DraftContext) -> PackageState:
        try:
            self.page.reload(wait_until="domcontentloaded", timeout=60_000)
            self._assert_authenticated()
            filename = Path(product.package_path).name
            self._exact_text_present(filename)
            state = self._read_package_state()
        except GlobalAuthError:
            raise
        except Exception as exc:
            raise AmbiguousWriteError("package could not be verified after reload") from exc
        return state

    def verify_required_sections(self, product: ProductInput, context: DraftContext) -> dict[str, str]:
        self._goto(f"{PARTNER_HOST}en-us/dashboard/products/{product.store_product_id}/overview")
        spec = self.map.exact("overview_section_states")
        states: dict[str, str] = {}
        for section in route_template(product.submission_route, product.product_type).required_sections:
            section_selector = str(spec["selector"]).replace("{section}", section)
            texts = [x.strip() for x in self.page.locator(section_selector).all_text_contents()]
            mapped = [spec.get("exact_states", {}).get(x) for x in texts]
            mapped = [x for x in mapped if x]
            states[section] = mapped[0] if len(mapped) == 1 else "UNKNOWN"
        return states

    def capture_evidence(self, product: ProductInput, context: DraftContext) -> list[dict[str, str]]:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", product.product_name).strip("-") or "product"
        screenshot = self.evidence_dir / f"{name}-{context.draft_id}-{stamp}.png"
        self.page.screenshot(path=str(screenshot), full_page=True)
        sha = hashlib.sha256(screenshot.read_bytes()).hexdigest()
        return [{"kind": "partner_center_draft_screenshot", "path": str(screenshot.resolve()), "sha256": sha, "captured_at_utc": utc_now()}]


class LivePlaywrightConnection:
    def __init__(self, cdp_url: str, selector_map_path: str | Path, evidence_dir: str | Path):
        self.cdp_url = cdp_url
        self.selector_map_path = selector_map_path
        self.evidence_dir = evidence_dir
        self._playwright = None
        self._browser = None

    def __enter__(self) -> PlaywrightPartnerCenterPort:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise LiveGateError("live mode requires the optional 'playwright' dependency") from exc
        selector_map = SelectorMap.load(self.selector_map_path)
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(self.cdp_url)
            pages = [
                page
                for context in self._browser.contexts
                for page in context.pages
                if str(page.url).startswith(PARTNER_HOST)
            ]
            if len(pages) != 1:
                raise LiveGateError(f"expected exactly one authenticated Partner Center tab; got {len(pages)}")
            return PlaywrightPartnerCenterPort(pages[0], selector_map, self.evidence_dir)
        except Exception:
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None
            raise

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._playwright is not None:
            self._playwright.stop()
