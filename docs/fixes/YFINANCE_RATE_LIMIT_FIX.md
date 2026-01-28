# yFinance Rate Limiting Fix

**Date:** 2026-01-28  
**Issue:** "Invalid/too-small price" warnings during `resimulate_all.py` causing 0.0 prices  
**Root Cause:** yFinance API rate limiting ("Too Many Requests") when running parallel simulations

## Problem

When running `resimulate_all.py` with 1303 predictions using 8 parallel workers:
```
WARNING - Invalid/too-small price for VGIT (0.0) - clearing existing simulation values
WARNING - Invalid/too-small price for MFC (0.0) - clearing existing simulation values
```

Testing showed the real error:
```python
yfinance.exceptions.YFinanceException: Too Many Requests. Rate limited. Try after a while.
```

The parallel processing was hammering yfinance too quickly → rate limit → empty responses → 0.0 prices.

## Solution

### 1. Added Rate Limiting to MarketDataProvider

**File:** `src/services/market_data.py`

Added intelligent rate limiting:
```python
def __init__(self):
    # Rate limiting to avoid yfinance "Too Many Requests" errors
    self._last_request_time = {}
    self._min_request_interval = 0.1  # 100ms between requests per ticker
    self._global_last_request = time.time()
    self._global_min_interval = 0.05  # 50ms between any requests

def _rate_limit(self, symbol: str = None):
    """Apply rate limiting to avoid yfinance throttling"""
    # Global rate limit (all requests)
    # Per-ticker rate limit (if symbol provided)
```

Applied rate limiting in:
- ✅ `get_live_price()` - Check cache first, then apply rate limit before API call
- ✅ `get_historical_data()` - Apply rate limit before fetching historical data

### 2. Enhanced Error Handling

Added specific rate limit error detection:
```python
except Exception as e:
    if "Too Many Requests" in str(e) or "Rate limit" in str(e):
        logger.warning(f"⚠️ Rate limited on {symbol}, using cached/saved data if available")
        return self._get_cached_data(symbol)
```

### 3. Reduced Default Parallel Workers

**File:** `scripts/resimulate_all.py`

Changed default from 8 → **4 workers** to reduce API pressure:
```python
def resimulate_all(db: Session, limit: int = None, workers: int = 4) -> dict:
    """default: 4 to avoid yfinance rate limits"""
```

## Impact

- ✅ Prevents "Too Many Requests" errors during bulk resimulation
- ✅ Falls back to cached data when rate-limited
- ✅ Still uses parallel processing (4 workers) for speed
- ✅ User can override with `--workers 1` for sequential processing if needed

## Usage

```bash
# Default (4 workers with rate limiting)
python scripts/resimulate_all.py

# Sequential processing (no rate limit issues)
python scripts/resimulate_all.py --workers 1

# More aggressive (may hit rate limits occasionally)
python scripts/resimulate_all.py --workers 8
```

## Technical Details

**Rate Limits Applied:**
- Global: 50ms between ANY requests (20 req/sec max)
- Per-ticker: 100ms between requests to same ticker (10 req/sec per ticker)

**Cache Strategy:**
- Check cache before making API calls
- Fall back to cached data on rate limit errors
- Cache TTL: 1 hour

**Error Hierarchy:**
1. Try live API call (with rate limiting)
2. If rate limited → use cache
3. If cache expired → skip (better than crashing)

## Related Files

- `src/services/market_data.py` - Rate limiting implementation
- `scripts/resimulate_all.py` - Reduced default workers
- `src/simulations/trading_simulator.py` - Handles 0.0 prices gracefully

## Testing

Verified with:
```bash
python test_tickers.py
# Before: "Too Many Requests" errors
# After: Rate-limited requests succeed
```
