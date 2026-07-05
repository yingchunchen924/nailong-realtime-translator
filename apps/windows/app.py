from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageEnhance, ImageOps, ImageTk

APP_NAME = "奶龙实时翻译"
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent
DEFAULT_TESSERACT_EXE = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")


def resource_path(*parts: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).joinpath(*parts)
    project_path = PROJECT_DIR.joinpath(*parts)
    if project_path.exists():
        return project_path
    return BASE_DIR.joinpath(*parts)


ASSET_DIR = resource_path("assets")
ICON_PATH = resource_path("assets", "nailong.ico")
IMAGE_PATH = resource_path("assets", "nailong.jpg")
LOCAL_TESSDATA_DIR = resource_path("tessdata")
BUNDLED_TESSERACT_EXE = resource_path("tesseract", "tesseract.exe")
CONFIG_DIR = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming")) / "NailongRealtimeTranslator"
CONFIG_PATH = CONFIG_DIR / "settings.json"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_RUN_VALUE = "NailongRealtimeTranslator"

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

MAX_TEXT_BLOCKS = 8


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


def region_to_dict(region: CaptureRegion | None) -> dict[str, int] | None:
    if region is None:
        return None
    return {
        "left": region.left,
        "top": region.top,
        "width": region.width,
        "height": region.height,
    }


def region_from_dict(value: object) -> CaptureRegion | None:
    if not isinstance(value, dict):
        return None
    try:
        left = int(value["left"])
        top = int(value["top"])
        width = max(1, int(value["width"]))
        height = max(1, int(value["height"]))
    except (KeyError, TypeError, ValueError):
        return None
    return CaptureRegion(left, top, width, height)


def load_saved_settings(path: Path = CONFIG_PATH) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_saved_settings(settings: dict[str, object], path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def windows_startup_command(
    executable: Path | None = None,
    script_path: Path | None = None,
    frozen: bool | None = None,
    background: bool = True,
) -> str:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    exe = Path(executable or sys.executable)
    if not is_frozen and exe.name.lower() == "python.exe":
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.exists():
            exe = pythonw

    args = [str(exe)]
    if not is_frozen:
        args.append(str(script_path or BASE_DIR / "app.py"))
    if background:
        args.append("--background")
    return subprocess.list2cmdline(args)


def is_windows_autostart_enabled() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, WINDOWS_RUN_VALUE)
        return str(value) == windows_startup_command()
    except Exception:
        return False


def set_windows_autostart(enabled: bool) -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, WINDOWS_RUN_VALUE, 0, winreg.REG_SZ, windows_startup_command())
            else:
                try:
                    winreg.DeleteValue(key, WINDOWS_RUN_VALUE)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


@dataclass
class TextBlock:
    source: str
    translated: str
    region: CaptureRegion


