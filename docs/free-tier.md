# 無料枠の確認結果と使用量設計 (2026-08 時点)

方針: **すべての枠で定常使用量を上限の 70% 未満に抑える**。
仕様は変わりうるため、四半期に一度は下記の公式ドキュメントを再確認すること。

## Cloudflare

| サービス | 無料枠 (2026-08) | 本システムの想定使用量 | 余裕 |
|---|---|---|---|
| Workers Free | 100,000 req/日, CPU 10ms/req | ingest ~36回/日 + API/Dashboard 閲覧 (数百/日) | 99%+ |
| D1 Free | rows read 500万/日, write 10万/日, 5GB | write: 数千〜1万rows/日, read: 数万/日 | 90%+ |
| Workers AI Free | 10,000 Neurons/日 (超過はエラー、課金なし) | 1日2回 × 最大20件 × llama-3.1-8b | 十分 (件数上限で保護) |

- 出典: developers.cloudflare.com/workers/platform/limits/ , /d1/platform/limits/ , /workers-ai/platform/pricing/
- cron トリガーは無料アカウント 5 個まで → 本システムは 1 Worker に 1 cron 定義 (1日2回発火) のみ。
- D1 は 1 リクエストあたり 50 クエリ制限あり → ingest はバッチ (`db.batch`) でまとめている。

## GitHub Actions

- **public リポジトリ + standard runner なら分数無制限で無料**。private は 2,000分/月。
- 本システムの実行時間試算 (public 前提なら課金対象外):
  - fast: 毎時 × ~3分 = 72分/日
  - normal: 12回/日 × ~4分 = 48分/日
  - slow: 4回/日 × ~4分 = 16分/日
  - private リポジトリの場合 約 4,100分/月となり無料枠超過 → **public リポジトリでの運用を推奨**。
    private にする場合は fast を 2〜3時間毎へ下げる (約 1,400分/月 ≒ 枠の70%)。
- schedule cron は最短5分・毎時0分は遅延/破棄されやすい → 17/23/41分にずらして設定済み。
- **60日間 push がないと schedule が自動停止する** (手動再有効化が必要)。
- 出典: docs.github.com/en/billing (About billing for GitHub Actions), docs.github.com/en/actions (schedule)

## 外部 API

| API | 制限 (2026-08) | キー | 使用量設計 |
|---|---|---|---|
| GitHub REST | 未認証60/h, PAT 5,000/h, Actions内 GITHUB_TOKEN 1,000/h/repo | 任意 | 20 repos × 2call = 40/実行 (Actions内なら余裕) |
| Hacker News (Firebase) | 公式に「rate limit なし」 | 不要 | ~120 items/実行 |
| arXiv | 3秒に1リクエスト・同時1接続 (利用規約) | 不要 | 1 リクエスト/実行 (max_results=200) |
| Hugging Face Hub | 匿名 500/5分, 認証 1,000/5分 | 任意 (HF_TOKEN 推奨) | 10 リクエスト/実行 |
| YouTube Data v3 | 10,000 units/日。**search.list は独立枠 100回/日に制度変更済み** | 必須 | search 不使用。channels(1)+playlistItems(5) = 6 units/実行 |
| FRED | 120 req/分, 無料 | 必須 (無料発行) | ~10 リクエスト/実行 |
| SEC EDGAR | 10 req/秒, User-Agent に連絡先必須 | 不要 (UA必須) | 9 リクエスト/実行, 0.2s sleep |
| Frankfurter (FX) | 明示上限なし (ECB 日次データ) | 不要 | 6 リクエスト/実行 |
| Coinbase Exchange public | 3 req/秒 | 不要 | 1 リクエスト/実行 |
| BOJ / Fed RSS | 常識的頻度 | 不要 | 各1リクエスト/実行 |

## 2026-08 調査での重要な発見

1. **Stooq は anti-bot JS 検証によりスクリプトからの CSV 取得が不可** (実測)。
   加えて非公開の日次ヒット上限あり。→ 市場データは FRED / Frankfurter / Coinbase に変更済み。
2. **YouTube search.list は「100回/日」の独立バケットに変更**。
   → uploads playlist 方式のみ使用 (search.list は実装しない)。
3. **BOJ が 2026-02 に時系列統計の公式 API を公開** (stat-search.boj.or.jp/api/v1)。
   → 現状は What's New RSS のみ使用。時系列が必要になったら追加 (limitations.md)。

## 月額コスト

**$0** — 全サービスが無料枠内。課金設定 (Cloudflare の従量課金有効化等) を行わない限り、
枠超過時はエラーになるだけで請求は発生しない。
