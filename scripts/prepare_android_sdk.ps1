$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

[array]$sdkCandidates = @(
    $env:ANDROID_HOME,
    $env:ANDROID_SDK_ROOT,
    "D:\Android\Sdk",
    "${env:LOCALAPPDATA}\Android\Sdk"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

if (-not $sdkCandidates) {
    throw "Android SDK not found. Install Android Studio SDK first."
}

$sourceSdk = [string]$sdkCandidates[0]
$targetSdk = $sourceSdk

if (-not (Test-Path (Join-Path $sourceSdk "platforms\android-36"))) {
    $minorPlatform = Join-Path $sourceSdk "platforms\android-36.1"
    if (Test-Path $minorPlatform) {
        $compatSdk = Join-Path $repoRoot "build\android-sdk-compat"
        New-Item -ItemType Directory -Force -Path `
            (Join-Path $compatSdk "platforms"), `
            (Join-Path $compatSdk "build-tools"), `
            (Join-Path $compatSdk "licenses"), `
            (Join-Path $compatSdk "platform-tools") | Out-Null

        $compatPlatform = Join-Path $compatSdk "platforms\android-36"
        if (-not (Test-Path $compatPlatform)) {
            Copy-Item -LiteralPath $minorPlatform -Destination $compatPlatform -Recurse -Force
        }

        $packageXml = Join-Path $compatPlatform "package.xml"
        if (Test-Path $packageXml) {
            $packageText = Get-Content -LiteralPath $packageXml -Raw
            $packageText = $packageText -replace "platforms;android-36\.1", "platforms;android-36"
            $packageText = $packageText -replace "<api-level>36\.1</api-level>", "<api-level>36</api-level>"
            Set-Content -LiteralPath $packageXml -Value $packageText -Encoding UTF8
        }

        $sourceProperties = Join-Path $compatPlatform "source.properties"
        if (Test-Path $sourceProperties) {
            $sourceText = Get-Content -LiteralPath $sourceProperties -Raw
            $sourceText = $sourceText -replace "AndroidVersion.ApiLevel=36\.1", "AndroidVersion.ApiLevel=36"
            Set-Content -LiteralPath $sourceProperties -Value $sourceText -Encoding ASCII
        }

        $buildToolsSource = Join-Path $sourceSdk "build-tools\36.1.0"
        if (Test-Path $buildToolsSource) {
            Copy-Item -LiteralPath $buildToolsSource -Destination (Join-Path $compatSdk "build-tools\36.1.0") -Recurse -Force
        }

        $platformToolsSource = Join-Path $sourceSdk "platform-tools"
        if (Test-Path $platformToolsSource) {
            Copy-Item -Path (Join-Path $platformToolsSource "*") -Destination (Join-Path $compatSdk "platform-tools") -Recurse -Force
        }

        $licensesSource = Join-Path $sourceSdk "licenses"
        if (Test-Path $licensesSource) {
            Copy-Item -Path (Join-Path $licensesSource "*") -Destination (Join-Path $compatSdk "licenses") -Recurse -Force
        }

        $targetSdk = $compatSdk
    }
}

$localProperties = Join-Path $repoRoot "local.properties"
"sdk.dir=$($targetSdk -replace '\\','/')" | Set-Content -Encoding ASCII $localProperties
Write-Host "Android SDK prepared: $targetSdk"
