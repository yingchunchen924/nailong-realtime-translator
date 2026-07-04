package com.nailong.realtimetranslator

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

class MainActivity : Activity() {
    private lateinit var projectionManager: MediaProjectionManager
    private lateinit var preferences: SharedPreferences
    private var targetIndex = 0
    private var showOriginal = false
    private var textOverlayMode = false
    private lateinit var targetButton: Button
    private lateinit var originalButton: Button
    private lateinit var textOverlayButton: Button
    private lateinit var sttEndpointInput: EditText
    private lateinit var sttApiKeyInput: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        projectionManager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        preferences = getSharedPreferences(AppSettings.PREFS_NAME, Context.MODE_PRIVATE)
        loadSettings()
        buildUi()
    }

    override fun onPause() {
        super.onPause()
        if (::sttEndpointInput.isInitialized && ::sttApiKeyInput.isInitialized) {
            saveSettings()
        }
    }

    private fun buildUi() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(48, 80, 48, 48)
        }

        val title = TextView(this).apply {
            text = "奶龙实时翻译"
            textSize = 28f
            gravity = Gravity.CENTER
        }
        val subtitle = TextView(this).apply {
            text = "后台运行，只在屏幕上显示一行字幕或译文覆盖。"
            textSize = 15f
            gravity = Gravity.CENTER
            setPadding(0, 18, 0, 28)
        }

        val overlayButton = Button(this).apply {
            text = "授权悬浮字幕"
            setOnClickListener { requestOverlayPermission() }
        }
        targetButton = Button(this).apply {
            text = targetButtonText()
            setOnClickListener { toggleTargetLanguage() }
        }
        originalButton = Button(this).apply {
            text = originalButtonText()
            setOnClickListener { toggleShowOriginal() }
        }
        textOverlayButton = Button(this).apply {
            text = textOverlayButtonText()
            setOnClickListener { toggleTextOverlayMode() }
        }
        sttEndpointInput = EditText(this).apply {
            hint = "语音转写接口（OpenAI Whisper 兼容）"
            setSingleLine(true)
            setText(preferences.getString(AppSettings.KEY_STT_ENDPOINT, WhisperHttpAudioSubtitleEngine.DEFAULT_ENDPOINT))
        }
        sttApiKeyInput = EditText(this).apply {
            hint = "语音转写 API Key（不填则只监听音频）"
            setSingleLine(true)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            setText(preferences.getString(AppSettings.KEY_STT_API_KEY, ""))
        }
        val screenButton = Button(this).apply {
            text = "开始屏幕/音频翻译"
            setOnClickListener { requestProjection() }
        }
        val stopButton = Button(this).apply {
            text = "停止后台翻译"
            setOnClickListener { stopService(Intent(this@MainActivity, FloatingTranslateService::class.java)) }
        }

        root.addView(title)
        root.addView(subtitle)
        root.addView(overlayButton, buttonParams())
        root.addView(targetButton, buttonParams())
        root.addView(originalButton, buttonParams())
        root.addView(textOverlayButton, buttonParams())
        root.addView(sttEndpointInput, buttonParams())
        root.addView(sttApiKeyInput, buttonParams())
        root.addView(screenButton, buttonParams())
        root.addView(stopButton, buttonParams())
        setContentView(ScrollView(this).apply { addView(root) })

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS, Manifest.permission.RECORD_AUDIO), 12)
        } else {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 12)
        }
    }

    private fun buttonParams(): LinearLayout.LayoutParams {
        return LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = 18 }
    }

    private fun requestOverlayPermission() {
        if (!Settings.canDrawOverlays(this)) {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")
            )
            startActivity(intent)
        }
    }

    private fun requestProjection() {
        if (!Settings.canDrawOverlays(this)) {
            requestOverlayPermission()
            return
        }
        startActivityForResult(projectionManager.createScreenCaptureIntent(), REQUEST_PROJECTION)
    }

    private fun toggleTargetLanguage() {
        targetIndex = (targetIndex + 1) % TARGET_LANGUAGES.size
        targetButton.text = targetButtonText()
        saveSettings()
    }

    private fun toggleShowOriginal() {
        showOriginal = !showOriginal
        originalButton.text = originalButtonText()
        saveSettings()
    }

    private fun toggleTextOverlayMode() {
        textOverlayMode = !textOverlayMode
        textOverlayButton.text = textOverlayButtonText()
        saveSettings()
    }

    private fun targetButtonText(): String {
        return "目标语言：${TARGET_LANGUAGES[targetIndex].label}"
    }

    private fun originalButtonText(): String {
        return if (showOriginal) "原文显示：开启" else "原文显示：关闭"
    }

    private fun textOverlayButtonText(): String {
        return if (textOverlayMode) "文字覆盖：开启" else "文字覆盖：关闭"
    }

    private fun loadSettings() {
        targetIndex = preferences.getInt(AppSettings.KEY_TARGET_INDEX, 0)
            .coerceIn(0, TARGET_LANGUAGES.lastIndex)
        showOriginal = preferences.getBoolean(AppSettings.KEY_SHOW_ORIGINAL, false)
        textOverlayMode = preferences.getBoolean(AppSettings.KEY_TEXT_OVERLAY_MODE, false)
    }

    private fun saveSettings() {
        preferences.edit()
            .putInt(AppSettings.KEY_TARGET_INDEX, targetIndex)
            .putBoolean(AppSettings.KEY_SHOW_ORIGINAL, showOriginal)
            .putBoolean(AppSettings.KEY_TEXT_OVERLAY_MODE, textOverlayMode)
            .putString(AppSettings.KEY_STT_ENDPOINT, sttEndpointInput.text.toString())
            .putString(AppSettings.KEY_STT_API_KEY, sttApiKeyInput.text.toString())
            .apply()
    }

    @Deprecated("Android framework callback")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_PROJECTION && resultCode == RESULT_OK && data != null) {
            saveSettings()
            val serviceIntent = Intent(this, FloatingTranslateService::class.java).apply {
                putExtra(FloatingTranslateService.EXTRA_RESULT_CODE, resultCode)
                putExtra(FloatingTranslateService.EXTRA_RESULT_DATA, data)
                putExtra(FloatingTranslateService.EXTRA_TARGET_LANGUAGE, TARGET_LANGUAGES[targetIndex].code)
                putExtra(FloatingTranslateService.EXTRA_SHOW_ORIGINAL, showOriginal)
                putExtra(FloatingTranslateService.EXTRA_TEXT_OVERLAY_MODE, textOverlayMode)
                putExtra(FloatingTranslateService.EXTRA_STT_ENDPOINT, sttEndpointInput.text.toString())
                putExtra(FloatingTranslateService.EXTRA_STT_API_KEY, sttApiKeyInput.text.toString())
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent)
            } else {
                startService(serviceIntent)
            }
            moveTaskToBack(true)
        }
    }

    companion object {
        private const val REQUEST_PROJECTION = 24
        private data class TargetLanguage(val label: String, val code: String)

        private val TARGET_LANGUAGES = listOf(
            TargetLanguage("中文", FloatingTranslateService.LANG_CHINESE),
            TargetLanguage("英语", FloatingTranslateService.LANG_ENGLISH),
            TargetLanguage("日语", FloatingTranslateService.LANG_JAPANESE),
            TargetLanguage("韩语", FloatingTranslateService.LANG_KOREAN),
            TargetLanguage("德语", FloatingTranslateService.LANG_GERMAN),
            TargetLanguage("法语", FloatingTranslateService.LANG_FRENCH),
            TargetLanguage("俄语", FloatingTranslateService.LANG_RUSSIAN),
        )
    }
}
