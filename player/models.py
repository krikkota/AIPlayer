"""Pinned, verified ASR artifacts. User-owned files are only read."""
from __future__ import annotations

import hashlib
import os
import platform
import urllib.request
import shutil
import time
from pathlib import Path
from PySide6.QtCore import QLockFile

from .jobs import check_cancel

REVISION = "322c3b29492673eb7d0b434bfa9dfb8653e34d02"
BASE = f"https://huggingface.co/istupakov/gigaam-v3-onnx/resolve/{REVISION}/"
FILES = {
    "model.int8.onnx": ("v3_e2e_ctc.int8.onnx", 224893347,
                        "2e3fcb7a7b66030336fd10c2fcfb033bd1dc7e1bf238fe5cfd83b1d0cfc9d28e"),
    "vocab.txt": ("v3_e2e_ctc_vocab.txt", 2007,
                  "142de7570b3de5b3035ce111a89c228e80e6085273731d944093ddf24fa539cd"),
}


class HTTPSRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith("https://"):
            raise ValueError("Источник модели перенаправил загрузку на небезопасный адрес.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_status(root: Path):
    folder = root / "models" / "gigaam-v3"
    partial = sum(min((folder/f"{name}.part").stat().st_size, spec[1])
                  for name, spec in FILES.items()
                  if (folder/f"{name}.part").is_file() and not (folder/f"{name}.part").is_symlink())
    return {"setupCanResume": partial>0, "setupBytes": partial,
            "setupTotal": sum(spec[1] for spec in FILES.values())}


def digest_file(path: Path, cancel=None) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            if cancel is not None:
                check_cancel(cancel)
            result.update(block)
    return result.hexdigest()


def resolve_files(folder: Path):
    result = {}
    for name, (remote, size, sha) in FILES.items():
        file = folder / name
        if not file.is_file():
            file = folder / remote
        if not file.is_file() or file.stat().st_size != size:
            return None
        result[name] = file
    return result


def verify(folder: Path, cancel=None) -> bool:
    files = resolve_files(folder)
    return bool(files and all(digest_file(files[name], cancel) == info[2]
                              for name, info in FILES.items()))


def candidates(root: Path, saved: str):
    paths = [Path(saved)] if saved else []
    paths.append(root / "models" / "gigaam-v3")
    if platform.system() == "Darwin":
        paths.extend([Path("/Applications/Voxsyl.app/Contents/Resources/models/gigaam"),
                      Path.home() / "Applications/Voxsyl.app/Contents/Resources/models/gigaam"])
    # Only known locations and an explicitly selected folder, never a disk scan.
    return list(dict.fromkeys(paths))


def discover(root: Path, saved: str, cancel):
    for folder in candidates(root, saved):
        check_cancel(cancel)
        if resolve_files(folder) and verify(folder, cancel):
            return str(folder)
    return ""


def download(root: Path, cancel, progress):
    (root/"models").mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = QLockFile(str(root/"models"/"gigaam-download.lock"))
    # A large download can legitimately outlive Qt's default stale timeout.
    # Keep PID-based crash recovery, without expiring a live owner's lock.
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        raise ValueError("Модель уже загружается в другом окне плеера. Дождитесь завершения загрузки.")
    try:
        return _download(root, cancel, progress)
    finally:
        lock.unlock()


def _download(root: Path, cancel, progress):
    folder = root / "models" / "gigaam-v3"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    if folder.is_symlink():
        raise ValueError("Каталог загрузки модели не должен быть символической ссылкой.")
    total = sum(x[1] for x in FILES.values())
    complete = 0
    opener = urllib.request.build_opener(HTTPSRedirects())
    started = time.monotonic()
    transferred = 0
    for name, (remote, size, expected) in FILES.items():
        check_cancel(cancel)
        target = folder / name
        partial = folder / f"{name}.part"
        if target.is_symlink() or partial.is_symlink():
            raise ValueError("Файл загрузки модели не должен быть символической ссылкой.")
        if target.is_file() and target.stat().st_size == size and digest_file(target, cancel) == expected:
            complete += size
            continue
        existing = partial.stat().st_size if partial.exists() else 0
        if existing == size and digest_file(partial, cancel) == expected:
            os.replace(partial, target)
            complete += size
            continue
        if existing >= size:
            partial.unlink()
            existing = 0
        if shutil.disk_usage(folder).free < size-existing+32*1024*1024:
            raise ValueError("Недостаточно места для модели. Освободите не менее 260 МБ и повторите загрузку.")
        headers = {"User-Agent": "LocalPlayer/0.1"}
        if existing:
            headers["Range"] = f"bytes={existing}-"
        request = urllib.request.Request(BASE + remote, headers=headers)
        with opener.open(request, timeout=20) as response:
            if existing and response.status != 206:
                existing = 0
            if response.status == 206:
                expected_range = f"bytes {existing}-{size-1}/{size}"
                if response.headers.get("Content-Range") != expected_range:
                    raise ValueError("Источник вернул неверный диапазон файла. Повторите загрузку.")
            with partial.open("ab" if existing else "wb") as stream:
                count = existing
                while True:
                    check_cancel(cancel)
                    block = response.read(min(256 * 1024, size-count+1))
                    if not block:
                        break
                    if count+len(block)>size:
                        raise ValueError("Источник вернул файл больше ожидаемого. Загрузка остановлена.")
                    stream.write(block)
                    count += len(block)
                    transferred += len(block)
                    elapsed = max(.1, time.monotonic()-started)
                    progress({"fraction": min(0.98, (complete + count) / total),
                              "bytes": complete+count, "total": total, "speed": transferred/elapsed,
                              "label": f"Загружено {(complete + count) / 1e6:.0f} из {total / 1e6:.0f} МБ"})
                stream.flush()
                os.fsync(stream.fileno())
        progress({"label": "Проверяем целостность модели…"})
        if partial.stat().st_size != size or digest_file(partial, cancel) != expected:
            partial.unlink(missing_ok=True)
            raise ValueError("Файл модели не прошёл проверку. Повторите загрузку.")
        os.replace(partial, target)
        complete += size
    return {"path": str(folder)}

