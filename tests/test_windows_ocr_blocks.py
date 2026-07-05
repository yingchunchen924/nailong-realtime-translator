import importlib.util
import sys
from pathlib import Path


def load_windows_app():
    app_path = Path(__file__).resolve().parents[1] / "apps" / "windows" / "app.py"
    spec = importlib.util.spec_from_file_location("nailong_windows_app", app_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_line_blocks_from_tesseract_data_are_scaled_and_grouped():
    app = load_windows_app()
    engine = app.TesseractOcrEngine(object())

    data = {
        "text": ["Hello", "world", "noise", "Bonjour"],
        "conf": ["92", "87", "12", "88"],
        "block_num": [1, 1, 1, 2],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 1, 1],
        "left": [10, 55, 400, 12],
        "top": [20, 22, 25, 50],
        "width": [40, 35, 20, 60],
        "height": [12, 10, 10, 14],
    }

    blocks = engine._line_blocks_from_data(data, scale=2.0, origin_left=100, origin_top=200)

    assert [block.source for block in blocks] == ["Hello world", "Bonjour"]
    assert blocks[0].region.left == 105
    assert blocks[0].region.top == 210
    assert blocks[0].region.width == 80
    assert blocks[0].region.height == 24
    assert blocks[1].region.left == 106
    assert blocks[1].region.top == 225


def test_text_block_overlay_signature_ignores_tiny_position_jitter():
    app = load_windows_app()

    first = [
        app.TextBlock("Hello", "你好", app.CaptureRegion(100, 200, 160, 30)),
        app.TextBlock("World", "世界", app.CaptureRegion(100, 240, 160, 30)),
    ]
    jittered = [
        app.TextBlock("Hello", "你好", app.CaptureRegion(103, 205, 160, 30)),
        app.TextBlock("World", "世界", app.CaptureRegion(101, 246, 160, 30)),
    ]
    changed = [
        app.TextBlock("Hello", "你好", app.CaptureRegion(100, 200, 160, 30)),
        app.TextBlock("World!", "世界", app.CaptureRegion(100, 240, 160, 30)),
    ]

    assert app.text_block_overlay_signature(first, False) == app.text_block_overlay_signature(jittered, False)
    assert app.text_block_overlay_signature(first, False) != app.text_block_overlay_signature(first, True)
    assert app.text_block_overlay_signature(first, False) != app.text_block_overlay_signature(changed, False)


def test_saved_settings_round_trip_region(tmp_path):
    app = load_windows_app()
    path = tmp_path / "settings.json"
    region = app.CaptureRegion(10, 20, 640, 360)

    app.save_saved_settings(
        {
            "source_label": "英语",
            "target_label": "中文",
            "mode_screen": True,
            "region": app.region_to_dict(region),
        },
        path,
    )

    loaded = app.load_saved_settings(path)
    assert loaded["source_label"] == "英语"
    assert loaded["target_label"] == "中文"
    assert app.region_from_dict(loaded["region"]) == region


def test_invalid_region_settings_are_ignored():
    app = load_windows_app()

    assert app.region_from_dict({"left": 1, "top": 2}) is None
    assert app.region_from_dict("bad") is None


def test_windows_startup_command_quotes_paths():
    app = load_windows_app()

    command = app.windows_startup_command(
        executable=Path(r"C:\Program Files\Python311\python.exe"),
        script_path=Path(r"C:\Users\hp\Documents\Nailong App\app.py"),
        frozen=False,
        background=False,
    )

    assert command == (
        r'"C:\Program Files\Python311\python.exe" '
        r'"C:\Users\hp\Documents\Nailong App\app.py"'
    )


def test_windows_startup_command_for_packaged_exe_has_no_script_arg():
    app = load_windows_app()

    command = app.windows_startup_command(
        executable=Path(r"C:\Program Files\Nailong\奶龙实时翻译.exe"),
        script_path=Path(r"C:\ignored\app.py"),
        frozen=True,
        background=False,
    )

    assert command == r'"C:\Program Files\Nailong\奶龙实时翻译.exe"'


def test_windows_autostart_command_runs_in_background():
    app = load_windows_app()

    command = app.windows_startup_command(
        executable=Path(r"C:\Program Files\Nailong\奶龙实时翻译.exe"),
        frozen=True,
    )

    assert command == r'"C:\Program Files\Nailong\奶龙实时翻译.exe" --background'


def test_single_instance_lock_is_noop_on_non_windows(monkeypatch):
    app = load_windows_app()

    monkeypatch.setattr(app.os, "name", "posix")
    lock = app.acquire_single_instance_lock()

    assert lock is not None
