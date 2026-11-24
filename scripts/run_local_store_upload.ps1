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

foreach ($entry in @(
  @{ Name = "ProductInput"; Value = $ProductInput },
  @{ Name = "IdentityJob"; Value = $IdentityJob },
  @{ Name = "CdpUrl"; Value = $CdpUrl },
  @{ Name = "OutputDir"; Value = $OutputDir }
)) {
  if ([string]::IsNullOrWhiteSpace([string]$entry.Value)) {
    throw "$($entry.Name.ToUpperInvariant())_REQUIRED"
  }
}
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
if ($null -eq $product -or $product -is [System.Array]) {
  throw "PRODUCT_INPUT_MUST_BE_ONE_JSON_OBJECT"
}
foreach ($name in @(
  "product_name", "store_product_id", "identity_name", "identity_publisher",
  "package_version", "package_path", "package_sha256", "security_package_sha256", "draft_id"
)) {
  if ([string]::IsNullOrWhiteSpace([string]$product.$name)) {
    throw "PRODUCT_INPUT_REQUIRED_FIELD:$name"
  }
}
if ([string]$product.package_sha256 -notmatch '^[0-9a-fA-F]{64}$') {
  throw "PACKAGE_SHA256_INVALID"
}
if ([string]$product.security_package_sha256 -ine [string]$product.package_sha256) {
  throw "SECURITY_PACKAGE_SHA256_MISMATCH"
}
$packagePath = [System.IO.Path]::GetFullPath([string]$product.package_path)
if (-not (Test-Path -LiteralPath $packagePath -PathType Leaf)) {
  throw "PACKAGE_FILE_NOT_FOUND"
}
$actualHash = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash
if ($actualHash -ine [string]$product.package_sha256) {
  throw "PACKAGE_SHA256_MISMATCH"
}

# OutputDir is a run root. Every invocation gets a unique child directory so a
# retry can never overwrite receipts from an ambiguous previous attempt.
$runId = "{0}-{1}" -f (Get-Date -Format "yyyyMMddTHHmmssfff"), ([guid]::NewGuid().ToString("N"))
$runDir = Join-Path $outRoot $runId
if (Test-Path -LiteralPath $runDir) {
  throw "RUN_DIRECTORY_COLLISION"
}
New-Item -ItemType Directory -Path $runDir -ErrorAction Stop | Out-Null

$identityReceipt = Join-Path $runDir "identity-reverify.json"
$stateReceipt = Join-Path $runDir "submission-state.json"
$liveJson = Join-Path $runDir "live-report.json"
$liveMd = Join-Path $runDir "live-report.md"
$verificationJson = Join-Path $runDir "live-report-verification.json"
$queuePath = Join-Path $runDir "single-product-queue.json"
$evidenceDir = Join-Path $runDir "evidence"
$attemptManifest = Join-Path $runDir "attempt-manifest.json"

