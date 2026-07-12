"""Supported crypto underlyings for futures, options, and indicators."""

SUPPORTED_ASSETS = frozenset({"BTC", "ETH"})

FUTURES_SYMBOL = {
    "BTC": "BTCUSD",
    "ETH": "ETHUSD",
}

OPTION_UNDERLYING = {
    "BTC": "BTC",
    "ETH": "ETH",
}


EXIT_IF_BUFFER_BY_ASSET = {
    "BTC": 200.0,
    "ETH": 8.0,
}

# Position P&L % numerator: (pnl × mult) / (entry × lots)
POSITION_PNL_PCT_NUMERATOR = {
    "BTC": 100.0 * 1000.0,
    "ETH": 100.0 * 100.0,
}

# Strategy combined P&L % numerator: (pnl × mult) / (combined_premium × size)
STRATEGY_PNL_PCT_NUMERATOR = {
    "BTC": 1000.0 * 100.0,
    "ETH": 100.0 * 100.0,
}


def normalize_asset(asset: str | None) -> str:
    key = (asset or "BTC").upper()
    if key not in SUPPORTED_ASSETS:
        raise ValueError(f"Unsupported asset: {asset}")
    return key


def futures_symbol(asset: str | None) -> str:
    return FUTURES_SYMBOL[normalize_asset(asset)]


def option_underlying(asset: str | None) -> str:
    return OPTION_UNDERLYING[normalize_asset(asset)]


def exit_if_buffer(asset: str | None) -> float:
    return EXIT_IF_BUFFER_BY_ASSET[normalize_asset(asset)]


def position_pnl_pct_numerator(asset: str | None) -> float:
    return POSITION_PNL_PCT_NUMERATOR[normalize_asset(asset)]


def strategy_pnl_pct_numerator(asset: str | None) -> float:
    return STRATEGY_PNL_PCT_NUMERATOR[normalize_asset(asset)]


def asset_from_symbol(symbol: str | None) -> str:
    if not symbol:
        return "BTC"
    upper = symbol.upper()
    if "-ETH-" in upper or upper.startswith("ETH"):
        return "ETH"
    return "BTC"
