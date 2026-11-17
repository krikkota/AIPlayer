"""Record startup failures before importing Qt/ONNX, including windowed Windows."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import traceback
from datetime import datetime, timezone


def open_startup_log():
    override=os.getenv('AIPLAYER_STARTUP_LOG')
    if override:
        path=Path(override)
    elif sys.platform=='win32':
        path=Path(os.getenv('LOCALAPPDATA') or Path.home()/'AppData/Local')/'LocalMedia/Player/logs/startup.log'
    elif sys.platform=='darwin':
        path=Path.home()/'Library/Application Support/LocalMedia/Player/logs/startup.log'
    else:
        path=Path(os.getenv('XDG_STATE_HOME') or Path.home()/'.local/state')/'AIPlayer/startup.log'
    try:
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if path.exists() and path.stat().st_size>2*1024*1024:
            path.replace(path.with_name('startup.previous.log'))
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        return path,os.fdopen(descriptor,'a',encoding='utf-8',errors='backslashreplace',buffering=1)
    except OSError:
        stream=tempfile.NamedTemporaryFile(mode='a',encoding='utf-8',prefix='AIPlayer-startup-',suffix='.log',delete=False)
        return Path(stream.name),stream


def show_startup_error(error, log_path):
    if os.getenv('AIPLAYER_STARTUP_CHECK')=='1':
        return
    message=("Не удалось запустить AIPlayer.\n\n"+str(error)[:600]+
             "\n\nЖурнал с подробностями:\n"+str(log_path)+
             "\n\nПередайте этот журнал, чтобы можно было исправить причину.")
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,message,'AIPlayer — ошибка запуска',0x10010)
    elif sys.stderr is not None:
        print(message,file=sys.stderr)


def run(start=None):
    previous_stdout,previous_stderr=sys.stdout,sys.stderr
    old_qt_handler=None;qt_handler_installed=False;log=None;path='Журнал недоступен'
    try:
        path,log=open_startup_log()
        if sys.stdout is None:sys.stdout=log
        if sys.stderr is None:sys.stderr=log
        log.write(f'\nSTART {datetime.now(timezone.utc).isoformat()} platform={sys.platform} frozen={getattr(sys,"frozen",False)}\n')
        log.write(f'executable={sys.executable}\npython={sys.version}\n')
        from PySide6.QtCore import qInstallMessageHandler
        def qt_message(kind,context,message):
            log.write(f'QT {kind.name}: {message}\n')
        old_qt_handler=qInstallMessageHandler(qt_message)
        qt_handler_installed=True
        if start is None:
            from .main import main
            start=main
        result=start()
        if result:
            raise RuntimeError(f'Приложение завершилось до успешного запуска (код {result}).')
        log.write('EXIT 0\n')
        return 0
    except Exception as error:
        if log is not None:
            traceback.print_exc(file=log);log.flush()
        show_startup_error(error,path)
        return 1
    finally:
        if qt_handler_installed:
            qInstallMessageHandler(old_qt_handler)
        sys.stdout,sys.stderr=previous_stdout,previous_stderr
        if log is not None:log.close()
