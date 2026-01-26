"""Add stop loss and take profit fields to trading_simulations

Revision ID: add_stop_loss_tp
Revises: 
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_stop_loss_tp'
down_revision = None  # Update this to point to the previous migration
branch_labels = None
depends_on = None


def upgrade():
    """Add stop loss and take profit columns to trading_simulations table."""
    # Add stop loss fields
    op.add_column('trading_simulations', 
        sa.Column('stop_loss_price', sa.Float(), nullable=True))
    op.add_column('trading_simulations', 
        sa.Column('stop_loss_pct', sa.Float(), nullable=True))
    op.add_column('trading_simulations', 
        sa.Column('stop_loss_type', sa.String(length=20), nullable=True))
    op.add_column('trading_simulations', 
        sa.Column('trailing_stop_price', sa.Float(), nullable=True))
    
    # Add take profit fields
    op.add_column('trading_simulations', 
        sa.Column('take_profit_price', sa.Float(), nullable=True))
    op.add_column('trading_simulations', 
        sa.Column('take_profit_pct', sa.Float(), nullable=True))
    op.add_column('trading_simulations', 
        sa.Column('risk_reward_ratio', sa.Float(), nullable=True))
    
    # Add exit strategy metadata
    op.add_column('trading_simulations', 
        sa.Column('exit_strategy', sa.JSON(), nullable=True))
    
    # Create index on stop_loss_type for filtering
    op.create_index(
        'idx_simulation_stop_loss_type', 
        'trading_simulations', 
        ['stop_loss_type'], 
        unique=False
    )


def downgrade():
    """Remove stop loss and take profit columns from trading_simulations table."""
    # Drop index
    op.drop_index('idx_simulation_stop_loss_type', table_name='trading_simulations')
    
    # Drop columns
    op.drop_column('trading_simulations', 'exit_strategy')
    op.drop_column('trading_simulations', 'risk_reward_ratio')
    op.drop_column('trading_simulations', 'take_profit_pct')
    op.drop_column('trading_simulations', 'take_profit_price')
    op.drop_column('trading_simulations', 'trailing_stop_price')
    op.drop_column('trading_simulations', 'stop_loss_type')
    op.drop_column('trading_simulations', 'stop_loss_pct')
    op.drop_column('trading_simulations', 'stop_loss_price')
