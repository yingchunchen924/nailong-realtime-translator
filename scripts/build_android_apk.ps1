$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

& (Join-Path $PSScriptRoot "prepare_android_sdk.ps1")

$localProperties = Join-Path $repoRoot "local.properties"
$sdkLine = Get-Content -LiteralPath $localProperties | Where-Object { $_ -like "sdk.dir=*" } | Select-Object -First 1
if (-not $sdkLine) {
    throw "local.properties does not contain sdk.dir"
}

$sdk = ($sdkLine -replace "^sdk\.dir=", "") -replace "/", "\"
$env:ANDROID_HOME = $sdk
$env:ANDROID_SDK_ROOT = $sdk

$androidStudioJbr = "D:\Android\jbr"
if (Test-Path $androidStudioJbr) {
    $env:JAVA_HOME = $androidStudioJbr
    $env:PATH = "$androidStudioJbr\bin;$env:PATH"
}

$env:PATH = "$sdk\platform-tools;$sdk\cmdline-tools\latest\bin;$sdk\tools\bin;$env:PATH"

if (Test-Path (Join-Path $repoRoot "gradlew.bat")) {
    & (Join-Path $repoRoot "gradlew.bat") ":apps:android:assembleDebug"
    exit $LASTEXITCODE
}

$gradleBat = Get-ChildItem "$env:USERPROFILE\.gradle\wrapper\dists" -Recurse -Filter gradle.bat -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($gradleBat) {
    & $gradleBat.FullName ":apps:android:assembleDebug" "--no-daemon"
    exit $LASTEXITCODE
}

& gradle ":apps:android:assembleDebug"
exit $LASTEXITCODE
