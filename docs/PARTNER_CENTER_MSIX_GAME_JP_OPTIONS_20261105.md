# Partner Center MSIX Game JP — Submission Options observation

Observed product: `STRATEGY MARKET` (`9PM2R3N22JX8`), draft `1152921505702134539`.

The user entered and saved the `runFullTrust` explanation. After Save, Partner Center returned to the draft overview and showed **Submission options — Complete**. Reopening and reloading Submission Options retained the exact 397-character text, with the textarea in a pristine state and no error. Publishing hold remained **Don't publish this submission until I select Publish now**.

The JP page reproduced the US selectors and composite Save signal:

- Restricted capability container: `section.section:has(h2[data-l10n-key='resCapSectionHeader'])`
- Exact `runFullTrust` textarea: `section.section:has(h2[data-l10n-key='resCapSectionHeader']):has(span:text-is('runFullTrust')) textarea.text-area-width[maxlength='500']`
- Save: accessible role `button`, exact name `Save`
- Success: redirect to the same draft overview, Overview `Complete`, then exact text retained after reload with a pristine textarea

Save-button enabled state is not a success signal. The raw package warning remains a warning. Certification and publication were not executed. JP certification remains `HOLD_JP_START_FLOW_UNRESOLVED`.

Because the same behavior is now observed on the US and JP products, the Submission Options restricted-capability selector/save/reload contract is promoted to the `msix_pwa_game` route-level teacher data with `observed_products = 2`.
