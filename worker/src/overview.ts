/**
 * Overview tab of the dashboard (dev-spec section 5): KPI tiles and charts built
 * from GET /api/overview. Hand-drawn SVG / HTML only (no chart library, no CDN).
 *
 * The three strings are spliced into DASHBOARD_HTML; OVERVIEW_JS runs inside the
 * dashboard's IIFE and uses its helpers (fmtTime, fetchJson, eventLabel, topicLabel).
 * Colors follow the dataviz palette's dark steps, validated against the panel
 * surface #161b22 (categorical slots 1-4 pass all adjacent CVD / contrast checks).
 */

export const OVERVIEW_CSS = `
  :root {
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500;
    --grid: #21262d; --axis: #30363d; --ink2: #c9d1d9;
    --st-good: #0ca30c; --st-warn: #fab219;
  }
  .ov-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 12px; }
  .ov-grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
  @media (min-width: 760px) {
    .ov-grid { grid-template-columns: 1fr 1fr; }
    .ov-grid .span2 { grid-column: 1 / -1; }
  }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; min-width: 0; }
  .card-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 10px; }
  .card-head h2 { font-size: 13px; font-weight: 600; }
  .card-head .sub { color: var(--muted); font-size: 12px; margin-left: 6px; font-weight: 400; }
  button.tblbtn { background: transparent; color: var(--muted); border: 1px solid var(--border); border-radius: 6px; padding: 1px 8px; font-size: 11px; cursor: pointer; flex-shrink: 0; }
  .card .tbl { display: none; overflow-x: auto; }
  .card.showtable .tbl { display: block; }
  .card.showtable .viz { display: none; }
  .tile .label { color: var(--muted); font-size: 12px; }
  .tile .value { font-size: 24px; font-weight: 600; margin-top: 2px; }
  .tile .note { color: var(--muted); font-size: 12px; margin-top: 2px; }
  .health { display: inline-flex; align-items: center; gap: 6px; font-size: 16px; font-weight: 600; margin-top: 6px; }
  .health .icon { font-size: 12px; }
  .legend { display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px; color: var(--ink2); margin-bottom: 6px; }
  .legend .key { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
  svg.chart { display: block; width: 100%; overflow: visible; }
  svg.chart text { fill: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
  svg.chart text.cap { fill: var(--ink2); }
  .hit { fill: transparent; cursor: default; }
  .hit:hover, .hit:focus { fill: rgba(255, 255, 255, 0.04); outline: none; }
  .bars { display: grid; grid-template-columns: minmax(70px, 38%) 1fr; gap: 6px 10px; align-items: center; }
  .bars .blabel { font-size: 12px; color: var(--ink2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .bars .brow { display: flex; align-items: center; gap: 6px; min-width: 0; border-radius: 4px; }
  .bars .brow:hover, .bars .brow:focus { background: rgba(255, 255, 255, 0.04); outline: none; }
  .bars .bar { height: 14px; background: var(--s1); border-radius: 0 4px 4px 0; min-width: 2px; }
  .bars .bval { font-size: 12px; color: var(--ink2); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .mkts { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
  .mkt { border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; min-width: 0; }
  .mkt .mname { color: var(--muted); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .mkt .mval { font-size: 16px; font-weight: 600; }
  .mkt .mchg { font-size: 12px; color: var(--ink2); font-variant-numeric: tabular-nums; }
  .evlist { list-style: none; }
  .evlist li { display: flex; gap: 10px; align-items: baseline; padding: 6px 0; border-bottom: 1px solid var(--border); }
  .evlist li:last-child { border-bottom: none; }
  .evlist .etitle { font-size: 13px; }
  .evlist .emeta { color: var(--muted); font-size: 12px; }
  .empty { color: var(--muted); font-size: 12px; padding: 12px 0; }
  #tip { position: fixed; display: none; z-index: 10; pointer-events: none; background: #0d1117; border: 1px solid var(--axis);
    border-radius: 6px; padding: 6px 8px; font-size: 12px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4); min-width: 110px; }
  #tip .ttitle { color: var(--muted); margin-bottom: 3px; }
  #tip .trow { display: flex; align-items: center; gap: 6px; }
  #tip .tkey { display: inline-block; width: 10px; height: 2px; border-radius: 1px; }
  #tip strong { font-variant-numeric: tabular-nums; }
  #tip .tlabel { color: var(--muted); }
`;

