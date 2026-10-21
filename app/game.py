"""Game rules and persistence for the paper-trading backend."""
from __future__ import annotations

import math
import sqlite3
import threading
import time
from collections import defaultdict
from typing import Any

import config
from app import activity
from app import auth
from app import derivatives
from app import i18n
from app import registry
from app.db import get_conn
from app.market import market

_trade_lock = threading.Lock()

MIN_PASSWORD_LEN = 4

# Spot shorting is allowed on a cash account, not a margin account: proceeds
# from the sale are held as collateral and the player must keep enough cash to
# buy the position back. This cap keeps one short from dwarfing the account.
MAX_SHORT_NOTIONAL_MULTIPLE = 1.0


class NotFoundError(Exception):
    """Raised when a requested game resource does not exist."""

    key = "player.notFound"

    def text(self, lang: str) -> str:
        return i18n.message(self.key, lang)


class UsernameTakenError(Exception):
    """Raised when registering a username that is already in use."""

    key = "register.usernameTaken"

    def text(self, lang: str) -> str:
        return i18n.message(self.key, lang)


class GameError(i18n.ValidationError):
    """A player-facing validation error carrying a message key plus parameters."""

    def __init__(self, key: str, **params) -> None:
        super().__init__(key, i18n.DEFAULT, **params)


def _now() -> int:
    return int(time.time())


def _row_to_dict(row) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _money(value: float) -> float:
    return round(float(value), 6)


def _pct(value: float) -> float:
    return round(float(value), 4)


def _format_qty(quantity: float) -> str:
    return f"{quantity:g}"


def register_player(username: str, password: str, recovery_word: str) -> dict[str, Any]:
    username = (username or "").strip()
    if not username:
        raise GameError("register.noUsername")
    if len(username) > 40:
        raise GameError("register.usernameTooLong")
    if not password or len(password) < MIN_PASSWORD_LEN:
        raise GameError("register.passwordTooShort", min=MIN_PASSWORD_LEN)
    recovery = auth.normalize_recovery(recovery_word)
    if not recovery:
        raise GameError("register.noRecoveryWord")

    created_at = _now()
    password_hash = auth.hash_secret(password)
    recovery_hash = auth.hash_secret(recovery)

    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO players (username, cash, created_at, password_hash, recovery_hash) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, float(config.STARTING_CASH), created_at, password_hash, recovery_hash),
        )
        conn.commit()
        player_id = int(cur.lastrowid)
    except sqlite3.IntegrityError:
        conn.rollback()
        raise UsernameTakenError()
    finally:
        conn.close()

    token = auth.create_session(player_id)
    return {"id": player_id, "username": username, "token": token}


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    username = (username or "").strip()
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash FROM players WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()
    if row is None or not auth.verify_secret(password or "", row["password_hash"]):
        return None
    token = auth.create_session(int(row["id"]))
    return {"id": int(row["id"]), "username": row["username"], "token": token}


def reset_password(username: str, recovery_word: str, new_password: str) -> dict[str, Any] | None:
    username = (username or "").strip()
    if not new_password or len(new_password) < MIN_PASSWORD_LEN:
        raise GameError("register.passwordTooShort", min=MIN_PASSWORD_LEN)
    recovery = auth.normalize_recovery(recovery_word)

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, username, recovery_hash FROM players WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None or not auth.verify_secret(recovery, row["recovery_hash"]):
            return None
        player_id = int(row["id"])
        uname = row["username"]
        conn.execute(
            "UPDATE players SET password_hash = ? WHERE id = ?",
            (auth.hash_secret(new_password), player_id),
        )
        conn.commit()
    finally:
        conn.close()

    # a successful reset drops any old sessions, then signs the player in fresh
    auth.delete_sessions_for_player(player_id)
    token = auth.create_session(player_id)
    return {"id": player_id, "username": uname, "token": token}


def get_player(player_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, cash, created_at FROM players WHERE id = ?",
            (player_id,),
        ).fetchone()
    return _row_to_dict(row)


