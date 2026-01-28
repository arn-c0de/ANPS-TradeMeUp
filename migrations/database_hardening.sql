-- ==========================================
-- Database Hardening & Security Migration
-- ==========================================
-- Adds constraints, indexes, and security measures
-- for production stability and data integrity
--
-- PostgreSQL-only version (SQLite support removed)
--
-- To apply:
--   psql -d trademeup < database_hardening.sql
-- ==========================================

-- Note: PostgreSQL enforces foreign keys by default


-- 2. ADD CHECK CONSTRAINTS
-- ==========================================
-- Ensure data values are within valid ranges
-- Note: Constraints are primarily enforced in model definitions


-- 3. ADD UNIQUE CONSTRAINTS (Prevent Duplicates)
-- ==========================================

-- Prevent duplicate predictions for same entity/time/horizon
CREATE UNIQUE INDEX IF NOT EXISTS idx_prediction_unique
ON predictions(entity_id, timestamp, horizon);

-- Prevent duplicate prediction outcomes
CREATE UNIQUE INDEX IF NOT EXISTS idx_outcome_unique
ON prediction_outcomes(prediction_id);

-- Prevent duplicate quality assessments
CREATE UNIQUE INDEX IF NOT EXISTS idx_quality_unique
ON data_quality_scores(news_id);

-- Prevent duplicate processed news records
CREATE UNIQUE INDEX IF NOT EXISTS idx_processed_unique
ON processed_news(news_id);


-- 4. ADD PARTIAL INDEXES (Performance + Data Quality)
-- ==========================================
-- These indexes only include rows matching a condition
-- = Smaller index size = Faster queries

-- Index only high-quality news
CREATE INDEX IF NOT EXISTS idx_high_quality_news
ON raw_news(published_at, fetched_at)
WHERE quality_score >= 0.6;

-- Index only high-impact scores (for prediction generation)
CREATE INDEX IF NOT EXISTS idx_high_impact_scores
ON impact_scores(created_at, entity_id, impact_score)
WHERE impact_score >= 0.4;

-- Index only confident predictions
CREATE INDEX IF NOT EXISTS idx_confident_predictions
ON predictions(created_at, entity_id, confidence)
WHERE confidence >= 0.5;

-- Index only correct prediction outcomes (for learning)
CREATE INDEX IF NOT EXISTS idx_correct_outcomes
ON prediction_outcomes(evaluation_timestamp, prediction_id)
WHERE direction_correct = 1;


-- 5. ADD COMPOSITE INDEXES (Frequently Used Together)
-- ==========================================

-- For predictions filtered by horizon + date + confidence
CREATE INDEX IF NOT EXISTS idx_predictions_filter
ON predictions(horizon, created_at DESC, confidence DESC);

-- For entity sentiment analysis over time
CREATE INDEX IF NOT EXISTS idx_entity_news_time
ON news_entity_mappings(entity_id, created_at DESC);

-- For regime detection queries
CREATE INDEX IF NOT EXISTS idx_market_regime_time
ON market_regimes(timestamp DESC);

-- For impact scoring queries
CREATE INDEX IF NOT EXISTS idx_impact_news_entity
ON impact_scores(news_id, entity_id, impact_score DESC);


-- 6. ADD COVERING INDEXES (Include Additional Columns)
-- ==========================================
-- SQLite doesn't support INCLUDE, but we can add columns to index
-- PostgreSQL: Use CREATE INDEX ... INCLUDE (col1, col2)

-- For entity lookups with metadata
CREATE INDEX IF NOT EXISTS idx_entity_lookup
ON entities(entity_id, entity_name, entity_type);


-- 7. DATA VALIDATION (PostgreSQL Only)
-- ==========================================
-- These require PostgreSQL's CHECK constraint syntax
-- Uncomment if using PostgreSQL:

