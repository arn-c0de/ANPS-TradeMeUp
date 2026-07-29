"""Databases Tab - Database management, export/import, and history."""

import base64
import json
import logging
import re
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.config.settings import VERSION
from src.models.analysis import (
    FactVerification,
    ImpactScore,
    MarketRegime,
    SignalDecayModel,
    SurpriseScore,
)
from src.models.chart_overlays import ChartOverlay
from src.models.data_quality import DataQualityScore
from src.models.database import engine as _engine
from src.models.entities import Entity, EntityRelationship, NewsEntityMapping
from src.models.predictions import BacktestResult, MarketData, Prediction, PredictionOutcome
from src.models.processed_news import ProcessedNews
from src.models.raw_news import RawNews
from src.models.trading_simulation import TradingSimulation
from src.utils.cache import cached_query

logger = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────
HISTORY_FILE = Path(__file__).resolve().parents[3] / "data" / "db_history.json"
EXPORT_FORMAT = "TradeMeUp-DB-Export"
EXPORT_FORMAT_VERSION = "1.0"
PAGE_SIZE = 20

# Table stats are a COUNT(*) per table; cache them briefly so tab switches do
# not re-run the whole set. The refresh button invalidates the entry.
DB_STATS_TTL = 10

# Security limits
_MAX_IMPORT_BYTES = 200 * 1024 * 1024   # 200 MB decoded
_MAX_ROWS_PER_TABLE = 500_000
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)

# FK-safe insertion order (parents before children)
_TABLE_ORDER_EXPORT = [
    "raw_news", "entities",
    "market_regimes", "backtest_results", "market_data", "chart_overlays",
    "processed_news", "data_quality_scores",
    "news_entity_mapping", "entity_relationships",
    "impact_scores", "surprise_scores", "fact_verifications", "signal_decay_models",
    "predictions", "prediction_outcomes", "trading_simulations",
]

_MODEL_MAP = {
    "raw_news": RawNews,
    "entities": Entity,
    "market_regimes": MarketRegime,
    "backtest_results": BacktestResult,
    "market_data": MarketData,
    "chart_overlays": ChartOverlay,
    "processed_news": ProcessedNews,
    "data_quality_scores": DataQualityScore,
    "news_entity_mapping": NewsEntityMapping,
    "entity_relationships": EntityRelationship,
    "impact_scores": ImpactScore,
    "surprise_scores": SurpriseScore,
    "fact_verifications": FactVerification,
    "signal_decay_models": SignalDecayModel,
    "predictions": Prediction,
    "prediction_outcomes": PredictionOutcome,
    "trading_simulations": TradingSimulation,
}


# Per-model column whitelist — built once at import time, prevents mass-assignment
_MODEL_COLUMNS: dict[str, frozenset] = {
    tbl: frozenset(c.name for c in model.__table__.columns)
    for tbl, model in _MODEL_MAP.items()
}

# ── JSON helpers ──────────────────────────────────────────────────────────────
class _DBEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode()
        return super().default(obj)


def _serialize_row(row) -> dict:
    result = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        if isinstance(val, UUID):
            val = str(val)
        elif isinstance(val, datetime):
            val = val.isoformat()
        result[col.name] = val
    return result


# ── history file helpers ──────────────────────────────────────────────────────
def _load_history() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text())
    except Exception:
        return []


def _save_history(events: list) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(events, indent=2))


def _record_event(event_type: str, stats: dict, notes: str = "", source_file: str = "") -> None:
    events = _load_history()
    events.append({
        "event_type": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "hostname": socket.gethostname(),
        "stats": stats,
        "notes": notes,
        "source_file": source_file,
    })
    _save_history(events)


# ── database query helpers ────────────────────────────────────────────────────
@cached_query(key_prefix="databases:table_stats", ttl=DB_STATS_TTL)
def _query_db_stats() -> dict:
    """Row count per managed table, plus the on-disk database size.

    One COUNT(*) per table plus a pg_database_size() call, so it is cached for
    the moment it takes a user to switch back to this tab. The explicit refresh
    button clears the entry first - see _refresh_stats.
    """
    stats = {}
    with Session(_engine) as db:
        for tbl, model in _MODEL_MAP.items():
            try:
                stats[tbl] = db.query(func.count()).select_from(model).scalar() or 0
            except Exception:
                stats[tbl] = "?"
        try:
            row = db.execute(text(
                "SELECT pg_size_pretty(pg_database_size(current_database()))"
            )).fetchone()
            stats["_db_size"] = row[0] if row else "N/A"
        except Exception:
            stats["_db_size"] = "N/A"
    return stats


def _get_db_stats() -> dict:
    """Table stats, or {'_error': ...} if the database is unreachable.

    The failure path stays outside the cache so a transient outage is not
    served back for the whole TTL.
    """
    try:
        return _query_db_stats()
    except Exception as e:
        return {"_error": str(e)}


def _invalidate_db_stats() -> None:
    """Drop the cached table stats after anything writes to the database."""
    try:
        _query_db_stats.cache_invalidate()
    except Exception as e:  # never let a cache problem break a delete/import
        logger.debug(f"Could not invalidate db stats cache: {e}")


def _get_news_page(page: int) -> tuple[list, int]:
    offset = page * PAGE_SIZE
    try:
        with Session(_engine) as db:
            total = db.query(func.count()).select_from(RawNews).scalar() or 0
            rows = (
                db.query(RawNews)
                .order_by(RawNews.published_at.desc())
                .offset(offset)
                .limit(PAGE_SIZE)
                .all()
            )
            news_ids = [str(r.news_id) for r in rows]
            processed_set = set()
            if news_ids:
                processed = db.query(ProcessedNews.news_id).filter(
                    ProcessedNews.news_id.in_(news_ids)
                ).all()
                processed_set = {str(p[0]) for p in processed}
            pred_counts = {}
            if news_ids:
                for nid in news_ids:
                    count = db.execute(text(
                        "SELECT COUNT(*) FROM predictions WHERE related_news_ids @> :arr::jsonb"
                    ), {"arr": json.dumps([nid])}).scalar()
                    pred_counts[nid] = count or 0
            data = []
            for r in rows:
                nid = str(r.news_id)
                data.append({
                    "news_id": nid,
                    "title": (r.title or "")[:80],
                    "source": r.source or "",
                    "published_at": r.published_at.strftime("%Y-%m-%d %H:%M") if r.published_at else "",
                    "processed": nid in processed_set,
                    "predictions": pred_counts.get(nid, 0),
                })
            return data, total
    except Exception:
        return [], 0


def _get_predictions_page(page: int) -> tuple[list, int]:
    offset = page * PAGE_SIZE
    try:
        with Session(_engine) as db:
            total = db.query(func.count()).select_from(Prediction).scalar() or 0
            rows = (
                db.query(Prediction)
                .order_by(Prediction.created_at.desc())
                .offset(offset)
                .limit(PAGE_SIZE)
                .all()
            )
            data = []
            for r in rows:
                news_count = len(r.related_news_ids) if r.related_news_ids else 0
                data.append({
                    "prediction_id": str(r.prediction_id),
                    "entity_id": r.entity_id or "",
                    "horizon": r.horizon or "",
                    "confidence": f"{r.confidence:.2f}" if r.confidence is not None else "",
                    "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                    "news_count": news_count,
                })
            return data, total
    except Exception:
        return [], 0


