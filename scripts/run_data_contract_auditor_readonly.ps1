#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$PackagePath = "$HOME\Desktop\DataContractAuditor-QA\store-output\20261123-120600-f88e492e\DataContractSchemaDrift_1.0.0.0_x64.msix",
    [string]$CdpUrl = "http://127.0.0.1:9222",
    [string]$OutputDir = "",
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RunningOnWindows = ($env:OS -eq "Windows_NT") -or ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT)
if (-not $RunningOnWindows) { throw "Windows only" }

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $Root

$ExpectedPackageSha = "4b373d2bc54ecbd3efa0a77a94005007777e66d641fa3908f523ac69fcd46984"
$ExpectedSourceSha = "5a09d81955e25664761ea25ecfb4ebf8d24cea6d"
$ExpectedStoreId = "9PDL4ZWSB45P"
$ExpectedDraftId = "1152921505702212222"
$ExpectedIdentity = "OkinawaDesktopTools.DataContractAuditor"
$ExpectedPublisher = "CN=46263F21-A700-41DB-8C9B-114C22FB82FC"
$ExpectedPfn = "OkinawaDesktopTools.DataContractAuditor_j8yefg9jgfh58"
$ExpectedPackageSid = "S-1-15-2-1604001028-3538366582-1604686486-898744028-3049784359-1003679317-2779270623"

if (-not (Test-Path -LiteralPath $PackagePath -PathType Leaf)) {
    throw "Formal Data Contract Auditor MSIX not found: $PackagePath"
}
$ResolvedPackage = (Resolve-Path -LiteralPath $PackagePath).Path
$ActualPackageSha = (Get-FileHash -LiteralPath $ResolvedPackage -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualPackageSha -cne $ExpectedPackageSha) {
    throw "HOLD_PACKAGE_SHA_MISMATCH expected=$ExpectedPackageSha actual=$ActualPackageSha"
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
    $PythonExe = if (Test-Path -LiteralPath $VenvPython -PathType Leaf) { $VenvPython } else { "python" }
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $Base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $env:TEMP }
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputDir = Join-Path $Base ("OkinawaDesktopTools\DataContractAuditor\partner-center-readonly\" + $Stamp)
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path

try {
    $CdpProbe = Invoke-RestMethod -Uri ($CdpUrl.TrimEnd("/") + "/json/version") -TimeoutSec 5
} catch {
    throw "PARTNER_CENTER_CDP_UNAVAILABLE: Start the authenticated Partner Center Edge CDP session, then rerun. $($_.Exception.Message)"
}
if (-not $CdpProbe.webSocketDebuggerUrl) {
    throw "PARTNER_CENTER_CDP_UNAVAILABLE: CDP endpoint did not expose webSocketDebuggerUrl."
}

$ProductPath = Join-Path $OutputDir "data-contract-auditor-formal-product-input.json"
$IdentityJobPath = Join-Path $OutputDir "data-contract-auditor-identity-reverify-job.json"

$Product = [ordered]@{
    product_type = "app"
    product_name = "Data Contract Auditor"
    app_summary = "Local Windows CSV and Excel data-contract comparison tool. Original input files are not modified."
    repository = "shihuiarenjinba-png/csv-import-validator"
    package_path = $ResolvedPackage
    store_product_id = $ExpectedStoreId
    submission_kind = "new"
    submission_route = "msix_pwa_app"
    submission_route_source = "upstream"
    package_type = "msix"
    package_sha256 = $ExpectedPackageSha
    source_sha = $ExpectedSourceSha
    source_branch = "codex/store-p0-data-contract-20261023"
    identity_name = $ExpectedIdentity
    identity_publisher = $ExpectedPublisher
    package_version = "1.0.0.0"
    checker_status = "FORMAL_UNSIGNED_MSIX_CREATED_AND_VERIFIED"
    human_local_qa_pass = $true
    draft_id = $ExpectedDraftId
    certification_gate = "HOLD"
}
$Product | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $ProductPath -Encoding UTF8

$IdentityJob = [ordered]@{
    schema_version = "existing-store-identity-reverify/1"
    source_sha = $ExpectedSourceSha
    package_sha256 = $ExpectedPackageSha
    expected = [ordered]@{
        product_name = "Data Contract Auditor"
        store_id = $ExpectedStoreId
        identity_name = $ExpectedIdentity
        publisher = $ExpectedPublisher
        package_family_name = $ExpectedPfn
        package_sid = $ExpectedPackageSid
    }
    permissions = [ordered]@{
        read_partner_center = $true
        create_product = $false
        start_submission = $false
        upload_package = $false
        edit_pricing = $false
        submit_certification = $false
        publish = $false
    }
}
$IdentityJob | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $IdentityJobPath -Encoding UTF8

$Teacher = Join-Path $PSScriptRoot "run_group_c_store_teacher.ps1"
$TeacherArgs = @{
    ProductInput = $ProductPath
    IdentityJob = $IdentityJobPath
    CdpUrl = $CdpUrl
    OutputDir = $OutputDir
    Mode = "ReadOnly"
    PythonExe = $PythonExe
}
& $Teacher @TeacherArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "DATA_CONTRACT_PARTNER_CENTER_READONLY=PASS"
Write-Host "STORE_ID=$ExpectedStoreId"
Write-Host "DRAFT_ID=$ExpectedDraftId"
Write-Host "SOURCE_SHA=$ExpectedSourceSha"
Write-Host "PACKAGE_SHA256=$ExpectedPackageSha"
Write-Host "OUTPUT_DIR=$OutputDir"
Write-Host "PACKAGE_UPLOAD=NOT_EXECUTED"
Write-Host "CERTIFICATION=NOT_EXECUTED"
Write-Host "PUBLISH=NOT_EXECUTED"
