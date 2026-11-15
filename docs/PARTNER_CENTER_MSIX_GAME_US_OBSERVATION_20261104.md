# Partner Center MSIX Game US observation — 2026-11-04

## Result

`STRATEGY MARKET US` (`9PJCWW6G6D42`) was matched to the existing `MSIX or PWA game` draft `1152921505702134687`. The authorized package was uploaded and parsed as version `0.25.25.0`, architecture `X64`.

Partner Center returned this exact package warning:

> Package acceptance validation warning: The following restricted capabilities require approval before you can use them in your app: runFullTrust.

The governing contract says `WARNING = HOLD`. Save was therefore not clicked. No certification, publication, pricing, market, listing, or submission-option action was performed. The JP product was not attempted because the US gate did not reach VALID.

## Evidence recorded

- Product, Store ID, Identity name, Publisher, and current draft matched exactly.
- Local package SHA-256 matched the immutable handoff: `38D50DF72E43D491FEAD9C69DED0780C5E35952B601260967D4AE96BA609455F`.
- Upload reached 100%, then displayed `Analyzing package`.
- The new row displayed version `0.25.25.0`, `X64`, rank 1, and Windows Desktop minimum version `10.0.22000.0`.
- After one reload, analysis had ended, the new package remained visible, Save was enabled, and the same `runFullTrust` warning remained visible.
- The prior version `0.25.15.0` remained present and was shown as pending removal if Save were clicked.

## Automation boundary

Observed upload and warning selectors are stored in `PARTNER_CENTER_MAP.json`. The complete validation taxonomy, package-section completion, Save success, and post-save required-section reconciliation remain unverified. Consequently `msix_pwa_game.live_write_supported` remains `false`; this observation must not be interpreted as `DRAFT_SAVED`.
