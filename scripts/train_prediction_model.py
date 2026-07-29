"""Train the direction classifier used by the prediction agent.

Builds a labelled dataset from historical impact scores, fits an XGBoost
classifier on the realised forward direction, and writes it to the path the
PredictionAgent loads from. Without a model on disk the agent falls back to
its heuristic, which is why every prediction so far has been labelled
``heuristic_v1``.

Usage:
    python scripts/train_prediction_model.py --days 180 --horizon 5
"""
import argparse
import logging
import pickle
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.settings import settings
from src.ml.feature_engineering import FeatureEngineer
from src.models.database import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Label encoding. Must stay in sync with
# PredictionAgent.CLASS_LABEL_ALIASES, which maps the numeric classes_ the
# fitted model exposes back onto direction names.
DIRECTION_TO_CLASS = {'down': 0, 'flat': 1, 'up': 2}

# Below this the fit is not worth trusting; reported rather than enforced so
# a deliberate smoke test can still run with --min-samples.
DEFAULT_MIN_SAMPLES = 200

# Fraction of the (time-ordered) dataset held out for evaluation.
TEST_FRACTION = 0.2


def build_dataset(days: int, horizon: int):
    """Build the labelled training frame."""
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    try:
        engineer = FeatureEngineer(db)
        df = engineer.create_training_dataset(
            start_date=start_date,
            end_date=end_date,
            horizon_days=horizon,
        )
        return df, engineer.get_feature_names()
    finally:
        db.close()


def train(df, feature_names, min_samples: int):
    """Fit the classifier and return (model, metrics)."""
    import numpy as np
    from xgboost import XGBClassifier

    if df.empty:
        raise SystemExit(
            "No labelled samples. Either there are no impact scores in the "
            "window, or none of them are old enough for the horizon to have "
            "elapsed."
        )

    if 'target_direction' not in df.columns:
        raise SystemExit("Dataset has no target_direction column.")

    if len(df) < min_samples:
        logger.warning(
            "Only %d labelled samples (below %d). The model will be fitted, "
            "but treat its accuracy as noise.",
            len(df),
            min_samples,
        )

    # Order by time and split chronologically. A random split would let the
    # model learn from the future, which is the standard way to produce a
    # backtest that cannot be reproduced live.
    df = df.sort_values('timestamp').reset_index(drop=True)

    y = df['target_direction'].map(DIRECTION_TO_CLASS)
    unusable = y.isna().sum()
    if unusable:
        logger.warning("Dropping %d rows with an unrecognised label", unusable)
        keep = y.notna()
        df, y = df[keep], y[keep]

    X = df[feature_names].astype(float).fillna(0.0)
    y = y.astype(int)

    distribution = y.value_counts().to_dict()
    logger.info(
        "Label distribution: %s",
        {name: distribution.get(code, 0) for name, code in DIRECTION_TO_CLASS.items()},
    )
    if y.nunique() < 2:
        raise SystemExit(
            "Every sample carries the same label - nothing to learn. Widen the "
            "window or lower the impact threshold."
        )

    split = max(1, int(len(df) * (1 - TEST_FRACTION)))
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    logger.info(
        "Training on %d samples, evaluating on %d (chronological split)",
        len(X_train),
        len(X_test),
    )

    model = XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective='multi:softprob',
        num_class=len(DIRECTION_TO_CLASS),
        eval_metric='mlogloss',
        random_state=42,
    )
    model.fit(X_train, y_train)

    metrics = {'train_samples': len(X_train), 'test_samples': len(X_test)}

    if len(X_test):
        predicted = model.predict(X_test)
        accuracy = float((predicted == y_test.to_numpy()).mean())
        # Always-predict-the-most-common-class baseline. An accuracy at or
        # below this means the model has learned nothing useful.
        baseline = float(y_test.value_counts(normalize=True).max())
        metrics['accuracy'] = accuracy
        metrics['majority_baseline'] = baseline
        logger.info("Hold-out accuracy: %.3f (majority baseline %.3f)", accuracy, baseline)
        if accuracy <= baseline:
            logger.warning(
                "The model does not beat always predicting the majority class. "
                "Do not put this into production."
            )

    importances = sorted(
        zip(feature_names, model.feature_importances_),
        key=lambda pair: pair[1],
        reverse=True,
    )
    logger.info("Top features: %s", [f"{n}={v:.3f}" for n, v in importances[:5]])

    return model, metrics


def save_model(model, model_version: str) -> Path:
    """Write the fitted model where PredictionAgent looks for it."""
    model_dir = Path(settings.model_path)
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / f"{model_version}.pkl"

    with open(model_path, 'wb') as f:
        pickle.dump(model, f)

    logger.info("Saved model to %s", model_path)
    return model_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=180,
                        help='How far back to pull impact scores (default: 180)')
    parser.add_argument('--horizon', type=int, default=5,
                        help='Forward return horizon in trading days (default: 5)')
    parser.add_argument('--model-version', default='xgboost_v1.0',
                        help='Filename stem under MODEL_PATH (default: xgboost_v1.0)')
    parser.add_argument('--min-samples', type=int, default=DEFAULT_MIN_SAMPLES,
                        help=f'Warn below this many samples (default: {DEFAULT_MIN_SAMPLES})')
    parser.add_argument('--dry-run', action='store_true',
                        help='Train and report, but do not write the model')
    args = parser.parse_args()

    logger.info("Building dataset (%d days, %dd horizon)", args.days, args.horizon)
    df, feature_names = build_dataset(args.days, args.horizon)

    model, metrics = train(df, feature_names, args.min_samples)

    if args.dry_run:
        logger.info("Dry run - model not saved. Metrics: %s", metrics)
        return

    save_model(model, args.model_version)
    logger.info(
        "Done. PredictionAgent will now load this model and label its output "
        "'%s' instead of 'heuristic_v1'. Metrics: %s",
        args.model_version,
        metrics,
    )


if __name__ == "__main__":
    main()
