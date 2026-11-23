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


EXISTING_PRODUCT_INITIAL_SUBMISSION = "EXISTING_PRODUCT_INITIAL_SUBMISSION"
EXISTING_PRODUCT_DRAFT_PRESENT = "EXISTING_PRODUCT_DRAFT_PRESENT"
EXISTING_PRODUCT_UPDATE_AVAILABLE = "EXISTING_PRODUCT_UPDATE_AVAILABLE"
UNKNOWN_PARTNER_CENTER_STATE = "UNKNOWN_PARTNER_CENTER_STATE"


@dataclass(frozen=True)
class SubmissionStateObservation:
    """Read-only signals from one existing Partner Center product.

    Buttons are evidence only. No caller may infer permission to click Start
    submission or Start update from this observation.
    """

    store_product_id: str
    existing_product_verified: bool
    draft_packages_urls: tuple[str, ...] = ()
    start_submission_visible: bool = False
    start_update_visible: bool = False
    current_packages_page_verified: bool = False
    active_package_count: int | None = None


@dataclass(frozen=True)
class SubmissionStateResult:
    state: str
    required_submission_kind: str = ""
    draft_id: str = ""
    draft_url: str = ""
    hold_code: str = ""


def classify_existing_product_submission_state(
    observation: SubmissionStateObservation,
) -> SubmissionStateResult:
    """Classify an existing product without starting or updating a submission."""

    product_id = observation.store_product_id.strip()
    if not product_id or not observation.existing_product_verified:
        return SubmissionStateResult(
            UNKNOWN_PARTNER_CENTER_STATE,
            hold_code="HOLD_UNKNOWN_SUBMISSION_STATE",
        )

    draft_matches: list[tuple[str, str]] = []
    for url in observation.draft_packages_urls:
        match = re.search(
            rf"/products/{re.escape(product_id)}/submissions/(\d+)/packages(?:$|[?#])",
            url,
        )
        if match:
            draft_id = match.group(1)
            draft_matches.append(
                (
                    draft_id,
                    f"{PARTNER_HOST}en-us/dashboard/products/{product_id}/submissions/{draft_id}",
                )
            )
    if len(observation.draft_packages_urls) == 1 and len(draft_matches) == 1:
        draft_id, draft_url = draft_matches[0]
        return SubmissionStateResult(
            EXISTING_PRODUCT_DRAFT_PRESENT,
            draft_id=draft_id,
            draft_url=draft_url,
        )
    if observation.draft_packages_urls:
        return SubmissionStateResult(
            UNKNOWN_PARTNER_CENTER_STATE,
            hold_code="HOLD_UNKNOWN_SUBMISSION_STATE",
        )

    initial_submission = (
        observation.start_submission_visible
        and not observation.start_update_visible
        and observation.current_packages_page_verified
        and observation.active_package_count == 0
    )
    if initial_submission:
        return SubmissionStateResult(
            EXISTING_PRODUCT_INITIAL_SUBMISSION,
            required_submission_kind="new",
            hold_code="HOLD_INITIAL_SUBMISSION_ROUTE_REQUIRED",
        )

    update_available = (
        observation.start_update_visible
        and not observation.start_submission_visible
        and observation.current_packages_page_verified
        and isinstance(observation.active_package_count, int)
        and observation.active_package_count > 0
    )
    if update_available:
        return SubmissionStateResult(
            EXISTING_PRODUCT_UPDATE_AVAILABLE,
            required_submission_kind="update",
            hold_code="HOLD_UPDATE_SUBMISSION_ROUTE_REQUIRED",
        )

    return SubmissionStateResult(
        UNKNOWN_PARTNER_CENTER_STATE,
        hold_code="HOLD_UNKNOWN_SUBMISSION_STATE",
    )


