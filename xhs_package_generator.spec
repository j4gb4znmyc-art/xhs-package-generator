# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all


streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all("streamlit")

datas = streamlit_datas + [
    ("app.py", "."),
]
binaries = streamlit_binaries
hiddenimports = streamlit_hiddenimports


a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="XHS_Package_Generator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
