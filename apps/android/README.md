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
- 首次使用某个语言方向时，系统会下载对应翻译模型。

## 后续增强

屏幕文字已接入 ML Kit Text Recognition v2。复杂排版、游戏字幕和中文准确率后续可继续评估 PaddleOCR Android。

音频字幕和更细的源语言自动识别后续继续接入。

音频字幕建议接入：

- Android AudioPlaybackCaptureConfiguration，受 App 是否允许捕获限制
- 或麦克风识别
- 或服务端 Whisper API

## 构建

用 Android Studio 打开仓库根目录 `nailong-realtime-translator`，等待 Gradle 同步后运行 `apps:android`。

本机当前未检测到 Android SDK，所以暂未生成 APK。
