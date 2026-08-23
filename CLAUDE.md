# プロジェクト概要

intel-hub は、AI・テクノロジーと金融市場の情報を収集・正規化・評価し、API とダッシュボードで提供する個人向けインテリジェンス基盤です。運用費は月額 $0 を絶対条件とし、Cloudflare Workers／D1／Workers AI と GitHub Actions の無料枠だけを使用します。

## ディレクトリ責務

| ディレクトリ | 責務 |
|---|---|
| `collectors/` | 情報源ごとの取得処理。HTTP fetch と純粋な parse 処理を分離する |
| `pipeline/` | 正規化、重複排除、スコアリング、イベント化、AI 契約 |
| `worker/` | Cloudflare Worker の API、ingest、Workers AI、ダッシュボード |
| `db/` | D1／SQLite 共通スキーマの唯一の正本 |
| `config/` | 情報源、トピック、エンティティ、市場、スコアリングの YAML 設定 |
| `scripts/` | collector runner、sink、再スコアリング、環境変数読み込み |
| `tests/` | fixture ベースのテスト |
| `docs/` | アーキテクチャ、内部契約、データ源、無料枠、制約、運用の文書 |

## 開発環境・注意点

- このマシンでは Python を必ず `py` で起動する。`python` は動作しない Windows Store のスタブを指す。
- 日本語を含むファイルを PowerShell の `Set-Content` や `-replace` で書き換えない。ANSI コードページで文字化けするため、エディタ／Write 系ツールを使う。
- `db/schema.sql` がスキーマの唯一の正本であり、Worker から変更してはならない。
- `docs/dev-spec.md` は collectors、pipeline、worker 間の拘束力あるインターフェース契約である。境界を変更する前に必ず読む。

## 主要コマンド

```powershell
py -m pip install -e ".[dev]"
npm --prefix worker install
py -m pytest
py -m scripts.run_collectors --tier fast --sink sqlite
py -m scripts.rescore
npm --prefix worker run dev
npm --prefix worker run check
```

## コード規約

- collector は `collect(config) -> tuple[list[...], RunStats]` を公開し、`collect()` の外へ例外を送出しない。
- 各 collector は HTTP fetch と純粋な `parse_*` 関数を分離し、fixture で解析処理をテストできるようにする。
- テストから実 API を呼び出さない。
- 日時はすべてタイムゾーン付き UTC とする。

## 設定駆動

監視対象の追加は `config/*.yaml` の編集だけで行い、コードは変更しない。RSS／API がない情報源は `method: none` かつ `enabled: false` で記録し、プロジェクト方針で禁止されているスクレイピングは行わない。
