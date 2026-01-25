"""Enhanced simulation risk analysis with new cost and position columns

Revision ID: enhanced_sim_risk
Revises: add_trading_sims
Create Date: 2026-01-25 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'enhanced_sim_risk'
down_revision: Union[str, None] = 'add_trading_sims'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new columns for enhanced risk analysis."""
    # Add new cost metric columns
    op.add_column('trading_simulations', sa.Column('overnight_cost_bps', sa.Float(), nullable=True))
    op.add_column('trading_simulations', sa.Column('borrow_cost_bps', sa.Float(), nullable=True))

    # Add new position metric columns
    op.add_column('trading_simulations', sa.Column('position_size_pct', sa.Float(), nullable=True))
    op.add_column('trading_simulations', sa.Column('position_value_usd', sa.Float(), nullable=True))

    # Add new index for risk-based queries
    op.create_index('idx_simulation_risk_score', 'trading_simulations', ['risk_score'], unique=False)


def downgrade() -> None:
    """Remove enhanced risk analysis columns."""
    # Drop index
    op.drop_index('idx_simulation_risk_score', table_name='trading_simulations')

    # Drop position metric columns
    op.drop_column('trading_simulations', 'position_value_usd')
    op.drop_column('trading_simulations', 'position_size_pct')

    # Drop cost metric columns
    op.drop_column('trading_simulations', 'borrow_cost_bps')
    op.drop_column('trading_simulations', 'overnight_cost_bps')
