from __future__ import annotations

import hashlib
import os
import queue
import shutil
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageEnhance, ImageOps, ImageTk

APP_NAME = "奶龙实时翻译"
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent
ASSET_DIR = PROJECT_DIR / "assets"
ICON_PATH = ASSET_DIR / "nailong.ico"
IMAGE_PATH = ASSET_DIR / "nailong.jpg"
LOCAL_TESSDATA_DIR = PROJECT_DIR / "tessdata"
DEFAULT_TESSERACT_EXE = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")

LANGUAGES = {
    "自动检测": "auto",
    "中文": "zh-CN",
    "英语": "en",
    "日语": "ja",
    "韩语": "ko",
    "德语": "de",
    "法语": "fr",
    "俄语": "ru",
    "西班牙语": "es",
    "意大利语": "it",
    "葡萄牙语": "pt",
}

WHISPER_LANGS = {
    "auto": None,
    "zh-CN": "zh",
    "en": "en",
    "ja": "ja",
    "ko": "ko",
    "de": "de",
    "fr": "fr",
    "ru": "ru",
    "es": "es",
    "it": "it",
    "pt": "pt",
}

TESSERACT_LANGS = {
    "auto": "eng",
    "zh-CN": "chi_sim",
    "en": "eng",
    "ja": "jpn",
    "ko": "kor",
    "de": "deu",
    "fr": "fra",
    "ru": "rus",
    "es": "spa",
    "it": "ita",
    "pt": "por",
}


@dataclass(frozen=True)
class CaptureRegion:
    left: int
    top: int
    width: int
    height: int

    def to_mss(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "width": max(1, self.width),
            "height": max(1, self.height),
        }

    def label(self) -> str:
        return f"x={self.left}, y={self.top}, w={self.width}, h={self.height}"


@dataclass
class Subtitle:
    source: str
    translated: str
    origin: str
    status: str
    region: CaptureRegion | None = None


class OptionalEngines:
    def __init__(self) -> None:
        self.mss = self._try_import("mss")
        self.pytesseract = self._try_import("pytesseract")
        self.deep_translator = self._try_import("deep_translator")
        self.soundcard = self._try_import("soundcard")
        self.faster_whisper = self._try_import("faster_whisper")
        self.numpy = self._try_import("numpy")
        self.pystray = self._try_import("pystray")
        self.tesseract_path = self._configure_tesseract()

    @staticmethod
    def _try_import(name: str):
        try:
            return __import__(name)
        except Exception:
            return None

    def _configure_tesseract(self) -> str | None:
        if not self.pytesseract:
            return None

        candidates = [
            shutil.which("tesseract"),
            str(DEFAULT_TESSERACT_EXE) if DEFAULT_TESSERACT_EXE.exists() else None,
        ]
        exe = next((item for item in candidates if item), None)
        if exe:
            self.pytesseract.pytesseract.tesseract_cmd = exe

        if LOCAL_TESSDATA_DIR.exists():
            os.environ["TESSDATA_PREFIX"] = str(LOCAL_TESSDATA_DIR)

        return exe

    def refresh(self) -> None:
        self.__init__()

    def status_lines(self) -> list[str]:
        items = [
            ("屏幕捕获", self.mss),
            ("OCR 文字识别", self.pytesseract),
            ("Tesseract 程序", self.tesseract_path),
            ("本地 OCR 语言包", LOCAL_TESSDATA_DIR.exists()),
            ("在线翻译", self.deep_translator),
            ("系统音频捕获", self.soundcard),
            ("Whisper 语音识别", self.faster_whisper),
            ("音频数组处理", self.numpy),
            ("后台托盘", self.pystray),
        ]
        return [f"{label}: {'可用' if module else '未安装'}" for label, module in items]


