-- Star schema for daily Steam game

CREATE TABLE IF NOT EXISTS dim_date (
    date_key     INT PRIMARY KEY,
    full_date    DATE NOT NULL UNIQUE,
    year         SMALLINT NOT NULL,
    quarter      SMALLINT NOT NULL,
    month        SMALLINT NOT NULL,
    day          SMALLINT NOT NULL,
    day_of_week  SMALLINT NOT NULL,
    is_weekend   BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_game (
    game_key   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    appid      INT NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    developer  TEXT,
    publisher  TEXT
);

CREATE TABLE IF NOT EXISTS dim_genre (
    genre_key   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    genre_name  TEXT NOT NULL UNIQUE
);

-- games <-> genres is many-to-many
CREATE TABLE IF NOT EXISTS bridge_game_genre (
    game_key   INT NOT NULL REFERENCES dim_game (game_key),
    genre_key  INT NOT NULL REFERENCES dim_genre (genre_key),
    PRIMARY KEY (game_key, genre_key)
);

CREATE TABLE IF NOT EXISTS fact_game_snapshot (
    date_key             INT NOT NULL REFERENCES dim_date (date_key),
    game_key             INT NOT NULL REFERENCES dim_game (game_key),
    price_usd            NUMERIC(8, 2),
    initial_price_usd    NUMERIC(8, 2),
    discount_pct         SMALLINT,
    positive_reviews     INT,
    negative_reviews     INT,
    owners_min           BIGINT,
    owners_max           BIGINT,
    avg_playtime_min     INT,
    median_playtime_min  INT,
    ccu                  INT,
    PRIMARY KEY (date_key, game_key)
);

CREATE INDEX IF NOT EXISTS idx_fact_game_key ON fact_game_snapshot (game_key);
CREATE INDEX IF NOT EXISTS idx_bridge_genre_key ON bridge_game_genre (genre_key);

-- refreshed after each load
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_genre_stats AS
SELECT
    d.full_date,
    gn.genre_name,
    COUNT(*)                                               AS games,
    ROUND(AVG(f.price_usd), 2)                             AS avg_price_usd,
    ROUND(100.0 * SUM(f.positive_reviews)
          / NULLIF(SUM(f.positive_reviews + f.negative_reviews), 0), 1)
                                                           AS positive_review_pct,
    SUM((f.owners_min + f.owners_max) / 2)                 AS est_total_owners,
    SUM(f.ccu)                                             AS total_ccu
FROM fact_game_snapshot f
JOIN dim_date d            ON d.date_key = f.date_key
JOIN bridge_game_genre b   ON b.game_key = f.game_key
JOIN dim_genre gn          ON gn.genre_key = b.genre_key
GROUP BY d.full_date, gn.genre_name
WITH NO DATA;