$manifest = [ordered]@{
  schema_version = "local-store-upload-attempt/1"
  run_id = $runId
  started_at_utc = [DateTime]::UtcNow.ToString("o")
  mode = $Mode
  product_name = [string]$product.product_name
  store_product_id = [string]$product.store_product_id
  draft_id = [string]$product.draft_id
  package_filename = [System.IO.Path]::GetFileName($packagePath)
  package_path = $packagePath
  package_sha256 = $actualHash.ToLowerInvariant()
  source_sha = [string]$product.source_sha
  source_branch = [string]$product.source_branch
}
if (Test-Path -LiteralPath $attemptManifest) {
  throw "ATTEMPT_MANIFEST_ALREADY_EXISTS"
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $attemptManifest -Encoding UTF8

Write-Host "LOCAL_STORE_RUN_ID=$runId"
Write-Host "LOCAL_STORE_STAGE=IDENTITY_REVERIFY"
& $PythonExe -m store_manager.cli verify-existing-identity --job $identityJobPath --output $identityReceipt --cdp-url $CdpUrl --evidence-dir $evidenceDir
if ($LASTEXITCODE -ne 0) {
  throw "IDENTITY_REVERIFY_FAILED:$LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $identityReceipt -PathType Leaf)) {
  throw "IDENTITY_REVERIFY_RECEIPT_MISSING"
}
$identity = Get-Content -LiteralPath $identityReceipt -Raw | ConvertFrom-Json
if (
  $identity.status -ne "EXISTING_IDENTITY_EXACT_MATCH" -or
  [string]$identity.store_id -cne [string]$product.store_product_id -or
  [string]$identity.identity_name -cne [string]$product.identity_name -or
  [string]$identity.publisher -cne [string]$product.identity_publisher -or
  [string]$identity.package_sha256 -ine [string]$product.package_sha256
) {
  throw "HOLD_IDENTITY_OR_PACKAGE_BINDING_MISMATCH"
}
foreach ($flag in @("created_or_reserved_product", "submission_started", "package_uploaded", "pricing_changed", "submitted", "published")) {
  if ($identity.PSObject.Properties.Name -notcontains $flag -or $identity.$flag -isnot [bool] -or $identity.$flag) {
    throw "READ_ONLY_IDENTITY_STEP_REPORTED_WRITE_OR_MISSING_FLAG:$flag"
  }
}

Write-Host "LOCAL_STORE_STAGE=EXISTING_DRAFT_RECONCILE"
& $PythonExe -m store_manager.cli inspect-existing-submission-state --input $inputPath --output $stateReceipt --cdp-url $CdpUrl --evidence-dir $evidenceDir
if ($LASTEXITCODE -ne 0) {
  throw "EXISTING_DRAFT_RECONCILE_FAILED:$LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $stateReceipt -PathType Leaf)) {
  throw "EXISTING_DRAFT_RECEIPT_MISSING"
}
$state = Get-Content -LiteralPath $stateReceipt -Raw | ConvertFrom-Json
if (
  $state.submission_state -ne "EXISTING_PRODUCT_DRAFT_PRESENT" -or
  [string]$state.store_id -cne [string]$product.store_product_id -or
  [string]$state.draft_id -cne [string]$product.draft_id
) {
  throw "HOLD_EXISTING_DRAFT_BINDING_MISMATCH"
}
foreach ($flag in @("created_or_reserved_product", "submission_started", "start_submission_clicked", "start_update_clicked", "package_uploaded", "pricing_changed", "submitted", "published")) {
  if ($state.PSObject.Properties.Name -notcontains $flag -or $state.$flag -isnot [bool] -or $state.$flag) {
    throw "READ_ONLY_DRAFT_STEP_REPORTED_WRITE_OR_MISSING_FLAG:$flag"
  }
}

if ($Mode -eq "ReadOnly") {
  Write-Host "LOCAL_STORE_STATUS=READ_ONLY_IDENTITY_AND_DRAFT_VERIFIED"
  Write-Host "LOCAL_STORE_DRAFT_ID=$($state.draft_id)"
  Write-Host "LOCAL_STORE_RUN_DIR=$runDir"
  exit 0
}

& $PythonExe -m store_manager.cli validate --input $inputPath
if ($LASTEXITCODE -ne 0) {
  throw "HOLD_PRODUCT_INPUT_VALIDATION:$LASTEXITCODE"
}

# -InputObject preserves the one-element array; piping @($product) would
# enumerate it and may serialize one product as a JSON object instead.
$queueJson = ConvertTo-Json -InputObject @($product) -Depth 40
Set-Content -LiteralPath $queuePath -Value $queueJson -Encoding UTF8
if (-not (Test-Path -LiteralPath $queuePath -PathType Leaf)) {
  throw "QUEUE_FILE_NOT_CREATED"
}
$queueText = Get-Content -LiteralPath $queuePath -Raw
if ([string]::IsNullOrWhiteSpace($queueText)) {
  throw "QUEUE_FILE_EMPTY"
}
try {
  $normalizedQueueText = $queueText.Trim()
  if (
    $normalizedQueueText.Length -lt 2 -or
    -not $normalizedQueueText.StartsWith("[") -or
    -not $normalizedQueueText.EndsWith("]")
  ) {
    throw "QUEUE_ROOT_MUST_BE_JSON_ARRAY"
  }
  # ConvertFrom-Json may enumerate a one-element JSON array as one object.
  # The bracket check proves the serialized root is an array; @() then
  # normalizes the parsed result for safe one-item count/index checks.
  $queueData = @(ConvertFrom-Json -InputObject $normalizedQueueText -ErrorAction Stop)
} catch {
  throw "QUEUE_FILE_INVALID_OR_NOT_ARRAY_JSON"
}
if ($queueData.Count -ne 1) {
  throw "QUEUE_MUST_BE_SINGLE_ITEM_JSON_ARRAY"
}
if (
  [string]$queueData[0].store_product_id -cne [string]$product.store_product_id -or
  [string]$queueData[0].draft_id -cne [string]$product.draft_id -or
  [string]$queueData[0].package_sha256 -ine [string]$product.package_sha256
) {
  throw "QUEUE_PRODUCT_BINDING_MISMATCH"
}

Write-Host "LOCAL_STORE_STAGE=LIVE_DRAFT_SAVE"
& $PythonExe -m store_manager.cli night-run --queue $queuePath --json-report $liveJson --markdown-report $liveMd --execution-mode live --confirm-live-draft --cdp-url $CdpUrl --evidence-dir $evidenceDir
if ($LASTEXITCODE -ne 0) {
  throw "LIVE_DRAFT_RUN_FAILED:$LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $liveJson -PathType Leaf)) {
  throw "LIVE_REPORT_MISSING"
}

# The CLI verifier checks the flattened QueueReport fields, immutable target
# binding, all required safety booleans, and the package hash again after upload.
Write-Host "LOCAL_STORE_STAGE=VERIFY_LIVE_RECEIPT"
& $PythonExe -m store_manager.cli verify-live-report --report $liveJson --input $inputPath --output $verificationJson
if ($LASTEXITCODE -ne 0) {
  throw "HOLD_LIVE_REPORT_VERIFICATION_FAILED:$LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $verificationJson -PathType Leaf)) {
  throw "LIVE_REPORT_VERIFICATION_RECEIPT_MISSING"
}
$verification = Get-Content -LiteralPath $verificationJson -Raw | ConvertFrom-Json
Write-Host "LOCAL_STORE_STATUS=$($verification.result_status)"
Write-Host "LOCAL_STORE_RUN_DIR=$runDir"
Write-Host "LOCAL_STORE_REPORT=$liveJson"
Write-Host "LOCAL_STORE_VERIFICATION=$verificationJson"
Write-Host "LOCAL_STORE_QUEUE=$queuePath"
