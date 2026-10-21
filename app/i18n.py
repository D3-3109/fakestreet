"""Server-side messages, matched to the locale the browser asks for.

Only strings that end up in front of a player live here. The API shapes stay
identical in both languages: callers get the same status codes and the same
`ok` flags, so the smoke test keeps working whichever locale is active.
"""
from __future__ import annotations

SUPPORTED = ("zh", "en")
DEFAULT = "en"

MESSAGES = {
    "en": {
        "auth.notSignedIn": "Not signed in",
        "auth.wrongAccount": "That's not your account",
        "auth.wrongCredentials": "Wrong username or password",
        "auth.wrongRecoveryWord": "That memorable word doesn't match",

        "register.noUsername": "Username is required",
        "register.usernameTooLong": "Username must be 40 characters or fewer",
        "register.usernameTaken": "Username already taken",
        "register.noRecoveryWord": "A memorable word is required",
        "register.passwordTooShort": "Password must be at least {min} characters",

        "player.notFound": "Player not found",

        "trade.unknownSymbol": "Unknown symbol: {symbol}",
        "trade.badQuantity": "Quantity must be greater than 0",
        "trade.badSide": "Side must be buy or sell",
        "trade.noPrice": "No price available for {symbol} right now",
        "trade.insufficientFunds": "Insufficient funds: need ${needed}, have ${cash}",
        "trade.insufficientHolding": "Insufficient {symbol}: you hold {held}, tried to sell {wanted}",
        "trade.bought": "Bought {quantity} {symbol} @ ${price}",
        "trade.sold": "Sold {quantity} {symbol} @ ${price}",
        "trade.coveredShort": "Bought {quantity} {symbol} @ ${price} to cover a short",
        "trade.shortOpened": "Shorted {quantity} {symbol} @ ${price}",
        "trade.shortLimit": "Short position too large: ${wanted} of exposure, limit ${limit}",

        "asset.badClass": "Pick stock, crypto, or fiat",
        "asset.unknownSymbol": "Unknown symbol: {symbol}",
        "asset.noSymbol": "Symbol is required",
        "asset.badSymbol": "Symbol must be 12 characters or fewer and use only A-Z, 0-9, dots, or hyphens",
        "asset.alreadyInGame": "{symbol} is already in the game",
        "asset.stockNotFound": "Couldn't find a stock with ticker {symbol}",
        "asset.missingProvider": "CoinGecko provider_id is required",
        "asset.coinNotFound": "Couldn't find that coin on CoinGecko — use search to find it",
        "asset.unsupportedCurrency": "{symbol} isn't a supported currency",

        "deriv.unknownSymbol": "Unknown symbol: {symbol}",
        "deriv.badKind": "Position type must be perp or future",
        "deriv.badDirection": "Direction must be long or short",
        "deriv.badSize": "Size must be greater than 0",
        "deriv.badLeverage": "Leverage must be at least 1",
        "deriv.marginTooSmall": "Margin ${margin} is below the ${min} minimum — raise the size or lower the leverage",
        "deriv.badAmount": "Amount must be greater than 0",
        "deriv.noPrice": "No price available for {symbol} right now",
        "deriv.insufficientMargin": "Not enough cash for margin: need ${needed}, have ${cash}",
        "deriv.insufficientCash": "Not enough cash: need ${needed}, have ${cash}",
        "deriv.positionGone": "That position is already closed",
        "deriv.opened": "Opened {direction} {size} {symbol} at {leverage}x, margin ${margin}",
        "deriv.closed": "Closed {symbol} for ${payout} ({result})",
        "deriv.liquidated": "Liquidated {symbol}: lost ${lost} of margin",
        "deriv.expired": "Future {symbol} settled at ${price} ({result})",
        "deriv.marginAdded": "Added ${amount} margin to {symbol}",
        "deriv.long": "long",
        "deriv.short": "short",
    },
    "zh": {
        "auth.notSignedIn": "尚未登录",
        "auth.wrongAccount": "这不是你的账号",
        "auth.wrongCredentials": "用户名或密码错误",
        "auth.wrongRecoveryWord": "记忆词不匹配",

        "register.noUsername": "请填写交易员昵称",
        "register.usernameTooLong": "昵称不能超过 40 个字符",
        "register.usernameTaken": "该昵称已被占用",
        "register.noRecoveryWord": "请填写记忆词",
        "register.passwordTooShort": "密码至少需要 {min} 个字符",

        "player.notFound": "找不到该玩家",

        "trade.unknownSymbol": "未知标的：{symbol}",
        "trade.badQuantity": "数量必须大于 0",
        "trade.badSide": "交易方向必须是买入或卖出",
        "trade.noPrice": "暂时获取不到 {symbol} 的价格",
        "trade.insufficientFunds": "资金不足：需要 ${needed}，当前有 ${cash}",
        "trade.insufficientHolding": "{symbol} 持仓不足：当前持有 {held}，尝试卖出 {wanted}",
        "trade.bought": "已买入 {quantity} {symbol}，成交价 ${price}",
        "trade.sold": "已卖出 {quantity} {symbol}，成交价 ${price}",
        "trade.coveredShort": "已买入 {quantity} {symbol} 平空，成交价 ${price}",
        "trade.shortOpened": "已做空 {quantity} {symbol}，成交价 ${price}",
        "trade.shortLimit": "空头敞口过大：${wanted}，上限 ${limit}",

        "asset.badClass": "请选择股票、加密货币或外汇",
        "asset.unknownSymbol": "未知标的：{symbol}",
        "asset.noSymbol": "请填写标的代码",
        "asset.badSymbol": "标的代码不能超过 12 个字符，且只能包含 A-Z、0-9、点和连字符",
        "asset.alreadyInGame": "{symbol} 已经在市场中了",
        "asset.stockNotFound": "找不到代码为 {symbol} 的股票",
        "asset.missingProvider": "缺少 CoinGecko 的 provider_id",
        "asset.coinNotFound": "在 CoinGecko 上找不到该币种，请用搜索功能查找",
        "asset.unsupportedCurrency": "{code} 不是受支持的货币",

        "deriv.unknownSymbol": "未知标的：{symbol}",
        "deriv.badKind": "仓位类型必须是永续或期货",
        "deriv.badDirection": "方向必须是做多或做空",
        "deriv.badSize": "数量必须大于 0",
        "deriv.badLeverage": "杠杆必须大于等于 1",
        "deriv.marginTooSmall": "保证金 ${margin} 低于最低要求 ${min}——请加大数量或降低杠杆",
        "deriv.badAmount": "金额必须大于 0",
        "deriv.noPrice": "暂时获取不到 {symbol} 的价格",
        "deriv.insufficientMargin": "保证金不足：需要 ${needed}，当前有 ${cash}",
        "deriv.insufficientCash": "现金不足：需要 ${needed}，当前有 ${cash}",
        "deriv.positionGone": "该仓位已经平掉了",
        "deriv.opened": "已开仓：{direction} {size} {symbol}，{leverage} 倍杠杆，保证金 ${margin}",
        "deriv.closed": "已平仓 {symbol}，返还 ${payout}（{result}）",
        "deriv.liquidated": "{symbol} 已爆仓：损失保证金 ${lost}",
        "deriv.expired": "期货 {symbol} 已到期结算，结算价 ${price}（{result}）",
        "deriv.marginAdded": "已为 {symbol} 追加保证金 ${amount}",
        "deriv.long": "做多",
        "deriv.short": "做空",
    },
}


