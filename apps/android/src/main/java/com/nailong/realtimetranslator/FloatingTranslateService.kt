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
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
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
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.TextRecognizer
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import com.google.mlkit.vision.text.japanese.JapaneseTextRecognizerOptions
import com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions
import com.google.mlkit.vision.text.latin.TextRecognizerOptions

class FloatingTranslateService : Service() {
    private val mainHandler = Handler(Looper.getMainLooper())
    private var overlayView: TextView? = null
    private var mediaProjection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null
    private val latinRecognizer by lazy { TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS) }
    private val chineseRecognizer by lazy { TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build()) }
    private val japaneseRecognizer by lazy { TextRecognition.getClient(JapaneseTextRecognizerOptions.Builder().build()) }
    private val koreanRecognizer by lazy { TextRecognition.getClient(KoreanTextRecognizerOptions.Builder().build()) }
    private var isRecognizing = false
    private var lastOcrAt = 0L
    private var lastText = ""

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
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
        }
        return START_STICKY
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

    private fun recognizeScreenImage(image: Image) {
        val bitmap = image.toBitmap()
        image.close()
        if (bitmap == null) {
            isRecognizing = false
            return
        }
        val inputImage = InputImage.fromBitmap(bitmap, 0)
        recognizeWithFallbacks(inputImage, listOf(chineseRecognizer, japaneseRecognizer, koreanRecognizer, latinRecognizer), 0)
    }

    private fun recognizeWithFallbacks(image: InputImage, recognizers: List<TextRecognizer>, index: Int) {
        if (index >= recognizers.size) {
            isRecognizing = false
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
                    if (text != lastText) {
                        lastText = text
                        overlayView?.text = text
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
            .setOngoing(true)
            .build()
    }

    override fun onDestroy() {
        virtualDisplay?.release()
        imageReader?.close()
        mediaProjection?.stop()
        latinRecognizer.close()
        chineseRecognizer.close()
        japaneseRecognizer.close()
        koreanRecognizer.close()
        overlayView?.let {
            (getSystemService(Context.WINDOW_SERVICE) as WindowManager).removeView(it)
        }
        super.onDestroy()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    companion object {
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"
        private const val CHANNEL_ID = "nailong_translate"
        private const val NOTIFICATION_ID = 1001
        private const val OCR_INTERVAL_MS = 1200L
        private const val MIN_TEXT_LENGTH = 2
    }
}
