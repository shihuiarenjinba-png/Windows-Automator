# Local Microsoft Store uploader — forensic report

Recorded: 2026-11-24 (JST)  
Scope: read-only review of prior code, tracked Store route evidence, teacher receipts and the supplied local logs. No Partner Center write was performed.

## Finding: proven upload route

The reusable, previously successful method is a local Playwright client attached over CDP to an already-authenticated Edge/Chromium Partner Center tab. The automation does not log in or handle MFA/CAPTCHA. This finding is supported by:

- `store_manager/live_draft.py`: `LivePlaywrightConnection`, `PlaywrightPartnerCenterPort`, exact selector map, Draft verification, package upload/analysis wait, Save, reload and postcondition checks.
- `store_manager/cli.py`: `night-run --execution-mode live --confirm-live-draft --cdp-url ...` dispatches to that local adapter.
- `docs/PARTNER_CENTER_MAP.json`: records the verified app/game routes, exact selectors, observed Microsoft states, reload checks and prohibited controls.
- `docs/PARTNER_CENTER_MSIX_APP_FOLIO_UPLOAD_20261112.md`: records a successful Folio package upload, known warning classification, Save, reload, and full Store Draft completion. It separately notes earlier chooser timeouts were reconciled before retry.
- Cross-repository teacher receipts under `Windows-all-auto/ops/`: Folder Automation Engine binds the local package SHA and IDs to `Uploading → Analyzing package → Validated`, Packages Save, same-Draft reload and retained package metadata.

The machine-readable product index is `STORE_UPLOADER_TEACHER_INDEX.json`. Product-specific IDs and package hashes are not promoted to route defaults.

## Evidence strength and limits

| Claim | Evidence | Conclusion |
|---|---|---|
| Browser method | Playwright/CDP implementation, live selector map and success reports | Proven route |
| Folio package upload and full Draft Save/reload | Folio live-operation report and route receipt | Proven at the recorded time |
| Folder exact binary | Package upload receipt includes filename, SHA-256, Identity, Publisher, Version and X64 | Strongest exact package binding found |
| Daymark and STRATEGY MARKET US/JP | Partner Center map and product completion reports | Draft package and Save/reload route recorded as complete; per-package SHA was not present in the shared route map reviewed here |
| Independent SHA from Partner Center | Partner Center UI does not expose the uploaded binary digest | Not observable; only the local pre-upload hash and immutable execution receipt can bind what the automation sent |
| Certification / publication | Reports and safety fields explicitly say not executed | Not claimed |
| Raw successful shell transcript | No matching Partner Center command log found in the named Temp files | Exact historical command line remains unverified |

The five historical products in the teacher index are Folder Automation Engine, Folio AI, Daymark AI, STRATEGY MARKET US, and STRATEGY MARKET JP. This reconciles the user's approximate count of four against the currently accessible route/receipt evidence; it does not imply that all five share the same package bytes or product settings.

## Supplied Temp logs

The requested `MITSUKI-20261124-*`, `MITSUKI-20261123-*` and older matching `.log` files were checked for `night-run`, `--queue`, `queuePath`, report arguments, `confirm-live-draft`, CDP argument and Partner Center state terms. They are Office Click-to-Run telemetry logs, not uploader logs; no matching Store command or upload receipt was found. They were not edited. `cv_debug.log` was not treated as Store evidence.

The command error in the supplied request is consistent with PowerShell expanding an unset/empty `$queuePath` so that `--queue` receives the next option token as its value. The user's command itself is the evidence for the error. The current Group C wrapper initializes `$queuePath` to `single-product-queue.json` under its output directory, writes a one-product JSON array after exact identity/Draft checks, then invokes `night-run`. A new generic wrapper with the same initialization and preflight checks is included at `scripts/run_local_store_upload.ps1`.

## Official CLI / direct HTTP alternatives

This investigation found no evidence that `msstore` or a Microsoft Store CLI performed these historical uploads. An absent `Get-Command msstore` result is not treated as historical proof. The reviewed success evidence points to local Playwright/CDP. API or direct HTTP calls are not introduced as a replacement.

## Data Contract Auditor current state

The local read-only records show exact existing Identity values, but the most recent saved `submission-state.json` (`20261123-162718`) is `HOLD_UNKNOWN_SUBMISSION_STATE`; do not treat an earlier read-only classification as current. The local ProductInput names an existing target Draft ID, but the current Partner Center state was not successfully reconciled.

