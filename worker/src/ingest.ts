/**
 * POST /api/ingest — receives the pipeline payload (dev-spec section 3)
 * and writes it into D1 with batched prepared statements.
 */

import type {
  Env,
  IngestItem,
  IngestPayload,
} from "./types";
import { json } from "./api";

const BATCH_CHUNK = 50;

/** JSON.stringify or null (for optional JSON columns). */
function j(v: unknown): string | null {
  return v === undefined || v === null ? null : JSON.stringify(v);
}

function payloadStr(p: Record<string, unknown> | null | undefined, key: string): string | null {
  const v = p ? p[key] : undefined;
  return typeof v === "string" ? v : null;
}

function payloadNum(p: Record<string, unknown> | null | undefined, key: string): number | null {
  const v = p ? p[key] : undefined;
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function payloadJson(p: Record<string, unknown> | null | undefined, key: string): string | null {
  const v = p ? p[key] : undefined;
  return v === undefined || v === null ? null : JSON.stringify(v);
}

/** Run statements through db.batch() in chunks, returning all results in order. */
async function runBatch(db: D1Database, stmts: D1PreparedStatement[]): Promise<D1Result[]> {
  const results: D1Result[] = [];
  for (let i = 0; i < stmts.length; i += BATCH_CHUNK) {
    const part = await db.batch(stmts.slice(i, i + BATCH_CHUNK));
    results.push(...part);
  }
  return results;
}

function sumChanges(results: D1Result[]): number {
  let total = 0;
  for (const r of results) {
    const c = r.meta ? r.meta.changes : 0;
    total += typeof c === "number" ? c : 0;
  }
  return total;
}

const ARTICLE_KINDS = new Set(["article", "hn", "filing"]);

// D1 の無料枠は 1 日 100,000 rows written で、書き込みがインデックス列に触れると
// インデックス分の行が追加で計上される (developers.cloudflare.com/d1/platform/pricing/)。
// collector は毎回フィードのウィンドウ全体を再送するため 1 日約 23,000 件が届くが、
// 実際に新規なのは 500 件程度でしかない。無条件の DO UPDATE は残り全部を毎時間
// 書き直しており、articles だけで 1 日約 70,000 行 (上限の 70%) を消費していた。
// そのため以下の upsert はすべて WHERE を持ち、内容が変わっていない行は 0 書き込みで済ませる。
//
// スコアは recency で減衰するので毎回値が変わり、そのままでは WHERE を素通りしてしまう。
// 減衰したスコアの反映はこのウィンドウ内の項目に限る。これを過ぎると recency 成分は
// 十分小さく、スコアを凍結してもダッシュボードの並び順は実質変わらない。
const SCORE_REFRESH_WINDOW = "-3 days";

function articleStmt(db: D1Database, it: IngestItem): D1PreparedStatement {
  const title = it.title ?? "";
  return db
    .prepare(
      `INSERT INTO articles (
         raw_item_id, source_id, external_id, url, canonical_url, title, normalized_title,
         summary, published_at, fetched_at, country, language, category, tags, topics,
         score, score_components, ai_status
       ) VALUES (
         (SELECT id FROM raw_items WHERE source_id = ?1 AND external_id = ?2),
         ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17
       )
       ON CONFLICT (source_id, external_id) DO UPDATE SET
         url = excluded.url,
         canonical_url = excluded.canonical_url,
         title = excluded.title,
         normalized_title = excluded.normalized_title,
         summary = excluded.summary,
         published_at = excluded.published_at,
         fetched_at = excluded.fetched_at,
         country = excluded.country,
         language = excluded.language,
         category = excluded.category,
         tags = excluded.tags,
         topics = excluded.topics,
         score = excluded.score,
         score_components = excluded.score_components,
         ai_status = CASE
           WHEN articles.ai_status IN ('done', 'failed') THEN articles.ai_status
           ELSE excluded.ai_status
         END
       WHERE articles.title IS NOT excluded.title
          OR articles.summary IS NOT excluded.summary
          OR articles.url IS NOT excluded.url
          OR articles.canonical_url IS NOT excluded.canonical_url
          OR articles.published_at IS NOT excluded.published_at
          OR articles.topics IS NOT excluded.topics
          OR (articles.score IS NOT excluded.score
              AND COALESCE(articles.published_at, articles.fetched_at)
                  > datetime('now', '${SCORE_REFRESH_WINDOW}'))`
    )
    .bind(
      it.source_id,
      it.external_id,
      it.url ?? null,
      it.canonical_url ?? null,
      title,
      it.normalized_title ?? title.toLowerCase(),
      it.summary ?? null,
      it.published_at ?? null,
      it.fetched_at,
      it.country ?? null,
      it.language ?? null,
      it.category ?? null,
      j(it.tags),
      j(it.topics),
      it.score ?? 0,
      j(it.score_components),
      it.ai_status ?? "none"
    );
}

function paperStmt(db: D1Database, it: IngestItem): D1PreparedStatement {
  const p = it.payload;
  return db
    .prepare(
      `INSERT INTO papers (
         raw_item_id, arxiv_id, url, title, abstract, authors, categories,
         published_at, updated_at, fetched_at, topics, score, ai_status
       ) VALUES (
         (SELECT id FROM raw_items WHERE source_id = ?1 AND external_id = ?2),
         ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13
       )
       ON CONFLICT (arxiv_id) DO UPDATE SET
         url = excluded.url,
         title = excluded.title,
         abstract = excluded.abstract,
         authors = excluded.authors,
         categories = excluded.categories,
         published_at = excluded.published_at,
         updated_at = excluded.updated_at,
         fetched_at = excluded.fetched_at,
         topics = excluded.topics,
         score = excluded.score,
         ai_status = CASE
           WHEN papers.ai_status IN ('done', 'failed') THEN papers.ai_status
           ELSE excluded.ai_status
         END
       WHERE papers.title IS NOT excluded.title
          OR papers.abstract IS NOT excluded.abstract
          OR papers.url IS NOT excluded.url
          OR papers.authors IS NOT excluded.authors
          OR papers.categories IS NOT excluded.categories
          OR papers.updated_at IS NOT excluded.updated_at
          OR papers.topics IS NOT excluded.topics
          OR (papers.score IS NOT excluded.score
              AND COALESCE(papers.published_at, papers.fetched_at)
                  > datetime('now', '${SCORE_REFRESH_WINDOW}'))`
    )
    .bind(
      it.source_id,
      it.external_id,
      it.url ?? null,
      it.title ?? "",
      payloadStr(p, "abstract") ?? it.summary ?? null,
      payloadJson(p, "authors"),
      payloadJson(p, "categories"),
      it.published_at ?? null,
      payloadStr(p, "updated"),
      it.fetched_at,
      j(it.topics),
      it.score ?? 0,
      it.ai_status ?? "none"
    );
}

function repoStmts(db: D1Database, it: IngestItem): { repo: D1PreparedStatement; snapshot: D1PreparedStatement } {
  const p = it.payload;
  const stars = payloadNum(p, "stars") ?? 0;
  const forks = payloadNum(p, "forks") ?? 0;
  const openIssues = payloadNum(p, "open_issues") ?? 0;
  const repo = db
    .prepare(
      `INSERT INTO repositories (
         full_name, url, description, language, topics, latest_release,
         release_published_at, stars, forks, open_issues, pushed_at, fetched_at, score
       ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13)
       ON CONFLICT (full_name) DO UPDATE SET
         url = excluded.url,
         description = excluded.description,
         language = excluded.language,
         topics = excluded.topics,
         latest_release = excluded.latest_release,
         release_published_at = excluded.release_published_at,
         stars = excluded.stars,
         forks = excluded.forks,
         open_issues = excluded.open_issues,
         pushed_at = excluded.pushed_at,
         fetched_at = excluded.fetched_at,
         score = excluded.score
       WHERE repositories.stars IS NOT excluded.stars
          OR repositories.forks IS NOT excluded.forks
          OR repositories.open_issues IS NOT excluded.open_issues
          OR repositories.description IS NOT excluded.description
          OR repositories.latest_release IS NOT excluded.latest_release
          OR repositories.pushed_at IS NOT excluded.pushed_at
          OR repositories.topics IS NOT excluded.topics
          OR repositories.score IS NOT excluded.score`
    )
    .bind(
      it.external_id,
      it.url ?? null,
      payloadStr(p, "description") ?? it.summary ?? null,
      payloadStr(p, "language") ?? it.language ?? null,
      payloadJson(p, "topics") ?? j(it.topics),
      payloadStr(p, "latest_release"),
      payloadStr(p, "release_published_at"),
      stars,
      forks,
      openIssues,
      payloadStr(p, "pushed_at"),
      it.fetched_at,
      it.score ?? 0
    );
  const snapshot = db
    .prepare(
      `INSERT OR IGNORE INTO repo_snapshots (full_name, snapped_at, stars, forks, open_issues)
       VALUES (?1, ?2, ?3, ?4, ?5)`
    )
    .bind(it.external_id, it.fetched_at, stars, forks, openIssues);
  return { repo, snapshot };
}

function modelStmt(db: D1Database, it: IngestItem): D1PreparedStatement {
  const p = it.payload;
  const slash = it.external_id.indexOf("/");
  const author = slash > 0 ? it.external_id.slice(0, slash) : null;
  return db
    .prepare(
      `INSERT INTO models (
         hf_id, url, author, pipeline_tag, tags, downloads, likes,
         hf_created_at, hf_updated_at, fetched_at, score
       ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)
       ON CONFLICT (hf_id) DO UPDATE SET
         url = excluded.url,
         author = excluded.author,
         pipeline_tag = excluded.pipeline_tag,
         tags = excluded.tags,
         downloads = excluded.downloads,
         likes = excluded.likes,
         hf_created_at = excluded.hf_created_at,
         hf_updated_at = excluded.hf_updated_at,
         fetched_at = excluded.fetched_at,
         score = excluded.score
       WHERE models.downloads IS NOT excluded.downloads
          OR models.likes IS NOT excluded.likes
          OR models.hf_updated_at IS NOT excluded.hf_updated_at
          OR models.pipeline_tag IS NOT excluded.pipeline_tag
          OR models.tags IS NOT excluded.tags
          OR models.url IS NOT excluded.url
          OR (models.score IS NOT excluded.score
              AND COALESCE(models.hf_updated_at, models.fetched_at)
                  > datetime('now', '${SCORE_REFRESH_WINDOW}'))`
    )
    .bind(
      it.external_id,
      it.url ?? null,
      author,
      payloadStr(p, "pipeline_tag"),
      payloadJson(p, "tags") ?? j(it.tags),
      payloadNum(p, "downloads") ?? 0,
      payloadNum(p, "likes") ?? 0,
      payloadStr(p, "createdAt"),
      payloadStr(p, "lastModified") ?? it.published_at ?? null,
      it.fetched_at,
      it.score ?? 0
    );
}

function videoStmt(db: D1Database, it: IngestItem): D1PreparedStatement {
  const p = it.payload;
  return db
    .prepare(
      `INSERT INTO videos (
         video_id, channel_id, channel_name, url, title, description,
         published_at, fetched_at, country, score
       ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)
       ON CONFLICT (video_id) DO UPDATE SET
         channel_id = excluded.channel_id,
         channel_name = excluded.channel_name,
         url = excluded.url,
         title = excluded.title,
         description = excluded.description,
         published_at = excluded.published_at,
         fetched_at = excluded.fetched_at,
         country = excluded.country,
         score = excluded.score
       WHERE videos.title IS NOT excluded.title
          OR videos.description IS NOT excluded.description
          OR videos.channel_name IS NOT excluded.channel_name
          OR videos.url IS NOT excluded.url
          OR videos.published_at IS NOT excluded.published_at
          OR (videos.score IS NOT excluded.score
              AND COALESCE(videos.published_at, videos.fetched_at)
                  > datetime('now', '${SCORE_REFRESH_WINDOW}'))`
    )
    .bind(
      it.external_id,
      payloadStr(p, "channel_id"),
      payloadStr(p, "channel_name"),
      it.url ?? null,
      it.title ?? "",
      payloadStr(p, "description") ?? it.summary ?? null,
      it.published_at ?? null,
      it.fetched_at,
      it.country ?? null,
      it.score ?? 0
    );
}

export async function handleIngest(request: Request, env: Env): Promise<Response> {
  const auth = request.headers.get("Authorization") ?? "";
  if (!env.INGEST_TOKEN || auth !== `Bearer ${env.INGEST_TOKEN}`) {
    return json({ ok: false, error: "unauthorized" }, 401);
  }

  let payload: IngestPayload;
  try {
    payload = (await request.json()) as IngestPayload;
  } catch {
    return json({ ok: false, error: "invalid JSON body" }, 400);
  }
  if (payload === null || typeof payload !== "object") {
    return json({ ok: false, error: "invalid payload" }, 400);
  }

  const db = env.DB;
  const sources = payload.sources ?? [];
  const items = payload.items ?? [];
  const marketSymbols = payload.market_symbols ?? [];
  const marketPrices = payload.market_prices ?? [];
  const macroValues = payload.macro_values ?? [];
  const events = payload.events ?? [];
  const collectorRuns = payload.collector_runs ?? [];

  const inserted: Record<string, number> = {
    sources: 0,
    raw_items: 0,
    articles: 0,
    papers: 0,
    repositories: 0,
    models: 0,
    videos: 0,
    events: 0,
    market_symbols: 0,
    market_prices: 0,
    macro_values: 0,
    collector_runs: 0,
  };

  try {
    // -- 1. sources (upsert) + placeholder sources for referenced-but-missing ids (FK) --
    const sourceStmts: D1PreparedStatement[] = [];
    const knownSourceIds = new Set<string>();
    for (const s of sources) {
      if (!s || typeof s.id !== "string" || s.id === "") continue;
      knownSourceIds.add(s.id);
      sourceStmts.push(
        db
          .prepare(
            `INSERT INTO sources (id, name, method, url, country, language, category, quality, tier, enabled, updated_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, datetime('now'))
             ON CONFLICT (id) DO UPDATE SET
               name = excluded.name,
               method = excluded.method,
               url = excluded.url,
               country = excluded.country,
               language = excluded.language,
               category = excluded.category,
               quality = excluded.quality,
               tier = excluded.tier,
               enabled = excluded.enabled,
               updated_at = datetime('now')
             WHERE sources.name IS NOT excluded.name
                OR sources.method IS NOT excluded.method
                OR sources.url IS NOT excluded.url
                OR sources.country IS NOT excluded.country
                OR sources.language IS NOT excluded.language
                OR sources.category IS NOT excluded.category
                OR sources.quality IS NOT excluded.quality
                OR sources.tier IS NOT excluded.tier
                OR sources.enabled IS NOT excluded.enabled`
          )
          .bind(
            s.id,
            s.name ?? s.id,
            s.method ?? "api",
            s.url ?? null,
            s.country ?? null,
            s.language ?? null,
            s.category ?? null,
            s.quality ?? 0.5,
            s.tier ?? "normal",
            s.enabled === false || s.enabled === 0 ? 0 : 1
          )
      );
    }
    const placeholderIds = new Set<string>();
    for (const it of items) {
      if (it && typeof it.source_id === "string" && it.source_id !== "" && !knownSourceIds.has(it.source_id)) {
        placeholderIds.add(it.source_id);
      }
    }
    for (const id of placeholderIds) {
      sourceStmts.push(
        db.prepare(`INSERT OR IGNORE INTO sources (id, name, method) VALUES (?1, ?2, 'api')`).bind(id, id)
      );
    }
    if (sourceStmts.length > 0) {
      inserted["sources"] = sumChanges(await runBatch(db, sourceStmts));
    }

    // -- 2. raw_items (INSERT OR IGNORE; ignored rows == duplicates) --
    const validItems = items.filter(
      (it): it is IngestItem =>
        !!it &&
        typeof it.source_id === "string" &&
        it.source_id !== "" &&
        typeof it.external_id === "string" &&
        it.external_id !== "" &&
        typeof it.kind === "string"
    );
    const rawStmts = validItems.map((it) =>
      db
        .prepare(
          `INSERT OR IGNORE INTO raw_items (
             source_id, external_id, kind, url, title, published_at, fetched_at,
             country, language, category, tags, raw_hash, payload_json
           ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13)`
        )
        .bind(
          it.source_id,
          it.external_id,
          it.kind,
          it.url ?? null,
          it.title ?? null,
          it.published_at ?? null,
          it.fetched_at,
          it.country ?? null,
          it.language ?? null,
          it.category ?? null,
          j(it.tags),
          it.raw_hash,
          j(it.payload)
        )
    );
    if (rawStmts.length > 0) {
      inserted["raw_items"] = sumChanges(await runBatch(db, rawStmts));
    }
    const duplicates = validItems.length - (inserted["raw_items"] ?? 0);

    // -- 3. typed tables (upserts) --
    const articleStmts: D1PreparedStatement[] = [];
    const paperStmts: D1PreparedStatement[] = [];
    const repositoryStmts: D1PreparedStatement[] = [];
    const modelStmts: D1PreparedStatement[] = [];
    const videoStmts: D1PreparedStatement[] = [];
    for (const it of validItems) {
      if (ARTICLE_KINDS.has(it.kind)) {
        articleStmts.push(articleStmt(db, it));
      } else if (it.kind === "paper") {
        paperStmts.push(paperStmt(db, it));
      } else if (it.kind === "repo") {
        const { repo, snapshot } = repoStmts(db, it);
        repositoryStmts.push(repo, snapshot);
      } else if (it.kind === "model") {
        modelStmts.push(modelStmt(db, it));
      } else if (it.kind === "video") {
        videoStmts.push(videoStmt(db, it));
      }
    }
    if (articleStmts.length > 0) inserted["articles"] = sumChanges(await runBatch(db, articleStmts));
    if (paperStmts.length > 0) inserted["papers"] = sumChanges(await runBatch(db, paperStmts));
    if (repositoryStmts.length > 0) {
      // repo upsert + snapshot pairs; count only repo rows (every even index)
      const results = await runBatch(db, repositoryStmts);
      let repoChanges = 0;
      for (let i = 0; i < results.length; i += 2) {
        const r = results[i];
        const c = r && r.meta ? r.meta.changes : 0;
        repoChanges += typeof c === "number" ? c : 0;
      }
      inserted["repositories"] = repoChanges;
    }
    if (modelStmts.length > 0) inserted["models"] = sumChanges(await runBatch(db, modelStmts));
    if (videoStmts.length > 0) inserted["videos"] = sumChanges(await runBatch(db, videoStmts));

    // -- 4. events + event_entities --
    // events と event_entities は別バッチにする。前者の書き込み数を独立して数えたいのと、
    // event_entities が events の id を引くので先に events を確定させる必要があるため。
    const eventStmts: D1PreparedStatement[] = [];
    const entityStmts: D1PreparedStatement[] = [];
    for (const ev of events) {
      if (!ev || typeof ev.event_type !== "string" || typeof ev.title !== "string" || typeof ev.occurred_at !== "string") {
        continue;
      }
      eventStmts.push(
        db
          .prepare(
            `INSERT INTO events (event_type, title, summary, occurred_at, country, importance, topics, source_count)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
             ON CONFLICT (event_type, title, occurred_at) DO UPDATE SET
               summary = excluded.summary,
               country = excluded.country,
               importance = MAX(events.importance, excluded.importance),
               topics = excluded.topics,
               source_count = MAX(events.source_count, excluded.source_count)
             WHERE events.summary IS NOT excluded.summary
                OR events.country IS NOT excluded.country
                OR events.topics IS NOT excluded.topics
                OR excluded.source_count > events.source_count
                OR excluded.importance > events.importance`
          )
          .bind(
            ev.event_type,
            ev.title,
            ev.summary ?? null,
            ev.occurred_at,
            ev.country ?? null,
            ev.importance ?? 0,
            j(ev.topics),
            ev.source_count ?? 1
          )
      );
      for (const entity of ev.entities ?? []) {
        if (typeof entity !== "string" || entity === "") continue;
        entityStmts.push(
          db
            .prepare(
              `INSERT OR IGNORE INTO event_entities (event_id, entity_id, role)
               SELECT id, ?4, 'subject' FROM events
               WHERE event_type = ?1 AND title = ?2 AND occurred_at = ?3`
            )
            .bind(ev.event_type, ev.title, ev.occurred_at, entity)
        );
      }
    }
    // 他テーブルと同じく「実際に書かれた行数」を返す。送信した文の数ではない。
    // ここを文の数にしていたため、変更のないイベントを毎回書き直していた事実が
    // ingest のレスポンスから見えなくなっていた。
    if (eventStmts.length > 0) inserted["events"] = sumChanges(await runBatch(db, eventStmts));
    if (entityStmts.length > 0) await runBatch(db, entityStmts);

    // -- 5. market symbols (definitions, then placeholders for the FK) + market_prices --
    const symbolStmts: D1PreparedStatement[] = [];
    for (const ms of marketSymbols) {
      if (!ms || typeof ms.canonical !== "string" || ms.canonical === "") continue;
      symbolStmts.push(
        db
          .prepare(
            `INSERT INTO market_symbols (canonical, name, asset, country, providers)
             VALUES (?1, ?2, ?3, ?4, ?5)
             ON CONFLICT (canonical) DO UPDATE SET
               name = excluded.name,
               asset = excluded.asset,
               country = excluded.country,
               providers = excluded.providers
             WHERE market_symbols.name IS NOT excluded.name
                OR market_symbols.asset IS NOT excluded.asset
                OR market_symbols.country IS NOT excluded.country
                OR market_symbols.providers IS NOT excluded.providers`
          )
          .bind(ms.canonical, ms.name ?? ms.canonical, ms.asset ?? "unknown", ms.country ?? null, j(ms.providers))
      );
    }
    if (symbolStmts.length > 0) inserted["market_symbols"] = sumChanges(await runBatch(db, symbolStmts));

    const marketStmts: D1PreparedStatement[] = [];
    const seenSymbols = new Set<string>();
    for (const mp of marketPrices) {
      if (!mp || typeof mp.symbol !== "string" || mp.symbol === "") continue;
      if (!seenSymbols.has(mp.symbol)) {
        seenSymbols.add(mp.symbol);
        marketStmts.push(
          db
            .prepare(`INSERT OR IGNORE INTO market_symbols (canonical, name, asset) VALUES (?1, ?2, 'unknown')`)
            .bind(mp.symbol, mp.symbol)
        );
      }
    }
    const priceStmts: D1PreparedStatement[] = [];
    for (const mp of marketPrices) {
      if (!mp || typeof mp.symbol !== "string" || mp.symbol === "" || typeof mp.ts !== "string" || typeof mp.interval !== "string") {
        continue;
      }
      priceStmts.push(
        db
          .prepare(
            `INSERT INTO market_prices (symbol, ts, interval, open, high, low, close, volume, provider)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
             ON CONFLICT (symbol, ts, interval, provider) DO UPDATE SET
               open = excluded.open,
               high = excluded.high,
               low = excluded.low,
               close = excluded.close,
               volume = excluded.volume
             WHERE market_prices.close IS NOT excluded.close
                OR market_prices.open IS NOT excluded.open
                OR market_prices.high IS NOT excluded.high
                OR market_prices.low IS NOT excluded.low
                OR market_prices.volume IS NOT excluded.volume`
          )
          .bind(
            mp.symbol,
            mp.ts,
            mp.interval,
            mp.open ?? null,
            mp.high ?? null,
            mp.low ?? null,
            mp.close ?? null,
            mp.volume ?? null,
            mp.provider ?? "unknown"
          )
      );
    }
    if (marketStmts.length > 0) await runBatch(db, marketStmts);
    if (priceStmts.length > 0) inserted["market_prices"] = sumChanges(await runBatch(db, priceStmts));

    // -- 6. macro_series (upsert, FK) + macro_values --
    const macroSeriesStmts: D1PreparedStatement[] = [];
    const seenSeries = new Set<string>();
    for (const mv of macroValues) {
      if (!mv || typeof mv.series_id !== "string" || mv.series_id === "" || seenSeries.has(mv.series_id)) continue;
      seenSeries.add(mv.series_id);
      macroSeriesStmts.push(
        db
          .prepare(
            `INSERT INTO macro_series (id, name, source, country) VALUES (?1, ?2, ?3, ?4)
             ON CONFLICT (id) DO UPDATE SET
               name = CASE WHEN excluded.name IS NOT NULL AND excluded.name != '' THEN excluded.name ELSE macro_series.name END,
               source = excluded.source,
               country = excluded.country
             WHERE (excluded.name IS NOT NULL AND excluded.name != ''
                    AND macro_series.name IS NOT excluded.name)
                OR macro_series.source IS NOT excluded.source
                OR macro_series.country IS NOT excluded.country`
          )
          .bind(mv.series_id, mv.name ?? null, mv.source ?? "fred", mv.country ?? null)
      );
    }
    const macroValueStmts: D1PreparedStatement[] = [];
    for (const mv of macroValues) {
      if (!mv || typeof mv.series_id !== "string" || mv.series_id === "" || typeof mv.date !== "string") continue;
      macroValueStmts.push(
        db
          .prepare(
            `INSERT INTO macro_values (series_id, date, value, fetched_at)
             VALUES (?1, ?2, ?3, datetime('now'))
             ON CONFLICT (series_id, date) DO UPDATE SET
               value = excluded.value,
               fetched_at = excluded.fetched_at
             WHERE macro_values.value IS NOT excluded.value`
          )
          .bind(mv.series_id, mv.date, mv.value ?? null)
      );
    }
    if (macroSeriesStmts.length > 0) await runBatch(db, macroSeriesStmts);
    if (macroValueStmts.length > 0) inserted["macro_values"] = sumChanges(await runBatch(db, macroValueStmts));

    // -- 7. collector_runs (plain insert) --
    const runStmts: D1PreparedStatement[] = [];
    for (const run of collectorRuns) {
      if (!run || typeof run.collector !== "string" || run.collector === "" || typeof run.started_at !== "string") continue;
      runStmts.push(
        db
          .prepare(
            `INSERT INTO collector_runs (collector, started_at, finished_at, status, fetched, inserted, duplicate, failed, error)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)`
          )
          .bind(
            run.collector,
            run.started_at,
            run.finished_at ?? null,
            run.status ?? "success",
            run.fetched ?? 0,
            run.inserted ?? 0,
            run.duplicate ?? 0,
            run.failed ?? 0,
            run.error ?? null
          )
      );
    }
    if (runStmts.length > 0) inserted["collector_runs"] = sumChanges(await runBatch(db, runStmts));

    return json({ ok: true, inserted, duplicates });
  } catch (err) {
    console.error("ingest failed:", err);
    return json({ ok: false, error: err instanceof Error ? err.message : String(err) }, 500);
  }
}
