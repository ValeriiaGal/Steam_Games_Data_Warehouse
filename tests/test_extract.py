"""Unit tests for the extract step"""

import json
from datetime import date
from unittest.mock import MagicMock

from pipeline import extract as extract_module
from pipeline.extract import extract, iter_game_records, slugify

FAKE_PAYLOAD = {
    "570": {"appid": 570, "name": "Dota 2", "price": "0"},
    "730": {"appid": 730, "name": "Counter-Strike 2", "price": "0"},
}


def test_iter_game_records_adds_genre_and_timestamp():
    records = list(iter_game_records("Action", FAKE_PAYLOAD, "2026-11-18T10:00:00+00:00"))
    assert len(records) == 2
    assert all(r["genre"] == "Action" for r in records)
    assert records[0]["extracted_at"] == "2026-11-18T10:00:00+00:00"


def test_slugify_makes_safe_file_names():
    assert slugify("Free To Play") == "free_to_play"


def test_extract_writes_one_jsonl_file_per_genre(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_module, "fetch_genre", MagicMock(return_value=FAKE_PAYLOAD))
    monkeypatch.setattr(extract_module, "REQUEST_PAUSE_SECONDS", 0)

    folder = extract(["Action", "Free To Play"], tmp_path, date(2026, 11, 18))

    assert folder == tmp_path / "load_date=2026-11-18"
    assert sorted(p.name for p in folder.iterdir()) == [
        "genre_action.jsonl",
        "genre_free_to_play.jsonl",
    ]
    lines = (folder / "genre_action.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["appid"] for line in lines] == [570, 730]