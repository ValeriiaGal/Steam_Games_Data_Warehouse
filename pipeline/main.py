"""Run the pipeline: extract -> transform -> load.
"""

import argparse
import logging
from datetime import date

from pipeline.config import Settings

STEPS = ["extract", "transform", "load"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Steam games ELT pipeline")
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=date.today(),
        help="Load date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--steps", nargs="+", choices=STEPS, default=STEPS, help="Which steps to run"
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    args = parse_args()
    settings = Settings()
    log = logging.getLogger("pipeline")
    log.info("Running steps %s for %s", args.steps, args.date)

    if "extract" in args.steps:
        from pipeline.extract import extract

        extract(settings.genres, settings.raw_dir, args.date)

    if "transform" in args.steps:
        from pipeline.transform import create_spark, transform

        spark = create_spark()
        try:
            transform(spark, settings.raw_dir, settings.clean_dir, args.date)
        finally:
            spark.stop()

    if "load" in args.steps:
        from pipeline.load import load

        load(settings.pg_dsn(), settings.clean_dir, args.date)

    log.info("Pipeline finished")


if __name__ == "__main__":
    main()