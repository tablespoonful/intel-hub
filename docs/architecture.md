# intel-hub アーキテクチャ

## 全体像

```text
┌────────────────────────────── GitHub Actions (無料枠) ──────────────────────────────┐
│  fast (毎時17分)          normal (2時間毎)              slow (6時間毎)               │
│  ├ Hacker News            ├ RSS (公式ブログ)            ├ arXiv                      │
│  ├ BOJ / Fed RSS          ├ GitHub repos                ├ YouTube (uploads playlist) │
│  └ 市場価格               └ Hugging Face                ├ FRED / SEC EDGAR           │
│    (Frankfurter/FRED/                                   └ RSS (slow tier)            │
│     Coinbase)                                                                        │
│            │ Python: collect → normalize → dedupe → score → events                   │
└────────────┼─────────────────────────────────────────────────────────────────────────┘
             │  POST /api/ingest  (Bearer INGEST_TOKEN)
             ▼
┌──────────────── Cloudflare Workers (無料枠) ────────────────┐
│  Worker (TypeScript)                                        │
│  ├ /api/ingest   : upsert (D1)                              │
│  ├ /api/*        : 参照 API (events/technology/markets/...) │
│  ├ /             : Dashboard (自己完結 HTML, PWA)           │
│  ├ /sw.js 等     : PWA 資産 (manifest, Service Worker, icon)│
│  └ scheduled cron: Workers AI 評価 (1日2回, 上位20件のみ)   │
│                    │                                        │
│                    ▼                                        │
│                Cloudflare D1 (SQLite)                       │
└─────────────────────────────────────────────────────────────┘
```

## パイプライン

```text
収集 (collectors/*)
 ↓ RawItem (payload に生レスポンス断片を保持)
正規化 (pipeline/normalize)   … title クリーニング / canonical URL / UTC / 言語推定
 ↓ NormalizedItem
重複排除 (pipeline/dedupe)    … external_id / raw_hash / canonical URL / タイトル類似度
 ↓                              (クロスランの重複は D1 の UNIQUE 制約で吸収)
ルールベース評価 (pipeline/scoring)
 ↓ score 0-100 = recency + source_quality + relevance + velocity + popularity + novelty
重要候補抽出                  … score >= ai_threshold → ai_status = pending
 ↓
AI評価 (worker/src/ai.ts)     … Workers AI (JSON Schema 強制) → ai_scores
 ↓
イベント化 (pipeline/events)  … entity 照合 + event_type 推定 → events / event_entities
 ↓
技術×市場の関連付け           … events → event_entities → entities.yaml tickers
 ↓                              → market_symbols → market_prices (event_market_reactions)
Dashboard / API
```

## 設計判断

- **Python collectors は stateless**。GitHub Actions 上で毎回クリーンに走り、
  結果を Worker へ POST する。ローカル開発では同一スキーマの SQLite に書ける (`--sink sqlite`)。
- **raw_items と正規化後テーブルを分離**。外部 API の仕様変更時も raw_items の
  payload_json から再処理できる (`scripts/rescore.py` が再スコアの実例)。
- **dedupe は 2 層**: バッチ内はタイトル類似度まで見る Python、バッチ間 (過去分) は
  D1 の UNIQUE 制約 (`INSERT OR IGNORE`)。embedding DB は導入しない。
- **AI は最後段のみ**。ルールベーススコアの上位 (`ai_threshold` 以上、1回最大20件) だけを
  Workers AI に渡す。AI が落ちても `ai_status = pending` のまま再試行可能で、
  システム全体は AI なしで動作する。
- **stars の増加速度**は repo_snapshots (取得ごとのスナップショット) から
  Worker の SQL で `stars_24h_delta` / `stars_7d_delta` を読み出し時に計算する。
- **市場データは Provider Adapter** (`MarketDataProvider`)。
  free provider (Frankfurter / FRED / Coinbase) → broker API → 有料 realtime へ
  markets.yaml の書き換えだけで差し替え可能。
- **イベント→市場の接続**: `events → event_entities → entities.yaml の tickers →
  market_symbols → market_prices` と辿れる。`event_market_reactions` (-15m/+15m/+1h/+4h/+1d)
  はスキーマとテーブルを用意済みで、計算ロジックは Phase 3+ (docs/limitations.md)。

## ディレクトリ

```text
collectors/   情報源ごとの取得 (fetch と pure parse を分離、テストは parse のみ叩く)
pipeline/     normalize / dedupe / scoring / events / ai (JSON Schema 契約)
worker/       Cloudflare Worker (API + ingest + Workers AI + Dashboard)
db/           schema.sql (D1/SQLite 共通の正)
config/       sources / topics / entities / markets / scoring (すべて YAML で差し替え可)
scripts/      runner / sinks / rescore / .env ローダ
tests/        fixture ベース (実 API は呼ばない)
.github/      collect-fast / collect-normal / collect-slow / test
docs/         本書 / data-sources / free-tier / limitations / operations / dev-spec
```
