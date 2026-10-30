-- intel-hub schema (Cloudflare D1 / SQLite 互換)
-- raw_items と正規化後テーブルを分離し、外部仕様変更時の再処理を可能にする。

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
  id            TEXT PRIMARY KEY,           -- 例: openai-news, github, arxiv
  name          TEXT NOT NULL,
  method        TEXT NOT NULL,              -- rss | api | none
  url           TEXT,
  country       TEXT,
  language      TEXT,
  category      TEXT,
  quality       REAL DEFAULT 0.5,
  tier          TEXT DEFAULT 'normal',      -- fast | normal | slow
  enabled       INTEGER DEFAULT 1,
  created_at    TEXT DEFAULT (datetime('now')),
  updated_at    TEXT DEFAULT (datetime('now'))
);

-- 生データ。payload_json に取得時のレスポンス断片を保持し再処理可能にする。
CREATE TABLE IF NOT EXISTS raw_items (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id     TEXT NOT NULL REFERENCES sources(id),
  external_id   TEXT NOT NULL,              -- ソース内で一意なID (guid / repo full_name / arxiv id ...)
  kind          TEXT NOT NULL,              -- article | paper | repo | model | video | hn | filing
  url           TEXT,
  title         TEXT,
  published_at  TEXT,                       -- ISO8601 UTC
  fetched_at    TEXT NOT NULL,
  country       TEXT,
  language      TEXT,
  category      TEXT,
  tags          TEXT,                       -- JSON array
  raw_hash      TEXT NOT NULL,              -- content hash (dedupe)
  payload_json  TEXT,
  UNIQUE (source_id, external_id)
);
CREATE INDEX IF NOT EXISTS idx_raw_items_hash ON raw_items(raw_hash);
CREATE INDEX IF NOT EXISTS idx_raw_items_published ON raw_items(published_at);

-- 正規化済み記事 (RSS / HN / 公式ニュース / macro発表)
CREATE TABLE IF NOT EXISTS articles (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  raw_item_id    INTEGER REFERENCES raw_items(id),
  source_id      TEXT NOT NULL REFERENCES sources(id),
  external_id    TEXT NOT NULL,
  url            TEXT,
  canonical_url  TEXT,
  title          TEXT NOT NULL,
  normalized_title TEXT NOT NULL,
  summary        TEXT,
  published_at   TEXT,
  fetched_at     TEXT NOT NULL,
  country        TEXT,
  language       TEXT,
  category       TEXT,
  tags           TEXT,
  topics         TEXT,                      -- JSON array of matched topic ids
  score          REAL DEFAULT 0,
  score_components TEXT,                    -- JSON breakdown
  ai_status      TEXT DEFAULT 'none',       -- none | pending | done | failed
  dedupe_of      INTEGER REFERENCES articles(id),
  created_at     TEXT DEFAULT (datetime('now')),
  UNIQUE (source_id, external_id)
);
CREATE INDEX IF NOT EXISTS idx_articles_score ON articles(score DESC);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_ai ON articles(ai_status, score DESC);

CREATE TABLE IF NOT EXISTS papers (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  raw_item_id   INTEGER REFERENCES raw_items(id),
  arxiv_id      TEXT NOT NULL UNIQUE,
  url           TEXT,
  title         TEXT NOT NULL,
  abstract      TEXT,
  authors       TEXT,                       -- JSON array
  categories    TEXT,                       -- JSON array
  published_at  TEXT,
  updated_at    TEXT,
  fetched_at    TEXT NOT NULL,
  topics        TEXT,
  score         REAL DEFAULT 0,
  ai_status     TEXT DEFAULT 'none'
);
CREATE INDEX IF NOT EXISTS idx_papers_score ON papers(score DESC);

CREATE TABLE IF NOT EXISTS repositories (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  full_name     TEXT NOT NULL UNIQUE,       -- owner/repo
  url           TEXT,
  description   TEXT,
  language      TEXT,
  topics        TEXT,
  latest_release     TEXT,
  release_published_at TEXT,
  stars         INTEGER DEFAULT 0,
  forks         INTEGER DEFAULT 0,
  open_issues   INTEGER DEFAULT 0,
  pushed_at     TEXT,
  fetched_at    TEXT NOT NULL,
  score         REAL DEFAULT 0
);

-- 差分計算用スナップショット (stars_24h_delta / stars_7d_delta)
CREATE TABLE IF NOT EXISTS repo_snapshots (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  full_name     TEXT NOT NULL,
  snapped_at    TEXT NOT NULL,
  stars         INTEGER,
  forks         INTEGER,
  open_issues   INTEGER,
  UNIQUE (full_name, snapped_at)
);
CREATE INDEX IF NOT EXISTS idx_repo_snap ON repo_snapshots(full_name, snapped_at DESC);