class Translator:
    def __init__(self, engines: OptionalEngines) -> None:
        self.engines = engines
        self.cache: dict[tuple[str, str, str], str] = {}

    def translate(self, text: str, source: str, target: str) -> str:
        text = " ".join(line.strip() for line in text.splitlines() if line.strip())
        if not text:
            return ""
        if source == target and source != "auto":
            return text

        key = (text, source, target)
        if key in self.cache:
            return self.cache[key]

        if self.engines.deep_translator:
            try:
                google = self.engines.deep_translator.GoogleTranslator
                translated = google(source=source, target=target).translate(text)
                self.cache[key] = translated
                return translated
            except Exception as exc:
                return f"翻译失败：{exc}"

        return f"待翻译：{text}"


class ScreenOcrWorker(threading.Thread):
    def __init__(
        self,
        engines: OptionalEngines,
        translator: Translator,
        output: queue.Queue,
        stop_event: threading.Event,
        settings_getter,
    ) -> None:
        super().__init__(daemon=True)
        self.engines = engines
        self.translator = translator
        self.output = output
        self.stop_event = stop_event
        self.settings_getter = settings_getter
        self.last_hash = ""
        self.last_text = ""

    def run(self) -> None:
        if not self.engines.mss or not self.engines.pytesseract:
            self.output.put(
                Subtitle(
                    "屏幕文字识别依赖未安装",
                    "请安装 mss、pytesseract 和 Tesseract OCR 后再启用屏幕翻译。",
                    "screen",
                    "等待依赖",
                )
            )
            return

        try:
            sct = self.engines.mss.mss()
        except Exception as exc:
            self.output.put(Subtitle("屏幕捕获失败", str(exc), "screen", "错误"))
            return

        while not self.stop_event.is_set():
            settings = self.settings_getter()
            region = settings["region"]
            monitor = region.to_mss() if region else sct.monitors[1]
            started = time.perf_counter()

            try:
                image = sct.grab(monitor)
                pil = Image.frombytes("RGB", image.size, image.rgb)
            except Exception as exc:
                self.output.put(Subtitle("屏幕捕获失败", str(exc), "screen", "错误"))
                time.sleep(settings["interval"])
                continue

            digest = hashlib.sha1(pil.resize((96, 54)).tobytes()).hexdigest()
            if digest != self.last_hash:
                self.last_hash = digest
                text = self._ocr(pil, settings["source"])
                if text and text != self.last_text:
                    self.last_text = text
                    translated = self.translator.translate(text, settings["source"], settings["target"])
                    elapsed = int((time.perf_counter() - started) * 1000)
                    self.output.put(Subtitle(text, translated, "screen", f"OCR {elapsed} ms", region))

            time.sleep(settings["interval"])

    def _ocr(self, image: Image.Image, source_lang: str) -> str:
        max_side = 1800
        if max(image.size) < max_side:
            scale = min(2.0, max_side / max(1, max(image.size)))
            image = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)

        gray = ImageOps.grayscale(image)
        gray = ImageEnhance.Contrast(gray).enhance(1.8)
        languages = self._ocr_languages(source_lang)
        try:
            config = "--psm 6"
            if LOCAL_TESSDATA_DIR.exists():
                config = f"--tessdata-dir {LOCAL_TESSDATA_DIR} --psm 6"
            text = self._best_ocr_result(gray, languages, config)
        except Exception as exc:
            return f"OCR 失败：{exc}"

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines[:6])

    def _ocr_languages(self, source_lang: str) -> list[str]:
        if source_lang == "auto":
            return ["eng", "chi_sim", "jpn", "kor", "deu+fra+rus+spa+ita+por"]
        return [TESSERACT_LANGS.get(source_lang, "eng")]

    def _best_ocr_result(self, image: Image.Image, languages: list[str], config: str) -> str:
        best_text = ""
        best_score = -1
        for lang in languages:
            text = self.engines.pytesseract.image_to_string(image, lang=lang, config=config)
            score = sum(ch.isalnum() or "\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff" or "\uac00" <= ch <= "\ud7af" for ch in text)
            if score > best_score:
                best_text = text
                best_score = score
        return best_text