def text_block_overlay_signature(blocks: list[TextBlock], show_original: bool) -> str:
    parts = [f"show_original={int(show_original)}"]
    for block in blocks[:MAX_TEXT_BLOCKS]:
        text = block.translated or block.source
        parts.append(
            "|".join(
                (
                    str(block.region.left // 8),
                    str(block.region.top // 8),
                    str(block.region.width // 8),
                    str(block.region.height // 8),
                    block.source.strip(),
                    text.strip(),
                )
            )
        )
    return "\n".join(parts)


@dataclass
class OcrResult:
    text: str
    blocks: list[TextBlock] = field(default_factory=list)


@dataclass
class Subtitle:
    source: str
    translated: str
    origin: str
    status: str
    region: CaptureRegion | None = None
    blocks: list[TextBlock] = field(default_factory=list)


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
            str(BUNDLED_TESSERACT_EXE) if BUNDLED_TESSERACT_EXE.exists() else None,
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


class TesseractOcrEngine:
    def __init__(self, engines: OptionalEngines) -> None:
        self.engines = engines

    def is_available(self) -> bool:
        return bool(self.engines.pytesseract)

    def recognize(self, image: Image.Image, source_lang: str) -> str:
        return self.recognize_with_blocks(image, source_lang, 0, 0).text

    def recognize_with_blocks(self, image: Image.Image, source_lang: str, origin_left: int, origin_top: int) -> OcrResult:
        if not self.engines.mss or not self.engines.pytesseract:
            return OcrResult("OCR 依赖未安装")

        scale = 1.0
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
            text, blocks = self._best_ocr_result(gray, languages, config, scale, origin_left, origin_top)
        except Exception as exc:
            return OcrResult(f"OCR 失败：{exc}")

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return OcrResult("\n".join(lines[:6]), blocks[:MAX_TEXT_BLOCKS])

    def _ocr_languages(self, source_lang: str) -> list[str]:
        if source_lang == "auto":
            return ["eng", "chi_sim", "jpn", "kor", "deu+fra+rus+spa+ita+por"]
        return [TESSERACT_LANGS.get(source_lang, "eng")]

    def _best_ocr_result(
        self,
        image: Image.Image,
        languages: list[str],
        config: str,
        scale: float,
        origin_left: int,
        origin_top: int,
    ) -> tuple[str, list[TextBlock]]:
        best_text = ""
        best_blocks: list[TextBlock] = []
        best_score = -1
        for lang in languages:
            text, blocks = self._ocr_text_and_blocks(image, lang, config, scale, origin_left, origin_top)
            score = sum(ch.isalnum() or "\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff" or "\uac00" <= ch <= "\ud7af" for ch in text)
            if score > best_score:
                best_text = text
                best_blocks = blocks
                best_score = score
        return best_text, best_blocks

    def _ocr_text_and_blocks(
        self,
        image: Image.Image,
        lang: str,
        config: str,
        scale: float,
        origin_left: int,
        origin_top: int,
    ) -> tuple[str, list[TextBlock]]:
        pytesseract = self.engines.pytesseract
        text = pytesseract.image_to_string(image, lang=lang, config=config)
        try:
            data = pytesseract.image_to_data(image, lang=lang, config=config, output_type=pytesseract.Output.DICT)
        except Exception:
            return text, []
        return text, self._line_blocks_from_data(data, scale, origin_left, origin_top)

    def _line_blocks_from_data(self, data: dict[str, list], scale: float, origin_left: int, origin_top: int) -> list[TextBlock]:
        grouped: dict[tuple[int, int, int], list[dict[str, object]]] = {}
        total = len(data.get("text", []))
        for index in range(total):
            word = str(data["text"][index]).strip()
            if not word:
                continue
            try:
                confidence = float(data["conf"][index])
            except (TypeError, ValueError):
                confidence = -1
            if confidence < 35:
                continue
            key = (
                int(data["block_num"][index]),
                int(data["par_num"][index]),
                int(data["line_num"][index]),
            )
            grouped.setdefault(key, []).append(
                {
                    "text": word,
                    "left": int(data["left"][index]),
                    "top": int(data["top"][index]),
                    "width": int(data["width"][index]),
                    "height": int(data["height"][index]),
                }
            )

        blocks: list[TextBlock] = []
        for words in grouped.values():
            line = " ".join(str(item["text"]) for item in words).strip()
            if len(line) < 2:
                continue
            left = min(int(item["left"]) for item in words)
            top = min(int(item["top"]) for item in words)
            right = max(int(item["left"]) + int(item["width"]) for item in words)
            bottom = max(int(item["top"]) + int(item["height"]) for item in words)
            region = CaptureRegion(
                origin_left + int(left / scale),
                origin_top + int(top / scale),
                max(80, int((right - left) / scale)),
                max(24, int((bottom - top) / scale)),
            )
            blocks.append(TextBlock(line, "", region))
        blocks.sort(key=lambda block: (block.region.top, block.region.left))
        return blocks


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
        self.tesseract = TesseractOcrEngine(engines)

    def run(self) -> None:
        if not self.engines.mss or not self.tesseract.is_available():
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
                origin_left = int(monitor.get("left", 0))
                origin_top = int(monitor.get("top", 0))
                ocr_result = self.tesseract.recognize_with_blocks(pil, settings["source"], origin_left, origin_top)
                text = ocr_result.text
                if text and text != self.last_text:
                    self.last_text = text
                    translated = self.translator.translate(text, settings["source"], settings["target"])
                    translated_blocks = [
                        TextBlock(
                            block.source,
                            self.translator.translate(block.source, settings["source"], settings["target"]),
                            block.region,
                        )
                        for block in ocr_result.blocks
                    ]
                    elapsed = int((time.perf_counter() - started) * 1000)
                    engine_label = settings.get("ocr_engine", "Tesseract")
                    self.output.put(
                        Subtitle(
                            text,
                            translated,
                            "screen",
                            f"{engine_label} OCR {elapsed} ms",
                            region,
                            translated_blocks,
                        )
                    )

            time.sleep(settings["interval"])


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
    def __init__(self, root: tk.Tk, app: "App") -> None:
        super().__init__(root)
        self.root = root
        self.app = app
        self.title("奶龙字幕")
        screen_w = self.winfo_screenwidth()
        width = min(980, max(680, screen_w - 320))
        height = 84
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
        self._drag_start: tuple[int, int] | None = None

        toolbar = tk.Frame(self, bg="#0f172a", height=22)
        toolbar.pack(fill="x", side="top")
        toolbar.pack_propagate(False)
        tk.Label(
            toolbar,
            text="奶龙字幕",
            fg="#cbd5e1",
            bg="#0f172a",
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left", padx=(10, 0))
        tk.Button(
            toolbar,
            text="设置",
            command=self.app.show_settings,
            fg="#ffffff",
            bg="#1f2937",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=8,
            pady=0,
        ).pack(side="right", padx=(0, 6), pady=2)
        tk.Button(
            toolbar,
            text="×",
            command=self.app.hide_subtitle_window,
            fg="#ffffff",
            bg="#7f1d1d",
            activebackground="#991b1b",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            width=3,
            pady=0,
        ).pack(side="right", padx=(0, 8), pady=2)
        self.label = tk.Label(
            self,
            textvariable=self.display_var,
            fg="#ffffff",
            bg="#111827",
            font=("Microsoft YaHei UI", 20, "bold"),
            wraplength=width - 64,
            justify="center",
        )
        self.label.pack(fill="both", expand=True, padx=16, pady=(4, 10))

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="打开设置", command=self.app.show_settings)
        self.menu.add_command(label="隐藏字幕条", command=self.app.hide_subtitle_window)
        self.menu.add_command(label="停止翻译", command=self.app.stop)
        self.menu.add_separator()
        self.menu.add_command(label="退出软件", command=self.app.quit_app)

        for widget in (self, toolbar, self.label):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<Double-Button-1>", lambda _event: self.app.show_settings())
            widget.bind("<Button-3>", self._show_menu)

    def _start_drag(self, event) -> None:
        self._drag_start = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag(self, event) -> None:
        if self._drag_start is None:
            return
        offset_x, offset_y = self._drag_start
        self.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")

    def _show_menu(self, event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

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
        self.root = root
        self.block_windows: list[tk.Toplevel] = []
        self.block_overlay_signature = ""
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
        if subtitle.blocks:
            self.withdraw()
            self._show_block_overlays(subtitle.blocks, show_original)
            return

        self.clear_block_overlays()
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

    def _show_block_overlays(self, blocks: list[TextBlock], show_original: bool) -> None:
        signature = text_block_overlay_signature(blocks, show_original)
        if signature == self.block_overlay_signature:
            return
        self.block_overlay_signature = signature
        self.clear_block_overlays(reset_signature=False)
        for block in blocks[:MAX_TEXT_BLOCKS]:
            window = tk.Toplevel(self.root)
            window.title("奶龙文字覆盖")
            window.configure(bg="#111827")
            window.attributes("-topmost", True)
            window.attributes("-alpha", 0.9)
            window.overrideredirect(True)
            if ICON_PATH.exists():
                window.iconbitmap(str(ICON_PATH))

            text = block.translated or block.source
            if show_original and block.source != text:
                text = f"{block.source}\n{text}"
            width = max(180, min(block.region.width + 44, 760))
            height = max(42, min(block.region.height + (54 if show_original else 34), 180))
            label = tk.Label(
                window,
                text=text,
                fg="#ffffff",
                bg="#111827",
                font=("Microsoft YaHei UI", 12, "bold"),
                justify="left",
                wraplength=width - 22,
                padx=10,
                pady=6,
            )
            label.pack(fill="both", expand=True)
            label.bind("<Double-Button-1>", lambda _event: self.root.deiconify())
            window.bind("<Double-Button-1>", lambda _event: self.root.deiconify())
            x = max(0, min(block.region.left, window.winfo_screenwidth() - width))
            y = max(0, min(block.region.top, window.winfo_screenheight() - height))
            window.geometry(f"{width}x{height}+{x}+{y}")
            self.block_windows.append(window)

    def clear_block_overlays(self, reset_signature: bool = True) -> None:
        if reset_signature:
            self.block_overlay_signature = ""
        for window in self.block_windows:
            if window.winfo_exists():
                window.destroy()
        self.block_windows.clear()

    def hide(self) -> None:
        self.clear_block_overlays()
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
        saved = load_saved_settings()
        self.region = region_from_dict(saved.get("region"))

        self.source_var = tk.StringVar(value=self._saved_choice(saved, "source_label", list(LANGUAGES), "自动检测"))
        self.target_var = tk.StringVar(value=self._saved_choice(saved, "target_label", list(LANGUAGES)[1:], "中文"))
        self.mode_screen = tk.BooleanVar(value=bool(saved.get("mode_screen", True)))
        self.mode_audio = tk.BooleanVar(value=bool(saved.get("mode_audio", True)))
        self.show_original_var = tk.BooleanVar(value=bool(saved.get("show_original", False)))
        self.display_mode_var = tk.StringVar(value=self._saved_choice(saved, "display_mode", ["字幕条", "文字覆盖"], "字幕条"))
        self.interval_var = tk.DoubleVar(value=self._saved_float(saved, "interval", 1.2, 0.6, 3.0))
        self.whisper_model_var = tk.StringVar(value=self._saved_choice(saved, "whisper_model", ["tiny", "base", "small"], "tiny"))
        self.ocr_engine_var = tk.StringVar(value=self._saved_choice(saved, "ocr_engine", ["Tesseract"], "Tesseract"))
        self.audio_device_var = tk.StringVar(value=str(saved.get("audio_device", "系统默认") or "系统默认"))
        self.region_var = tk.StringVar(value=self.region_label())
        self.status_var = tk.StringVar(value="准备就绪")
        self.autostart_var = tk.BooleanVar(value=is_windows_autostart_enabled())

        self._build_ui()
        self.tray_icon = None
        self._setup_tray()
        self.root.after(250, self._poll_subtitles)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        if "--background" in sys.argv:
            self.root.after(300, self.start_minimized)

    @staticmethod
    def _saved_choice(settings: dict[str, object], key: str, valid: list[str], default: str) -> str:
        value = settings.get(key)
        return value if isinstance(value, str) and value in valid else default

    @staticmethod
    def _saved_float(settings: dict[str, object], key: str, default: float, minimum: float, maximum: float) -> float:
        try:
            value = float(settings.get(key, default))
        except (TypeError, ValueError):
            return default
        return min(max(value, minimum), maximum)

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

        ttk.Label(controls, text="OCR 引擎").grid(row=4, column=2, sticky="e", padx=(14, 8), pady=(16, 0))
        ttk.Combobox(
            controls,
            textvariable=self.ocr_engine_var,
            values=["Tesseract"],
            state="readonly",
            width=18,
        ).grid(row=4, column=3, columnspan=2, sticky="w", pady=(16, 0))

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
        ttk.Checkbutton(actions, text="开机自启", variable=self.autostart_var, command=self.toggle_autostart).pack(
            side="left", padx=(12, 0)
        )

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
            "ocr_engine": self.ocr_engine_var.get(),
        }

    def saved_settings(self) -> dict[str, object]:
        return {
            "source_label": self.source_var.get(),
            "target_label": self.target_var.get(),
            "mode_screen": self.mode_screen.get(),
            "mode_audio": self.mode_audio.get(),
            "show_original": self.show_original_var.get(),
            "display_mode": self.display_mode_var.get(),
            "interval": float(self.interval_var.get()),
            "whisper_model": self.whisper_model_var.get(),
            "ocr_engine": self.ocr_engine_var.get(),
            "audio_device": self.audio_device_var.get(),
            "region": region_to_dict(self.region),
        }

    def save_settings(self) -> None:
        try:
            save_saved_settings(self.saved_settings())
        except Exception:
            pass

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
        self.region_var.set(self.region_label())
        self.save_settings()

    def clear_region(self) -> None:
        self.region = None
        self.region_var.set(self.region_label())
        self.save_settings()

    def region_label(self) -> str:
        return f"屏幕区域：{self.region.label()}" if self.region else "屏幕区域：全屏"

    def swap_languages(self) -> None:
        source = self.source_var.get()
        target = self.target_var.get()
        if source == "自动检测":
            self.source_var.set(target)
            self.target_var.set("中文" if target != "中文" else "英语")
        else:
            self.source_var.set(target)
            self.target_var.set(source)
        self.save_settings()

    def start(self) -> None:
        self.stop()
        self.save_settings()
        self.stop_event = threading.Event()
        startup_messages: list[str] = []

        if self.mode_screen.get():
            if self.engines.mss and self.engines.pytesseract and self.engines.tesseract_path:
                self.workers.append(
                    ScreenOcrWorker(self.engines, self.translator, self.subtitles, self.stop_event, self.settings)
                )
            else:
                startup_messages.append("屏幕翻译缺少 mss、pytesseract 或 Tesseract OCR 程序。")
        if self.mode_audio.get():
            if self.engines.soundcard and self.engines.faster_whisper and self.engines.numpy:
                self.workers.append(
                    AudioSubtitleWorker(self.engines, self.translator, self.subtitles, self.stop_event, self.settings)
                )
            else:
                startup_messages.append("音频字幕缺少 soundcard、faster-whisper 或 numpy。")
        if not self.workers:
            message = "\n".join(startup_messages) if startup_messages else "请至少选择一种检测方式。"
            self.preview_source.set("未启动实时翻译")
            self.preview_translated.set(message)
            self.status_var.set("需要先检查设置或依赖")
            self.show_settings()
            messagebox.showinfo(APP_NAME, message)
            return

        self.show_subtitle_window()
        self.apply_display_options()
        for worker in self.workers:
            worker.start()
        suffix = f"；{len(startup_messages)} 项功能因依赖缺失未启动" if startup_messages else ""
        self.status_var.set(f"实时翻译已启动{suffix}")

    def stop(self) -> None:
        self.stop_event.set()
        self.workers = []
        if self.subtitle_window and self.subtitle_window.winfo_exists():
            self.subtitle_window.withdraw()
        if self.text_overlay_window and self.text_overlay_window.winfo_exists():
            self.text_overlay_window.hide()
        self.status_var.set("已停止")

    def show_subtitle_window(self) -> None:
        if self.subtitle_window is None or not self.subtitle_window.winfo_exists():
            self.subtitle_window = SubtitleWindow(self.root, self)
        else:
            self.subtitle_window.deiconify()
            self.subtitle_window.lift()
        self.apply_display_options()

    def hide_subtitle_window(self) -> None:
        if self.subtitle_window and self.subtitle_window.winfo_exists():
            self.subtitle_window.withdraw()

    def show_text_overlay_window(self) -> None:
        if self.text_overlay_window is None or not self.text_overlay_window.winfo_exists():
            self.text_overlay_window = TextOverlayWindow(self.root)

    def apply_display_options(self) -> None:
        self.save_settings()
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

    def toggle_autostart(self) -> None:
        enabled = self.autostart_var.get()
        if set_windows_autostart(enabled):
            self.status_var.set("已开启开机自启" if enabled else "已关闭开机自启")
            return
        self.autostart_var.set(is_windows_autostart_enabled())
        messagebox.showwarning(APP_NAME, "开机自启设置失败，请确认当前 Windows 账户权限。")

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
        self.save_settings()
        self.hide_settings()

    def quit_app(self) -> None:
        self.save_settings()
        self.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
