-- Performance optimization indexes for GUI
-- Run this migration to apply new indexes for faster database queries

-- Index for predictions filtered by horizon and created date
CREATE INDEX IF NOT EXISTS idx_predictions_horizon ON predictions(horizon, created_at);

-- Index for raw news filtered by fetched date (used in statistics tab)
CREATE INDEX IF NOT EXISTS idx_raw_news_fetched ON raw_news(fetched_at);

-- Verify indexes were created
SELECT
    tablename,
    indexname
FROM
    pg_indexes
WHERE
    indexname IN ('idx_predictions_horizon', 'idx_raw_news_fetched')
ORDER BY
    tablename, indexname;