class AudioSubtitleWorker(threading.Thread):
    def __init__(
        self,
        engines: OptionalEngines,
        translator: Translator,
        output: queue.Queue,
        stop_event: threading.Event,
        settings_getter,
    ) -> None:
        super().__init__(daemon=True)
        self.engines = engines
        self.translator = translator
        self.output = output
        self.stop_event = stop_event
        self.settings_getter = settings_getter
        self.last_text = ""

    def run(self) -> None:
        if not self.engines.soundcard or not self.engines.faster_whisper or not self.engines.numpy:
            self.output.put(
                Subtitle(
                    "音频字幕依赖未安装",
                    "请安装 soundcard、faster-whisper、numpy 后再启用电脑内置播放音频字幕。",
                    "audio",
                    "等待依赖",
                )
            )
            return

        settings = self.settings_getter()
        model_name = settings["whisper_model"]
        self.output.put(Subtitle("正在加载语音模型", f"Whisper 模型：{model_name}", "audio", "加载中"))

        try:
            model = self.engines.faster_whisper.WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
            )
        except Exception as exc:
            self.output.put(Subtitle("Whisper 模型加载失败", str(exc), "audio", "错误"))
            return

        try:
            mic = self._select_loopback_device()
        except Exception as exc:
            self.output.put(Subtitle("系统音频捕获失败", str(exc), "audio", "错误"))
            return

        samplerate = 16000
        chunk_seconds = 4
        self.output.put(Subtitle("音频字幕已启动", "正在监听电脑当前播放的声音。", "audio", "实时"))

        try:
            with mic.recorder(samplerate=samplerate, channels=1) as recorder:
                while not self.stop_event.is_set():
                    settings = self.settings_getter()
                    audio = recorder.record(numframes=samplerate * chunk_seconds)
                    audio = self._to_mono_float32(audio)
                    if self._is_quiet(audio):
                        continue

                    source_lang = WHISPER_LANGS.get(settings["source"])
                    try:
                        segments, _info = model.transcribe(
                            audio,
                            language=source_lang,
                            vad_filter=True,
                            beam_size=1,
                        )
                        text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
                    except Exception as exc:
                        self.output.put(Subtitle("语音识别失败", str(exc), "audio", "错误"))
                        continue

                    if text and text != self.last_text:
                        self.last_text = text
                        translated = self.translator.translate(text, settings["source"], settings["target"])
                        self.output.put(Subtitle(text, translated, "audio", "实时"))
        except Exception as exc:
            self.output.put(Subtitle("系统音频捕获中断", str(exc), "audio", "错误"))

    def _to_mono_float32(self, audio):
        np = self.engines.numpy
        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        return audio

    def _is_quiet(self, audio) -> bool:
        np = self.engines.numpy
        if audio.size == 0:
            return True
        rms = float(np.sqrt(np.mean(audio * audio)))
        return rms < 0.008

    def _select_loopback_device(self):
        settings = self.settings_getter()
        preferred = settings.get("audio_device", "系统默认")
        microphones = self.engines.soundcard.all_microphones(include_loopback=True)
        loopbacks = [mic for mic in microphones if "loopback" in str(mic).lower()]

        if preferred and preferred != "系统默认":
            for mic in loopbacks:
                if preferred in str(mic):
                    return mic

        speaker = self.engines.soundcard.default_speaker()
        for mic in loopbacks:
            if speaker.name in str(mic):
                return mic
        if loopbacks:
            return loopbacks[0]
        return self.engines.soundcard.get_microphone(speaker.name, include_loopback=True)