def reconcile_ambiguous_initial_submission(
    result: SubmissionStateResult,
) -> tuple[str, bool]:
    """Classify the safe next step after an ambiguous Start submission attempt.

    This helper is read-only policy. It never authorizes or performs a retry.
    """
    if result.state == EXISTING_PRODUCT_DRAFT_PRESENT and result.draft_id:
        return "INITIAL_SUBMISSION_DRAFT_PRESENT_RECOVERED", False
    if result.state == EXISTING_PRODUCT_INITIAL_SUBMISSION:
        return "INITIAL_SUBMISSION_NOT_OBSERVED_RETRY_REQUIRES_NEW_APPROVAL", True
    return "HOLD_AMBIGUOUS_WRITE", False


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
class GameRuntimeQaObservation:
    """Sales-blocking runtime evidence required for an MSIX game release."""

    exact_package_source_provenance: bool = False
    clean_launch: bool = False
    start: bool = False
    gameplay_progress: bool = False
    major_controls: bool = False
    save: bool = False
    relaunch: bool = False
    restore: bool = False
    continue_gameplay: bool = False
    normal_exit: bool = False
    store_listing_matches_runtime: bool = False
    blocking_defect: bool = False
    runtime_policy_blocked: bool = False
    package_bytes_changed: bool = False
    legacy_save_source: str = "none"
    legacy_save_compatible: bool | None = None


def game_runtime_qa_next_state(observation: GameRuntimeQaObservation) -> str:
    """Require functional state transitions, not DOM handlers or static tests."""

    if observation.package_bytes_changed or observation.blocking_defect:
        return "PACKAGE_REPLACEMENT_REQUIRED"
    if observation.legacy_save_source not in {
        "none",
        "development_qa",
        "public_release",
    }:
        return "HOLD_LEGACY_SAVE_SOURCE_UNKNOWN"
    if (
        observation.legacy_save_source == "public_release"
        and observation.legacy_save_compatible is not True
    ):
        return "PACKAGE_REPLACEMENT_REQUIRED"
    if observation.runtime_policy_blocked:
        return "RUNTIME_QA_REQUIRED_POLICY_BLOCK"
    required = (
        observation.exact_package_source_provenance,
        observation.clean_launch,
        observation.start,
        observation.gameplay_progress,
        observation.major_controls,
        observation.save,
        observation.relaunch,
        observation.restore,
        observation.continue_gameplay,
        observation.normal_exit,
        observation.store_listing_matches_runtime,
    )
    if not all(required):
        return "RUNTIME_QA_REQUIRED"
    return "RUNTIME_FUNCTIONAL_QA_PASS"


def game_certification_review_state(
    *,
    draft_state: str,
    runtime_qa_state: str,
    package_decision: str,
    certification_executed: bool,
    publish_executed: bool,
) -> str:
    """Keep games behind runtime QA while leaving the app route unchanged."""

    if certification_executed or publish_executed:
        return "HOLD_PROHIBITED_ACTION_EXECUTED"
    if draft_state != "STORE_DRAFT_COMPLETE":
        return draft_state
    if runtime_qa_state == "PACKAGE_REPLACEMENT_REQUIRED":
        return runtime_qa_state
    if runtime_qa_state != "RUNTIME_FUNCTIONAL_QA_PASS":
        return runtime_qa_state
    if package_decision != "PACKAGE_KEEP":
        return "PACKAGE_DECISION_REQUIRED"
    return "READY_FOR_CERTIFICATION_REVIEW"


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
    def inspect_existing_product_submission_state(self, product: ProductInput) -> SubmissionStateResult: ...
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
        normalized_text=normalize_explanation_text(explanation.text)
        if len(normalized_text)>500:
            raise LiveGateError(f"RESTRICTED_CAPABILITY_JUSTIFICATION_TOO_LONG: {capability}")
        if not explanation.confirmed or explanation.package_sha256.casefold()!=package_sha.casefold():
            raise LiveGateError(f"RESTRICTED_CAPABILITY_CONFIRMATION_REQUIRED: {capability}")
        port.fill_capability_explanation(capability,normalized_text)
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


