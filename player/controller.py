from __future__ import annotations

import os
import platform
import shutil
import subprocess
import urllib.error
from pathlib import Path

from PySide6.QtCore import QObject, Property, QThreadPool, QUrl, Signal, Slot, QTimer, Qt
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QFileDialog
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from . import asr, media, models
from .jobs import Job
from .ollama import Ollama, semantic_search
from .storage import Store, atomic_json, media_key, read_json, read_transcript
from .security import local_media_path
from .search import text_hits, highlighted
from .transcript import TranscriptModel


class Controller(QObject):
    changed = Signal()
    rowsChanged = Signal()
    meaningResultsChanged = Signal()
    meaningSettingsRequested = Signal()
    ollamaModelsChanged = Signal()
    waveformChanged = Signal()
    mediaUrlChanged = Signal()
    seekRequested = Signal(int)
    clipRequested = Signal(float, float)
    rowRevealRequested = Signal(int)

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.player = QMediaPlayer(self)
        self.player.setObjectName("mediaPlayer")
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.7)
        self.player.setAudioOutput(self.audio)
        self.player.positionChanged.connect(lambda value: self.updatePosition(value / 1000))
        self.player.errorOccurred.connect(lambda code, text: self.mediaError(text))
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.neural_pool = QThreadPool(self)
        self.neural_pool.setMaxThreadCount(1)
        self._jobs = []
        self._operation = None
        self._discovery = None
        self._generation = 0
        self._path = None
        self._key = ""
        self._audio = ""
        self._url = ""
        self._segments = []
        self._rows = []
        self._transcript_model = TranscriptModel(self)
        self._peaks = []
        self._hits = []
        self._meaning_hits = []
        self._active = -1
        self._selection = (-1, -1)
        self._query = ""
        self._semantic_mode = False
        self._complete = False
        self._state = {"onboarding": not store.settings["onboarded"], "settingsOpen": False,
            "step": 0, "asrReady": False, "asrChecking": True, "asrPath": "",
            "setupBusy": False, "setupLabel": "Проверяем модель…", "setupFraction": -1.0,
            "setupCanResume": False, "setupBytes": 0, "setupTotal": 224895354, "setupSpeed": 0.0,
            "setupPhase": "checking", "ollamaInstalled": self.ollama_installed(),
            "setupError": "", "ollamaState": "unknown", "ollamaError": "", "models": [],
            "selectedModel": store.settings["semantic_model"], "selectedKind": store.settings["semantic_kind"],
            "title": "Плеер", "fileName": "", "status": "Откройте видео или аудио",
            "busy": False, "operation": "", "fraction": -1.0, "error": "", "hasMedia": False,
            "transcriptReady": False, "transcriptPartial": False, "searchCount": 0, "searchIndex": -1,
            "searchHint": "", "activeRow": -1, "selectedStart": -1, "selectedEnd": -1,
            "searchPerformed": False, "searchQuery": "", "searchError": "", "videoResolution": "",
            "meaningPerformed": False, "meaningQuery": "", "meaningCount": 0, "meaningIndex": -1,
            "meaningError": "", "meaningHint": "", "meaningNotice": "",
            "recent": store.settings["recent"], "lastExport": ""}
        QTimer.singleShot(0, self.checkModel)
        self.update(**models.download_status(store.root))

    @Property("QVariantMap", notify=changed)
    def state(self):
        return self._state

    @Property("QVariantList", notify=rowsChanged)
    def rows(self):
        return self._rows

    @Property(QObject, constant=True)
    def transcriptModel(self):
        return self._transcript_model

    @Property("QVariantList", notify=meaningResultsChanged)
    def meaningResults(self):
        return [{**hit, "time": self.formatTime(hit["start"]),
                 "endTime": self.formatTime(hit["end"]),
                 "text": " ".join(row["text"] for row in self._segments
                                   if row["start"] < hit["end"] and row["end"] > hit["start"])}
                for hit in self._meaning_hits]

    @Property("QVariantList", notify=ollamaModelsChanged)
    def meaningModels(self):
        return [model for model in self._state["models"] if model["fits"]]

    @Property("QVariantList", notify=waveformChanged)
    def waveform(self):
        return self._peaks

    @Property(str, notify=mediaUrlChanged)
    def mediaUrl(self):
        return self._url

    @Slot(QObject)
    def attachVideo(self, sink):
        self.player.setVideoSink(sink)
        def dimensions():
            size = sink.videoSize()
            self.update(videoResolution=f"{size.width()} × {size.height()}" if size.isValid() else "")
        sink.videoSizeChanged.connect(dimensions)
        dimensions()

    def update(self, **values):
        models_changed = "models" in values and values["models"] != self._state["models"]
        self._state = {**self._state, **values}
        if models_changed:
            self.ollamaModelsChanged.emit()
        self.changed.emit()

    def job(self, function, result, progress=None, error=None, neural=False):
        job = Job(function)
        self._jobs.append(job)
        job.events.result.connect(result)
        if progress:
            job.events.progress.connect(progress)
        job.events.error.connect(error or (lambda text: self.update(error=text)))
        def done():
            if job in self._jobs:
                self._jobs.remove(job)
        job.events.finished.connect(done)
        (self.neural_pool if neural else self.pool).start(job)
        return job

    def operation(self, kind, function, result, label, neural=False):
        if self._operation:
            self._operation.cancel.set()
        generation = self._generation
        self.update(busy=True, operation=kind, status=label, fraction=-1.0, error="")
        job = None
        def current():
            return generation == self._generation and self._operation is job
        def receive(value):
            if not current():
                return
            self._operation = None
            self.update(busy=False, operation="", fraction=-1.0)
            if value.get("cancelled"):
                self.update(status="Операция отменена")
                if kind == "semantic":
                    self.update(meaningNotice="Поиск остановлен. Его можно запустить снова.")
            else:
                result(value)
        def progress(value):
            if not current():
                return
            self.update(status=value.get("label", label), fraction=value.get("fraction", -1.0))
            if "segments" in value:
                self._segments = value["segments"]
                self.update(transcriptPartial=True)
                self.rebuild_rows()
                atomic_json(self.store.cache(self._key, "transcript.json"),
                            {"segments": self._segments, "complete": False})
        def failure(text):
            if current():
                self._operation = None
                self.update(busy=False, operation="", status="Не удалось завершить операцию")
                if kind == "semantic":
                    self.update(meaningError=text)
                else:
                    self.update(error=text)
        job = self.job(function, receive, progress, failure, neural)
        self._operation = job

    @Slot()
    def checkModel(self):
        if self._discovery or self._state["setupBusy"]:
            return
        self.update(asrChecking=True, setupPhase="checking", setupLabel="Проверяем модель…", setupError="")
        def result(value):
            self._discovery = None
            path = value.get("path", "")
            if path:
                self.store.update(asr_path=path)
            self.update(asrChecking=False, asrReady=bool(path), asrPath=path,
                        setupPhase="ready" if path else "missing",
                        setupLabel="Модель готова" if path else "Нужна модель распознавания")
            if path and self._audio and not self._complete and not self._operation:
                self.transcribe()
        def failure(text):
            self._discovery = None
            self.update(asrChecking=False, setupPhase="error", setupError=text)
        self._discovery = self.job(
            lambda cancel, progress: {"path": models.discover(self.store.root, self.store.settings["asr_path"], cancel)},
            result, error=failure)

    @Slot()
    def chooseModelFolder(self):
        if self._state["setupBusy"] or self._state["asrChecking"]:
            return
        folder = QFileDialog.getExistingDirectory(None, "Папка модели GigaAM")
        if not folder:
            return
        self.update(setupBusy=True, setupPhase="verifying", setupLabel="Проверяем выбранную модель…", setupError="")
        def result(value):
            self.update(setupBusy=False)
            if value.get("cancelled"):
                self.update(setupPhase="paused", setupLabel="Проверка остановлена.")
                return
            self.store.update(asr_path=folder)
            self.update(asrReady=True, asrPath=folder, setupPhase="ready", setupLabel="Модель готова")
            if self._audio and not self._complete and not self._operation:
                self.transcribe()
        def verify(cancel, progress):
            if not models.verify(Path(folder), cancel):
                raise ValueError("В папке нет совместимой GigaAM v3 E2E CTC INT8 или файлы повреждены.")
            return {"path": folder}
        self._setup_job = self.job(verify, result,
            error=lambda text: self.update(setupBusy=False, setupPhase="error", setupError=text))

    @Slot()
    def downloadModel(self):
        if self._state["setupBusy"] or self._state["asrChecking"] or self._state["asrReady"]:
            return
        self.update(setupBusy=True, setupPhase="downloading", setupLabel="Подключаемся…", setupFraction=-1.0, setupError="", setupSpeed=0.0)
        def result(value):
            self.update(setupBusy=False, **models.download_status(self.store.root))
            if value.get("cancelled"):
                self.update(setupPhase="paused", setupLabel="Загрузка приостановлена. Можно продолжить с того же места.")
                return
            self.store.update(asr_path=value["path"])
            self.update(asrReady=True, asrPath=value["path"], setupPhase="ready", setupLabel="Модель готова", setupFraction=1.0)
            if self._audio and not self._complete and not self._operation:
                self.transcribe()
        def download(cancel, progress):
            try:
                return models.download(self.store.root, cancel, progress)
            except (urllib.error.URLError, TimeoutError) as error:
                from .jobs import check_cancel
                check_cancel(cancel)
                raise ValueError("Не удалось связаться с сервером модели. Проверьте интернет и повторите: уже загруженная часть сохранена.") from error
        def progress(value):
            self.update(setupLabel=value.get("label", ""), setupFraction=value.get("fraction", -1.0),
                        setupPhase="verifying" if "целостность" in value.get("label", "") else "downloading",
                        setupBytes=value.get("bytes", self._state["setupBytes"]),
                        setupSpeed=value.get("speed", self._state["setupSpeed"]))
        self._setup_job = self.job(download, result, progress,
            lambda text: self.update(setupBusy=False, setupPhase="error", setupError=text,
                                     **models.download_status(self.store.root)))

    @Slot()
    def cancelSetup(self):
        if hasattr(self, "_setup_job"):
            self._setup_job.cancel.set()

    @Slot(int)
    def setStep(self, step):
        if self._state["setupBusy"]:
            return
        step = max(0, min(2 if self._state["onboarding"] else 1, step))
        self.update(step=step, setupError="")
        if step == 1:
            self.refreshOllama()

    @Slot()
    def finishSetup(self):
        if self._state["setupBusy"]:
            self.cancelSetup()
        self.store.update(onboarded=True)
        self.update(onboarding=False, settingsOpen=False)

    @Slot()
    def finishSetupAndOpen(self):
        self.finishSetup()
        self.openDialog()

    @staticmethod
    def ollama_installed():
        if platform.system() == "Darwin":
            return Path("/Applications/Ollama.app").is_dir() or (Path.home()/"Applications/Ollama.app").is_dir()
        if platform.system() == "Windows":
            return (Path(os.getenv("LOCALAPPDATA", ""))/"Programs/Ollama/ollama app.exe").is_file()
        return bool(shutil.which("ollama"))

    @Slot()
    def settings(self):
        self.update(settingsOpen=True, step=0, setupError="")
        self.checkModel()

    @Slot()
    def semanticSettings(self):
        self.meaningSettingsRequested.emit()

    @Slot()
    def closeSettings(self):
        if self._state["setupBusy"]:
            self.cancelSetup()
        self.update(settingsOpen=False)

    @Slot()
    def refreshOllama(self):
        if self._state["ollamaState"] == "checking":
            return
        self.update(ollamaState="checking", ollamaError="", ollamaInstalled=self.ollama_installed())
        def result(value):
            installed = value.get("models", [])
            self.update(models=installed, ollamaInstalled=True, ollamaState="ready" if installed else "empty")
        self.job(lambda cancel, progress: {"models": Ollama().models(cancel)}, result,
            error=lambda text: self.update(ollamaState="offline", ollamaError=text))

    @Slot(str)
    def selectOllamaModel(self, name):
        model = next((m for m in self._state["models"] if m["name"] == name), None)
        if not model or not model["fits"]:
            self.update(ollamaError="Выберите совместимую модель размером до 3 ГБ.")
            return
        changed = (name, model["kind"], model["digest"]) != (
            self.store.settings["semantic_model"], self.store.settings["semantic_kind"],
            self.store.settings["semantic_digest"])
        if changed:
            self.clearMeaning()
        self.store.update(semantic_model=name, semantic_kind=model["kind"], semantic_digest=model["digest"])
        self.update(selectedModel=name, selectedKind=model["kind"], ollamaError="")

    @Slot()
    def launchOllama(self):
        try:
            if platform.system() == "Darwin":
                subprocess.Popen(["/usr/bin/open", "-a", "Ollama"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif platform.system() == "Windows":
                path = Path(os.getenv("LOCALAPPDATA", "")) / "Programs/Ollama/ollama app.exe"
                if not path.exists():
                    raise FileNotFoundError()
                os.startfile(path)
            else:
                binary = shutil.which("ollama")
                if not binary:
                    raise FileNotFoundError()
                subprocess.Popen([binary, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            QTimer.singleShot(1800, self.refreshOllama)
        except OSError:
            self.installOllama()

    @Slot()
    def installOllama(self):
        suffix = {"Windows":"/windows", "Darwin":"/mac", "Linux":"/linux"}.get(platform.system(), "")
        QDesktopServices.openUrl(QUrl("https://ollama.com/download"+suffix))

    @Slot()
    def openDialog(self):
        name, _ = QFileDialog.getOpenFileName(None, "Открыть видео или аудио", "",
            "Медиа (*.mp4 *.mkv *.mov *.webm *.avi *.m4v *.mp3 *.wav *.m4a *.flac *.ogg *.opus *.aac);;Все файлы (*)")
        if name:
            self.openMedia(name)

    @Slot(str)
    def openMedia(self, name):
        try:
            path = local_media_path(name)
        except (OSError, ValueError) as error:
            self.update(error=str(error) if isinstance(error, ValueError) else "Файл недоступен. Возможно, он был перемещён.")
            return
        if self._operation:
            self._operation.cancel.set()
            self._operation = None
        self._generation += 1
        self._path = path.resolve()
        self._key = media_key(self._path)
        self._audio = ""
        self._peaks = []
        self.waveformChanged.emit()
        cached = read_transcript(self.store.cache(self._key, "transcript.json"))
        self._segments = cached.get("segments", [])
        self._complete = cached.get("complete", False)
        self._query = ""
        self._semantic_mode = False
        self._hits = []
        self.clearMeaning()
        self._active = -1
        self._selection = (-1, -1)
        self.rebuild_rows(reset=True)
        self._url = QUrl.fromLocalFile(str(self._path)).toString()
        self.mediaUrlChanged.emit()
        self.player.setSource(QUrl.fromLocalFile(str(self._path)))
        self.player.play()
        self.store.recent(self._path)
        self.update(title=self._path.stem, fileName=self._path.name, hasMedia=True, error="",
                    recent=self.store.settings["recent"], transcriptReady=self._complete,
                    transcriptPartial=bool(self._segments) and not self._complete, activeRow=-1,
                    selectedStart=-1, selectedEnd=-1, searchCount=0, searchIndex=-1, searchHint="",
                    searchPerformed=False, searchQuery="", searchError="")
        source, target = self._path, self.store.cache(self._key, "audio.wav")
        def ready(value):
            self._audio = value["audio"]
            self._peaks = value["waveform"]
            self.waveformChanged.emit()
            self.update(status="Расшифровка сохранена" if self._complete else "Звуковая дорожка готова")
            if not self._complete and self._state["asrReady"]:
                self.transcribe()
            elif not self._complete and not self._state["asrChecking"]:
                self.update(status="Настройте GigaAM для расшифровки")
        self.operation("prepare", lambda cancel, progress: media.prepare_audio(source, target, cancel, progress),
                       ready, "Подготавливаем звуковую дорожку…")

    @Slot()
    def transcribe(self):
        if not self._audio or not self._state["asrReady"]:
            self.settings()
            return
        audio, folder = Path(self._audio), Path(self._state["asrPath"])
        self.clearMeaning()
        def result(value):
            self._segments = value["segments"]
            self._complete = True
            atomic_json(self.store.cache(self._key, "transcript.json"), value)
            self.rebuild_rows()
            self.update(transcriptReady=True, transcriptPartial=False,
                        status="Расшифровка сохранена" if self._segments else "Речь не обнаружена")
        self.operation("transcribe", lambda cancel, progress: asr.transcribe(audio, folder, cancel, progress),
                       result, "Загружаем GigaAM…", neural=True)

    def rebuild_rows(self, reset=False):
        if self._query:
            index = self._state["searchIndex"]
            previous = self._hits[index] if 0 <= index < len(self._hits) else None
            self._hits = text_hits(self._segments, self._query)
            index = next((i for i, hit in enumerate(self._hits)
                          if previous and (hit["row"], hit["offset"]) ==
                          (previous["row"], previous.get("offset"))), 0 if self._hits else -1)
            self.update(searchCount=len(self._hits), searchIndex=index,
                        searchPerformed=True, searchQuery=self._query)
        active = self._hits[self._state["searchIndex"]] if 0 <= self._state["searchIndex"] < len(self._hits) else None
        literal = bool(self._query)
        matches = {}
        for hit in self._hits:
            matches.setdefault(hit["row"], []).append(hit)
        self._rows = [{**row, "time": self.formatTime(row["start"]), "row": i,
                       "match": i in matches,
                       "richText": highlighted(row["text"],
                            matches.get(i, []) if literal else [], active)}
                      for i, row in enumerate(self._segments)]
        self._transcript_model.replace(self._rows, reset)
        self.rowsChanged.emit()

    @Slot(str, result=str)
    def baseName(self, path):
        return Path(path).name

    @Slot(float, result=str)
    def formatTime(self, seconds):
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"

    @Slot(float)
    def updatePosition(self, seconds):
        active = next((i for i, row in enumerate(self._segments) if row["start"] <= seconds <= row["end"]), -1)
        if active != self._active:
            self._active = active
            self.update(activeRow=active)

    @Slot(int, bool)
    def selectRow(self, index, extend, seek=True):
        if not 0 <= index < len(self._segments):
            return
        anchor = self._selection[0] if extend and self._selection[0] >= 0 else index
        self._selection = (anchor, index)
        low, high = sorted(self._selection)
        self.update(selectedStart=low, selectedEnd=high)
        if not extend and seek:
            self.seekRequested.emit(round(self._segments[index]["start"] * 1000))
        self.rowRevealRequested.emit(index)
        if extend:
            self.trimSelection()

    @Slot(int)
    def selectRowFromPointer(self, index):
        self.selectRow(index, bool(QGuiApplication.keyboardModifiers() & Qt.ShiftModifier))

    @Slot()
    def trimSelection(self):
        low, high = sorted(self._selection)
        if low >= 0:
            index = self._state["meaningIndex"]
            if self._semantic_mode and low == high and 0 <= index < len(self._meaning_hits):
                hit = self._meaning_hits[index]
                if hit["row"] == low:
                    self.clipRequested.emit(hit["start"], hit["end"])
                    return
            self.clipRequested.emit(self._segments[low]["start"], self._segments[high]["end"])

    @Slot(str)
    def findText(self, query):
        self._query = query.strip()
        self._hits = []
        self.update(searchCount=0, searchIndex=-1, searchHint="", searchError="",
                    searchPerformed=bool(self._query), searchQuery=self._query)
        self.rebuild_rows()
        if self._hits:
            self.navigateHit(0)

    @Slot(str)
    def findMeaning(self, query):
        query = query.strip()
        if len(query)>2000:
            self.update(meaningError="Сократите запрос до 2000 символов: опишите одну тему или вопрос.")
            return
        if not query or not self._segments:
            return
        if self._state["busy"]:
            self.update(meaningError="Дождитесь завершения текущей обработки или отмените её.")
            return
        if not self._state["transcriptReady"]:
            self.update(meaningError="Сначала дождитесь готовой расшифровки.")
            return
        model = self.store.settings["semantic_model"]
        if not model:
            self.semanticSettings()
            return
        self._meaning_hits = []
        self.meaningResultsChanged.emit()
        self.update(meaningPerformed=False, meaningQuery=query, meaningCount=0, meaningIndex=-1,
                    meaningError="", meaningHint="", meaningNotice="")
        segments = list(self._segments)
        cache = self.store.cache(self._key, "embeddings.npz")
        def result(value):
            self._meaning_hits = value["hits"]
            self.meaningResultsChanged.emit()
            self.update(meaningCount=len(self._meaning_hits), meaningIndex=-1,
                        meaningPerformed=True, meaningQuery=query,
                        status=f"Найдено фрагментов: {len(self._meaning_hits)}",
                        meaningHint="По близости к теме" if value.get("kind") == "embedding" else "По выбранной теме")
        self.operation("semantic", lambda cancel, progress: semantic_search(
            Ollama(), model, query, segments, cache, cancel, progress), result, "Подключаем выбранную модель…", True)

    @Slot()
    def clearSearch(self):
        self._query = ""
        self._hits = []
        self.update(searchPerformed=False, searchQuery="", searchCount=0, searchIndex=-1, searchHint="", searchError="")
        self.rebuild_rows()

    @Slot(bool)
    def setSearchSection(self, semantic):
        self._semantic_mode = semantic

    @Slot(str)
    def editMeaning(self, query):
        if query.strip() != self._state["meaningQuery"]:
            self.clearMeaning()
            self.update(meaningQuery=query.strip())

    @Slot()
    def clearMeaning(self):
        self._cancel_meaning()
        self._meaning_hits = []
        self.meaningResultsChanged.emit()
        self.update(meaningPerformed=False, meaningQuery="", meaningCount=0, meaningIndex=-1,
                    meaningError="", meaningHint="", meaningNotice="")

    @Slot()
    def cancelMeaning(self):
        self._cancel_meaning()
        self.update(meaningNotice="Поиск остановлен. Его можно запустить снова.")

    def _cancel_meaning(self):
        if self._state["operation"] == "semantic" and self._operation:
            self._operation.cancel.set()
            self._operation = None
            self.update(busy=False, operation="", fraction=-1.0, status="Поиск отменён")

    @Slot(int)
    def selectMeaningResult(self, index):
        if not 0 <= index < len(self._meaning_hits):
            return
        hit = self._meaning_hits[index]
        self.update(meaningIndex=index)
        self.selectRow(hit["row"], False, False)
        self.seekRequested.emit(round(hit["start"] * 1000))

    @Slot(int)
    def navigateMeaning(self, direction):
        if self._meaning_hits:
            current = self._state["meaningIndex"]
            index = (current + direction if current >= 0 else -1 if direction < 0 else 0) % len(self._meaning_hits)
            self.selectMeaningResult(index)

    @Slot(int)
    def navigateHit(self, direction):
        if not self._hits:
            return
        current = self._state["searchIndex"]
        index = ((current + direction) if current >= 0 else (len(self._hits)-1 if direction < 0 else 0)) % len(self._hits)
        hit = self._hits[index]
        self.update(searchIndex=index)
        self.rebuild_rows()
        self.selectRow(hit["row"], False, False)
        self.seekRequested.emit(round(hit["start"] * 1000))

    @Slot(int)
    def navigateTranscript(self, direction):
        if self._query:
            self.navigateHit(direction)
        elif self._segments:
            current = self._selection[1] if self._selection[1] >= 0 else self._active
            index = (current + direction) % len(self._segments) if current >= 0 else (len(self._segments)-1 if direction < 0 else 0)
            self.selectRow(index, False)

    @Slot(float, float, bool)
    def exportClip(self, start, end, video):
        if self._path is None or self._state["busy"]:
            return
        suffix = ".mp4" if video else ".wav"
        suggested = self._path.with_name(f"{self._path.stem} — фрагмент{suffix}")
        filters = "Видео MP4 (*.mp4)" if video else "Аудио WAV (*.wav);;Аудио FLAC (*.flac);;Аудио M4A (*.m4a)"
        name, _ = QFileDialog.getSaveFileName(None, "Сохранить фрагмент", str(suggested), filters)
        if not name:
            return
        output = Path(name)
        if not output.suffix:
            output = output.with_suffix(suffix)
        source = self._path
        def result(value):
            self.update(status="Фрагмент сохранён", lastExport=value["path"])
        self.operation("export", lambda cancel, progress: media.export_clip(source, output, start, end,
                       video, cancel, progress), result, "Сохраняем фрагмент…")

    @Slot()
    def exportTranscript(self):
        if not self._segments:
            return
        name, selected = QFileDialog.getSaveFileName(None, "Сохранить расшифровку",
            str(self._path.with_suffix(".srt")), "Субтитры SRT (*.srt);;Текст (*.txt)")
        if not name:
            return
        target = Path(name)
        if target == self._path or target.exists():
            self.update(error="Выберите новое имя файла для расшифровки.")
            return
        if target.suffix.lower() == ".txt":
            text = "\n\n".join(f"{self.formatTime(s['start'])}  {s['text']}" for s in self._segments)
        else:
            def timestamp(seconds):
                millis = max(0, round(seconds * 1000))
                hours, rest = divmod(millis, 3600000)
                minutes, rest = divmod(rest, 60000)
                secs, ms = divmod(rest, 1000)
                return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"
            text = "\n\n".join(f"{i+1}\n{timestamp(s['start'])} --> {timestamp(s['end'])}\n{s['text']}"
                               for i, s in enumerate(self._segments)) + "\n"
        try:
            with target.open("x", encoding="utf-8") as stream:
                stream.write(text)
            self.update(status="Расшифровка экспортирована")
        except OSError as error:
            self.update(error=str(error))

    @Slot()
    def copyTranscript(self):
        QGuiApplication.clipboard().setText("\n\n".join(s["text"] for s in self._segments))
        self.update(status="Текст скопирован")

    @Slot()
    def revealExport(self):
        path = self._state.get("lastExport")
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    @Slot()
    def cancelOperation(self):
        if self._state["operation"] == "semantic":
            self.cancelMeaning()
            return
        if self._operation:
            self._operation.cancel.set()

    @Slot(str)
    def mediaError(self, text):
        self.update(error="Не удалось воспроизвести файл: " + text)

    @Slot()
    def dismissError(self):
        self.update(error="")

    def shutdown(self):
        self.player.stop()
        for job in self._jobs:
            job.cancel.set()
        self.pool.waitForDone(2500)
        self.neural_pool.waitForDone(5000)

