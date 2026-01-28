"""Add trading_simulations table

Revision ID: add_trading_sims
Revises: 156ce40ea7a5
Create Date: 2026-01-24 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from src.models.types import GUID


# revision identifiers, used by Alembic.
revision: str = 'add_trading_sims'
down_revision: Union[str, None] = '156ce40ea7a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add trading_simulations table for trading simulation outcomes."""
    op.create_table(
        'trading_simulations',
        sa.Column('simulation_id', GUID(), nullable=False),
        sa.Column('prediction_id', GUID(), nullable=False),
        sa.Column('entity_id', sa.String(length=50), nullable=False),
        sa.Column('horizon', sa.String(length=10), nullable=False),
        sa.Column('decision', sa.String(length=10), nullable=False),
        sa.Column('expected_return_pct', sa.Float(), nullable=True),
        sa.Column('actual_return_pct', sa.Float(), nullable=True),
        sa.Column('divergence_pct', sa.Float(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('calibrated_confidence', sa.Float(), nullable=True),
        sa.Column('transaction_cost_bps', sa.Float(), nullable=True),
        sa.Column('cost_breakdown', JSONB(), nullable=True),
        sa.Column('risk_breakdown', JSONB(), nullable=True),
        sa.Column('simulation_metadata', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['prediction_id'], ['predictions.prediction_id'], ),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.entity_id'], ),
        sa.PrimaryKeyConstraint('simulation_id')
    )
    
    # Create indexes
    op.create_index('idx_simulation_prediction', 'trading_simulations', ['prediction_id'], unique=False)
    op.create_index('idx_simulation_entity_time', 'trading_simulations', ['entity_id', 'created_at'], unique=False)
    op.create_index('idx_simulation_decision', 'trading_simulations', ['decision', 'created_at'], unique=False)


def downgrade() -> None:
    """Remove trading_simulations table."""
    op.drop_index('idx_simulation_decision', table_name='trading_simulations')
    op.drop_index('idx_simulation_entity_time', table_name='trading_simulations')
    op.drop_index('idx_simulation_prediction', table_name='trading_simulations')
    op.drop_table('trading_simulations')
