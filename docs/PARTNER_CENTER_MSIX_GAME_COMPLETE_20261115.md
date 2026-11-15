# MSIX Game — two-product Store Draft completion

Observed through Microsoft Partner Center on 2026-11-15. The dedicated `msix_pwa_game` route was completed and reloaded on two independent existing products.

## Immutable product evidence

| Product | Store ID | Draft ID | Package | Version |
|---|---|---|---|---|
| STRATEGY MARKET US | `9PJCWW6G6D42` | `1152921505702134687` | `STRATEGY_MARKET_USA_0.25.25.0_FINAL_UI_STORE_CANDIDATE_x64.msix` | `0.25.25.0` |
| STRATEGY MARKET | `9PM2R3N22JX8` | `1152921505702134539` | `STRATEGY_MARKET_JP_0.1.24.0_STORE_CANDIDATE_x64.msix` | `0.1.24.0` |

No product, Store ID, Draft ID, identity, publisher, or package version was changed.

## Store listing observations

The US product retained both English (United States) and Japanese (Japan) as `Complete`. The JP product retained Japanese (Japan) as `Complete`. Each listing used five final-version Desktop PNGs.

The deterministic Japanese US listing path was:

1. Fill the exact Description, five Product features, Short title, Short description, seven Keywords, and public Developed by value.
2. Commit each keyword with `Enter`; a populated combobox is not proof until the exact chip appears once.
3. Scope the plus control to the selected Desktop screenshot tab.
4. Upload one exact PNG per chooser invocation.
5. Wait until both the Desktop count and thumbnail count increment by exactly one before selecting the next file.
6. Save once, verify redirect to the same product Overview, and require Store listings `Complete`.
7. Reopen Manage Store listing languages and require every selected locale to be `Complete`.
8. Use the top exact product breadcrumb to return to the same product Overview, then verify all six sections again after reload.

The observed Desktop count sequence was `0 -> 1 -> 2 -> 3 -> 4 -> 5`. The automation must not retry an upload while the prior write is unknown.

## Final reconciliation

Both products retained `Complete` for:

- Pricing and availability
- Properties
- Age ratings
- Packages
- Store listings
- Submission options

The US Overview also retained the exact package filename and `Validated`. `Submit for certification` and `Publish` were not invoked.

Final Store state: `STORE_DRAFT_COMPLETE` for both products. This state alone is not certification readiness. The game route additionally requires `RUNTIME_FUNCTIONAL_QA_PASS` and `PACKAGE_KEEP`.

The 2026-11-15 pre-certification rerun verified exact package/source provenance and static regressions, but Windows Application Control blocked both exact payload executables before launch. The current state is therefore `RUNTIME_QA_REQUIRED_POLICY_BLOCK`, not `READY_FOR_CERTIFICATION_REVIEW`. JP saves found under the workspace QA profiles are development/QA-only and are classified `LEGACY_DEV_SAVE_NONBLOCKING`; no save was deleted.

Teacher-data state: `MULTI_PRODUCT_MSIX_GAME_ROUTE_VERIFIED`.

The route remains `live_write_supported=false` until these verified GUI steps are integrated behind one product-profile-gated public command. Certification and publication remain separate explicit owner gates.
