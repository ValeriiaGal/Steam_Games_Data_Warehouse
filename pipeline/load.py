"""Load the clean Parquet data into the PostgreSQL star schema."""

import logging
from datetime import date
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

log = logging.getLogger(__name__)


def date_key(day: date) -> int:
    return day.year * 10000 + day.month * 100 + day.day


def read_partition(clean_dir: Path, table: str, load_date: date) -> pd.DataFrame:
    path = clean_dir / table / f"load_date={load_date.isoformat()}"
    return pd.read_parquet(path)


def to_rows(df: pd.DataFrame, columns: list[str]) -> list[tuple]:
    subset = df[columns].astype(object).where(df[columns].notna(), None)
    return [tuple(row) for row in subset.itertuples(index=False, name=None)]


def upsert_dim_date(cur, day: date) -> int:
    key = date_key(day)
    cur.execute(
        """
        INSERT INTO dim_date (date_key, full_date, year, quarter, month, day, day_of_week, is_weekend)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (date_key) DO NOTHING
        """,
        (
            key,
            day,
            day.year,
            (day.month - 1) // 3 + 1,
            day.month,
            day.day,
            day.isoweekday(),
            day.isoweekday() >= 6,
        ),
    )
    return key


def upsert_dim_game(cur, games: pd.DataFrame) -> None:
    execute_values(
        cur,
        """
        INSERT INTO dim_game (appid, name, developer, publisher) VALUES %s
        ON CONFLICT (appid) DO UPDATE
           SET name = EXCLUDED.name,
               developer = EXCLUDED.developer,
               publisher = EXCLUDED.publisher
        """,
        to_rows(games, ["appid", "name", "developer", "publisher"]),
    )


def upsert_dim_genre(cur, genres: list[str]) -> None:
    execute_values(
        cur,
        "INSERT INTO dim_genre (genre_name) VALUES %s ON CONFLICT (genre_name) DO NOTHING",
        [(g,) for g in genres],
    )


def insert_bridge(cur, game_genres: pd.DataFrame) -> None:
    cur.execute("CREATE TEMP TABLE stg_game_genre (appid INT, genre TEXT) ON COMMIT DROP")
    execute_values(
        cur,
        "INSERT INTO stg_game_genre (appid, genre) VALUES %s",
        to_rows(game_genres, ["appid", "genre"]),
    )
    cur.execute(
        """
        INSERT INTO bridge_game_genre (game_key, genre_key)
        SELECT g.game_key, gn.genre_key
        FROM stg_game_genre s
        JOIN dim_game  g  ON g.appid = s.appid
        JOIN dim_genre gn ON gn.genre_name = s.genre
        ON CONFLICT DO NOTHING
        """
    )


FACT_COLUMNS = [
    "appid",
    "price_usd",
    "initial_price_usd",
    "discount_pct",
    "positive_reviews",
    "negative_reviews",
    "owners_min",
    "owners_max",
    "avg_playtime_min",
    "median_playtime_min",
    "ccu",
]


def replace_facts(cur, games: pd.DataFrame, key: int) -> None:
    cur.execute(
        """
        CREATE TEMP TABLE stg_fact (
            appid INT, price_usd NUMERIC(8,2), initial_price_usd NUMERIC(8,2),
            discount_pct INT, positive_reviews INT, negative_reviews INT,
            owners_min BIGINT, owners_max BIGINT, avg_playtime_min INT,
            median_playtime_min INT, ccu INT
        ) ON COMMIT DROP
        """
    )
    execute_values(
        cur,
        f"INSERT INTO stg_fact ({', '.join(FACT_COLUMNS)}) VALUES %s",
        to_rows(games, FACT_COLUMNS),
    )
    cur.execute("DELETE FROM fact_game_snapshot WHERE date_key = %s", (key,))
    cur.execute(
        """
        INSERT INTO fact_game_snapshot (
            date_key, game_key, price_usd, initial_price_usd, discount_pct,
            positive_reviews, negative_reviews, owners_min, owners_max,
            avg_playtime_min, median_playtime_min, ccu)
        SELECT %s, g.game_key, s.price_usd, s.initial_price_usd, s.discount_pct,
               s.positive_reviews, s.negative_reviews, s.owners_min, s.owners_max,
               s.avg_playtime_min, s.median_playtime_min, s.ccu
        FROM stg_fact s
        JOIN dim_game g ON g.appid = s.appid
        """,
        (key,),
    )


def load(dsn: str, clean_dir: Path, load_date: date) -> None:
    games = read_partition(clean_dir, "games", load_date)
    game_genres = read_partition(clean_dir, "game_genres", load_date)

    conn = psycopg2.connect(dsn)
    try:
        with conn:  # one transaction: commit on success, rollback on error
            with conn.cursor() as cur:
                key = upsert_dim_date(cur, load_date)
                upsert_dim_game(cur, games)
                upsert_dim_genre(cur, sorted(game_genres["genre"].unique()))
                insert_bridge(cur, game_genres)
                replace_facts(cur, games, key)
                cur.execute("REFRESH MATERIALIZED VIEW mv_genre_stats")
                cur.execute(
                    "SELECT count(*) FROM fact_game_snapshot WHERE date_key = %s", (key,)
                )
                fact_count = cur.fetchone()[0]
    finally:
        conn.close()

    log.info("Load done: %d fact rows for %s", fact_count, load_date.isoformat())