"""Run the optional model on CPU using a clean, temporary data directory."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from player.models import download_sat
from player.segmentation import refine


def main():
    text = ("Мы", "будем", "получать", "отчёты", "каждую", "неделю.")
    starts = (0.0, 0.3, 0.6, 3.8, 4.1, 4.4)
    words = [dict(text=word, start=at, end=at + 0.25) for word, at in zip(text, starts)]
    from player.asr import group_words

    before = group_words(words)
    assert len(before) == 2
    with TemporaryDirectory(prefix="aiplayer-sat-check-") as folder:
        cancel = Event()
        root = Path(folder)
        download_sat(root, cancel, lambda progress: None)
        after = refine(before, root, cancel)
        assert len(after) == 1
        assert after[0]["words"] == words
    print("SaT INT8 CPU inference passed")


if __name__ == "__main__":
    main()
