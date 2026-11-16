"""Literal transcript occurrences with positions in the original text and audio."""
from __future__ import annotations

from html import escape


def text_hits(segments, query):
    query = query.strip().casefold()
    if not query:
        return []
    hits = []
    for row, segment in enumerate(segments):
        text = segment["text"]
        folded, positions = [], []
        for index, character in enumerate(text):
            value = character.casefold()
            folded.append(value)
            positions.extend([index] * len(value))
        folded = "".join(folded)
        cursor = 0
        words = []
        for word in segment.get("words", []):
            at = text.find(word["text"], cursor)
            if at >= 0:
                words.append((at, at + len(word["text"]), word))
                cursor = at + len(word["text"])
        cursor = 0
        while (at := folded.find(query, cursor)) >= 0:
            left, right = positions[at], positions[at + len(query) - 1] + 1
            matched = [w for start, end, w in words if start < right and end > left]
            hits.append({"row": row, "offset": left, "limit": right, "text": text,
                         "start": matched[0]["start"] if matched else segment["start"],
                         "end": matched[-1]["end"] if matched else segment["end"]})
            cursor = at + len(query)
    return hits


def highlighted(text, hits, active):
    parts, cursor = [], 0
    for hit in hits:
        start, end = hit["offset"], hit["limit"]
        parts.append(escape(text[cursor:start]))
        color = "#6a5b88" if hit is active else "#393244"
        parts.append(f'<span style="background-color:{color};color:#ffffff">{escape(text[start:end])}</span>')
        cursor = end
    parts.append(escape(text[cursor:]))
    return "".join(parts)
