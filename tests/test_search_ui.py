"""Exercise the real QML search field and navigation, without model or device dependencies."""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QObject, QPointF, Qt, QUrl, QEventLoop, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import shiboken6

from player.controller import Controller
from player.storage import Store

_application = None


def test_semantic_failure_does_not_replace_literal_search(tmp_path, monkeypatch):
    global _application
    _application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(Controller, "checkModel", lambda self: None)
    store = Store(tmp_path)
    store.update(onboarded=True, semantic_model="fixture-model")
    controller = Controller(store)
    controller._segments = [dict(start=0, end=3, text="Срок и срок")]
    controller.update(transcriptReady=True)
    controller.findText("срок")
    def failure(*args):
        raise ValueError("Некорректный ответ локальной модели")
    monkeypatch.setattr("player.controller.semantic_search", failure)
    try:
        controller.findMeaning("обсуждение сроков")
        for _ in range(100):
            if not controller.state["busy"]:
                break
            QTest.qWait(10)
        assert controller.state["meaningError"] == "Некорректный ответ локальной модели"
        assert not controller.state["error"] and controller.state["searchCount"] == 2
        assert not controller.state["meaningPerformed"] and not controller.meaningResults
        controller.editMeaning("новая тема")
        assert not controller.state["meaningError"] and controller.state["searchCount"] == 2
    finally:
        controller.shutdown()


