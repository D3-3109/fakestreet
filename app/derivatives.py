"""Leveraged positions: perpetuals, dated futures, and short selling.

Design notes, because the arithmetic here is what keeps the game honest.

Isolated margin
---------------
Every position locks `margin` in cash and nothing else. Notional is
`size * entry_price * multiplier`, and `leverage = notional / margin`. Because
margin is all that is at risk, liquidation can always close the row without
touching the rest of the player's account, so equity can never go negative and
no player can owe the house money.

Profit and loss
---------------
Long:   pl = (price - entry) * size * multiplier
Short:  pl = (entry - price) * size * multiplier
Funding is added on top (credited when positive, charged when negative).
Equity of a position is `margin + pl + funding_paid`.

Liquidation
-----------
`MAINTENANCE_MARGIN_PCT` is the share of margin that must survive. Once
equity falls to that fraction of margin (or below), the position is closed at
the current price for whatever is left. With a 50% threshold a position is
liquidated after losing half its margin, which is well before equity reaches
zero. The close is still clamped so the player never loses more than the margin.

Funding for perpetuals
----------------------
The rate is derived from how lopsided open interest is inside this game rather
than invented: longs pay shorts when long notional exceeds short notional, and
the reverse when shorts dominate. That makes crowding expensive for whoever is
on the heavy side, which is the behaviour real perp funding produces.
"""
from __future__ import annotations

import math
import sqlite3
import threading
import time
from typing import Any, Iterable

import config
from app import activity
from app import i18n
from app import registry
from app.db import get_conn
from app.market import market

KINDS = ("perp", "future")
DIRECTIONS = ("long", "short")

_lock = threading.Lock()


class PositionError(i18n.ValidationError):
    """A player-facing rejection while opening, closing, or managing a position."""


def _now() -> int:
    return int(time.time())


def _money(value: float) -> float:
    return round(float(value), 6)


def _pct(value: float) -> float:
    return round(float(value), 4)


def multiplier_for(symbol: str) -> float:
    asset = registry.get_asset(symbol)
    klass = (asset or {}).get("asset_class", "stock")
    return float(config.CONTRACT_MULTIPLIERS.get(klass, 1.0))


def notional_of(size: float, price: float, multiplier: float) -> float:
    return float(size) * float(price) * float(multiplier)


def pl_of(direction: str, entry: float, price: float, size: float, multiplier: float) -> float:
    """Unrealised profit/loss in USD, funding excluded."""
    delta = (price - entry) if direction == "long" else (entry - price)
    return float(delta) * float(size) * float(multiplier)


def liquidation_price(direction: str, entry: float, size: float, multiplier: float,
                      margin: float, maintenance_pct: float) -> float | None:
    """Price at which equity drops to the maintenance floor.

    With the default 0% floor this is the price where the whole margin is gone,
    i.e. a move of 1/leverage against the position. Returns None when the
    position cannot be liquidated by price alone, so callers skip it.
    """
    if size <= 0 or multiplier <= 0:
        return None
    per_unit = float(size) * float(multiplier)
    # equity = margin + pl = maintenance_pct% * margin  ->  pl = -(1-k)*margin
    loss_at_stop = margin * (1.0 - maintenance_pct / 100.0)
    if loss_at_stop <= 0:
        return None
    distance = loss_at_stop / per_unit
    price = entry - distance if direction == "long" else entry + distance
    # A 0% floor puts the theoretical stop exactly at the entry for an infinitely
    # leveraged book; keep a hair of room so a position is not stillborn.
    return price if price > 0 else 0.0


def required_margin(size: float, price: float, multiplier: float, leverage: float) -> float:
    return notional_of(size, price, multiplier) / float(leverage)


def max_leverage() -> float:
    """Highest leverage the game allows.

    `MAX_LEVERAGE = 0` means uncapped, in which case the real ceiling comes from
    the minimum margin: a position can never post less than MIN_POSITION_MARGIN,
    so the multiple tops out where margin would fall below it.
    """
    if config.MAX_LEVERAGE and config.MAX_LEVERAGE > 0:
        return float(config.MAX_LEVERAGE)
    return math.inf


