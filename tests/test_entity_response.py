from src.api.routers.entities import EntityResponse
from src.models.entities import Entity


def test_entity_response_reads_metadata_column_not_sqlalchemy_metadata():
    # Entity.metadata is SQLAlchemy's MetaData; the JSONB column is metadata_.
    entity = Entity(
        entity_id="AAPL", entity_type="company", entity_name="Apple", metadata_={"sector": "Tech"}
    )

    response = EntityResponse.model_validate(entity)

    assert response.metadata == {"sector": "Tech"}
    assert response.model_dump()["metadata"] == {"sector": "Tech"}


def test_entity_response_without_metadata():
    entity = Entity(entity_id="SPY", entity_type="index", entity_name="S&P 500")

    assert EntityResponse.model_validate(entity).metadata is None
