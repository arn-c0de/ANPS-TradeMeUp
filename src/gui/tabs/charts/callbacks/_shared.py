"""Chart tab callbacks: shared helpers."""

import json
import logging
from typing import Any

from dash import callback_context
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.database import engine as _engine

# The shared provider singleton, not a per-module instance.

logger = logging.getLogger(__name__)


def _get_triggered_relayout(relayout_data_list: list, graph_ids: list) -> tuple[str | None, dict | None]:
    """Resolve which chart graph triggered a relayoutData callback.

    Returns (tab_id, relayout_data) or (None, None) if the trigger cannot be
    resolved (no trigger, unparseable ID, or graph not found).
    """
    if not callback_context.triggered:
        return None, None

    trigger = callback_context.triggered[0]["prop_id"]
    if ".relayoutData" not in trigger:
        return None, None

    try:
        trigger_id = json.loads(trigger.split(".")[0])
        tab_id = trigger_id.get("index")
    except Exception as e:
        logger.debug(f"Could not parse relayout trigger ID: {e}")
        return None, None

    for idx, graph_id in enumerate(graph_ids):
        if graph_id.get("index") == tab_id:
            if idx < len(relayout_data_list):
                return tab_id, relayout_data_list[idx]
            return None, None

    return None, None


def _isoformat_or_str(value: Any) -> str:
    """Serialize a timestamp-like value (pandas Timestamp, datetime, str) to a string."""
    try:
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        if hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%dT%H:%M:%S')
        return str(value)
    except Exception:
        return str(value)


def _search_entity_symbols(search_value: str) -> list[dict[str, str]]:
    """Search the Entity table by ticker or company name; return dropdown options."""
    from src.models.entities import Entity

    try:
        with Session(_engine) as db:
            search_term = f"%{search_value.upper()}%"
            entities = db.scalars(
                select(Entity).where(
                    (Entity.entity_id.ilike(search_term)) |
                    (Entity.entity_name.ilike(search_term))
                ).limit(20)
            ).all()

            # Format as dropdown options: "AAPL - Apple Inc."
            return [
                {"label": f"{entity.entity_id} - {entity.entity_name}", "value": entity.entity_id}
                for entity in entities
            ]
    except Exception as e:
        logger.error(f"Error searching symbols: {e}")
        return []
