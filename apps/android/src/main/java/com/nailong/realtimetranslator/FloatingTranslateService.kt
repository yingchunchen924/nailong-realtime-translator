package com.nailong.realtimetranslator

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.graphics.Rect
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioPlaybackCaptureConfiguration
import android.media.AudioRecord
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.provider.Settings
import android.view.Gravity
import android.view.WindowManager
import android.widget.TextView
import com.google.mlkit.common.model.DownloadConditions
import com.google.mlkit.nl.languageid.LanguageIdentification
import com.google.mlkit.nl.languageid.LanguageIdentifier
import com.google.mlkit.nl.translate.TranslateLanguage
import com.google.mlkit.nl.translate.Translation
import com.google.mlkit.nl.translate.Translator
import com.google.mlkit.nl.translate.TranslatorOptions
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.Text
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.TextRecognizer
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import com.google.mlkit.vision.text.japanese.JapaneseTextRecognizerOptions
import com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions
import com.google.mlkit.vision.text.latin.TextRecognizerOptions

class FloatingTranslateService : Service() {
    private val mainHandler = Handler(Looper.getMainLooper())
    private var overlayView: TextView? = null
    private val textOverlayViews = mutableListOf<TextView>()
    private var mediaProjection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null
    private var audioRecord: AudioRecord? = null
    private var audioThread: Thread? = null
    @Volatile private var isAudioCapturing = false
    private var audioSubtitleEngine: AudioSubtitleEngine = PlaceholderAudioSubtitleEngine()
    private val latinRecognizer by lazy { TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS) }
    private val chineseRecognizer by lazy { TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build()) }
    private val japaneseRecognizer by lazy { TextRecognition.getClient(JapaneseTextRecognizerOptions.Builder().build()) }
    private val koreanRecognizer by lazy { TextRecognition.getClient(KoreanTextRecognizerOptions.Builder().build()) }
    private val languageIdentifier: LanguageIdentifier by lazy { LanguageIdentification.getClient() }
    private val translators = mutableMapOf<String, Translator>()
    private var isRecognizing = false
    private var lastOcrAt = 0L
    private var lastText = ""
    private var lastTextOverlaySignature = ""
    private var targetLanguage = LANG_CHINESE
    private var showOriginal = false
    private var textOverlayMode = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        targetLanguage = intent?.getStringExtra(EXTRA_TARGET_LANGUAGE) ?: savedTargetLanguage()
        showOriginal = intent?.takeIf { it.hasExtra(EXTRA_SHOW_ORIGINAL) }?.getBooleanExtra(EXTRA_SHOW_ORIGINAL, false)
            ?: savedShowOriginal()
        textOverlayMode = intent?.takeIf { it.hasExtra(EXTRA_TEXT_OVERLAY_MODE) }?.getBooleanExtra(EXTRA_TEXT_OVERLAY_MODE, false)
            ?: savedTextOverlayMode()
        configureAudioSubtitleEngine(intent)
        showOverlay("奶龙实时翻译已在后台运行")
        val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
        val data = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            intent?.getParcelableExtra(EXTRA_RESULT_DATA, Intent::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent?.getParcelableExtra(EXTRA_RESULT_DATA)
        }
        if (resultCode != 0 && data != null) {
            startProjection(resultCode, data)
            startPlaybackAudioCapture()
        }
        return START_STICKY
    }

    private fun configureAudioSubtitleEngine(intent: Intent?) {
        val preferences = getSharedPreferences(AppSettings.PREFS_NAME, Context.MODE_PRIVATE)
        val endpoint = (
            intent?.getStringExtra(EXTRA_STT_ENDPOINT)
                ?: preferences.getString(AppSettings.KEY_STT_ENDPOINT, WhisperHttpAudioSubtitleEngine.DEFAULT_ENDPOINT)
        ).orEmpty().trim()
        val apiKey = (
            intent?.getStringExtra(EXTRA_STT_API_KEY)
                ?: preferences.getString(AppSettings.KEY_STT_API_KEY, "")
        ).orEmpty().trim()
        val model = (
            intent?.getStringExtra(EXTRA_STT_MODEL)
                ?: preferences.getString(AppSettings.KEY_STT_MODEL, WhisperHttpAudioSubtitleEngine.DEFAULT_MODEL)
        ).orEmpty().trim().ifBlank { WhisperHttpAudioSubtitleEngine.DEFAULT_MODEL }
        audioSubtitleEngine.close()
        audioSubtitleEngine = if (endpoint.isNotBlank() && apiKey.isNotBlank()) {
            WhisperHttpAudioSubtitleEngine(endpoint, apiKey, model)
        } else {
            PlaceholderAudioSubtitleEngine()
        }
    }

    private fun savedTargetLanguage(): String {
        val preferences = getSharedPreferences(AppSettings.PREFS_NAME, Context.MODE_PRIVATE)
        return when (preferences.getInt(AppSettings.KEY_TARGET_INDEX, 0)) {
            1 -> LANG_ENGLISH
            2 -> LANG_JAPANESE
            3 -> LANG_KOREAN
            4 -> LANG_GERMAN
            5 -> LANG_FRENCH
            6 -> LANG_RUSSIAN
            else -> LANG_CHINESE
        }
    }

    private fun savedShowOriginal(): Boolean {
        val preferences = getSharedPreferences(AppSettings.PREFS_NAME, Context.MODE_PRIVATE)
        return preferences.getBoolean(AppSettings.KEY_SHOW_ORIGINAL, false)
    }

    private fun savedTextOverlayMode(): Boolean {
        val preferences = getSharedPreferences(AppSettings.PREFS_NAME, Context.MODE_PRIVATE)
        return preferences.getBoolean(AppSettings.KEY_TEXT_OVERLAY_MODE, false)
    }

    private fun showOverlay(text: String) {
        if (!Settings.canDrawOverlays(this)) return
        if (overlayView != null) {
            overlayView?.text = text
            return
        }

        overlayView = TextView(this).apply {
            this.text = text
            textSize = 18f
            setTextColor(0xffffffff.toInt())
            setBackgroundResource(com.nailong.realtimetranslator.R.drawable.subtitle_bg)
            gravity = Gravity.CENTER
            maxLines = 2
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL
            x = 0
            y = 90
            width = resources.displayMetrics.widthPixels - dp(28)
        }

        val windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        windowManager.addView(overlayView, params)
    }

    private fun startProjection(resultCode: Int, data: Intent) {
        val manager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        mediaProjection = manager.getMediaProjection(resultCode, data)
        val metrics = resources.displayMetrics
        imageReader = ImageReader.newInstance(
            metrics.widthPixels,
            metrics.heightPixels,
            PixelFormat.RGBA_8888,
            2
        )
        virtualDisplay = mediaProjection?.createVirtualDisplay(
            "NailongScreenCapture",
            metrics.widthPixels,
            metrics.heightPixels,
            metrics.densityDpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            imageReader?.surface,
            null,
            null
        )
        imageReader?.setOnImageAvailableListener({ reader ->
            val image = reader.acquireLatestImage() ?: return@setOnImageAvailableListener
            val now = System.currentTimeMillis()
            if (isRecognizing || now - lastOcrAt < OCR_INTERVAL_MS) {
                image.close()
                return@setOnImageAvailableListener
            }
            lastOcrAt = now
            isRecognizing = true
            recognizeScreenImage(image)
        }, mainHandler)
    }

    private fun startPlaybackAudioCapture() {
        val projection = mediaProjection ?: return
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q || isAudioCapturing) return

        val config = AudioPlaybackCaptureConfiguration.Builder(projection)
            .addMatchingUsage(AudioAttributes.USAGE_MEDIA)
            .addMatchingUsage(AudioAttributes.USAGE_GAME)
            .addMatchingUsage(AudioAttributes.USAGE_UNKNOWN)
            .build()
        val audioFormat = AudioFormat.Builder()
            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
            .setSampleRate(AUDIO_SAMPLE_RATE)
            .setChannelMask(AudioFormat.CHANNEL_IN_MONO)
            .build()
        val minBufferSize = AudioRecord.getMinBufferSize(
            AUDIO_SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )
        val bufferSize = maxOf(minBufferSize, AUDIO_SAMPLE_RATE * 2)
        audioRecord = AudioRecord.Builder()
            .setAudioPlaybackCaptureConfig(config)
            .setAudioFormat(audioFormat)
            .setBufferSizeInBytes(bufferSize)
            .build()

        isAudioCapturing = true
        audioThread = Thread {
            capturePlaybackAudio(bufferSize)
        }.apply {
            name = "NailongPlaybackAudioCapture"
            start()
        }
    }

    private fun capturePlaybackAudio(bufferSize: Int) {
        val recorder = audioRecord ?: return
        val buffer = ShortArray(bufferSize / 2)
        try {
            recorder.startRecording()
            while (isAudioCapturing) {
                val read = recorder.read(buffer, 0, buffer.size)
                if (read <= 0) continue
                val rms = calculateRms(buffer, read)
                if (rms > AUDIO_ACTIVITY_THRESHOLD) {
                    audioSubtitleEngine.acceptPcm16(buffer, read, AUDIO_SAMPLE_RATE) { result ->
                        mainHandler.post {
                            if (result.isTranscript) {
                                translateText(result.text)
                            } else {
                                overlayView?.text = result.text
                            }
                        }
                    }
                }
            }
        } catch (_: SecurityException) {
            mainHandler.post {
                overlayView?.text = "音频捕获权限不足，请重新授权录音和屏幕捕获"
            }
        } finally {
            runCatching { recorder.stop() }
        }
    }

    private fun calculateRms(buffer: ShortArray, length: Int): Double {
        if (length <= 0) return 0.0
        var sum = 0.0
        for (index in 0 until length) {
            val sample = buffer[index].toDouble() / Short.MAX_VALUE
            sum += sample * sample
        }
        return kotlin.math.sqrt(sum / length)
    }

    private fun recognizeScreenImage(image: Image) {
        val bitmap = image.toBitmap()
        image.close()
        if (bitmap == null) {
            isRecognizing = false
            clearTextBlockOverlays()
            return
        }
        val inputImage = InputImage.fromBitmap(bitmap, 0)
        recognizeWithFallbacks(inputImage, listOf(chineseRecognizer, japaneseRecognizer, koreanRecognizer, latinRecognizer), 0)
    }

    private fun recognizeWithFallbacks(image: InputImage, recognizers: List<TextRecognizer>, index: Int) {
        if (index >= recognizers.size) {
            isRecognizing = false
            clearTextBlockOverlays()
            return
        }
        recognizers[index].process(image)
            .addOnSuccessListener { result ->
                val text = result.text.lineSequence()
                    .map { it.trim() }
                    .filter { it.isNotEmpty() }
                    .take(3)
                    .joinToString(" ")
                if (text.length >= MIN_TEXT_LENGTH) {
                    if (textOverlayMode) {
                        showTextBlockOverlays(result.textBlocks)
                    } else if (text != lastText) {
                        lastText = text
                        translateText(text)
                    }
                    isRecognizing = false
                } else {
                    recognizeWithFallbacks(image, recognizers, index + 1)
                }
            }
            .addOnFailureListener {
                recognizeWithFallbacks(image, recognizers, index + 1)
            }
    }

    private fun translateText(text: String) {
        translateTextForDisplay(
            text,
            onProgress = { overlayView?.text = it }
        ) { translated ->
            overlayView?.text = translated
        }
    }

    private fun translateTextForDisplay(
        text: String,
        onProgress: ((String) -> Unit)? = null,
        onTranslated: (String) -> Unit
    ) {
        identifySourceLanguage(text) { sourceLanguage ->
            translateFromSource(text, sourceLanguage, onProgress, onTranslated)
        }
    }

    private fun translateFromSource(
        text: String,
        sourceLanguage: String,
        onProgress: ((String) -> Unit)?,
        onTranslated: (String) -> Unit
    ) {
        val target = targetLanguage.toMlKitLanguage()
        if (sourceLanguage == target) {
            onTranslated(text)
            return
        }
        val translator = translatorFor(sourceLanguage, target)
        val conditions = DownloadConditions.Builder().build()
        onProgress?.invoke("$text\n正在准备翻译模型...")
        translator.downloadModelIfNeeded(conditions)
            .addOnSuccessListener {
                translator.translate(text)
                    .addOnSuccessListener { translated ->
                        onTranslated(formatTranslation(text, translated))
                    }
                    .addOnFailureListener {
                        onTranslated(text)
                    }
            }
            .addOnFailureListener {
                onTranslated(text)
            }
    }

    private fun identifySourceLanguage(text: String, onIdentified: (String) -> Unit) {
        val scriptGuess = guessSourceLanguageByScript(text)
        if (scriptGuess != null) {
            onIdentified(scriptGuess)
            return
        }
        languageIdentifier.identifyLanguage(text)
            .addOnSuccessListener { tag ->
                onIdentified(tag.toMlKitLanguageOrEnglish())
            }
            .addOnFailureListener {
                onIdentified(TranslateLanguage.ENGLISH)
            }
    }

    private fun translatorFor(source: String, target: String): Translator {
        val key = "$source->$target"
        return translators.getOrPut(key) {
            val options = TranslatorOptions.Builder()
                .setSourceLanguage(source)
                .setTargetLanguage(target)
                .build()
            Translation.getClient(options)
        }
    }

    private fun guessSourceLanguageByScript(text: String): String? {
        return when {
            text.any { it in '\u4e00'..'\u9fff' } -> TranslateLanguage.CHINESE
            text.any { it in '\u3040'..'\u30ff' } -> TranslateLanguage.JAPANESE
            text.any { it in '\uac00'..'\ud7af' } -> TranslateLanguage.KOREAN
            text.any { it in '\u0400'..'\u04ff' } -> TranslateLanguage.RUSSIAN
            else -> null
        }
    }

    private fun formatTranslation(original: String, translated: String): String {
        return if (showOriginal && original != translated) {
            "$original\n$translated"
        } else {
            translated
        }
    }

    private fun showTextBlockOverlays(blocks: List<Text.TextBlock>) {
        if (!Settings.canDrawOverlays(this)) return
        val windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val metrics = resources.displayMetrics
        val candidates = blocks.asSequence()
            .mapNotNull { block ->
                val box = block.boundingBox ?: return@mapNotNull null
                if (block.text.trim().length < MIN_TEXT_LENGTH) return@mapNotNull null
                block to box
            }
            .sortedWith(compareBy<Pair<Text.TextBlock, Rect>> { it.second.top }.thenBy { it.second.left })
            .take(MAX_TEXT_BLOCK_OVERLAYS)
            .toList()
        val signature = candidates.joinToString("|") { (block, box) ->
            "${box.left / 8},${box.top / 8},${box.width() / 8},${box.height() / 8}:${block.text.trim()}"
        }
        if (signature == lastTextOverlaySignature) return
        lastTextOverlaySignature = signature
        clearTextBlockOverlays(resetSignature = false)
        candidates.forEach { (block, box) ->
            val view = TextView(this).apply {
                text = if (showOriginal) block.text.trim() else "翻译中..."
                textSize = 13f
                setTextColor(0xffffffff.toInt())
                setBackgroundResource(com.nailong.realtimetranslator.R.drawable.subtitle_bg)
                setPadding(dp(6), dp(4), dp(6), dp(4))
                maxLines = if (showOriginal) 3 else 2
            }
            val params = textBlockLayoutParams(box, metrics.widthPixels, metrics.heightPixels)
            windowManager.addView(view, params)
            textOverlayViews.add(view)
            translateTextForDisplay(block.text.trim()) { translated ->
                view.text = translated
            }
        }
    }

    private fun textBlockLayoutParams(
        box: Rect,
        screenWidth: Int,
        screenHeight: Int
    ): WindowManager.LayoutParams {
        val minWidth = dp(96)
        val width = (box.width() + dp(20)).coerceIn(minWidth, screenWidth - dp(24))
        return WindowManager.LayoutParams(
            width,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = box.left.coerceIn(dp(8), maxOf(dp(8), screenWidth - width - dp(8)))
            y = box.top.coerceIn(dp(16), maxOf(dp(16), screenHeight - dp(72)))
        }
    }

    private fun clearTextBlockOverlays(resetSignature: Boolean = true) {
        if (resetSignature) lastTextOverlaySignature = ""
        if (textOverlayViews.isEmpty()) return
        val windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        textOverlayViews.forEach { view ->
            runCatching { windowManager.removeView(view) }
        }
        textOverlayViews.clear()
    }

    private fun String.toMlKitLanguage(): String {
        return when (this) {
            LANG_ENGLISH -> TranslateLanguage.ENGLISH
            LANG_JAPANESE -> TranslateLanguage.JAPANESE
            LANG_KOREAN -> TranslateLanguage.KOREAN
            LANG_GERMAN -> TranslateLanguage.GERMAN
            LANG_FRENCH -> TranslateLanguage.FRENCH
            LANG_RUSSIAN -> TranslateLanguage.RUSSIAN
            else -> TranslateLanguage.CHINESE
        }
    }

    private fun String.toMlKitLanguageOrEnglish(): String {
        return when (this.lowercase()) {
            "zh", "zh-cn", "zh-tw" -> TranslateLanguage.CHINESE
            "en" -> TranslateLanguage.ENGLISH
            "ja" -> TranslateLanguage.JAPANESE
            "ko" -> TranslateLanguage.KOREAN
            "de" -> TranslateLanguage.GERMAN
            "fr" -> TranslateLanguage.FRENCH
            "ru" -> TranslateLanguage.RUSSIAN
            "es" -> TranslateLanguage.SPANISH
            "it" -> TranslateLanguage.ITALIAN
            "pt" -> TranslateLanguage.PORTUGUESE
            else -> TranslateLanguage.ENGLISH
        }
    }

    private fun Image.toBitmap(): Bitmap? {
        val plane = planes.firstOrNull() ?: return null
        val buffer = plane.buffer
        val pixelStride = plane.pixelStride
        val rowStride = plane.rowStride
        val rowPadding = rowStride - pixelStride * width
        val bitmapWidth = width + rowPadding / pixelStride
        val bitmap = Bitmap.createBitmap(bitmapWidth, height, Bitmap.Config.ARGB_8888)
        bitmap.copyPixelsFromBuffer(buffer)
        return Bitmap.createBitmap(bitmap, 0, 0, width, height)
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "奶龙实时翻译",
                NotificationManager.IMPORTANCE_LOW
            )
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun buildNotification(): Notification {
        val openIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            openIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val stopIntent = Intent(this, FloatingTranslateService::class.java).apply {
            action = ACTION_STOP
        }
        val stopPendingIntent = PendingIntent.getService(
            this,
            1,
            stopIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, CHANNEL_ID)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        return builder
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("奶龙实时翻译")
            .setContentText("后台翻译运行中")
            .setContentIntent(pendingIntent)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "停止", stopPendingIntent)
            .setOngoing(true)
            .build()
    }

    override fun onDestroy() {
        isAudioCapturing = false
        audioThread?.interrupt()
        audioRecord?.release()
        audioSubtitleEngine.close()
        virtualDisplay?.release()
        imageReader?.close()
        mediaProjection?.stop()
        latinRecognizer.close()
        chineseRecognizer.close()
        japaneseRecognizer.close()
        koreanRecognizer.close()
        languageIdentifier.close()
        translators.values.forEach { it.close() }
        overlayView?.let {
            (getSystemService(Context.WINDOW_SERVICE) as WindowManager).removeView(it)
        }
        clearTextBlockOverlays()
        super.onDestroy()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    companion object {
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"
        const val EXTRA_TARGET_LANGUAGE = "target_language"
        const val EXTRA_SHOW_ORIGINAL = "show_original"
        const val EXTRA_TEXT_OVERLAY_MODE = "text_overlay_mode"
        const val EXTRA_STT_ENDPOINT = "stt_endpoint"
        const val EXTRA_STT_MODEL = "stt_model"
        const val EXTRA_STT_API_KEY = "stt_api_key"
        const val ACTION_STOP = "com.nailong.realtimetranslator.STOP"
        const val LANG_CHINESE = "zh"
        const val LANG_ENGLISH = "en"
        const val LANG_JAPANESE = "ja"
        const val LANG_KOREAN = "ko"
        const val LANG_GERMAN = "de"
        const val LANG_FRENCH = "fr"
        const val LANG_RUSSIAN = "ru"
        private const val CHANNEL_ID = "nailong_translate"
        private const val NOTIFICATION_ID = 1001
        private const val OCR_INTERVAL_MS = 1200L
        private const val MIN_TEXT_LENGTH = 2
        private const val MAX_TEXT_BLOCK_OVERLAYS = 10
        private const val AUDIO_SAMPLE_RATE = 16000
        private const val AUDIO_ACTIVITY_THRESHOLD = 0.015
    }
}