def leverage_ceiling(price: float, size: float, multiplier: float) -> float:
    """Largest leverage that still leaves at least MIN_POSITION_MARGIN posted."""
    notional = notional_of(size, price, multiplier)
    if notional <= 0:
        return 0.0
    floor = max(config.MIN_POSITION_MARGIN, 1e-9)
    return notional / floor


def _validate_open(symbol: str, kind: str, direction: str, size: float, leverage: float,
                   lang: str) -> tuple[dict, float, float]:
    if registry.get_asset(symbol) is None:
        raise PositionError("deriv.unknownSymbol", lang, symbol=symbol)
    if kind not in KINDS:
        raise PositionError("deriv.badKind", lang)
    if direction not in DIRECTIONS:
        raise PositionError("deriv.badDirection", lang)
    if not isinstance(size, (int, float)) or not math.isfinite(float(size)) or float(size) <= 0:
        raise PositionError("deriv.badSize", lang)
    if not isinstance(leverage, (int, float)) or not math.isfinite(float(leverage)):
        raise PositionError("deriv.badLeverage", lang)
    lev = float(leverage)
    if lev < 1:
        raise PositionError("deriv.badLeverage", lang)
    ceiling = max_leverage()
    if math.isfinite(ceiling) and lev > ceiling:
        raise PositionError("deriv.badLeverage", lang, max=ceiling)
    return registry.get_asset(symbol), float(size), lev


def open_position(*, player_id: int, symbol: str, kind: str, direction: str, size: float,
                  leverage: float, lang: str = i18n.DEFAULT) -> dict[str, Any]:
    symbol = str(symbol or "").strip().upper()
    kind = str(kind or "").strip().lower()
    direction = str(direction or "").strip().lower()
    asset, size, lev = _validate_open(symbol, kind, direction, size, leverage, lang)

    price = float(market.get_price(symbol))
    if not math.isfinite(price) or price <= 0:
        raise PositionError("deriv.noPrice", lang, symbol=symbol)

    multiplier = multiplier_for(symbol)
    notional = notional_of(size, price, multiplier)
    margin = required_margin(size, price, multiplier, lev)
    if margin <= 0:
        raise PositionError("deriv.badSize", lang)
    if margin < config.MIN_POSITION_MARGIN:
        # Uncapped leverage still needs a floor or the margin becomes float dust
        # and every position liquidates on the first tick.
        raise PositionError(
            "deriv.marginTooSmall", lang,
            min=f"{config.MIN_POSITION_MARGIN:,.2f}",
            margin=f"{margin:,.4f}",
        )

    now = _now()
    expires_at = None
    if kind == "future":
        expires_at = now + int(config.FUTURE_DURATION_SECONDS)

    with _lock:
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT cash FROM players WHERE id = ?", (player_id,)).fetchone()
            if row is None:
                raise PositionError("auth.notSignedIn", lang)
            cash = float(row["cash"])
            if cash < margin:
                conn.rollback()
                raise PositionError(
                    "deriv.insufficientMargin", lang,
                    needed=f"{margin:,.2f}", cash=f"{cash:,.2f}",
                )

            cur = conn.execute(
                "INSERT INTO positions (player_id, symbol, kind, direction, size, multiplier, "
                "leverage, margin, entry_price, funding_paid, opened_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
                (player_id, symbol, kind, direction, size, multiplier, lev, margin,
                 price, now, expires_at),
            )
            position_id = int(cur.lastrowid)
            conn.execute("UPDATE players SET cash = ? WHERE id = ?", (cash - margin, player_id))
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            conn.close()

    activity.log(
        "position_open",
        player_id=player_id,
        symbol=symbol,
        amount=_money(margin),
        detail={
            "kind": kind,
            "direction": direction,
            "size": _money(size),
            "leverage": lev,
            "entry_price": _money(price),
            "notional": _money(notional),
        },
        ts=now,
    )
    return get_position(position_id) or {}


