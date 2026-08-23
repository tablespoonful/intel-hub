/**
 * GET API endpoints (dev-spec section 4).
 * All queries use bind parameters only; user input is never interpolated into SQL.
 */

import type { Env } from "./types";

const CORS = { "Access-Control-Allow-Origin": "*" };

export function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...CORS },
  });
}

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 200;

function limitOf(params: URLSearchParams): number {
  const raw = params.get("limit");
  if (raw === null || raw === "") return DEFAULT_LIMIT;
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return DEFAULT_LIMIT;
  return Math.min(Math.floor(n), MAX_LIMIT);
}

function numberOrNull(v: string | null): number | null {
  if (v === null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

interface Filter {
  conds: string[];
  binds: (string | number)[];
}

function addEq(f: Filter, column: string, value: string | null): void {
  if (value !== null && value !== "") {
    f.conds.push(`${column} = ?`);
    f.binds.push(value);
  }
}

function addTopic(f: Filter, value: string | null): void {
  if (value !== null && value !== "") {
    f.conds.push(`topics LIKE ?`);
    f.binds.push(`%"${value}"%`);
  }
}

function addGte(f: Filter, column: string, value: number | null): void {
  if (value !== null) {
    f.conds.push(`${column} >= ?`);
    f.binds.push(value);
  }
}

function addRange(f: Filter, column: string, from: string | null, to: string | null): void {
  if (from !== null && from !== "") {
    f.conds.push(`${column} >= ?`);
    f.binds.push(from);
  }
  if (to !== null && to !== "") {
    f.conds.push(`${column} <= ?`);
    f.binds.push(to);
  }
}

function whereSql(f: Filter): string {
  return f.conds.length > 0 ? ` WHERE ${f.conds.join(" AND ")}` : "";
}

async function listEvents(env: Env, params: URLSearchParams): Promise<Response> {
  const f: Filter = { conds: [], binds: [] };
  addEq(f, "country", params.get("country"));
  addEq(f, "event_type", params.get("category"));
  addTopic(f, params.get("topic"));
  addGte(f, "importance", numberOrNull(params.get("min_score")));
  addRange(f, "occurred_at", params.get("from"), params.get("to"));
  const sql = `SELECT * FROM events${whereSql(f)} ORDER BY importance DESC, occurred_at DESC LIMIT ?`;
  const res = await env.DB.prepare(sql).bind(...f.binds, limitOf(params)).all();
  return json({ items: res.results });
}

async function eventDetail(env: Env, id: number): Promise<Response> {
  const event = await env.DB.prepare(`SELECT * FROM events WHERE id = ?`).bind(id).first();
  if (!event) return json({ ok: false, error: "event not found" }, 404);
  const [entities, reactions] = await env.DB.batch([
    env.DB.prepare(`SELECT * FROM event_entities WHERE event_id = ?`).bind(id),
    env.DB.prepare(`SELECT * FROM event_market_reactions WHERE event_id = ?`).bind(id),
  ]);
  return json({
    event,
    entities: entities?.results ?? [],
    market_reactions: reactions?.results ?? [],
  });
}

async function listTechnology(env: Env, params: URLSearchParams): Promise<Response> {
  const f: Filter = { conds: [], binds: [] };
  addEq(f, "country", params.get("country"));
  addEq(f, "category", params.get("category"));
  addTopic(f, params.get("topic"));
  addGte(f, "score", numberOrNull(params.get("min_score")));
  addRange(f, "published_at", params.get("from"), params.get("to"));
  const sql = `SELECT * FROM articles${whereSql(f)} ORDER BY score DESC, published_at DESC LIMIT ?`;
  const res = await env.DB.prepare(sql).bind(...f.binds, limitOf(params)).all();
  return json({ items: res.results });
}

async function listMarkets(env: Env, params: URLSearchParams): Promise<Response> {
  const symbol = params.get("symbol");
  const interval = params.get("interval");
  const limit = limitOf(params);

  let prices: Record<string, unknown>[];
  if (symbol !== null && symbol !== "") {
    // recent candles for one symbol
    const f: Filter = { conds: ["symbol = ?"], binds: [symbol] };
    addEq(f, "interval", interval);
    const res = await env.DB
      .prepare(`SELECT * FROM market_prices${whereSql(f)} ORDER BY ts DESC LIMIT ?`)
      .bind(...f.binds, limit)
      .all();
    prices = res.results;
  } else {
    // latest bar per (symbol, interval)
    const f: Filter = { conds: [], binds: [] };
    addEq(f, "p.interval", interval);
    const cond = f.conds.length > 0 ? ` AND ${f.conds.join(" AND ")}` : "";
    const res = await env.DB
      .prepare(
        `SELECT p.* FROM market_prices p
         WHERE NOT EXISTS (
           SELECT 1 FROM market_prices q
           WHERE q.symbol = p.symbol AND q.interval = p.interval
             AND (q.ts > p.ts OR (q.ts = p.ts AND q.id > p.id))
         )${cond}
         ORDER BY p.symbol, p.interval LIMIT ?`
      )
      .bind(...f.binds, limit)
      .all();
    prices = res.results;
  }

  const macro = await env.DB
    .prepare(
      `SELECT v.series_id, v.date, v.value, v.fetched_at, s.name, s.source, s.country
       FROM macro_values v
       LEFT JOIN macro_series s ON s.id = v.series_id
       WHERE NOT EXISTS (
         SELECT 1 FROM macro_values w
         WHERE w.series_id = v.series_id
           AND (w.date > v.date OR (w.date = v.date AND w.id > v.id))
       )
       ORDER BY v.series_id LIMIT ?`
    )
    .bind(limit)
    .all();

  return json({ prices, macro: macro.results });
}

async function listPapers(env: Env, params: URLSearchParams): Promise<Response> {
  const f: Filter = { conds: [], binds: [] };
  addGte(f, "score", numberOrNull(params.get("min_score")));
  const sql = `SELECT * FROM papers${whereSql(f)} ORDER BY score DESC, published_at DESC LIMIT ?`;
  const res = await env.DB.prepare(sql).bind(...f.binds, limitOf(params)).all();
  return json({ items: res.results });
}

async function listRepos(env: Env, params: URLSearchParams): Promise<Response> {
  const res = await env.DB
    .prepare(
      `SELECT r.*,
         COALESCE(r.stars - (
           SELECT s.stars FROM repo_snapshots s
           WHERE s.full_name = r.full_name AND s.snapped_at <= datetime('now', '-1 day')
           ORDER BY s.snapped_at DESC LIMIT 1
         ), 0) AS stars_24h_delta,
         COALESCE(r.stars - (
           SELECT s.stars FROM repo_snapshots s
           WHERE s.full_name = r.full_name AND s.snapped_at <= datetime('now', '-7 days')
           ORDER BY s.snapped_at DESC LIMIT 1
         ), 0) AS stars_7d_delta
       FROM repositories r
       ORDER BY stars_24h_delta DESC, r.stars DESC
       LIMIT ?`
    )
    .bind(limitOf(params))
    .all();
  return json({ items: res.results });
}

async function listModels(env: Env, params: URLSearchParams): Promise<Response> {
  const res = await env.DB
    .prepare(`SELECT * FROM models ORDER BY downloads DESC LIMIT ?`)
    .bind(limitOf(params))
    .all();
  return json({ items: res.results });
}

async function health(env: Env): Promise<Response> {
  const [lastRuns, failures, stale] = await env.DB.batch([
    env.DB.prepare(
      `SELECT * FROM collector_runs
       WHERE id IN (SELECT MAX(id) FROM collector_runs GROUP BY collector)
       ORDER BY collector`
    ),
    env.DB.prepare(
      `SELECT COUNT(*) AS c FROM collector_runs
       WHERE status = 'failed' AND started_at >= datetime('now', '-1 day')`
    ),
    env.DB.prepare(
      `SELECT collector FROM collector_runs
       GROUP BY collector
       HAVING MAX(CASE WHEN status = 'success' AND started_at >= datetime('now', '-1 day') THEN 1 ELSE 0 END) = 0
       ORDER BY collector`
    ),
  ]);
  const failureRow = (failures?.results ?? [])[0] as { c?: number } | undefined;
  const staleRows = (stale?.results ?? []) as { collector?: string }[];
  return json({
    ok: true,
    last_runs: lastRuns?.results ?? [],
    failure_count_24h: failureRow && typeof failureRow.c === "number" ? failureRow.c : 0,
    stale_sources: staleRows.map((r) => r.collector).filter((c): c is string => typeof c === "string"),
  });
}

/** Route GET /api/* requests. Returns null when the path is unknown. */
export async function handleApi(url: URL, env: Env): Promise<Response> {
  const path = url.pathname;
  const params = url.searchParams;

  if (path === "/api/events") return listEvents(env, params);

  const eventMatch = /^\/api\/events\/(\d+)$/.exec(path);
  if (eventMatch !== null && eventMatch[1] !== undefined) {
    const id = Number(eventMatch[1]);
    if (!Number.isInteger(id)) return json({ ok: false, error: "invalid event id" }, 400);
    return eventDetail(env, id);
  }

  if (path === "/api/technology") return listTechnology(env, params);
  if (path === "/api/markets") return listMarkets(env, params);
  if (path === "/api/papers") return listPapers(env, params);
  if (path === "/api/repos") return listRepos(env, params);
  if (path === "/api/models") return listModels(env, params);
  if (path === "/api/health") return health(env);

  return json({ ok: false, error: "not found" }, 404);
}
