from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# No telemetry from the bundled ASR helper, no implicit model downloads.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QStandardPaths, QTimer, QUrl
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEvent, Qt

from . import __version__
from .controller import Controller
from .storage import Store


class PlayerApplication(QApplication):
    controller = None
    pending_file = ""

    def event(self, event):
        if event.type() == QEvent.FileOpen:
            path = event.file() or event.url().toLocalFile()
            if not path:
                return False
            if self.controller:
                self.controller.openMedia(path)
            else:
                self.pending_file = path
            return True
        return super().event(event)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?")
    parser.add_argument("--data-dir")
    parser.add_argument("--screenshot")
    parser.add_argument("--quit-after", type=int, default=0)
    parser.add_argument("--show-settings", action="store_true")
    parser.add_argument("--onboarding", action="store_true")
    parser.add_argument("--setup-step", type=int, default=-1)
    parser.add_argument("--trim", action="store_true")
    parser.add_argument("--mute", action="store_true")
    parser.add_argument("--size")
    args = parser.parse_args()
    app = PlayerApplication(sys.argv[:1])
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    app.setOrganizationName("LocalMedia")
    app.setApplicationName("Player")
    app.setApplicationDisplayName("Плеер")
    app.setApplicationVersion(__version__)
    assets = Path(__file__).parent / "assets"
    if sys.platform != "darwin":
        app.setWindowIcon(QIcon(str(assets / "Player.png")))
    for font in (assets / "fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont("Onest", 13))
    root = Path(args.data_dir or os.getenv("PLAYER_DATA_DIR") or
                QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
    controller = Controller(Store(root))
    if args.onboarding:
        controller.update(onboarding=True)
    app.controller = controller
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bridge", controller)
    engine.rootContext().setContextProperty("player", controller.player)
    engine.rootContext().setContextProperty("sound", controller.audio)
    engine.rootContext().setContextProperty("assetRoot", QUrl.fromLocalFile(str(assets) + "/").toString())
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "qml/Main.qml")))
    if not engine.rootObjects():
        controller.shutdown()
        raise RuntimeError("Не удалось загрузить интерфейс плеера. Подробности записаны в журнал запуска.")
    window = engine.rootObjects()[0]
    screen = app.primaryScreen()
    if screen:
        area = screen.availableGeometry()
        window.resize(max(window.minimumWidth(), min(1240, area.width()-32)),
                      max(window.minimumHeight(), min(800, area.height()-40)))
    if args.size:
        width, height = (int(x) for x in args.size.split("x"))
        window.resize(width, height)
    if args.mute:
        controller.audio.setMuted(True)
    if args.file:
        QTimer.singleShot(300, lambda: controller.openMedia(args.file))
    elif app.pending_file:
        pending_file = app.pending_file
        app.pending_file = ""
        QTimer.singleShot(300, lambda: controller.openMedia(pending_file))
    if args.show_settings:
        QTimer.singleShot(600, controller.settings)
    if args.setup_step >= 0:
        QTimer.singleShot(900, lambda: controller.setStep(args.setup_step))
    if args.trim:
        QTimer.singleShot(1800, lambda: window.setProperty("trimOpen", True))
    if args.screenshot:
        def capture():
            from PySide6.QtCore import QObject
            instance = controller.player
            if instance:
                details = {}
                for key in ["source", "mediaStatus", "playbackState", "position", "duration", "errorString", "hasVideo"]:
                    try:
                        details[key] = str(instance.property(key))
                    except RuntimeError:
                        details[key] = "unavailable"
                print("PLAYER_STATE", details, flush=True)
            window.grabWindow().save(args.screenshot)
        QTimer.singleShot(max(2000, args.quit_after - 500), capture)
    if args.quit_after:
        QTimer.singleShot(args.quit_after, app.quit)
    app.aboutToQuit.connect(controller.shutdown)
    result = app.exec()
    # Tear down QML while its context objects are still alive.
    import shiboken6
    for item in engine.rootObjects():
        shiboken6.delete(item)
    shiboken6.delete(engine)
    return result


if __name__ == "__main__":
    raise SystemExit(main())