export const OVERVIEW_HTML = `
  <section class="tab active" id="tab-overview">
    <div class="status" id="overview-status">読み込み中…</div>
    <div class="ov-kpis" id="ov-kpis"></div>
    <div class="ov-grid">
      <div class="card span2" id="card-volume">
        <div class="card-head"><h2>記事数の推移<span class="sub">直近14日・情報源別</span></h2><button class="tblbtn" type="button">表</button></div>
        <div class="viz"></div><div class="tbl"></div>
      </div>
      <div class="card" id="card-topics">
        <div class="card-head"><h2>注目トピック<span class="sub">7日間の記事数</span></h2><button class="tblbtn" type="button">表</button></div>
        <div class="viz"></div><div class="tbl"></div>
      </div>
      <div class="card" id="card-events">
        <div class="card-head"><h2>イベント種別<span class="sub">7日間の件数</span></h2><button class="tblbtn" type="button">表</button></div>
        <div class="viz"></div><div class="tbl"></div>
      </div>
      <div class="card span2" id="card-markets">
        <div class="card-head"><h2>マーケット<span class="sub">日足・直近30本</span></h2><button class="tblbtn" type="button">表</button></div>
        <div class="viz"></div><div class="tbl"></div>
      </div>
      <div class="card" id="card-top-events">
        <div class="card-head"><h2>重要イベント<span class="sub">7日間の上位5件</span></h2></div>
        <div class="viz"></div>
      </div>
      <div class="card" id="card-repos">
        <div class="card-head"><h2>GitHub 急上昇<span class="sub">7日間のスター増</span></h2><button class="tblbtn" type="button">表</button></div>
        <div class="viz"></div><div class="tbl"></div>
      </div>
    </div>
  </section>
`;

