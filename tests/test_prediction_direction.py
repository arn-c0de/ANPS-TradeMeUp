"""Directional sanity of the prediction heuristic.

The heuristic used to add ``impact_score`` to the bullish side, which made
impact act as a bullish signal rather than a magnitude. The result was that no
combination of inputs could produce a negative expected return, and the higher
the impact the harder it became to call a fall - exactly backwards for the
articles that matter most. These tests pin the direction down.
"""
import numpy as np
import pytest

from src.agents.prediction_agent import PredictionAgent


@pytest.fixture(scope="module")
def agent():
    # No trained model on disk, so this exercises the heuristic path - which
    # is the path that actually runs in production until a model is trained.
    return PredictionAgent()


def features(impact=0.5, sentiment=0.0, surprise_direction=0, surprise_magnitude=0.0):
    return {
        'impact_score': impact,
        'sentiment_overall': sentiment,
        'surprise_direction': surprise_direction,
        'surprise_magnitude': surprise_magnitude,
    }


def test_negative_sentiment_predicts_a_fall(agent):
    result = agent._predict_with_heuristics(
        features(impact=0.9, sentiment=-0.8), '5d'
    )

    probabilities = result['direction_probabilities']
    assert probabilities['down'] > probabilities['up']
    assert result['expected_return']['mean'] < 0


def test_positive_sentiment_predicts_a_rise(agent):
    result = agent._predict_with_heuristics(
        features(impact=0.9, sentiment=0.8), '5d'
    )

    probabilities = result['direction_probabilities']
    assert probabilities['up'] > probabilities['down']
    assert result['expected_return']['mean'] > 0


def test_impact_sets_magnitude_not_direction(agent):
    """Raising impact must not move a bearish call towards bullish."""
    low = agent._predict_with_heuristics(features(impact=0.4, sentiment=-0.6), '5d')
    high = agent._predict_with_heuristics(features(impact=1.0, sentiment=-0.6), '5d')

    # Still bearish at both ends...
    assert low['expected_return']['mean'] < 0
    assert high['expected_return']['mean'] < 0
    # ...and more so where the news matters more.
    assert high['expected_return']['mean'] < low['expected_return']['mean']


def test_no_directional_signal_stays_balanced(agent):
    result = agent._predict_with_heuristics(features(impact=0.9, sentiment=0.0), '5d')

    probabilities = result['direction_probabilities']
    assert probabilities['up'] == pytest.approx(probabilities['down'], abs=1e-9)
    assert result['expected_return']['mean'] == pytest.approx(0.0, abs=1e-9)


def test_surprise_direction_breaks_a_sentiment_tie(agent):
    downside = agent._predict_with_heuristics(
        features(impact=0.8, sentiment=0.0, surprise_direction=-1, surprise_magnitude=1.0),
        '5d',
    )
    upside = agent._predict_with_heuristics(
        features(impact=0.8, sentiment=0.0, surprise_direction=1, surprise_magnitude=1.0),
        '5d',
    )

    assert downside['expected_return']['mean'] < 0
    assert upside['expected_return']['mean'] > 0


def test_sign_of_expected_return_tracks_sentiment_across_the_grid(agent):
    """The defect was global, so assert the property globally."""
    for impact in np.linspace(0.4, 1.0, 13):
        for sentiment in np.linspace(-1.0, 1.0, 21):
            result = agent._predict_with_heuristics(
                features(impact=impact, sentiment=sentiment), '5d'
            )
            mean = result['expected_return']['mean']

            if sentiment < -0.05:
                assert mean < 0, f"impact={impact:.2f} sentiment={sentiment:.2f}"
            elif sentiment > 0.05:
                assert mean > 0, f"impact={impact:.2f} sentiment={sentiment:.2f}"


def test_probabilities_stay_a_distribution(agent):
    for impact in (0.0, 0.4, 1.0):
        for sentiment in (-1.0, -0.3, 0.0, 0.3, 1.0):
            probabilities = agent._predict_with_heuristics(
                features(impact=impact, sentiment=sentiment), '5d'
            )['direction_probabilities']

            assert sum(probabilities.values()) == pytest.approx(1.0)
            assert all(0.0 <= p <= 1.0 for p in probabilities.values())


def test_undecided_model_implies_no_move(agent):
    """A model with no edge must not imply a positive return."""
    agent_with_model = PredictionAgent()

    class _UndecidedModel:
        classes_ = ['down', 'flat', 'up']

        def predict_proba(self, X):
            return np.array([[1 / 3, 1 / 3, 1 / 3]])

    agent_with_model.model = _UndecidedModel()

    from src.ml.feature_engineering import FeatureEngineer

    result = agent_with_model._predict_with_model(
        features(impact=0.8, sentiment=0.0),
        FeatureEngineer(None),
        '5d',
    )

    assert result['source'] == 'model'
    assert result['expected_return']['mean'] == pytest.approx(0.0, abs=1e-9)