def get_position(position_id: int) -> dict[str, Any] | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM positions WHERE id = ?", (position_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    data = dict(row)
    _decorate(data, market.get_prices([data["symbol"]]).get(data["symbol"]))
    return data


def _decorate(pos: dict, price: float | None) -> None:
    """Attach live valuation fields to a raw positions row, in place."""
    entry = float(pos["entry_price"])
    size = float(pos["size"])
    mult = float(pos["multiplier"])
    margin = float(pos["margin"])
    funding = float(pos["funding_paid"] or 0.0)
    direction = pos["direction"]

    mark = float(price) if price is not None and price > 0 else entry
    notional = notional_of(size, mark, mult)
    pl = pl_of(direction, entry, mark, size, mult)
    equity = margin + pl + funding
    maintenance = margin * (config.MAINTENANCE_MARGIN_PCT / 100.0)
    liq = liquidation_price(direction, entry, size, mult, margin, config.MAINTENANCE_MARGIN_PCT)

    asset = registry.get_asset(pos["symbol"]) or {"name": pos["symbol"], "asset_class": "unknown"}
    pos["name"] = asset["name"]
    pos["asset_class"] = asset["asset_class"]
    pos["mark_price"] = _money(mark)
    pos["notional"] = _money(notional)
    pos["unrealized_pl"] = _money(pl)
    pos["unrealized_pl_pct"] = _pct(pl / margin * 100.0) if margin else 0.0
    pos["equity"] = _money(equity)
    pos["maintenance_margin"] = _money(maintenance)
    pos["liquidation_price"] = _money(liq) if liq is not None else None
    pos["margin_ratio"] = _pct(equity / margin * 100.0) if margin else 0.0
    pos["is_open"] = pos.get("closed_at") is None