def _get_simulations_page(page: int) -> tuple[list, int]:
    offset = page * PAGE_SIZE
    try:
        with Session(_engine) as db:
            total = db.query(func.count()).select_from(TradingSimulation).scalar() or 0
            rows = (
                db.query(TradingSimulation)
                .order_by(TradingSimulation.created_at.desc())
                .offset(offset)
                .limit(PAGE_SIZE)
                .all()
            )
            data = []
            for r in rows:
                data.append({
                    "simulation_id": str(r.simulation_id),
                    "entity_id": r.entity_id or "",
                    "horizon": r.horizon or "",
                    "decision": r.decision or "",
                    "expected_return_pct": f"{r.expected_return_pct:.2f}%" if r.expected_return_pct is not None else "",
                    "actual_return_pct": f"{r.actual_return_pct:.2f}%" if r.actual_return_pct is not None else "–",
                    "risk_score": f"{r.risk_score:.2f}" if r.risk_score is not None else "",
                    "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                })
            return data, total
    except Exception:
        return [], 0


def _delete_simulation(sim_id: str) -> int:
    _invalidate_db_stats()
    try:
        with Session(_engine) as db:
            n = db.execute(text(
                "DELETE FROM trading_simulations WHERE simulation_id = :id"
            ), {"id": sim_id}).rowcount
            db.commit()
        return n
    except Exception:
        return 0


def _delete_news_cascade(news_id: str, also_delete_predictions: bool) -> tuple[int, int]:
    """Delete a news article and all related records. Returns (news_deleted, predictions_deleted)."""
    _invalidate_db_stats()
    pred_count = 0
    try:
        with Session(_engine) as db:
            if also_delete_predictions:
                pred_ids = db.execute(text(
                    "SELECT prediction_id FROM predictions WHERE related_news_ids @> :arr::jsonb"
                ), {"arr": json.dumps([news_id])}).fetchall()
                pred_ids = [str(row[0]) for row in pred_ids]
                if pred_ids:
                    db.execute(text(
                        "DELETE FROM trading_simulations WHERE prediction_id = ANY(:ids)"
                    ), {"ids": pred_ids})
                    db.execute(text(
                        "DELETE FROM prediction_outcomes WHERE prediction_id = ANY(:ids)"
                    ), {"ids": pred_ids})
                    db.execute(text(
                        "DELETE FROM predictions WHERE prediction_id = ANY(:ids)"
                    ), {"ids": pred_ids})
                    pred_count = len(pred_ids)
            db.execute(text("DELETE FROM fact_verifications WHERE news_id = :id"), {"id": news_id})
            db.execute(text("DELETE FROM surprise_scores WHERE news_id = :id"), {"id": news_id})
            db.execute(text("DELETE FROM signal_decay_models WHERE news_id = :id"), {"id": news_id})
            db.execute(text("DELETE FROM impact_scores WHERE news_id = :id"), {"id": news_id})
            db.execute(text("DELETE FROM data_quality_scores WHERE news_id = :id"), {"id": news_id})
            db.execute(text("DELETE FROM news_entity_mapping WHERE news_id = :id"), {"id": news_id})
            db.execute(text("DELETE FROM processed_news WHERE news_id = :id"), {"id": news_id})
            db.execute(text("DELETE FROM raw_news WHERE news_id = :id"), {"id": news_id})
            db.commit()
        return 1, pred_count
    except Exception:
        return 0, 0


def _delete_prediction(pred_id: str) -> int:
    _invalidate_db_stats()
    try:
        with Session(_engine) as db:
            db.execute(text(
                "DELETE FROM trading_simulations WHERE prediction_id = :id"
            ), {"id": pred_id})
            db.execute(text(
                "DELETE FROM prediction_outcomes WHERE prediction_id = :id"
            ), {"id": pred_id})
            n = db.execute(text(
                "DELETE FROM predictions WHERE prediction_id = :id"
            ), {"id": pred_id}).rowcount
            db.commit()
        return n
    except Exception:
        return 0


# ── export / import ───────────────────────────────────────────────────────────
_DATE_COLS = {
    "raw_news": "created_at", "processed_news": "processing_timestamp",
    "predictions": "created_at", "prediction_outcomes": "created_at",
    "trading_simulations": "created_at", "impact_scores": "created_at",
    "surprise_scores": "created_at", "fact_verifications": "verified_at",
    "signal_decay_models": "created_at", "data_quality_scores": "created_at",
    "news_entity_mapping": "created_at", "entity_relationships": "created_at",
    "entities": "created_at", "market_regimes": "created_at",
    "backtest_results": "created_at", "chart_overlays": "created_at",
}


def _cutoff_from_range(timerange: str, custom_start: str | None, custom_end: str | None):
    """Return (start_dt, end_dt) or (None, None) for all-time."""
    from datetime import timedelta
    now = datetime.now(UTC)
    _map = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
    if timerange in _map:
        return now - timedelta(days=_map[timerange]), now
    if timerange == "custom" and custom_start:
        try:
            start = datetime.fromisoformat(custom_start).replace(tzinfo=UTC)
            end = datetime.fromisoformat(custom_end).replace(tzinfo=UTC) if custom_end else now
            if start > end:
                start, end = end, start
            return start, end
        except (ValueError, TypeError):
            return None, None
    return None, None


def _export_db(selected_tables: list,
               timerange: str = "all",
               custom_start: str | None = None,
               custom_end: str | None = None) -> str:
    data: dict[str, list] = {}
    stats: dict[str, int] = {}
    start_dt, end_dt = _cutoff_from_range(timerange, custom_start, custom_end)
    try:
        with Session(_engine) as db:
            for tbl in _TABLE_ORDER_EXPORT:
                if tbl not in selected_tables:
                    continue
                model = _MODEL_MAP[tbl]
                q = db.query(model)
                date_col_name = _DATE_COLS.get(tbl)
                if start_dt and date_col_name and hasattr(model, date_col_name):
                    date_col = getattr(model, date_col_name)
                    q = q.filter(date_col >= start_dt, date_col <= end_dt)
                rows = q.all()
                data[tbl] = [_serialize_row(r) for r in rows]
                stats[tbl] = len(data[tbl])
    except Exception as e:
        return json.dumps({"error": str(e)})

    history = _load_history()
    export_obj = {
        "format": EXPORT_FORMAT,
        "format_version": EXPORT_FORMAT_VERSION,
        "app_version": VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "hostname": socket.gethostname(),
        "export_stats": stats,
        "import_history": history,
        "data": data,
    }
    _record_event("export", stats, notes=f"tables: {', '.join(selected_tables)}")
    return json.dumps(export_obj, indent=2, cls=_DBEncoder)


def _parse_import_file(content_b64: str) -> tuple[dict | None, str | None]:
    """Returns (parsed_obj, error_message). Exactly one is None."""
    try:
        if "," in content_b64:
            content_b64 = content_b64.split(",", 1)[1]

        # Size guard before decoding
        if len(content_b64) > _MAX_IMPORT_BYTES * 4 // 3 + 4:
            return None, f"File exceeds the {_MAX_IMPORT_BYTES // (1024*1024)} MB import limit."

        raw = base64.b64decode(content_b64).decode("utf-8")

        if len(raw.encode()) > _MAX_IMPORT_BYTES:
            return None, f"File exceeds the {_MAX_IMPORT_BYTES // (1024*1024)} MB import limit."

        obj = json.loads(raw)

        if not isinstance(obj, dict):
            return None, "Invalid file: top-level structure must be a JSON object."
        if obj.get("format") != EXPORT_FORMAT:
            return None, "Invalid file: not a TradeMeUp export (.tmu)."
        if obj.get("format_version") != EXPORT_FORMAT_VERSION:
            return None, (
                f"Unsupported format version '{obj.get('format_version')}'. "
                f"Expected '{EXPORT_FORMAT_VERSION}'."
            )

        data = obj.get("data")
        if not isinstance(data, dict):
            return None, "Invalid file: 'data' section missing or malformed."

        # Validate per-table structure
        for tbl, rows in data.items():
            if tbl not in _MODEL_MAP:
                # Unknown table — skip silently (forward-compat)
                continue
            if not isinstance(rows, list):
                return None, f"Invalid file: table '{tbl}' must be a list."
            if len(rows) > _MAX_ROWS_PER_TABLE:
                return None, (
                    f"Table '{tbl}' contains {len(rows):,} rows which exceeds the "
                    f"per-table limit of {_MAX_ROWS_PER_TABLE:,}."
                )
            for i, row in enumerate(rows[:5]):          # spot-check first 5
                if not isinstance(row, dict):
                    return None, f"Invalid file: row {i} in '{tbl}' is not a JSON object."

        return obj, None
    except (UnicodeDecodeError, base64.binascii.Error):
        return None, "File could not be decoded. Is it a valid .tmu export?"
    except json.JSONDecodeError:
        return None, "File is not valid JSON."
    except Exception:
        return None, "Unexpected error while reading the file."


def _sanitise_str(val: Any, max_len: int = 200) -> str:
    """Return a safe printable string, truncated to max_len."""
    return str(val)[:max_len].encode("ascii", errors="replace").decode("ascii")


def _coerce_row(row_dict: dict, tbl: str) -> dict:
    """
    Return a copy of row_dict with:
    - only columns that belong to the model (prevents mass-assignment)
    - values type-coerced to match column types
    """
    from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
    from sqlalchemy.dialects.postgresql import JSONB

    model = _MODEL_MAP[tbl]
    valid_cols = _MODEL_COLUMNS[tbl]
    col_types = {c.name: type(c.type) for c in model.__table__.columns}
    result = {}
    for key, val in row_dict.items():
        if key not in valid_cols:
            continue                            # drop unknown keys
        if val is None:
            result[key] = None
            continue
        col_type = col_types.get(key)
        try:
            if col_type in (Float,):
                result[key] = float(val)
            elif col_type in (Integer,):
                result[key] = int(val)
            elif col_type in (Boolean,):
                result[key] = bool(val)
            elif col_type in (String, Text):
                result[key] = str(val)[:10_000]
            elif col_type in (DateTime,):
                if isinstance(val, str):
                    dt = datetime.fromisoformat(val)
                    result[key] = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
                else:
                    result[key] = val
            elif col_type is JSONB:
                # Must be a JSON-serialisable type
                if not isinstance(val, (dict, list, str, int, float, bool, type(None))):
                    result[key] = None
                else:
                    result[key] = val
            else:
                result[key] = val
        except (ValueError, TypeError):
            result[key] = None
    return result


def _execute_import(obj: dict, mode: str,
                    timerange: str = "all",
                    custom_start: str | None = None,
                    custom_end: str | None = None) -> dict:
    """mode: 'merge' or 'replace'. Returns result stats dict."""
    _invalidate_db_stats()
    data = obj.get("data", {})
    if not isinstance(data, dict):
        return {"results": {}, "errors": ["Malformed import file."]}

    results: dict[str, int] = {}
    errors: list[str] = []
    start_dt, end_dt = _cutoff_from_range(timerange, custom_start, custom_end)

    def _in_window(row_dict: dict, tbl: str) -> bool:
        if not start_dt:
            return True
        col = _DATE_COLS.get(tbl)
        if not col or col not in row_dict or row_dict[col] is None:
            return True
        try:
            val = row_dict[col]
            if isinstance(val, str):
                dt = datetime.fromisoformat(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
            else:
                dt = val
            return start_dt <= dt <= end_dt
        except Exception:
            return True

    if mode not in ("merge", "replace"):
        return {"results": {}, "errors": ["Invalid import mode."]}

    if mode == "replace":
        try:
            with Session(_engine) as db:
                for tbl in reversed(_TABLE_ORDER_EXPORT):
                    if tbl in data and tbl in _MODEL_MAP:
                        db.query(_MODEL_MAP[tbl]).delete()
                db.commit()
        except Exception:
            return {"results": {}, "errors": ["Failed to clear existing data before replace."]}

    for tbl in _TABLE_ORDER_EXPORT:
        if tbl not in data or tbl not in _MODEL_MAP:
            continue
        raw_rows = data[tbl]
        if not isinstance(raw_rows, list):
            errors.append(f"{tbl}: skipped (not a list).")
            continue
        raw_rows = raw_rows[:_MAX_ROWS_PER_TABLE]

        model = _MODEL_MAP[tbl]
        rows = [r for r in raw_rows if isinstance(r, dict) and _in_window(r, tbl)]
        inserted = 0
        skipped = 0
        for row_dict in rows:
            try:
                safe = _coerce_row(row_dict, tbl)
                with Session(_engine) as db:
                    instance = model(**safe)
                    if mode == "merge":
                        db.merge(instance)
                    else:
                        db.add(instance)
                    db.commit()
                    inserted += 1
            except Exception:
                skipped += 1
        results[tbl] = inserted
        if skipped:
            errors.append(f"{tbl}: {skipped} row(s) skipped due to constraint violations.")

    # Sanitise file metadata before writing to local history
    filter_note = "" if timerange == "all" else f", filter={timerange}"
    safe_host = _sanitise_str(obj.get("hostname", "unknown"), 64)
    safe_ts   = _sanitise_str(obj.get("exported_at", "unknown"), 32)
    _record_event(
        "import",
        results,
        notes=f"mode={mode}{filter_note}, from={safe_host}, exported={safe_ts}",
        source_file=safe_host,
    )
    return {"results": results, "errors": errors}


# ── layout helpers ────────────────────────────────────────────────────────────
def _stat_card(title: str, value: Any, color: str = "primary") -> dbc.Col:
    return dbc.Col(
        dbc.Card([
            dbc.CardBody([
                html.P(title, className="text-muted small mb-1"),
                html.H4(str(value), className=f"fw-bold text-{color} mb-0"),
            ], className="p-3")
        ], className="rounded-3 border-0 shadow-sm h-100"),
        xs=6, md=3, className="mb-3"
    )


def _page_controls(page: int, total: int, page_size: int,
                   prev_id: str, next_id: str, info_id: str) -> html.Div:
    total_pages = max(1, (total + page_size - 1) // page_size)
    return html.Div([
        dbc.Button("← Prev", id=prev_id, size="sm", color="secondary",
                   disabled=page == 0, className="me-2"),
        html.Span(f"Page {page + 1} / {total_pages}  ({total} records)",
                  id=info_id, className="text-muted small align-middle"),
        dbc.Button("Next →", id=next_id, size="sm", color="secondary",
                   disabled=page >= total_pages - 1, className="ms-2"),
    ], className="d-flex align-items-center mt-3")


# ── create_layout ─────────────────────────────────────────────────────────────
def create_layout() -> dbc.Container:
    return dbc.Container([
        # Header
        dbc.Row([
            dbc.Col([
                html.H2("Databases", className="mb-1 fw-bold"),
                html.P("Browse, export, import, and manage your PostgreSQL database.",
                       className="text-muted mb-0"),
            ], width=12),
        ], className="mb-4"),

        # Stats row (populated by callback)
        html.Div(id="db-stats-row", className="mb-4"),

        # Refresh button
        dbc.Row([
            dbc.Col(
                dbc.Button("↻ Refresh Stats", id="db-refresh-stats",
                           color="outline-secondary", size="sm"),
                width="auto"
            )
        ], className="mb-3"),

        # Main sub-tabs
        dbc.Tabs([
            # ── Browse ────────────────────────────────────────────────────────
            dbc.Tab(label="🔍 Browse", tab_id="db-tab-browse", children=[
                html.Div(className="pt-4", children=[
                    dbc.Tabs([
                        # News browser
                        dbc.Tab(label="📰 News", tab_id="db-browse-news", children=[
                            html.Div(className="pt-3", children=[
                                html.Div(id="db-news-table-container"),
                                html.Div(id="db-news-page-controls"),
                                # Delete modal trigger
                                html.Div(id="db-news-delete-status", className="mt-2"),
                            ])
                        ]),
                        # Predictions browser
                        dbc.Tab(label="🎯 Predictions", tab_id="db-browse-preds", children=[
                            html.Div(className="pt-3", children=[
                                html.Div(id="db-pred-table-container"),
                                html.Div(id="db-pred-page-controls"),
                                html.Div(id="db-pred-delete-status", className="mt-2"),
                            ])
                        ]),
                        # Simulations browser
                        dbc.Tab(label="🧪 Simulations", tab_id="db-browse-sims", children=[
                            html.Div(className="pt-3", children=[
                                html.Div(id="db-sim-table-container"),
                                html.Div(id="db-sim-page-controls"),
                                html.Div(id="db-sim-delete-status", className="mt-2"),
                            ])
                        ]),
                    ], id="db-browse-subtabs", active_tab="db-browse-news"),
                ])
            ]),

            # ── Export ────────────────────────────────────────────────────────
            dbc.Tab(label="📤 Export", tab_id="db-tab-export", children=[
                html.Div(className="pt-4", children=[
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader(html.H6("Export Database to .tmu File", className="mb-0 fw-semibold")),
                                dbc.CardBody([
                                    html.P(
                                        "Select which tables to include in the export. "
                                        "The file will contain all records along with the local import/export history.",
                                        className="text-muted small mb-3"
                                    ),
                                    # Time window
                                    dbc.Label("Time Window", className="fw-semibold small"),
                                    dbc.Row([
                                        dbc.Col([
                                            dcc.Dropdown(
                                                id="db-export-timerange",
                                                options=[
                                                    {"label": "All data (default)", "value": "all"},
                                                    {"label": "Last 24 hours", "value": "1d"},
                                                    {"label": "Last 7 days", "value": "7d"},
                                                    {"label": "Last 30 days", "value": "30d"},
                                                    {"label": "Last 90 days", "value": "90d"},
                                                    {"label": "Custom range", "value": "custom"},
                                                ],
                                                value="all",
                                                clearable=False,
                                                className="mb-2",
                                            )
                                        ], md=6),
                                        dbc.Col([
                                            html.Div(id="db-export-custom-dates-wrap", children=[
                                                dcc.DatePickerRange(
                                                    id="db-export-custom-dates",
                                                    display_format="YYYY-MM-DD",
                                                    start_date=None,
                                                    end_date=None,
                                                )
                                            ], style={"display": "none"}),
                                        ], md=6),
                                    ], className="mb-3"),
                                    html.Hr(className="my-3"),
                                    dbc.Label("Tables to export", className="fw-semibold small"),
                                    dcc.Checklist(
                                        id="db-export-tables",
                                        options=[{"label": f" {t}", "value": t} for t in _TABLE_ORDER_EXPORT],
                                        value=_TABLE_ORDER_EXPORT,
                                        labelStyle={"display": "block", "marginBottom": "4px"},
                                        className="mb-3 small",
                                    ),
                                    dbc.Row([
                                        dbc.Col(
                                            dbc.Button("Select All", id="db-export-select-all",
                                                       size="sm", color="outline-secondary"),
                                            width="auto"
                                        ),
                                        dbc.Col(
                                            dbc.Button("Clear All", id="db-export-clear-all",
                                                       size="sm", color="outline-secondary"),
                                            width="auto"
                                        ),
                                    ], className="mb-4"),
                                    dbc.Alert(
                                        "The export embeds the full local history so any system that imports "
                                        "this file will see when and where it was originally created.",
                                        color="info", className="small mb-4"
                                    ),
                                    dbc.Button("⬇ Export to .tmu", id="db-export-btn",
                                               color="primary", className="w-100 rounded-2"),
                                    html.Div(id="db-export-status", className="mt-3"),
                                    dcc.Download(id="db-export-download"),
                                ])
                            ], className="rounded-3 border-0 shadow-sm")
                        ], md=8)
                    ])
                ])
            ]),

            # ── Import ────────────────────────────────────────────────────────
            dbc.Tab(label="📥 Import", tab_id="db-tab-import", children=[
                html.Div(className="pt-4", children=[
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader(html.H6("Import from .tmu File", className="mb-0 fw-semibold")),
                                dbc.CardBody([
                                    dcc.Upload(
                                        id="db-import-upload",
                                        children=html.Div([
                                            html.Span("Drag & drop a .tmu file here, or "),
                                            html.A("click to browse", className="text-primary"),
                                        ]),
                                        style={
                                            "width": "100%", "height": "80px",
                                            "lineHeight": "80px", "borderWidth": "2px",
                                            "borderStyle": "dashed", "borderRadius": "8px",
                                            "textAlign": "center", "borderColor": "#555",
                                            "backgroundColor": "#1a1a2e",
                                        },
                                        accept=".tmu,.json",
                                        className="mb-4",
                                    ),
                                    # Preview area
                                    html.Div(id="db-import-preview"),
                                    # Mode selector
                                    html.Div(id="db-import-mode-section", style={"display": "none"}, children=[
                                        html.Hr(),
                                        dbc.Label("Time Filter (optional)", className="fw-semibold small"),
                                        html.P("Only import records within this date range. Leave as 'All data' to import everything.",
                                               className="text-muted small mb-2"),
                                        dbc.Row([
                                            dbc.Col([
                                                dcc.Dropdown(
                                                    id="db-import-timerange",
                                                    options=[
                                                        {"label": "All data (default)", "value": "all"},
                                                        {"label": "Last 24 hours", "value": "1d"},
                                                        {"label": "Last 7 days", "value": "7d"},
                                                        {"label": "Last 30 days", "value": "30d"},
                                                        {"label": "Last 90 days", "value": "90d"},
                                                        {"label": "Custom range", "value": "custom"},
                                                    ],
                                                    value="all",
                                                    clearable=False,
                                                    className="mb-2",
                                                )
                                            ], md=6),
                                            dbc.Col([
                                                html.Div(id="db-import-custom-dates-wrap", children=[
                                                    dcc.DatePickerRange(
                                                        id="db-import-custom-dates",
                                                        display_format="YYYY-MM-DD",
                                                    )
                                                ], style={"display": "none"}),
                                            ], md=6),
                                        ], className="mb-3"),
                                        html.Hr(),
                                        dbc.Label("Import Mode", className="fw-semibold small"),
                                        dbc.RadioItems(
                                            id="db-import-mode",
                                            options=[
                                                {"label": " Merge — add new records, skip duplicates (safe)",
                                                 "value": "merge"},
                                                {"label": " Replace — clear selected tables first, then insert all records (destructive!)",
                                                 "value": "replace"},
                                            ],
                                            value="merge",
                                            className="mb-3 small",
                                        ),
                                        dbc.Alert(
                                            "Replace mode will permanently delete all existing data in the imported tables before inserting. "
                                            "This cannot be undone.",
                                            id="db-import-replace-warning",
                                            color="warning",
                                            style={"display": "none"},
                                            className="small mb-3",
                                        ),
                                        dbc.Button("✓ Confirm Import", id="db-import-confirm-btn",
                                                   color="success", className="w-100 rounded-2"),
                                        html.Div(id="db-import-result", className="mt-3"),
                                    ]),
                                ])
                            ], className="rounded-3 border-0 shadow-sm")
                        ], md=8)
                    ])
                ])
            ]),

            # ── History ───────────────────────────────────────────────────────
            dbc.Tab(label="📋 History", tab_id="db-tab-history", children=[
                html.Div(className="pt-4", children=[
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader([
                                    dbc.Row([
                                        dbc.Col(html.H6("Import / Export History", className="mb-0 fw-semibold")),
                                        dbc.Col(
                                            dbc.Button("↻ Refresh", id="db-history-refresh",
                                                       size="sm", color="outline-secondary"),
                                            width="auto"
                                        ),
                                        dbc.Col(
                                            dbc.Button("🗑 Clear History", id="db-history-clear-btn",
                                                       size="sm", color="outline-danger"),
                                            width="auto"
                                        ),
                                    ], align="center")
                                ]),
                                dbc.CardBody([
                                    html.Div(id="db-history-table"),
                                    html.Div(id="db-history-clear-status", className="mt-2"),
                                ])
                            ], className="rounded-3 border-0 shadow-sm")
                        ], width=12)
                    ])
                ])
            ]),
        ], id="db-main-tabs", active_tab="db-tab-browse"),

        # Shared state
        dcc.Store(id="db-news-page", data=0),
        dcc.Store(id="db-pred-page", data=0),
        dcc.Store(id="db-sim-page", data=0),
        dcc.Store(id="db-import-parsed", data=None),
        dcc.Store(id="db-delete-news-id", data=None),
        dcc.Store(id="db-delete-pred-id", data=None),
        dcc.Store(id="db-delete-sim-id", data=None),

        # Delete confirmation modals
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Delete News Article")),
            dbc.ModalBody([
                html.Div(id="db-news-delete-modal-body"),
                html.Hr(),
                dbc.Switch(
                    id="db-news-delete-also-preds",
                    label="Also delete all predictions linked to this article",
                    value=True,
                    className="mt-2"
                ),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="db-news-delete-cancel", color="secondary",
                           className="me-2 rounded-2"),
                dbc.Button("Delete", id="db-news-delete-confirm", color="danger",
                           className="rounded-2"),
            ])
        ], id="db-news-delete-modal", is_open=False, backdrop="static"),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Delete Prediction")),
            dbc.ModalBody([
                html.Div(id="db-pred-delete-modal-body"),
                html.P("This will also remove any associated outcomes and simulations.",
                       className="text-warning small mt-2"),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="db-pred-delete-cancel", color="secondary",
                           className="me-2 rounded-2"),
                dbc.Button("Delete", id="db-pred-delete-confirm", color="danger",
                           className="rounded-2"),
            ])
        ], id="db-pred-delete-modal", is_open=False, backdrop="static"),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Delete Simulation")),
            dbc.ModalBody(html.Div(id="db-sim-delete-modal-body")),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="db-sim-delete-cancel", color="secondary",
                           className="me-2 rounded-2"),
                dbc.Button("Delete", id="db-sim-delete-confirm", color="danger",
                           className="rounded-2"),
            ])
        ], id="db-sim-delete-modal", is_open=False, backdrop="static"),

    ], fluid=True)


