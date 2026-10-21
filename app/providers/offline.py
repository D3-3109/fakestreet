"""Deterministic stand-ins for the market data providers.

Purpose: CI must be able to test *our* code without depending on Yahoo,
CoinGecko, or the ECB. Those endpoints rate-limit, block datacenter IPs, and go
down, and none of that has anything to do with whether a trade settles or a
position liquidates correctly.

Enable with `TRADING_GAME_OFFLINE=1`. Prices are derived from the symbol name,
so they are stable across runs and a chart of them is smooth rather than noise.
Both the quotes and the search surfaces mirror the real modules exactly, so
`market.py` and `registry.py` run unmodified.
"""
from __future__ import annotations

import builtins
import hashlib
import time
from typing import Dict, List, Tuple

# Ranges match the real providers so callers keep the same behaviour.
HISTORY_POINTS = {"1d": 24, "5d": 60, "1mo": 30, "6mo": 180, "1y": 365}


def _seed(symbol: str) -> int:
    return int(hashlib.sha256(symbol.encode("utf-8")).hexdigest()[:8], 16)


def _base_price(symbol: str, klass: str) -> float:
    """A plausible, stable starting price per symbol.

    Ranges are chosen so the smoke test's sanity checks hold: BTC above 1000,
    AAPL between 10 and 10000, fiat well below 2.
    """
    seed = _seed(symbol)
    if klass == "crypto":
        if symbol == "BTC":
            return 65000.0
        if symbol == "ETH":
            return 3200.0
        return 10.0 + (seed % 5000) / 10.0
    if klass == "fiat":
        # USD per unit of the foreign currency.
        return 0.5 + (seed % 100) / 100.0
    if symbol == "AAPL":
        return 190.0
    return 20.0 + (seed % 80000) / 100.0


def _drift(symbol: str, index: int) -> float:
    """A deterministic pseudo-random walk, ±1.5% per step."""
    h = hashlib.sha256(f"{symbol}:{index}".encode("utf-8")).hexdigest()
    delta = (int(h[:8], 16) % 3001 - 1500) / 100000.0
    return 1.0 + delta


def _price_at(symbol: str, klass: str, steps_ago: int) -> float:
    price = _base_price(symbol, klass)
    # Walk backwards from the current step so "now" is always the base price.
    for i in range(steps_ago):
        price = price / _drift(symbol, i)
    return round(price, 6)


def _all_assets() -> List[dict]:
    """Built-ins plus any custom assets, tolerating a database that is not ready.

    The stub is used both inside the running app (database present) and by the
    CI contract check in a bare script (no database), so a missing table must
    not turn into a crash.
    """
    import config

    try:
        from app import registry

        return list(registry.all_assets())
    except Exception:
        return [dict(asset) for asset in config.ASSETS]


def _resolve(symbol: str) -> Tuple[str, str]:
    """Map any identifier the market layer might pass to (display_symbol, klass).

    The caller is not always a display symbol: crypto arrives as a CoinGecko id
    (`bitcoin`), stocks and fiat arrive as the symbol itself. Resolving through
    the registry handles both without the caller having to care.
    """
    wanted = str(symbol or "").strip()
    for asset in _all_assets():
        if asset["symbol"].upper() == wanted.upper() or asset["provider_id"] == wanted:
            return asset["symbol"].upper(), asset["asset_class"]
    return wanted.upper(), "stock"


def _klass_of(symbol: str) -> str:
    return _resolve(symbol)[1]


def get_quotes(symbols: List[str]) -> Dict[str, Tuple[float, float]]:
    """Current price plus previous close, matching the real provider shape.

    Keys are echoed back exactly as received, because the caller indexes the
    result by whatever id it passed in (a display symbol or a CoinGecko id).
    """
    out: Dict[str, Tuple[float, float]] = {}
    for key in symbols:
        display, klass = _resolve(key)
        price = _base_price(display, klass)
        prev = _price_at(display, klass, 1)
        out[key] = (round(price, 6), round(prev, 6))
    return out


