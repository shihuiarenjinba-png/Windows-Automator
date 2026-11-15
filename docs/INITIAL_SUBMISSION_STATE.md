# Existing Store product submission-state inspection

`inspect-existing-submission-state` is a read-only Partner Center command for
an existing Store product. It verifies the exact Identity, reads Overview and
Current packages, and emits one of:

- `EXISTING_PRODUCT_INITIAL_SUBMISSION`
- `EXISTING_PRODUCT_DRAFT_PRESENT`
- `EXISTING_PRODUCT_UPDATE_AVAILABLE`
- `UNKNOWN_PARTNER_CENTER_STATE`

The command never clicks **Start submission** or **Start update**, creates a
product, uploads a package, changes pricing, submits certification, or
publishes. Conflicting or incomplete signals produce
`HOLD_UNKNOWN_SUBMISSION_STATE`.

Example:

```powershell
python -m store_manager.cli inspect-existing-submission-state `
  --input C:\qa\prepared-product.json `
  --output C:\qa\submission-state-receipt.json `
  --cdp-url $env:PARTNER_CENTER_CDP_URL
```

For `EXISTING_PRODUCT_INITIAL_SUBMISSION`, the required input value is
`submission_kind=new`, but the actual Start submission click remains a
separate owner-authorized write action. The live draft workflow continues to
stop with `HOLD_INITIAL_SUBMISSION_ROUTE_REQUIRED` until that authorization and
a separately implemented start step exist.
