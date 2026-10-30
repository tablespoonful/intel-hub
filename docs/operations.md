# 運用手順

## 初回デプロイ

1. **Cloudflare アカウント準備** (無料プランで可)
   ```powershell
   cd worker
   npm install
   npx wrangler login
   ```
2. **D1 データベース作成**
   ```powershell
   npx wrangler d1 create intel-hub
   # 出力された database_id を worker/wrangler.toml の REPLACE_WITH_D1_ID に貼る
   npx wrangler d1 execute intel-hub --remote --file=../db/schema.sql
   ```
3. **ingest 用トークンを設定** (十分長いランダム文字列)
   ```powershell
   npx wrangler secret put INGEST_TOKEN
   ```
4. **デプロイ**
   ```powershell
   npx wrangler deploy
   # 表示された URL (https://intel-hub.<subdomain>.workers.dev) を控える
   ```
5. **GitHub リポジトリ設定** (public 推奨 — free-tier.md 参照)
   - Settings → Secrets and variables → Actions に登録:
     - `INTEL_HUB_INGEST_URL` : Worker の URL
     - `INTEL_HUB_INGEST_TOKEN` : 手順3と同じ値
     - `FRED_API_KEY` : fred.stlouisfed.org で無料発行
     - `SEC_EDGAR_USER_AGENT` : `"名前 連絡先メール"` 形式
     - `YOUTUBE_API_KEY` (任意), `HF_TOKEN` (任意)
   - push すると test workflow が走り、collect-* は schedule で動き始める
   - 初回は Actions タブから `collect-fast` 等を手動実行 (workflow_dispatch) して確認

## 継続デプロイ (GitHub Actions)

初回デプロイ後は `.github/workflows/deploy.yml` が Worker を更新するので、手元の PC は不要。

- `main` に `worker/**`・`db/schema.sql`・`deploy.yml` の変更が入ると自動実行。Actions タブから手動実行 (workflow_dispatch) も可
- 手順: 型チェック → (`db/schema.sql` が変わったときだけ) D1 に適用 → `wrangler deploy`
  - スキーマ適用中は D1 がクエリを受け付けないため、毎回は流さない。push 前後の差分に `db/schema.sql` が含まれるときだけ適用する
  - 手動実行では `apply_schema` にチェックを入れたときだけ適用する (スキーマは `IF NOT EXISTS` のみなので何度流しても安全)
- `INGEST_TOKEN` など Worker の secret は `wrangler deploy` で消えない (再設定不要)
- 必要な GitHub Secrets:
  - `CLOUDFLARE_API_TOKEN` : dash.cloudflare.com → My Profile → API Tokens → 「Edit Cloudflare Workers」テンプレートに
    **Account / D1 / Edit** の権限を追加して作成
  - `CLOUDFLARE_ACCOUNT_ID` : Workers & Pages の画面に表示されるアカウント ID
- Worker の URL はジョブログの `Deploy Worker` ステップ末尾に出る

## 日常の確認

- **Dashboard**: Worker URL を開く (NOW / AI / Market / Papers / GitHub)
  - アプリとして使う: PC は Edge/Chrome のアドレスバーの「インストール」、iPhone は Safari の共有 →「ホーム画面に追加」
  - オフライン時は最後に表示したタブのデータを「オフライン: 保存済みのデータを表示しています」付きで表示する
- **ヘルスチェック**: `GET /api/health`
  - `last_runs` : collector ごとの最終実行
  - `failure_count_24h` : 直近24時間の失敗数
  - `stale` : 24時間以上成功していない collector → Actions のログを確認
- **Workers AI の消費**: Cloudflare ダッシュボード → AI → 使用量 (10,000 Neurons/日)

## よくある対応

| 症状 | 対応 |
|---|---|
| ある RSS feed が 404 | サイト側の URL 変更。sources.yaml を修正 (直らなければ `enabled: false`) |
| GitHub collector が rate limit | Actions 内では GITHUB_TOKEN が自動付与されるので通常発生しない。ローカルでは PAT を .env に設定 |
| ai_status = pending が溜まる | Workers AI 障害 or Neurons 枯渇。cron が翌日以降自動で再試行するので放置でよい |
| schedule が止まった | 60日 push なしで自動停止。Actions タブから re-enable + 軽微な commit |
| D1 write 上限が近い | collect 頻度を下げる (workflows の cron を編集) |

## ローカル開発

```powershell
py -m pip install -e ".[dev]"          # セットアップ
py -m pytest                            # テスト
py -m scripts.run_collectors --tier fast --sink sqlite   # ローカル収集 (data/intel.db)
py -m scripts.rescore                   # config 変更後の再スコア
cd worker; npx wrangler dev             # Worker をローカル起動 (http://localhost:8787)
```

ローカル Worker に流し込む場合は `.dev.vars` に `INGEST_TOKEN=...` を書き、
`.env` の `INTEL_HUB_INGEST_URL=http://localhost:8787` を設定して `--sink worker`。
