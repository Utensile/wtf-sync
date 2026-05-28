# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for WoW WTF Sync Tool
# Works on Windows, macOS, and Linux — run on each platform separately.

import sys

block_cipher = None

a = Analysis(
    ['wow_wtf_sync.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.filedialog'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'pandas', 'PIL', 'matplotlib'],  # keep it slim
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── macOS: build a proper .app bundle ────────────────────────────────────────
if sys.platform == "darwin":
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name='WTF Sync',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,   # no terminal window
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False, upx=True,
        upx_exclude=[],
        name='WTF Sync',
    )
    app = BUNDLE(
        coll,
        name='WTF Sync.app',
        icon=None,
        bundle_identifier='com.wow.wtfsync',
        info_plist={
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleDisplayName': 'WTF Sync',
            'NSHighResolutionCapable': True,
        },
    )

# ── Windows: single .exe, no console window ──────────────────────────────────
elif sys.platform == "win32":
    exe = EXE(
        pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
        name='WTF Sync',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,   # no ugly black cmd window
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
        onefile=True,
    )

# ── Linux: single binary ─────────────────────────────────────────────────────
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
        name='wtf-sync',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        onefile=True,
    )
