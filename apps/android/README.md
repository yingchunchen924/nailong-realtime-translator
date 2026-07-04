# 奶龙实时翻译 Android 端

这是 Android 原生端工程，用于在手机上后台运行实时翻译服务。

## 当前能力

- 启动页只负责授权和开关，不长期占用前台。
- 申请悬浮窗权限、录音权限、通知权限和屏幕捕获权限。
- 使用 Foreground Service 在后台运行。
- 使用 WindowManager 显示屏幕底部一行悬浮字幕。
- 支持字幕条模式和屏幕文字覆盖模式。
- 使用 ML Kit Text Recognition v2 做屏幕 OCR：中文、日文、韩文、拉丁文字。
- 使用 ML Kit Language ID 自动判断源语言。
- 使用 ML Kit Translate 翻译为中文、英语、日语、韩语、德语、法语、俄语。
- 使用 AudioPlaybackCapture 捕获手机当前播放的媒体或游戏音频。
- `AudioSubtitleEngine` 支持 OpenAI Whisper 兼容 HTTP 转写接口。
- 不填写 API Key 时，音频捕获会运行，但只显示监听状态。
- 保存目标语言、是否显示原文、文字覆盖模式、语音转写接口和 API Key。
- 原文显示关闭时只显示译文，开启时显示原文和译文。
- 前台通知带有“停止”按钮，可直接关闭后台翻译、音频捕获和悬浮层。

## 后续增强

- 在真机上继续验证不同品牌手机的悬浮窗、通知和屏幕捕获权限流程。
- 将文字覆盖从最多 6 个文字块升级为更精细的逐行覆盖、遮挡避让和稳定跟踪。
- 继续评估端侧语音识别，减少对网络转写接口的依赖。
- 评估 PaddleOCR Android 作为复杂场景增强。

## 构建

本机一键构建：

```bat
apps\android\build_apk.bat
```

PowerShell 构建：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_android_apk.ps1
```

GitHub Actions 会在推送到 `main` 后构建 `nailong-android-debug.zip`。
