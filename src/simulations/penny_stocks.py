"""Shared penny-stock classification for the simulation modules.

The cost engine and the exit-strategy engine both need to know whether a price
belongs to a penny stock, and both read the same ``penny_stock_handling``
config block. Keeping one implementation prevents them from disagreeing about
which prices count as tradeable.
"""

# Below this price a quote is treated as noise rather than a tradeable level.
# Read from config["penny_stock_handling"]["min_valid_price_usd"]; the constant
# is only the fallback when that key is absent.
DEFAULT_MIN_VALID_PRICE_USD = 0.00001
DEFAULT_PENNY_THRESHOLD_USD = 1.0
DEFAULT_ULTRA_PENNY_THRESHOLD_USD = 0.001


def penny_config(config: dict) -> dict:
    """Return the penny-stock config block."""
    return config.get("penny_stock_handling", {}) or {}


def min_valid_price(config: dict) -> float:
    """Lowest price still considered a usable quote."""
    return penny_config(config).get("min_valid_price_usd", DEFAULT_MIN_VALID_PRICE_USD)


def penny_handling_enabled(config: dict) -> bool:
    """Whether penny-stock special handling is switched on."""
    return bool(penny_config(config).get("enabled", False))


def is_penny_stock(config: dict, price: float) -> bool:
    """True for a valid price at or below the penny threshold (default $1.00)."""
    if not penny_handling_enabled(config):
        return False
    threshold = penny_config(config).get("price_threshold_usd", DEFAULT_PENNY_THRESHOLD_USD)
    return min_valid_price(config) < price <= threshold


def is_ultra_penny_stock(config: dict, price: float) -> bool:
    """True for a valid price below the ultra-penny threshold (default $0.001)."""
    if not penny_handling_enabled(config):
        return False
    ultra = penny_config(config).get(
        "ultra_penny_threshold_usd", DEFAULT_ULTRA_PENNY_THRESHOLD_USD
    )
    return min_valid_price(config) < price < ultra
