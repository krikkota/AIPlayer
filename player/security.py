"""Local input boundary. This is input validation, not a decoder sandbox."""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from urllib.parse import unquote, urlsplit

MEDIA_EXTENSIONS = {".mp4", ".m4v", ".mov", ".m4a", ".mkv", ".webm", ".avi",
                    ".mp3", ".wav", ".flac", ".ogg", ".opus", ".aac"}


def local_media_path(value: str | Path) -> Path:
    value = str(value)
    if not value or "\x00" in value or value.startswith(("\\\\", "//")):
        raise ValueError("Откройте локальный аудио- или видеофайл.")
    if value.lower().startswith("file:"):
        url = urlsplit(value)
        if url.netloc not in ("", "localhost") or url.query or url.fragment:
            raise ValueError("Сетевые адреса и плейлисты не поддерживаются.")
        value = unquote(url.path)
        if os.name == "nt" and re.match(r"^/[A-Za-z]:/", value):
            value = value[1:]
    elif re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value) and not re.match(r"^[A-Za-z]:[\\/]", value):
        raise ValueError("Сетевые адреса и плейлисты не поддерживаются.")
    if value.startswith(("\\\\", "//")) or "\x00" in value:
        raise ValueError("Откройте локальный аудио- или видеофайл.")
    path = Path(value).resolve(strict=True)
    if not stat.S_ISREG(path.stat().st_mode) or path.suffix.lower() not in MEDIA_EXTENSIONS:
        raise ValueError("Выберите поддерживаемый аудио- или видеофайл, а не плейлист.")
    with path.open("rb") as stream:
        header = stream.read(512)
    # Reject disguised text playlists before either native decoder sees them.
    known = (header.startswith((b"\x1aE\xdf\xa3", b"fLaC", b"OggS", b"ID3"))
             or (header[:4] in (b"RIFF", b"RF64") and header[8:12] in (b"WAVE", b"AVI "))
             or header[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip")
             or any(header[i] == 0xff and header[i+1] & 0xe0 == 0xe0
                    for i in range(min(16, len(header)-1))))
    if not known:
        raise ValueError("Файл не похож на поддерживаемую запись. Плейлисты и ссылки не открываются.")
    return path


def configure_runtime():
    # Apply before Qt Multimedia is imported, including source/dev launches.
    os.environ["QT_MEDIA_BACKEND"] = "ffmpeg"
    os.environ["QT_FFMPEG_PROTOCOL_WHITELIST"] = "file"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

