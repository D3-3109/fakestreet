"""Event log behind the live feed, the personal alert bell, and season recaps.

Events store a `kind` plus a JSON `detail` payload with raw numbers instead of a
finished sentence. The client renders each kind through its own translation
table, so one stored event reads correctly in every language and never goes
stale when wording changes.

This module deliberately imports nothing from the rest of the app: game,
derivatives, and seasons all write here, so it has to stay dependency-free.
"""
from __future__ import annotations

import json
import time
from typing import Any, Iterable

from app.db import get_conn

# Kinds shown in the public feed. Everything else is personal-only.
PUBLIC_KINDS = {
    "trade",
    "position_open",
    "position_close",
    "liquidation",
    "future_settle",
    "season_start",
    "season_end",
    "overtake",
}

# Kinds that deserve the player's attention in the alert bell.
ALERT_KINDS = {"liquidation", "margin_warning", "overtake", "future_settle", "rank_up"}


def log(
    kind: str,
    *,
    player_id: int | None = None,
    symbol: str | None = None,
    amount: float | None = None,
    detail: dict[str, Any] | None = None,
    season_id: int | None = None,
    ts: int | None = None,
) -> None:
    """Append one event. Failures must never break the trade that caused them."""
    try:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO activity (ts, player_id, kind, symbol, amount, detail, season_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    int(ts if ts is not None else time.time()),
                    int(player_id) if player_id is not None else None,
                    kind,
                    symbol,
                    float(amount) if amount is not None else None,
                    json.dumps(detail or {}, ensure_ascii=False),
                    season_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # The feed is decoration; losing an event is better than losing a trade.
        pass


def _row_to_event(row) -> dict[str, Any]:
    try:
        detail = json.loads(row["detail"] or "{}")
    except (ValueError, TypeError):
        detail = {}
    return {
        "id": int(row["id"]),
        "ts": int(row["ts"]),
        "player_id": int(row["player_id"]) if row["player_id"] is not None else None,
        "username": row["username"] if "username" in row.keys() else None,
        "kind": row["kind"],
        "symbol": row["symbol"],
        "amount": float(row["amount"]) if row["amount"] is not None else None,
        "detail": detail,
    }


def feed(*, limit: int = 40, since_id: int | None = None, public_only: bool = True,
         season_id: int | None = None) -> list[dict[str, Any]]:
    """Newest-first events. `since_id` returns only events newer than that id."""
    clauses: list[str] = []
    params: list[Any] = []
    if public_only:
        allowed = sorted(PUBLIC_KINDS)
        clauses.append(f"a.kind IN ({','.join('?' for _ in allowed)})")
        params.extend(allowed)
    if since_id is not None:
        clauses.append("a.id > ?")
        params.append(int(since_id))
    if season_id is not None:
        clauses.append("(a.season_id = ? OR a.season_id IS NULL)")
        params.append(int(season_id))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(int(limit), 200)))
    conn = get_conn()
    try:
        rows = conn.execute(
            f"SELECT a.*, p.username FROM activity a "
            f"LEFT JOIN players p ON p.id = a.player_id {where} "
            "ORDER BY a.id DESC LIMIT ?",
            params,
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_event(row) for row in rows]


def alerts_for(player_id: int, *, limit: int = 20, since: int | None = None) -> list[dict[str, Any]]:
    """Personal alerts only (liquidations, margin warnings, being overtaken)."""
    allowed = sorted(ALERT_KINDS)
    clauses = [f"a.kind IN ({','.join('?' for _ in allowed)})", "a.player_id = ?"]
    params: list[Any] = list(allowed) + [int(player_id)]
    if since is not None:
        clauses.append("a.ts > ?")
        params.append(int(since))
    params.append(max(1, min(int(limit), 100)))

    conn = get_conn()
    try:
        rows = conn.execute(
            f"SELECT a.*, p.username FROM activity a "
            f"LEFT JOIN players p ON p.id = a.player_id "
            f"WHERE {' AND '.join(clauses)} ORDER BY a.id DESC LIMIT ?",
            params,
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_event(row) for row in rows]


def unseen_count(player_id: int, since_ts: int) -> int:
    allowed = sorted(ALERT_KINDS)
    conn = get_conn()
    try:
        row = conn.execute(
            f"SELECT COUNT(*) AS n FROM activity WHERE player_id = ? AND ts > ? "
            f"AND kind IN ({','.join('?' for _ in allowed)})",
            [int(player_id), int(since_ts)] + allowed,
        ).fetchone()
    finally:
        conn.close()
    return int(row["n"]) if row else 0


def prune(older_than_ts: int) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM activity WHERE ts < ?", (int(older_than_ts),))
        conn.commit()
    finally:
        conn.close()
