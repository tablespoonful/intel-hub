/**
 * Shared types for the intel-hub Worker.
 * Ingest payload types follow docs/dev-spec.md section 3 exactly.
 */

export interface Env {
  DB: D1Database;
  AI: Ai;
  /** Secret: bearer token for POST /api/ingest */
  INGEST_TOKEN: string;
}

/** sources.yaml-derived source definition */
export interface IngestSource {
  id: string;
  name?: string | null;
  method?: string | null;
  url?: string | null;
  country?: string | null;
  language?: string | null;
  category?: string | null;
  quality?: number | null;
  tier?: string | null;
  enabled?: boolean | number | null;
}

/** Normalized + scored item (kind decides target table) */
export interface IngestItem {
  source_id: string;
  external_id: string;
  kind: string; // article | paper | repo | model | video | hn | filing
  url?: string | null;
  canonical_url?: string | null;
  title?: string | null;
  normalized_title?: string | null;
  summary?: string | null;
  published_at?: string | null;
  fetched_at: string;
  country?: string | null;
  language?: string | null;
  category?: string | null;
  tags?: string[] | null;
  topics?: string[] | null;
  score?: number | null;
  score_components?: Record<string, unknown> | null;
  ai_status?: "none" | "pending" | null;
  raw_hash: string;
  payload?: Record<string, unknown> | null;
}

export interface IngestMarketPrice {
  symbol: string;
  ts: string;
  interval: string;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  volume?: number | null;
  provider: string;
}

export interface IngestMacroValue {
  series_id: string;
  name?: string | null;
  source?: string | null;
  country?: string | null;
  date: string;
  value?: number | null;
}

export interface IngestEvent {
  event_type: string;
  title: string;
  summary?: string | null;
  occurred_at: string;
  country?: string | null;
  importance?: number | null;
  topics?: string[] | null;
  entities?: string[] | null;
  source_count?: number | null;
}

export interface IngestCollectorRun {
  collector: string;
  started_at: string;
  finished_at?: string | null;
  status?: string | null;
  fetched?: number | null;
  inserted?: number | null;
  duplicate?: number | null;
  failed?: number | null;
  error?: string | null;
}

export interface IngestPayload {
  sources?: IngestSource[];
  items?: IngestItem[];
  market_prices?: IngestMarketPrice[];
  macro_values?: IngestMacroValue[];
  events?: IngestEvent[];
  collector_runs?: IngestCollectorRun[];
}

export interface IngestResponse {
  ok: boolean;
  inserted: Record<string, number>;
  duplicates: number;
}
