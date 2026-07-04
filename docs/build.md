# 构建说明

## Windows

```bat
apps\windows\install_dependencies.bat
apps\windows\build_exe.bat
```

产物位置：

```text
dist\windows\奶龙实时翻译.exe
```

本机验证：

```bat
python -m py_compile apps\windows\app.py
pytest -q tests\test_windows_ocr_blocks.py
```

## Android

先确认 Android Studio 和 SDK 已安装。本机已验证 SDK 位于：

```text
C:\Users\hp\AppData\Local\Android\Sdk
```

如果只安装了 `android-36.1` 平台，脚本会自动在用户文档目录创建一个兼容 SDK 镜像：

```text
C:\Users\hp\Documents\Codex\android-sdk-compat
```

命令行构建：

```bat
apps\android\build_apk.bat
```

也可以直接运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_android_apk.ps1
```

产物位置：

```text
apps\android\build\outputs\apk\debug\android-debug.apk
```

本机已通过 `:apps:android:assembleDebug`，发布目录中也已生成：

```text
outputs\nailong-realtime-translator-release\nailong-android-debug.apk
outputs\nailong-realtime-translator-release\nailong-android-debug.zip
```
