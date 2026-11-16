# Existing Store product submission-state inspection and initial Draft start

`inspect-existing-submission-state` is a read-only Partner Center command for
an existing Store product. It verifies the exact Identity, reads Overview and
Current packages, and emits one of:

- `EXISTING_PRODUCT_INITIAL_SUBMISSION`
- `EXISTING_PRODUCT_DRAFT_PRESENT`
- `EXISTING_PRODUCT_UPDATE_AVAILABLE`
- `UNKNOWN_PARTNER_CENTER_STATE`

The inspection command never clicks **Start submission** or **Start update**, creates
a product, uploads a package, changes pricing, submits certification, or publishes.
Conflicting or incomplete signals produce `HOLD_UNKNOWN_SUBMISSION_STATE`.

Example read-only inspection:

```powershell
python -m store_manager.cli inspect-existing-submission-state `
  --input C:\qa\prepared-product.json `
  --output C:\qa\submission-state-receipt.json `
  --cdp-url $env:PARTNER_CENTER_CDP_URL
```

## Initial submission route

For `EXISTING_PRODUCT_INITIAL_SUBMISSION`, the required input value is
`submission_kind=new`.

The initial-Draft start step is implemented separately from normal draft/package
processing:

- CLI: `start-initial-submission`
- wrapper: `scripts/run_initial_submission_start.ps1`
- explicit CLI acknowledgement: `--confirm-start-submission`
- required job contract: exact Store ID, source SHA, package SHA, identity, publisher,
  `submission_kind=new`, and permission scope
- permitted write: **Start submission only**
- forbidden writes in this step: product creation/reservation, package upload, pricing,
  certification submission and Publish

Immediately before clicking, the implementation re-runs the read-only submission-state
inspection and requires `EXISTING_PRODUCT_INITIAL_SUBMISSION`. It then requires
exactly one visible **Start submission** control. After the click, it re-inspects the
product and requires `EXISTING_PRODUCT_DRAFT_PRESENT` with a non-empty Draft ID.

If the click result cannot be reconciled exactly, the operation fails closed as an
ambiguous write and MUST NOT be blindly retried.

A successful receipt must report `INITIAL_SUBMISSION_DRAFT_CREATED` and must prove
that package upload, pricing change, certification submission and publication did not
occur.

This implementation does not make a checked-in `owner_approved: true` value a
standing authorization. The operator still requires direct execution-time owner
approval before the external `Start submission` write.
