# Folder Automation Engine — Store execution handoff after manual Start submission

Updated: 2026-11-17 JST

## Purpose

Complete the Microsoft Store submission preparation for **Folder Automation Engine** while preserving the frozen package and preventing duplicate Partner Center writes.

The product owner has already clicked **Start submission** manually. Therefore **never click Start submission again**. The next operation is read-only reconciliation.

This handoff stops at:

`READY_FOR_MSIX_UPLOAD_APPROVAL`

Package upload, certification, Private publish, promotional-code generation, and Public release remain separate explicit gates.

## Correct working branches

Do not use the older Store automation branch for this operation.

- Folder Automation Engine
  - repository: `shihuiarenjinba-png/folder-automation-engine`
  - branch: `codex/folder-standard-consumer-ui-20261026`
  - frozen product source: `51597b389384be6cf2b3d85c09ee66099b80807e`
  - later Store metadata/runbook commits do **not** replace the frozen product source
- Windows-Automator
  - repository: `shihuiarenjinba-png/Windows-Automator`
  - branch: `codex/msix-commercial-contract-20261115`
  - known handoff HEAD: `d8838436633a544413d4599d5dbb64bad9ab2539`
  - PR: #2
- Windows-all-auto
  - repository: `shihuiarenjinba-png/Windows-all-auto`
  - branch: `codex/msix-commercial-handoff-20261115`
  - PR: #166

The older Windows-Automator branch `codex/store-submission-automation-20261026` does not contain the required post-ambiguous-start reconciliation script and must not be used for this Folder run.

## Immutable Store identity

- Product: `Folder Automation Engine`
- Store ID: `9P99MJX1R4V6`
- Identity: `OkinawaDesktopTools.FolderAutomationEngine`
- Publisher: `CN=46263F21-A700-41DB-8C9B-114C22FB82FC`
- Publisher display name: `Okinawa Desktop Tools`
- PFN: `OkinawaDesktopTools.FolderAutomationEngine_j8yefg9jgfh58`
- Package SID: `S-1-15-2-795676864-310991790-2802347502-2718627192-2651328981-310414558-459028798`
- Version: `1.0.0.0`
- Architecture: `x64`

Never infer or alter these values.

## Frozen package

Only this local file may be uploaded:

```text
C:\Users\aaron\Desktop\portfolio-audit\_group_b_store_qa_20261024\artifacts\FolderAutomationEngine\ci-51597b3\FolderAutomationEngine-Store-MSIX-UNSIGNED-DRAFT\store-out-43697191105\FolderAutomationEngine_1.0.0.0_x64_StoreDraft_UNSIGNED.msix
```

Expected filename:

`FolderAutomationEngine_1.0.0.0_x64_StoreDraft_UNSIGNED.msix`

Expected SHA-256:

`911F8EB13ABFDBB51BEA8F279006D138D6BE9CBA4A25413416C1D70458676450`

Expected EXE SHA-256:

`D53161EA1119445AFB8070D989D4A72E8019895B8C5E166738A3E38718B54976`

Artifact provenance:

- workflow run: `43697191105`
- Store artifact: `14155171103`
- Windows artifact: `14155410314`

Do not rebuild, substitute, download another artifact copy as an implicit replacement, or use a package generated from a newer metadata commit.

## Stage 1 — prove the local file exists

On the user's Windows PC:

```powershell
$msix = 'C:\Users\aaron\Desktop\portfolio-audit\_group_b_store_qa_20261024\artifacts\FolderAutomationEngine\ci-51597b3\FolderAutomationEngine-Store-MSIX-UNSIGNED-DRAFT\store-out-43697191105\FolderAutomationEngine_1.0.0.0_x64_StoreDraft_UNSIGNED.msix'

Test-Path -LiteralPath $msix
Get-Item -LiteralPath $msix | Select-Object FullName, Length, LastWriteTime
Get-FileHash -LiteralPath $msix -Algorithm SHA256
```

Required:

- `Test-Path=True`
- SHA-256 exact match with the frozen value

If missing:

`HOLD_LOCAL_MSIX_NOT_FOUND`

If the SHA differs:

`HOLD_LOCAL_MSIX_SHA_MISMATCH`

Do not rebuild to make either hold disappear.

## Stage 2 — read-only reconcile the manually-created Draft

The owner already performed Start submission.

Use:

```text
folder-automation-engine/store/LOCAL_POST_MANUAL_START_RECONCILE_JOB_20261117.json
```

and Windows-Automator:

```text
scripts/reconcile_initial_submission_attempt.ps1
```

Example:

```powershell
$folderRepo = 'C:\Users\aaron\Desktop\portfolio-audit\_task_worktrees\folder-automation-engine'
$automator = 'C:\Users\aaron\Desktop\portfolio-audit\_task_worktrees\Windows-Automator'
$work = 'C:\Users\aaron\Desktop\portfolio-audit\STORE_UPLOAD_ASSETS_20261019\FolderAutomationEngine\local-store-preflight-20261116'
$cdp = $env:PARTNER_CENTER_CDP_URL

$automatorInput = Join-Path $work 'windows-automator-input-initial-draft-HOLD.json'
$reconcileReceipt = Join-Path $work 'initial-submission-reconcile-receipt-20261117.json'

Set-Location $automator
pwsh -File .\scripts\reconcile_initial_submission_attempt.ps1 `
  -Input $automatorInput `
  -Output $reconcileReceipt `
  -CdpUrl $cdp
