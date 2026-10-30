/**
 * Dashboard (dev-spec section 5): a single self-contained dark-theme HTML page.
 * Vanilla JS only, same-origin fetch to /api/*, no external resources.
 */

import { OVERVIEW_CSS, OVERVIEW_HTML, OVERVIEW_JS } from "./overview";

export const DASHBOARD_HTML: string = `<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>intel-hub</title>
<meta name="theme-color" content="#161b22">
<meta name="apple-mobile-web-app-title" content="intel-hub">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<style>
  :root {
    --bg: #0d1117; --panel: #161b22; --border: #30363d;
    --fg: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
    --good: #3fb950; --bad: #f85149;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--fg); font: 14px/1.5 -apple-system, "Segoe UI", "Hiragino Sans", "Noto Sans JP", sans-serif; }
  header { display: flex; align-items: center; gap: 16px; padding: 10px 16px; border-bottom: 1px solid var(--border); background: var(--panel); position: sticky; top: 0; }
  header h1 { font-size: 16px; color: var(--accent); white-space: nowrap; flex-shrink: 0; }
  nav { display: flex; gap: 4px; flex-wrap: wrap; }
  button.tabbtn, button.fbtn {
    background: transparent; color: var(--muted); border: 1px solid var(--border);
    border-radius: 6px; padding: 4px 12px; cursor: pointer; font-size: 13px;
  }
  button.tabbtn.active, button.fbtn.active { background: #1f6feb33; color: var(--accent); border-color: var(--accent); }
  main { max-width: 1100px; margin: 0 auto; padding: 16px; }
  section.tab { display: none; }
  section.tab.active { display: block; }
  .filters { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; align-items: center; }
  .filters .flabel { color: var(--muted); font-size: 12px; margin-right: 4px; }
  .tablewrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 8px; background: var(--panel); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }
  td.wrap { white-space: normal; min-width: 260px; }
  th { color: var(--muted); font-weight: 600; font-size: 12px; }
  tr:last-child td { border-bottom: none; }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .orig { color: var(--muted); font-size: 12px; margin-top: 1px; }
  .score { display: inline-block; min-width: 34px; text-align: center; border-radius: 4px; padding: 0 6px; background: #1f6feb33; color: var(--accent); font-weight: 600; }
  .muted { color: var(--muted); }
  .pos { color: var(--good); }
  .neg { color: var(--bad); }
  .status { padding: 10px; color: var(--muted); }
  h2.subhead { font-size: 13px; color: var(--muted); margin: 14px 0 6px; }
${OVERVIEW_CSS}</style>
</head>
<body>
<header>
  <h1>intel-hub</h1>
  <nav id="tabs">
    <button class="tabbtn active" data-tab="overview">概要</button>
    <button class="tabbtn" data-tab="now">速報</button>
    <button class="tabbtn" data-tab="ai">AI記事</button>
    <button class="tabbtn" data-tab="market">マーケット</button>
    <button class="tabbtn" data-tab="papers">論文</button>
    <button class="tabbtn" data-tab="github">GitHub</button>
  </nav>
</header>
<main>
${OVERVIEW_HTML}
  <section class="tab" id="tab-now">
    <div class="tablewrap"><div class="status" id="now-status">読み込み中…</div><table id="now-table"></table></div>
  </section>

  <section class="tab" id="tab-ai">
    <div class="filters" id="ai-country">
      <span class="flabel">国:</span>
      <button class="fbtn active" data-value="">すべて</button>
      <button class="fbtn" data-value="US">米国</button>
      <button class="fbtn" data-value="CN">中国</button>
      <button class="fbtn" data-value="JP">日本</button>
    </div>
    <div class="filters" id="ai-topic">
      <span class="flabel">トピック:</span>
      <button class="fbtn active" data-value="">すべて</button>
      <button class="fbtn" data-value="llm">LLM</button>
      <button class="fbtn" data-value="agent">エージェント</button>
      <button class="fbtn" data-value="reasoning">推論</button>
      <button class="fbtn" data-value="multimodal">マルチモーダル</button>
      <button class="fbtn" data-value="robotics">ロボティクス</button>
      <button class="fbtn" data-value="rl">強化学習</button>
    </div>
    <div class="tablewrap"><div class="status" id="ai-status">読み込み中…</div><table id="ai-table"></table></div>
  </section>

  <section class="tab" id="tab-market">
    <h2 class="subhead">価格（銘柄ごとの最新値）</h2>
    <div class="tablewrap"><div class="status" id="market-status">読み込み中…</div><table id="market-table"></table></div>
    <h2 class="subhead">マクロ指標（系列ごとの最新値）</h2>
    <div class="tablewrap"><table id="macro-table"></table></div>
  </section>

  <section class="tab" id="tab-papers">
    <div class="tablewrap"><div class="status" id="papers-status">読み込み中…</div><table id="papers-table"></table></div>
  </section>

  <section class="tab" id="tab-github">
    <div class="tablewrap"><div class="status" id="github-status">読み込み中…</div><table id="github-table"></table></div>
  </section>
</main>
<div id="tip" role="tooltip"></div>
<script>
(function () {
  "use strict";
  var state = { country: "", topic: "" };
  var loaded = {};

  function esc(v) {
    var s = v === null || v === undefined ? "" : String(v);
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function fmtTime(s) {
    if (!s) return "";
    return String(s).replace("T", " ").replace(/(:\\d\\d)(\\.\\d+)?(Z|\\+.*)?$/, "$1");
  }
  function fmtNum(v) {
    if (v === null || v === undefined) return "";
    var n = Number(v);
    if (!isFinite(n)) return esc(v);
    return n.toLocaleString("en-US", { maximumFractionDigits: 4 });
  }
  function scoreCell(v) {
    var n = Math.round(Number(v) || 0);
    return '<span class="score">' + n + "</span>";
  }
  function linkCell(url, title, titleJa) {
    var ja = titleJa && titleJa !== title ? titleJa : "";
    var t = esc(ja || title || "（タイトルなし）");
    var head = url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + t + "</a>" : t;
    // the Japanese title leads; the original stays visible underneath
    return ja ? head + '<div class="orig">' + esc(title) + "</div>" : head;
  }
  function setStatus(id, msg) {
    var el = document.getElementById(id);
    if (el) {
      el.textContent = msg || "";
      el.style.display = msg ? "block" : "none";
    }
  }
  function fetchJson(path, statusId, cb) {
    setStatus(statusId, "読み込み中…");
    var offline = false;
    fetch(path)
      .then(function (r) {
        // set by the service worker when the network is unreachable
        offline = r.headers.get("X-Intel-Hub-Offline") === "1";
        if (!r.ok) throw new Error(offline ? "オフラインで、保存済みのデータもありません" : "HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        setStatus(statusId, "");
        cb(data);
        if (offline) setStatus(statusId, "オフライン: 保存済みのデータを表示しています");
      })
      .catch(function (err) {
        setStatus(statusId, "エラー: " + err.message);
      });
  }
  function renderTable(tableId, headers, rowsHtml, statusId) {
    var table = document.getElementById(tableId);
    if (!table) return;
    if (rowsHtml.length === 0) {
      table.innerHTML = "";
      setStatus(statusId, "データがありません");
      return;
    }
    var head = "<tr>";
    for (var i = 0; i < headers.length; i++) head += "<th>" + esc(headers[i]) + "</th>";
    head += "</tr>";
    table.innerHTML = "<thead>" + head + "</thead><tbody>" + rowsHtml.join("") + "</tbody>";
  }

  // display names for pipeline enums; unknown values fall back to the raw id
  var EVENT_LABELS = {
    model_release: "モデル公開", product_launch: "製品発表", research: "研究", funding: "資金調達",
    robotics_release: "ロボティクス発表", policy: "政策", regulation: "規制", central_bank: "中央銀行",
    earnings: "決算", partnership: "提携", filing: "開示"
  };
  var TOPIC_LABELS = {
    llm: "LLM", multimodal: "マルチモーダル", reasoning: "推論", agent: "エージェント",
    robotics: "ロボティクス", rl: "強化学習", markets: "市場", macro: "マクロ経済"
  };
  function eventLabel(v) { return v ? EVENT_LABELS[v] || v : ""; }
  function topicLabel(v) { return v ? TOPIC_LABELS[v] || v : ""; }

  function loadNow() {
    fetchJson("/api/events?limit=20", "now-status", function (data) {
      var rows = (data.items || []).map(function (e) {
        return "<tr><td>" + scoreCell(e.importance) +
          '</td><td class="muted">' + esc(fmtTime(e.occurred_at)) +
          "</td><td>" + esc(e.country || "") +
          '</td><td class="muted">' + esc(eventLabel(e.event_type)) +
          '</td><td class="wrap">' + linkCell("", e.title, e.title_ja) +
          "</td><td>" + esc(e.source_count) + "</td></tr>";
      });
      renderTable("now-table", ["スコア", "日時", "国", "種別", "タイトル", "ソース数"], rows, "now-status");
    });
  }

  function loadAi() {
    var q = "/api/technology?limit=50";
    if (state.country) q += "&country=" + encodeURIComponent(state.country);
    if (state.topic) q += "&topic=" + encodeURIComponent(state.topic);
    fetchJson(q, "ai-status", function (data) {
      var rows = (data.items || []).map(function (a) {
        return "<tr><td>" + scoreCell(a.score) +
          '</td><td class="wrap">' + linkCell(a.url, a.title, a.title_ja) +
          '</td><td class="muted">' + esc(a.source_id || "") +
          "</td><td>" + esc(a.country || "") +
          '</td><td class="muted">' + esc(a.category || "") +
          '</td><td class="muted">' + esc(fmtTime(a.published_at)) + "</td></tr>";
      });
      renderTable("ai-table", ["スコア", "タイトル", "情報源", "国", "カテゴリ", "公開日時"], rows, "ai-status");
    });
  }

  function loadMarket() {
    fetchJson("/api/markets", "market-status", function (data) {
      var rows = (data.prices || []).map(function (p) {
        return "<tr><td>" + esc(p.symbol) +
          "</td><td>" + fmtNum(p.close) +
          '</td><td class="muted">' + esc(p.interval) +
          '</td><td class="muted">' + esc(fmtTime(p.ts)) +
          '</td><td class="muted">' + esc(p.provider) + "</td></tr>";
      });
      renderTable("market-table", ["銘柄", "終値", "足", "日時", "提供元"], rows, "market-status");
      var mrows = (data.macro || []).map(function (m) {
        return "<tr><td>" + esc(m.series_id) +
          '</td><td class="wrap muted">' + esc(m.name || "") +
          "</td><td>" + fmtNum(m.value) +
          '</td><td class="muted">' + esc(m.date) +
          "</td><td>" + esc(m.country || "") + "</td></tr>";
      });
      renderTable("macro-table", ["系列", "名称", "値", "日付", "国"], mrows, "market-status");
    });
  }

  function loadPapers() {
    fetchJson("/api/papers?limit=50", "papers-status", function (data) {
      var rows = (data.items || []).map(function (p) {
        return "<tr><td>" + scoreCell(p.score) +
          '</td><td class="wrap">' + linkCell(p.url, p.title, p.title_ja) +
          '</td><td class="muted">' + esc(p.arxiv_id || "") +
          '</td><td class="muted">' + esc(fmtTime(p.published_at)) + "</td></tr>";
      });
      renderTable("papers-table", ["スコア", "タイトル", "arXiv", "公開日時"], rows, "papers-status");
    });
  }

  function deltaCell(v) {
    var n = Number(v) || 0;
    var cls = n > 0 ? "pos" : n < 0 ? "neg" : "muted";
    var sign = n > 0 ? "+" : "";
    return '<td class="' + cls + '">' + sign + n.toLocaleString("en-US") + "</td>";
  }

  function loadGithub() {
    fetchJson("/api/repos?limit=50", "github-status", function (data) {
      var rows = (data.items || []).map(function (r) {
        return '<tr><td class="wrap">' + linkCell(r.url, r.full_name) +
          "</td><td>" + fmtNum(r.stars) + "</td>" +
          deltaCell(r.stars_24h_delta) + deltaCell(r.stars_7d_delta) +
          '<td class="muted">' + esc(r.language || "") +
          '</td><td class="muted">' + esc(r.latest_release || "") + "</td></tr>";
      });
      renderTable("github-table", ["リポジトリ", "スター", "24時間増減", "7日増減", "言語", "リリース"], rows, "github-status");
    });
  }

${OVERVIEW_JS}
  var loaders = { overview: loadOverview, now: loadNow, ai: loadAi, market: loadMarket, papers: loadPapers, github: loadGithub };

  function showTab(name) {
    var btns = document.querySelectorAll("#tabs .tabbtn");
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle("active", btns[i].getAttribute("data-tab") === name);
    }
    var secs = document.querySelectorAll("section.tab");
    for (var k = 0; k < secs.length; k++) {
      secs[k].classList.toggle("active", secs[k].id === "tab-" + name);
    }
    if (!loaded[name]) {
      loaded[name] = true;
      loaders[name]();
    } else if (name === "overview") {
      renderOverview(); // charts measured their width while visible; re-fit after other tabs
    }
  }

  document.getElementById("tabs").addEventListener("click", function (ev) {
    var t = ev.target;
    if (t && t.classList && t.classList.contains("tabbtn")) showTab(t.getAttribute("data-tab"));
  });

  function bindFilter(groupId, key) {
    var group = document.getElementById(groupId);
    group.addEventListener("click", function (ev) {
      var t = ev.target;
      if (!t || !t.classList || !t.classList.contains("fbtn")) return;
      var btns = group.querySelectorAll(".fbtn");
      for (var i = 0; i < btns.length; i++) btns[i].classList.toggle("active", btns[i] === t);
      state[key] = t.getAttribute("data-value") || "";
      loadAi();
    });
  }
  bindFilter("ai-country", "country");
  bindFilter("ai-topic", "topic");

  showTab("overview");

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(function (err) {
      console.warn("service worker registration failed:", err);
    });
  }
})();
</script>
</body>
</html>
`;
