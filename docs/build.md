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
