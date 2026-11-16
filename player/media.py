from __future__ import annotations

import os
import subprocess
import tempfile
import time
import math
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import soundfile as sf

from .jobs import check_cancel


def ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def process(arguments, cancel):
    # Disk-backed diagnostics avoid retaining decoder output in memory.
    with tempfile.TemporaryFile() as error:
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        child = subprocess.Popen([ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error",
                                 "-protocol_whitelist", "file", "-format_whitelist",
                                 "mov,matroska,webm,avi,wav,mp3,flac,ogg,aac", *arguments],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=error, **flags)
        try:
            while child.poll() is None:
                check_cancel(cancel)
                time.sleep(0.05)
            if child.returncode:
                error.seek(0)
                text = error.read(8192).decode("utf-8", "replace").strip()
                raise RuntimeError(text or "Не удалось обработать этот файл.")
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


def prepare_audio(source: Path, target: Path, cancel, progress):
    if not target.exists():
        fd, name = tempfile.mkstemp(prefix=".aiplayer-", suffix=".wav", dir=target.parent)
        os.close(fd)
        partial = Path(name)
        progress({"label": "Подготавливаем звуковую дорожку…", "fraction": -1})
        try:
            process(["-y", "-i", str(source), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000",
                     "-c:a", "pcm_s16le", "-f", "wav", str(partial)], cancel)
            check_cancel(cancel)
            os.replace(partial, target)
        finally:
            partial.unlink(missing_ok=True)
    with sf.SoundFile(target) as audio:
        length = len(audio)
        bins = 900
        peaks = np.zeros(bins, dtype=np.float32)
        step = max(1, int(np.ceil(length / bins)))
        for i in range(bins):
            check_cancel(cancel)
            block = audio.read(step, dtype="float32")
            if not len(block):
                break
            peaks[i] = float(np.max(np.abs(block)))
        if peaks.max() > 0:
            peaks = np.sqrt(peaks / peaks.max())
        return {"audio": str(target), "waveform": peaks.tolist(), "duration": length / 16000}


def export_clip(source: Path, output: Path, start: float, end: float, video: bool, cancel, progress):
    if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end:
        raise ValueError("Конец фрагмента должен быть позже начала.")
    if source.resolve() == output.resolve():
        raise ValueError("Выберите новый файл для фрагмента.")
    # Never overwrite even a pre-existing destination selected accidentally.
    if output.exists():
        raise ValueError("Этот файл уже существует. Выберите другое имя.")
    fd, name = tempfile.mkstemp(prefix=".aiplayer-", suffix=output.suffix, dir=output.parent)
    os.close(fd)
    partial = Path(name)
    arguments = ["-y", "-ss", f"{start:.3f}", "-i", str(source.resolve()), "-t", f"{end-start:.3f}"]
    if video:
        arguments += ["-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-crf", "18",
                      "-preset", "fast", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    elif output.suffix.lower() == ".wav":
        arguments += ["-map", "0:a:0", "-vn", "-c:a", "pcm_s16le"]
    elif output.suffix.lower() == ".flac":
        arguments += ["-map", "0:a:0", "-vn", "-c:a", "flac"]
    else:
        arguments += ["-map", "0:a:0", "-vn", "-c:a", "aac", "-b:a", "192k"]
    progress({"label": "Сохраняем точный фрагмент…", "fraction": -1})
    try:
        process([*arguments, str(partial)], cancel)
        check_cancel(cancel)
        # Windows rename fails if the destination exists, including on FAT.
        # POSIX rename would overwrite; link supplies no-clobber publication.
        if os.name == "nt":
            os.rename(partial, output)
        else:
            os.link(partial, output)
        return {"path": str(output)}
    finally:
        partial.unlink(missing_ok=True)