```

Required result:

`INITIAL_SUBMISSION_DRAFT_PRESENT_RECOVERED`

Require:

- exact Store ID
- nonempty numeric Draft ID
- Draft URL for the same product
- `write_performed=false`

If a Draft is not proven:

`HOLD_SUBMISSION_RECONCILE_REQUIRED`

Never retry Start submission from this run.

## Stage 3 — bind the recovered Draft

After the reconciliation receipt proves the Draft, bind the Draft ID/URL to the Store handoff through Windows-all-auto.

If the existing `apply_initial_submission_receipt.py` contract accepts only an initial-start receipt, either:

1. normalize the read-only recovered receipt to the same immutable Draft binding contract without fabricating a write, or
2. add a dedicated `apply_recovered_initial_submission_receipt.py` helper plus tests.

The final handoff must record the recovered Draft while preserving:

- `submission_started` as historical/manual owner action
- no automated Start click
- no package upload
- no pricing write
- no certification
- no publish

Do not mark a write that the automation did not perform.

## Stage 4 — read-only Store-field collection

With the recovered exact Draft, inspect without Save/write:

### Packages
- no wrong package already present
- accepted package type
- architecture field/state
- current validation/package state

### Pricing and availability
- visible JPY price choices
- current/default price
- 7-day trial availability
- markets

### Distribution / audience
- Public/Private audience options
- Customer groups
- Known User Group availability
- existing candidate group, if any

### Properties
- category choices
- privacy field
- local file/folder access declaration
- external network/cloud
- external account
- camera
- microphone
- location
- restricted capability / runFullTrust
- driver/service dependency

### Store listing
- Japanese/English language rows
- description fields
- screenshots
- icons
- Privacy URL
- Support URL

### Submission options
- certification notes
- security questions
- runFullTrust explanation field
- publishing timing

Persist a local observation receipt. Do not store browser cookies/tokens/profile data in GitHub.

## Stage 5 — assets and business/security holds

The handoff currently intentionally contains unresolved values. Do not bypass them.

Expected unresolved items may include:

- exact JPY retail price/tier
- Private audience Known User Group
- owner visual approval
- final screenshots/icons
- security owner confirmation / personal-data declaration

Use current Partner Center observations to narrow the choices, but do not invent decisions.

Store images directory:

```text
C:\Users\aaron\Desktop\portfolio-audit\STORE_UPLOAD_ASSETS_20261019\FolderAutomationEngine\local-store-preflight-20261116\store-images
```

Missing or unverified assets:

`HOLD_STORE_ASSETS`

## Stage 6 — pre-upload exact-package recheck

Immediately before any future upload, rerun:

```powershell
Test-Path -LiteralPath $msix
Get-FileHash -LiteralPath $msix -Algorithm SHA256
```

Then require the entire immutable binding:

- Store ID = `9P99MJX1R4V6`
- Identity = `OkinawaDesktopTools.FolderAutomationEngine`
- Publisher exact match
- Version = `1.0.0.0`
- Architecture = `x64`
- Source SHA = `51597b389384be6cf2b3d85c09ee66099b80807e`
- MSIX SHA = `911F8EB13ABFDBB51BEA8F279006D138D6BE9CBA4A25413416C1D70458676450`

Any mismatch:

`HOLD_EXACT_PACKAGE_MISMATCH`

## Stage 7 — stop before package upload

Only after:

- local MSIX exists
- SHA matches
- exact Draft is recovered and bound
- Store fields were read
- assets/business/security requirements have been classified
- no unknown product/identity/package state remains

return:

`READY_FOR_MSIX_UPLOAD_APPROVAL`

Stop there.

Do **not** upload the package in this phase.

## Required code-owner work

While performing the flow, make the orchestration reusable rather than Folder-only where safe:

1. Preserve the read-only recovered-Draft path as a first-class state.
2. Ensure a recovered Draft can be bound without pretending the automation clicked Start.
3. Add regression tests for:
   - manual Start already performed + Draft present
   - no Draft after manual-start claim
   - multiple/ambiguous Draft URLs
   - Store ID mismatch
   - write_performed=true in a reconciliation receipt
   - missing local package
   - local SHA mismatch
4. Add a deterministic pre-upload gate that returns exactly:
   - `HOLD_LOCAL_MSIX_NOT_FOUND`
   - `HOLD_LOCAL_MSIX_SHA_MISMATCH`
   - `HOLD_SUBMISSION_RECONCILE_REQUIRED`
   - `HOLD_EXACT_PACKAGE_MISMATCH`
   - `HOLD_STORE_ASSETS`
   - or `READY_FOR_MSIX_UPLOAD_APPROVAL`
5. Certification and Publish must remain impossible from this command.
6. Do not generalize Folder-specific Store ID, Identity, SHA, version, price, audience, listing text, or security answers into route defaults.

## Completion report

Return:

### Local package
- exists:
- path:
- size:
- last_write_time:
- sha256:
- exact_match:

### Draft
- Store ID:
- Draft ID:
- Draft URL:
- reconcile status:
- automated write performed: false

### Store observations
- Packages:
- Pricing:
- Trial:
- Markets:
- Audience:
- Customer group:
- Properties:
- Store listing:
- Submission options:
- Assets:

### Holds
- price:
- audience:
- security:
- assets:
- other:

### Final state

Either a precise HOLD code, or:

`READY_FOR_MSIX_UPLOAD_APPROVAL`

Package upload: `NOT EXECUTED`
Certification: `NOT EXECUTED`
Publish: `NOT EXECUTED`
