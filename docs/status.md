# 当前开发状态

## Windows

已完成：

- 后台/托盘运行。
- 默认隐藏设置窗口。
- 底部一行字幕条，用于视频和音频字幕。
- 可双击字幕条打开设置。
- 显示原文开关。
- 屏幕文字翻译的文字块覆盖窗口，基于 Tesseract 行级坐标贴近原文字位置。
- 屏幕区域框选。
- 系统播放音频 loopback 设备选择。
- Tesseract OCR 本地语言包。
- OCR 引擎抽象入口，当前默认 Tesseract。
- OCR 文字块坐标合并测试。
- PyInstaller 本机打包已通过，产物为 `dist/windows/奶龙实时翻译.exe`。

待继续：

- 增加 PaddleOCR 或 Windows OCR 作为第二 OCR 引擎，提高中文/日韩准确率。
- 继续优化文字覆盖的稳定跟踪和遮挡避让。
- 预下载 Whisper 模型，避免第一次使用等待。
- 继续完善 Windows 安装包、自动更新和签名。

## Android

已完成：

- 原生 Kotlin 工程。
- 授权页。
- 悬浮窗权限入口。
- MediaProjection 屏幕捕获授权入口。
- Foreground Service 后台运行。
- 屏幕底部一行悬浮字幕。
- ML Kit 屏幕帧 OCR：中文、日文、韩文、拉丁文字。
- ML Kit Translate：中文、英语、日语、韩语、德语、法语、俄语目标语言切换。
- ML Kit Language ID：自动识别源语言，改善拉丁文字语言判断。
- AudioPlaybackCapture：捕获 Android 媒体/游戏播放音频。
- AudioSubtitleEngine：支持 OpenAI Whisper 兼容 HTTP 转写接口。
- 保存目标语言、是否显示原文、语音转写接口和 API Key，下次打开会自动沿用。
- 原文显示开关：关闭时悬浮字幕只显示译文，开启时显示原文和译文。
- 文字覆盖模式：把 OCR 识别到的屏幕文字块翻译后显示在原位置附近。

待继续：

- 安装 Android SDK 并构建 APK。
- 评估 PaddleOCR Android 作为复杂场景增强。
- 增强 Android 端侧语音识别，减少对网络接口的依赖。
- 将文字覆盖从最多 6 个文字块升级到更精细的逐行覆盖、遮挡避让和稳定跟踪。

## GitHub

仓库目标：`yingchunchen924/nailong-realtime-translator`

本机尚未登录 GitHub CLI。推送前需要完成登录或提供可用 Git 凭据。
