# STRATEGY MARKET US / JP — pre-certification runtime QA

Observed on 2026-11-15. Certification and Publish were not executed.

## Decision boundary

The route now requires:

`STORE_DRAFT_COMPLETE -> RUNTIME_QA_REQUIRED -> RUNTIME_FUNCTIONAL_QA_PASS -> PACKAGE_KEEP -> READY_FOR_CERTIFICATION_REVIEW`

Partner Center `Validated` and six `Complete` sections do not satisfy the runtime gate.

## STRATEGY MARKET US

- Current package: `STRATEGY_MARKET_USA_0.25.25.0_FINAL_UI_STORE_CANDIDATE_x64.msix`
- Version: `0.25.25.0`
- SHA-256: `38D50DF72E43D491FEAD9C69DED0780C5E35952B601260967D4AE96BA609455F`
- Source commit: `e1a4b9262947558236db4903de3cfecdb9efc94c`
- Manifest: `OkinawaDesktopTools.1662426D23FD4`, expected Publisher, x64, `Windows.Desktop`
- Package/source provenance: PASS
- Package-extracted and QA-runtime `app.asar`: exact SHA match
- Package-extracted and QA-runtime executable: exact SHA match
- Static regression and Store packaging tests: PASS
- Source UI browser proxy: PASS for clean-profile Start, automatic time progress, pause/resume, all seven primary tabs, browser autosave, reload/restore, continued progress, and a capital-investment 30 decision through 2026Q4 quarter close
- Source UI retained after reload: date `2026-12-30`, cash `$971.3M`, and `2026Q4` result
- Proxy boundary: this exercised the exact source commit in Edge, not the MSIX desktop wrapper; normal desktop-app exit was not represented
- Clean launch: blocked before launch by Windows Application Control policy
- Start / gameplay / controls / Save / relaunch / Restore / continue / exit: NOT RUN because the exact payload did not launch

State: `RUNTIME_QA_REQUIRED_POLICY_BLOCK`.

The package is not approved for sale or certification review in this state. The evidence does not prove a code defect or justify changing package bytes, so replacement is not asserted.

## STRATEGY MARKET JP

- Current package: `STRATEGY_MARKET_JP_0.1.24.0_STORE_CANDIDATE_x64.msix`
- Version: `0.1.24.0`
- SHA-256: `A4A16A8942A339C8C71C7795A50E7E111A8AD9AE31B6FEB9243998B3128139AB`
- Source commit: `b6d98e31a7b8abfe24c915bab7f38be0f089ebc6`
- Manifest: `OkinawaDesktopTools.STRATEGYMARKET`, expected Publisher, x64, `Windows.Desktop`
- Package/source provenance: PASS
- Package-extracted and QA-runtime `app.asar`: exact SHA match
- Package-extracted and QA-runtime executable: exact SHA match
- Native-save, Store packaging, new-profile start, current-save restore, malformed-save protection tests: PASS
- Source UI browser proxy: PASS for clean-profile Start, automatic time progress, pause/resume, all seven primary tabs, browser autosave, reload/restore, continued progress, and a capital-investment 30 decision through 2020Q1 quarter close
- Source UI retained after reload: date `2020-03-31`, cash `¥1,006M`, and `2020Q1` result
- Proxy boundary: this exercised the exact source commit in Edge, not the MSIX desktop wrapper; normal desktop-app exit was not represented
- Clean launch: blocked before launch by Windows Application Control policy
- Start / gameplay / controls / Save / relaunch / Restore / continue / exit: NOT RUN because the exact payload did not launch

State: `RUNTIME_QA_REQUIRED_POLICY_BLOCK`.

### Legacy save classification

The located historical saves are under `store-screenshots/qa-user-data` and have QA/rejected/MSIX-test profile names. The game products are still unpublished Store drafts. These saves are classified `LEGACY_DEV_SAVE_NONBLOCKING`, not public-user saves.

No old save was deleted. The current source tests prove that an invalid or old save remains protected, blocks Start, exposes export and explicit reset controls, and is not automatically removed. This is useful safety evidence but does not substitute for the missing exact-payload UI E2E.

## Source UI proxy interpretation

The Edge runs materially reduce uncertainty about Start, gameplay state transitions, navigation, quarterly decisions, browser persistence, and restore logic. They do not prove MSIX installation, Electron startup, native save-file behavior, process exit, or relaunch under the packaged identity. Therefore the proxy receives no certification-gate credit and the fail-closed state remains unchanged.

## Final outcome

- Current packages may be sold now: **NO**
- US certification readiness: **NO — RUNTIME_QA_REQUIRED_POLICY_BLOCK**
- JP certification readiness: **NO — RUNTIME_QA_REQUIRED_POLICY_BLOCK**
- Package replacement proven necessary: **NO**
- Package keep proven: **NO**
- Security policy changed: NO
- Test certificate installed: NO
- Certification / Publish: NOT EXECUTED

The safe next action is to run both exact payloads in an authorized Windows QA environment where Store test packages can launch without altering security policy, then complete the required visible E2E. If the E2E passes, record `PACKAGE_KEEP`; if it reveals a P0/P1 defect, rebuild with a version bump and replace the Store package.