The configured local candidate was read-only hashed and its ZIP manifest read without launching it. SHA-256 is `4b373d2bc54ecbd3efa0a77a94005007777e66d641fa3908f523ac69fcd46984`; Identity/Publisher/Version/Architecture match the Data Contract Auditor ProductInput. It contains `en-US` and `ja-JP` manifest resources and the four named logo files. However, its embedded source commit is `5a09d81955e25664761ea25ecfb4ebf8d24cea6d`, while the required pinned revision is `107e59f2cbcde9c6ca88cf1aaf3d52262004e6e0`. The local ProductInput has no `security_package_sha256`; owner-approved artwork evidence and certified commercial-license evidence remain absent. The input's `human_local_qa_pass=true` is recorded as a claim, not independently reproduced QA. This candidate therefore is not eligible for upload.

Separately, the Cloud Auto Uploader job remains `upload_approved: false` with a formal SHA placeholder. The pinned GitHub source revision previously inspected did not contain the configured formal MSIX path. Do not substitute this local package or promote its logo files without the required owner approvals.

## Unresolved

1. The original `C:\Users\aaron\Desktop\Windows-Automator` repository metadata is access-restricted in this session. The existing code snapshot was read from an isolated worktree and the current local scripts from readable source files; no original repo state was modified.
2. Raw successful process command lines and per-run raw browser logs were not present among the supplied Temp logs.
3. Per-product SHA-256 values for four historic products are not available in the reviewed common teacher index; do not infer them from filenames.
4. The CDP endpoint is machine/session-local. It is not a cloud endpoint and must not be copied to logs or remote workflow configuration.
5. The merged/reviewed app route has `live_write_supported=true` but is explicitly profile-gated to the two observed products (Folio AI and Daymark AI). The code accepts only the exact `runFullTrust` warning when the manifest contains only that capability and its owner-confirmed justification is bound to the same package SHA. DCA is not one of the two observed profiles; it must pass its own Identity/Draft, formal-package, security-confirmation, local-QA and immutable-hash gates before a write is eligible.

## Follow-up hardening implemented in the dedicated worktree

- `scripts/run_local_store_upload.ps1` now treats `-OutputDir` as a run root and creates a unique timestamp/GUID child directory for every invocation. It records an `attempt-manifest.json` without the CDP endpoint, keeping reports, queue files, and screenshots from separate attempts isolated.
- The one-item queue is serialized with `ConvertTo-Json -InputObject @($product)`, checked as a JSON array from its raw delimiters, parsed back, and rebound to the exact Product ID, Draft ID and package SHA before `night-run`. This avoids PowerShell's one-item pipeline/JSON enumeration ambiguity.
- `store_manager.cli verify-live-report` and `verify_live_report_payload` were added. They validate the flattened `QueueReport.to_dict()` structure, one-result report shape, exact Product/Draft/filename/Identity/source/SHA binding, a post-run local package rehash, successful upload/Save/reload flags, and explicit false values for product creation, submission start, pricing changes, certification and publication.
- `LiveDraftWorkflow` now records explicit false flags for creating/reserving a product, starting submission/update, and changing pricing. Missing or non-false safety flags fail receipt verification.
- The wrapper checks read-only Identity and Draft receipts for explicit no-write flags, defaults to ReadOnly, and requires `-ConfirmLiveDraft` for a Draft package write.
- The execution map and runbook now document per-attempt isolation and post-upload receipt verification. Tests cover flattened versus nested report structure, safety-flag omission/activation, target/Identity/SHA mismatches, and package bytes changing during the attempt.

## Latest verification

GitHub Actions run [#289](https://github.com/shihuiarenjinba/Windows-Automator/actions/runs/45354878346) completed successfully on the current branch. It passed:

- `python -m unittest discover -s tests -v`: 218 tests
- `python -m compileall -q store_manager tests`
- JSON parsing for `STORE_UPLOADER_TEACHER_INDEX.json` and `docs/PARTNER_CENTER_MAP.json`
- PowerShell parser validation for `scripts/run_local_store_upload.ps1`
- Windows PowerShell single-item queue serialization, JSON-array root check, parse-back and Product/Draft/SHA binding checks

These checks cover code and local input/receipt contracts. They do not exercise a live Partner Center session or prove Microsoft's independent binary digest.

No actual upload, certification, publication, price change, market change, or new Submission was run. GitHub Actions validates code and local receipt logic only; it does not connect to Partner Center or exercise a live write.
