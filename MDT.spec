# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['MDT.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.icns', '.'), ('MDT.ui', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MDT',
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
    icon='icon.icns',
)

app = BUNDLE(
    exe,
    name='MDT.app',
    icon='icon.icns',
    bundle_identifier=None,
    info_plist={
        'LSUIElement': '1'
    },
)
