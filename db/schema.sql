-- Trading game schema. All monetary values are USD.
-- Safe to run repeatedly; every statement is IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS players (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    cash          REAL    NOT NULL,
    created_at    INTEGER NOT NULL,
    password_hash TEXT,                  -- PBKDF2 string, null only for legacy rows
    recovery_hash TEXT                   -- PBKDF2 hash of the normalized memorable word
);

-- Session tokens issued on login/register/recover. A player may have several
-- (e.g. phone + laptop); logout deletes one, a password reset can clear them all.
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    player_id  INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (player_id) REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS holdings (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    symbol    TEXT    NOT NULL,
    quantity  REAL    NOT NULL,          -- units held (may be fractional)
    avg_cost  REAL    NOT NULL,          -- average USD cost basis per unit
    UNIQUE(player_id, symbol),
    FOREIGN KEY (player_id) REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    symbol    TEXT    NOT NULL,
    side      TEXT    NOT NULL,          -- 'buy' or 'sell'
    quantity  REAL    NOT NULL,
    price     REAL    NOT NULL,          -- USD per unit at execution
    total     REAL    NOT NULL,          -- USD value of the trade
    ts        INTEGER NOT NULL,
    FOREIGN KEY (player_id) REFERENCES players(id)
);

-- Optional persistent price cache the market layer may use to survive restarts
-- and to fall back on when a provider is unreachable.
CREATE TABLE IF NOT EXISTS price_cache (
    symbol     TEXT PRIMARY KEY,
    price      REAL NOT NULL,            -- USD
    prev_close REAL,                     -- USD, for daily change %
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS custom_assets (
    symbol      TEXT PRIMARY KEY,
    name        TEXT    NOT NULL,
    asset_class TEXT    NOT NULL,       -- 'stock' | 'crypto' | 'fiat'
    provider_id TEXT    NOT NULL,
    added_by    INTEGER,                -- player id, nullable
    created_at  INTEGER NOT NULL
);

-- Leveraged derivative positions. One row is one position; it is always opened
-- and closed as a whole, which keeps liquidation arithmetic unambiguous.
--
--   kind        'perp' (no expiry) | 'future' (settles at expires_at)
--   direction   'long' | 'short'
--   size        units of the underlying (fractional allowed)
--   multiplier  notional = size * entry_price * multiplier
--   leverage    notional / margin
--   margin      cash locked from the player; the most this row can lose
--   entry_price underlying price when opened
--   funding_paid running total of funding credited(+)/charged(-) to the player
--
-- Isolated margin: losses beyond `margin` are impossible because the row is
-- liquidated before equity goes negative.
CREATE TABLE IF NOT EXISTS positions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id    INTEGER NOT NULL,
    symbol       TEXT    NOT NULL,
    kind         TEXT    NOT NULL,       -- 'perp' | 'future'
    direction    TEXT    NOT NULL,       -- 'long' | 'short'
    size         REAL    NOT NULL,
    multiplier   REAL    NOT NULL,
    leverage     REAL    NOT NULL,
    margin       REAL    NOT NULL,       -- USD locked
    entry_price  REAL    NOT NULL,       -- USD per unit of underlying
    funding_paid REAL    NOT NULL DEFAULT 0,
    opened_at    INTEGER NOT NULL,
    expires_at   INTEGER,                -- null for perps, unix ts for futures
    closed_at    INTEGER,                -- null while open
    close_price  REAL,                   -- settlement price, null while open
    close_reason TEXT,                   -- 'manual' | 'liquidated' | 'expired'
    realized_pl  REAL,                   -- net USD result, null while open
    FOREIGN KEY (player_id) REFERENCES players(id)
);

-- Running funding ledger so the game can show what the carry actually cost.
CREATE TABLE IF NOT EXISTS funding_payments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id  INTEGER NOT NULL,
    player_id    INTEGER NOT NULL,
    rate         REAL    NOT NULL,       -- applied rate, positive = longs pay
    amount       REAL    NOT NULL,       -- USD credited(+)/charged(-)
    price        REAL    NOT NULL,
    ts           INTEGER NOT NULL,
    FOREIGN KEY (position_id) REFERENCES positions(id)
);

-- Seasons: a fixed window everyone competes in. On rollover the winner is
-- archived to season_results and every account resets to the starting cash so
-- someone who joined late is not permanently behind.
CREATE TABLE IF NOT EXISTS seasons (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    starts_at  INTEGER NOT NULL,
    ends_at    INTEGER NOT NULL,
    status     TEXT    NOT NULL,        -- 'active' | 'closed'
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS season_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id       INTEGER NOT NULL,
    player_id       INTEGER NOT NULL,
    username        TEXT    NOT NULL,
    final_net_worth REAL    NOT NULL,
    return_pct      REAL    NOT NULL,
    rank            INTEGER NOT NULL,
    trades          INTEGER NOT NULL DEFAULT 0,
    liquidations    INTEGER NOT NULL DEFAULT 0,
    created_at      INTEGER NOT NULL
);

-- Periodic snapshot of each player's book. This is the only place past equity
-- is stored, so every chart and daily report is derived from it.
CREATE TABLE IF NOT EXISTS equity_snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id        INTEGER NOT NULL,
    season_id        INTEGER,
    ts               INTEGER NOT NULL,
    net_worth        REAL    NOT NULL,
    cash             REAL    NOT NULL,
    holdings_value   REAL    NOT NULL,
    positions_equity REAL    NOT NULL,
    return_pct       REAL    NOT NULL
);

-- Raw price samples. Feeds the market index, the sparklines, and the daily
-- price movement shown on the dashboard.
CREATE TABLE IF NOT EXISTS price_snapshots (
    symbol TEXT    NOT NULL,
    ts     INTEGER NOT NULL,
    price  REAL    NOT NULL,
    PRIMARY KEY (symbol, ts)
);

-- Equal-weighted index over every tradable symbol, rebased to 1000 at the
-- first sample. Gives the dashboard one honest line to chart.
CREATE TABLE IF NOT EXISTS index_snapshots (
    ts         INTEGER PRIMARY KEY,
    value      REAL    NOT NULL,
    change_pct REAL    NOT NULL
);

-- Event log: the live feed, the personal alert bell, and season storytelling
-- all read from here. `detail` is JSON so the client can localize each event
-- instead of the server baking in one language.
CREATE TABLE IF NOT EXISTS activity (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        INTEGER NOT NULL,
    player_id INTEGER,
    kind      TEXT    NOT NULL,
    symbol    TEXT,
    amount    REAL,
    detail    TEXT,
    season_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_holdings_player ON holdings(player_id);
CREATE INDEX IF NOT EXISTS idx_tx_player       ON transactions(player_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_player ON sessions(player_id);
CREATE INDEX IF NOT EXISTS idx_positions_open   ON positions(player_id, closed_at);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol, closed_at);
CREATE INDEX IF NOT EXISTS idx_funding_position ON funding_payments(position_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_equity_player     ON equity_snapshots(player_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_equity_season     ON equity_snapshots(season_id, ts);
CREATE INDEX IF NOT EXISTS idx_price_symbol      ON price_snapshots(symbol, ts DESC);
CREATE INDEX IF NOT EXISTS idx_activity_ts       ON activity(ts DESC);
CREATE INDEX IF NOT EXISTS idx_activity_player   ON activity(player_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_season_results    ON season_results(season_id, rank);
