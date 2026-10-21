"""FastAPI application for the local paper-trading game."""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import config
from app import activity
from app import auth
from app import derivatives
from app import i18n
from app import registry
from app import seasons
from app import snapshots
from app.db import init_db
from app.game import (
    NotFoundError,
    UsernameTakenError,
    authenticate,
    execute_trade,
    get_leaderboard,
    get_player,
    get_portfolio,
    get_transactions,
    register_player,
    reset_password,
)
from app.market import market
from app.models import (
    AddAssetRequest,
    AddMarginRequest,
    LoginRequest,
    OpenPositionRequest,
    RecoverRequest,
    RegisterRequest,
    TradeRequest,
)
from app.providers import crypto, fiat, stocks

log = logging.getLogger("trading_game")

_monitor_task: asyncio.Task | None = None
_funding_task: asyncio.Task | None = None
_snapshot_task: asyncio.Task | None = None
_season_task: asyncio.Task | None = None


async def _position_monitor_loop() -> None:
    """Liquidate under-margined positions, settle futures, warn before liquidation."""
    while True:
        try:
            await asyncio.sleep(config.POSITION_MONITOR_SECONDS)
            result = await asyncio.to_thread(derivatives.monitor_positions)
            if result["liquidated"] or result["expired"] or result.get("warned"):
                log.info(
                    "position monitor: %d liquidated, %d expired, %d warned",
                    len(result["liquidated"]), len(result["expired"]), len(result.get("warned") or []),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("position monitor iteration failed")


async def _funding_loop() -> None:
    """Apply perpetual funding on a fixed interval."""
    while True:
        try:
            await asyncio.sleep(config.FUNDING_INTERVAL_SECONDS)
            payments = await asyncio.to_thread(derivatives.apply_funding)
            if payments:
                log.info("funding applied to %d positions", len(payments))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("funding iteration failed")


async def _snapshot_loop() -> None:
    """Record prices, the market index, and every player's equity.

    This is what makes charts and daily reports possible, and it also keeps the
    price cache warm so a quiet server still has fresh quotes.
    """
    while True:
        try:
            await asyncio.sleep(config.SNAPSHOT_INTERVAL_SECONDS)
            season = await asyncio.to_thread(seasons.current_season)
            result = await asyncio.to_thread(
                snapshots.sample_all, int(season["id"]) if season else None,
            )
            await asyncio.to_thread(snapshots.prune, config.SNAPSHOT_RETENTION_DAYS)
            log.info(
                "snapshot: %d prices, index=%s, %d equity rows",
                result["prices"], result["index"], result["equity_rows"],
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("snapshot iteration failed")


async def _season_loop() -> None:
    """Roll the season over when its window ends."""
    while True:
        try:
            await asyncio.sleep(60)
            closed = await asyncio.to_thread(seasons.rollover_if_due)
            if closed:
                log.info("season %s closed, next season started", closed.get("closed"))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("season rollover failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _monitor_task, _funding_task, _snapshot_task, _season_task
    init_db()
    season = seasons.ensure_active()
    log.info("active season: %s (ends in %ss)", season.get("name"), season.get("seconds_left"))
    _monitor_task = asyncio.create_task(_position_monitor_loop())
    _funding_task = asyncio.create_task(_funding_loop())
    _snapshot_task = asyncio.create_task(_snapshot_loop())
    _season_task = asyncio.create_task(_season_loop())
    # Prime the very first sample so a freshly started server has one data point
    # instead of an empty chart until the first interval elapses.
    asyncio.create_task(_first_sample())
    try:
        yield
    finally:
        for task in (_monitor_task, _funding_task, _snapshot_task, _season_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass


async def _first_sample() -> None:
    try:
        await asyncio.sleep(3)
        season = await asyncio.to_thread(seasons.current_season)
        await asyncio.to_thread(snapshots.sample_all, int(season["id"]) if season else None)
    except Exception:
        log.exception("initial sample failed")


app = FastAPI(title="Trading Game", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthError(Exception):
    """Raised for missing/invalid tokens (401) or wrong-account access (403)."""

    def __init__(self, message: str = "Not signed in", status_code: int = 401) -> None:
        self.message = message
        self.status_code = status_code


def request_lang(accept_language: str | None) -> str:
    """Resolve the locale for one request from its Accept-Language header."""
    return i18n.resolve(accept_language)


@app.exception_handler(AuthError)
async def _auth_error_handler(_request, exc: AuthError):
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "message": exc.message})


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def current_player_id(
    authorization: str | None = Header(default=None),
    accept_language: str | None = Header(default=None),
) -> int:
    player_id = auth.resolve_token(_extract_token(authorization))
    if player_id is None:
        raise AuthError(i18n.message("auth.notSignedIn", request_lang(accept_language)), 401)
    return player_id


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/assets")
def assets() -> dict:
    custom = registry.custom_symbols()
    rows = []
    for asset in market.get_assets():
        row = asset.to_dict()
        row["custom"] = row["symbol"] in custom
        rows.append(row)
    return {
        "base_currency": config.BASE_CURRENCY,
        "as_of": int(time.time()),
        "assets": rows,
    }


@app.get("/api/assets/search")
def asset_search(
    klass: str = Query(alias="class"),
    q: str = Query(default=""),
    accept_language: str | None = Header(default=None),
) -> dict:
    klass = (klass or "").strip().lower()
    if klass not in {"stock", "crypto", "fiat"}:
        return JSONResponse(status_code=400, content={
            "ok": False,
            "message": i18n.message("asset.badClass", request_lang(accept_language)),
        })
    if klass == "stock":
        results = stocks.search(q)
    elif klass == "crypto":
        results = crypto.search(q)
    else:
        results = fiat.search(q)
    return {"class": klass, "results": results}


@app.post("/api/assets")
def add_asset(
    body: AddAssetRequest,
    current: int = Depends(current_player_id),
    accept_language: str | None = Header(default=None),
):
    lang = request_lang(accept_language)
    try:
        registry.create_custom_asset(
            body.asset_class,
            body.symbol,
            provider_id=body.provider_id,
            name=body.name,
            added_by=current,
            lang=lang,
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "message": str(exc)})

    symbol = body.symbol.strip().upper()
    asset = registry.get_asset(symbol)
    price = 0.0
    prev_close = 0.0
    try:
        price = float(market.get_price(symbol))
        cached = market._cache.get(symbol) or {}
        prev_close = float(cached.get("prev_close") or price)
    except Exception:
        pass
    response_asset = {
        "symbol": asset["symbol"],
        "name": asset["name"],
        "asset_class": asset["asset_class"],
        "provider_id": asset["provider_id"],
        "price": round(price, 6),
        "prev_close": round(prev_close, 6),
        "change_pct": round(0.0 if not prev_close else (price / prev_close - 1.0) * 100.0, 2),
        "custom": True,
    }
    return {"ok": True, "asset": response_asset}


@app.get("/api/assets/{symbol}/history")
def asset_history(
    symbol: str,
    range: str = Query(default=config.HISTORY_DEFAULT_RANGE),
    accept_language: str | None = Header(default=None),
) -> dict:
    symbol = symbol.strip().upper()
    try:
        history = market.get_history(symbol, range=range)
    except KeyError:
        raise HTTPException(status_code=404, detail=i18n.message(
            "asset.unknownSymbol", request_lang(accept_language), symbol=symbol,
        ))
    return {
        "symbol": symbol,
        "range": range,
        "points": [{"t": int(ts), "price": float(price)} for ts, price in history],
    }


@app.post("/api/register")
def register(body: RegisterRequest, accept_language: str | None = Header(default=None)):
    lang = request_lang(accept_language)
    try:
        return register_player(body.username, body.password, body.recovery_word)
    except (UsernameTakenError, ValueError) as exc:
        message = exc.text(lang) if hasattr(exc, "text") else str(exc)
        return JSONResponse(status_code=400, content={"ok": False, "message": message})


@app.post("/api/login")
def login(body: LoginRequest, accept_language: str | None = Header(default=None)):
    result = authenticate(body.username, body.password)
    if result is None:
        return JSONResponse(status_code=401, content={
            "ok": False,
            "message": i18n.message("auth.wrongCredentials", request_lang(accept_language)),
        })
    return result


@app.post("/api/recover")
def recover(body: RecoverRequest, accept_language: str | None = Header(default=None)):
    lang = request_lang(accept_language)
    try:
        result = reset_password(body.username, body.recovery_word, body.new_password)
    except ValueError as exc:
        message = exc.text(lang) if hasattr(exc, "text") else str(exc)
        return JSONResponse(status_code=400, content={"ok": False, "message": message})
    if result is None:
        return JSONResponse(status_code=401, content={
            "ok": False,
            "message": i18n.message("auth.wrongRecoveryWord", lang),
        })
    return result


@app.post("/api/logout")
def logout(authorization: str | None = Header(default=None)):
    auth.delete_session(_extract_token(authorization))
    return {"ok": True}


@app.get("/api/me")
def me(
    player_id: int = Depends(current_player_id),
    accept_language: str | None = Header(default=None),
):
    player = get_player(player_id)
    if player is None:
        raise AuthError(i18n.message("auth.notSignedIn", request_lang(accept_language)), 401)
    return {"id": player["id"], "username": player["username"]}


@app.get("/api/players/{player_id}/portfolio")
def player_portfolio(
    player_id: int,
    current: int = Depends(current_player_id),
    accept_language: str | None = Header(default=None),
) -> dict:
    lang = request_lang(accept_language)
    if player_id != current:
        raise AuthError(i18n.message("auth.wrongAccount", lang), 403)
    try:
        return get_portfolio(player_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.text(lang))


@app.get("/api/players/{player_id}/transactions")
def player_transactions(
    player_id: int,
    current: int = Depends(current_player_id),
    limit: int = Query(default=100),
    accept_language: str | None = Header(default=None),
) -> dict:
    lang = request_lang(accept_language)
    if player_id != current:
        raise AuthError(i18n.message("auth.wrongAccount", lang), 403)
    try:
        return {"player_id": player_id, "transactions": get_transactions(player_id, limit=limit)}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.text(lang))


@app.post("/api/trade")
def trade(
    body: TradeRequest,
    current: int = Depends(current_player_id),
    accept_language: str | None = Header(default=None),
):
    lang = request_lang(accept_language)
    try:
        ok, message, execution, cash = execute_trade(
            current, body.symbol, body.side, body.quantity, lang=lang,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.text(lang))
    content = {"ok": ok, "message": message}
    if ok:
        content["execution"] = execution
        content["cash"] = cash
        return content
    return JSONResponse(status_code=400, content=content)


@app.get("/api/leaderboard")
def leaderboard() -> dict:
    return {"leaderboard": get_leaderboard()}


# --- Derivatives -------------------------------------------------------------

def _deriv_payload(position: dict, lang: str) -> dict:
    """Shape one position for the client, adding presentation-only fields."""
    data = dict(position)
    data.pop("player_id", None)
    data["direction_label"] = i18n.message(
        "deriv.long" if position.get("direction") == "long" else "deriv.short", lang,
    )
    return data


@app.get("/api/derivatives/config")
def derivatives_config() -> dict:
    """Limits and defaults the trading UI needs before opening a position."""
    return {
        "max_leverage": config.MAX_LEVERAGE,
        "uncapped_leverage": config.MAX_LEVERAGE <= 0,
        "default_leverage": config.DEFAULT_LEVERAGE,
        "min_position_margin": config.MIN_POSITION_MARGIN,
        "maintenance_margin_pct": config.MAINTENANCE_MARGIN_PCT,
        "funding_interval_seconds": config.FUNDING_INTERVAL_SECONDS,
        "funding_rate_cap": config.FUNDING_RATE_CAP,
        "future_duration_seconds": config.FUTURE_DURATION_SECONDS,
        "contract_multipliers": config.CONTRACT_MULTIPLIERS,
        "monitor_interval_seconds": config.POSITION_MONITOR_SECONDS,
    }


@app.get("/api/derivatives/funding/{symbol}")
def derivatives_funding(symbol: str) -> dict:
    """Current funding rate for one symbol's perp, plus book composition."""
    symbol = symbol.strip().upper()
    if registry.get_asset(symbol) is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")
    return {
        "symbol": symbol,
        "rate": derivatives.funding_rate(symbol),
        "interval_seconds": config.FUNDING_INTERVAL_SECONDS,
    }


@app.get("/api/players/{player_id}/positions")
def player_positions(
    player_id: int,
    current: int = Depends(current_player_id),
    include_closed: bool = Query(default=False),
    accept_language: str | None = Header(default=None),
) -> dict:
    lang = request_lang(accept_language)
    if player_id != current:
        raise AuthError(i18n.message("auth.wrongAccount", lang), 403)
    items = derivatives.list_positions(player_id, include_closed=include_closed)
    return {"player_id": player_id, "positions": [_deriv_payload(item, lang) for item in items]}


@app.get("/api/players/{player_id}/funding")
def player_funding(
    player_id: int,
    current: int = Depends(current_player_id),
    accept_language: str | None = Header(default=None),
) -> dict:
    lang = request_lang(accept_language)
    if player_id != current:
        raise AuthError(i18n.message("auth.wrongAccount", lang), 403)
    return {"player_id": player_id, "payments": derivatives.funding_history(player_id)}


@app.post("/api/positions")
def open_position(
    body: OpenPositionRequest,
    current: int = Depends(current_player_id),
    accept_language: str | None = Header(default=None),
):
    lang = request_lang(accept_language)
    try:
        position = derivatives.open_position(
            player_id=current,
            symbol=body.symbol,
            kind=body.kind,
            direction=body.direction,
            size=body.size,
            leverage=body.leverage,
            lang=lang,
        )
    except ValueError as exc:
        message = exc.text(lang) if hasattr(exc, "text") else str(exc)
        return JSONResponse(status_code=400, content={"ok": False, "message": message})

    direction = i18n.message(
        "deriv.long" if position["direction"] == "long" else "deriv.short", lang,
    )
    message = i18n.message(
        "deriv.opened", lang,
        direction=direction,
        size=f"{position['size']:g}",
        symbol=position["symbol"],
        leverage=f"{position['leverage']:g}",
        margin=f"{position['margin']:,.2f}",
    )
    return {"ok": True, "message": message, "position": _deriv_payload(position, lang)}


@app.post("/api/positions/{position_id}/close")
def close_position(
    position_id: int,
    current: int = Depends(current_player_id),
    accept_language: str | None = Header(default=None),
):
    lang = request_lang(accept_language)
    try:
        receipt = derivatives.close_position(
            player_id=current, position_id=position_id, lang=lang,
        )
    except ValueError as exc:
        message = exc.text(lang) if hasattr(exc, "text") else str(exc)
        return JSONResponse(status_code=400, content={"ok": False, "message": message})

    if receipt["realized_pl"] >= 0:
        result = f"+${receipt['realized_pl']:,.2f}"
    else:
        result = f"-${abs(receipt['realized_pl']):,.2f}"
    message = i18n.message(
        "deriv.closed", lang, symbol=receipt["symbol"],
        payout=f"{receipt['payout']:,.2f}", result=result,
    )
    return {"ok": True, "message": message, "receipt": receipt}


@app.post("/api/positions/{position_id}/margin")
def add_position_margin(
    position_id: int,
    body: AddMarginRequest,
    current: int = Depends(current_player_id),
    accept_language: str | None = Header(default=None),
):
    lang = request_lang(accept_language)
    try:
        position = derivatives.add_margin(
            player_id=current, position_id=position_id, amount=body.amount, lang=lang,
        )
    except ValueError as exc:
        message = exc.text(lang) if hasattr(exc, "text") else str(exc)
        return JSONResponse(status_code=400, content={"ok": False, "message": message})

    message = i18n.message(
        "deriv.marginAdded", lang,
        symbol=position["symbol"], amount=f"{body.amount:,.2f}",
    )
    return {"ok": True, "message": message, "position": _deriv_payload(position, lang)}


@app.post("/api/positions/monitor")
def run_position_monitor() -> dict:
    """Manual sweep, handy for testing liquidation without waiting for the loop."""
    return derivatives.monitor_positions()


# --- Dashboard: index, feed, season, reports ---------------------------------

@app.get("/api/dashboard")
def dashboard() -> dict:
    """Everything the exchange-style home screen needs in one round trip.

    Bundled so the board can poll a single endpoint instead of five; the whole
    payload is a few KB.
    """
    season = seasons.current_season()
    return {
        "season": season,
        "index": {
            "series": snapshots.index_series(hours=24, points=180),
            "value": _latest_index_value(),
        },
        "feed": activity.feed(limit=30),
        "leaderboard": get_leaderboard(),
        "season_history": seasons.history(limit=5),
        "assets": [],
        "as_of": int(time.time()),
    }


def _latest_index_value() -> dict | None:
    series = snapshots.index_series(hours=24, points=2)
    if not series:
        return None
    last = series[-1]
    first = series[0]
    change = (last["v"] / first["v"] - 1.0) * 100.0 if first["v"] else 0.0
    return {"value": round(last["v"], 2), "change_pct": round(change, 2), "ts": last["t"]}


@app.get("/api/index/series")
def index_series(hours: int = Query(default=24), points: int = Query(default=180)) -> dict:
    return {"series": snapshots.index_series(hours=hours, points=points)}


@app.get("/api/sparklines")
def sparklines(hours: int = Query(default=24), points: int = Query(default=30)) -> dict:
    return {"sparklines": snapshots.sparklines(hours=hours, points=points)}


@app.get("/api/activity")
def activity_feed(
    limit: int = Query(default=40),
    since_id: int | None = Query(default=None),
) -> dict:
    events = activity.feed(limit=limit, since_id=since_id)
    return {"events": events, "as_of": int(time.time())}


@app.get("/api/alerts")
def alerts(
    current: int = Depends(current_player_id),
    since: int | None = Query(default=None),
) -> dict:
    events = activity.alerts_for(current, limit=20, since=since)
    return {"alerts": events, "unseen": activity.unseen_count(current, since or 0)}


@app.get("/api/players/{player_id}/equity")
def player_equity(
    player_id: int,
    current: int = Depends(current_player_id),
    hours: int = Query(default=168),
    accept_language: str | None = Header(default=None),
) -> dict:
    lang = request_lang(accept_language)
    if player_id != current:
        raise AuthError(i18n.message("auth.wrongAccount", lang), 403)
    return {"player_id": player_id, "series": snapshots.equity_series(player_id, hours=hours)}


@app.get("/api/players/{player_id}/report")
def player_report(
    player_id: int,
    current: int = Depends(current_player_id),
    hours: int = Query(default=24),
    accept_language: str | None = Header(default=None),
) -> dict:
    """Daily report: how the book moved, what was traded, what went wrong."""
    lang = request_lang(accept_language)
    if player_id != current:
        raise AuthError(i18n.message("auth.wrongAccount", lang), 403)
    end = int(time.time())
    start = end - hours * 3600
    return snapshots.daily_report(player_id, day_start=start, day_end=end)


@app.get("/api/seasons/current")
def season_current() -> dict:
    season = seasons.current_season()
    if season is None:
        return {"season": None, "leaderboard": []}
    results = seasons.results(int(season["id"])) if season["status"] == "closed" else []
    return {"season": season, "results": results, "leaderboard": get_leaderboard()}


@app.get("/api/seasons/history")
def season_history(limit: int = Query(default=10)) -> dict:
    return {"seasons": seasons.history(limit=limit)}


@app.post("/api/seasons/rollover")
def season_rollover() -> dict:
    """Force the season to end now. Used to test the reset without waiting a week."""
    season = seasons.current_season()
    if season is None:
        return {"ok": False, "message": "No active season"}
    return {"ok": True, "result": seasons.close_season(int(season["id"]))}


@app.post("/api/snapshots/run")
def run_snapshot() -> dict:
    """Force one sampling pass (testing aid and manual refresh)."""
    season = seasons.current_season()
    return snapshots.sample_all(int(season["id"]) if season else None)


_WEB_DIR = Path(__file__).resolve().parents[1] / "web"
app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
