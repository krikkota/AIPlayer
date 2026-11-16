from __future__ import annotations

import threading
import traceback
import sys
from PySide6.QtCore import QObject, QRunnable, Signal


class Cancelled(Exception):
    pass


def check_cancel(cancel: threading.Event):
    if cancel.is_set():
        raise Cancelled()


class Events(QObject):
    progress = Signal(object)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class Job(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.events = Events()
        self.cancel = threading.Event()
        self.function = function

    def run(self):
        try:
            self.events.result.emit(self.function(self.cancel, self.events.progress.emit))
        except Cancelled:
            self.events.result.emit({"cancelled": True})
        except Exception as error:
            # Windowed Windows builds may have no stderr. Diagnostics must
            # never prevent delivery of the error/retry state to the UI.
            try:
                if sys.stderr is not None:
                    traceback.print_exc()
            except (OSError, ValueError):
                pass
            self.events.error.emit(str(error))
        finally:
            self.events.finished.emit()

