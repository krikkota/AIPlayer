import hashlib
import json
import threading
from pathlib import Path

import numpy as np
import pytest

from player.asr import words_from_ctc, group_words
from player.jobs import Cancelled
from player.models import digest_file, resolve_files
from player.ollama import Ollama, merge_hits, semantic_search
from player.storage import Store, atomic_json, media_key


def test_ctc_blank_repeat_and_timestamps():
    ids = [0, 0, 3, 0, 1, 1, 3, 2]
    logits = np.full((1, len(ids), 4), -10.0)
    for i, token in enumerate(ids): logits[0, i, token] = 0
    words = words_from_ctc(logits, ["▁да", "!", "▁нет", "<blk>"], 1.0)
    assert [w["text"] for w in words] == ["да", "да!", "нет"]
    assert words[0]["start"] == 1
    assert words[-1]["start"] == pytest.approx(1.28)


def test_phrase_boundaries_keep_pause_and_sentence():
    words = [{"text": "Привет", "start": 0, "end": 1},
             {"text": "мир", "start": 1, "end": 2},
             {"text": "снова.", "start": 2, "end": 3},
             {"text": "Позже", "start": 5, "end": 6}]
    rows = group_words(words)
    assert [r["text"] for r in rows] == ["Привет мир снова.", "Позже"]
    assert rows[1]["start"] == 5


def test_atomic_state_survives_reload_and_unicode(tmp_path):
    store = Store(tmp_path)
    store.update(onboarded=True, asr_path="/модели/речь")
    assert Store(tmp_path).settings["asr_path"] == "/модели/речь"
    assert Store(tmp_path).settings["onboarded"] is True
    assert not list(tmp_path.glob(".write-*"))


def test_replaced_media_invalidates_transcript(tmp_path):
    file = tmp_path / "запись.mp4"
    file.write_bytes(b"video-a")
    first = media_key(file)
    file.write_bytes(b"video-b")
    assert media_key(file) != first


def test_hash_cancellation_and_incomplete_model(tmp_path):
    file = tmp_path / "model.int8.onnx"
    file.write_bytes(b"not a model")
    assert resolve_files(tmp_path) is None
    cancel = threading.Event(); cancel.set()
    with pytest.raises(Cancelled): digest_file(file, cancel)


def test_merge_keeps_gaps_and_verified_source_intervals():
    hits = [{"start": 5, "end": 8, "text": "b", "row": 1, "score": .7},
            {"start": 1, "end": 6, "text": "a", "row": 0, "score": .8},
            {"start": 12, "end": 15, "text": "c", "row": 2, "score": .6}]
    result = merge_hits(hits)
    assert [(h["start"],h["end"]) for h in result] == [(1,8),(12,15)]
    assert result[0]["row"] == 0


class EmbeddingClient:
    digest = "one"
    document_calls = 0
    def verify_model(self, name, cancel):
        return {"name":name,"kind":"embedding","digest":self.digest}
    def embeddings(self, name, texts, cancel):
        if len(texts)>1: self.document_calls += 1
        rows = [[1,0] if "срок" in t else [0,1] for t in texts]
        return np.array(rows,dtype=np.float32)


def test_search_returns_real_phrase_and_invalidates_changed_model(tmp_path):
    client = EmbeddingClient(); cancel = threading.Event()
    rows = [{"start":0,"end":3,"text":"дизайн"},
            {"start":4,"end":7,"text":"сроки запуска"}]
    cache = tmp_path/"index.npz"
    result = semantic_search(client,"model","сроки",rows,cache,cancel,lambda _:None)
    assert result["hits"][0]["start"] == 4
    assert client.document_calls == 1
    semantic_search(client,"model","сроки",rows,cache,cancel,lambda _:None)
    assert client.document_calls == 1
    client.digest = "two"
    semantic_search(client,"model","сроки",rows,cache,cancel,lambda _:None)
    assert client.document_calls == 2


def test_completion_cannot_invent_timestamp_or_segment(monkeypatch):
    client = Ollama()
    monkeypatch.setattr(client, "request", lambda *a,**k:{"message":{"content":'{"ids":[400]}'}})
    with pytest.raises(ValueError, match="проверяемые"):
        client.classify("model","тема",[{"text":"реальная фраза"}],threading.Event())


def test_completion_requests_bounded_schema_without_thinking(monkeypatch):
    client = Ollama()
    def request(path, payload, *args):
        assert path == "/api/chat" and payload["think"] is False
        assert payload["format"]["properties"]["ids"]["items"]["enum"] == [0, 1]
        assert payload["format"]["required"] == ["ids"]
        return {"done_reason": "stop", "message": {"content": '{"ids":[1,1]}'}}
    monkeypatch.setattr(client, "request", request)
    assert client.classify("model", "тема", [{"text":"а"}, {"text":"б"}], threading.Event()) == [1]


@pytest.mark.parametrize("response, error", [
    ({"done_reason":"length", "message":{"content":"", "thinking":"reasoning"}}, "лимиту"),
    ({"message":{"content":'{"ids":[]}'}}, None),
    ({"message":{"content":'{"0":{"reason":"Связь","match":"true"}}'}}, "формат"),
    ({"message":{"content":'{"0":"true"}'}}, "формат"),
    ({"message":{"content":'{"0":1}'}}, "формат"),
    ({"message":{"content":'{}'}}, "формат"),
    ({"message":{"content":'{"ids":[true]}'}}, "формат"),
    ({"message":{"content":'{"ids":["0"]}'}}, "формат"),
    ({"message":{"content":'[]'}}, "формат"),
    ({"message":{"content":'{"ids":[],"timestamp":1}'}}, "формат"),
    ({"message":{"content":''}}, "формат"),
])
def test_completion_distinguishes_empty_results_and_invalid_answers(monkeypatch, response, error):
    client = Ollama()
    monkeypatch.setattr(client, "request", lambda *a, **k: response)
    if error:
        with pytest.raises(ValueError, match=error):
            client.classify("model", "тема", [{"text":"фраза"}], threading.Event())
    else:
        assert client.classify("model", "тема", [{"text":"фраза"}], threading.Event()) == []


def test_cloud_and_oversized_models_are_not_accepted(monkeypatch):
    client = Ollama()
    def request(path,payload=None,*a,**k):
        if path == "/api/tags":
            return {"models":[{"name":"cloud-cloud","size":1},
                               {"name":"remote","size":1},
                               {"name":"large","size":4_000_000_000},
                               {"name":"small","size":900_000_000}]}
        return {"capabilities":["completion"],"model_info":{"layers":8},
                **({"remote_host":"https://ollama.com"} if payload["model"]=="remote" else {})}
    monkeypatch.setattr(client,"request",request)
    values=client.models()
    assert [m["name"] for m in values] == ["small","large"]
    with pytest.raises(ValueError,match="лимит"):
        client.verify_model("large")

