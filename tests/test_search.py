from player.search import text_hits, highlighted


def test_repeated_occurrences_have_separate_audio_positions():
    rows = [{"start": 0, "end": 6, "text": "Срок, срок и СРОК.", "words": [
        {"text": "Срок,", "start": .2, "end": 1},
        {"text": "срок", "start": 2, "end": 3},
        {"text": "и", "start": 3.4, "end": 3.5},
        {"text": "СРОК.", "start": 4, "end": 5}]}]
    hits = text_hits(rows, " СРОК ")
    assert [(h["row"], h["start"]) for h in hits] == [(0, .2), (0, 2), (0, 4)]
    assert [rows[0]["text"][h["offset"]:h["limit"]] for h in hits] == ["Срок", "срок", "СРОК"]


def test_unicode_casefold_and_html_are_not_corrupted():
    row = {"start": 3, "end": 5, "text": 'Straße <план> & "СРОК"'}
    hits = text_hits([row], "STRASSE")
    assert len(hits) == 1
    html = highlighted(row["text"], hits, hits[0])
    assert '>Straße</span>' in html and '&lt;план&gt;' in html and '&amp;' in html
    assert text_hits([row], "несуществующее") == []


def test_phrase_query_uses_intersecting_word_interval():
    row = {"start": 0, "end": 9, "text": "Обсудим сроки запуска проекта.", "words": [
        {"text": "Обсудим", "start": 0, "end": 1},
        {"text": "сроки", "start": 2, "end": 3},
        {"text": "запуска", "start": 4, "end": 5},
        {"text": "проекта.", "start": 6, "end": 8}]}
    hit = text_hits([row], "сроки запуска")[0]
    assert (hit["start"], hit["end"]) == (2, 5)