def get_portfolio(player_id: int) -> dict[str, Any]:
    player = get_player(player_id)
    if player is None:
        raise NotFoundError()

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT symbol, quantity, avg_cost FROM holdings WHERE player_id = ? ORDER BY symbol",
            (player_id,),
        ).fetchall()

    symbols = [row["symbol"] for row in rows]
    prices = market.get_prices(symbols) if symbols else {}
    holdings = []
    holdings_value = 0.0

    for row in rows:
        symbol = row["symbol"]
        asset = registry.get_asset(symbol) or {"name": symbol, "asset_class": "unknown"}
        quantity = float(row["quantity"])
        avg_cost = float(row["avg_cost"])
        price = float(prices.get(symbol, 0.0))
        value = quantity * price
        cost_basis = quantity * avg_cost
        pl = value - cost_basis
        pl_pct = 0.0 if avg_cost == 0 else (price / avg_cost - 1.0) * 100.0
        holdings_value += value
        holdings.append(
            {
                "symbol": symbol,
                "name": asset["name"],
                "asset_class": asset["asset_class"],
                "quantity": quantity,
                "avg_cost": _money(avg_cost),
                "price": _money(price),
                "value": _money(value),
                "cost_basis": _money(cost_basis),
                "pl": _money(pl),
                "pl_pct": _pct(pl_pct),
                "is_short": quantity < 0,
            }
        )

    # Margin cash is already gone from players.cash, so the value of open
    # positions has to be added back as equity (margin + live P/L), not notional.
    perms = derivatives.list_positions(player_id, include_closed=False)
    margin_locked = sum(float(p["margin"]) for p in perms)
    positions_pl = sum(float(p["unrealized_pl"]) + float(p.get("funding_paid") or 0.0) for p in perms)
    positions_equity = margin_locked + positions_pl

    cash = float(player["cash"])
    net_worth = cash + holdings_value + positions_equity
    total_pl = net_worth - float(config.STARTING_CASH)
    total_pl_pct = (total_pl / float(config.STARTING_CASH)) * 100.0 if config.STARTING_CASH else 0.0
    return {
        "player_id": player["id"],
        "username": player["username"],
        "cash": _money(cash),
        "holdings": holdings,
        "holdings_value": _money(holdings_value),
        "positions": perms,
        "margin_locked": _money(margin_locked),
        "positions_pl": _money(positions_pl),
        "positions_equity": _money(positions_equity),
        "net_worth": _money(net_worth),
        "starting_cash": float(config.STARTING_CASH),
        "total_pl": _money(total_pl),
        "total_pl_pct": _pct(total_pl_pct),
    }