def list_positions(player_id: int, include_closed: bool = False, limit: int = 50) -> list[dict[str, Any]]:
    conn = get_conn()
    try:
        if include_closed:
            rows = conn.execute(
                "SELECT * FROM positions WHERE player_id = ? "
                "ORDER BY (closed_at IS NULL) DESC, opened_at DESC LIMIT ?",
                (player_id, int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM positions WHERE player_id = ? AND closed_at IS NULL "
                "ORDER BY opened_at DESC",
                (player_id,),
            ).fetchall()
    finally:
        conn.close()

    items = [dict(row) for row in rows]
    symbols = sorted({item["symbol"] for item in items})
    prices = market.get_prices(symbols) if symbols else {}
    for item in items:
        if item.get("closed_at") is None:
            _decorate(item, prices.get(item["symbol"]))
        else:
            _decorate_closed(item)
    return items


def _decorate_closed(pos: dict) -> None:
    """Closed rows carry a settled result; no live price is involved."""
    entry = float(pos["entry_price"])
    close = float(pos["close_price"] or entry)
    size = float(pos["size"])
    mult = float(pos["multiplier"])
    margin = float(pos["margin"])
    funding = float(pos["funding_paid"] or 0.0)
    pl = pl_of(pos["direction"], entry, close, size, mult)
    realized = pos.get("realized_pl")

    asset = registry.get_asset(pos["symbol"]) or {"name": pos["symbol"], "asset_class": "unknown"}
    pos["name"] = asset["name"]
    pos["asset_class"] = asset["asset_class"]
    pos["mark_price"] = _money(close)
    pos["notional"] = _money(notional_of(size, entry, mult))
    pos["unrealized_pl"] = 0.0
    pos["unrealized_pl_pct"] = 0.0
    pos["equity"] = 0.0
    pos["maintenance_margin"] = 0.0
    pos["liquidation_price"] = None
    pos["margin_ratio"] = 0.0
    pos["is_open"] = False
    pos["pl"] = _money(pl)
    pos["realized_pl"] = _money(float(realized)) if realized is not None else _money(pl + funding)
    pos["realized_pl_pct"] = _pct((float(pos["realized_pl"]) / margin * 100.0) if margin else 0.0)


def open_positions_summary(player_id: int) -> dict[str, float]:
    """Margin locked and live P/L for one player, used by the portfolio."""
    items = list_positions(player_id, include_closed=False)
    margin = sum(float(item["margin"]) for item in items)
    unrealized = sum(float(item["unrealized_pl"]) + float(item.get("funding_paid") or 0.0) for item in items)
    notional = sum(float(item["notional"]) for item in items)
    return {"margin": margin, "unrealized_pl": unrealized, "notional": notional, "count": len(items)}


def _settle(conn: sqlite3.Connection, pos: dict, price: float, reason: str) -> dict[str, Any]:
    """Close one position inside an existing transaction. Returns the receipt."""
    entry = float(pos["entry_price"])
    size = float(pos["size"])
    mult = float(pos["multiplier"])
    margin = float(pos["margin"])
    funding = float(pos["funding_paid"] or 0.0)

    pl = pl_of(pos["direction"], entry, price, size, mult)
    payout = margin + pl + funding
    # Isolated margin means the worst case is losing the posted margin.
    if payout < 0:
        payout = 0.0
    realized = payout - margin

    now = _now()
    conn.execute(
        "UPDATE positions SET closed_at = ?, close_price = ?, close_reason = ?, realized_pl = ? "
        "WHERE id = ? AND closed_at IS NULL",
        (now, price, reason, realized, pos["id"]),
    )
    conn.execute(
        "UPDATE players SET cash = cash + ? WHERE id = ?", (payout, pos["player_id"]),
    )
    return {
        "position_id": int(pos["id"]),
        "player_id": int(pos["player_id"]),
        "symbol": pos["symbol"],
        "kind": pos["kind"],
        "direction": pos["direction"],
        "size": size,
        "entry_price": _money(entry),
        "close_price": _money(price),
        "margin": _money(margin),
        "pl": _money(pl),
        "funding": _money(funding),
        "realized_pl": _money(realized),
        "payout": _money(payout),
        "reason": reason,
    }


def _log_settlement(receipt: dict[str, Any]) -> None:
    """Emit the feed/alerts entry for a settled position.

    Kept out of `_settle` so it runs after the transaction commits: a rolled
    back close must not leave a "position closed" event behind.
    """
    common = {
        "kind": receipt.get("kind"),
        "direction": receipt.get("direction"),
        "size": receipt.get("size"),
        "entry_price": receipt.get("entry_price"),
        "close_price": receipt.get("close_price"),
        "margin": receipt.get("margin"),
    }
    reason = receipt.get("reason")
    if reason == "liquidated":
        activity.log(
            "liquidation",
            player_id=receipt.get("player_id"),
            symbol=receipt.get("symbol"),
            amount=receipt.get("realized_pl"),
            detail=common,
        )
    elif reason == "expired":
        activity.log(
            "future_settle",
            player_id=receipt.get("player_id"),
            symbol=receipt.get("symbol"),
            amount=receipt.get("realized_pl"),
            detail=common,
        )
    else:
        activity.log(
            "position_close",
            player_id=receipt.get("player_id"),
            symbol=receipt.get("symbol"),
            amount=receipt.get("realized_pl"),
            detail=common,
        )


def close_position(*, player_id: int, position_id: int,
                   lang: str = i18n.DEFAULT) -> dict[str, Any]:
    pos = _load_open(position_id, player_id, lang)

    price = float(market.get_price(pos["symbol"]))
    if not math.isfinite(price) or price <= 0:
        raise PositionError("deriv.noPrice", lang, symbol=pos["symbol"])

    with _lock:
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            fresh = conn.execute(
                "SELECT * FROM positions WHERE id = ? AND closed_at IS NULL", (position_id,)
            ).fetchone()
            if fresh is None:
                conn.rollback()
                raise PositionError("deriv.positionGone", lang)
            receipt = _settle(conn, dict(fresh), price, "manual")
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            conn.close()

    receipt["player_id"] = player_id
    _log_settlement(receipt)
    return receipt


def _load_open(position_id: int, player_id: int, lang: str) -> dict[str, Any]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM positions WHERE id = ? AND player_id = ? AND closed_at IS NULL",
            (position_id, player_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise PositionError("deriv.positionGone", lang)
    return dict(row)


def add_margin(*, player_id: int, position_id: int, amount: float,
               lang: str = i18n.DEFAULT) -> dict[str, Any]:
    """Top up a position's margin, lowering its liquidation risk."""
    if not isinstance(amount, (int, float)) or not math.isfinite(float(amount)) or float(amount) <= 0:
        raise PositionError("deriv.badAmount", lang)
    amount = float(amount)
    _load_open(position_id, player_id, lang)

    with _lock:
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT cash FROM players WHERE id = ?", (player_id,)).fetchone()
            if row is None:
                raise PositionError("auth.notSignedIn", lang)
            cash = float(row["cash"])
            if cash < amount:
                conn.rollback()
                raise PositionError(
                    "deriv.insufficientCash", lang, needed=f"{amount:,.2f}", cash=f"{cash:,.2f}",
                )
            conn.execute("UPDATE players SET cash = ? WHERE id = ?", (cash - amount, player_id))
            conn.execute(
                "UPDATE positions SET margin = margin + ? WHERE id = ? AND closed_at IS NULL",
                (amount, position_id),
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            conn.close()
    return get_position(position_id) or {}


def funding_rate(symbol: str) -> float:
    """Perp funding rate for one symbol from this game's own open interest.

    Crowded longs pay shorts and vice versa, scaled by how lopsided the book is
    and capped so a small player base cannot produce absurd rates.
    """
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT direction, size, multiplier, entry_price FROM positions "
            "WHERE symbol = ? AND kind = 'perp' AND closed_at IS NULL",
            (symbol,),
        ).fetchall()
    finally:
        conn.close()

    long_notional = 0.0
    short_notional = 0.0
    for row in rows:
        value = notional_of(row["size"], row["entry_price"], row["multiplier"])
        if row["direction"] == "long":
            long_notional += value
        else:
            short_notional += value

    total = long_notional + short_notional
    if total <= 0:
        return 0.0
    # (long - short) / total is in [-1, 1]; scale to the cap.
    skew = (long_notional - short_notional) / total
    return max(-config.FUNDING_RATE_CAP, min(config.FUNDING_RATE_CAP, skew * config.FUNDING_RATE_CAP))


def apply_funding(now: int | None = None) -> list[dict[str, Any]]:
    """Charge/credit funding on every open perp, returning what happened."""
    now = _now() if now is None else int(now)
    conn = get_conn()
    try:
        symbols = [row["symbol"] for row in conn.execute(
            "SELECT DISTINCT symbol FROM positions WHERE kind = 'perp' AND closed_at IS NULL"
        ).fetchall()]
    finally:
        conn.close()

    payments: list[dict[str, Any]] = []
    for symbol in symbols:
        rate = funding_rate(symbol)
        if abs(rate) < 1e-12:
            continue
        price = float(market.get_price(symbol))
        if not math.isfinite(price) or price <= 0:
            continue

        with _lock:
            conn = get_conn()
            try:
                conn.execute("BEGIN IMMEDIATE")
                rows = conn.execute(
                    "SELECT * FROM positions WHERE symbol = ? AND kind = 'perp' AND closed_at IS NULL",
                    (symbol,),
                ).fetchall()
                for row in rows:
                    pos = dict(row)
                    notional = notional_of(pos["size"], price, pos["multiplier"])
                    # Longs pay when the rate is positive, shorts pay when negative.
                    signed = -rate if pos["direction"] == "long" else rate
                    amount = notional * signed
                    # Funding can never take more than the position still has.
                    floor = -(float(pos["margin"]) + float(pos["funding_paid"] or 0.0))
                    if float(pos["margin"]) + float(pos["funding_paid"] or 0.0) <= 0:
                        amount = 0.0
                    elif amount < floor:
                        amount = floor
                    if amount == 0.0:
                        continue
                    conn.execute(
                        "UPDATE positions SET funding_paid = funding_paid + ? WHERE id = ?",
                        (amount, pos["id"]),
                    )
                    conn.execute(
                        "INSERT INTO funding_payments (position_id, player_id, rate, amount, price, ts) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (pos["id"], pos["player_id"], rate, amount, price, now),
                    )
                    payments.append({
                        "position_id": int(pos["id"]),
                        "player_id": int(pos["player_id"]),
                        "symbol": symbol,
                        "rate": rate,
                        "amount": _money(amount),
                    })
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise
            finally:
                conn.close()
    return payments


def _near_liquidation(pos: dict, price: float | None) -> bool:
    """True if this position is within one cache interval of its stop.

    Used to decide which symbols deserve a forced price refresh during the
    monitor sweep. Returns False when the price is unknown (nothing to compare)
    or when the position cannot be liquidated by price alone.
    """
    if price is None or not math.isfinite(float(price)) or float(price) <= 0:
        return False
    entry = float(pos["entry_price"])
    size = float(pos["size"])
    mult = float(pos["multiplier"])
    margin = float(pos["margin"])
    liq = liquidation_price(pos["direction"], entry, size, mult, margin,
                            config.MAINTENANCE_MARGIN_PCT)
    if liq is None:
        return False
    # Treat "within 0.5% of the stop" as at risk; that is wider than a typical
    # 5-minute move for most symbols, so anything this close needs a live quote.
    return abs(float(price) - liq) / max(liq, 1e-9) <= 0.005


def monitor_positions(lang: str = i18n.DEFAULT) -> dict[str, Any]:
    """Liquidate under-margined positions and settle expired futures.

    Safe to call from a background loop: every decision re-reads state inside a
    write transaction, so a concurrent manual close cannot be double-settled.
    """
    liquidated: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []
    warned: list[dict[str, Any]] = []
    checked = 0
    now = _now()

    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM positions WHERE closed_at IS NULL").fetchall()
    finally:
        conn.close()

    prices = market.get_prices(sorted({row["symbol"] for row in rows})) if rows else {}

    # At high leverage a position can be liquidated by a move smaller than the
    # price cache TTL, so a stale quote would make "instant bankruptcy" arrive
    # whenever the cache happens to refresh. Any position already close to its
    # stop forces a fresh quote for its symbol.
    at_risk = {
        row["symbol"] for row in rows
        if _near_liquidation(dict(row), prices.get(row["symbol"]))
    }
    if at_risk:
        try:
            market.refresh_symbols(sorted(at_risk))
            prices.update(market.get_prices(sorted(at_risk)))
        except Exception:
            # Fall back to the cached price; a blip should not stall the sweep.
            pass

    for row in rows:
        pos = dict(row)
        checked += 1
        price = prices.get(pos["symbol"])
        if price is None or not math.isfinite(float(price)) or float(price) <= 0:
            continue
        price = float(price)

        pos["funding_paid"] = pos.get("funding_paid") or 0.0
        equity = float(pos["margin"]) + pl_of(
            pos["direction"], float(pos["entry_price"]), price,
            float(pos["size"]), float(pos["multiplier"]),
        ) + float(pos["funding_paid"])
        maintenance = float(pos["margin"]) * (config.MAINTENANCE_MARGIN_PCT / 100.0)

        reason = None
        if equity <= maintenance:
            reason = "liquidated"
        elif pos["kind"] == "future" and pos["expires_at"] and now >= int(pos["expires_at"]):
            reason = "expired"
        if reason is None:
            # Warn once per position when it first enters the danger zone, so the
            # player hears about it before the liquidation, not after.
            if float(pos["margin"]) > 0:
                ratio = equity / float(pos["margin"]) * 100.0
                if ratio <= config.MARGIN_WARN_PERCENT and not _already_warned(pos["id"]):
                    activity.log(
                        "margin_warning",
                        player_id=int(pos["player_id"]),
                        symbol=pos["symbol"],
                        amount=round(ratio, 2),
                        detail={
                            "position_id": int(pos["id"]),
                            "margin_ratio": round(ratio, 2),
                            "direction": pos["direction"],
                            "kind": pos["kind"],
                            "liquidation_price": liquidation_price(
                                pos["direction"], float(pos["entry_price"]),
                                float(pos["size"]), float(pos["multiplier"]),
                                float(pos["margin"]), config.MAINTENANCE_MARGIN_PCT,
                            ),
                            "mark_price": price,
                        },
                        ts=now,
                    )
                    warned.append({"position_id": int(pos["id"]), "ratio": round(ratio, 2)})
            continue

        with _lock:
            conn = get_conn()
            try:
                conn.execute("BEGIN IMMEDIATE")
                fresh = conn.execute(
                    "SELECT * FROM positions WHERE id = ? AND closed_at IS NULL", (pos["id"],)
                ).fetchone()
                if fresh is None:
                    conn.rollback()
                    continue
                receipt = _settle(conn, dict(fresh), price, reason)
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise
            finally:
                conn.close()

        _log_settlement(receipt)
        (liquidated if reason == "liquidated" else expired).append(receipt)

    return {"checked": checked, "liquidated": liquidated, "expired": expired, "warned": warned}


def _already_warned(position_id: int, window_seconds: int = 3600) -> bool:
    """True if this position already produced a margin warning recently."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM activity WHERE kind = 'margin_warning' AND detail LIKE ? "
            "AND ts > ? LIMIT 1",
            (f'%"position_id": {int(position_id)}%', _now() - window_seconds),
        ).fetchone()
    finally:
        conn.close()
    return row is not None


def portfolio_equity_adjustment(player_ids: Iterable[int]) -> dict[int, dict[str, float]]:
    """Margin + unrealised P/L per player, for net-worth calculations.

    Open positions hold cash that is already deducted from `players.cash`, so
    net worth has to add the position equity back, not the notional.
    """
    ids = list(dict.fromkeys(int(pid) for pid in player_ids))
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    conn = get_conn()
    try:
        rows = conn.execute(
            f"SELECT * FROM positions WHERE closed_at IS NULL AND player_id IN ({placeholders})",
            ids,
        ).fetchall()
    finally:
        conn.close()

    symbols = sorted({row["symbol"] for row in rows})
    prices = market.get_prices(symbols) if symbols else {}

    out: dict[int, dict[str, float]] = {}
    for row in rows:
        pos = dict(row)
        pid = int(pos["player_id"])
        price = prices.get(pos["symbol"])
        mark = float(price) if price is not None and float(price) > 0 else float(pos["entry_price"])
        pl = pl_of(pos["direction"], float(pos["entry_price"]), mark,
                   float(pos["size"]), float(pos["multiplier"]))
        equity = float(pos["margin"]) + pl + float(pos["funding_paid"] or 0.0)
        bucket = out.setdefault(pid, {"margin": 0.0, "equity": 0.0, "unrealized_pl": 0.0, "count": 0})
        bucket["margin"] += float(pos["margin"])
        bucket["equity"] += equity
        bucket["unrealized_pl"] += pl + float(pos["funding_paid"] or 0.0)
        bucket["count"] += 1
    return out


def funding_history(player_id: int, limit: int = 50) -> list[dict[str, Any]]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT f.*, p.symbol, p.direction FROM funding_payments f "
            "JOIN positions p ON p.id = f.position_id "
            "WHERE f.player_id = ? ORDER BY f.ts DESC, f.id DESC LIMIT ?",
            (player_id, int(limit)),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "position_id": int(row["position_id"]),
            "symbol": row["symbol"],
            "direction": row["direction"],
            "rate": float(row["rate"]),
            "amount": _money(row["amount"]),
            "price": _money(row["price"]),
            "ts": int(row["ts"]),
        }
        for row in rows
    ]
