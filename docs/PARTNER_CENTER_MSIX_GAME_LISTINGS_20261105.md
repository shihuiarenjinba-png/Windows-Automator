# MSIX Game Store listings observation — 2026-11-05

## Scope

The live Partner Center drafts for `STRATEGY MARKET US` (`9PJCWW6G6D42`) and `STRATEGY MARKET` (`9PM2R3N22JX8`) were read without submitting either product for certification.

## Route-level field mapping

The same listing form was observed for both products and for the `en-US` / `ja-JP` locale pages:

- Description: `textarea#description-required`
- What's new: `textarea#releaseNotes`
- First feature: `input#feature-0`
- Desktop screenshot tab: `#tab-0`
- Short title: `input#shortTitle`
- Short description: `textarea#shortDescription`
- Copyright/trademark: `input#trademark`
- Additional license terms: `textarea#additionalLicenseTerms`
- Developed by: `input#devStudio`
- Save: exactly one button with accessible name `Save`

The Desktop panel states that PNG files are accepted, at least one screenshot is required, and `1366 x 768` or larger is recommended.

## Product observations

### STRATEGY MARKET US

- Package languages: English (United States) = Complete; Japanese (Japan) = Incomplete.
- English listing contained seven screenshots from `0.25.21.0`; these are not valid for the submitted `0.25.25.0` package.
- English `Developed by` contained internal review text and must be replaced by the public name `Okinawa Desktop Tools`.
- Japanese (Japan) listing was empty and contained zero Desktop screenshots.
- Two five-image sets were captured from the actual `0.25.25.0` Windows runtime: one English UI set and one Japanese UI set. Every image is `1426 x 923` PNG and has a recorded SHA-256 in the fixture.

### STRATEGY MARKET

- Package language: Japanese (Japan) = Incomplete.
- Additional languages `English` and `Japanese` were present but incomplete. The Japan package itself supports `ja-JP`; the exact language plan therefore retains Japanese (Japan) and removes only the two additional rows.
- Japanese (Japan) listing was empty and contained zero Desktop screenshots.
- The final `0.1.24.0` runtime was launched with an isolated clean user-data directory. The four-step new-game flow reached the live dashboard and the Operations, Market, Finance, and Strategy views.
- Five Store images were captured from that exact runtime at `1440 x 930` PNG. Their SHA-256 values are recorded in the fixture; no older `0.1.23.0` image is accepted as a substitute.
- The existing default-profile save was read but not modified. The current save guard rejects it as `invalid or incomplete v4 save`; this is a protected migration/recovery concern, not evidence against clean-profile startup.

## Composite Save success contract

A listing Save is proven only when all of the following are true:

1. The listing Save action returns without authentication loss.
2. Reload returns the exact description and public developer name.
3. Reload shows the expected Desktop screenshot count.
4. The form is pristine after reload.
5. Overview reports Store listings as `Complete`.

Save-button enabled/disabled state alone is not a success signal. `Submit for certification` and `Publish` are outside this contract.
