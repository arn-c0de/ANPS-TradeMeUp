"""Custom SQLAlchemy types for PostgreSQL."""
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import TypeDecorator


class GUID(TypeDecorator):
    """PostgreSQL-native UUID type.
    
    Uses PostgreSQL's native UUID type for optimal performance.
    UUIDs are stored natively without string conversion overhead.
    """
    impl = UUID(as_uuid=True)
    cache_ok = True
