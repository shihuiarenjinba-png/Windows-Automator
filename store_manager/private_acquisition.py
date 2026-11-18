from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ZERO_COST_PROMO_EXISTING = "ZERO_COST_ROUTE_PROMO_CODE_EXISTING"
ZERO_COST_FREE_TRIAL = "ZERO_COST_ROUTE_FREE_TRIAL"
ZERO_COST_PRIVATE_FREE = "ZERO_COST_ROUTE_PRIVATE_FREE"
PROMO_GENERATION_APPROVAL = "PROMO_CODE_GENERATION_REQUIRES_APPROVAL"
TEMP_FREE_APPROVAL = "TEMPORARY_FREE_PRIVATE_BETA_REQUIRES_APPROVAL"
STORE_SIGNED_PRIVATE_PUBLISH_REQUIRED = "STORE_SIGNED_PRIVATE_PUBLISH_REQUIRED"
HOLD_PAID_CHECKOUT = "HOLD_ZERO_COST_ACQUISITION_PAID_CHECKOUT"
HOLD_PRIVATE_AUDIENCE = "HOLD_PRIVATE_AUDIENCE_NOT_PROVEN"
HOLD_ZERO_COST_ROUTE = "HOLD_ZERO_COST_ROUTE_UNPROVEN"
HOLD_CONFLICTING = "HOLD_CONFLICTING_ACQUISITION_EVIDENCE"


@dataclass(frozen=True)
class PrivateAcquisitionObservation:
    """Read-only Store acquisition evidence for one already-frozen product.

    This object never authorizes Partner Center writes. It only classifies which
    zero-cost acquisition route, if any, has been proven from live observations.
    """

    private_audience_configured: bool | None = None
    test_account_in_private_audience: bool | None = None
    store_signed_private_build_published: bool | None = None
    current_price_is_free: bool | None = None
    free_trial_visible: bool | None = None
    free_trial_zero_cost_confirmed: bool | None = None
    existing_unredeemed_promo_code_available: bool | None = None
    promo_code_generation_available: bool | None = None
    temporary_free_change_available: bool | None = None
    paid_checkout_required: bool | None = None


@dataclass(frozen=True)
class PrivateAcquisitionDecision:
    state: str
    acquisition_route: Literal[
        "promo_code_existing",
        "free_trial",
        "private_free",
        "promo_code_generate",
        "temporary_free_private_beta",
        "none",
    ] = "none"
    write_required: bool = False
    owner_approval_required: bool = False
    acquisition_allowed_now: bool = False


def classify_private_acquisition(
    observation: PrivateAcquisitionObservation,
) -> PrivateAcquisitionDecision:
    """Fail-closed zero-cost Store acquisition classification.

    Priority intentionally avoids owner self-payment:
    existing promo code -> already-configured zero-cost trial -> already-free private
    build -> promo-code generation approval -> temporary-free approval -> HOLD.
    """

    if (
        observation.private_audience_configured is False
        or observation.test_account_in_private_audience is False
    ):
        return PrivateAcquisitionDecision(HOLD_PRIVATE_AUDIENCE)

    if observation.store_signed_private_build_published is not True:
        return PrivateAcquisitionDecision(
            STORE_SIGNED_PRIVATE_PUBLISH_REQUIRED,
            write_required=True,
            owner_approval_required=True,
        )

    zero_cost_positive = any(
        value is True
        for value in (
            observation.existing_unredeemed_promo_code_available,
            observation.free_trial_zero_cost_confirmed,
            observation.current_price_is_free,
        )
    )
    if observation.paid_checkout_required is True and zero_cost_positive:
        return PrivateAcquisitionDecision(HOLD_CONFLICTING)

    if observation.existing_unredeemed_promo_code_available is True:
        return PrivateAcquisitionDecision(
            ZERO_COST_PROMO_EXISTING,
            acquisition_route="promo_code_existing",
            acquisition_allowed_now=True,
        )

    if (
        observation.free_trial_visible is True
        and observation.free_trial_zero_cost_confirmed is True
    ):
        return PrivateAcquisitionDecision(
            ZERO_COST_FREE_TRIAL,
            acquisition_route="free_trial",
            acquisition_allowed_now=True,
        )

    if observation.current_price_is_free is True:
        return PrivateAcquisitionDecision(
            ZERO_COST_PRIVATE_FREE,
            acquisition_route="private_free",
            acquisition_allowed_now=True,
        )

    if observation.promo_code_generation_available is True:
        return PrivateAcquisitionDecision(
            PROMO_GENERATION_APPROVAL,
            acquisition_route="promo_code_generate",
            write_required=True,
            owner_approval_required=True,
        )

    if observation.temporary_free_change_available is True:
        return PrivateAcquisitionDecision(
            TEMP_FREE_APPROVAL,
            acquisition_route="temporary_free_private_beta",
            write_required=True,
            owner_approval_required=True,
        )

    if observation.paid_checkout_required is True:
        return PrivateAcquisitionDecision(HOLD_PAID_CHECKOUT)

    return PrivateAcquisitionDecision(HOLD_ZERO_COST_ROUTE)
