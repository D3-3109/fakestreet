"""Periodic market and equity sampling.

Everything that needs history reads from here:

  * the dashboard index line
  * per-symbol sparklines on the market table
  * each player's equity curve
  * the daily report

One sampler writes all of it on a fixed interval, so the charts stay populated
even when nobody has a page open. Before this existed the market cache only
refreshed on request, which meant a chart of "the last hour" was really a chart
of "the handful of times someone loaded the market tab".
"""
from __future__ import annotations

import time
from typing import Any

import config
from app import registry
from app.db import get_conn
from app.market import market

# The index is rebased to this at its first sample so early values read like a
# quote rather than an arbitrary sum.
INDEX_BASE = 1000.0


def _now() -> int:
    return int(time.time())


def _bucket(ts: int) -> int:
    """Round a timestamp down to the sampling grid.

    Snapping keeps the primary keys stable (one sample per symbol per slot) and
    makes the series evenly spaced, which the charts rely on.
    """
    step = max(1, int(config.SNAPSHOT_INTERVAL_SECONDS))
    return (ts // step) * step


def sample_prices(ts: int | None = None) -> dict[str, float]:
    """Record one price sample per tradable symbol."""
    ts = _bucket(_now() if ts is None else int(ts))
    assets = registry.all_assets()
    symbols = [a["symbol"] for a in assets]
    prices = market.get_prices(symbols)
    prices = {s: p for s, p in prices.items() if p and p > 0}
    if not prices:
        return {}

    conn = get_conn()
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO price_snapshots (symbol, ts, price) VALUES (?, ?, ?)",
            [(symbol, ts, float(price)) for symbol, price in prices.items()],
        )
        conn.commit()
    finally:
        conn.close()
    return prices


def sample_index(ts: int | None = None, prices: dict[str, float] | None = None) -> float | None:
    """Equal-weighted index across every priced symbol, rebased to 1000.

    Equal weighting is deliberate: a market-cap weighted index would be
    dominated by BTC and AAPL, and the point here is "did the whole board move".
    """
    ts = _bucket(_now() if ts is None else int(ts))
    if prices is None:
        prices = sample_prices(ts)
    if not prices:
        return None

    conn = get_conn()
    try:
        base_rows = conn.execute(
            "SELECT symbol, price FROM price_snapshots WHERE ts = "
            "(SELECT MIN(ts) FROM price_snapshots)"
        ).fetchall()
        base = {row["symbol"]: float(row["price"]) for row in base_rows}
        if not base:
            return None

        # Only symbols present in both the base and the current sample can be
        # compared; a newly added asset joins the index from then on.
        ratios = [
            prices[symbol] / base[symbol]
            for symbol in base
            if symbol in prices and base[symbol] > 0
        ]
        if not ratios:
            return None
        value = INDEX_BASE * (sum(ratios) / len(ratios))
        change_pct = (value / INDEX_BASE - 1.0) * 100.0

        conn.execute(
            "INSERT OR REPLACE INTO index_snapshots (ts, value, change_pct) VALUES (?, ?, ?)",
            (ts, value, change_pct),
        )
        conn.commit()
        return value
    finally:
        conn.close()


def sample_equity(ts: int | None = None, season_id: int | None = None) -> int:
    """Record net worth for every player. Returns how many rows were written."""
    ts = _bucket(_now() if ts is None else int(ts))

    # Imported lazily: game imports this module's siblings, and a top-level
    # import would create a cycle.
    from app import game

    conn = get_conn()
    try:
        players = conn.execute("SELECT id FROM players").fetchall()
    finally:
        conn.close()

    written = 0
    for row in players:
        player_id = int(row["id"])
        try:
            portfolio = game.get_portfolio(player_id)
        except Exception:
            continue
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO equity_snapshots "
                "(player_id, season_id, ts, net_worth, cash, holdings_value, positions_equity, return_pct) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    player_id, season_id, ts,
                    float(portfolio["net_worth"]),
                    float(portfolio["cash"]),
                    float(portfolio["holdings_value"]),
                    float(portfolio.get("positions_equity", 0.0)),
                    float(portfolio["total_pl_pct"]),
                ),
            )
            conn.commit()
            written += 1
        finally:
            conn.close()
    return written