export const OVERVIEW_JS = `
  // ---------------- overview tab ----------------
  var SVGNS = "http://www.w3.org/2000/svg";
  // most articles carry no country (Hacker News dominates), so the stack splits by source type
  var SOURCE_SERIES = [
    { key: "official", label: "企業・研究ブログ", color: "var(--s1)" },
    { key: "hn", label: "Hacker News", color: "var(--s2)" },
    { key: "central_bank", label: "中央銀行", color: "var(--s3)" },
    { key: "filing", label: "SEC 開示", color: "var(--s4)" }
  ];
  var overviewData = null;
  var tip = document.getElementById("tip");

  function h(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
  }
  function s(name, attrs) {
    var e = document.createElementNS(SVGNS, name);
    for (var k in attrs) {
      if (Object.prototype.hasOwnProperty.call(attrs, k)) e.setAttribute(k, String(attrs[k]));
    }
    return e;
  }
  function compact(n) {
    var a = Math.abs(n);
    if (a >= 1e6) return (n / 1e6).toFixed(a >= 1e7 ? 0 : 1) + "M";
    if (a >= 1e4) return (n / 1e3).toFixed(a >= 1e5 ? 0 : 1) + "K";
    return Math.round(n).toLocaleString("en-US");
  }
  function niceStep(raw) {
    if (raw <= 0) return 1;
    var p = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var steps = [1, 2, 2.5, 5, 10];
    for (var i = 0; i < steps.length; i++) if (steps[i] * p >= raw) return steps[i] * p;
    return 10 * p;
  }

  // one shared tooltip; rows = [{ value, label, color }]; every string goes through textContent
  function showTip(x, y, title, rows) {
    tip.textContent = "";
    tip.appendChild(h("div", "ttitle", title));
    rows.forEach(function (r) {
      var row = h("div", "trow");
      if (r.color) {
        var key = h("span", "tkey");
        key.style.background = r.color;
        row.appendChild(key);
      }
      row.appendChild(h("strong", "", r.value));
      if (r.label) row.appendChild(h("span", "tlabel", r.label));
      tip.appendChild(row);
    });
    tip.style.display = "block";
    var w = tip.offsetWidth, ht = tip.offsetHeight;
    var left = Math.min(x + 12, window.innerWidth - w - 8);
    var top = y - ht - 12 < 8 ? y + 16 : y - ht - 12;
    tip.style.left = Math.max(8, left) + "px";
    tip.style.top = top + "px";
  }
  function hideTip() { tip.style.display = "none"; }
  function bindTip(node, getTip) {
    node.setAttribute("tabindex", "0");
    node.addEventListener("pointermove", function (ev) { var t = getTip(ev); showTip(ev.clientX, ev.clientY, t[0], t[1]); });
    node.addEventListener("pointerleave", hideTip);
    node.addEventListener("focus", function () {
      var r = node.getBoundingClientRect(), t = getTip(null);
      showTip(r.left + r.width / 2, r.top, t[0], t[1]);
    });
    node.addEventListener("blur", hideTip);
  }

  function table(headers, rows) {
    var t = h("table");
    var tr = h("tr");
    headers.forEach(function (x) { tr.appendChild(h("th", "", x)); });
    var thead = h("thead"); thead.appendChild(tr); t.appendChild(thead);
    var tb = h("tbody");
    rows.forEach(function (r) {
      var row = h("tr");
      r.forEach(function (c) { row.appendChild(h("td", "", c)); });
      tb.appendChild(row);
    });
    t.appendChild(tb);
    var wrap = h("div", "tablewrap"); wrap.appendChild(t);
    return wrap;
  }
  function cardParts(id) {
    var card = document.getElementById(id);
    var viz = card.querySelector(".viz"), tbl = card.querySelector(".tbl");
    viz.textContent = "";
    if (tbl) tbl.textContent = "";
    return { card: card, viz: viz, tbl: tbl };
  }

  function kpiTile(label, value, note) {
    var t = h("div", "card tile");
    t.appendChild(h("div", "label", label));
    t.appendChild(h("div", "value", value));
    if (note) t.appendChild(h("div", "note", note));
    return t;
  }
  function renderKpis(d) {
    var box = document.getElementById("ov-kpis");
    box.textContent = "";
    var c = d.counts || {};
    box.appendChild(kpiTile("イベント（24時間）", compact(c.events_24h || 0), "7日間: " + compact(c.events_7d || 0)));
    box.appendChild(kpiTile("記事（24時間）", compact(c.articles_24h || 0), "7日間: " + compact(c.articles_7d || 0)));
    box.appendChild(kpiTile("論文（7日間）", compact(c.papers_7d || 0), ""));
    var hl = d.health || {};
    var stale = (hl.stale_sources || []).length, failed = hl.failure_count_24h || 0;
    var ok = stale === 0 && failed === 0;
    var t = h("div", "card tile");
    t.appendChild(h("div", "label", "収集の状態"));
    var st = h("div", "health");
    var icon = h("span", "icon", ok ? "●" : "▲");
    icon.style.color = ok ? "var(--st-good)" : "var(--st-warn)";
    st.appendChild(icon);
    st.appendChild(h("span", "", ok ? "正常" : "要確認"));
    t.appendChild(st);
    // a stale collector may still be running with partial failures, so name it rather than call it stopped
    var notes = [];
    if (stale) notes.push("24時間成功なし: " + hl.stale_sources.join(", "));
    if (failed) notes.push("24時間の失敗 " + failed + " 件");
    t.appendChild(h("div", "note", notes.length ? notes.join(" / ") : "全コレクター稼働中"));
    box.appendChild(t);
  }

  function dayList(generatedAt, n) {
    var end = Date.parse(String(generatedAt).slice(0, 10) + "T00:00:00Z");
    var out = [];
    for (var i = n - 1; i >= 0; i--) out.push(new Date(end - i * 86400000).toISOString().slice(0, 10));
    return out;
  }

  // stacked columns: articles per day, split by source type
  function renderVolume(d) {
    var p = cardParts("card-volume");
    var days = dayList(d.generated_at, d.days || 14);
    var byDay = {};
    days.forEach(function (day) { byDay[day] = { official: 0, hn: 0, central_bank: 0, filing: 0, total: 0 }; });
    (d.articles_by_day || []).forEach(function (r) {
      var b = byDay[r.day];
      if (!b) return;
      b[r.source_group] = (b[r.source_group] || 0) + r.n;
      b.total += r.n;
    });
    var max = 0;
    days.forEach(function (day) { max = Math.max(max, byDay[day].total); });
    if (max === 0) { p.viz.appendChild(h("div", "empty", "この期間の記事はまだありません")); return; }

    var legend = h("div", "legend");
    SOURCE_SERIES.forEach(function (sr) {
      var item = h("span");
      var key = h("span", "key"); key.style.background = sr.color;
      item.appendChild(key); item.appendChild(document.createTextNode(sr.label));
      legend.appendChild(item);
    });
    p.viz.appendChild(legend);

    var W = Math.max(280, p.viz.clientWidth), plotH = 170, top = 14, left = 34, right = 6, axisH = 22;
    var H = top + plotH + axisH, plotW = W - left - right;
    var step = niceStep(max / 4), yMax = Math.ceil(max / step) * step;
    var svg = s("svg", { "class": "chart", width: W, height: H, viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "直近" + days.length + "日の情報源別記事数" });
    for (var v = 0; v <= yMax + 1e-9; v += step) {
      var gy = top + plotH - (v / yMax) * plotH;
      svg.appendChild(s("line", { x1: left, x2: W - right, y1: gy, y2: gy, stroke: v === 0 ? "var(--axis)" : "var(--grid)", "stroke-width": 1 }));
      var lbl = s("text", { x: left - 6, y: gy + 4, "text-anchor": "end" }); lbl.textContent = compact(v); svg.appendChild(lbl);
    }
    var band = plotW / days.length, colW = Math.min(24, band * 0.6);
    var labelEvery = Math.ceil(40 / band);
    days.forEach(function (day, i) {
      var b = byDay[day], x = left + i * band + (band - colW) / 2, base = top + plotH;
      var segs = SOURCE_SERIES.filter(function (sr) { return b[sr.key] > 0; });
      segs.forEach(function (sr, j) {
        var hgt = (b[sr.key] / yMax) * plotH, isTop = j === segs.length - 1;
        var y0 = base - hgt, y1 = base - (j === 0 ? 0 : 2);
        if (y1 - y0 < 1) y0 = y1 - 1;
        var r = isTop ? Math.min(4, (y1 - y0) / 2, colW / 2) : 0;
        var d2 = "M" + x + "," + y1 + "V" + (y0 + r) + "Q" + x + "," + y0 + " " + (x + r) + "," + y0 +
          "H" + (x + colW - r) + "Q" + (x + colW) + "," + y0 + " " + (x + colW) + "," + (y0 + r) + "V" + y1 + "Z";
        var path = s("path", { d: d2 }); path.style.fill = sr.color;
        svg.appendChild(path);
        base -= hgt;
      });
      if ((days.length - 1 - i) % labelEvery === 0) {
        var t = s("text", { x: left + i * band + band / 2, y: top + plotH + 15, "text-anchor": "middle" });
        t.textContent = day.slice(5).replace("-", "/");
        svg.appendChild(t);
      }
      if (i === days.length - 1 && b.total > 0) {
        var cap = s("text", { "class": "cap", x: left + i * band + band / 2, y: top + plotH - (b.total / yMax) * plotH - 4, "text-anchor": "middle" });
        cap.textContent = compact(b.total);
        svg.appendChild(cap);
      }
      var hit = s("rect", { "class": "hit", x: left + i * band, y: top, width: band, height: plotH, "aria-label": day + " 合計 " + b.total });
      bindTip(hit, function () {
        return [day + "（合計 " + compact(b.total) + "）", SOURCE_SERIES.map(function (sr) {
          return { value: compact(b[sr.key]), label: sr.label, color: sr.color };
        })];
      });
      svg.appendChild(hit);
    });
    p.viz.appendChild(svg);
    p.tbl.appendChild(table(["日付"].concat(SOURCE_SERIES.map(function (sr) { return sr.label; }), ["合計"]), days.map(function (day) {
      var b = byDay[day];
      return [day].concat(SOURCE_SERIES.map(function (sr) { return b[sr.key]; }), [b.total]);
    })));
  }

  // ranked horizontal bars (one hue): items = [{ label, value, href }]
  function renderBars(id, items, unit, emptyMsg) {
    var p = cardParts(id);
    if (!items.length) { p.viz.appendChild(h("div", "empty", emptyMsg)); return; }
    var max = Math.max.apply(null, items.map(function (it) { return it.value; })) || 1;
    var grid = h("div", "bars");
    items.forEach(function (it) {
      var lab = h("div", "blabel");
      if (it.href) {
        var a = h("a", "", it.label);
        a.href = it.href; a.target = "_blank"; a.rel = "noopener noreferrer";
        lab.appendChild(a);
      } else {
        lab.textContent = it.label;
      }
      lab.title = it.label;
      var row = h("div", "brow");
      var bar = h("div", "bar");
      bar.style.width = Math.max(1, (it.value / max) * 82) + "%";
      row.appendChild(bar);
      row.appendChild(h("span", "bval", it.prefix ? it.prefix + compact(it.value) : compact(it.value)));
      row.setAttribute("aria-label", it.label + " " + it.value + unit);
      bindTip(row, function () { return [it.label, [{ value: it.value.toLocaleString("en-US") + unit }]]; });
      grid.appendChild(lab); grid.appendChild(row);
    });
    p.viz.appendChild(grid);
    p.tbl.appendChild(table(["項目", "値"], items.map(function (it) { return [it.label, it.value]; })));
  }

  // price precision by magnitude: 131,505 / 16.22 / 1.1011
  function fmtPrice(v) {
    var a = Math.abs(Number(v));
    var digits = a >= 10000 ? 0 : a >= 10 ? 2 : 4;
    return Number(v).toLocaleString("en-US", { minimumFractionDigits: Math.min(digits, 2), maximumFractionDigits: digits });
  }

  function fmtChange(m) {
    var pts = m.points, first = pts[0][1], last = pts[pts.length - 1][1];
    if (m.asset === "rate") {
      var bp = Math.round((last - first) * 100);
      return (bp > 0 ? "▲ +" : bp < 0 ? "▼ " : "– ") + bp + "bp";
    }
    if (!first) return "";
    var pct = ((last - first) / Math.abs(first)) * 100;
    return (pct > 0 ? "▲ +" : pct < 0 ? "▼ " : "– ") + pct.toFixed(2) + "%";
  }

  // market tiles: latest close, change over the window, sparkline with crosshair
  function renderMarkets(d) {
    var p = cardParts("card-markets");
    var mk = (d.markets || []).filter(function (m) { return m.points && m.points.length >= 2; });
    if (!mk.length) { p.viz.appendChild(h("div", "empty", "価格データがまだありません")); return; }
    var grid = h("div", "mkts");
    p.viz.appendChild(grid);
    mk.forEach(function (m) {
      var pts = m.points, last = pts[pts.length - 1];
      var tile = h("div", "mkt");
      tile.appendChild(h("div", "mname", m.name));
      tile.appendChild(h("div", "mval", fmtPrice(last[1])));
      tile.appendChild(h("div", "mchg", fmtChange(m) + "（" + pts.length + "本）"));
      grid.appendChild(tile);
      var W = Math.max(100, tile.clientWidth - 20), H = 40, pad = 5;
      var lo = Infinity, hi = -Infinity;
      pts.forEach(function (q) { lo = Math.min(lo, q[1]); hi = Math.max(hi, q[1]); });
      if (hi === lo) { hi += 1; lo -= 1; }
      function px(i) { return pad + (i / (pts.length - 1)) * (W - pad * 2); }
      function py(v) { return pad + (1 - (v - lo) / (hi - lo)) * (H - pad * 2); }
      var svg = s("svg", { "class": "chart", width: W, height: H, viewBox: "0 0 " + W + " " + H, role: "img",
        "aria-label": m.name + " の直近" + pts.length + "本の終値" });
      var dpath = pts.map(function (q, i) { return (i ? "L" : "M") + px(i).toFixed(1) + "," + py(q[1]).toFixed(1); }).join("");
      svg.appendChild(s("path", { d: dpath, fill: "none", stroke: "var(--s1)", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
      svg.appendChild(s("circle", { cx: px(pts.length - 1), cy: py(last[1]), r: 4, fill: "var(--s1)", stroke: "var(--panel)", "stroke-width": 2 }));
      var cross = s("line", { y1: 0, y2: H, stroke: "var(--muted)", "stroke-width": 1, visibility: "hidden" });
      var dot = s("circle", { r: 4, fill: "var(--s1)", stroke: "var(--panel)", "stroke-width": 2, visibility: "hidden" });
      svg.appendChild(cross); svg.appendChild(dot);
      var hit = s("rect", { "class": "hit", x: 0, y: 0, width: W, height: H, "aria-label": m.name + " 最新 " + last[1] });
      var idx = pts.length - 1;
      bindTip(hit, function (ev) {
        if (ev) {
          var r = svg.getBoundingClientRect();
          idx = Math.round(((ev.clientX - r.left) / r.width * W - pad) / (W - pad * 2) * (pts.length - 1));
          idx = Math.max(0, Math.min(pts.length - 1, idx));
        } else {
          idx = pts.length - 1;
        }
        cross.setAttribute("x1", px(idx)); cross.setAttribute("x2", px(idx)); cross.setAttribute("visibility", "visible");
        dot.setAttribute("cx", px(idx)); dot.setAttribute("cy", py(pts[idx][1])); dot.setAttribute("visibility", "visible");
        return [pts[idx][0], [{ value: fmtPrice(pts[idx][1]), label: m.name, color: "var(--s1)" }]];
      });
      hit.addEventListener("pointerleave", function () { cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); });
      hit.addEventListener("blur", function () { cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); });
      svg.appendChild(hit);
      tile.appendChild(svg);
    });
    p.tbl.appendChild(table(["銘柄", "最新値", "日付", "期間の変化"], mk.map(function (m) {
      var last = m.points[m.points.length - 1];
      return [m.name, fmtPrice(last[1]), last[0], fmtChange(m)];
    })));
  }

  function renderTopEvents(d) {
    var p = cardParts("card-top-events");
    var evs = d.top_events || [];
    if (!evs.length) { p.viz.appendChild(h("div", "empty", "この7日間のイベントはまだありません")); return; }
    var ul = h("ul", "evlist");
    evs.forEach(function (e) {
      var li = h("li");
      li.appendChild(h("span", "score", Math.round(Number(e.importance) || 0)));
      var body = h("div");
      body.appendChild(h("div", "etitle", e.title || ""));
      body.appendChild(h("div", "emeta", [eventLabel(e.event_type), e.country, fmtTime(e.occurred_at), "ソース " + (e.source_count || 1)].filter(Boolean).join(" · ")));
      li.appendChild(body);
      ul.appendChild(li);
    });
    p.viz.appendChild(ul);
  }

  function renderOverview() {
    var d = overviewData;
    if (!d) return;
    renderKpis(d);
    renderVolume(d);
    renderBars("card-topics", (d.topics_7d || []).map(function (r) { return { label: topicLabel(r.topic), value: r.n }; }), " 件", "この7日間のトピック付き記事はまだありません");
    renderBars("card-events", (d.event_types_7d || []).map(function (r) { return { label: eventLabel(r.event_type), value: r.n }; }), " 件", "この7日間のイベントはまだありません");
    renderMarkets(d);
    renderTopEvents(d);
    renderBars("card-repos", (d.repo_movers_7d || []).map(function (r) { return { label: r.full_name, value: r.delta, href: r.url, prefix: "+" }; }), " stars", "7日間でスターが増えたリポジトリはまだありません");
  }

  function loadOverview() {
    fetchJson("/api/overview", "overview-status", function (data) {
      overviewData = data;
      renderOverview();
    });
  }

  document.getElementById("tab-overview").addEventListener("click", function (ev) {
    var t = ev.target;
    if (!t || !t.classList || !t.classList.contains("tblbtn")) return;
    var card = t.closest(".card");
    var on = card.classList.toggle("showtable");
    t.textContent = on ? "グラフ" : "表";
  });

  var resizeTimer = null;
  window.addEventListener("resize", function () {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      if (document.getElementById("tab-overview").classList.contains("active")) renderOverview();
    }, 150);
  });
`;
