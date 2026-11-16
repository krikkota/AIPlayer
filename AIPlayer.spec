# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys
import re
import subprocess
from PyInstaller.utils.hooks import collect_data_files, copy_metadata
import imageio_ffmpeg

root = Path(SPECPATH)
datas = [(str(root / "player/qml"), "player/qml"),
         (str(root / "player/assets"), "player/assets"),
         (str(root / "licenses"), "licenses")]
datas += collect_data_files("onnx_asr", includes=["preprocessors/data/fbanks.npz"])
datas += copy_metadata("onnx-asr")
binary = imageio_ffmpeg.get_ffmpeg_exe()
a = Analysis([str(root / "launcher.py")], pathex=[str(root)],
    binaries=[(binary, "imageio_ffmpeg/binaries")], datas=datas,
    hiddenimports=["PySide6.QtQuick", "PySide6.QtQuickControls2", "PySide6.QtQml",
                   "PySide6.QtMultimedia", "PySide6.QtMultimediaQuick", "PySide6.QtSvg",
                   "onnx_asr.preprocessors.numpy_preprocessor"],
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
              "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtQuick3D", "PySide6.QtCharts",
              "torch", "transformers", "huggingface_hub", "pytest", "tkinter", "matplotlib", "IPython"],
    noarchive=False)

# Qt's generic QML hook collects every installed QML plugin, including the
# 225 MB WebEngine framework. Ship only the modules this app imports.
qt_modules = {"Core", "Gui", "Network", "Widgets", "DBus", "OpenGL", "OpenGLWidgets", "Concurrent",
    "Qml", "QmlMeta", "QmlModels", "QmlWorkerScript", "QmlCore", "QmlCompiler",
    "Quick", "QuickControls2", "QuickControls2Impl", "QuickControls2Basic", "QuickTemplates2",
    "QuickLayouts", "QuickEffects", "ShaderTools", "Multimedia", "MultimediaQuick", "Svg"}

if sys.platform == "darwin":
    # Retain the transitive native framework dependencies of those modules.
    # Filtering by QML imports alone can remove required support frameworks.
    framework_files = {}
    for entry in a.binaries:
        match = re.search(r"/Qt(\w+)\.framework/", entry[0])
        if match:
            framework_files.setdefault(match.group(1), entry[1])
    scanned = set()
    while qt_modules - scanned:
        module = next(iter(qt_modules - scanned))
        scanned.add(module)
        if module not in framework_files:
            continue
        imports = subprocess.check_output(["otool", "-L", framework_files[module]], text=True)
        qt_modules.update(re.findall(r"Qt(\w+)\.framework/", imports))

if sys.platform == "win32":
    # Qt's Windows DLL dependencies differ from macOS frameworks. Preserve
    # their transitive imports before trimming optional Qt modules.
    import pefile
    dll_files = {}
    for entry in a.binaries:
        match = re.search(r"Qt6(\w+)\.dll$", entry[0], re.I)
        if match:
            dll_files[match.group(1).lower()] = entry[1]
    pending = {module.lower() for module in qt_modules}
    scanned = set()
    while pending-scanned:
        module = next(iter(pending-scanned))
        scanned.add(module)
        if module not in dll_files:
            continue
        with pefile.PE(dll_files[module], fast_load=True) as binary_info:
            binary_info.parse_data_directories(directories=[1,13])
            for dependency in (getattr(binary_info,"DIRECTORY_ENTRY_IMPORT",[]) +
                               getattr(binary_info,"DIRECTORY_ENTRY_DELAY_IMPORT",[])):
                match = re.fullmatch(r"Qt6(\w+)\.dll", dependency.dll.decode("ascii"), re.I)
                if match:
                    pending.add(match.group(1).lower())
    qt_modules.update(pending)

qt_modules_lower = {module.lower() for module in qt_modules}

def needed_path(path):
    name = "/"+path.replace("\\", "/").lstrip("/")
    if "/plugins/multimedia/" in name and "ffmpeg" not in name.rsplit("/",1)[-1].lower():
        return False
    qml_root = "/Qt/qml/" if "/Qt/qml/" in name else "/PySide6/qml/" if "/PySide6/qml/" in name else ""
    if qml_root:
        relative = name.split(qml_root, 1)[1]
        if relative.startswith(("QtQml/", "QtMultimedia/")):
            return True
        if relative.startswith("QtQuick/"):
            item = relative[len("QtQuick/"):]
            if "/" not in item:
                return True
            return item.startswith(("Controls/Basic/", "Controls/impl/", "Templates/", "Layouts/", "Window/", "Effects/")) or (item.startswith("Controls/") and item.count("/") == 1)
        return False
    match = re.search(r"/Qt(\w+)\.framework/", name)
    if match and match.group(1).lower() not in qt_modules_lower:
        return False
    match = re.search(r"(?:lib)?Qt6(\w+)(?:\.dll|\.so)", name)
    if match and match.group(1).lower() not in qt_modules_lower:
        return False
    if "/Qt/translations/" in name:
        return name.endswith(("_ru.qm", "_en.qm"))
    return "QtWebEngineProcess" not in name

def needed(entry):
    # PyInstaller also creates flat aliases such as QtWebEngineCore. Keep an
    # alias only if its target survived the module filter; dangling aliases
    # otherwise make macOS's sealed-resource verification fail with ENOENT.
    return needed_path(entry[0]) and (entry[2] != "SYMLINK" or needed_path(entry[1]))

a.binaries = [entry for entry in a.binaries if needed(entry)]
a.datas = [entry for entry in a.datas if needed(entry)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="AIPlayer", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          argv_emulation=False,
          uac_admin=False,
          icon=str(root / "player/assets/Player.icns") if sys.platform == "darwin" else str(root / "player/assets/Player.ico") if sys.platform == "win32" else None)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="AIPlayer")
if sys.platform == "darwin":
    app = BUNDLE(collection, name="AIPlayer.app", icon=str(root / "player/assets/Player.icns"),
        bundle_identifier="local.aiplayer.desktop", info_plist={
            "CFBundleDisplayName": "AIPlayer", "CFBundleShortVersionString": "0.2.0",
            "NSHighResolutionCapable": True, "LSMinimumSystemVersion": "14.0",
            "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
            "CFBundleDocumentTypes": [{"CFBundleTypeName": "Audio and Video", "CFBundleTypeRole": "Viewer",
                "LSItemContentTypes": ["public.movie", "public.audio"],
                "CFBundleTypeExtensions": ["mp4", "mkv", "mov", "webm", "avi", "mp3", "wav", "m4a", "flac", "ogg", "opus"]}]
        })

