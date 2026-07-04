# 当前开发状态

## Windows

已完成：

- 后台/托盘运行。
- 默认隐藏设置窗口。
- 底部一行字幕条，用于视频和音频字幕。
- 可双击字幕条打开设置。
- 显示原文开关。
- 屏幕文字翻译的区域级覆盖窗口。
- 屏幕区域框选。
- 系统播放音频 loopback 设备选择。
- Tesseract OCR 本地语言包。
- OCR 引擎抽象入口，当前默认 Tesseract。

待继续：

- 增加 PaddleOCR 或 Windows OCR 作为第二 OCR 引擎，提高中文/日韩准确率。
- 文本覆盖从区域级提升到逐行/逐块坐标。
- 预下载 Whisper 模型，避免第一次使用等待。
- PyInstaller 打包成 exe。

## Android

已完成：

- 原生 Kotlin 工程。
- 授权页。
- 悬浮窗权限入口。
- MediaProjection 屏幕捕获授权入口。
- Foreground Service 后台运行。
- 屏幕底部一行悬浮字幕。
- ML Kit 屏幕帧 OCR：中文、日文、韩文、拉丁文字。
- ML Kit Translate：基础中文/英语目标语言切换。

待继续：

- 安装 Android SDK 并构建 APK。
- 评估 PaddleOCR Android 作为复杂场景增强。
- 扩展 Android 目标语言列表到日语、韩语、德语、法语、俄语等。
- 接入 Android 音频捕获/语音识别。
- 接入音频捕获/语音识别。

## GitHub

仓库目标：`yingchunchen924/nailong-realtime-translator`

本机尚未登录 GitHub CLI。推送前需要完成登录或提供可用 Git 凭据。