def execute_trade(
    player_id: int,
    symbol: str,
    side: str,
    quantity: float,
    lang: str = i18n.DEFAULT,
) -> tuple[bool, str, dict[str, Any] | None, float]:
    symbol = symbol.strip().upper() if isinstance(symbol, str) else symbol
    side = side.strip().lower() if isinstance(side, str) else side

    with _trade_lock:
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            player = conn.execute(
                "SELECT id, cash FROM players WHERE id = ?",
                (player_id,),
            ).fetchone()
            if player is None:
                raise NotFoundError()

            cash = float(player["cash"])
            if registry.get_asset(symbol) is None:
                conn.rollback()
                return False, i18n.message("trade.unknownSymbol", lang, symbol=symbol), None, cash

            if not isinstance(quantity, (int, float)) or not math.isfinite(float(quantity)) or float(quantity) <= 0:
                conn.rollback()
                return False, i18n.message("trade.badQuantity", lang), None, cash
            quantity = float(quantity)

            if side not in {"buy", "sell"}:
                conn.rollback()
                return False, i18n.message("trade.badSide", lang), None, cash

            price = float(market.get_price(symbol))
            # An unreachable provider leaves the price cache empty, and the
            # market layer reports that as 0.0. Trading at 0 would hand out
            # free shares, so refuse the order instead of booking it.
            if not math.isfinite(price) or price <= 0:
                conn.rollback()
                return False, i18n.message("trade.noPrice", lang, symbol=symbol), None, cash
            total = quantity * price
            ts = _now()

            if side == "buy":
                holding = conn.execute(
                    "SELECT quantity, avg_cost FROM holdings WHERE player_id = ? AND symbol = ?",
                    (player_id, symbol),
                ).fetchone()
                held = float(holding["quantity"]) if holding is not None else 0.0

                # Buying while short covers the short first, at the short's own
                # cost basis; only the remainder opens a new long.
                if held < -1e-9:
                    if cash < total:
                        conn.rollback()
                        return False, i18n.message(
                            "trade.insufficientFunds", lang,
                            needed=f"{total:,.2f}", cash=f"{cash:,.2f}",
                        ), None, cash
                    closing_qty = min(quantity, -held)
                    remaining_qty = quantity - closing_qty
                    leftover = held + closing_qty
                    if abs(leftover) <= 1e-9:
                        if remaining_qty > 1e-9:
                            conn.execute(
                                "UPDATE holdings SET quantity = ?, avg_cost = ? WHERE player_id = ? AND symbol = ?",
                                (remaining_qty, price, player_id, symbol),
                            )
                        else:
                            conn.execute(
                                "DELETE FROM holdings WHERE player_id = ? AND symbol = ?",
                                (player_id, symbol),
                            )
                    else:
                        conn.execute(
                            "UPDATE holdings SET quantity = ? WHERE player_id = ? AND symbol = ?",
                            (leftover, player_id, symbol),
                        )
                    new_cash = cash - total
                    verb_key = "trade.coveredShort"
                else:
                    if cash < total:
                        conn.rollback()
                        return False, i18n.message(
                            "trade.insufficientFunds", lang,
                            needed=f"{total:,.2f}", cash=f"{cash:,.2f}",
                        ), None, cash

                    if holding is None:
                        conn.execute(
                            "INSERT INTO holdings (player_id, symbol, quantity, avg_cost) VALUES (?, ?, ?, ?)",
                            (player_id, symbol, quantity, price),
                        )
                    else:
                        old_qty = float(holding["quantity"])
                        old_avg = float(holding["avg_cost"])
                        new_qty = old_qty + quantity
                        new_avg = ((old_qty * old_avg) + (quantity * price)) / new_qty
                        conn.execute(
                            "UPDATE holdings SET quantity = ?, avg_cost = ? WHERE player_id = ? AND symbol = ?",
                            (new_qty, new_avg, player_id, symbol),
                        )
                    new_cash = cash - total
                    verb_key = "trade.bought"
            else:
                holding = conn.execute(
                    "SELECT quantity, avg_cost FROM holdings WHERE player_id = ? AND symbol = ?",
                    (player_id, symbol),
                ).fetchone()
                held = float(holding["quantity"]) if holding is not None else 0.0

                if held >= quantity - 1e-9:
                    # Normal long sale, possibly flat afterwards.
                    remaining = held - quantity
                    if remaining <= 1e-9:
                        conn.execute(
                            "DELETE FROM holdings WHERE player_id = ? AND symbol = ?",
                            (player_id, symbol),
                        )
                    else:
                        conn.execute(
                            "UPDATE holdings SET quantity = ? WHERE player_id = ? AND symbol = ?",
                            (remaining, player_id, symbol),
                        )
                    new_cash = cash + total
                    verb_key = "trade.sold"
                else:
                    # Either opening a short or extending an existing one. Cash
                    # proceeds are credited, but the resulting short exposure is
                    # capped so one order cannot dwarf the account.
                    new_qty = held - quantity
                    short_notional = abs(new_qty) * price
                    max_notional = max(cash, float(config.STARTING_CASH)) * MAX_SHORT_NOTIONAL_MULTIPLE
                    if short_notional > max_notional + 1e-9:
                        conn.rollback()
                        return False, i18n.message(
                            "trade.shortLimit", lang,
                            limit=f"{max_notional:,.2f}", wanted=f"{short_notional:,.2f}",
                        ), None, cash

                    if holding is None:
                        conn.execute(
                            "INSERT INTO holdings (player_id, symbol, quantity, avg_cost) VALUES (?, ?, ?, ?)",
                            (player_id, symbol, new_qty, price),
                        )
                    elif held < -1e-9:
                        # Extending an existing short: blend the entry price.
                        old_avg = float(holding["avg_cost"])
                        weight = abs(new_qty)
                        blended = ((abs(held) * old_avg) + (quantity * price)) / weight if weight else price
                        conn.execute(
                            "UPDATE holdings SET quantity = ?, avg_cost = ? WHERE player_id = ? AND symbol = ?",
                            (new_qty, blended, player_id, symbol),
                        )
                    else:
                        # Flipping from long to short in one order: the new short
                        # leg starts at this fill price.
                        conn.execute(
                            "UPDATE holdings SET quantity = ?, avg_cost = ? WHERE player_id = ? AND symbol = ?",
                            (new_qty, price, player_id, symbol),
                        )
                    new_cash = cash + total
                    verb_key = "trade.shortOpened"

            conn.execute("UPDATE players SET cash = ? WHERE id = ?", (new_cash, player_id))
            conn.execute(
                "INSERT INTO transactions (player_id, symbol, side, quantity, price, total, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (player_id, symbol, side, quantity, price, total, ts),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # Logged after the write commits so a failed trade never shows up in the feed.
    is_short_leg = verb_key in ("trade.shortOpened", "trade.coveredShort")
    activity.log(
        "trade",
        player_id=player_id,
        symbol=symbol,
        amount=_money(total),
        detail={
            "side": side,
            "quantity": _money(quantity),
            "price": _money(price),
            "short": is_short_leg,
        },
        ts=ts,
    )
    if is_short_leg:
        activity.log(
            "position_open",
            player_id=player_id,
            symbol=symbol,
            amount=_money(total),
            detail={"kind": "spot_short", "direction": "short", "size": _money(quantity)},
            ts=ts,
        )

    execution = {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": _money(price),
        "total": _money(total),
    }
    message = i18n.message(
        verb_key, lang,
        quantity=_format_qty(quantity), symbol=symbol, price=f"{price:,.2f}",
    )
    return True, message, execution, _money(new_cash)


def get_transactions(player_id: int, limit: int = 100) -> list[dict[str, Any]]:
    if get_player(player_id) is None:
        raise NotFoundError()
    limit = max(1, min(int(limit), 500))
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, symbol, side, quantity, price, total, ts FROM transactions WHERE player_id = ? ORDER BY ts DESC, id DESC LIMIT ?",
            (player_id, limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "symbol": row["symbol"],
            "side": row["side"],
            "quantity": float(row["quantity"]),
            "price": _money(row["price"]),
            "total": _money(row["total"]),
            "ts": row["ts"],
        }
        for row in rows
    ]


