# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:/Users/lan/WorkBuddy/2026-11-02-19-15-16/tools/platform-tools/adb.exe', '.'), ('C:/Users/lan/WorkBuddy/2026-11-02-19-15-16/tools/platform-tools/AdbWinApi.dll', '.'), ('C:/Users/lan/WorkBuddy/2026-11-02-19-15-16/tools/platform-tools/AdbWinUsbApi.dll', '.'), ('C:/Users/lan/WorkBuddy/2026-11-02-19-15-16/tools/platform-tools/libwinpthread-1.dll', '.')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('rapidocr_onnxruntime')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'easyocr', 'onnxruntime.transformers', 'onnxruntime.quantization', 'onnxruntime.training'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ShuaKe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ShuaKe',
)
