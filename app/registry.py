"""Merged asset registry for built-in and user-added assets."""
from __future__ import annotations

import re
import sqlite3
import time

import config
from app import i18n
from app.db import get_conn
from app.providers import crypto, fiat, stocks

SYMBOL_RE = re.compile(r"^[A-Z0-9.-]+$")
ASSET_CLASSES = {"stock", "crypto", "fiat"}


def builtin_assets() -> list[dict]:
    return [dict(asset) for asset in config.ASSETS]


def custom_assets() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT symbol, name, asset_class, provider_id FROM custom_assets ORDER BY created_at, symbol"
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def all_assets() -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for asset in builtin_assets() + custom_assets():
        symbol = str(asset["symbol"]).upper()
        if symbol in seen:
            continue
        item = dict(asset)
        item["symbol"] = symbol
        out.append(item)
        seen.add(symbol)
    return out


def get_asset(symbol) -> dict | None:
    wanted = str(symbol or "").strip().upper()
    if not wanted:
        return None
    for asset in all_assets():
        if asset["symbol"].upper() == wanted:
            return dict(asset)
    return None


def custom_symbols() -> set[str]:
    return {asset["symbol"].upper() for asset in custom_assets()}


def create_custom_asset(
    asset_class,
    symbol,
    provider_id=None,
    name=None,
    added_by=None,
    lang: str = i18n.DEFAULT,
) -> dict:
    klass = str(asset_class or "").strip().lower()
    code = str(symbol or "").strip().upper()
    provider = str(provider_id or "").strip()
    display_name = str(name or "").strip()

    if not code:
        raise i18n.ValidationError("asset.noSymbol", lang)
    if len(code) > 12 or SYMBOL_RE.fullmatch(code) is None:
        raise i18n.ValidationError("asset.badSymbol", lang)
    if klass not in ASSET_CLASSES:
        raise i18n.ValidationError("asset.badClass", lang)
    if get_asset(code) is not None:
        raise i18n.ValidationError("asset.alreadyInGame", lang, symbol=code)

    if klass == "stock":
        provider = code
        quotes = stocks.get_quotes([provider])
        if provider not in quotes:
            raise i18n.ValidationError("asset.stockNotFound", lang, symbol=code)
        if not display_name:
            display_name = _stock_name(code)
    elif klass == "crypto":
        if not provider:
            raise i18n.ValidationError("asset.missingProvider", lang)
        quotes = crypto.get_quotes([provider])
        if provider not in quotes:
            raise i18n.ValidationError("asset.coinNotFound", lang)
        if not display_name:
            display_name = _crypto_name(code, provider)
    else:
        provider = code
        supported = fiat.supported()
        if code not in supported:
            raise i18n.ValidationError("asset.unsupportedCurrency", lang, code=code)
        display_name = display_name or supported[code]

    display_name = display_name or code
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO custom_assets (symbol, name, asset_class, provider_id, added_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (code, display_name, klass, provider, added_by, int(time.time())),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise i18n.ValidationError("asset.alreadyInGame", lang, symbol=code)
    finally:
        conn.close()

    return {"symbol": code, "name": display_name, "asset_class": klass, "provider_id": provider}


def _stock_name(symbol: str) -> str:
    for row in stocks.search(symbol):
        if row.get("symbol", "").upper() == symbol:
            return row.get("name") or symbol
    return symbol


def _crypto_name(symbol: str, provider_id: str) -> str:
    for row in crypto.search(provider_id):
        if row.get("provider_id") == provider_id or row.get("symbol", "").upper() == symbol:
            return row.get("name") or symbol
    return symbol
