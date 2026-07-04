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
