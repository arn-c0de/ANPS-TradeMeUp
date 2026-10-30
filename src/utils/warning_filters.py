"""Silence noisy third-party warnings in one place.

yfinance and pandas emit FutureWarning/DeprecationWarning chatter at call time
(not at import time), so the filters only need to be installed before the first
download, not before the imports.
"""
import logging
import warnings


def silence_third_party_warnings() -> None:
    """Install the warning filters and log levels used across the app. Idempotent."""
    warnings.filterwarnings('ignore', category=FutureWarning, module='yfinance')
    warnings.filterwarnings('ignore', category=DeprecationWarning, module='yfinance')
    warnings.filterwarnings('ignore', message='.*Timestamp.utcnow.*')
    try:
        from pandas.errors import Pandas4Warning
        warnings.filterwarnings('ignore', category=Pandas4Warning)
    except ImportError:
        pass
    logging.getLogger('yfinance').setLevel(logging.ERROR)
