"""Download games from the SteamSpy API and save them as raw JSON Lines."""

import json
import logging
import time
from collections.abc import Iterator
from datetime import date, datetime, timezone
from pathlib import Path

import requests

API_URL = "https://steamspy.com/api.php"
REQUEST_PAUSE_SECONDS = 1.0
MAX_RETRIES = 3

log = logging.getLogger(__name__)


def fetch_genre(genre: str, session: requests.Session | None = None) -> dict:
    http = session or requests.Session()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = http.get(
                API_URL, params={"request": "genre", "genre": genre}, timeout=60
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            log.warning("Genre %s, attempt %d failed: %s", genre, attempt, error)
            if attempt == MAX_RETRIES:
                raise
            time.sleep(5 * attempt)
    return {}


def iter_game_records(genre: str, payload: dict, extracted_at: str) -> Iterator[dict]:
    for game in payload.values():
        yield {**game, "genre": genre, "extracted_at": extracted_at}


def slugify(text: str) -> str:
    return text.strip().lower().replace(" ", "_")


def write_jsonl(records: Iterator[dict], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def extract(genres: list[str], raw_dir: Path, load_date: date) -> Path:
    partition_dir = raw_dir / f"load_date={load_date.isoformat()}"
    extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    session = requests.Session()

    total = 0
    for genre in genres:
        payload = fetch_genre(genre, session)
        records = iter_game_records(genre, payload, extracted_at)
        count = write_jsonl(records, partition_dir / f"genre_{slugify(genre)}.jsonl")
        log.info("Extracted %4d games for genre %s", count, genre)
        total += count
        time.sleep(REQUEST_PAUSE_SECONDS)

    log.info("Extract done: %d records written to %s", total, partition_dir)
    return partition_dir