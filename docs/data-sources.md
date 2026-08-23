# データソース一覧

取得方法の優先順位: **API > RSS/Atom > 公式 JSON feed > 公式 HTML**。
利用規約に反するスクレイピングは行わない。RSS が無いサイトは `method: none` として
config に URL のみ記録し、collector は実行しない。

## AI / Technology

| ソース | 方式 | collector | tier | 備考 |
|---|---|---|---|---|
| OpenAI News | RSS | rss | normal | openai.com/news/rss.xml |
| Google DeepMind | RSS | rss | normal | deepmind.google/blog/rss.xml |
| Google AI | RSS | rss | normal | blog.google/technology/ai/rss/ |
| NVIDIA Blog / Robotics | RSS | rss | normal | robotics はカテゴリ別 feed |
| Microsoft Research | RSS | rss | normal | |
| Hugging Face Blog | RSS | rss | normal | |
| Boston Dynamics | RSS | rss | normal | |
| Sakana AI | RSS | rss | normal | sakana.ai/feed.xml (2026-08 検証) |
| Preferred Networks | RSS | rss | normal | |
| Anthropic / Meta AI / 中国勢 (Qwen, DeepSeek, Zhipu, Moonshot, MiniMax, Baidu, Tencent, Huawei) / Physical AI 各社 (PI, Figure, 1X, Skild, Unitree, AgiBot, UBTECH, Fourier) / NTT / Sony AI / TRI / Mujin / AIST / RIKEN | **none** | - | - | 公式 RSS なし (2026-08)。GitHub/HF/HN 経由で捕捉。将来 RSS が提供されたら sources.yaml に追記するだけで有効化できる |
| GitHub リポジトリ 20件 | API | github | normal | repo + releases/latest。stars/forks/issues をスナップショット保存し増加速度を評価 |
| Hugging Face Hub | API | huggingface | normal | 10 キーワード × 30件, lastModified 順 |
| arXiv (cs.AI/CL/LG/RO/CV) | API (Atom) | arxiv | slow | 1リクエスト, topic キーワードでフィルタ |
| Hacker News | API (Firebase) | hackernews | fast | top(>=20pt)+new, AI/LLM/Agent/Robotics 関連のみ保存 |
| YouTube チャンネル 5件 | API | youtube | slow | channels → uploads playlist → playlistItems (search 不使用) |

## Financial / Market

| ソース | 方式 | collector | tier | 対象 |
|---|---|---|---|---|
| Frankfurter (ECB) | API | markets | fast | USDJPY, EURUSD, EURJPY, GBPUSD, USDCNH(CNY代理), AUDUSD (日次) |
| FRED | API | markets / fred | fast / slow | SP500, NASDAQ100, VIXCLS, NIKKEI225, DGS2, DGS10, DTWEXBGS, DCOILWTICO + CPI/UNRATE/FEDFUNDS |
| Coinbase Exchange | API | markets | fast | BTC-USD 15分足 |
| Bank of Japan | RSS | macro_rss | fast | What's New (政策発表等) |
| Federal Reserve | RSS | macro_rss | fast | プレスリリース全件 |
| SEC EDGAR | API | sec_edgar | slow | 監視9社の 8-K / 10-Q / 10-K |
| PBOC / 中国国家統計局 | none | - | - | API 不安定のため MVP 対象外。必要になれば公式発表 URL のイベント保存から開始 |

## 取得できないもの (無料の規約準拠ソースが存在しない)

- 個別株 OHLCV (NVDA 等)、SOX / Russell 2000 / TOPIX / CSI300 / 上海総合 / HSI / HSTECH、
  JP10Y、Gold spot — markets.yaml で `enabled: false`。
  broker API (無料口座) か有料 provider を `MarketDataProvider` として追加すれば有効化できる。
  詳細は limitations.md。
