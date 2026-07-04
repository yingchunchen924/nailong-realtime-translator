package com.nailong.realtimetranslator

interface AudioSubtitleEngine {
    fun acceptPcm16(
        samples: ShortArray,
        length: Int,
        sampleRate: Int,
        onSubtitle: (String) -> Unit
    )

    fun close()
}

class PlaceholderAudioSubtitleEngine : AudioSubtitleEngine {
    private var lastNoticeAt = 0L

    override fun acceptPcm16(
        samples: ShortArray,
        length: Int,
        sampleRate: Int,
        onSubtitle: (String) -> Unit
    ) {
        val now = System.currentTimeMillis()
        if (now - lastNoticeAt > NOTICE_INTERVAL_MS) {
            lastNoticeAt = now
            onSubtitle("正在监听播放音频，等待语音字幕引擎接入...")
        }
    }

    override fun close() = Unit

    companion object {
        private const val NOTICE_INTERVAL_MS = 3500L
    }
}
