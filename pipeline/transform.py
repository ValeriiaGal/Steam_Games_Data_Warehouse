"""Clean the raw JSON with PySpark and write partitioned Parquet."""

import logging
from datetime import date
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

HIDDEN_APPID = 999999

log = logging.getLogger(__name__)


def create_spark(app_name: str = "steam-games-dwh") -> SparkSession:
    spark = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .config("spark.ui.showConsoleProgress", "false")
        # overwrite only the partitions being written
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def parse_owners(owners_col: F.Column) -> tuple[F.Column, F.Column]:
    no_commas = F.regexp_replace(owners_col, ",", "")
    parts = F.split(no_commas, r"\s*\.\.\s*")
    return parts.getItem(0).cast("long"), parts.getItem(1).cast("long")


def clean_games(raw: DataFrame) -> DataFrame:
    owners_min, owners_max = parse_owners(F.col("owners"))

    typed = raw.select(
        F.col("appid").cast("int").alias("appid"),
        F.trim(F.col("name")).alias("name"),
        F.trim(F.col("developer")).alias("developer"),
        F.trim(F.col("publisher")).alias("publisher"),
        (F.col("price").cast("int") / 100).cast("decimal(8,2)").alias("price_usd"),
        (F.col("initialprice").cast("int") / 100)
        .cast("decimal(8,2)")
        .alias("initial_price_usd"),
        F.col("discount").cast("int").alias("discount_pct"),
        F.col("positive").cast("int").alias("positive_reviews"),
        F.col("negative").cast("int").alias("negative_reviews"),
        owners_min.alias("owners_min"),
        owners_max.alias("owners_max"),
        F.col("average_forever").cast("int").alias("avg_playtime_min"),
        F.col("median_forever").cast("int").alias("median_playtime_min"),
        F.col("ccu").cast("int").alias("ccu"),
    )

    for column in ("developer", "publisher"):
        typed = typed.withColumn(
            column, F.when(F.col(column) == "", None).otherwise(F.col(column))
        )

    return (
        typed.filter(F.col("appid").isNotNull())
        .filter(F.col("appid") != HIDDEN_APPID)
        .filter(F.col("name").isNotNull() & (F.col("name") != ""))
        .dropDuplicates(["appid"])  # a game appears once per genre in raw data
    )


def build_game_genres(raw: DataFrame) -> DataFrame:
    return (
        raw.select(F.col("appid").cast("int").alias("appid"), F.col("genre"))
        .filter(F.col("appid").isNotNull() & (F.col("appid") != HIDDEN_APPID))
        .dropDuplicates()
    )


def transform(spark: SparkSession, raw_dir: Path, clean_dir: Path, load_date: date) -> None:
    day = load_date.isoformat()
    raw = spark.read.json(str(raw_dir / f"load_date={day}"))

    games = clean_games(raw).withColumn("load_date", F.lit(day))
    game_genres = build_game_genres(raw).withColumn("load_date", F.lit(day))

    games.write.mode("overwrite").partitionBy("load_date").parquet(str(clean_dir / "games"))
    game_genres.write.mode("overwrite").partitionBy("load_date").parquet(
        str(clean_dir / "game_genres")
    )

    log.info(
        "Transform done: %d raw rows -> %d games, %d game-genre pairs",
        raw.count(),
        games.count(),
        game_genres.count(),
    )