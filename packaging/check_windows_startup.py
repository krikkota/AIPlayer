"""Launch the actual Windows package; fail unless it renders its first window."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time


def window_texts(pid):
    user32=ctypes.WinDLL('user32',use_last_error=True)
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.EnumChildWindows.argtypes = [wintypes.HWND, callback, wintypes.LPARAM]
    user32.EnumWindows.argtypes = [callback, wintypes.LPARAM]
    result=[]
    def text(hwnd):
        length=user32.GetWindowTextLengthW(hwnd)
        buffer=ctypes.create_unicode_buffer(min(length,16384)+1)
        user32.GetWindowTextW(hwnd,buffer,len(buffer))
        return buffer.value
    def visit(hwnd,_):
        owner=wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid:
            values=[text(hwnd)]
            def child(child_hwnd,_):
                value=text(child_hwnd)
                if value:values.append(value)
                return True
            child_callback=callback(child)
            user32.EnumChildWindows(hwnd,child_callback,0)
            result.append(values)
        return True
    handler=callback(visit)
    user32.EnumWindows(handler,0)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--exe')
    parser.add_argument('--installer')
    parser.add_argument('--report-root',default='work/startup-check')
    parser.add_argument('--platform',default='windows')
    args=parser.parse_args()
    report=Path(args.report_root).resolve();report.mkdir(parents=True,exist_ok=True)
    if args.installer:
        install_dir=report/'Установка плеера'
        installed=subprocess.run([str(Path(args.installer).resolve()),'/VERYSILENT',
            '/SUPPRESSMSGBOXES','/NORESTART','/SP-',f'/DIR={install_dir}',f'/LOG={report/"install.log"}'],timeout=180)
        if installed.returncode:
            raise RuntimeError(f'Installer exited {installed.returncode}')
        exe=install_dir/'AIPlayer.exe'
    else:
        exe=Path(args.exe).resolve()
    (report/'payload.txt').write_text('\n'.join(str(p.relative_to(exe.parent)) for p in sorted(exe.parent.rglob('*')) if p.is_file()),encoding='utf-8')
    screenshot=report/'first-window.png'
    env={**os.environ,'QT_QPA_PLATFORM':args.platform,'AIPLAYER_STARTUP_CHECK':'1',
         'AIPLAYER_STARTUP_LOG':str(report/'startup.log')}
    args=[str(exe),'--data-dir',str(report/'Чистые настройки'),'--quit-after','5500',
          '--screenshot',str(screenshot),'--mute']
    started=time.monotonic();dialogs=[];timed_out=False
    with (report/'stdout.log').open('wb') as output,(report/'stderr.log').open('wb') as error:
        process=subprocess.Popen(args,cwd=exe.parent,env=env,stdout=output,stderr=error)
        while process.poll() is None and time.monotonic()-started<30:
            dialogs=window_texts(process.pid)
            time.sleep(.25)
        if process.poll() is None:
            timed_out=True;process.kill();process.wait()
    dimensions=None
    if screenshot.exists():
        with screenshot.open('rb') as stream:header=stream.read(24)
        if header[:8]==b'\x89PNG\r\n\x1a\n':dimensions=struct.unpack('>II',header[16:24])
    passed=process.returncode==0 and dimensions and min(dimensions)>=300 and not timed_out
    result=dict(exe=str(exe),exit_code=process.returncode,timed_out=timed_out,
                screenshot_dimensions=dimensions,windows=dialogs,passed=bool(passed))
    (report/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
