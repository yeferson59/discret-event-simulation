# -*- mode: python ; coding: utf-8 -*-
# Build con PyInstaller para macOS (.app), Windows (.exe) y Linux desde el
# mismo spec. Correr con: uv run pyinstaller discret_simulator.spec
#
# El ícono es opcional: si `packaging/icon.ico` / `packaging/icon.icns` no
# existen (build local sin generarlos), se usa el default de PyInstaller.
# El workflow de CI (.github/workflows/build-installers.yml) los genera
# antes de este paso.

import os

_ICO = "packaging/icon.ico" if os.path.isfile("packaging/icon.ico") else None
_ICNS = "packaging/icon.icns" if os.path.isfile("packaging/icon.icns") else None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("ui/web", "ui/web")],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name="SimuladorEventosDiscretos",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_ICO,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SimuladorEventosDiscretos",
)

app = BUNDLE(
    coll,
    name="SimuladorEventosDiscretos.app",
    icon=_ICNS,
    bundle_identifier="edu.unipamplona.discretsimulator",
    info_plist={
        "CFBundleName": "Simulador de Eventos Discretos",
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
    },
)