def get_leaderboard() -> list[dict[str, Any]]:
    ranked = _compute_leaderboard()
    _detect_overtakes(ranked)
    return ranked


def _compute_leaderboard() -> list[dict[str, Any]]:
    with get_conn() as conn:
        players = conn.execute("SELECT id, username, cash FROM players ORDER BY id").fetchall()
        holding_rows = conn.execute("SELECT player_id, symbol, quantity FROM holdings").fetchall()

    symbols = sorted({row["symbol"] for row in holding_rows})
    prices = market.get_prices(symbols) if symbols else {}
    holdings_by_player: dict[int, list[Any]] = defaultdict(list)
    for row in holding_rows:
        holdings_by_player[int(row["player_id"])].append(row)

    player_ids = [int(player["id"]) for player in players]
    deriv_by_player = derivatives.portfolio_equity_adjustment(player_ids)

    ranked = []
    for player in players:
        player_id = int(player["id"])
        holdings_value = sum(
            float(row["quantity"]) * float(prices.get(row["symbol"], 0.0))
            for row in holdings_by_player[player_id]
        )
        deriv = deriv_by_player.get(player_id, {})
        net_worth = float(player["cash"]) + holdings_value + float(deriv.get("equity", 0.0))
        total_pl_pct = ((net_worth - float(config.STARTING_CASH)) / float(config.STARTING_CASH)) * 100.0 if config.STARTING_CASH else 0.0
        ranked.append(
            {
                "player_id": player_id,
                "username": player["username"],
                "net_worth": _money(net_worth),
                "total_pl_pct": _pct(total_pl_pct),
                "margin_locked": _money(float(deriv.get("margin", 0.0))),
                "open_positions": int(deriv.get("count", 0)),
            }
        )

    # Rank on net worth, then on return, then on who got there with less margin
    # in play. Ties used to fall back to registration order, which looked arbitrary.
    ranked.sort(key=lambda item: (-item["net_worth"], -item["total_pl_pct"], item["open_positions"]))
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return ranked


# Last known rank per player, so an overtake is detected by comparison rather
# than by reacting to every leaderboard read.
_last_ranks: dict[int, int] = {}
_overtake_lock = threading.Lock()
OVERTAKE_COOLDOWN_SECONDS = 600
_last_overtake_at: dict[int, int] = {}


def _detect_overtakes(ranked: list[dict[str, Any]]) -> None:
    """Emit an alert when a player drops below someone they were ahead of.

    Ranks are compared against the previous leaderboard read. State is in
    memory on purpose: after a restart there is no "previous", so the first read
    only establishes a baseline and never spams everyone with alerts. A cooldown
    keeps two players swapping places back and forth from generating a stream of
    alerts, since the dashboard polls this every few seconds.
    """
    now = _now()
    with _overtake_lock:
        previous = dict(_last_ranks)
        for entry in ranked:
            pid = int(entry["player_id"])
            old_rank = previous.get(pid)
            new_rank = int(entry["rank"])
            if old_rank is None or new_rank <= old_rank:
                continue
            last = _last_overtake_at.get(pid, 0)
            if now - last < OVERTAKE_COOLDOWN_SECONDS:
                continue
            # Someone climbed past this player; name whoever is now directly above.
            ahead = [e for e in ranked if int(e["rank"]) == new_rank - 1]
            by = ahead[0]["username"] if ahead else None
            activity.log(
                "overtake",
                player_id=pid,
                amount=float(entry["net_worth"]),
                detail={"by": by, "from_rank": old_rank, "to_rank": new_rank},
                ts=now,
            )
            _last_overtake_at[pid] = now
        _last_ranks.clear()
        _last_ranks.update({int(e["player_id"]): int(e["rank"]) for e in ranked})
