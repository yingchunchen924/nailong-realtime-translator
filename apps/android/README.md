# 奶龙实时翻译 Android 端

这是 Android 原生端工程。

## 当前能力

- 启动页只负责授权和开关，不长期占用前台。
- 申请悬浮窗权限。
- 申请录音/通知权限。
- 使用 MediaProjection 请求屏幕捕获权限。
- 启动前台服务后台运行。
- 使用 WindowManager 在屏幕底部显示一行悬浮字幕。

## 后续识别引擎

屏幕文字建议接入：

- ML Kit Text Recognition v2
- 或 PaddleOCR Android

音频字幕建议接入：

- Android AudioPlaybackCaptureConfiguration，受 App 是否允许捕获限制
- 或麦克风识别
- 或服务端 Whisper API

## 构建

用 Android Studio 打开仓库根目录 `nailong-realtime-translator`，等待 Gradle 同步后运行 `apps:android`。

本机当前未检测到 Android SDK，所以暂未生成 APK。