def sample_all(season_id: int | None = None) -> dict[str, Any]:
    """One full sampling pass, used by the background loop."""
    ts = _bucket(_now())
    prices = sample_prices(ts)
    index_value = sample_index(ts, prices) if prices else None
    equity_rows = sample_equity(ts, season_id)
    return {"ts": ts, "prices": len(prices), "index": index_value, "equity_rows": equity_rows}


# --- readers -----------------------------------------------------------------

def index_series(hours: int = 24, points: int = 120) -> list[dict[str, float]]:
    since = _now() - hours * 3600
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT ts, value FROM index_snapshots WHERE ts >= ? ORDER BY ts", (since,)
        ).fetchall()
    finally:
        conn.close()
    series = [{"t": int(r["ts"]), "v": float(r["value"])} for r in rows]
    return _downsample(series, points)


def equity_series(player_id: int, hours: int = 168, points: int = 200) -> list[dict[str, float]]:
    since = _now() - hours * 3600
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT ts, net_worth FROM equity_snapshots WHERE player_id = ? AND ts >= ? ORDER BY ts",
            (int(player_id), since),
        ).fetchall()
    finally:
        conn.close()
    series = [{"t": int(r["ts"]), "v": float(r["net_worth"])} for r in rows]
    return _downsample(series, points)


def price_series(symbol: str, hours: int = 24, points: int = 60) -> list[dict[str, float]]:
    since = _now() - hours * 3600
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT ts, price FROM price_snapshots WHERE symbol = ? AND ts >= ? ORDER BY ts",
            (symbol.upper(), since),
        ).fetchall()
    finally:
        conn.close()
    series = [{"t": int(r["ts"]), "v": float(r["price"])} for r in rows]
    return _downsample(series, points)


def sparklines(hours: int = 24, points: int = 30) -> dict[str, list[float]]:
    """Compact price history per symbol for the market table sparklines."""
    since = _now() - hours * 3600
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT symbol, ts, price FROM price_snapshots WHERE ts >= ? ORDER BY symbol, ts",
            (since,),
        ).fetchall()
    finally:
        conn.close()

    grouped: dict[str, list[dict[str, float]]] = {}
    for row in rows:
        grouped.setdefault(row["symbol"], []).append({"t": int(row["ts"]), "v": float(row["price"])})
    return {
        symbol: [point["v"] for point in _downsample(series, points)]
        for symbol, series in grouped.items()
    }


def _downsample(series: list[dict[str, float]], max_points: int) -> list[dict[str, float]]:
    """Keep at most `max_points`, preserving first and last for correct shape."""
    if len(series) <= max_points:
        return series
    step = (len(series) - 1) / (max_points - 1)
    picked = [series[round(i * step)] for i in range(max_points)]
    picked[-1] = series[-1]
    return picked


