# 奶龙实时翻译

奶龙实时翻译是一款后台运行的实时翻译工具，目标覆盖 Windows 电脑端和 Android 手机端。

## 产品目标

- 视频/音频内容：实时识别播放声音，生成一行悬浮字幕。
- 屏幕文字内容：识别屏幕上显示的文字，把译文覆盖到原位置附近。
- 可选择是否显示原文。
- 支持中文与英语、日语、韩语、德语、法语、俄语等常见语言互译。
- Windows 端后台运行，主界面不占屏；Android 端使用悬浮窗服务。

## 当前工程

- `apps/windows`：Windows 桌面端，Python 实现。
- `apps/android`：Android 原生端，Kotlin/Gradle 工程。
- `assets`：奶龙图标资源。
- `tessdata`：Tesseract OCR 语言包。

## Windows 运行

```bat
apps\windows\start.bat
```

启动后默认进入后台，只显示字幕条。系统托盘菜单可打开设置、暂停翻译或退出。

Windows 端可在设置里切换“字幕条 / 文字覆盖”。文字覆盖模式会使用 Tesseract 的行级坐标，把屏幕文字翻译成多个小浮层并放到原文字附近；“显示原文”开启时会同时显示原文和译文。

## Android

Android 端正在按原生悬浮窗方案实现：

- MediaProjection 捕获屏幕文字。
- Foreground Service 后台运行。
- WindowManager 显示一行字幕/文字覆盖。
- ML Kit 识别屏幕帧文字，当前先显示识别原文。
- ML Kit on-device Translate 支持中文、英语、日语、韩语、德语、法语、俄语目标语言切换。
- ML Kit Language ID 用于自动识别源语言，改善英语、德语、法语等拉丁文字语言区分。
- Android 已接入系统播放音频捕获管线，并预留语音字幕引擎接口。
- Android 音频字幕可配置 OpenAI Whisper 兼容 HTTP 转写接口。
- Android 会保存目标语言、是否显示原文、语音转写接口和 API Key。
- 原文显示关闭时只显示译文，开启时显示原文和译文。
- Android 可开启文字覆盖模式，把 OCR 识别到的屏幕文字块翻译后覆盖到原位置附近。
- 后续继续优化端侧语音识别。
