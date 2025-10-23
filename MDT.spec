# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['MDT.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.icns', '.'), ('MDT.ui', '.')],
    hiddenimports=['AppKit', 'AppKit.NSPasteboard'],
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
    entitlements_file='entitlements.plist',
    icon='icon.icns',
)

app = BUNDLE(
    exe,
    name='MDT.app',
    icon='icon.icns',
    bundle_identifier='com.mdt.app',
    info_plist={
        'LSUIElement': '1',
        'NSAppleEventsUsageDescription': '需要权限来切换桌面',
        'NSSystemAdministrationUsageDescription': '需要权限来监听鼠标按键',
        'CFBundleName': 'MDT',
        'CFBundleDisplayName': 'MDT',
        'CFBundleGetInfoString': "MDT - 鼠标桌面切换",
        'CFBundleIdentifier': "com.mdt.app",
        'CFBundleVersion': "1.0.0",
        'CFBundleShortVersionString': "1.0.0",
        'NSHighResolutionCapable': 'True',
    },
)
