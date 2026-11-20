"""Optionally join incomplete phrases across pauses with SaT 3L INT8."""
from bisect import bisect_left
from math import exp

import numpy as np
import onnxruntime as ort

from .asr import SENTENCE_END, make_segment
from .jobs import check_cancel
from .models import sat_folder, verify_sat

MIN_PAUSE = 2.0
MAX_PAUSE = 5.0
MAX_WORDS = 45
MAX_DURATION = 24.0
CONTINUATION_THRESHOLD = .01


def pause_candidates(segments):
    candidates = []
    end = 0.0
    for index, segment in enumerate(segments):
        if index:
            gap = segment["words"][0]["start"] - end
            if MIN_PAUSE < gap <= MAX_PAUSE and not SENTENCE_END.search(segments[index - 1]["words"][-1]["text"]):
                candidates.append(index)
        end = max(end, segment["end"])
    return candidates


def merge_continuations(segments, scores):
    result = []
    for index, segment in enumerate(segments):
        if scores.get(index, 1.0) >= CONTINUATION_THRESHOLD:
            result.append(segment)
            continue
        previous = result[-1]
        duration = max(previous["end"], segment["end"]) - min(previous["start"], segment["start"])
        if duration <= MAX_DURATION and len(previous["words"]) + len(segment["words"]) <= MAX_WORDS:
            result[-1] = make_segment(previous["words"] + segment["words"])
        else:
            result.append(segment)
    return result


def boundary_scores(segments, candidates, folder, cancel):
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    parts, offsets = [], {}
    length = 0
    for index, segment in enumerate(segments):
        offsets[index] = length
        for word in segment["words"]:
            word_text = word["text"]
            prefix = " " if parts and word_text[0] not in ",.!?;:" else ""
            parts.append(prefix + word_text)
            length += len(prefix) + len(word_text)
    text = "".join(parts)
    check_cancel(cancel)
    encoded = tokenizer.encode(text, add_special_tokens=False)
    ids = encoded.ids
    if not ids:
        return {}
    # Map each proposed cut to the last subword ending exactly at the cut.
    # If a cut does not align with the tokenizer, leave it alone.
    token_at_end = {end: i for i, (start, end) in enumerate(encoded.offsets) if end > start}
    requested = {index: token_at_end[offsets[index]] for index in candidates if offsets[index] in token_at_end}
    if not requested:
        return {}

    options = ort.SessionOptions()
    options.intra_op_num_threads = 3
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    model = ort.InferenceSession(str(folder / "model.onnx"), sess_options=options,
                                 providers=["CPUExecutionProvider"])

    # Same overlapping 510-token windows as the SaT reference. Skip windows
    # that cannot contribute to a requested boundary.
    width = min(510, len(ids))
    last = len(ids) - width
    starts = [*range(0, last, 256), last]
    requested_tokens = sorted(set(requested.values()))
    windows = []
    for start in starts:
        first = bisect_left(requested_tokens, start)
        stop = bisect_left(requested_tokens, start + width)
        if first < stop:
            windows.append((start, requested_tokens[first:stop]))
    samples = {token: [] for token in requested_tokens}
    bos, eos = tokenizer.token_to_id("<s>"), tokenizer.token_to_id("</s>")
    for i in range(0, len(windows), 4):
        check_cancel(cancel)
        batch = windows[i:i + 4]
        inputs = np.array([[bos, *ids[start:start + width], eos] for start, _ in batch], dtype=np.int64)
        logits, = model.run(["logits"], {
            "input_ids": inputs,
            "attention_mask": np.ones(inputs.shape, dtype=np.float32),
        })
        for slot, (start, tokens) in enumerate(batch):
            for token in tokens:
                samples[token].append(float(logits[slot, token - start + 1, 0]))
    # Work in logit space and average overlapping context before the sigmoid.
    return {index: 1 / (1 + exp(-max(-60, min(60, sum(samples[token]) / len(samples[token])))))
            for index, token in requested.items()}


def refine(segments, root, cancel):
    if not segments or any(not row.get("words") or any(not w["text"] for w in row["words"]) for row in segments):
        return segments
    candidates = pause_candidates(segments)
    if not candidates:
        return segments
    if not verify_sat(root, cancel):
        raise ValueError("Файлы SaT не прошли проверку. Загрузите модель заново.")
    scores = boundary_scores(segments, candidates, sat_folder(root), cancel)
    check_cancel(cancel)
    return merge_continuations(segments, scores)