class RegionSelector(tk.Toplevel):
    def __init__(self, root: tk.Tk, on_selected) -> None:
        super().__init__(root)
        self.on_selected = on_selected
        self.start_x = 0
        self.start_y = 0
        self.rect_id = None
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.28)
        self.configure(bg="black")
        self.title("选择屏幕翻译区域")
        self.canvas = tk.Canvas(self, cursor="crosshair", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Escape>", lambda _event: self.destroy())

    def _on_press(self, event) -> None:
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.rect_id = self.canvas.create_rectangle(
            event.x,
            event.y,
            event.x,
            event.y,
            outline="#facc15",
            width=3,
        )

    def _on_drag(self, event) -> None:
        if self.rect_id is not None:
            self.canvas.coords(
                self.rect_id,
                self.start_x - self.winfo_rootx(),
                self.start_y - self.winfo_rooty(),
                event.x_root - self.winfo_rootx(),
                event.y_root - self.winfo_rooty(),
            )

    def _on_release(self, event) -> None:
        left = min(self.start_x, event.x_root)
        top = min(self.start_y, event.y_root)
        width = abs(event.x_root - self.start_x)
        height = abs(event.y_root - self.start_y)
        self.destroy()
        if width < 20 or height < 20:
            return
        self.on_selected(CaptureRegion(left, top, width, height))


class SubtitleWindow(tk.Toplevel):
    def __init__(self, root: tk.Tk) -> None:
        super().__init__(root)
        self.title("奶龙字幕")
        screen_w = self.winfo_screenwidth()
        width = min(980, max(680, screen_w - 320))
        height = 72
        x = int((screen_w - width) / 2)
        y = max(20, self.winfo_screenheight() - height - 88)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.configure(bg="#111827")
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.88)
        self.overrideredirect(True)
        if ICON_PATH.exists():
            self.iconbitmap(str(ICON_PATH))

        self.show_original = tk.BooleanVar(value=False)
        self.source_text = ""
        self.translated_text = "奶龙实时翻译已在后台运行"
        self.display_var = tk.StringVar(value=self.translated_text)

        self.label = tk.Label(
            self,
            textvariable=self.display_var,
            fg="#ffffff",
            bg="#111827",
            font=("Microsoft YaHei UI", 20, "bold"),
            wraplength=width - 48,
            justify="center",
        )
        self.label.pack(fill="both", expand=True, padx=24, pady=10)
        self.label.bind("<Double-Button-1>", lambda _event: root.deiconify())
        self.bind("<Double-Button-1>", lambda _event: root.deiconify())

    def set_show_original(self, value: bool) -> None:
        self.show_original.set(value)
        self._refresh_text()

    def update_subtitle(self, subtitle: Subtitle) -> None:
        self.source_text = subtitle.source
        self.translated_text = subtitle.translated or subtitle.source
        self._refresh_text()

    def _refresh_text(self) -> None:
        if self.show_original.get() and self.source_text:
            self.display_var.set(f"{self.source_text}  |  {self.translated_text}")
        else:
            self.display_var.set(self.translated_text)


class TextOverlayWindow(tk.Toplevel):
    def __init__(self, root: tk.Tk) -> None:
        super().__init__(root)
        self.title("奶龙文字覆盖")
        self.withdraw()
        self.configure(bg="#111827")
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.88)
        self.overrideredirect(True)
        if ICON_PATH.exists():
            self.iconbitmap(str(ICON_PATH))
        self.text_var = tk.StringVar(value="")
        self.label = tk.Label(
            self,
            textvariable=self.text_var,
            fg="#ffffff",
            bg="#111827",
            font=("Microsoft YaHei UI", 16, "bold"),
            justify="left",
            wraplength=760,
            padx=16,
            pady=10,
        )
        self.label.pack(fill="both", expand=True)
        self.label.bind("<Double-Button-1>", lambda _event: root.deiconify())

    def update_overlay(self, subtitle: Subtitle, show_original: bool) -> None:
        region = subtitle.region
        if region is None:
            self.withdraw()
            return
        text = subtitle.translated or subtitle.source
        if show_original:
            text = f"{subtitle.source}\n{text}"
        width = max(320, min(region.width, 900))
        height = max(72, min(region.height + 34, 260))
        self.label.configure(wraplength=width - 32)
        self.text_var.set(text)
        self.geometry(f"{width}x{height}+{region.left}+{region.top}")
        self.deiconify()
        self.lift()

    def hide(self) -> None:
        self.withdraw()


