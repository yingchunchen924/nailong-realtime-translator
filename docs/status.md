# 当前开发状态

## Windows

已完成：

- 后台和托盘运行。
- 默认隐藏设置窗口，只显示底部一行字幕。
- 双击字幕条打开设置。
- 可选择字幕条模式或文字覆盖模式。
- 可选择是否显示原文。
- Tesseract 行级 OCR，能把屏幕文字识别为多个文字块。
- 文字覆盖窗口能把译文贴近原文字位置显示，并减少同一画面重复重建造成的闪烁。
- 屏幕区域框选。
- 系统播放音频 loopback 设备选择。
- 自动保存并恢复语言、检测模式、显示方式、刷新间隔、语音模型、音频设备和屏幕区域。
- Windows exe 本机打包通过。

待继续：

- 增加 PaddleOCR 或 Windows OCR 作为第二 OCR 引擎，提高中日韩复杂画面准确率。
- 继续优化文字覆盖的遮挡避让、滚动页面表现和更复杂排版。
- 预下载或内置语音识别模型，减少首次使用等待。
- 完善 Windows 安装包、自动更新和签名。

## Android

已完成：

- 原生 Kotlin 工程。
- 悬浮窗权限入口。
- MediaProjection 屏幕捕获授权入口。
- Foreground Service 后台运行。
- 底部一行悬浮字幕。
- ML Kit OCR：中文、日文、韩文、拉丁文字。
- ML Kit Translate：中文、英语、日语、韩语、德语、法语、俄语目标语言切换。
- ML Kit Language ID 自动识别源语言。
- AudioPlaybackCapture 捕获 Android 媒体和游戏播放音频。
- Whisper 兼容 HTTP 转写接口。
- 保存目标语言、是否显示原文、文字覆盖模式、转写接口、模型名和 API Key。
- 文字覆盖模式：把 OCR 识别到的最多 10 个屏幕文字块翻译后显示到原位置附近，并减少同一画面重复重建造成的闪烁。
- 前台通知“停止”按钮，能关闭后台翻译、音频捕获和悬浮层。
- Android debug APK 本机构建通过。

待继续：

- 在真机上安装 APK 做权限、悬浮窗、音频捕获和 OCR 实测。
- 增强 Android 端侧语音识别，减少对网络转写接口的依赖。
- 将文字覆盖继续升级为更细的逐行覆盖、遮挡避让和稳定跟踪。
- 做正式签名 APK 或安装包发布流程。

## GitHub

目标仓库：

```text
yingchunchen924/nailong-realtime-translator
```

当前 `main` 分支已成功推送到 GitHub。仓库包含 Windows 和 Android 的 GitHub Actions 构建流程。
