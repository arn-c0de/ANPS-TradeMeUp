"""
Chart overlay store helpers and DB persistence.
"""

import logging
import uuid

from src.models.database import engine

logger = logging.getLogger(__name__)


def normalize_overlay_store(overlays_data):
    """Ensure overlay store has the expected shape."""
    if not isinstance(overlays_data, dict):
        return {"tabs": {}}
    tabs = overlays_data.get("tabs")
    if not isinstance(tabs, dict):
        tabs = {}
    return {"tabs": tabs}


def ensure_overlay_tab(overlays_data, tab_id):
    """Ensure an overlay entry exists for a given tab id."""
    tabs = overlays_data.setdefault("tabs", {})
    tab_entry = tabs.get(tab_id)
    if not isinstance(tab_entry, dict):
        tab_entry = {}
    tab_entry.setdefault("brackets", [])
    tab_entry.setdefault("breaks", [])
    tabs[tab_id] = tab_entry
    return tab_entry


def flatten_overlay_items(tab_overlays: dict):
    """Return list of (group, item) in stable order for shapes."""
    items = []
    for group in ("brackets", "breaks"):
        for item in (tab_overlays or {}).get(group, []) or []:
            items.append((group, item))
    return items


def load_overlays_from_db():
    """Load all chart overlays from database."""
    from sqlalchemy.orm import Session

    from src.models.chart_overlays import ChartOverlay

    try:
        with Session(engine) as db:
            overlays_db = db.query(ChartOverlay).all()
            logger.info("[DB Load] Found %d overlays in database", len(overlays_db))

            overlays_dict = {"tabs": {}}

            for overlay in overlays_db:
                key = f"{overlay.symbol}_{overlay.timeframe}"
                if key not in overlays_dict["tabs"]:
                    overlays_dict["tabs"][key] = {"brackets": [], "breaks": []}

                overlays_dict["tabs"][key][overlay.group].append(overlay.to_dict())
                logger.info(
                    "[DB Load]   %s %s %s: $%s (%s)",
                    overlay.symbol,
                    overlay.timeframe,
                    overlay.group,
                    overlay.price,
                    overlay.name,
                )

            logger.info("[DB Load] Loaded %d overlay groups", len(overlays_dict["tabs"]))
            return overlays_dict
    except Exception as e:
        logger.error("[DB Load] Error loading overlays from DB: %s", e, exc_info=True)
        return {"tabs": {}}


def save_overlays_to_db(overlays_data, tabs_data):
    """Save chart overlays to database."""
    from sqlalchemy.orm import Session

    from src.models.chart_overlays import ChartOverlay

    try:
        tabs = tabs_data.get("tabs", []) if isinstance(tabs_data, dict) else []
        tab_map = {
            tab["id"]: (tab["symbol"], tab["timeframe"])
            for tab in tabs
            if "id" in tab
        }

        logger.info("[DB Save] Tab map: %s", tab_map)
        logger.info(
            "[DB Save] Overlays tabs: %s",
            list(overlays_data.get("tabs", {}).keys()),
        )

        with Session(engine) as db:
            deleted_count = db.query(ChartOverlay).delete()
            logger.info("[DB Save] Deleted %d existing overlays", deleted_count)

            overlays = overlays_data.get("tabs", {})
            saved_count = 0
            for tab_id, tab_data in overlays.items():
                if tab_id in tab_map:
                    symbol, timeframe = tab_map[tab_id]
                elif "_" in tab_id:
                    parts = tab_id.split("_", 1)
                    if len(parts) == 2:
                        symbol, timeframe = parts
                    else:
                        logger.warning(
                            "[DB Save] Cannot parse tab_id %s, skipping", tab_id
                        )
                        continue
                else:
                    logger.warning(
                        "[DB Save] Tab ID %s not recognized, skipping", tab_id
                    )
                    continue

                logger.info(
                    "[DB Save] Processing %s %s (tab_id: %s)",
                    symbol,
                    timeframe,
                    tab_id,
                )

                for group in ["brackets", "breaks"]:
                    items = tab_data.get(group, [])
                    logger.info("[DB Save]   %s: %d items", group, len(items))
                    for item in items:
                        try:
                            overlay_id = uuid.UUID(item.get("id", ""))
                        except (ValueError, AttributeError):
                            overlay_id = uuid.uuid4()

                        overlay = ChartOverlay(
                            overlay_id=overlay_id,
                            symbol=symbol,
                            timeframe=timeframe,
                            group=group,
                            price=float(item["price"]),
                            name=item.get("name", ""),
                            color=item.get(
                                "color",
                                "#00ff88" if group == "brackets" else "#ff4444",
                            ),
                            visible=item.get("visible", True),
                        )
                        db.add(overlay)
                        saved_count += 1
                        logger.info(
                            "[DB Save]     Added %s at $%s (name: %s)",
                            group,
                            item["price"],
                            item.get("name", "N/A"),
                        )

            db.commit()
            logger.info(
                "[DB Save] Successfully saved %d overlays to database", saved_count
            )
    except Exception as e:
        logger.error(
            "[DB Save] Error saving overlays to DB: %s", e, exc_info=True
        )
