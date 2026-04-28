"""Add system_logs table for centralised log storage

Revision ID: add_system_logs
Revises: postgresql_opts
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'add_system_logs'
down_revision = 'postgresql_opts'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'system_logs',
        sa.Column('log_id',    sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('level',     sa.String(20),  nullable=False, server_default='INFO'),
        sa.Column('source',    sa.String(50),  nullable=False, server_default='system'),
        sa.Column('component', sa.String(100), nullable=True),
        sa.Column('message',   sa.Text(),      nullable=False),
        sa.Column('details',   JSONB,          nullable=True),
    )
    op.create_index('idx_syslog_ts',        'system_logs', ['timestamp'])
    op.create_index('idx_syslog_source_ts', 'system_logs', ['source', 'timestamp'])
    op.create_index('idx_syslog_level_ts',  'system_logs', ['level',  'timestamp'])


def downgrade():
    op.drop_index('idx_syslog_level_ts',  table_name='system_logs')
    op.drop_index('idx_syslog_source_ts', table_name='system_logs')
    op.drop_index('idx_syslog_ts',        table_name='system_logs')
    op.drop_table('system_logs')
