@echo off
cd /d "%~dp0\..\.."

if not defined ANDROID_HOME (
  if exist "D:\Android\Sdk" set "ANDROID_HOME=D:\Android\Sdk"
)
if not defined ANDROID_SDK_ROOT (
  if defined ANDROID_HOME set "ANDROID_SDK_ROOT=%ANDROID_HOME%"
)
if defined ANDROID_HOME (
  echo sdk.dir=%ANDROID_HOME:\=/%> local.properties
  set "PATH=%ANDROID_HOME%\platform-tools;%ANDROID_HOME%\cmdline-tools\latest\bin;%ANDROID_HOME%\tools\bin;%PATH%"
)

if exist "gradlew.bat" (
  call gradlew.bat :apps:android:assembleDebug
) else (
  gradle :apps:android:assembleDebug
)
pause
