"""GigaAM v3 E2E CTC INT8; bounded audio windows with real CTC times."""
from __future__ import annotations

import gc
import re
from pathlib import Path

import numpy as np
import onnxruntime as ort
import soundfile as sf
from onnx_asr.preprocessors.numpy_preprocessor import GigaamPreprocessorNumpy

from .jobs import check_cancel
from .models import resolve_files, verify

ort.disable_telemetry_events()


def words_from_ctc(log_probs, vocab, offset: float):
    ids = np.argmax(log_probs[0], axis=-1)
    blank = len(vocab) - 1
    emitted = []
    previous = -1
    for frame, value in enumerate(ids):
        token = int(value)
        if token != blank and token != previous:
            emitted.append((vocab[token], offset + frame * 0.04,
                            offset + (frame + 1) * 0.04))
        elif token != blank and emitted:
            emitted[-1] = (emitted[-1][0], emitted[-1][1], offset + (frame + 1) * 0.04)
        previous = token
    words = []
    for token, start, end in emitted:
        if token in ("<unk>", "<blk>", "<blank>"):
            continue
        begins = token.startswith("▁")
        text = token.replace("▁", " ")
        if begins or not words:
            if text.strip():
                words.append({"text": text.strip(), "start": max(0, start), "end": end})
            else:
                words.append({"text": "", "start": max(0, start), "end": end})
        else:
            words[-1]["text"] += text
            words[-1]["end"] = end
    return [word for word in words if word["text"].strip()]


SENTENCE_END = re.compile(r"""[.!?…]["»”’')\]]*$""")
CLAUSE_END = re.compile(r"[,;:]$")
LINKING_WORDS = frozenset(
    "в во на за из от к ко до для по о об обо с со у без под над при про "
    "через между перед и или но а что чтобы который которая которые".split()
)


def split_long_phrase(words):
    """Choose a readable break in the latter half of a long phrase."""
    size = len(words)
    target = size * 0.75
    candidates = range(max(1, size // 2), min(size, max(2, size * 9 // 10 + 1)))

    def quality(index):
        left, right = words[index - 1], words[index]
        pause = right["start"] - left["end"]
        if CLAUSE_END.search(left["text"]):
            priority = 3
        elif left["text"].casefold().lstrip("«\"(") in LINKING_WORDS:
            priority = 0
        elif pause >= 0.45:
            priority = 2
        else:
            priority = 1
        return priority, -abs(index - target)

    return max(candidates, key=quality)


def group_words(words):
    segments, group = [], []
    group_end = 0.0
    for word in words:
        if group and word["start"] - group_end > 2.0:
            segments.append(make_segment(group))
            group = []
        group_end = max(group_end, word["end"]) if group else word["end"]
        group.append(word)
        duration = group_end - group[0]["start"]
        if SENTENCE_END.search(word["text"]):
            segments.append(make_segment(group))
            group = []
        elif len(group) > 1 and (duration >= 24 or len(group) >= 45):
            cut = split_long_phrase(group)
            segments.append(make_segment(group[:cut]))
            group = group[cut:]
            group_end = max(item["end"] for item in group)
    if group:
        segments.append(make_segment(group))
    return segments


def make_segment(words):
    text = " ".join(x["text"] for x in words)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return {"start": round(min(word["start"] for word in words), 3),
            "end": round(max(word["end"] for word in words), 3),
            "text": text, "words": words}


def regroup_cached_segments(segments):
    """Reuse word timings from prior builds when they cover all saved text."""
    words = []
    for segment in segments:
        timed_words = segment.get("words")
        if not timed_words or make_segment(timed_words)["text"] != segment["text"]:
            return segments
        words.extend(timed_words)
    # Adjacent inference windows may overlap slightly. Keep the recognized word
    # order and allow overlap instead of discarding the entire regrouping.
    return group_words(words)


def transcribe(audio_path: Path, model_path: Path, cancel, progress):
    files = resolve_files(model_path)
    if not files or not verify(model_path, cancel):
        raise ValueError("Модель GigaAM недоступна. Укажите её в настройках.")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 3
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.log_severity_level = 3
    session = ort.InferenceSession(str(files["model.int8.onnx"]), options,
                                   providers=["CPUExecutionProvider"])
    preprocessor = GigaamPreprocessorNumpy("gigaam_v3")
    entries = [line.rsplit(" ", 1) for line in files["vocab.txt"].read_text(encoding="utf-8").splitlines()]
    vocab = [""] * len(entries)
    for token, index in entries:
        vocab[int(index)] = token
    words = []
    with sf.SoundFile(audio_path) as audio:
        total = len(audio) / audio.samplerate
        core_start = 0.0
        while core_start < total:
            check_cancel(cancel)
            core_end = min(total, core_start + 20.0)
            start = max(0, core_start - 0.6)
            end = min(total, core_end + 0.6)
            audio.seek(round(start * 16000))
            waveform = audio.read(round((end - start) * 16000), dtype="float32")
            if len(waveform) >= 320 and np.max(np.abs(waveform)) > 0.0001:
                features, lengths = preprocessor(waveform[None, :], np.array([len(waveform)], dtype=np.int64))
                outputs = session.run(["log_probs"], {"features": features, "feature_lengths": lengths})[0]
                part = words_from_ctc(outputs, vocab, start)
                # Each word belongs to one non-overlapping ownership window;
                # context overlaps improve boundaries without duplicate text.
                words.extend(w for w in part if core_start <= (w["start"] + w["end"]) / 2 < core_end)
            segments = group_words(words)
            progress({"fraction": core_end / max(total, 0.001), "label": "Распознаём речь…",
                      "segments": segments})
            core_start = core_end
    del session, preprocessor
    gc.collect()
    return {"segments": group_words(words), "complete": True}

