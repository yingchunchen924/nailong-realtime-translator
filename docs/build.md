# 构建说明

## Windows

```bat
apps\windows\install_dependencies.bat
apps\windows\build_exe.bat
```

脚本会把 PyInstaller 的临时用户目录和配置目录放在 `apps\windows\build` 内，避免受系统用户目录权限影响。

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

推荐用 Android Studio 打开仓库根目录并运行 `apps:android`。

命令行构建：

```bat
apps\android\build_apk.bat
```

产物位置：

```text
apps\android\build\outputs\apk\debug\android-debug.apk
```

Android 构建需要本机安装 Android SDK。GitHub Actions 会在云端自动准备 SDK。

仓库没有提交 Gradle Wrapper，Android CI 会通过 `gradle/actions/setup-gradle` 安装 Gradle 8.10.2 后执行构建。
