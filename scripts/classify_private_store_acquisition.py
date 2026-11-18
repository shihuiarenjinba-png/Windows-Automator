from __future__ import annotations

import argparse
import json
from pathlib import Path

from store_manager.private_acquisition import (
    PrivateAcquisitionObservation,
    classify_private_acquisition,
)


FIELDS = (
    "private_audience_configured",
    "test_account_in_private_audience",
    "store_signed_private_build_published",
    "current_price_is_free",
    "free_trial_visible",
    "free_trial_zero_cost_confirmed",
    "existing_unredeemed_promo_code_available",
    "promo_code_generation_available",
    "temporary_free_change_available",
    "paid_checkout_required",
)


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("observation must be a JSON object")
    return value


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--observation", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()

    if a.output.exists() or a.output.is_symlink():
        raise SystemExit("refusing to overwrite existing acquisition decision evidence")

    raw = load(a.observation)
    if raw.get("schema_version") != "private-store-acquisition-observation/1":
        raise SystemExit("unsupported private acquisition observation schema")
    if raw.get("read_only_observation") is not True:
        raise SystemExit("observation must explicitly be read_only_observation=true")
    if raw.get("partner_center_write_performed") is not False:
        raise SystemExit("observation must prove partner_center_write_performed=false")

    values = {}
    for field in FIELDS:
        value = raw.get(field)
        if value not in (True, False, None):
            raise SystemExit(f"{field} must be true, false, or null")
        values[field] = value

    decision = classify_private_acquisition(
        PrivateAcquisitionObservation(**values)
    )
    output = {
        "schema_version": "private-store-acquisition-decision/1",
        "status": decision.state,
        "acquisition_route": decision.acquisition_route,
        "write_required": decision.write_required,
        "owner_approval_required": decision.owner_approval_required,
        "acquisition_allowed_now": decision.acquisition_allowed_now,
        "read_only_observation": True,
        "partner_center_write_performed": False,
        "package_uploaded": False,
        "certification_submitted": False,
        "published_by_this_command": False,
        "source_observation_path": str(a.observation),
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
