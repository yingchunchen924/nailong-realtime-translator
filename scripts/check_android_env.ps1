$ErrorActionPreference = "SilentlyContinue"

$sdkCandidates = @(
    $env:ANDROID_HOME,
    $env:ANDROID_SDK_ROOT,
    "D:\Android\Sdk",
    "$env:LOCALAPPDATA\Android\Sdk"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

if (-not $sdkCandidates) {
    Write-Host "Android SDK: not found"
    exit 1
}

$sdk = $sdkCandidates[0]
Write-Host "Android SDK: $sdk"

$adb = Join-Path $sdk "platform-tools\adb.exe"
$sdkManager = Join-Path $sdk "cmdline-tools\latest\bin\sdkmanager.bat"

Write-Host ("adb: " + ($(if (Test-Path $adb) { $adb } else { "not found" })))
Write-Host ("sdkmanager: " + ($(if (Test-Path $sdkManager) { $sdkManager } else { "not found" })))

$gradle = Get-Command gradle -ErrorAction SilentlyContinue
Write-Host ("gradle: " + ($(if ($gradle) { $gradle.Source } else { "not found" })))

$localProperties = Join-Path (Resolve-Path ".").Path "local.properties"
"sdk.dir=$($sdk -replace '\\','/')" | Set-Content -Encoding ASCII $localProperties
Write-Host "local.properties updated: $localProperties"
