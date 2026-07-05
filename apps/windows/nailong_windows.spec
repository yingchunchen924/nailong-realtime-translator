# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None

base_dir = Path.cwd()
project_dir = base_dir.parent.parent

datas = [
    (str(project_dir / "assets"), "assets"),
    (str(project_dir / "tessdata"), "tessdata"),
]
binaries = []
hiddenimports = []

for package in (
    "PIL",
    "mss",
    "pytesseract",
    "deep_translator",
    "soundcard",
    "faster_whisper",
    "numpy",
    "pystray",
    "ctranslate2",
    "tokenizers",
    "huggingface_hub",
):
    try:
        package_datas, package_binaries, package_hiddenimports = collect_all(package)
    except Exception:
        continue
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

tesseract_dir = Path(os.environ.get("NAILONG_TESSERACT_DIR", r"C:\Program Files\Tesseract-OCR"))
if (tesseract_dir / "tesseract.exe").exists():
    datas.append((str(tesseract_dir), "tesseract"))

a = Analysis(
    ["app.py"],
    pathex=[str(base_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="奶龙实时翻译",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_dir / "assets" / "nailong.ico"),
)
