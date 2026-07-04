# 奶龙实时翻译 Android 端

这是 Android 原生端工程。

## 当前能力

- 启动页只负责授权和开关，不长期占用前台。
- 申请悬浮窗权限。
- 申请录音/通知权限。
- 使用 MediaProjection 请求屏幕捕获权限。
- 启动前台服务后台运行。
- 使用 WindowManager 在屏幕底部显示一行悬浮字幕。
- 使用 ML Kit 对屏幕帧进行中文、日文、韩文、拉丁文字 OCR。
- 使用 ML Kit Translate 把识别文本翻译为中文、英语、日语、韩语、德语、法语、俄语。
- 使用 ML Kit Language ID 自动判断源语言。
- 使用 AudioPlaybackCapture 捕获手机当前播放的媒体/游戏音频。
- `AudioSubtitleEngine` 支持 OpenAI Whisper 兼容 HTTP 转写接口。
- 不填写 API Key 时，音频捕获会运行但只显示监听状态。
- 会保存目标语言、是否显示原文、语音转写接口和 API Key。
- 原文显示关闭时只显示译文，开启时显示原文和译文。
- 文字覆盖模式会把 OCR 识别到的屏幕文字块翻译后显示在原位置附近。
- 前台通知带有“停止”按钮，可直接关闭后台翻译、音频捕获和悬浮层。
- 首次使用某个语言方向时，系统会下载对应翻译模型。

## 后续增强

屏幕文字已接入 ML Kit Text Recognition v2。复杂排版、游戏字幕和中文准确率后续可继续评估 PaddleOCR Android。

当前文字覆盖会优先选择屏幕上方到下方的前 6 个文字块，后续可继续升级为更精细的逐行覆盖和避让算法。

音频捕获和 Whisper HTTP 转写已接入；端侧语音识别后续继续优化。

音频字幕建议接入：

- Android AudioPlaybackCaptureConfiguration，受 App 是否允许捕获限制
- 或麦克风识别
- 或服务端 Whisper API

## 构建

用 Android Studio 打开仓库根目录 `nailong-realtime-translator`，等待 Gradle 同步后运行 `apps:android`。

本机当前未检测到 Android SDK，所以暂未生成 APK。

GitHub Actions 会显式安装 Gradle 8.10.2，并在云端构建 debug APK。