/*
-- Validate quality score range
ALTER TABLE data_quality_scores
ADD CONSTRAINT check_quality_score_range
CHECK (quality_score >= 0 AND quality_score <= 1);

-- Validate confidence range
ALTER TABLE predictions
ADD CONSTRAINT check_confidence_range
CHECK (confidence >= 0 AND confidence <= 1);

-- Validate impact score range
ALTER TABLE impact_scores
ADD CONSTRAINT check_impact_score_range
CHECK (impact_score >= 0 AND impact_score <= 1);

-- Validate surprise score range
ALTER TABLE surprise_scores
ADD CONSTRAINT check_surprise_range
CHECK (surprise_normalized >= 0 AND surprise_normalized <= 1);

-- Ensure timestamps make sense
ALTER TABLE predictions
ADD CONSTRAINT check_prediction_timestamp
CHECK (created_at >= timestamp);

ALTER TABLE raw_news
ADD CONSTRAINT check_news_timestamp
CHECK (fetched_at >= published_at);
*/


-- 8. SET DEFAULT VALUES (Safety Net)
-- ==========================================
-- SQLite doesn't support ALTER COLUMN, do this in models
-- PostgreSQL can use:
-- ALTER TABLE table_name ALTER COLUMN col_name SET DEFAULT value;


-- 9. ADD CASCADING DELETES (Referential Integrity)
-- ==========================================
-- This ensures related records are deleted when parent is deleted
-- NOTE: Can't modify existing foreign keys in SQLite
-- Must be done during table creation or table rebuild

-- Example for PostgreSQL:
/*
ALTER TABLE prediction_outcomes
DROP CONSTRAINT IF EXISTS prediction_outcomes_prediction_id_fkey,
ADD CONSTRAINT prediction_outcomes_prediction_id_fkey
FOREIGN KEY (prediction_id)
REFERENCES predictions(prediction_id)
ON DELETE CASCADE;
*/


-- 10. VERIFY INDEXES WERE CREATED
-- ==========================================

-- PostgreSQL: Check indexes
SELECT tablename, indexname, indexdef 
FROM pg_indexes 
WHERE schemaname = 'public' 
    AND indexname LIKE 'idx_%' 
ORDER BY tablename, indexname;


-- 11. ANALYZE TABLES (Update Statistics)
-- ==========================================
-- Helps query planner make better decisions

ANALYZE;


-- 12. VACUUM DATABASE (Reclaim Space)
-- ==========================================
-- PostgreSQL: Reclaim space and update statistics
-- Run this periodically for maintenance

-- VACUUM;  -- Uncomment to run during maintenance


-- ==========================================
-- VERIFICATION QUERIES
-- ==========================================

-- Check for duplicate predictions (should return 0)
SELECT
    entity_id,
    timestamp,
    horizon,
    COUNT(*) as duplicates
FROM
    predictions
GROUP BY
    entity_id, timestamp, horizon
HAVING
    COUNT(*) > 1;

-- Check for orphaned prediction outcomes (should return 0)
SELECT
    COUNT(*)
FROM
    prediction_outcomes po
LEFT JOIN
    predictions p ON po.prediction_id = p.prediction_id
WHERE
    p.prediction_id IS NULL;

-- Check for orphaned processed news (should return 0)
SELECT
    COUNT(*)
FROM
    processed_news pn
LEFT JOIN
    raw_news rn ON pn.news_id = rn.news_id
WHERE
    rn.news_id IS NULL;

-- Check index usage (SQLite)
-- Run actual queries and check:
-- EXPLAIN QUERY PLAN SELECT ...;


-- ==========================================
-- MAINTENANCE SCHEDULE
-- ==========================================

/*
Weekly:
- ANALYZE; (update statistics)

Monthly:
- VACUUM; (reclaim space, SQLite only)
- Check for orphaned records
- Review slow query log

Quarterly:
- Review and optimize indexes based on actual usage
- Check database size and growth
- Audit data integrity
*/


-- ==========================================
-- ROLLBACK PLAN (If Issues Occur)
-- ==========================================

/*
If migration causes problems:

1. Drop new indexes:
   DROP INDEX IF EXISTS idx_prediction_unique;
   DROP INDEX IF EXISTS idx_outcome_unique;
   -- ... etc

2. Restore from backup:
   -- Always have a backup before running migrations!

3. Re-run previous working migration
*/


-- ==========================================
-- COMPLETION
-- ==========================================

SELECT 'Database hardening migration completed successfully!' AS status;
