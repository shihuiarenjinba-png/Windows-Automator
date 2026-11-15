# Partner Center MSIX Game US — Packages Save and Submission Options

## Packages after the user's manual Save

- Product: `STRATEGY MARKET US`
- Store ID: `9PJCWW6G6D42`
- Draft: `1152921505702134687`
- Retained package: `STRATEGY_MARKET_USA_0.25.25.0_FINAL_UI_STORE_CANDIDATE_x64.msix`
- Version / architecture: `0.25.25.0 / X64`
- Device family: `Windows.Desktop min version 10.0.22000.0`
- Old `0.25.15.0`: absent after reload
- Overview: `Validated` and `Complete`
- Raw package acceptance state: `WARNING` for `runFullTrust`

The Packages Save button remained enabled after reload, so its enabled state is not used as proof of success. Save success is the composite of Overview Complete/Validated and a reload that retains the new package while the old package is absent.

## Submission Options teaching trace

The manifest declared exactly `runFullTrust`. Partner Center exposed one Restricted capabilities section and one matching textarea with `maxlength=500`. The script must scope the field by the localized section heading and exact `runFullTrust` token; it must not use the only textarea on the page as its sole selector.

The evidence-based game explanation was entered and Save was clicked. Partner Center redirected to the draft URL, Overview changed Submission options to `Complete`, and reopening Submission Options returned the exact explanation in a pristine textarea. The Save button was still enabled after reload, so button state is not a success signal.

## State model

- `package_acceptance_state = WARNING`
- `restricted_capability = runFullTrust`
- `restricted_capability_explanation = SAVED`
- `packages_section = COMPLETE`
- `submission_options = COMPLETE`
- `certification_gate = HOLD`

The exact warning may be classified as `RESTRICTED_CAPABILITY_REVIEW_REQUIRED` to select the Submission Options workflow. It must never be rewritten as package `VALID`. Any other warning remains `PACKAGE_VALIDATION_WARNING` and HOLD.

No certification submission, publication, pricing, market, identity, product-type, or Store listing change was performed.
