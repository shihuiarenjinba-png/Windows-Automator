# Folio AI MSIX App — live upload and analysis

Observed on 2026-11-12 on the exact Folio AI draft after reconciling earlier file-chooser timeouts.

## Proven state transitions

`PACKAGE_UPLOAD_REQUIRED` → `PACKAGE_UPLOAD_IN_PROGRESS` → `PACKAGE_ANALYZING` → `PACKAGE_WARNING_REVIEW` → `PACKAGE_SAVE_REQUIRED`

- The visible `browse your files.` link opened the verified multiple file input.
- The exact immutable MSIX was passed once through the browser file chooser.
- Partner Center exposed the filename, 100% progress, `Uploading`, then `Analyzing package`.
- Analysis produced only the known exact `runFullTrust` warning.
- The package row exposed `v1.0.3.0, X64` and `Windows.Desktop min version 10.0.19041.0`.
- Package details exposed `ja-jp`, `en-us`, `runFullTrust`, and the Store filter capability.
- Windows 10/11 Desktop changed from unchecked before upload to checked after analysis without a separate script click.
- Save redirected to the Folio product overview. Overview showed the exact package filename, `Validated`, and `Complete`.
- Reopening Packages retained `v1.0.3.0`, `X64`, `Windows.Desktop`, Desktop checked, and the exact warning.

## Expired-section recovery

A direct Packages reload displayed `Sign in required`. No authentication control was automated. The top product breadcrumb (`role=link`, exact product name, `href=#`) returned to the same product overview. The recovery postcondition is the exact product overview URL and heading plus Packages `Validated / Complete`. Reopening Packages after recovery again retained the expected package and warning.

## Failure-path evidence

Earlier chooser timeouts were reconciled by reloading the same Store ID and Draft ID. No package row or progress existed, so no write had occurred and the deterministic state was `SAFE_RETRY_ALLOWED`. The successful retry was performed only after the same package SHA-256 and empty draft were reverified.

## Safety boundary

The raw Microsoft result remains `WARNING`; it is not relabeled `VALID`. Unknown warnings and all errors remain hard holds. Certification and publishing were not invoked. Packages is now `PACKAGE_SAVED`; the route selector map remains disabled for unattended end-to-end writes until the remaining Store sections and owner decisions are completed and verified.

## Evidence resolution and remaining owner-input boundary

Fields are classified as `CURRENT_VALUE_PRESERVE`, `EVIDENCE_VALUE_APPLY`, or `OWNER_INPUT_REQUIRED`; an empty Store field is not automatically treated as an owner decision.

- Pricing and availability: All worldwide markets, future markets, Public audience, Store discoverability, ASAP release, and never-stop-acquisition are current values and remain unchanged. No PriceSchedule exists and no confirmed price exists in the repository, so only the base price is `OWNER_INPUT_REQUIRED`.
- Properties: product behavior supports primary category `Productivity`. `FOLIO_PRIVACY.md` matches the implementation, and Partner Center supports inline privacy-policy text when no public URL exists. The public GitHub Issues page was verified while logged out and is the support URL. The `/api/ask` path calls Ollama `/api/generate`, so the generative-AI declaration is `Yes`.
- IARC: Folio is neither a game nor primarily social/communication software, so App Type is `All Other App Types`; direct board rating remains `No`.
- Listings: the English and Japanese copy is version-consistent. Exactly five screenshot files exist, all Japanese UI, all 1920×1080, with no debug/test labels. The same verified files are used for both listing languages; no non-existent English screenshot set is recorded.
- Submission Options: the fixed `runFullTrust` explanation matches `packagedClassicApp`, `mediumIL`, `runFullTrust`, and `asInvoker`. The publication boundary is `MANUAL_PUBLISH_GATE`; certification and publication remain prohibited.

## Store Draft completion run

The owner selected a one-time purchase and exact Japanese retail price `JPY 780`. Partner Center offered an exact `780` option, so no tier fallback was used. Save returned to the same Folio product, and a fresh Pricing and availability load retained `JPY - Japan / 780`, All worldwide markets, and future markets. Overview reported Pricing and availability `Complete`.

Properties was saved with category `Productivity`, the repository-backed bilingual privacy policy as Partner Center inline text, the publicly readable GitHub Issues support URL, and Generative AI `Yes`. A fresh load retained all values and Overview reported `Complete`.

The IARC questionnaire used `All Other App Types`. The evidence-backed answers produced the IARC 10.4 preview with ESRB Everyone, IARC 3+, Microsoft 3+, and PEGI 3+. The preview's final checkbox combines two personal legal declarations: acceptance of the IARC Terms of Use and age-of-majority attestation. The script did not infer either declaration. The product owner explicitly performed that checkbox and Save. Overview then reported Age ratings `Complete`.

English and Japanese listings were saved separately. Each retained its prepared description, short description, features, and exactly five `1920x1080` real UI screenshots after a fresh load. Overview reported Store listings `Complete`.

Submission Options was saved with `Don't publish this submission until I select Publish now` and the exact evidence-backed `runFullTrust` explanation. A fresh load retained both values and Overview reported `Complete`.

## Screenshot chooser teacher rule

Use the visible Desktop new-image `+` button, not a guessed hidden file input. The chooser accepts one `.png` at a time. After `setFiles`, wait for both the thumbnail and the authoritative `Desktop (n)` counter increment, then wait for the `+` button to return before selecting the next file.

A chooser wait timed out during this run even though Partner Center completed the second image upload. The correct recovery is `timeout -> read Desktop count and thumbnails -> decide whether a write occurred`. Never retry blindly: that would create a duplicate upload. This exact reconciliation is now fixed as teacher data.

## Current boundary

After the owner completed the IARC declaration and Save, Overview showed all six required sections as `Complete`. The automation reopened Age ratings, observed the `/ageratings/summary` route, and verified IARC version 10.4 plus the generated ESRB Everyone, IARC 3+, Microsoft 3+, and PEGI 3+ ratings. A fresh summary reload retained those values. `Continue` returned to the same Folio overview, and a final full Overview reload again retained Pricing, Properties, Age ratings, Packages, Store listings, and Submission Options as `Complete`; the exact package remained `Validated`.

The reusable teacher rule is deliberately narrower than the Folio result. The route may reuse Age ratings navigation, questionnaire/preview/summary state detection, detection of the combined legal-attestation boundary, Save redirect detection, Overview reconciliation, and summary reload verification. It must not copy the Folio App Type, questionnaire answers, generated ratings, or owner attestation to another product. A new product must derive its answers from its own implementation evidence, and a personal legal declaration must be supplied by that product owner.

The resulting state is `STORE_DRAFT_COMPLETE` and the next state is `READY_FOR_CERTIFICATION_REVIEW`. Certification and publishing were not invoked. Final machine-readable evidence is tracked in `partner_center_msix_pwa_app_folio_complete.json`; the earlier owner-input fixture remains as the fail-closed pre-attestation transition.
