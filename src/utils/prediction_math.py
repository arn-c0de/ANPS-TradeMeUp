"""Shared interpretation of the numbers stored on a Prediction row.

The prediction tables store direction probabilities and expected returns as
free-form JSON, so reading them takes a little care. Keeping that logic here
means the simulator and the performance service cannot drift apart on what a
given prediction actually predicts.
"""
import logging

from src.utils.json_helpers import ensure_dict

logger = logging.getLogger(__name__)

# Expected returns are stored either as decimals (0.02 == 2%) or as percentages
# (2.0 == 2%). Anything within +/-50% is read as a decimal; real predictions
# rarely exceed that, while decimal-format values cluster well below it.
DECIMAL_FORMAT_LIMIT = 0.50

# A "flat" prediction counts as correct when the realised move stays inside
# this band. Percent, matching how actual_return is stored. Several agents
# used a bare 0.01 here, which reads as 0.01% and made "flat" effectively
# impossible to get right.
FLAT_RETURN_TOLERANCE_PCT = 1.0


def get_predicted_direction(prediction, default: str = "flat") -> str:
    """Return the most likely direction ('up' / 'down' / 'flat').

    Args:
        prediction: Prediction object with a ``direction_probabilities`` mapping.
        default: Value to return when no usable probabilities are stored.
    """
    probabilities = ensure_dict(getattr(prediction, "direction_probabilities", None), {})

    # Ignore entries without a comparable probability: max() would raise on a
    # None value, and a stored null carries no information anyway.
    usable = {
        key: value for key, value in probabilities.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    if not usable:
        return default

    return max(usable, key=usable.get)


def get_expected_return_pct(prediction) -> float:
    """Return the predicted return as a percentage (2.0 means +2%).

    Honours an explicit ``is_percentage`` flag on the stored payload and falls
    back to :data:`DECIMAL_FORMAT_LIMIT` as a format heuristic otherwise.
    """
    expected_return = ensure_dict(getattr(prediction, "expected_return", None), {})

    mean_value = expected_return.get("mean")
    if mean_value is None:
        return 0.0

    try:
        mean_value = float(mean_value)
    except (TypeError, ValueError):
        logger.warning("Non-numeric expected_return.mean: %r", mean_value)
        return 0.0

    is_percentage = expected_return.get("is_percentage")
    if is_percentage is True:
        return mean_value
    if is_percentage is False:
        return mean_value * 100.0

    if abs(mean_value) <= DECIMAL_FORMAT_LIMIT:
        return mean_value * 100.0

    if abs(mean_value) > 100:
        logger.warning(
            "Unusually large expected return %.4f for prediction %s - treating as percentage",
            mean_value,
            getattr(prediction, "prediction_id", "<unknown>"),
        )
    return mean_value
