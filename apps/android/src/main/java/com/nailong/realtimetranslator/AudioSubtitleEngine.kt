package com.nailong.realtimetranslator

import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.net.HttpURLConnection
import java.net.URL
import kotlin.math.min

data class AudioSubtitleResult(
    val text: String,
    val isTranscript: Boolean
)

interface AudioSubtitleEngine {
    fun acceptPcm16(
        samples: ShortArray,
        length: Int,
        sampleRate: Int,
        onSubtitle: (AudioSubtitleResult) -> Unit
    )

    fun close()
}

class PlaceholderAudioSubtitleEngine : AudioSubtitleEngine {
    private var lastNoticeAt = 0L

    override fun acceptPcm16(
        samples: ShortArray,
        length: Int,
        sampleRate: Int,
        onSubtitle: (AudioSubtitleResult) -> Unit
    ) {
        val now = System.currentTimeMillis()
        if (now - lastNoticeAt > NOTICE_INTERVAL_MS) {
            lastNoticeAt = now
            onSubtitle(AudioSubtitleResult("正在监听播放音频，等待语音字幕引擎接入...", false))
        }
    }

    override fun close() = Unit

    companion object {
        private const val NOTICE_INTERVAL_MS = 3500L
    }
}

class WhisperHttpAudioSubtitleEngine(
    private val endpoint: String,
    private val apiKey: String,
    private val model: String = DEFAULT_MODEL
) : AudioSubtitleEngine {
    private var pending = ShortArray(CHUNK_SAMPLE_RATE_SECONDS * DEFAULT_SAMPLE_RATE)
    private var pendingLength = 0
    @Volatile private var inFlight = false
    @Volatile private var closed = false
    private var lastErrorNoticeAt = 0L
    private var lastTranscript = ""
    private var lastTranscriptAt = 0L

    override fun acceptPcm16(
        samples: ShortArray,
        length: Int,
        sampleRate: Int,
        onSubtitle: (AudioSubtitleResult) -> Unit
    ) {
        if (closed || endpoint.isBlank() || apiKey.isBlank()) {
            val now = System.currentTimeMillis()
            if (now - lastErrorNoticeAt > ERROR_NOTICE_INTERVAL_MS) {
                lastErrorNoticeAt = now
                onSubtitle(AudioSubtitleResult("正在监听播放音频，等待语音字幕引擎接入...", false))
            }
            return
        }

        ensureCapacity(sampleRate)
        var offset = 0
        while (offset < length) {
            val writable = min(length - offset, pending.size - pendingLength)
            System.arraycopy(samples, offset, pending, pendingLength, writable)
            pendingLength += writable
            offset += writable

            if (pendingLength >= pending.size) {
                if (!inFlight) {
                    val chunk = pending.copyOf(pendingLength)
                    pendingLength = 0
                    submitChunk(chunk, sampleRate, onSubtitle)
                } else {
                    pendingLength = 0
                }
            }
        }
    }

    private fun ensureCapacity(sampleRate: Int) {
        val expected = CHUNK_SAMPLE_RATE_SECONDS * sampleRate
        if (pending.size != expected && pendingLength == 0) {
            pending = ShortArray(expected)
        }
    }

    private fun submitChunk(
        chunk: ShortArray,
        sampleRate: Int,
        onSubtitle: (AudioSubtitleResult) -> Unit
    ) {
        inFlight = true
        Thread {
            try {
                val transcript = normalizeTranscript(transcribeWav(toWav(chunk, sampleRate)))
                if (shouldEmitTranscript(transcript)) {
                    lastTranscript = transcript
                    lastTranscriptAt = System.currentTimeMillis()
                    onSubtitle(AudioSubtitleResult(transcript, true))
                }
            } catch (exc: Exception) {
                val now = System.currentTimeMillis()
                if (now - lastErrorNoticeAt > ERROR_NOTICE_INTERVAL_MS) {
                    lastErrorNoticeAt = now
                    onSubtitle(AudioSubtitleResult("语音转写失败：${exc.message ?: "网络或接口错误"}", false))
                }
            } finally {
                inFlight = false
            }
        }.apply {
            name = "NailongWhisperTranscription"
            start()
        }
    }

    private fun normalizeTranscript(text: String): String {
        return text.lineSequence()
            .map { it.trim().replace(Regex("\\s+"), " ") }
            .filter { it.isNotEmpty() }
            .joinToString(" ")
            .trim()
    }

    private fun shouldEmitTranscript(text: String): Boolean {
        if (text.length < MIN_TRANSCRIPT_LENGTH) return false
        if (isLikelyNonSpeechCaption(text)) return false
        val now = System.currentTimeMillis()
        if (text == lastTranscript && now - lastTranscriptAt < DUPLICATE_TRANSCRIPT_SUPPRESS_MS) {
            return false
        }
        return true
    }

    private fun isLikelyNonSpeechCaption(text: String): Boolean {
        val normalized = text.trim().lowercase().trim('.', '。', '!', '！', '?', '？')
        return normalized in setOf(
            "[music]",
            "(music)",
            "music",
            "[silence]",
            "(silence)",
            "silence",
            "字幕",
            "谢谢观看",
            "感谢观看"
        )
    }

    private fun transcribeWav(wav: ByteArray): String {
        val boundary = "----NailongBoundary${System.currentTimeMillis()}"
        val connection = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 30000
            readTimeout = 60000
            doOutput = true
            setRequestProperty("Authorization", "Bearer $apiKey")
            setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        }

        DataOutputStream(connection.outputStream).use { out ->
            out.writeFormField(boundary, "model", model)
            out.writeFormField(boundary, "response_format", "json")
            out.writeFileField(boundary, "file", "audio.wav", "audio/wav", wav)
            out.writeBytes("--$boundary--\r\n")
        }

        val responseCode = connection.responseCode
        val body = if (responseCode in 200..299) {
            connection.inputStream.bufferedReader().use { it.readText() }
        } else {
            connection.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty()
        }
        if (responseCode !in 200..299) {
            throw IllegalStateException("HTTP $responseCode $body")
        }
        return JSONObject(body).optString("text", "").trim()
    }

    private fun toWav(samples: ShortArray, sampleRate: Int): ByteArray {
        val pcmBytes = samples.size * 2
        val output = ByteArrayOutputStream(44 + pcmBytes)
        DataOutputStream(output).use { out ->
            out.writeBytes("RIFF")
            out.writeIntLe(36 + pcmBytes)
            out.writeBytes("WAVE")
            out.writeBytes("fmt ")
            out.writeIntLe(16)
            out.writeShortLe(1)
            out.writeShortLe(1)
            out.writeIntLe(sampleRate)
            out.writeIntLe(sampleRate * 2)
            out.writeShortLe(2)
            out.writeShortLe(16)
            out.writeBytes("data")
            out.writeIntLe(pcmBytes)
            samples.forEach { out.writeShortLe(it.toInt()) }
        }
        return output.toByteArray()
    }

    override fun close() {
        closed = true
    }

    private fun DataOutputStream.writeFormField(boundary: String, name: String, value: String) {
        writeBytes("--$boundary\r\n")
        writeBytes("Content-Disposition: form-data; name=\"$name\"\r\n\r\n")
        writeBytes(value)
        writeBytes("\r\n")
    }

    private fun DataOutputStream.writeFileField(
        boundary: String,
        name: String,
        filename: String,
        contentType: String,
        bytes: ByteArray
    ) {
        writeBytes("--$boundary\r\n")
        writeBytes("Content-Disposition: form-data; name=\"$name\"; filename=\"$filename\"\r\n")
        writeBytes("Content-Type: $contentType\r\n\r\n")
        write(bytes)
        writeBytes("\r\n")
    }

    private fun DataOutputStream.writeIntLe(value: Int) {
        write(value and 0xff)
        write((value shr 8) and 0xff)
        write((value shr 16) and 0xff)
        write((value shr 24) and 0xff)
    }

    private fun DataOutputStream.writeShortLe(value: Int) {
        write(value and 0xff)
        write((value shr 8) and 0xff)
    }

    companion object {
        const val DEFAULT_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
        const val DEFAULT_MODEL = "whisper-1"
        private const val DEFAULT_SAMPLE_RATE = 16000
        private const val CHUNK_SAMPLE_RATE_SECONDS = 5
        private const val ERROR_NOTICE_INTERVAL_MS = 8000L
        private const val MIN_TRANSCRIPT_LENGTH = 2
        private const val DUPLICATE_TRANSCRIPT_SUPPRESS_MS = 12000L
    }
}
