"""Unit tests for the PySpark cleaning logic"""

from decimal import Decimal

from pipeline.transform import build_game_genres, clean_games


def raw_game(**overrides) -> dict:
    game = {
        "appid": 570,
        "name": "Dota 2",
        "developer": "Valve",
        "publisher": "Valve",
        "positive": 100,
        "negative": 20,
        "owners": "1,000,000 .. 2,000,000",
        "average_forever": 300,
        "median_forever": 120,
        "price": "1999",
        "initialprice": "2999",
        "discount": "33",
        "ccu": 5000,
        "genre": "Action",
    }
    game.update(overrides)
    return game


def test_prices_are_converted_from_cents_to_dollars(spark):
    df = spark.createDataFrame([raw_game()])
    row = clean_games(df).collect()[0]
    assert row.price_usd == Decimal("19.99")
    assert row.initial_price_usd == Decimal("29.99")
    assert row.discount_pct == 33


def test_owners_range_is_split_into_min_and_max(spark):
    df = spark.createDataFrame([raw_game(owners="20,000 .. 50,000")])
    row = clean_games(df).collect()[0]
    assert (row.owners_min, row.owners_max) == (20000, 50000)


def test_game_in_several_genres_becomes_one_row(spark):
    df = spark.createDataFrame(
        [raw_game(genre="Action"), raw_game(genre="Strategy"), raw_game(appid=730, name="CS2")]
    )
    assert clean_games(df).count() == 2


def test_hidden_and_nameless_games_are_dropped(spark):
    df = spark.createDataFrame(
        [raw_game(), raw_game(appid=999999, name="Hidden"), raw_game(appid=1, name="  ")]
    )
    result = clean_games(df).collect()
    assert [r.appid for r in result] == [570]


def test_empty_developer_becomes_null(spark):
    df = spark.createDataFrame([raw_game(developer="")])
    assert clean_games(df).collect()[0].developer is None


def test_game_genres_keeps_each_pair_once(spark):
    df = spark.createDataFrame(
        [raw_game(genre="Action"), raw_game(genre="Action"), raw_game(genre="Strategy")]
    )
    pairs = {(r.appid, r.genre) for r in build_game_genres(df).collect()}
    assert pairs == {(570, "Action"), (570, "Strategy")}