class App:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("920x680")
        self.root.minsize(820, 620)
        if ICON_PATH.exists():
            self.root.iconbitmap(str(ICON_PATH))

        self.engines = OptionalEngines()
        self.translator = Translator(self.engines)
        self.subtitles: queue.Queue[Subtitle] = queue.Queue()
        self.stop_event = threading.Event()
        self.workers: list[threading.Thread] = []
        self.subtitle_window: SubtitleWindow | None = None
        self.text_overlay_window: TextOverlayWindow | None = None
        self.region: CaptureRegion | None = None

        self.source_var = tk.StringVar(value="自动检测")
        self.target_var = tk.StringVar(value="中文")
        self.mode_screen = tk.BooleanVar(value=True)
        self.mode_audio = tk.BooleanVar(value=True)
        self.show_original_var = tk.BooleanVar(value=False)
        self.display_mode_var = tk.StringVar(value="字幕条")
        self.interval_var = tk.DoubleVar(value=1.2)
        self.whisper_model_var = tk.StringVar(value="tiny")
        self.audio_device_var = tk.StringVar(value="系统默认")
        self.region_var = tk.StringVar(value="屏幕区域：全屏")
        self.status_var = tk.StringVar(value="准备就绪")

        self._build_ui()
        self.tray_icon = None
        self._setup_tray()
        self.root.after(250, self._poll_subtitles)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(300, self.start_minimized)

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, padding=22)
        shell.pack(fill="both", expand=True)

        header = ttk.Frame(shell)
        header.pack(fill="x")

        if IMAGE_PATH.exists():
            image = Image.open(IMAGE_PATH).resize((78, 78), Image.Resampling.LANCZOS)
            self.logo = ImageTk.PhotoImage(image)
            ttk.Label(header, image=self.logo).pack(side="left", padx=(0, 16))

        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text=APP_NAME, font=("Microsoft YaHei UI", 23, "bold")).pack(anchor="w")
        ttk.Label(
            title_box,
            text="实时屏幕文字翻译 + 电脑内置播放音频字幕",
            font=("Microsoft YaHei UI", 11),
        ).pack(anchor="w", pady=(4, 0))

        controls = ttk.LabelFrame(shell, text="翻译设置", padding=16)
        controls.pack(fill="x", pady=(24, 12))

        ttk.Label(controls, text="原语言").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Combobox(
            controls,
            textvariable=self.source_var,
            values=list(LANGUAGES),
            state="readonly",
            width=18,
        ).grid(row=0, column=1, sticky="w")

        ttk.Label(controls, text="目标语言").grid(row=0, column=2, sticky="w", padx=(24, 8))
        ttk.Combobox(
            controls,
            textvariable=self.target_var,
            values=list(LANGUAGES)[1:],
            state="readonly",
            width=18,
        ).grid(row=0, column=3, sticky="w")

        ttk.Button(controls, text="中外互换", command=self.swap_languages).grid(row=0, column=4, sticky="w", padx=(14, 0))

        ttk.Checkbutton(controls, text="检测屏幕显示语言", variable=self.mode_screen).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(16, 0)
        )
        ttk.Checkbutton(controls, text="检测电脑内置播放音频", variable=self.mode_audio).grid(
            row=1, column=2, columnspan=2, sticky="w", pady=(16, 0)
        )
        ttk.Checkbutton(controls, text="显示原文", variable=self.show_original_var, command=self.apply_display_options).grid(
            row=1, column=4, sticky="w", pady=(16, 0)
        )

        ttk.Label(controls, text="刷新间隔").grid(row=2, column=0, sticky="w", pady=(16, 0))
        ttk.Scale(controls, from_=0.6, to=3.0, variable=self.interval_var, orient="horizontal").grid(
            row=2, column=1, columnspan=2, sticky="ew", pady=(16, 0)
        )

        ttk.Label(controls, text="语音模型").grid(row=2, column=3, sticky="e", padx=(14, 8), pady=(16, 0))
        ttk.Combobox(
            controls,
            textvariable=self.whisper_model_var,
            values=["tiny", "base", "small"],
            state="readonly",
            width=10,
        ).grid(row=2, column=4, sticky="w", pady=(16, 0))

        ttk.Label(controls, text="音频设备").grid(row=3, column=0, sticky="w", pady=(16, 0))
        self.audio_device_combo = ttk.Combobox(
            controls,
            textvariable=self.audio_device_var,
            values=self.audio_device_options(),
            state="readonly",
            width=46,
        )
        self.audio_device_combo.grid(row=3, column=1, columnspan=4, sticky="ew", pady=(16, 0))

        ttk.Label(controls, text="显示方式").grid(row=4, column=0, sticky="w", pady=(16, 0))
        ttk.Combobox(
            controls,
            textvariable=self.display_mode_var,
            values=["字幕条", "文字覆盖"],
            state="readonly",
            width=18,
        ).grid(row=4, column=1, sticky="w", pady=(16, 0))

        controls.columnconfigure(2, weight=1)

        region_box = ttk.LabelFrame(shell, text="屏幕区域", padding=16)
        region_box.pack(fill="x", pady=(0, 12))
        ttk.Label(region_box, textvariable=self.region_var).pack(side="left", fill="x", expand=True)
        ttk.Button(region_box, text="框选区域", command=self.select_region).pack(side="left", padx=(8, 0))
        ttk.Button(region_box, text="恢复全屏", command=self.clear_region).pack(side="left", padx=(8, 0))

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=8)
        ttk.Button(actions, text="开始实时翻译", command=self.start).pack(side="left")
        ttk.Button(actions, text="停止", command=self.stop).pack(side="left", padx=10)
        ttk.Button(actions, text="显示字幕窗", command=self.show_subtitle_window).pack(side="left")
        ttk.Button(actions, text="引擎状态", command=self.show_engine_status).pack(side="left", padx=10)
        ttk.Button(actions, text="刷新引擎", command=self.refresh_engines).pack(side="left")

        preview = ttk.LabelFrame(shell, text="当前字幕", padding=16)
        preview.pack(fill="both", expand=True, pady=(12, 0))
        self.preview_source = tk.StringVar(value="点击“开始实时翻译”后，这里会显示识别到的原文。")
        self.preview_translated = tk.StringVar(value="这里会显示目标语言字幕。")
        ttk.Label(preview, textvariable=self.preview_source, wraplength=820, font=("Microsoft YaHei UI", 12)).pack(
            anchor="w", fill="x"
        )
        ttk.Label(
            preview,
            textvariable=self.preview_translated,
            wraplength=820,
            font=("Microsoft YaHei UI", 18, "bold"),
        ).pack(anchor="w", fill="x", pady=(12, 0))
        ttk.Label(shell, textvariable=self.status_var).pack(anchor="w", pady=(14, 0))

    def settings(self) -> dict[str, object]:
        return {
            "source": LANGUAGES[self.source_var.get()],
            "target": LANGUAGES[self.target_var.get()],
            "interval": float(self.interval_var.get()),
            "region": self.region,
            "whisper_model": self.whisper_model_var.get(),
            "audio_device": self.audio_device_var.get(),
            "show_original": self.show_original_var.get(),
            "display_mode": self.display_mode_var.get(),
        }

    def audio_device_options(self) -> list[str]:
        if not self.engines.soundcard:
            return ["系统默认"]
        try:
            devices = []
            for mic in self.engines.soundcard.all_microphones(include_loopback=True):
                label = str(mic)
                if "loopback" in label.lower():
                    devices.append(label)
            return ["系统默认"] + devices
        except Exception:
            return ["系统默认"]

    def select_region(self) -> None:
        RegionSelector(self.root, self.set_region)

    def set_region(self, region: CaptureRegion) -> None:
        self.region = region
        self.region_var.set(f"屏幕区域：{region.label()}")

    def clear_region(self) -> None:
        self.region = None
        self.region_var.set("屏幕区域：全屏")

    def swap_languages(self) -> None:
        source = self.source_var.get()
        target = self.target_var.get()
        if source == "自动检测":
            self.source_var.set(target)
            self.target_var.set("中文" if target != "中文" else "英语")
        else:
            self.source_var.set(target)
            self.target_var.set(source)

    def start(self) -> None:
        self.stop()
        self.stop_event = threading.Event()
        self.show_subtitle_window()
        self.apply_display_options()

        if self.mode_screen.get():
            self.workers.append(
                ScreenOcrWorker(self.engines, self.translator, self.subtitles, self.stop_event, self.settings)
            )
        if self.mode_audio.get():
            self.workers.append(
                AudioSubtitleWorker(self.engines, self.translator, self.subtitles, self.stop_event, self.settings)
            )
        if not self.workers:
            messagebox.showinfo(APP_NAME, "请至少选择一种检测方式。")
            return

        for worker in self.workers:
            worker.start()
        self.status_var.set("实时翻译已启动")

    def stop(self) -> None:
        self.stop_event.set()
        self.workers = []
        self.status_var.set("已停止")

    def show_subtitle_window(self) -> None:
        if self.subtitle_window is None or not self.subtitle_window.winfo_exists():
            self.subtitle_window = SubtitleWindow(self.root)
        else:
            self.subtitle_window.deiconify()
            self.subtitle_window.lift()
        self.apply_display_options()

    def show_text_overlay_window(self) -> None:
        if self.text_overlay_window is None or not self.text_overlay_window.winfo_exists():
            self.text_overlay_window = TextOverlayWindow(self.root)

    def apply_display_options(self) -> None:
        if self.subtitle_window and self.subtitle_window.winfo_exists():
            self.subtitle_window.set_show_original(self.show_original_var.get())
            self.subtitle_window.deiconify()
        if self.text_overlay_window and self.text_overlay_window.winfo_exists() and self.display_mode_var.get() != "文字覆盖":
            self.text_overlay_window.hide()

    def show_engine_status(self) -> None:
        messagebox.showinfo(APP_NAME, "\n".join(self.engines.status_lines()))

    def refresh_engines(self) -> None:
        self.engines.refresh()
        if hasattr(self, "audio_device_combo"):
            self.audio_device_combo.configure(values=self.audio_device_options())
        self.status_var.set("引擎状态已刷新")

    def _poll_subtitles(self) -> None:
        while True:
            try:
                subtitle = self.subtitles.get_nowait()
            except queue.Empty:
                break
            self.preview_source.set(subtitle.source)
            self.preview_translated.set(subtitle.translated)
            self.status_var.set(subtitle.status)
            if self.display_mode_var.get() == "文字覆盖" and subtitle.origin == "screen":
                self.show_text_overlay_window()
                self.text_overlay_window.update_overlay(subtitle, self.show_original_var.get())
            elif self.subtitle_window and self.subtitle_window.winfo_exists():
                self.subtitle_window.update_subtitle(subtitle)
        self.root.after(250, self._poll_subtitles)

    def start_minimized(self) -> None:
        self.show_subtitle_window()
        self.start()
        self.root.withdraw()
        self.status_var.set("后台运行中")

    def show_settings(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_settings(self) -> None:
        self.root.withdraw()

    def _setup_tray(self) -> None:
        if not self.engines.pystray:
            return
        try:
            image = Image.open(ICON_PATH if ICON_PATH.exists() else IMAGE_PATH).resize((64, 64), Image.Resampling.LANCZOS)
            menu = self.engines.pystray.Menu(
                self.engines.pystray.MenuItem("打开设置", lambda _icon, _item: self.root.after(0, self.show_settings)),
                self.engines.pystray.MenuItem("隐藏设置", lambda _icon, _item: self.root.after(0, self.hide_settings)),
                self.engines.pystray.MenuItem("开始翻译", lambda _icon, _item: self.root.after(0, self.start)),
                self.engines.pystray.MenuItem("停止翻译", lambda _icon, _item: self.root.after(0, self.stop)),
                self.engines.pystray.MenuItem("退出", lambda _icon, _item: self.root.after(0, self.quit_app)),
            )
            self.tray_icon = self.engines.pystray.Icon(APP_NAME, image, APP_NAME, menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception:
            self.tray_icon = None

    def _on_close(self) -> None:
        self.hide_settings()

    def quit_app(self) -> None:
        self.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