def resolve(accept_language: str | None) -> str:
    """Pick a supported locale from an Accept-Language header value."""
    if not accept_language:
        return DEFAULT
    # Good enough for "zh-CN,zh;q=0.9,en;q=0.8": take the first supported tag.
    for part in accept_language.split(","):
        tag = part.split(";")[0].strip().lower()
        if not tag:
            continue
        primary = tag.split("-")[0]
        if primary in SUPPORTED:
            return primary
    return DEFAULT


def message(key: str, lang: str = DEFAULT, **params) -> str:
    """Look up a message, falling back to English and then to the key itself."""
    table = MESSAGES.get(lang) or MESSAGES[DEFAULT]
    text = table.get(key) or MESSAGES[DEFAULT].get(key) or key
    if not params:
        return text
    try:
        return text.format(**params)
    except (KeyError, IndexError):
        return text


class ValidationError(ValueError):
    """A player-facing rejection that keeps its message key for the response.

    It subclasses ValueError so existing `except ValueError` handlers keep
    working; the key lets the API answer in whatever language was requested.
    Pass a language to `text()` when the request locale is only known at the
    response site, otherwise the one given at construction is used.
    """

    def __init__(self, key: str, lang: str = DEFAULT, **params) -> None:
        self.key = key
        self.lang = lang
        self.params = params
        super().__init__(self.text())

    def text(self, lang: str | None = None) -> str:
        return message(self.key, lang or self.lang, **self.params)
