# 既知の制約と将来候補

## 0円運用のために外した / 縮小したもの

| 項目 | 現状 | 将来の選択肢 (課金 or 追加作業) |
|---|---|---|
| 個別株・日本株・中国株・香港株の価格 | 取得なし (markets.yaml で enabled: false)。Stooq が anti-bot 化し、無料かつ規約準拠のソースが消滅 (2026-08 実測) | 証券会社の無料 API (例: 国内ネット証券, Alpaca 等) を `MarketDataProvider` 実装で追加。interface は用意済み |
| SOX / RUT / TOPIX / CSI300 / SHCOMP / HSI / HSTECH / JP10Y / Gold | 同上 | 同上 |
| FX・指数の足種 | 日次のみ (ECB 参照レート / FRED 終値)。BTC のみ 15分足 | intraday が必要なら broker API へ差し替え |
| event_market_reactions (-15m/+15m/+1h/+4h/+1d) | テーブル・スキーマのみ。計算ロジック未実装 | 日次データでは -15m/+15m が原理的に不可能。intraday provider 導入後に Worker の cron で計算する |
| X (Twitter) | 取得なし (有料 API のみのため方針で禁止) | - |
| 商用ニュース API / Bloomberg | 取得なし | - |
| 中国語公式サイト (Zhipu, Moonshot 等) | RSS なしのため取得なし。GitHub / Hugging Face / HN 経由で間接捕捉 | RSSHub 等のセルフホストは追加コストとメンテを伴うため見送り |
| PBOC / 中国国家統計局 | 未実装 | 公式発表 URL をイベントとして保存する軽量 collector から開始可 |
| BOJ 時系列統計 API (2026-02 公開) | 未実装 (What's New RSS のみ) | stat-search.boj.or.jp/api/v1 collector を追加すれば JGB 利回り等を macro_values に入れられる |
| 重複排除 | 文字列正規化 + hash + タイトル類似度のみ | embedding ベースの意味的統合は方針により導入しない (必要になるまで) |
| Digest (日次まとめ) | digests テーブルのみ。生成未実装 | Workers AI の cron に digest 生成を追加 (Neurons 消費に注意) |
| YouTube 統計 (views) | playlistItems では取得不可のため views=0 | videos.list (1unit/50本) を追加すれば取得可能 |
| AI 評価モデル | @cf/meta/llama-3.1-8b-instruct (無料枠内) | 精度が欲しければ有料の大型モデル / 外部 API |

## 運用上の注意

- **public リポジトリでないと GitHub Actions 分数が無料枠を超える** (free-tier.md 参照)。
- GitHub Actions は 60 日間 push がないと schedule が止まる → 月1回程度の軽微な commit で回避。
- 無料 API の仕様変更 (特に Cloudflare / YouTube / HF の rate limit) は四半期ごとに再確認。
- 市場データは監視・分析用途限定。**自動売買の約定判断には使用しない**。