def daily_report(player_id: int, day_start: int | None = None, day_end: int | None = None,
                 season_id: int | None = None) -> dict[str, Any]:
    """One day's summary for a player: equity move, best/worst, trades, alerts.

    The report is derived entirely from stored snapshots and the event log, so
    it works retroactively for any day that has data.
    """
    end = _now() if day_end is None else int(day_end)
    start = end - 86400 if day_start is None else int(day_start)

    conn = get_conn()
    try:
        snaps = conn.execute(
            "SELECT ts, net_worth, cash, holdings_value, positions_equity, return_pct "
            "FROM equity_snapshots WHERE player_id = ? AND ts >= ? AND ts <= ? ORDER BY ts",
            (int(player_id), start, end),
        ).fetchall()
    finally:
        conn.close()

    if not snaps:
        return {
            "player_id": player_id,
            "start_ts": start, "end_ts": end,
            "has_data": False,
            "start_net_worth": None, "end_net_worth": None,
            "change": 0.0, "change_pct": 0.0,
            "high": None, "low": None, "points": 0,
            "trades": 0, "liquidations": 0, "positions_opened": 0,
            "best_symbol": None, "worst_symbol": None,
            "holdings": [],
        }

    first, last = snaps[0], snaps[-1]
    start_nw = float(first["net_worth"])
    end_nw = float(last["net_worth"])
    change = end_nw - start_nw
    change_pct = (change / start_nw * 100.0) if start_nw else 0.0
    high = max(float(s["net_worth"]) for s in snaps)
    low = min(float(s["net_worth"]) for s in snaps)

    conn = get_conn()
    try:
        counts = conn.execute(
            "SELECT "
            " SUM(CASE WHEN kind = 'trade' THEN 1 ELSE 0 END) AS trades, "
            " SUM(CASE WHEN kind = 'liquidation' THEN 1 ELSE 0 END) AS liquidations, "
            " SUM(CASE WHEN kind = 'position_open' THEN 1 ELSE 0 END) AS opened "
            "FROM activity WHERE player_id = ? AND ts >= ? AND ts <= ?",
            (int(player_id), start, end),
        ).fetchone()

        # Best/worst mover among symbols the player actually traded that day.
        moved = conn.execute(
            "SELECT symbol, "
            " (SELECT price FROM price_snapshots p2 WHERE p2.symbol = p1.symbol AND p2.ts <= ? ORDER BY p2.ts DESC LIMIT 1) AS p_start, "
            " (SELECT price FROM price_snapshots p3 WHERE p3.symbol = p1.symbol AND p3.ts <= ? ORDER BY p3.ts DESC LIMIT 1) AS p_end "
            "FROM (SELECT DISTINCT symbol FROM activity WHERE player_id = ? AND ts >= ? AND ts <= ? AND symbol IS NOT NULL) p1",
            (start, end, int(player_id), start, end),
        ).fetchall()

        holdings = conn.execute(
            "SELECT symbol, quantity, avg_cost FROM holdings WHERE player_id = ?", (int(player_id),)
        ).fetchall()
    finally:
        conn.close()

    movers = []
    for row in moved:
        if row["p_start"] and row["p_end"] and float(row["p_start"]) > 0:
            pct = (float(row["p_end"]) / float(row["p_start"]) - 1.0) * 100.0
            movers.append({"symbol": row["symbol"], "change_pct": round(pct, 2)})
    movers.sort(key=lambda m: m["change_pct"])

    return {
        "player_id": player_id,
        "start_ts": int(first["ts"]),
        "end_ts": int(last["ts"]),
        "has_data": True,
        "start_net_worth": round(start_nw, 2),
        "end_net_worth": round(end_nw, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "points": len(snaps),
        "trades": int(counts["trades"] or 0) if counts else 0,
        "liquidations": int(counts["liquidations"] or 0) if counts else 0,
        "positions_opened": int(counts["opened"] or 0) if counts else 0,
        "best_symbol": movers[-1] if movers else None,
        "worst_symbol": movers[0] if movers else None,
        "holdings": [
            {"symbol": r["symbol"], "quantity": float(r["quantity"]), "avg_cost": float(r["avg_cost"])}
            for r in holdings
        ],
        "series": [{"t": int(s["ts"]), "v": round(float(s["net_worth"]), 2)} for s in snaps],
    }


def prune(older_than_days: int = 14) -> None:
    """Drop samples nobody will chart any more; keeps the SQLite file small."""
    cutoff = _now() - int(older_than_days) * 86400
    conn = get_conn()
    try:
        conn.execute("DELETE FROM price_snapshots WHERE ts < ?", (cutoff,))
        conn.execute("DELETE FROM index_snapshots WHERE ts < ?", (cutoff,))
        conn.execute("DELETE FROM equity_snapshots WHERE ts < ?", (cutoff,))
        conn.commit()
    finally:
        conn.close()
