param(
  [Parameter(Mandatory=$true)][string]$Input,
  [Parameter(Mandatory=$true)][string]$IdentityJob,
  [Parameter(Mandatory=$true)][string]$CdpUrl,
  [Parameter(Mandatory=$true)][string]$OutputDir,
  [ValidateSet("ReadOnly","LiveDraft")][string]$Mode = "ReadOnly",
  [switch]$ConfirmLiveDraft
)

$ErrorActionPreference = "Stop"
if (-not $IsWindows) { throw "Windows only" }

$inputPath = (Resolve-Path -LiteralPath $Input).Path
$identityJobPath = (Resolve-Path -LiteralPath $IdentityJob).Path
$outRoot = [System.IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $outRoot -Force | Out-Null

$identityReceipt = Join-Path $outRoot "identity-reverify.json"
$stateReceipt = Join-Path $outRoot "submission-state.json"
$liveJson = Join-Path $outRoot "live-report.json"
$liveMd = Join-Path $outRoot "live-report.md"
$queuePath = Join-Path $outRoot "single-product-queue.json"

Write-Host "GROUP_C_TEACHER_STAGE=IDENTITY_REVERIFY"
python -m store_manager.cli verify-existing-identity `
  --job $identityJobPath `
  --output $identityReceipt `
  --cdp-url $CdpUrl
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$identity = Get-Content -LiteralPath $identityReceipt -Raw | ConvertFrom-Json
if ($identity.status -ne "EXISTING_IDENTITY_EXACT_MATCH") {
  throw "HOLD_IDENTITY_EXACT_MATCH_REQUIRED"
}
if ($identity.package_uploaded -or $identity.pricing_changed -or $identity.submitted -or $identity.published) {
  throw "Read-only identity step reported an unexpected write."
}

Write-Host "GROUP_C_TEACHER_STAGE=SUBMISSION_STATE"
python -m store_manager.cli inspect-existing-submission-state `
  --input $inputPath `
  --output $stateReceipt `
  --cdp-url $CdpUrl
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$state = Get-Content -LiteralPath $stateReceipt -Raw | ConvertFrom-Json
if ($state.package_uploaded -or $state.pricing_changed -or $state.submitted -or $state.published) {
  throw "Read-only submission-state step reported an unexpected write."
}

if ($Mode -eq "ReadOnly") {
  Write-Host ("GROUP_C_TEACHER_PROBE_PASS state=" + $state.submission_state)
  exit 0
}

if (-not $ConfirmLiveDraft) {
  throw "LiveDraft mode requires -ConfirmLiveDraft at action time."
}
if ($state.submission_state -ne "EXISTING_PRODUCT_DRAFT_PRESENT") {
  throw ("HOLD_EXISTING_DRAFT_REQUIRED state=" + $state.submission_state)
}
if (-not $state.submission_kind_matches) {
  throw "HOLD_SUBMISSION_KIND_MISMATCH"
}

Write-Host "GROUP_C_TEACHER_STAGE=FORMAL_INPUT_VALIDATE"
python -m store_manager.cli validate --input $inputPath
if ($LASTEXITCODE -ne 0) {
  throw "HOLD_FORMAL_PRODUCT_INPUT_VALIDATION"
}

$product = Get-Content -LiteralPath $inputPath -Raw | ConvertFrom-Json
@($product) | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $queuePath -Encoding UTF8

Write-Host "GROUP_C_TEACHER_STAGE=LIVE_DRAFT"
python -m store_manager.cli night-run `
  --queue $queuePath `
  --json-report $liveJson `
  --markdown-report $liveMd `
  --execution-mode live `
  --confirm-live-draft `
  --cdp-url $CdpUrl `
  --evidence-dir (Join-Path $outRoot "evidence")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$report = Get-Content -LiteralPath $liveJson -Raw | ConvertFrom-Json
if (-not $report.results -or $report.results.Count -ne 1) {
  throw "HOLD_LIVE_REPORT_SHAPE_UNKNOWN"
}
$result = $report.results[0]
$allowedStatuses = @(
  "DRAFT_SAVED",
  "PACKAGE_SAVED_STORE_DRAFT_REMAINING_SECTIONS_REQUIRED"
)
if ($allowedStatuses -notcontains $result.status) {
  throw ("HOLD_LIVE_DRAFT_NOT_SAVED status=" + $result.status)
}
if ($result.details.submitted -or $result.details.certified -or $result.details.published) {
  throw "PROHIBITED_CERTIFICATION_OR_PUBLISH_SIDE_EFFECT"
}

if ($result.status -eq "DRAFT_SAVED") {
  Write-Host ("GROUP_C_LIVE_DRAFT_PASS product=" + $result.product_name)
} else {
  Write-Host ("GROUP_C_PACKAGE_SAVED_REMAINING_SECTIONS product=" + $result.product_name)
}
Write-Host ("GROUP_C_LIVE_REPORT=" + $liveJson)
