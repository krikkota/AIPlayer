import os
from pathlib import Path
from threading import Event
from urllib.error import URLError

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QUrl, Qt, QPointF
from PySide6.QtGui import QFontDatabase
from PySide6.QtQuick import QQuickItem
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog
import shiboken6

from player.controller import Controller
from player.storage import Store
from player.jobs import check_cancel

_app=None


def test_first_run_download_recovery_optional_ollama_and_first_file(tmp_path,monkeypatch):
    global _app
    _app=QApplication.instance() or QApplication([])
    assets=Path(__file__).resolve().parents[1]/'player/assets'
    for font in (assets/'fonts').glob('*.ttf'):QFontDatabase.addApplicationFont(str(font))
    monkeypatch.setattr(Controller,'checkModel',lambda self:self.update(asrChecking=False,setupPhase='missing'))
    ollama=[]
    def offline(self):
        ollama.append(True);self.update(ollamaState='offline',ollamaInstalled=False)
    monkeypatch.setattr(Controller,'refreshOllama',offline)
    opened=[]
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a:(opened.append(True) or '', ''))
    c=Controller(Store(tmp_path))
    engine=QQmlApplicationEngine()
    for name,value in [('bridge',c),('player',c.player),('sound',c.audio)]:engine.rootContext().setContextProperty(name,value)
    engine.rootContext().setContextProperty('assetRoot',QUrl.fromLocalFile(str(assets)+'/').toString())
    engine.load(QUrl.fromLocalFile(str(assets.parent/'qml/Main.qml')))
    assert engine.rootObjects()
    w=engine.rootObjects()[0]
    def find(name,parent=None):
        parent=parent or w.contentItem()
        if parent.objectName()==name:return parent
        for child in parent.childItems():
            result=find(name,child)
            if result is not None:return result
    def click(name):
        item=find(name);assert item and item.isEnabled() and item.isVisible(),name
        QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint())
        QTest.qWait(30)
    def wait(check):
        for _ in range(150):
            if check():return
            QTest.qWait(10)
        assert check(),c.state
    try:
        QTest.qWait(100)
        assert c.state['onboarding'] and not ollama
        assert find('onboardingContinue').property('text')=='Загрузить 225 МБ'
        def failed(*a):raise URLError('offline')
        monkeypatch.setattr('player.controller.models.download',failed)
        click('onboardingContinue');wait(lambda:not c.state['setupBusy'])
        assert 'интернет' in c.state['setupError'] and find('onboardingContinue').property('text')=='Повторить загрузку'
        def pause(root,cancel,progress):
            folder=root/'models/gigaam-v3';folder.mkdir(parents=True,exist_ok=True)
            (folder/'model.int8.onnx.part').write_bytes(b'partial')
            progress(dict(fraction=.4,bytes=100,total=225000000,speed=1e6,label='Загрузка'))
            cancel.wait(2);check_cancel(cancel)
        monkeypatch.setattr('player.controller.models.download',pause)
        click('onboardingContinue');wait(lambda:c.state['setupBytes']==100)
        click('pauseModelDownload');wait(lambda:not c.state['setupBusy'])
        assert c.state['setupCanResume'] and not c.state['asrReady']
        assert find('onboardingContinue').property('text')=='Продолжить загрузку'
        def ready(root,cancel,progress):
            progress(dict(label='Проверяем целостность модели…'))
            return dict(path=str(root/'models/gigaam-v3'))
        monkeypatch.setattr('player.controller.models.download',ready)
        click('onboardingContinue');wait(lambda:c.state['asrReady'])
        assert Store(tmp_path).settings['asr_path']
        click('onboardingContinue')
        assert c.state['step']==1 and ollama and find('onboardingLaunchOllama').property('text')=='Установить Ollama'
        click('onboardingContinue')
        assert c.state['step']==2 and c.state['onboarding']
        click('onboardingContinue')
        assert opened and not c.state['onboarding'] and Store(tmp_path).settings['onboarded']
        restarted=Controller(Store(tmp_path))
        assert not restarted.state['onboarding']
        restarted.shutdown()
    finally:
        c.shutdown()
        for root in engine.rootObjects():shiboken6.delete(root)
        shiboken6.delete(engine)