def test_empty_media_area_opens_dialog_and_accepts_file_drop(tmp_path, monkeypatch):
    from PySide6.QtCore import QMimeData
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QFileOpenEvent
    from PySide6.QtWidgets import QFileDialog
    from player.main import PlayerApplication
    import wave

    global _application
    _application = QApplication.instance() or PlayerApplication([])
    monkeypatch.setattr(Controller, "checkModel", lambda self: None)
    dialogs = []
    def choose_file(*args):
        dialogs.append(True)
        return "", ""
    monkeypatch.setattr(QFileDialog, "getOpenFileName", choose_file)
    store = Store(tmp_path / "data")
    store.update(onboarded=True)
    controller = Controller(store)
    _application.controller = controller
    assets = Path(__file__).resolve().parents[1] / "player/assets"
    engine = QQmlApplicationEngine()
    for name, value in [("bridge", controller), ("player", controller.player), ("sound", controller.audio)]:
        engine.rootContext().setContextProperty(name, value)
    engine.rootContext().setContextProperty("assetRoot", QUrl.fromLocalFile(str(assets) + "/").toString())
    engine.load(QUrl.fromLocalFile(str(assets.parent / "qml/Main.qml")))
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    try:
        QTest.qWait(100)
        QApplication.sendEvent(_application, QFileOpenEvent(QUrl()))
        assert not controller.state["error"]
        area = window.findChild(QQuickItem, "emptyMediaButton")
        for point in [QPointF(area.width()/2, area.height()/2), QPointF(20, 20), QPointF(area.width()-20, area.height()-20)]:
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, area.mapToScene(point).toPoint())
        assert len(dialogs) == 3
        window.requestActivate()
        area.forceActiveFocus()
        QTest.qWait(50)
        assert area.hasActiveFocus()
        assert not window.property("playbackKeysAllowed"), (window.property("activeFocusItem"), window.property("activeFocusControl"))
        QTest.keyClick(window, Qt.Key_Space)
        assert len(dialogs) == 4

        source = tmp_path / "перетаскивание.wav"
        with wave.open(str(source), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 16000)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(source))])
        point = area.mapToScene(QPointF(area.width()/2, area.height()/2)).toPoint()
        enter = QDragEnterEvent(QPointF(point), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(window, enter)
        move = QDragMoveEvent(QPointF(point), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(window, move)
        drop = QDropEvent(QPointF(point), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(window, drop)
        QTest.qWait(50)
        assert drop.isAccepted()
        assert controller.state["hasMedia"] and controller.state["fileName"] == source.name
        QApplication.sendEvent(_application, QFileOpenEvent(str(source)))
        assert controller.state["fileName"] == source.name and not controller.state["error"]
        assert not area.property("visible")
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
        assert len(dialogs) == 4  # loaded media does not reopen the file chooser
    finally:
        _application.controller = None
        controller.shutdown()
        for root in engine.rootObjects():
            shiboken6.delete(root)
        shiboken6.delete(engine)


def test_search_field_arrows_keyboard_empty_and_partial_transcript(tmp_path, monkeypatch):
    global _application
    _application = QApplication.instance() or QApplication([])
    assets = Path(__file__).resolve().parents[1] / "player/assets"
    for font in (assets / "fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(font))
    monkeypatch.setattr(Controller, "checkModel", lambda self: None)
    store = Store(tmp_path)
    store.update(onboarded=True)
    controller = Controller(store)
    controller._segments = [
        {"start": 1, "end": 3, "text": "Срок и срок.", "words": [
            {"text": "Срок", "start": 1, "end": 1.5},
            {"text": "срок.", "start": 2, "end": 2.5}]},
        {"start": 4, "end": 6, "text": "Ещё один СРОК."}]
    controller._segments.extend({"start": 7+i*2, "end": 8+i*2, "text": "Нейтральная фраза для проверки прокрутки."} for i in range(16))
    controller._segments.append({"start": 50, "end": 52, "text": "Последний срок находится вне экрана."})
    controller.rebuild_rows()
    controller.update(transcriptReady=True)
    seeks = []
    controller.seekRequested.connect(seeks.append)
    engine = QQmlApplicationEngine()
    for name, value in [("bridge", controller), ("player", controller.player), ("sound", controller.audio)]:
        engine.rootContext().setContextProperty(name, value)
    engine.rootContext().setContextProperty("assetRoot", QUrl.fromLocalFile(str(assets) + "/").toString())
    engine.load(QUrl.fromLocalFile(str(assets.parent / "qml/Main.qml")))
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    try:
        QTest.qWait(100)
        for name in ["transportMain", "transportOptions"]:
            group = window.findChild(QQuickItem, name)
            buttons = [item for item in group.childItems() if item.property("iconName") is not None]
            centers = [item.y()+item.height()/2 for item in buttons]
            assert max(centers)-min(centers) < .5  # differently sized controls share a visual axis
        field = window.findChild(QQuickItem, "searchField")
        field.setProperty("text", "СрОк")
        QTest.qWait(50)
        assert controller.state["searchCount"] == 4 and seeks[-1] == 1000
        def find_item(name, parent=None):
            parent = parent or window.contentItem()
            if parent.objectName() == name:
                return parent
            for child in parent.childItems():
                found = find_item(name, child)
                if found is not None:
                    return found
            return None
        def click(name):
            item = find_item(name)
            point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
            QTest.qWait(50)
        click("nextResult")
        assert controller.state["searchIndex"] == 1 and seeks[-1] == 2000
        click("previousResult")
        assert controller.state["searchIndex"] == 0
        field.forceActiveFocus()
        QTest.keyClick(window, Qt.Key_Return)
        assert controller.state["searchIndex"] == 1
        QTest.keyClick(window, Qt.Key_Return, Qt.ShiftModifier)
        assert controller.state["searchIndex"] == 0
        window.setProperty("followText", False)
        controller.navigateHit(-1)
        QTest.qWait(50)
        assert controller.state["searchIndex"] == 3 and seeks[-1] == 50000
        assert window.findChild(QObject, "transcriptView").property("contentY") > 0
        field.setProperty("text", "неттакойфразы")
        feedback = window.findChild(QObject, "searchFeedback")
        assert controller.state["searchCount"] == 0
        assert feedback.property("visible") and "Ничего не найдено" in feedback.property("text")
        assert not window.findChild(QObject, "nextResult").property("enabled")
        controller.update(busy=True, operation="transcribe", transcriptPartial=True)
        assert feedback.property("visible") and "Распознавание продолжается" in feedback.property("text")
        controller._segments.append({"start": 53, "end": 55, "text": "Здесь неттакойфразы"})
        controller.rebuild_rows()
        assert controller.state["searchCount"] == 1  # new ASR output refreshes an existing query
        click("clearSearch")
        assert field.property("text") == "" and not controller.state["searchPerformed"]
        controller.update(busy=False, operation="", transcriptPartial=False)
        controller.store.update(semantic_model="fixture-model")
        controller.update(selectedModel="fixture-model")
        calls = []
        def empty_meaning(*args):
            calls.append(args[2])
            return {"hits": [], "kind": "completion"}
        monkeypatch.setattr("player.controller.semantic_search", empty_meaning)
        click("meaningTab")
        meaning_field = window.findChild(QQuickItem, "meaningQuery")
        meaning_field.setProperty("text", "другая тема")
        assert window.property("semantic") and not calls and not controller.state["busy"]
        click("semanticFind")
        loop = QEventLoop()
        timer = QTimer()
        timer.setInterval(20)
        timer.timeout.connect(lambda: loop.quit() if controller.state["meaningPerformed"] else None)
        timer.start()
        QTimer.singleShot(2000, loop.quit)
        loop.exec()
        timer.stop()
        assert calls == ["другая тема"] and controller.state["meaningCount"] == 0
        assert controller.state["meaningPerformed"] and "ничего не найдено" in window.findChild(QObject, "meaningFeedback").property("text")
        from types import SimpleNamespace
        from threading import Event
        installed = [
            dict(name="fixture-model", kind="completion", digest="one", fits=True, sizeLabel="1.9 ГБ"),
            dict(name="embedding-test", kind="embedding", digest="two", fits=True, sizeLabel="0.4 ГБ"),
            dict(name="too-large", kind="completion", digest="three", fits=False, sizeLabel="4.0 ГБ")]
        refreshes = []
        def refresh(self):
            refreshes.append(True)
            self.update(models=installed, ollamaState="ready")
        monkeypatch.setattr(Controller, "refreshOllama", refresh)
        controller.update(selectedModel="fixture-model")
        click("meaningSettingsButton")
        QTest.qWait(300)
        assert refreshes and not controller.state["settingsOpen"]
        combo = window.findChild(QQuickItem, "meaningModelCombo")
        assert combo.property("count") == 2  # models above the limit are excluded
        cancellation = Event()
        controller._operation = SimpleNamespace(cancel=cancellation)
        controller._meaning_hits = [dict(start=1, end=3, row=0, text="Срок")]
        controller.update(busy=True, operation="semantic", meaningPerformed=True, meaningCount=1, meaningIndex=0)
        click("meaningModelCombo")
        QTest.keyClick(window, Qt.Key_Down)
        controller.update(activeRow=5)  # playback updates must not rebuild the open dropdown
        assert combo.property("highlightedIndex") == 1
        QTest.keyClick(window, Qt.Key_Return)
        QTest.qWait(50)
        assert cancellation.is_set() and controller._operation is None
        assert not controller.state["busy"] and not controller.state["meaningPerformed"]
        assert controller.state["meaningCount"] == 0 and not controller._meaning_hits
        assert controller.state["selectedModel"] == "embedding-test"
        assert Store(store.root).settings["semantic_model"] == "embedding-test"
        assert combo.property("displayText") == "embedding-test"
        QTest.keyClick(window, Qt.Key_Escape)
        QTest.qWait(50)
        assert not controller.state["settingsOpen"]
        assert meaning_field.property("text") == "другая тема" and len(calls) == 1  # no automatic search
        click("transcriptTab")
        field.setProperty("text", "срок")
        literal_count = controller.state["searchCount"]
        controller.selectOllamaModel("fixture-model")
        assert literal_count > 0 and controller.state["searchCount"] == literal_count
        assert len(controller._hits) == literal_count  # model changes preserve literal results
        # The two sections have separate drafts/results. A literal search must
        # neither cancel a running model nor be overwritten by its late result.
        release = Event()
        def controlled_meaning(*args):
            calls.append(args[2])
            release.wait(2)
            return {"hits": [dict(start=1, end=3, row=0, text="Срок"),
                             dict(start=50, end=52, row=18, text="Последний срок")], "kind":"completion"}
        monkeypatch.setattr("player.controller.semantic_search", controlled_meaning)
        click("meaningTab")
        assert meaning_field.property("text") == "другая тема"
        meaning_field.setProperty("text", "Обсуждение сроков")
        click("semanticFind")
        running = controller._operation
        assert controller.state["busy"] and running is not None
        click("transcriptTab")
        field.setProperty("text", "Последний")
        assert controller.state["searchCount"] == 1 and not running.cancel.is_set()
        before_completion = list(seeks)
        release.set()
        for _ in range(50):
            if controller.state["meaningPerformed"]:
                break
            QTest.qWait(20)
        assert controller.state["meaningCount"] == 2 and controller.state["searchCount"] == 1
        assert seeks == before_completion  # background completion does not move playback
        click("meaningTab")
        assert meaning_field.property("text") == "Обсуждение сроков"
        click("meaningResult_0")
        assert seeks[-1] == 1000 and controller.state["meaningIndex"] == 0
        click("nextMeaning")
        assert seeks[-1] == 50000 and controller.state["meaningIndex"] == 1
        click("revealMeaning_1")
        assert not window.property("semantic") and field.property("text") == "Последний"
        click("meaningTab")
        assert controller.state["meaningCount"] == 2
        QTest.keyClick(window, Qt.Key_F, Qt.ControlModifier)
        assert not window.property("semantic") and field.hasActiveFocus()
        click("meaningTab")
        release.clear()
        click("semanticFind")
        running = controller._operation
        click("cancelMeaning")
        assert running.cancel.is_set() and not controller.state["busy"]
        release.set()
        QTest.qWait(100)
        assert not controller.state["meaningPerformed"] and not controller.meaningResults
        assert "остановлен" in controller.state["meaningNotice"]
    finally:
        controller.shutdown()
        for root in engine.rootObjects():
            shiboken6.delete(root)
        shiboken6.delete(engine)
