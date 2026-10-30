/**
 * intel-hub Worker entry point: fetch router + scheduled handler.
 */

import type { Env } from "./types";
import { handleApi, json } from "./api";
import { handleIngest } from "./ingest";
import { runAiEvaluation } from "./ai";
import { runTitleTranslation } from "./translate";
import { DASHBOARD_HTML } from "./dashboard";
import { handlePwa } from "./pwa";

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Authorization, Content-Type",
  "Access-Control-Max-Age": "86400",
};

export default {
  async fetch(request, env, _ctx): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    if (path === "/" || path === "/index.html") {
      if (request.method !== "GET") return json({ ok: false, error: "method not allowed" }, 405);
      return new Response(DASHBOARD_HTML, {
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    }

    const pwa = request.method === "GET" ? handlePwa(path) : null;
    if (pwa) return pwa;

    if (path === "/api/ingest") {
      if (request.method !== "POST") return json({ ok: false, error: "method not allowed" }, 405);
      return handleIngest(request, env);
    }

    if (path.startsWith("/api/")) {
      if (request.method !== "GET") return json({ ok: false, error: "method not allowed" }, 405);
      try {
        return await handleApi(url, env);
      } catch (err) {
        console.error(`api error on ${path}:`, err);
        return json({ ok: false, error: err instanceof Error ? err.message : String(err) }, 500);
      }
    }

    return json({ ok: false, error: "not found" }, 404);
  },

  async scheduled(controller, env, ctx): Promise<void> {
    if (controller.cron === "37 * * * *") {
      ctx.waitUntil(runTitleTranslation(env));
    } else {
      ctx.waitUntil(runAiEvaluation(env));
    }
  },
} satisfies ExportedHandler<Env>;
