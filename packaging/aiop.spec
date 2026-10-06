# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the AIOP Windows build.

Produces a onedir bundle at dist/AIOP/. The whisper weights are deliberately
NOT included: they are downloaded on first run (~142 MB). Whisper DLLs and the
config template are copied next to the executable by packaging/build.ps1 so the
frozen path resolution (Path(sys.executable).parent) finds them transparently.
"""

a = Analysis(
    ["../src/aiop/__main__.py"],
    pathex=["../src"],
    binaries=[],
    datas=[],
    hiddenimports=["yaml"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="AIOP",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AIOP",
)