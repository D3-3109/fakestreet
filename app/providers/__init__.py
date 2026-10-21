"""Market data provider adapters.

When `TRADING_GAME_OFFLINE=1` deterministic offline stand-ins are exported
instead of the real HTTP providers. Everything downstream (`market.py`,
`registry.py`) imports these names and is unaware of the switch.

This exists so CI can test trade settlement, liquidation math, season rollover
and so on without depending on Yahoo or CoinGecko staying reachable from a
datacenter IP. Production runs never set the variable and get the live feeds.
"""
import os

_offline = os.environ.get("TRADING_GAME_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}

if _offline:
    from . import offline as _stub

    # Each name must expose the same callables as the real module: get_quotes,
    # search, get_history, and (for fiat) supported.
    stocks = _stub.stocks
    crypto = _stub.crypto
    fiat = _stub.fiat
else:
    from . import crypto, fiat, stocks

__all__ = ["crypto", "fiat", "stocks"]
