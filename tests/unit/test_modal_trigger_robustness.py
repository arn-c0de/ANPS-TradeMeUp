"""
Test for robust modal trigger handling when multiple inputs fire simultaneously
"""
import json
from unittest.mock import Mock, patch

import pytest


class MockCallbackContext:
    """Mock Dash callback_context"""
    def __init__(self, triggered_list):
        self.triggered = triggered_list


def test_modal_opens_when_sim_detail_btn_is_second_trigger():
    """
    Test that sim-detail-btn click opens modal even when it's not the first
    trigger in the list (e.g., another input with value=0 fires first)
    """
    import importlib
    predictions = importlib.import_module('src.gui.tabs.predictions')

    # Simulate multiple triggers where first has value=0 (ignored)
    # and second is the actual sim-detail-btn click
    mock_triggered = [
        {"prop_id": "some-other-input.value", "value": 0},  # Should be skipped
        {"prop_id": '{"type":"sim-detail-btn","index":"test-pred-123"}.n_clicks', "value": 1}
    ]

    # Directly test helper that parses triggered list
    action, pid = predictions._find_first_valid_trigger(mock_triggered)

    assert action == "detail"
    assert pid == "test-pred-123"


def test_modal_handles_pred_detail_btn_as_first_trigger():
    """Test that pred-detail-btn still works as first valid trigger"""
    mock_triggered = [
        {"prop_id": '{"type":"pred-detail-btn","index":"pred-456"}.n_clicks', "value": 1}
    ]

    import importlib
    predictions = importlib.import_module('src.gui.tabs.predictions')

    # Directly test helper for pred-detail-btn
    action, pid = predictions._find_first_valid_trigger(mock_triggered)
    assert action == "detail"
    assert pid == "pred-456"


def test_modal_ignores_all_zero_triggers():
    """Test that modal doesn't open when all triggers have value=0"""
    mock_triggered = [
        {"prop_id": "input1.value", "value": 0},
        {"prop_id": "input2.value", "value": None},
    ]

    import importlib
    predictions = importlib.import_module('src.gui.tabs.predictions')

    # Directly test helper when all triggers are zero/None
    action, pid = predictions._find_first_valid_trigger(mock_triggered)
    assert action is None
    assert pid is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
