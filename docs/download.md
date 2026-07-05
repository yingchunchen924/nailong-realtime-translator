# 下载安装

当前可下载版本：v0.1.6

下载页面：

https://github.com/yingchunchen924/nailong-realtime-translator/releases/tag/v0.1.6

## Windows 电脑

下载 `nailong-windows.zip`，解压后运行里面的 `奶龙实时翻译.exe`。

双击启动后会先显示设置窗口。选择语言、检测方式和显示方式后，点击“开始实时翻译”，屏幕上才会显示字幕条。

字幕条会保持在屏幕最上层，可以拖动位置；右键字幕条可打开设置、隐藏字幕条、停止翻译或退出软件。字幕条右上角的“×”只隐藏字幕条，不会强制退出软件。

设置页里的“开机自启”可以让软件随 Windows 登录后自动后台运行。

## Android 手机

下载 `nailong-android-debug.zip`，解压后安装里面的 APK。

首次打开需要授予悬浮窗、屏幕捕获、通知等权限。开启后，手机屏幕上只保留底部一行字幕；文字覆盖模式会把识别到的屏幕文字翻译后贴近原位置显示。

## 已包含的下载包

- `nailong-windows.zip`：Windows 电脑端。
- `nailong-android-debug.zip`：Android 手机端调试 APK。
- `nailong-realtime-translator-source.zip`：当前版本源码。

## 当前限制

- Android 语音字幕需要配置 Whisper 兼容 HTTP 转写接口后使用。
- Windows 首次使用语音识别时会下载 Whisper 模型，速度取决于网络。
- 手机端仍建议在真机上按机型测试悬浮窗、音频捕获和屏幕识别权限。
