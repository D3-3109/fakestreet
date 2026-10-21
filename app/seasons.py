"""Season lifecycle: weekly windows that reset every account.

Why seasons exist at all
------------------------
A permanent leaderboard has two problems for a group of friends: whoever
registered first is permanently ahead, and there is never a moment where
anybody wins. A weekly window fixes both — everyone starts from the same
starting cash, and Sunday night actually means something.

Rollover
--------
When the active season expires the server archives the final standings into
`season_results` and resets every player to the starting cash, closing all
open positions and clearing spot holdings. Resetting is honest for this game
because nothing outside the season is meant to persist.
"""
from __future__ import annotations

import json
import time
from typing import Any

import config
from app import activity
from app.db import get_conn


def _now() -> int:
    return int(time.time())


def current_season() -> dict[str, Any] | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM seasons WHERE status = 'active' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    season = dict(row)
    season["seconds_left"] = max(0, int(season["ends_at"]) - _now())
    return season


def start_season(name: str | None = None, days: int | None = None) -> dict[str, Any]:
    """Open a new season. Resets every account so the race starts even."""
    days = int(days if days is not None else config.SEASON_LENGTH_DAYS)
    now = _now()
    starts_at = now
    ends_at = now + days * 86400
    label = name or time.strftime("%Y-%m-%d", time.localtime(starts_at))

    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE seasons SET status = 'closed' WHERE status = 'active'")
        cur = conn.execute(
            "INSERT INTO seasons (name, starts_at, ends_at, status, created_at) "
            "VALUES (?, ?, ?, 'active', ?)",
            (label, starts_at, ends_at, now),
        )
        season_id = int(cur.lastrowid)
        _reset_accounts(conn)
        conn.commit()
    finally:
        conn.close()

    activity.log(
        "season_start",
        season_id=season_id,
        detail={"name": label, "ends_at": ends_at, "days": days},
        ts=now,
    )
    return current_season() or {}


def _reset_accounts(conn) -> None:
    """Wipe books back to the starting cash. History rows are left alone."""
    conn.execute("DELETE FROM holdings")
    conn.execute("DELETE FROM positions WHERE closed_at IS NULL")
    conn.execute("UPDATE players SET cash = ?", (float(config.STARTING_CASH),))


def rollover_if_due() -> dict[str, Any] | None:
    """Close the active season and open the next one when its window ended."""
    season = current_season()
    if season is None:
        return start_season()
    if int(season["ends_at"]) > _now():
        return None
    return close_season(int(season["id"]))


def close_season(season_id: int) -> dict[str, Any]:
    """Archive final standings for a season, then start the next one."""
    from app import game  # local import: game imports snapshots, not seasons

    standings = game.get_leaderboard()
    now = _now()

    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM seasons WHERE id = ?", (season_id,)).fetchone()
        if row is None:
            conn.rollback()
            return {}
        conn.execute("DELETE FROM season_results WHERE season_id = ?", (season_id,))

        for entry in standings:
            counts = conn.execute(
                "SELECT "
                " SUM(CASE WHEN kind = 'trade' THEN 1 ELSE 0 END) AS trades, "
                " SUM(CASE WHEN kind = 'liquidation' THEN 1 ELSE 0 END) AS liquidations "
                "FROM activity WHERE player_id = ? AND season_id = ?",
                (entry["player_id"], season_id),
            ).fetchone()
            conn.execute(
                "INSERT INTO season_results "
                "(season_id, player_id, username, final_net_worth, return_pct, rank, trades, liquidations, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    season_id, entry["player_id"], entry["username"],
                    float(entry["net_worth"]), float(entry["total_pl_pct"]), int(entry["rank"]),
                    int(counts["trades"] or 0) if counts else 0,
                    int(counts["liquidations"] or 0) if counts else 0,
                    now,
                ),
            )
        conn.execute("UPDATE seasons SET status = 'closed' WHERE id = ?", (season_id,))
        conn.commit()
    finally:
        conn.close()

    winner = standings[0] if standings else None
    activity.log(
        "season_end",
        season_id=season_id,
        detail={
            "name": row["name"],
            "winner": winner["username"] if winner else None,
            "winner_return_pct": winner["total_pl_pct"] if winner else None,
        },
        ts=now,
    )

    next_season = start_season()
    return {"closed": season_id, "winner": winner, "next": next_season}


def results(season_id: int, limit: int = 20) -> list[dict[str, Any]]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM season_results WHERE season_id = ? ORDER BY rank LIMIT ?",
            (int(season_id), int(limit)),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "rank": int(r["rank"]),
            "player_id": int(r["player_id"]),
            "username": r["username"],
            "final_net_worth": round(float(r["final_net_worth"]), 2),
            "return_pct": round(float(r["return_pct"]), 2),
            "trades": int(r["trades"]),
            "liquidations": int(r["liquidations"]),
        }
        for r in rows
    ]


def history(limit: int = 10) -> list[dict[str, Any]]:
    """Past seasons with their winners, for the hall-of-fame panel."""
    conn = get_conn()
    try:
        seasons = conn.execute(
            "SELECT * FROM seasons WHERE status = 'closed' ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        out = []
        for season in seasons:
            winner = conn.execute(
                "SELECT username, return_pct, final_net_worth FROM season_results "
                "WHERE season_id = ? ORDER BY rank LIMIT 1",
                (season["id"],),
            ).fetchone()
            out.append({
                "id": int(season["id"]),
                "name": season["name"],
                "starts_at": int(season["starts_at"]),
                "ends_at": int(season["ends_at"]),
                "winner": winner["username"] if winner else None,
                "winner_return_pct": round(float(winner["return_pct"]), 2) if winner else None,
                "winner_net_worth": round(float(winner["final_net_worth"]), 2) if winner else None,
            })
    finally:
        conn.close()
    return out


def ensure_active() -> dict[str, Any]:
    """Guarantee an active season exists. Called at startup."""
    season = current_season()
    if season is not None:
        rollover_if_due()
        return current_season() or {}
    return start_season()