CREATE TABLE IF NOT EXISTS models (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  hf_id         TEXT NOT NULL UNIQUE,       -- org/model
  url           TEXT,
  author        TEXT,
  pipeline_tag  TEXT,
  tags          TEXT,
  downloads     INTEGER DEFAULT 0,
  likes         INTEGER DEFAULT 0,
  hf_created_at TEXT,
  hf_updated_at TEXT,
  fetched_at    TEXT NOT NULL,
  score         REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS videos (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id      TEXT NOT NULL UNIQUE,
  channel_id    TEXT,
  channel_name  TEXT,
  url           TEXT,
  title         TEXT,
  description   TEXT,
  published_at  TEXT,
  fetched_at    TEXT NOT NULL,
  country       TEXT,
  score         REAL DEFAULT 0
);

-- ---------------- markets ----------------

CREATE TABLE IF NOT EXISTS market_symbols (
  canonical     TEXT PRIMARY KEY,           -- USDJPY, SPX, NVDA, US10Y ...
  name          TEXT NOT NULL,
  asset         TEXT NOT NULL,              -- fx | index | equity | rate | commodity | crypto
  country       TEXT,
  providers     TEXT                        -- JSON {provider: provider_symbol}
);

CREATE TABLE IF NOT EXISTS market_prices (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol        TEXT NOT NULL REFERENCES market_symbols(canonical),
  ts            TEXT NOT NULL,              -- ISO8601 UTC (bar open time)
  interval      TEXT NOT NULL,              -- 1d | 15m | 5m ...
  open          REAL, high REAL, low REAL, close REAL,
  volume        REAL,
  provider      TEXT NOT NULL,
  UNIQUE (symbol, ts, interval, provider)
);
CREATE INDEX IF NOT EXISTS idx_prices_symbol_ts ON market_prices(symbol, interval, ts DESC);

CREATE TABLE IF NOT EXISTS macro_series (
  id            TEXT PRIMARY KEY,           -- FRED series id 等
  name          TEXT,
  source        TEXT,                       -- fred | boj | ...
  unit          TEXT,
  country       TEXT
);

CREATE TABLE IF NOT EXISTS macro_values (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  series_id     TEXT NOT NULL REFERENCES macro_series(id),
  date          TEXT NOT NULL,
  value         REAL,
  fetched_at    TEXT NOT NULL,
  UNIQUE (series_id, date)
);

-- ---------------- events ----------------

CREATE TABLE IF NOT EXISTS events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type    TEXT NOT NULL,              -- model_release | funding | ... (docs参照)
  title         TEXT NOT NULL,
  summary       TEXT,
  occurred_at   TEXT NOT NULL,
  country       TEXT,
  importance    REAL DEFAULT 0,             -- 0-100
  topics        TEXT,                       -- JSON array
  source_count  INTEGER DEFAULT 1,
  created_at    TEXT DEFAULT (datetime('now')),
  UNIQUE (event_type, title, occurred_at)
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(occurred_at DESC);

CREATE TABLE IF NOT EXISTS event_entities (
  event_id      INTEGER NOT NULL REFERENCES events(id),
  entity_id     TEXT NOT NULL,              -- entities.yaml の id
  role          TEXT DEFAULT 'subject',
  PRIMARY KEY (event_id, entity_id)
);

-- イベント前後の価格変化 (将来 Worker 側で計算して埋める)
CREATE TABLE IF NOT EXISTS event_market_reactions (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id      INTEGER NOT NULL REFERENCES events(id),
  symbol        TEXT NOT NULL,
  window        TEXT NOT NULL,              -- -15m | +15m | +1h | +4h | +1d
  price_before  REAL,
  price_after   REAL,
  change_pct    REAL,
  computed_at   TEXT,
  UNIQUE (event_id, symbol, window)
);

-- ---------------- AI ----------------

CREATE TABLE IF NOT EXISTS ai_scores (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  target_kind   TEXT NOT NULL,              -- article | paper
  target_id     INTEGER NOT NULL,
  model         TEXT,
  summary_ja    TEXT,
  importance    REAL,
  novelty       REAL,
  category      TEXT,
  country       TEXT,
  entities      TEXT,                       -- JSON array
  why_it_matters TEXT,
  market_relevance REAL,
  technology_relevance REAL,
  raw_response  TEXT,
  created_at    TEXT DEFAULT (datetime('now')),
  UNIQUE (target_kind, target_id)
);

-- タイトルの日本語訳。Worker の毎時 cron が Workers AI で埋める。原文は各テーブルが正で、
-- source_title が原文と変わったら訳し直す。
CREATE TABLE IF NOT EXISTS title_translations (
  target_kind   TEXT NOT NULL,              -- event | article | paper
  target_id     INTEGER NOT NULL,
  lang          TEXT NOT NULL DEFAULT 'ja',
  source_title  TEXT NOT NULL,              -- 訳したときの原文
  title         TEXT NOT NULL,
  model         TEXT,                       -- 翻訳モデル。元から日本語なら 'source'
  created_at    TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (target_kind, target_id, lang)
);

CREATE TABLE IF NOT EXISTS digests (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  digest_date   TEXT NOT NULL,
  kind          TEXT DEFAULT 'daily',
  content_md    TEXT,
  created_at    TEXT DEFAULT (datetime('now')),
  UNIQUE (digest_date, kind)
);

-- ---------------- observability ----------------

CREATE TABLE IF NOT EXISTS collector_runs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  collector     TEXT NOT NULL,
  started_at    TEXT NOT NULL,
  finished_at   TEXT,
  status        TEXT DEFAULT 'running',     -- running | success | partial | failed
  fetched       INTEGER DEFAULT 0,
  inserted      INTEGER DEFAULT 0,
  duplicate     INTEGER DEFAULT 0,
  failed        INTEGER DEFAULT 0,
  error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_collector ON collector_runs(collector, started_at DESC);
