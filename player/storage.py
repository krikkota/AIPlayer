"""Atomic local state. No media content leaves the machine."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import math
from pathlib import Path


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_json(path: Path, default=None, max_bytes=16*1024*1024):
    try:
        with path.open("rb") as stream:
            raw = stream.read(max_bytes+1)
        if len(raw) > max_bytes:
            return default
        return json.loads(raw)
    except (OSError, ValueError, RecursionError):
        return default


def read_transcript(path: Path):
    value = read_json(path, {}, 64*1024*1024)
    if not isinstance(value, dict) or type(value.get("complete")) is not bool:
        return {}
    rows = value.get("segments")
    if not isinstance(rows, list) or len(rows) > 100_000:
        return {}
    def valid(row):
        return (isinstance(row, dict) and isinstance(row.get("text"), str) and len(row["text"]) <= 100_000
                and all(type(row.get(k)) in (int,float) and math.isfinite(row[k]) for k in ("start","end"))
                and 0 <= row["start"] <= row["end"] <= 864_000)
    for row in rows:
        if not valid(row):
            return {}
        words = row.get("words", [])
        if not isinstance(words, list) or len(words)>100_000 or any(not valid(w) for w in words):
            return {}
    return value


def media_key(path: Path) -> str:
    stat = path.stat()
    # Include real file content at both ends so replacing a same-size file
    # cannot accidentally reuse its transcript. Never hash a whole movie.
    digest = hashlib.sha256()
    digest.update(f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    with path.open("rb") as stream:
        digest.update(stream.read(65536))
        stream.seek(max(0, stat.st_size - 65536))
        digest.update(stream.read(65536))
    return digest.hexdigest()[:32]


class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        (root / "cache").mkdir(exist_ok=True, mode=0o700)
        (root / "models").mkdir(exist_ok=True, mode=0o700)
        if os.name == "posix":
            for folder in (root, root/"cache", root/"models"):
                if folder.stat().st_uid == os.getuid():
                    folder.chmod(0o700)
        saved = read_json(root / "settings.json", {}, 1024*1024)
        if not isinstance(saved, dict):
            saved = {}
        self.settings = {"onboarded": False, "asr_path": "", "sat_enabled": False, "semantic_model": "",
                         "semantic_kind": "", "semantic_digest": "", "recent": []}
        for key, default in self.settings.items():
            value = saved.get(key, default)
            if key == "recent":
                value = [p for p in value[:12] if isinstance(p,str) and len(p)<=4096] if isinstance(value,list) else []
            elif type(value) is not type(default) or isinstance(value,str) and len(value)>4096:
                value = default
            self.settings[key] = value

    def update(self, **changes):
        self.settings.update(changes)
        atomic_json(self.root / "settings.json", self.settings)

    def cache(self, key: str, suffix: str) -> Path:
        if any(c in key+suffix for c in ("/", "\\", "\x00")) or key in (".",".."):
            raise ValueError("Некорректное имя локального индекса.")
        return self.root / "cache" / f"{key}.{suffix}"

    def recent(self, path: Path):
        entries = [str(path), *[x for x in self.settings["recent"] if x != str(path)]]
        self.update(recent=entries[:12])

