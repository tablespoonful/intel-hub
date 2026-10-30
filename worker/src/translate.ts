/**
 * Scheduled title translation (dev-spec section 4, "Workers AI").
 * Fills title_translations with Japanese titles for recent events, articles
 * and papers using Workers AI m2m100. Titles already in Japanese are stored
 * as-is without a model call. A failed or non-Japanese result is not stored,
 * so the title is retried on the next run.
 */

import type { Env } from "./types";

const MODEL = "@cf/meta/m2m100-1.2b";
const LANG = "ja";
// Free plan: 50 D1 queries per invocation. 3 SELECTs + 1 INSERT per title
// keeps a run at 23 queries, well under the cap, and ~2 Neurons per title
// keeps an hourly run far inside the 10,000 Neurons/day allocation.
const MAX_TITLES_PER_RUN = 20;
const WINDOW_DAYS = 7;
const MAX_TITLE_CHARS = 300;

const JAPANESE = /[぀-ヿ一-鿿]/;

interface TitleRow {
  kind: string; // "event" | "article" | "paper"
  id: number;
  title: string;
  [key: string]: unknown;
}

/** Rows whose Japanese title is missing or was made from a different original. */
function pending(env: Env, table: string, kind: string, timeCol: string, rankCol: string, extra: string, since: string, limit: number) {
  return env.DB
    .prepare(
      `SELECT '${kind}' AS kind, x.id, x.title FROM ${table} x
       LEFT JOIN title_translations t
         ON t.target_kind = '${kind}' AND t.target_id = x.id AND t.lang = '${LANG}'
       WHERE x.${timeCol} >= ?1${extra} AND (t.target_id IS NULL OR t.source_title IS NOT x.title)
       ORDER BY x.${rankCol} DESC
       LIMIT ?2`
    )
    .bind(since, limit);
}

async function translateOne(env: Env, title: string): Promise<string | null> {
  // m2m100 is not in every workers-types model catalog; call through a narrow structural type.
  const ai = env.AI as unknown as { run(model: string, input: unknown): Promise<unknown> };
  const result = await ai.run(MODEL, {
    text: title.slice(0, MAX_TITLE_CHARS),
    source_lang: "english",
    target_lang: "japanese",
  });
  const text =
    result !== null && typeof result === "object" && "translated_text" in result
      ? (result as { translated_text: unknown }).translated_text
      : null;
  if (typeof text !== "string") return null;
  const out = text.trim();
  return out !== "" && JAPANESE.test(out) ? out : null;
}

export async function runTitleTranslation(env: Env): Promise<void> {
  const since = new Date(Date.now() - WINDOW_DAYS * 86_400_000).toISOString().replace(/\.\d{3}Z$/, "Z");
  // Events lead the dashboard, then news, then papers; each kind may use the whole
  // budget, and the loop below stops once it is spent.
  const [events, articles, papers] = await env.DB.batch<TitleRow>([
    pending(env, "events", "event", "occurred_at", "importance", "", since, MAX_TITLES_PER_RUN),
    pending(env, "articles", "article", "published_at", "score", " AND x.dedupe_of IS NULL", since, MAX_TITLES_PER_RUN),
    pending(env, "papers", "paper", "published_at", "score", "", since, MAX_TITLES_PER_RUN),
  ]);
  const rows = [...(events?.results ?? []), ...(articles?.results ?? []), ...(papers?.results ?? [])].slice(
    0,
    MAX_TITLES_PER_RUN
  );
  if (rows.length === 0) return;

  const writes: D1PreparedStatement[] = [];
  let failed = 0;
  for (const row of rows) {
    let ja: string | null = null;
    let model = MODEL;
    if (JAPANESE.test(row.title)) {
      ja = row.title;
      model = "source";
    } else {
      try {
        ja = await translateOne(env, row.title);
      } catch (err) {
        console.warn(`translate: ${row.kind} ${row.id} failed:`, err);
      }
    }
    if (ja === null) {
      failed += 1;
      continue;
    }
    writes.push(
      env.DB
        .prepare(
          `INSERT INTO title_translations (target_kind, target_id, lang, source_title, title, model)
           VALUES (?1, ?2, ?3, ?4, ?5, ?6)
           ON CONFLICT (target_kind, target_id, lang) DO UPDATE SET
             source_title = excluded.source_title,
             title = excluded.title,
             model = excluded.model,
             created_at = datetime('now')`
        )
        .bind(row.kind, row.id, LANG, row.title, ja, model)
    );
  }
  if (writes.length > 0) await env.DB.batch(writes);
  console.log(`translate: stored ${writes.length}, failed ${failed} of ${rows.length}`);
}
