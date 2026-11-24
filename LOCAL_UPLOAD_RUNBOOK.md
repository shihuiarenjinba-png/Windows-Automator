# Local Store Draft upload runbook

This runbook uses the known local Playwright/CDP lane. It requires Windows, Python 3.11+, the project dependencies, and an already-authenticated Partner Center tab. The owner handles login/MFA/CAPTCHA manually; the script does not inspect browser credentials. The current app selector route is enabled only for the two observed app profiles (Folio AI and Daymark AI); a different product must first pass its product-specific gates and UI/profile review.

## 1. Prepare the inputs

Use one product's exact prepared `ProductInput` JSON and matching read-only Identity job. The product input must bind an existing `store_product_id`, `draft_id`, `package_path`, `package_sha256`, `security_package_sha256`, `identity_name`, `identity_publisher`, and `package_version`. The package must exist and its bytes must match both SHA fields. The identity job must be `existing-store-identity-reverify/1` with only read permissions.

Do not use the QA_UNSIGNED artifact as a formal package. Do not fill in a missing SHA with a hash inferred from a filename. If any identity, Draft, package, version, or route field is uncertain, stop.

## 2. Start the authenticated browser

Start the approved local Edge/Chromium CDP session by the existing organization procedure, sign in manually, and leave the Partner Center tab open. Pass the CDP endpoint through the current shell environment or secure local configuration. Do not paste the endpoint into a report, issue, or shared log. Never forward the local endpoint into GitHub Actions.

## 3. Read-only identity and Draft verification

```powershell
$ErrorActionPreference = 'Stop'
$productInput = 'C:\path\to\data-contract-auditor-formal-product-input.json'
$identityJob = 'C:\path\to\data-contract-auditor-identity-reverify-job.json'
$outDir = 'C:\path\to\store-run\data-contract-auditor'
$cdpUrl = $env:PARTNER_CENTER_CDP_URL
if ([string]::IsNullOrWhiteSpace($cdpUrl)) { throw 'PARTNER_CENTER_CDP_URL is empty; start the owner-authenticated local CDP browser first.' }
& .\scripts\run_local_store_upload.ps1 `
  -ProductInput $productInput `
  -IdentityJob $identityJob `
  -CdpUrl $cdpUrl `
  -OutputDir $outDir `
  -Mode ReadOnly
```

Expected result: `LOCAL_STORE_STATUS=READ_ONLY_IDENTITY_AND_DRAFT_VERIFIED`. This verifies the configured existing Product/Draft and package digest. It performs no upload. All receipts are written under a unique timestamp/GUID child directory inside `$outDir`; a new run never overwrites the previous run.

## 4. Queue and `--queue` argument error

Do not copy/paste a `night-run` command that refers to `$queuePath`, `$liveJson`, `$liveMd`, or `$CdpUrl` unless the same shell session initialized them. The Group C wrapper and the included `run_local_store_upload.ps1` initialize these paths from `-OutputDir`; the local runner creates a unique timestamp/GUID child directory for each attempt and writes `single-product-queue.json` there.

The reported error `argument --queue: expected one argument` occurs when PowerShell expands an unset/empty `$queuePath` and the next token (such as `--json-report`) is parsed as the missing argument. Use the wrapper above instead of choosing an arbitrary replacement path. If invoking the CLI manually for offline work, initialize and verify variables first:

```powershell
# Use the exact LOCAL_STORE_RUN_DIR printed by that invocation.
$runDir = 'C:\\path\\to\\store-run\\data-contract-auditor\\<timestamp-guid>'
$queuePath = Join-Path $runDir 'single-product-queue.json'
$liveJson = Join-Path $runDir 'live-report.json'
$liveMd = Join-Path $runDir 'live-report.md'
if (-not (Test-Path -LiteralPath $queuePath -PathType Leaf)) { throw "Queue file was not generated: $queuePath" }
```

The queue must be a non-empty JSON array containing a single ProductInput for this wrapper. The runner uses `ConvertTo-Json -InputObject @($product)` so a one-item queue remains an array rather than being enumerated into a JSON object. It parses the file back and rechecks the Product ID, Draft ID and SHA before invoking Python. The Python CLI also rejects blank paths, missing/invalid JSON, non-array/empty contents, duplicate Product IDs, and absent existing Draft IDs.

## 5. Live Draft package upload

This is a Partner Center write. Run it only after the formal package and owner decision are ready and the action-time authorization required by the governing process is present. It cannot create a new Store product or Submission and exposes no Certification or Publish operation.

```powershell
& .\scripts\run_local_store_upload.ps1 `
  -ProductInput $productInput `
  -IdentityJob $identityJob `
  -CdpUrl $cdpUrl `
  -OutputDir $outDir `
  -Mode LiveDraft `
  -ConfirmLiveDraft
```

The script rehashes the package, verifies exact existing identity and Draft, runs product-input validation, generates and re-parses the single-item queue, and then invokes the existing `night-run` route. It runs `verify-live-report` afterwards; that verifier checks the flattened QueueReport result, exact Product/Draft/Identity/filename/SHA binding, an unchanged post-run local package hash, successful upload/Save/reload flags, and explicit false values for product creation, submission start, pricing changes, certification and publication. `-ConfirmLiveDraft` is required at action time. It is not a Certification or Publish approval.

## 6. Reconcile and recover

- Authentication expired, selector count changed, Product/Draft mismatch, unknown warning/error, or invalid report: stop and preserve artifacts.
- Upload/Save timeout: do not rerun upload. First inspect the same Product/Draft read-only; determine whether upload is absent, active, validated, or saved.
- If Partner Center already shows the package, UI filename/Validated/Complete alone is insufficient to assert SHA identity. Require the matching immutable local attempt receipt; otherwise classify as `RECONCILE_REQUIRED`.
- Retry only after exact target state is reconciled to prove the prior write did not occur.
- Retain `attempt-manifest.json`, `identity-reverify.json`, `submission-state.json`, `live-report.json`, `live-report.md`, `live-report-verification.json`, the queue and screenshot evidence in the unique restricted local run directory. The manifest records run ID, target IDs, filename and local SHA but never the CDP endpoint. Redact account details before sharing.

## 7. Output meaning

`live-report-verification.json` with `status=LIVE_DRAFT_RECEIPT_VERIFIED` means the local verifier accepted the one-result report, exact Product/Draft/Identity/filename/SHA bindings, unchanged post-run local package bytes, and required safety flags.

`DRAFT_SAVED` means the current adapter verified the Store sections it owns after reload. `PACKAGE_SAVED_STORE_DRAFT_REMAINING_SECTIONS_REQUIRED` means the package/Draft step succeeded but other sections remain. Neither means Certified or Published. The verification receipt explicitly records `microsoft_independent_sha256_observed=false`: Partner Center UI does not expose an independently calculated binary digest.
