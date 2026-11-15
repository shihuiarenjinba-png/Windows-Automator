# Folio AI MSIX App — read-only pre-upload observation

Observed on 2026-11-11 without uploading, selecting a device family, saving, submitting, or publishing.

## Exact target

- Product: `Folio AI`
- Partner Center route: `MSIX or PWA app`
- Store ID: `9P0VNLJ5FPF5`
- Draft ID: `1152921505702219486`
- Package Identity: `OkinawaDesktopTools.FolioAI`
- Publisher: `CN=46263F21-A700-41DB-8C9B-114C22FB82FC`
- Candidate: `FolioAI_1.0.3.0_x64_STORE_CANDIDATE_UNSIGNED.msix`
- Candidate SHA-256: `AEECFA80D79FFD9AFE2B290DCEF8E390FC0CA9433CC73335368B1164D9F4E459`

The product search returned exactly one `Folio AI` row. The Product Identity page matched the package manifest and immutable handoff.

## Initial draft state

- Pricing and availability: all worldwide markets, public and discoverable, but no base price configured.
- Properties: primary category and privacy declaration are unanswered.
- Age ratings: new IARC questionnaire selected; app type is unanswered.
- Packages: empty; Windows 10/11 Desktop is unchecked; future device families is checked.
- Store listings: package languages are unavailable until a package is uploaded.
- Submission Options: publish-as-soon-as-certified is selected; no restricted-capability section is visible before package upload.

These are observations, not approved desired values. Pricing, markets, categories, declarations, ratings, and publish hold remain owner or product-profile decisions.

## Fail-closed boundary

The checked-in `msix_pwa_app` route remains `live_write_supported=false`. Upload, Microsoft analysis states, warning classification, Save success, reload retention, `runFullTrust`, and Overview reconciliation are not promoted until a real authorized upload is observed.

Machine-readable evidence is stored in `tests/fixtures/partner_center_msix_pwa_app_folio_preupload.json` and guarded by `tests/test_msix_app_folio_preupload.py`.