def accepted_package_validation(product: ProductInput, state: PackageState) -> str:
    """Accept VALID or the one exact, already owner-confirmed runFullTrust warning.

    validate_live_gate() has already required every manifest restricted capability
    explanation to be confirmed and bound to this exact package SHA.  No other
    warning is promoted.
    """

    if state.validation == "ERROR":
        raise PackageValidationError(state.error or "Microsoft package validation failed")
    if state.validation == "VALID":
        return "VALID"
    if state.validation == "WARNING":
        detail = state.warning or "Microsoft package validation returned WARNING"
        warning_code, capabilities = classify_package_warning(detail)
        manifest_capabilities = restricted_capabilities_from_package(product.package_path)
        if (
            warning_code == "RESTRICTED_CAPABILITY_REVIEW_REQUIRED"
            and capabilities == ("runFullTrust",)
            and manifest_capabilities == capabilities
        ):
            explanation = product.restricted_capability_justifications.get("runFullTrust")
            package_sha = file_sha256(product.package_path)
            if (
                explanation
                and explanation.confirmed
                and explanation.text.strip()
                and explanation.package_sha256.casefold() == package_sha.casefold()
            ):
                return "KNOWN_RUNFULLTRUST_WARNING_ACCEPTED"
        capability_detail = f" ({', '.join(capabilities)})" if capabilities else ""
        raise LiveGateError(
            f"{warning_code}{capability_detail}: {detail}; manual review is required"
        )
    raise AmbiguousWriteError(f"package validation is {state.validation}")


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
        upload_validation = accepted_package_validation(product, state)
        if upload_validation == "KNOWN_RUNFULLTRUST_WARNING_ACCEPTED":
            actions.append("packages:known_warning_accepted:runFullTrust")
        if state.section_completion != "COMPLETE":
            raise LiveGateError(f"Packages section is {state.section_completion}")
        self.port.save_packages(product, context)
        actions.append("packages:save_draft")
        verified = self.port.reload_and_verify_package(product, context)
        reload_validation = accepted_package_validation(product, verified)
        if reload_validation == "KNOWN_RUNFULLTRUST_WARNING_ACCEPTED":
            actions.append("packages:reload_known_warning_verified:runFullTrust")
        if verified.section_completion != "COMPLETE":
            raise AmbiguousWriteError("saved package could not be proven Complete after reload")
        sections = self.port.verify_required_sections(product, context)
        if tuple(sections) != template.required_sections:
            raise LiveGateError("required section evidence is incomplete or out of order")
        incomplete = [name for name, status in sections.items() if status not in {"SAVED", "NOT_REQUIRED"}]
        if incomplete:
            actions.append("draft:remaining_sections:" + ",".join(incomplete))
        evidence = self.port.capture_evidence(product, context)
        if not evidence:
            raise AmbiguousWriteError("draft evidence capture is empty")
        completed_at = utc_now()
        details: dict[str, Any] = {
            "execution_mode": "live",
            "draft_saved": not incomplete,
            "draft_complete": not incomplete,
            "package_saved": True,
            "save_verified_after_reload": True,
            "package_uploaded": True,
            "package_validation": verified.validation,
            "package_validation_classification": reload_validation,
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
            "remaining_sections": incomplete,
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
        status = (
            "DRAFT_SAVED"
            if not incomplete
            else "PACKAGE_SAVED_STORE_DRAFT_REMAINING_SECTIONS_REQUIRED"
        )
        return UploadOutcome(status, actions, details)


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
        self.last_submission_probe: dict[str, Any] = {}
        self.last_navigation: dict[str, Any] = {}

    def ensure_route_ready(self, product: ProductInput) -> None:
        self.map.activate(product.submission_route)

    def _goto(self, url: str) -> None:
        response = self.page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        self._assert_authenticated()
        try:
            self.page.wait_for_load_state("load", timeout=15_000)
        except Exception:
            pass
        # Partner Center is a SPA; domcontentloaded can fire before identity
        # fields are hydrated. Exact-value helpers below still fail closed.
        wait = getattr(self.page, "wait_for_timeout", None)
        if callable(wait):
            wait(500)
        try:
            title = str(self.page.title() or "")
        except Exception:
            title = ""
        self.last_navigation = {
            "requested_url": url,
            "observed_url": str(self.page.url),
            "http_status": getattr(response, "status", None),
            "title": title,
        }

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

    def _exact_text_present(self, text: str, timeout_ms: int = 15_000) -> None:
        deadline = monotonic() + timeout_ms / 1000
        while monotonic() < deadline:
            visible = self._visible_exact_text_count(text)
            if visible >= 1:
                return

            # Partner Center renders some identity values inside readonly form
            # controls or asynchronously into the page body. Accept only the
            # exact expected value, never fuzzy matching.
            for selector in ("input", "textarea"):
                locator = self.page.locator(selector)
                all_nodes = getattr(locator, "all", None)
                nodes = all_nodes() if callable(all_nodes) else ()
                for node in nodes:
                    try:
                        value = node.input_value()
                    except Exception:
                        continue
                    if value == text:
                        return

            try:
                body_text = self.page.locator("body").inner_text()
            except Exception:
                body_text = ""
            lines = {line.strip() for line in body_text.splitlines() if line.strip()}
            if text in lines:
                return

            wait = getattr(self.page, "wait_for_timeout", None)
            if callable(wait):
                wait(250)

        raise LiveGateError(
            f"expected exact Partner Center value {text!r}; not observed within {timeout_ms}ms"
        )

    def _verify_identity_page_context(self, product_name: str, store_product_id: str) -> None:
        if not product_name.strip():
            raise LiveGateError("existing identity verifier requires product_name")
        if not store_product_id.strip():
            raise LiveGateError("existing identity verifier requires store_product_id")
        current = str(self.page.url)
        expected_path = f"/products/{store_product_id}/identity"
        if expected_path not in current:
            raise LiveGateError(
                f"HOLD_STORE_ID_URL_MISMATCH expected_path={expected_path!r} observed={current!r}"
            )
        # Partner Center may expose only the generic browser title "Partner Center"
        # while the SPA is still fully loaded. Product identity is therefore bound
        # to the exact Store ID in the URL plus exact identity fields below, not
        # to the volatile document.title value.

    def _visible_exact_text_count(self, text: str) -> int:
        locator = self.page.get_by_text(text, exact=True)
        all_items = getattr(locator, "all", None)
        if callable(all_items):
            return sum(1 for item in all_items() if item.is_visible())
        count = locator.count()
        if count < 1:
            return 0
        visible = getattr(locator, "is_visible", None)
        return 1 if callable(visible) and visible() else count

    def _visible_locator_count(self, selector: str) -> int:
        return sum(1 for item in self.page.locator(selector).all() if item.is_visible())

    def verify_existing_identity_values(
        self,
        *,
        product_name: str,
        store_product_id: str,
        identity_name: str,
        identity_publisher: str,
        package_family_name: str = "",
        package_sid: str = "",
    ) -> dict[str, object]:
        """Read-only exact-match verification of an existing Partner Center identity.

        This never creates/reserves a product, starts a submission, uploads a
        package, changes pricing, submits certification, or publishes.
        """
        identity_url = f"{PARTNER_HOST}en-us/dashboard/products/{store_product_id}/identity"
        self._goto(identity_url)
        self._verify_identity_page_context(product_name, store_product_id)
        required = (
            ("identity_name", identity_name),
            ("identity_publisher", identity_publisher),
        )
        optional = (
            ("package_family_name", package_family_name),
            ("package_sid", package_sid),
        )
        matched: list[str] = ["product_name", "store_product_id"]
        for key, value in required:
            if not str(value or "").strip():
                raise LiveGateError(f"existing identity verifier requires {key}")
            self._exact_text_present(str(value))
            matched.append(key)
        for key, value in optional:
            if str(value or "").strip():
                self._exact_text_present(str(value))
                matched.append(key)
        return {
            "status": "EXISTING_IDENTITY_EXACT_MATCH",
            "partner_center_reverified": True,
            "identity_url": identity_url,
            "matched_fields": matched,
            "store_product_id": store_product_id,
            "product_name": product_name,
            "identity_name": identity_name,
            "identity_publisher": identity_publisher,
            "package_family_name": package_family_name,
            "package_sid": package_sid,
        }

    def inspect_existing_product_submission_state(self, product: ProductInput) -> SubmissionStateResult:
        """Read one existing product state without clicking any Start control."""

        identity_url = f"{PARTNER_HOST}en-us/dashboard/products/{product.store_product_id}/identity"
        self._goto(identity_url)
        self._verify_identity_page_context(product.product_name, product.store_product_id)
        self._exact_text_present(product.identity_name)
        self._exact_text_present(product.identity_publisher)

        # If an exact draft_id is already pinned by upstream evidence, probe that
        # draft directly with a read-only GET before relying on overview link
        # discovery. Partner Center may not render a packages link on overview
        # even though the existing draft is valid.
        self.last_submission_probe = {
            "pinned_draft_id": str(product.draft_id or "").strip(),
            "product_type": product.product_type,
        }
        if str(product.draft_id or "").strip():
            expected_draft_id = str(product.draft_id).strip()
            known_packages_url = (
                f"{PARTNER_HOST}en-us/dashboard/products/{product.store_product_id}/"
                f"submissions/{expected_draft_id}/packages"
            )
            self._goto(known_packages_url)
            current = str(self.page.url)
            observed_title = str(self.last_navigation.get("title") or "")
            packages_http_status = self.last_navigation.get("http_status")
            exact_path = (
                f"/products/{product.store_product_id}/submissions/"
                f"{expected_draft_id}/packages"
            )
            exact_url_retained = exact_path in current
            packages_label_count = self._visible_exact_text_count("Packages")
            file_input_count = self.page.locator('input[type="file"]').count()
            try:
                body_text = self.page.locator("body").inner_text()
            except Exception:
                body_text = ""
            error_markers = (
                "Page not found",
                "Something went wrong",
                "We couldn't find",
                "We can’t find",
                "doesn't exist",
                "does not exist",
            )
            error_marker = next(
                (marker for marker in error_markers if marker.casefold() in body_text.casefold()),
                "",
            )
            packages_title_signal = "packages" in observed_title.casefold()
            packages_signal = (
                packages_label_count >= 1
                or file_input_count >= 1
                or packages_title_signal
            )

            draft_root_url = (
                f"{PARTNER_HOST}en-us/dashboard/products/{product.store_product_id}/"
                f"submissions/{expected_draft_id}"
            )
            self._goto(draft_root_url)
            root_observed_url = str(self.page.url)
            root_title = str(self.last_navigation.get("title") or "")
            root_http_status = self.last_navigation.get("http_status")
            try:
                root_body = self.page.locator("body").inner_text()
            except Exception:
                root_body = ""
            root_error_marker = next(
                (marker for marker in error_markers if marker.casefold() in root_body.casefold()),
                "",
            )
            section_labels = (
                "Pricing and availability",
                "Properties",
                "Age ratings",
                "Packages",
                "Store listings",
                "Submission options",
            )
            visible_sections = tuple(
                label for label in section_labels
                if self._visible_exact_text_count(label) >= 1
            )
            submission_links = tuple(
                href
                for link in self.page.locator("a[href]").all()
                if (href := (link.get_attribute("href") or "").strip())
                and f"/products/{product.store_product_id}/submissions/{expected_draft_id}/" in href
            )
            root_exact_path = (
                f"/products/{product.store_product_id}/submissions/{expected_draft_id}"
            )
            root_url_retained = root_exact_path in root_observed_url
            root_signal = (
                len(visible_sections) >= 2
                or len(submission_links) >= 1
            )

            self.last_submission_probe.update({
                "pinned_draft_requested_url": known_packages_url,
                "pinned_draft_observed_url": current,
                "pinned_draft_observed_title": observed_title,
                "pinned_draft_http_status": packages_http_status,
                "pinned_draft_exact_url_retained": exact_url_retained,
                "pinned_draft_packages_label_count": packages_label_count,
                "pinned_draft_file_input_count": file_input_count,
                "pinned_draft_packages_title_signal": packages_title_signal,
                "pinned_draft_error_marker": error_marker,
                "pinned_draft_packages_signal": packages_signal,
                "pinned_draft_root_requested_url": draft_root_url,
                "pinned_draft_root_observed_url": root_observed_url,
                "pinned_draft_root_observed_title": root_title,
                "pinned_draft_root_http_status": root_http_status,
                "pinned_draft_root_url_retained": root_url_retained,
                "pinned_draft_root_visible_sections": list(visible_sections),
                "pinned_draft_root_submission_link_count": len(submission_links),
                "pinned_draft_root_error_marker": root_error_marker,
                "pinned_draft_root_signal": root_signal,
            })
            if (
                not error_marker
                and not root_error_marker
                and (
                    (exact_url_retained and packages_signal)
                    or (root_url_retained and root_signal)
                )
            ):
                self.last_submission_probe["classification_source"] = "PINNED_DRAFT_DIRECT_READONLY"
                self.last_submission_probe["classified_state"] = EXISTING_PRODUCT_DRAFT_PRESENT
                return SubmissionStateResult(
                    EXISTING_PRODUCT_DRAFT_PRESENT,
                    draft_id=expected_draft_id,
                    draft_url=(
                        f"{PARTNER_HOST}en-us/dashboard/products/"
                        f"{product.store_product_id}/submissions/{expected_draft_id}"
                    ),
                )

        if product.product_type == "app":
            overview_url = f"{PARTNER_HOST}en-us/dashboard/apps/{product.store_product_id}/overview"
        else:
            overview_url = f"{PARTNER_HOST}en-us/dashboard/products/{product.store_product_id}/overview"
        self._goto(overview_url)
        self.last_submission_probe["overview_requested_url"] = overview_url
        self.last_submission_probe["overview_observed_url"] = str(self.page.url)
        draft_packages_urls = tuple(
            href
            for link in self.page.locator("a[href]").all()
            if (href := (link.get_attribute("href") or "").strip())
            and re.search(
                rf"/products/{re.escape(product.store_product_id)}/submissions/\d+/packages(?:$|[?#])",
                href,
            )
        )
        start_submission_visible = self._visible_exact_text_count("Start submission") == 1
        start_update_visible = self._visible_exact_text_count("Start update") == 1
        self.last_submission_probe.update({
            "overview_draft_packages_url_count": len(draft_packages_urls),
            "start_submission_visible": start_submission_visible,
            "start_update_visible": start_update_visible,
        })

        current_packages_url = f"{PARTNER_HOST}en-us/dashboard/apps/{product.store_product_id}/managepackages"
        self._goto(current_packages_url)
        current_packages_page_verified = (
            self._visible_exact_text_count("Your active packages are listed below.") == 1
        )
        active_package_count = None
        if current_packages_page_verified:
            active_package_count = self._visible_locator_count("table tbody tr")
        self.last_submission_probe.update({
            "current_packages_requested_url": current_packages_url,
            "current_packages_observed_url": str(self.page.url),
            "current_packages_page_verified": current_packages_page_verified,
            "active_package_count": active_package_count,
        })

        observation = SubmissionStateObservation(
            store_product_id=product.store_product_id,
            existing_product_verified=True,
            draft_packages_urls=draft_packages_urls,
            start_submission_visible=start_submission_visible,
            start_update_visible=start_update_visible,
            current_packages_page_verified=current_packages_page_verified,
            active_package_count=active_package_count,
        )
        result = classify_existing_product_submission_state(observation)
        self.last_submission_probe["classification_source"] = "OVERVIEW_AND_CURRENT_PACKAGES"
        self.last_submission_probe["classified_state"] = result.state
        return result

    def start_initial_submission_draft(self, product: ProductInput) -> DraftContext:
        """Create only the first draft for an already-reserved Store product.

        Preconditions are re-read immediately before the click. This method does
        not upload a package, edit pricing, submit certification, or publish.
        """
        if product.submission_kind != "new":
            raise LiveGateError("initial submission start requires submission_kind=new")
        before = self.inspect_existing_product_submission_state(product)
        if before.state != EXISTING_PRODUCT_INITIAL_SUBMISSION:
            raise LiveGateError(
                f"HOLD_INITIAL_SUBMISSION_STATE_CHANGED: expected {EXISTING_PRODUCT_INITIAL_SUBMISSION}, got {before.state}"
            )
        button = self.page.get_by_text("Start submission", exact=True)
        if button.count() != 1 or not button.is_visible():
            raise LiveGateError("expected exactly one visible Start submission control")
        try:
            button.click(timeout=30_000)
            self._assert_authenticated()
            self.page.wait_for_timeout(1000)
        except GlobalAuthError:
            raise
        except Exception as exc:
            raise AmbiguousWriteError("Start submission result is unknown") from exc

        after = self.inspect_existing_product_submission_state(product)
        if after.state != EXISTING_PRODUCT_DRAFT_PRESENT or not after.draft_id:
            raise AmbiguousWriteError(
                f"Start submission may have changed Partner Center but draft could not be reconciled ({after.state})"
            )
        return DraftContext(product.store_product_id, after.draft_id, after.draft_url)

    def verify_product_and_draft(self, product: ProductInput) -> DraftContext:
        result = self.inspect_existing_product_submission_state(product)
        if result.state == EXISTING_PRODUCT_INITIAL_SUBMISSION:
            raise LiveGateError(
                "HOLD_INITIAL_SUBMISSION_ROUTE_REQUIRED: existing product has no active package or draft; "
                "submission_kind must be new and Start submission is never clicked automatically"
            )
        if result.state == EXISTING_PRODUCT_UPDATE_AVAILABLE:
            raise LiveGateError(
                "HOLD_UPDATE_SUBMISSION_ROUTE_REQUIRED: Start update is available but is never clicked automatically"
            )
        if result.state != EXISTING_PRODUCT_DRAFT_PRESENT:
            raise LiveGateError("HOLD_UNKNOWN_SUBMISSION_STATE: Partner Center state is not an exact supported state")
        if product.draft_id and product.draft_id != result.draft_id:
            raise LiveGateError("draft_id does not match the current Partner Center draft")
        return DraftContext(product.store_product_id, result.draft_id, result.draft_url)

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