def _search(symbols: List[str], query: str, limit: int) -> List[dict]:
    query = (query or "").strip().upper()
    if not query:
        return []
    by_symbol = {a["symbol"].upper(): a for a in _all_assets()}
    results = []
    for symbol in symbols:
        if query not in symbol.upper():
            continue
        asset = by_symbol.get(symbol.upper(), {})
        results.append({
            "symbol": symbol,
            "name": asset.get("name", symbol),
            "provider_id": asset.get("provider_id", symbol),
        })
        if len(results) >= limit:
            break
    return results


def get_history(symbol: str, range_: str = "1mo") -> List[Tuple[int, float]]:
    """Evenly spaced points ending now, so charts and reports have real data.

    The parameter is named `range_` because the real providers also call it
    `range`, and shadowing the builtin breaks the loop below.
    """
    display, klass = _resolve(symbol)
    count = HISTORY_POINTS.get(range_, HISTORY_POINTS["1mo"])
    step = 3600 if range_ in ("1d", "5d") else 86400
    now = int(time.time())
    points: List[Tuple[int, float]] = []
    for i in builtins.range(count - 1, -1, -1):
        points.append((now - i * step, _price_at(display, klass, i)))
    return points


# --- per-class modules, mirroring the real APIs ------------------------------

class _Stocks:
    @staticmethod
    def get_quotes(symbols: List[str]) -> Dict[str, Tuple[float, float]]:
        return get_quotes([s for s in symbols if _klass_of(s) == "stock"])

    @staticmethod
    def search(query: str, limit: int = 10) -> List[dict]:
        symbols = [a["symbol"] for a in _all_assets() if a["asset_class"] == "stock"]
        return _search(symbols, query, limit)

    @staticmethod
    def get_history(ticker: str, range: str = "1mo") -> List[Tuple[int, float]]:
        return get_history(ticker, range)


class _Crypto:
    @staticmethod
    def get_quotes(coin_ids: List[str]) -> Dict[str, Tuple[float, float]]:
        # Keys stay as the CoinGecko ids the caller passed; `_resolve` inside
        # get_quotes maps them to display symbols for pricing.
        return get_quotes(list(coin_ids))

    @staticmethod
    def search(query: str, limit: int = 10) -> List[dict]:
        assets = [a for a in _all_assets() if a["asset_class"] == "crypto"]
        query = (query or "").strip().upper()
        if not query:
            return []
        results = []
        for asset in assets:
            if query in asset["symbol"].upper() or query in asset["name"].upper():
                results.append({
                    "symbol": asset["symbol"],
                    "name": asset["name"],
                    "provider_id": asset["provider_id"],
                })
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def get_history(coin_id: str, range: str = "1mo") -> List[Tuple[int, float]]:
        return get_history(coin_id, range)


class _Fiat:
    @staticmethod
    def get_quotes(symbols: List[str]) -> Dict[str, Tuple[float, float]]:
        return get_quotes([s for s in symbols if _klass_of(s) == "fiat"])

    @staticmethod
    def supported() -> Dict[str, str]:
        return {
            a["symbol"]: a["name"]
            for a in _all_assets()
            if a["asset_class"] == "fiat"
        }

    @staticmethod
    def search(query: str, limit: int = 10) -> List[dict]:
        query = (query or "").strip().lower()
        if not query:
            return []
        results = []
        for asset in _all_assets():
            if asset["asset_class"] != "fiat":
                continue
            if query in asset["symbol"].lower() or query in asset["name"].lower():
                results.append({
                    "symbol": asset["symbol"],
                    "name": asset["name"],
                    "provider_id": asset["provider_id"],
                })
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def get_history(symbol: str, range: str = "1mo") -> List[Tuple[int, float]]:
        return get_history(symbol, range)


stocks = _Stocks
crypto = _Crypto
fiat = _Fiat