# ── register_callbacks ────────────────────────────────────────────────────────
def register_callbacks(app) -> None:

    # ── stats refresh ─────────────────────────────────────────────────────────
    @app.callback(
        Output("db-stats-row", "children"),
        [Input("tabs", "active_tab"), Input("db-refresh-stats", "n_clicks")],
        prevent_initial_call=False,
    )
    def _refresh_stats(active_tab, _n):
        # An explicit refresh click must re-query, not re-serve the cache.
        if dash.callback_context.triggered_id == "db-refresh-stats":
            _query_db_stats.cache_invalidate()

        stats = _get_db_stats()
        if "_error" in stats:
            return dbc.Alert(f"DB error: {stats['_error']}", color="danger")
        cards = [
            _stat_card("Raw News", stats.get("raw_news", 0), "info"),
            _stat_card("Processed News", stats.get("processed_news", 0), "info"),
            _stat_card("Predictions", stats.get("predictions", 0), "success"),
            _stat_card("Simulations", stats.get("trading_simulations", 0), "success"),
            _stat_card("Entities", stats.get("entities", 0), "warning"),
            _stat_card("Entity Relations", stats.get("entity_relationships", 0), "warning"),
            _stat_card("News↔Entity Maps", stats.get("news_entity_mapping", 0), "secondary"),
            _stat_card("Impact Scores", stats.get("impact_scores", 0), "secondary"),
            _stat_card("Surprise Scores", stats.get("surprise_scores", 0), "light"),
            _stat_card("Outcomes", stats.get("prediction_outcomes", 0), "light"),
            _stat_card("Market Regimes", stats.get("market_regimes", 0), "light"),
            _stat_card("Chart Overlays", stats.get("chart_overlays", 0), "light"),
            _stat_card("Backtest Results", stats.get("backtest_results", 0), "light"),
            _stat_card("Market Data", stats.get("market_data", 0), "light"),
            _stat_card("Fact Verif.", stats.get("fact_verifications", 0), "light"),
            _stat_card("DB Size", stats.get("_db_size", "N/A"), "primary"),
        ]
        return dbc.Row(cards)

    # ── news browser ──────────────────────────────────────────────────────────
    @app.callback(
        [Output("db-news-table-container", "children"),
         Output("db-news-page-controls", "children")],
        [Input("db-news-page", "data"),
         Input("db-news-delete-status", "children"),
         Input("db-browse-subtabs", "active_tab")],
        prevent_initial_call=False,
    )
    def _render_news_table(page, _delete_trigger, active_sub):
        page = page or 0
        rows, total = _get_news_page(page)
        if not rows:
            table = html.P("No news articles found.", className="text-muted")
        else:
            table = dbc.Table([
                html.Thead(html.Tr([
                    html.Th("Title"), html.Th("Source"), html.Th("Published"),
                    html.Th("Processed"), html.Th("Predictions"), html.Th(""),
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(r["title"] + ("…" if len(r["title"]) == 80 else ""),
                                className="small"),
                        html.Td(r["source"], className="small"),
                        html.Td(r["published_at"], className="small text-muted"),
                        html.Td("✓" if r["processed"] else "–",
                                className="text-success" if r["processed"] else "text-muted"),
                        html.Td(str(r["predictions"]),
                                className="text-warning" if r["predictions"] else "text-muted"),
                        html.Td(
                            dbc.Button("🗑", id={"type": "db-news-del-btn", "index": r["news_id"]},
                                       size="sm", color="outline-danger", className="py-0 px-2"),
                        ),
                    ]) for r in rows
                ]),
            ], bordered=False, hover=True, responsive=True, size="sm",
               className="text-light mt-2 small")

        controls = _page_controls(
            page, total, PAGE_SIZE,
            "db-news-prev", "db-news-next", "db-news-page-info"
        )
        return table, controls

    @app.callback(
        Output("db-news-page", "data", allow_duplicate=True),
        [Input("db-news-prev", "n_clicks"), Input("db-news-next", "n_clicks")],
        State("db-news-page", "data"),
        prevent_initial_call=True,
    )
    def _news_paginate(prev, nxt, page):
        page = page or 0
        triggered = dash.callback_context.triggered[0]["prop_id"]
        if "prev" in triggered:
            return max(0, page - 1)
        return page + 1

    # ── news delete modal ─────────────────────────────────────────────────────
    @app.callback(
        [Output("db-news-delete-modal", "is_open"),
         Output("db-news-delete-modal-body", "children"),
         Output("db-delete-news-id", "data")],
        [Input({"type": "db-news-del-btn", "index": dash.ALL}, "n_clicks"),
         Input("db-news-delete-cancel", "n_clicks"),
         Input("db-news-delete-confirm", "n_clicks")],
        State("db-news-delete-modal", "is_open"),
        prevent_initial_call=True,
    )
    def _news_delete_modal(del_clicks, cancel, confirm, is_open):
        ctx = dash.callback_context
        if not ctx.triggered:
            return dash.no_update, dash.no_update, dash.no_update
        trigger_id = ctx.triggered[0]["prop_id"]
        if "db-news-del-btn" in trigger_id and any(c for c in (del_clicks or []) if c):
            import json as _json
            id_part = trigger_id.split(".")[0]
            news_id = _json.loads(id_part)["index"]
            body = html.Div([
                html.P(f"Article ID: {news_id[:18]}…", className="text-muted small"),
                html.P("This will permanently delete the article and all directly related records "
                       "(processed data, entity mappings, impact scores, etc.).",
                       className="small"),
            ])
            return True, body, news_id
        if "cancel" in trigger_id:
            return False, dash.no_update, None
        if "confirm" in trigger_id:
            return False, dash.no_update, dash.no_update
        return dash.no_update, dash.no_update, dash.no_update

    @app.callback(
        [Output("db-news-delete-status", "children"),
         Output("db-news-page", "data")],
        Input("db-news-delete-confirm", "n_clicks"),
        [State("db-delete-news-id", "data"),
         State("db-news-delete-also-preds", "value"),
         State("db-news-page", "data")],
        prevent_initial_call=True,
    )
    def _execute_news_delete(n_clicks, news_id, also_preds, page):
        if not n_clicks or not news_id:
            return dash.no_update, dash.no_update
        n, p = _delete_news_cascade(news_id, also_preds)
        if n:
            msg = f"Deleted 1 article and {p} predictions." if p else "Deleted 1 article."
            return dbc.Alert(msg, color="success", dismissable=True, duration=4000), page or 0
        return dbc.Alert("Delete failed.", color="danger", dismissable=True), page or 0

    # ── predictions browser ───────────────────────────────────────────────────
    @app.callback(
        [Output("db-pred-table-container", "children"),
         Output("db-pred-page-controls", "children")],
        [Input("db-pred-page", "data"),
         Input("db-pred-delete-status", "children"),
         Input("db-browse-subtabs", "active_tab")],
        prevent_initial_call=False,
    )
    def _render_pred_table(page, _trigger, _active):
        page = page or 0
        rows, total = _get_predictions_page(page)
        if not rows:
            table = html.P("No predictions found.", className="text-muted")
        else:
            table = dbc.Table([
                html.Thead(html.Tr([
                    html.Th("Prediction ID"), html.Th("Entity"), html.Th("Horizon"),
                    html.Th("Confidence"), html.Th("News"), html.Th("Created"), html.Th(""),
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(r["prediction_id"][:18] + "…", className="small text-muted font-monospace"),
                        html.Td(r["entity_id"], className="small fw-semibold"),
                        html.Td(r["horizon"], className="small"),
                        html.Td(r["confidence"], className="small"),
                        html.Td(str(r["news_count"]), className="small text-muted"),
                        html.Td(r["created_at"], className="small text-muted"),
                        html.Td(
                            dbc.Button("🗑", id={"type": "db-pred-del-btn", "index": r["prediction_id"]},
                                       size="sm", color="outline-danger", className="py-0 px-2"),
                        ),
                    ]) for r in rows
                ]),
            ], bordered=False, hover=True, responsive=True, size="sm",
               className="text-light mt-2 small")

        controls = _page_controls(
            page, total, PAGE_SIZE,
            "db-pred-prev", "db-pred-next", "db-pred-page-info"
        )
        return table, controls

    @app.callback(
        Output("db-pred-page", "data", allow_duplicate=True),
        [Input("db-pred-prev", "n_clicks"), Input("db-pred-next", "n_clicks")],
        State("db-pred-page", "data"),
        prevent_initial_call=True,
    )
    def _pred_paginate(prev, nxt, page):
        page = page or 0
        triggered = dash.callback_context.triggered[0]["prop_id"]
        if "prev" in triggered:
            return max(0, page - 1)
        return page + 1

    @app.callback(
        [Output("db-pred-delete-modal", "is_open"),
         Output("db-pred-delete-modal-body", "children"),
         Output("db-delete-pred-id", "data")],
        [Input({"type": "db-pred-del-btn", "index": dash.ALL}, "n_clicks"),
         Input("db-pred-delete-cancel", "n_clicks"),
         Input("db-pred-delete-confirm", "n_clicks")],
        State("db-pred-delete-modal", "is_open"),
        prevent_initial_call=True,
    )
    def _pred_delete_modal(del_clicks, cancel, confirm, is_open):
        ctx = dash.callback_context
        if not ctx.triggered:
            return dash.no_update, dash.no_update, dash.no_update
        trigger_id = ctx.triggered[0]["prop_id"]
        if "db-pred-del-btn" in trigger_id and any(c for c in (del_clicks or []) if c):
            import json as _json
            id_part = trigger_id.split(".")[0]
            pred_id = _json.loads(id_part)["index"]
            body = html.P(f"Prediction ID: {pred_id[:36]}", className="text-muted small")
            return True, body, pred_id
        if "cancel" in trigger_id:
            return False, dash.no_update, None
        if "confirm" in trigger_id:
            return False, dash.no_update, dash.no_update
        return dash.no_update, dash.no_update, dash.no_update

    @app.callback(
        [Output("db-pred-delete-status", "children"),
         Output("db-pred-page", "data")],
        Input("db-pred-delete-confirm", "n_clicks"),
        [State("db-delete-pred-id", "data"), State("db-pred-page", "data")],
        prevent_initial_call=True,
    )
    def _execute_pred_delete(n_clicks, pred_id, page):
        if not n_clicks or not pred_id:
            return dash.no_update, dash.no_update
        n = _delete_prediction(pred_id)
        if n:
            return dbc.Alert("Prediction deleted.", color="success", dismissable=True, duration=4000), page or 0
        return dbc.Alert("Delete failed.", color="danger", dismissable=True), page or 0

    # ── simulations browser ───────────────────────────────────────────────────
    @app.callback(
        [Output("db-sim-table-container", "children"),
         Output("db-sim-page-controls", "children")],
        [Input("db-sim-page", "data"),
         Input("db-sim-delete-status", "children"),
         Input("db-browse-subtabs", "active_tab")],
        prevent_initial_call=False,
    )
    def _render_sim_table(page, _trigger, _active):
        page = page or 0
        rows, total = _get_simulations_page(page)
        if not rows:
            table = html.P("No simulations found.", className="text-muted")
        else:
            decision_color = {"buy": "success", "sell": "danger", "hold": "secondary"}
            table = dbc.Table([
                html.Thead(html.Tr([
                    html.Th("ID"), html.Th("Entity"), html.Th("Horizon"),
                    html.Th("Decision"), html.Th("Expected"), html.Th("Actual"),
                    html.Th("Risk"), html.Th("Created"), html.Th(""),
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(r["simulation_id"][:12] + "…", className="small text-muted font-monospace"),
                        html.Td(r["entity_id"], className="small fw-semibold"),
                        html.Td(r["horizon"], className="small"),
                        html.Td(dbc.Badge(r["decision"], color=decision_color.get(r["decision"], "secondary"))),
                        html.Td(r["expected_return_pct"], className="small"),
                        html.Td(r["actual_return_pct"], className="small"),
                        html.Td(r["risk_score"], className="small"),
                        html.Td(r["created_at"], className="small text-muted"),
                        html.Td(
                            dbc.Button("🗑", id={"type": "db-sim-del-btn", "index": r["simulation_id"]},
                                       size="sm", color="outline-danger", className="py-0 px-2"),
                        ),
                    ]) for r in rows
                ]),
            ], bordered=False, hover=True, responsive=True, size="sm",
               className="text-light mt-2 small")

        controls = _page_controls(
            page, total, PAGE_SIZE,
            "db-sim-prev", "db-sim-next", "db-sim-page-info"
        )
        return table, controls

    @app.callback(
        Output("db-sim-page", "data", allow_duplicate=True),
        [Input("db-sim-prev", "n_clicks"), Input("db-sim-next", "n_clicks")],
        State("db-sim-page", "data"),
        prevent_initial_call=True,
    )
    def _sim_paginate(prev, nxt, page):
        page = page or 0
        triggered = dash.callback_context.triggered[0]["prop_id"]
        if "prev" in triggered:
            return max(0, page - 1)
        return page + 1

    @app.callback(
        [Output("db-sim-delete-modal", "is_open"),
         Output("db-sim-delete-modal-body", "children"),
         Output("db-delete-sim-id", "data")],
        [Input({"type": "db-sim-del-btn", "index": dash.ALL}, "n_clicks"),
         Input("db-sim-delete-cancel", "n_clicks"),
         Input("db-sim-delete-confirm", "n_clicks")],
        State("db-sim-delete-modal", "is_open"),
        prevent_initial_call=True,
    )
    def _sim_delete_modal(del_clicks, cancel, confirm, is_open):
        ctx = dash.callback_context
        if not ctx.triggered:
            return dash.no_update, dash.no_update, dash.no_update
        trigger_id = ctx.triggered[0]["prop_id"]
        if "db-sim-del-btn" in trigger_id and any(c for c in (del_clicks or []) if c):
            import json as _json
            sim_id = _json.loads(trigger_id.split(".")[0])["index"]
            body = html.P(f"Simulation ID: {sim_id[:36]}", className="text-muted small")
            return True, body, sim_id
        if "cancel" in trigger_id:
            return False, dash.no_update, None
        if "confirm" in trigger_id:
            return False, dash.no_update, dash.no_update
        return dash.no_update, dash.no_update, dash.no_update

    @app.callback(
        [Output("db-sim-delete-status", "children"),
         Output("db-sim-page", "data")],
        Input("db-sim-delete-confirm", "n_clicks"),
        [State("db-delete-sim-id", "data"), State("db-sim-page", "data")],
        prevent_initial_call=True,
    )
    def _execute_sim_delete(n_clicks, sim_id, page):
        if not n_clicks or not sim_id:
            return dash.no_update, dash.no_update
        n = _delete_simulation(sim_id)
        if n:
            return dbc.Alert("Simulation deleted.", color="success", dismissable=True, duration=4000), page or 0
        return dbc.Alert("Delete failed.", color="danger", dismissable=True), page or 0

    # ── export custom date picker visibility ──────────────────────────────────
    @app.callback(
        Output("db-export-custom-dates-wrap", "style"),
        Input("db-export-timerange", "value"),
        prevent_initial_call=True,
    )
    def _toggle_export_dates(val):
        return {"display": "block"} if val == "custom" else {"display": "none"}

    # ── export select/clear all ───────────────────────────────────────────────
    @app.callback(
        Output("db-export-tables", "value"),
        [Input("db-export-select-all", "n_clicks"),
         Input("db-export-clear-all", "n_clicks")],
        prevent_initial_call=True,
    )
    def _toggle_export_tables(sel, clr):
        triggered = dash.callback_context.triggered[0]["prop_id"]
        if "select-all" in triggered:
            return _TABLE_ORDER_EXPORT
        return []

    # ── export download ───────────────────────────────────────────────────────
    @app.callback(
        [Output("db-export-download", "data"),
         Output("db-export-status", "children")],
        Input("db-export-btn", "n_clicks"),
        [State("db-export-tables", "value"),
         State("db-export-timerange", "value"),
         State("db-export-custom-dates", "start_date"),
         State("db-export-custom-dates", "end_date")],
        prevent_initial_call=True,
    )
    def _do_export(n_clicks, selected_tables, timerange, custom_start, custom_end):
        if not n_clicks:
            return dash.no_update, dash.no_update
        if not selected_tables:
            return dash.no_update, dbc.Alert("Select at least one table.", color="warning")
        try:
            content = _export_db(selected_tables, timerange, custom_start, custom_end)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = "" if timerange == "all" else f"_{timerange}"
            filename = f"trademeup_export{suffix}_{ts}.tmu"
            parsed = json.loads(content)
            total = sum(
                len(parsed.get("data", {}).get(t, []))
                for t in selected_tables
            )
            status = dbc.Alert(
                f"Export ready: {len(selected_tables)} tables, {total} total records.",
                color="success", dismissable=True
            )
            return dcc.send_string(content, filename), status
        except Exception as e:
            return dash.no_update, dbc.Alert(f"Export failed: {e}", color="danger")

    # ── import upload + preview ───────────────────────────────────────────────
    @app.callback(
        [Output("db-import-preview", "children"),
         Output("db-import-parsed", "data"),
         Output("db-import-mode-section", "style")],
        Input("db-import-upload", "contents"),
        State("db-import-upload", "filename"),
        prevent_initial_call=True,
    )
    def _handle_upload(contents, filename):
        if not contents:
            return html.Div(), None, {"display": "none"}
        obj, err = _parse_import_file(contents)
        if err:
            return (
                dbc.Alert(err, color="danger"),
                None,
                {"display": "none"},
            )
        stats = obj.get("export_stats", {})
        history = obj.get("import_history", [])
        preview = dbc.Card([
            dbc.CardHeader(html.H6("File Preview", className="mb-0 fw-semibold")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.P([html.Strong("Exported at: "), obj.get("exported_at", "?")], className="small mb-1"),
                        html.P([html.Strong("Hostname: "), obj.get("hostname", "?")], className="small mb-1"),
                        html.P([html.Strong("App version: "), obj.get("app_version", "?")], className="small mb-1"),
                        html.P([html.Strong("Format version: "), obj.get("format_version", "?")], className="small mb-3"),
                    ]),
                ]),
                html.H6("Records in this file:", className="small fw-semibold mb-2"),
                dbc.Row([
                    dbc.Col(
                        html.Div([
                            html.Span(f"{tbl}: ", className="text-muted small"),
                            html.Span(str(stats.get(tbl, 0)), className="fw-bold small"),
                        ], className="mb-1"),
                        md=4
                    )
                    for tbl in _TABLE_ORDER_EXPORT if tbl in stats
                ]),
                html.Hr() if history else html.Div(),
                html.H6(f"Embedded history ({len(history)} events):", className="small fw-semibold mb-2") if history else html.Div(),
                dbc.Table([
                    html.Thead(html.Tr([html.Th("Date"), html.Th("Type"), html.Th("Host"), html.Th("Notes")])),
                    html.Tbody([
                        html.Tr([
                            html.Td(e.get("timestamp", "")[:19], className="small"),
                            html.Td(e.get("event_type", ""), className="small"),
                            html.Td(e.get("hostname", ""), className="small"),
                            html.Td(e.get("notes", "")[:60], className="small text-muted"),
                        ]) for e in history
                    ])
                ], bordered=False, hover=True, size="sm", responsive=True,
                   className="text-light small") if history else html.P("No embedded history.", className="text-muted small"),
            ])
        ], className="rounded-3 border-0 shadow-sm mb-3")

        return preview, obj, {"display": "block"}

    # ── toggle import custom dates ────────────────────────────────────────────
    @app.callback(
        Output("db-import-custom-dates-wrap", "style"),
        Input("db-import-timerange", "value"),
        prevent_initial_call=True,
    )
    def _toggle_import_dates(val):
        return {"display": "block"} if val == "custom" else {"display": "none"}

    # ── toggle replace warning ────────────────────────────────────────────────
    @app.callback(
        Output("db-import-replace-warning", "style"),
        Input("db-import-mode", "value"),
        prevent_initial_call=True,
    )
    def _toggle_replace_warning(mode):
        return {"display": "block"} if mode == "replace" else {"display": "none"}

    # ── execute import ────────────────────────────────────────────────────────
    @app.callback(
        Output("db-import-result", "children"),
        Input("db-import-confirm-btn", "n_clicks"),
        [State("db-import-parsed", "data"),
         State("db-import-mode", "value"),
         State("db-import-timerange", "value"),
         State("db-import-custom-dates", "start_date"),
         State("db-import-custom-dates", "end_date")],
        prevent_initial_call=True,
    )
    def _do_import(n_clicks, parsed, mode, timerange, custom_start, custom_end):
        if not n_clicks or not parsed:
            return dash.no_update
        result = _execute_import(parsed, mode or "merge", timerange or "all", custom_start, custom_end)
        errors = result.get("errors", [])
        results = result.get("results", {})
        total = sum(results.values())
        rows = [
            html.Tr([html.Td(tbl, className="small"), html.Td(str(cnt), className="small fw-bold")])
            for tbl, cnt in results.items()
        ]
        children = [
            dbc.Alert(
                [html.Strong("Import complete! "), f"{total} records inserted/merged."],
                color="success", dismissable=True
            ),
            dbc.Table([
                html.Thead(html.Tr([html.Th("Table"), html.Th("Inserted")])),
                html.Tbody(rows),
            ], bordered=False, size="sm", responsive=True, className="text-light small mt-2") if rows else html.Div(),
        ]
        if errors:
            children.append(dbc.Alert([
                html.Strong(f"{len(errors)} error(s) (first 5 shown):"),
                html.Ul([html.Li(e, className="small") for e in errors[:5]])
            ], color="warning", dismissable=True))
        return html.Div(children)

    # ── history tab ───────────────────────────────────────────────────────────
    @app.callback(
        Output("db-history-table", "children"),
        [Input("db-tab-history", "value"),
         Input("db-history-refresh", "n_clicks"),
         Input("db-history-clear-status", "children"),
         Input("db-main-tabs", "active_tab")],
        prevent_initial_call=False,
    )
    def _render_history(_tab, _refresh, _clear, active_main):
        events = _load_history()
        if not events:
            return html.P("No import/export history yet.", className="text-muted")
        rows = []
        for e in reversed(events):
            stats = e.get("stats", {})
            stats_str = ", ".join(f"{k}: {v}" for k, v in stats.items() if not k.startswith("_"))
            rows.append(html.Tr([
                html.Td(e.get("timestamp", "")[:19], className="small font-monospace"),
                html.Td(
                    dbc.Badge(e.get("event_type", ""), color="primary" if e.get("event_type") == "export" else "success"),
                ),
                html.Td(e.get("hostname", ""), className="small"),
                html.Td(stats_str[:80], className="small text-muted"),
                html.Td(e.get("notes", "")[:60], className="small text-muted"),
            ]))
        return dbc.Table([
            html.Thead(html.Tr([
                html.Th("Timestamp"), html.Th("Type"), html.Th("Host"),
                html.Th("Stats"), html.Th("Notes"),
            ])),
            html.Tbody(rows),
        ], bordered=False, hover=True, responsive=True, size="sm",
           className="text-light")

    @app.callback(
        Output("db-history-clear-status", "children"),
        Input("db-history-clear-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def _clear_history(n_clicks):
        if not n_clicks:
            return dash.no_update
        _save_history([])
        return dbc.Alert("History cleared.", color="info", dismissable=True, duration=3000)
