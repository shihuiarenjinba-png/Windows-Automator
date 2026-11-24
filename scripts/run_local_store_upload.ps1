param(
  [Parameter(Mandatory=$true)][string]$ProductInput,
  [Parameter(Mandatory=$true)][string]$IdentityJob,
  [Parameter(Mandatory=$true)][string]$CdpUrl,
  [Parameter(Mandatory=$true)][string]$OutputDir,
  [ValidateSet("ReadOnly","LiveDraft")][string]$Mode = "ReadOnly",
  [switch]$ConfirmLiveDraft,
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ProductInput)) { throw "PRODUCT_INPUT_REQUIRED" }
if ([string]::IsNullOrWhiteSpace($IdentityJob)) { throw "IDENTITY_JOB_REQUIRED" }
if ([string]::IsNullOrWhiteSpace($CdpUrl)) { throw "CDP_URL_REQUIRED" }
if ([string]::IsNullOrWhiteSpace($OutputDir)) { throw "OUTPUT_DIR_REQUIRED" }
if ($Mode -eq "LiveDraft" -and -not $ConfirmLiveDraft) {
  throw "LiveDraft mode requires -ConfirmLiveDraft at action time."
}

$inputPath = (Resolve-Path -LiteralPath $ProductInput -ErrorAction Stop).Path
$identityJobPath = (Resolve-Path -LiteralPath $IdentityJob -ErrorAction Stop).Path
$outRoot = [System.IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $outRoot -Force | Out-Null

try {
  $product = Get-Content -LiteralPath $inputPath -Raw | ConvertFrom-Json -ErrorAction Stop
} catch {
  throw "PRODUCT_INPUT_INVALID_JSON"
}
foreach ($name in @("product_name","store_product_id","identity_name","identity_publisher","package_version","package_path","package_sha256","security_package_sha256","draft_id")) {
  if ([string]::IsNullOrWhiteSpace([string]$product.$name)) { throw "PRODUCT_INPUT_REQUIRED_FIELD:$name" }
}
if ([string]$product.package_sha256 -notmatch '^[0-9a-fA-F]{64}$') { throw "PACKAGE_SHA256_INVALID" }
if ([string]$product.security_package_sha256 -cne [string]$product.package_sha256) { throw "SECURITY_PACKAGE_SHA256_MISMATCH" }
$packagePath = [System.IO.Path]::GetFullPath([string]$product.package_path)
if (-not (Test-Path -LiteralPath $packagePath -PathType Leaf)) { throw "PACKAGE_FILE_NOT_FOUND" }
$actualHash = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash
if ($actualHash -cne [string]$product.package_sha256) { throw "PACKAGE_SHA256_MISMATCH" }

$identityReceipt = Join-Path $outRoot "identity-reverify.json"
$stateReceipt = Join-Path $outRoot "submission-state.json"
$liveJson = Join-Path $outRoot "live-report.json"
$liveMd = Join-Path $outRoot "live-report.md"
$queuePath = Join-Path $outRoot "single-product-queue.json"
$evidenceDir = Join-Path $outRoot "evidence"

Write-Host "LOCAL_STORE_STAGE=IDENTITY_REVERIFY"
& $PythonExe -m store_manager.cli verify-existing-identity --job $identityJobPath --output $identityReceipt --cdp-url $CdpUrl
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$identity = Get-Content -LiteralPath $identityReceipt -Raw | ConvertFrom-Json
if ($identity.status -ne "EXISTING_IDENTITY_EXACT_MATCH" -or [string]$identity.store_id -cne [string]$product.store_product_id -or [string]$identity.identity_name -cne [string]$product.identity_name -or [string]$identity.publisher -cne [string]$product.identity_publisher -or [string]$identity.package_sha256 -cne [string]$product.package_sha256) {
  throw "HOLD_IDENTITY_OR_PACKAGE_BINDING_MISMATCH"
}
if ($identity.created_or_reserved_product -or $identity.submission_started -or $identity.package_uploaded -or $identity.pricing_changed -or $identity.submitted -or $identity.published) {
  throw "READ_ONLY_IDENTITY_STEP_REPORTED_WRITE"
}

Write-Host "LOCAL_STORE_STAGE=EXISTING_DRAFT_RECONCILE"
& $PythonExe -m store_manager.cli inspect-existing-submission-state --input $inputPath --output $stateReceipt --cdp-url $CdpUrl
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$state = Get-Content -LiteralPath $stateReceipt -Raw | ConvertFrom-Json
if ($state.submission_state -ne "EXISTING_PRODUCT_DRAFT_PRESENT" -or [string]$state.store_id -cne [string]$product.store_product_id -or [string]$state.draft_id -cne [string]$product.draft_id) {
  throw "HOLD_EXISTING_DRAFT_BINDING_MISMATCH"
}
if ($state.package_uploaded -or $state.pricing_changed -or $state.submitted -or $state.published) {
  throw "READ_ONLY_DRAFT_STEP_REPORTED_WRITE"
}

if ($Mode -eq "ReadOnly") {
  Write-Host "LOCAL_STORE_STATUS=READ_ONLY_IDENTITY_AND_DRAFT_VERIFIED"
  Write-Host "LOCAL_STORE_DRAFT_ID=$($state.draft_id)"
  exit 0
}

& $PythonExe -m store_manager.cli validate --input $inputPath
if ($LASTEXITCODE -ne 0) { throw "HOLD_PRODUCT_INPUT_VALIDATION" }
@($product) | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $queuePath -Encoding UTF8
if (-not (Test-Path -LiteralPath $queuePath -PathType Leaf)) { throw "QUEUE_FILE_NOT_CREATED" }
$queueText = Get-Content -LiteralPath $queuePath -Raw
if ([string]::IsNullOrWhiteSpace($queueText)) { throw "QUEUE_FILE_EMPTY" }

Write-Host "LOCAL_STORE_STAGE=LIVE_DRAFT_SAVE"
& $PythonExe -m store_manager.cli night-run --queue $queuePath --json-report $liveJson --markdown-report $liveMd --execution-mode live --confirm-live-draft --cdp-url $CdpUrl --evidence-dir $evidenceDir
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$report = Get-Content -LiteralPath $liveJson -Raw | ConvertFrom-Json
if (-not $report.results -or $report.results.Count -ne 1) { throw "HOLD_LIVE_REPORT_SHAPE_UNKNOWN" }
$result = $report.results[0]
if ($result.details.submitted -or $result.details.certified -or $result.details.published) { throw "PROHIBITED_CERTIFICATION_OR_PUBLISH_SIDE_EFFECT" }
if ($result.status -notin @("DRAFT_SAVED","PACKAGE_SAVED_STORE_DRAFT_REMAINING_SECTIONS_REQUIRED")) {
  throw "HOLD_LIVE_DRAFT_NOT_SAVED:$($result.status)"
}
Write-Host "LOCAL_STORE_STATUS=$($result.status)"
Write-Host "LOCAL_STORE_REPORT=$liveJson"
Write-Host "LOCAL_STORE_QUEUE=$queuePath"
