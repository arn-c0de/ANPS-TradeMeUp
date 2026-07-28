#!/usr/bin/env python3
"""
PostgreSQL Performance Benchmark Script
========================================

Benchmarks PostgreSQL database performance for TradeMeUp operations.
Tests key query patterns used in the application.

Usage:
    python scripts/benchmark_postgresql.py

Benchmarks:
    1. Dashboard queries (recent predictions, top entities)
    2. Prediction lookups (by ID, by entity, by horizon)
    3. Vector similarity search (embedding nearest neighbors)
    4. JSONB queries (JSON field filtering)
    5. Concurrent access (simulate multiple agents/callbacks)
    6. Complex joins (prediction + entity + simulation data)
"""

import concurrent.futures
import logging
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import func, select, text

from src.models.database import SessionLocal, engine
from src.models.entities import Entity
from src.models.predictions import Prediction
from src.models.processed_news import ProcessedNews
from src.models.trading_simulation import TradingSimulation

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BenchmarkResult:
    """Container for benchmark results."""

    def __init__(self, name: str):
        self.name = name
        self.times: list[float] = []

    def add_time(self, elapsed: float):
        self.times.append(elapsed)

    def get_stats(self) -> dict:
        if not self.times:
            return {"error": "No data"}

        return {
            "mean": statistics.mean(self.times),
            "median": statistics.median(self.times),
            "min": min(self.times),
            "max": max(self.times),
            "stdev": statistics.stdev(self.times) if len(self.times) > 1 else 0,
            "count": len(self.times),
        }

    def print_stats(self):
        stats = self.get_stats()
        if "error" in stats:
            logger.error(f"{self.name}: {stats['error']}")
            return

        logger.info(f"\n{'='*60}")
        logger.info(f"Benchmark: {self.name}")
        logger.info(f"{'='*60}")
        logger.info(f"Runs:      {stats['count']}")
        logger.info(f"Mean:      {stats['mean']*1000:.2f} ms")
        logger.info(f"Median:    {stats['median']*1000:.2f} ms")
        logger.info(f"Min:       {stats['min']*1000:.2f} ms")
        logger.info(f"Max:       {stats['max']*1000:.2f} ms")
        if stats['count'] > 1:
            logger.info(f"StdDev:    {stats['stdev']*1000:.2f} ms")


def benchmark_dashboard_queries(iterations: int = 10) -> BenchmarkResult:
    """Benchmark typical dashboard queries."""
    result = BenchmarkResult("Dashboard Queries (Recent Predictions + Top Entities)")

    for _ in range(iterations):
        with SessionLocal() as session:
            start = time.time()

            # Get recent predictions with entity info
            predictions = session.execute(
                select(Prediction, Entity)
                .join(Entity, Prediction.entity_id == Entity.entity_id)
                .where(Prediction.created_at > datetime.now(UTC) - timedelta(days=7))
                .order_by(Prediction.created_at.desc())
                .limit(50)
            ).all()

            # Get top entities by prediction count
            top_entities = session.execute(
                select(Entity.entity_id, Entity.entity_name, func.count(Prediction.prediction_id))
                .join(Prediction, Entity.entity_id == Prediction.entity_id)
                .group_by(Entity.entity_id, Entity.entity_name)
                .order_by(func.count(Prediction.prediction_id).desc())
                .limit(10)
            ).all()

            elapsed = time.time() - start
            result.add_time(elapsed)

    return result


def benchmark_prediction_lookups(iterations: int = 100) -> BenchmarkResult:
    """Benchmark prediction lookup queries."""
    result = BenchmarkResult("Prediction Lookups (ID + Entity + Horizon)")

    # Get some prediction IDs first
    with SessionLocal() as session:
        sample_predictions = session.execute(
            select(Prediction.prediction_id)
            .limit(iterations)
        ).scalars().all()

    if not sample_predictions:
        logger.warning("No predictions found in database, skipping benchmark")
        return result

    for pred_id in sample_predictions[:iterations]:
        with SessionLocal() as session:
            start = time.time()

            # Lookup prediction by ID with related data
            prediction = session.execute(
                select(Prediction, Entity)
                .join(Entity, Prediction.entity_id == Entity.entity_id)
                .where(Prediction.prediction_id == pred_id)
            ).first()

            elapsed = time.time() - start
            result.add_time(elapsed)

    return result


def benchmark_vector_similarity(iterations: int = 10) -> BenchmarkResult:
    """Benchmark vector similarity search using pgvector."""
    result = BenchmarkResult("Vector Similarity Search (Embedding Nearest Neighbors)")

    # Get a sample embedding first
    with SessionLocal() as session:
        sample = session.execute(
            select(ProcessedNews.embedding)
            .where(ProcessedNews.embedding.isnot(None))
            .limit(1)
        ).scalar()

    if sample is None:
        logger.warning("No embeddings found in database, skipping benchmark")
        return result

    for _ in range(iterations):
        with SessionLocal() as session:
            start = time.time()

            # Find nearest neighbors using cosine distance
            # Note: Requires pgvector extension
            neighbors = session.execute(text("""
                SELECT news_id, embedding <=> :query_embedding AS distance
                FROM processed_news
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> :query_embedding
                LIMIT 10
            """), {"query_embedding": str(sample)}).all()

            elapsed = time.time() - start
            result.add_time(elapsed)

    return result


