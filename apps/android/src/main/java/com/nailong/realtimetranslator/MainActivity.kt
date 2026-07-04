package com.nailong.realtimetranslator

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    private lateinit var projectionManager: MediaProjectionManager
    private var targetIndex = 0
    private lateinit var targetButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        projectionManager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        buildUi()
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
        root.addView(screenButton, buttonParams())
        root.addView(stopButton, buttonParams())
        setContentView(root)

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
    }

    private fun targetButtonText(): String {
        return "目标语言：${TARGET_LANGUAGES[targetIndex].label}"
    }

    @Deprecated("Android framework callback")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_PROJECTION && resultCode == RESULT_OK && data != null) {
            val serviceIntent = Intent(this, FloatingTranslateService::class.java).apply {
                putExtra(FloatingTranslateService.EXTRA_RESULT_CODE, resultCode)
                putExtra(FloatingTranslateService.EXTRA_RESULT_DATA, data)
                putExtra(FloatingTranslateService.EXTRA_TARGET_LANGUAGE, TARGET_LANGUAGES[targetIndex].code)
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
