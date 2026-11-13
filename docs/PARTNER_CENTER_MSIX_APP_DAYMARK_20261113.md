# Daymark AI MSIX App — second-product Store Draft verification

Observed on 2026-11-13 by applying the existing `msix_pwa_app` Folio route to a different product profile.

## Immutable product evidence

- Product: `Daymark AI`
- Store ID: `9PKJ9KMJZBC0`
- Draft ID: `1152921505702220032`
- Identity: `OkinawaDesktopTools.DaymarkAI`
- Publisher: `CN=46263F21-A700-41DB-8C9B-114C22FB82FC`
- Package: `DaymarkAI_1.0.4.0_x64_STORE_CANDIDATE_UNSIGNED.msix`
- SHA-256: `7E7996AD240AC27A3060080591475DA0C013CC9A5E7BC969379E2778B04E5D24`
- Version / architecture / family: `1.0.4.0 / X64 / Windows.Desktop`

The package produced the same exact known `runFullTrust` warning as Folio, no unknown warning, and no error. Save, reopen, and reload retained the exact package and Overview reported `Validated / Complete`.

## Product-specific values

- One-time purchase, exact `JPY 780`
- Existing markets preserved
- Category `Lifestyle`
- Generative AI `Yes`; AI required `No`
- Daymark-specific public Privacy and Support URLs
- English and Japanese copy from `DAYMARK_STORE_LISTING.md`
- The same five verified `1920x1080` Japanese UI screenshots in both locales
- Manual publish gate

These remain product-profile data and are not route defaults.

## New deterministic observations

### Lazy-rendered fields

Pricing did not expose `Currency` and `Retail price` until the Pricing section was scrolled into view. Submission Options likewise did not expose `Restricted capabilities` until the lower section was rendered. The route now renders the target section before resolving its scoped selector.

### Screenshot reconciliation

The Desktop chooser accepts one PNG per invocation. After the first image, unnamed button order changes because every thumbnail adds image and caption controls. The reusable selector is the Desktop panel's scoped visible `new-image-button`, never the first or last unnamed button.

Partner Center sometimes returned from `setFiles` before the Desktop count changed, and one transient `Bad Response` preceded a later successful count increment. Therefore:

1. Record the previous Desktop and thumbnail counts.
2. Open the scoped visible plus control.
3. Set one exact PNG.
4. Wait until both counts increment by exactly one.
5. On timeout/error, reconcile current counts and reload before deciding whether retry is safe.
6. Never retry when either counter proves the write occurred.

### runFullTrust limit

An initial 609-character explanation remained visible but showed `609/500` and left Submission Options incomplete. The final Daymark-specific explanation was 495 characters, retained after reload, and changed Overview to `Complete`. The 500-character limit is now a pre-write hard gate.

### IARC branch and owner boundary

Daymark used `All Other App Types`. Optional local generative-AI output required `Online Content = Yes`. The conditional violence, sexuality, offensive-language, and controlled-substance questions were answered from Daymark's constrained source-grounded local Ollama implementation, not copied from Folio. The generated IARC 10.4 preview was ESRB Everyone, IARC 3+, Microsoft 3+, and PEGI 3+.

The combined Terms of Use / age-of-majority checkbox was left to the product owner. This was the only human intervention. After the owner clicked the checkbox and Save, the automation verified Age ratings `Complete` and performed a final full Overview reload.

## Final state

All six required sections retained `Complete`:

- Pricing and availability
- Properties
- Age ratings
- Packages
- Store listings
- Submission options

`Submit for certification` and `Publish` were not invoked.

Final state: `STORE_DRAFT_COMPLETE` -> `READY_FOR_CERTIFICATION_REVIEW`.

Route evidence: `MULTI_PRODUCT_MSIX_APP_ROUTE_VERIFIED` (`observed_products = 2`).