def benchmark_jsonb_queries(iterations: int = 50) -> BenchmarkResult:
    """Benchmark JSONB field queries using GIN indexes."""
    result = BenchmarkResult("JSONB Queries (JSON Field Filtering)")

    for _ in range(iterations):
        with SessionLocal() as session:
            start = time.time()

            # Query using JSONB containment
            high_confidence = session.execute(text("""
                SELECT prediction_id, entity_id, confidence
                FROM predictions
                WHERE direction_probabilities @> '{"up": 0.6}'::jsonb
                LIMIT 20
            """)).all()

            # Query sentiment JSON
            positive_sentiment = session.execute(text("""
                SELECT news_id, sentiment->>'overall' as overall_sentiment
                FROM processed_news
                WHERE sentiment @> '{"overall": "positive"}'::jsonb
                LIMIT 20
            """)).all()

            elapsed = time.time() - start
            result.add_time(elapsed)

    return result


def benchmark_concurrent_access(num_workers: int = 10, queries_per_worker: int = 10) -> BenchmarkResult:
    """Benchmark concurrent database access (simulates multiple agents/callbacks)."""
    result = BenchmarkResult(f"Concurrent Access ({num_workers} workers, {queries_per_worker} queries each)")

    def worker_task():
        """Single worker performing multiple queries."""
        times = []
        for _ in range(queries_per_worker):
            with SessionLocal() as session:
                start = time.time()

                # Perform a typical query
                predictions = session.execute(
                    select(Prediction)
                    .where(Prediction.created_at > datetime.now(UTC) - timedelta(days=1))
                    .limit(10)
                ).all()

                elapsed = time.time() - start
                times.append(elapsed)
        return times

    # Run workers concurrently
    start_total = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_task) for _ in range(num_workers)]

        for future in concurrent.futures.as_completed(futures):
            worker_times = future.result()
            for t in worker_times:
                result.add_time(t)

    total_time = time.time() - start_total
    logger.info(f"Total concurrent execution time: {total_time:.2f}s")

    return result


def benchmark_complex_joins(iterations: int = 20) -> BenchmarkResult:
    """Benchmark complex joins across multiple tables."""
    result = BenchmarkResult("Complex Joins (Prediction + Entity + Simulation)")

    for _ in range(iterations):
        with SessionLocal() as session:
            start = time.time()

            # Complex query joining predictions, entities, and simulations
            results = session.execute(
                select(
                    Prediction.prediction_id,
                    Prediction.confidence,
                    Entity.entity_name,
                    TradingSimulation.decision,
                    TradingSimulation.actual_return_pct
                )
                .join(Entity, Prediction.entity_id == Entity.entity_id)
                .join(TradingSimulation, Prediction.prediction_id == TradingSimulation.prediction_id)
                .where(Prediction.created_at > datetime.now(UTC) - timedelta(days=30))
                .order_by(Prediction.created_at.desc())
                .limit(100)
            ).all()

            elapsed = time.time() - start
            result.add_time(elapsed)

    return result


def main():
    """Run all benchmarks."""
    logger.info("="*60)
    logger.info("PostgreSQL Performance Benchmark")
    logger.info("="*60)

    # Test connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection OK")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        sys.exit(1)

    # Check for data
    with SessionLocal() as session:
        pred_count = session.execute(select(func.count(Prediction.prediction_id))).scalar()
        entity_count = session.execute(select(func.count(Entity.entity_id))).scalar()
        news_count = session.execute(select(func.count(ProcessedNews.news_id))).scalar()

    logger.info("\nDatabase stats:")
    logger.info(f"  Predictions: {pred_count:,}")
    logger.info(f"  Entities: {entity_count:,}")
    logger.info(f"  Processed News: {news_count:,}")

    if pred_count < 100:
        logger.warning("\n⚠️  Warning: Database has limited data. Benchmarks may not be representative.")

    # Run benchmarks
    benchmarks = []

    logger.info("\n" + "="*60)
    logger.info("Running benchmarks...")
    logger.info("="*60)

    benchmarks.append(benchmark_dashboard_queries(iterations=10))
    benchmarks.append(benchmark_prediction_lookups(iterations=100))
    benchmarks.append(benchmark_jsonb_queries(iterations=50))
    benchmarks.append(benchmark_vector_similarity(iterations=10))
    benchmarks.append(benchmark_complex_joins(iterations=20))
    benchmarks.append(benchmark_concurrent_access(num_workers=10, queries_per_worker=10))

    # Print results
    logger.info("\n" + "="*60)
    logger.info("BENCHMARK RESULTS")
    logger.info("="*60)

    for benchmark in benchmarks:
        benchmark.print_stats()

    # Summary
    logger.info("\n" + "="*60)
    logger.info("SUMMARY")
    logger.info("="*60)

    for benchmark in benchmarks:
        stats = benchmark.get_stats()
        if "error" not in stats:
            logger.info(f"{benchmark.name}: {stats['mean']*1000:.2f} ms (avg)")

    logger.info("\n✅ Benchmarks complete!")


if __name__ == "__main__":
    main()
