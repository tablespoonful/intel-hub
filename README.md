# intel-hub

個人向け AI/テクノロジー × 金融マーケットの情報インテリジェンス基盤。
**月額 $0** で運用できることを最優先に設計 (Cloudflare Workers/D1/Workers AI + GitHub Actions の無料枠のみ)。

```text
収集 → 正規化 → 重複排除 → ルールベース評価 → 重要候補抽出 → AI評価 → イベント化
     → 技術情報と市場情報を関連付け → Dashboard / API
```

- 対象: 米・中・日の LLM / Agent / Physical AI / Robotics 動向 + FX・株価指数・金利・BTC・マクロ指標
- 情報源: 公式ブログ RSS / GitHub / Hugging Face / arXiv / Hacker News / YouTube /
  FRED / SEC EDGAR / BOJ / Fed / Frankfurter / Coinbase (詳細: [docs/data-sources.md](docs/data-sources.md))
- アーキテクチャ: [docs/architecture.md](docs/architecture.md) /
  無料枠設計: [docs/free-tier.md](docs/free-tier.md) /
  制約: [docs/limitations.md](docs/limitations.md) /
  運用: [docs/operations.md](docs/operations.md)

## クイックスタート (ローカル)

前提: Python 3.12+ / Node.js 18+ (Worker 開発時のみ)

### Windows PowerShell

```powershell
# セットアップ
py -m pip install -e ".[dev]"

# テスト (実 API は呼ばない)
py -m pytest

# 収集をローカル SQLite (data/intel.db) へ
py -m scripts.run_collectors --tier fast --sink sqlite     # HN + 中銀RSS + 市場価格
py -m scripts.run_collectors --tier normal --sink sqlite   # 公式ブログ + GitHub + HF
py -m scripts.run_collectors --tier slow --sink sqlite     # arXiv + YouTube + FRED + SEC

# config 変更後の再スコアリング
py -m scripts.rescore
```

### make が使える環境 (macOS / Linux / Git Bash)

```bash
make setup    # pip install -e ".[dev]"
make test     # pytest
make collect  # 全 tier をローカル SQLite へ
make score    # 再スコアリング
make dev      # worker をローカル起動 (wrangler dev)
```

API キーは `.env` に置く (`.env.example` をコピー)。**キーが無い collector は自動スキップ**されるので、
何も設定しなくても RSS / GitHub / arXiv / HN / FX / BTC は動く。

## デプロイ (すべて無料枠)

[docs/operations.md](docs/operations.md) の手順どおり:

1. `wrangler d1 create intel-hub` → `wrangler.toml` に database_id を設定
2. `wrangler d1 execute intel-hub --remote --file=../db/schema.sql`
3. `wrangler secret put INGEST_TOKEN` → `wrangler deploy`
4. GitHub Secrets (`INTEL_HUB_INGEST_URL` 等) を設定 → Actions が fast/normal/slow の3系統で自動収集

Dashboard は Worker の URL 直下 (`/`)。API は `/api/events`, `/api/technology`,
`/api/markets`, `/api/papers`, `/api/repos`, `/api/models`, `/api/health`。

## 設定ファイル

| ファイル | 内容 |
|---|---|
| `config/sources.yaml` | 監視対象 (RSS / GitHub repos / HF keywords / arXiv / HN / YouTube / SEC) |
| `config/topics.yaml` | トピック定義・キーワード・event_type ヒント |
| `config/entities.yaml` | エンティティ統一辞書 (企業 → ticker) |
| `config/markets.yaml` | 市場シンボル ↔ provider マッピング |
| `config/scoring.yaml` | スコア重み・AI 送信閾値 |

監視対象の追加は YAML に追記するだけ。コード変更は不要。

## 注意

- 無料市場データは**監視・分析用途限定**。自動売買の約定判断には使わない。
- 外部コンテンツ (記事・README 等) 内の命令文はデータとして扱う (プロンプトインジェクション対策は worker/src/ai.ts 参照)。
