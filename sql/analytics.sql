-- 1. Top 3 games per genre by positive reviews
WITH latest AS (
    SELECT MAX(date_key) AS date_key FROM fact_game_snapshot
),
ranked AS (
    SELECT
        gn.genre_name,
        g.name,
        f.positive_reviews,
        ROW_NUMBER() OVER (PARTITION BY gn.genre_name
                           ORDER BY f.positive_reviews DESC) AS rank_in_genre
    FROM fact_game_snapshot f
    JOIN latest l             ON l.date_key = f.date_key
    JOIN dim_game g           ON g.game_key = f.game_key
    JOIN bridge_game_genre b  ON b.game_key = f.game_key
    JOIN dim_genre gn         ON gn.genre_key = b.genre_key
)
SELECT genre_name, rank_in_genre, name, positive_reviews
FROM ranked
WHERE rank_in_genre <= 3
ORDER BY genre_name, rank_in_genre;


-- 2. Genres ranked by review score
SELECT
    genre_name,
    games,
    avg_price_usd,
    positive_review_pct,
    RANK() OVER (ORDER BY positive_review_pct DESC) AS rank_by_reviews
FROM mv_genre_stats
WHERE full_date = (SELECT MAX(full_date) FROM mv_genre_stats)
ORDER BY rank_by_reviews;


-- 3. Free vs paid games
SELECT
    CASE WHEN f.price_usd = 0 THEN 'Free' ELSE 'Paid' END        AS price_type,
    COUNT(*)                                                     AS games,
    ROUND(100.0 * SUM(f.positive_reviews)
          / NULLIF(SUM(f.positive_reviews + f.negative_reviews), 0), 1)
                                                                 AS positive_review_pct,
    ROUND(AVG(f.median_playtime_min) / 60.0, 1)                  AS avg_median_playtime_h,
    COUNT(*) FILTER (WHERE f.owners_min >= 1000000)              AS games_with_1m_plus_owners
FROM fact_game_snapshot f
WHERE f.date_key = (SELECT MAX(date_key) FROM fact_game_snapshot)
GROUP BY price_type;


-- 4. Review score by price bucket
WITH priced AS (
    SELECT
        f.*,
        CASE
            WHEN f.price_usd = 0     THEN '0. Free'
            WHEN f.price_usd < 5     THEN '1. Under $5'
            WHEN f.price_usd < 15    THEN '2. $5 - $15'
            WHEN f.price_usd < 30    THEN '3. $15 - $30'
            ELSE                          '4. $30+'
        END AS price_bucket
    FROM fact_game_snapshot f
    WHERE f.date_key = (SELECT MAX(date_key) FROM fact_game_snapshot)
)
SELECT
    price_bucket,
    COUNT(*) AS games,
    ROUND(100.0 * SUM(positive_reviews)
          / NULLIF(SUM(positive_reviews + negative_reviews), 0), 1) AS positive_review_pct
FROM priced
GROUP BY price_bucket
ORDER BY price_bucket;


-- 5. Developers with 5+ games and their share of all reviews
WITH dev AS (
    SELECT
        g.developer,
        COUNT(*)                                       AS games,
        SUM(f.positive_reviews + f.negative_reviews)  AS total_reviews
    FROM fact_game_snapshot f
    JOIN dim_game g ON g.game_key = f.game_key
    WHERE f.date_key = (SELECT MAX(date_key) FROM fact_game_snapshot)
      AND g.developer IS NOT NULL
    GROUP BY g.developer
    HAVING COUNT(*) >= 5
)
SELECT
    developer,
    games,
    total_reviews,
    ROUND(100.0 * total_reviews / SUM(total_reviews) OVER (), 2) AS share_of_reviews_pct
FROM dev
ORDER BY total_reviews DESC
LIMIT 15;


-- 6. Day-over-day change in players online
WITH top_games AS (
    SELECT game_key
    FROM fact_game_snapshot
    WHERE date_key = (SELECT MAX(date_key) FROM fact_game_snapshot)
    ORDER BY ccu DESC
    LIMIT 5
)
SELECT
    g.name,
    d.full_date,
    f.ccu,
    f.ccu - LAG(f.ccu) OVER (PARTITION BY f.game_key ORDER BY d.full_date) AS ccu_change
FROM fact_game_snapshot f
JOIN top_games t ON t.game_key = f.game_key
JOIN dim_game g  ON g.game_key = f.game_key
JOIN dim_date d  ON d.date_key = f.date_key
ORDER BY g.name, d.full_date;


-- 7. Query plan with and without the index
EXPLAIN ANALYZE
SELECT * FROM fact_game_snapshot
WHERE game_key = (SELECT game_key FROM dim_game WHERE appid = 570);

DROP INDEX IF EXISTS idx_fact_game_key;

EXPLAIN ANALYZE
SELECT * FROM fact_game_snapshot
WHERE game_key = (SELECT game_key FROM dim_game WHERE appid = 570);

CREATE INDEX idx_fact_game_key ON fact_game_snapshot (game_key);