"""PostgreSQL-specific optimizations (GIN indexes, pgvector, extensions)

Revision ID: postgresql_opts
Revises: add_stop_loss_tp
Create Date: 2026-01-28

This migration adds PostgreSQL-specific performance optimizations:
- Enables pgvector extension for vector similarity search
- Adds GIN indexes on JSONB columns for fast JSON queries
- Adds IVFFlat index on embedding vectors for similarity search
- Adds partial indexes for common query patterns
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'postgresql_opts'
down_revision = 'add_stop_loss_tp'
branch_labels = None
depends_on = None


def upgrade():
    """Apply PostgreSQL-specific optimizations."""
    
    # Note: Extensions (uuid-ossp, vector) should be created manually in psql before running migrations
    # Tables are now created with JSONB directly (no conversion needed)
    # This migration adds performance indexes only
    
    # 1. GIN indexes for JSONB columns (fast JSON queries and containment searches)
    
    # Predictions table JSONB indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_key_drivers_gin 
        ON predictions USING gin (key_drivers)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_direction_probs_gin 
        ON predictions USING gin (direction_probabilities)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_model_contributions_gin 
        ON predictions USING gin (model_contributions)
    """)
    
    # Processed news JSONB indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_processed_news_sentiment_gin 
        ON processed_news USING gin (sentiment)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_processed_news_key_facts_gin 
        ON processed_news USING gin (key_facts)
    """)
    
    # Trading simulations JSONB indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_trading_sims_metadata_gin 
        ON trading_simulations USING gin (simulation_metadata)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_trading_sims_risk_breakdown_gin 
        ON trading_simulations USING gin (risk_breakdown)
    """)
    
    # Analysis tables JSONB indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_impact_scores_breakdown_gin 
        ON impact_scores USING gin (impact_breakdown)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_market_regimes_regime_gin 
        ON market_regimes USING gin (regime)
    """)
    
    # 4. Note: IVFFlat index for vectors skipped (requires pgvector extension)
    # To add vector index later when pgvector is installed:
    # CREATE INDEX idx_embeddings_ivfflat ON processed_news 
    # USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    
    # 5. Additional standard indexes (no partial indexes to avoid transaction issues)
    
    # Predictions recent index
    op.create_index('idx_predictions_recent', 'predictions', ['created_at', 'confidence'], unique=False)
    
    # Active simulations index
    op.create_index('idx_simulations_active', 'trading_simulations', ['decision', 'created_at'], unique=False)


def downgrade():
    """Remove PostgreSQL-specific optimizations."""
    
    # Drop GIN indexes
    op.drop_index('idx_predictions_key_drivers_gin', table_name='predictions')
    op.drop_index('idx_predictions_direction_probs_gin', table_name='predictions')
    op.drop_index('idx_predictions_model_contributions_gin', table_name='predictions')
    op.drop_index('idx_processed_news_sentiment_gin', table_name='processed_news')
    op.drop_index('idx_processed_news_key_facts_gin', table_name='processed_news')
    op.drop_index('idx_trading_sims_metadata_gin', table_name='trading_simulations')
    op.drop_index('idx_trading_sims_risk_breakdown_gin', table_name='trading_simulations')
    op.drop_index('idx_impact_scores_breakdown_gin', table_name='impact_scores')
    op.drop_index('idx_market_regimes_regime_gin', table_name='market_regimes')
    
    # Drop standard indexes
    op.drop_index('idx_predictions_recent', table_name='predictions')
    op.drop_index('idx_simulations_active', table_name='trading_simulations')
