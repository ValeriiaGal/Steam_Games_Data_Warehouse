# Steam Games Data Warehouse

ELT pipeline that collects data on ~2,000 Steam games from the SteamSpy API, cleans it with PySpark and loads it into a PostgreSQL star schema.

**Stack:** Python, PySpark, PostgreSQL, Parquet, Docker Compose, pytest

## How it works
1. `extract.py` – downloads games by genre and saves raw JSON (partitioned by date)
2. `transform.py` – cleans the data with PySpark and writes Parquet
3. `load.py` – loads it into a star schema in one transaction
4. `sql/analytics.sql` – example queries (window functions, CTEs, materialized view)

## Run
```bash
docker compose up --build -d
```
Database: `localhost:5433`, db `steam_dwh`, user/password `steam`/`steam`

Tests: `docker compose run --rm pipeline pytest`