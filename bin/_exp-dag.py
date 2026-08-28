#!/usr/bin/env python3
"""_exp-dag.py — render the experiment DAG as ONE self-contained interactive HTML page.

Reads {"project":…, "nodes":[…], "edges":[…]} as JSON on stdin, writes HTML to stdout. `lab-exp dag`
builds that JSON (it owns graph_maps, so the edge semantics stay in one place) and pipes it here.

No external assets: layout, markdown rendering, pan/zoom, and the README panel are all inline. That
matters because the page is meant to be handed to `lab-report publish`, which encrypts it — the
decrypted document is written with document.write, so a CDN <script> would work, but a self-contained
page keeps the report readable offline and years later.
"""
import html
import json
import sys


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"_exp-dag: invalid JSON on stdin: {e}", file=sys.stderr)
        return 2
    if not data.get("nodes"):
        print("_exp-dag: no experiments in the registry — nothing to draw", file=sys.stderr)
        return 3
    title = html.escape(data.get("project") or "experiments", quote=True)
    live = "--live" in sys.argv[1:]
    sys.stdout.write(
        TEMPLATE.replace("__TITLE__", title).replace("__LIVE__", "true" if live else "false")
                .replace("__DATA__", json.dumps(data, ensure_ascii=False))
    )
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>__TITLE__ — experiment DAG</title>
<style>
 :root {
   color-scheme: light dark;
   --bg:#fbfbfa; --fg:#1a1a19; --mut:#6b6b68; --line:#d6d5d1; --panel:#fff;
   --planned:#8a8a86; --running:#2f6fd0; --ran:#1f9d55; --failed:#d2453f; --other:#8557c9;
   --superseded:#b3b1ab;
 }
 @media (prefers-color-scheme: dark) {
   :root { --bg:#16171a; --fg:#e9e9e6; --mut:#9a9a96; --line:#33353a; --panel:#1d1f23; }
 }
 * { box-sizing: border-box; }
 html,body { height:100%; margin:0; }
 body { font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
        background:var(--bg); color:var(--fg); display:flex; flex-direction:column; }
 header { padding:.7rem 1rem; border-bottom:1px solid var(--line); display:flex; gap:.9rem;
          align-items:center; flex-wrap:wrap; }
 header h1 { font-size:1rem; margin:0; font-weight:650; }
 header .count { color:var(--mut); font-size:.85em; }
 input[type=search] { flex:1; min-width:10rem; max-width:22rem; padding:.4rem .6rem; font:inherit;
   border:1px solid var(--line); border-radius:7px; background:var(--panel); color:inherit; }
 .legend { display:flex; gap:.7rem; font-size:.8rem; color:var(--mut); flex-wrap:wrap; }
 .legend i { display:inline-block; width:.62rem; height:.62rem; border-radius:50%; margin-right:.28rem;
             vertical-align:middle; }
 main { flex:1; display:flex; min-height:0; }
 #graph { flex:1; min-width:0; position:relative; overflow:hidden; cursor:grab; }
 #graph.drag { cursor:grabbing; }
 #hint { position:absolute; left:.8rem; bottom:.7rem; font-size:.78rem; color:var(--mut);
         pointer-events:none; }
 aside { width:min(30rem,42vw); border-left:1px solid var(--line); background:var(--panel);
         overflow:auto; padding:1.1rem 1.3rem; }
 aside.empty { display:grid; place-items:center; color:var(--mut); text-align:center; }
 aside h2 { font-size:1.05rem; margin:.1rem 0 .15rem; }
 .meta { color:var(--mut); font-size:.83rem; margin-bottom:.5rem; }
 .chips { display:flex; gap:.35rem; flex-wrap:wrap; margin:.5rem 0 1rem; }
 .chip { font-size:.75rem; padding:.13rem .5rem; border-radius:999px; border:1px solid var(--line); }
 .kv { display:grid; grid-template-columns:auto 1fr; gap:.2rem .8rem; font-size:.85rem;
       margin:0 0 1rem; }
 .kv dt { color:var(--mut); }
 .kv dd { margin:0; overflow-wrap:anywhere; }
 .rel a { display:block; font-size:.85rem; text-decoration:none; color:inherit; padding:.12rem 0; }
 .rel a:hover { text-decoration:underline; }
 .md { border-top:1px solid var(--line); padding-top:.9rem; }
 .md h1,.md h2,.md h3 { font-size:.98rem; margin:1.1rem 0 .35rem; }
 .md h1:first-child,.md h2:first-child { margin-top:0; }
 .md p,.md li { font-size:.88rem; }
 .md code { font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;
            background:color-mix(in srgb, currentColor 9%, transparent); padding:.08em .35em;
            border-radius:4px; }
 .md pre { background:color-mix(in srgb, currentColor 7%, transparent); padding:.6rem .75rem;
           border-radius:8px; overflow:auto; }
 .md pre code { background:none; padding:0; }
 .md hr { border:0; border-top:1px solid var(--line); margin:1rem 0; }
 svg text { user-select:none; }
 .node rect { stroke-width:1.5px; }
 .node.dim { opacity:.16; }
 .edge.dim { opacity:.06; }
 .edge.hot { stroke-width:2.2px; }
 /* search HIT: emphasize the match rather than removing everything else, so a result keeps the
    lineage around it visible. Needs its own accent because .dim alone reads as "slightly faded
    page" once several nodes match. */
 .node.hit rect { stroke-width:3px; }
 .node.hit { filter: drop-shadow(0 0 7px color-mix(in srgb, var(--fg) 40%, transparent)); }
 .node.miss { opacity:.13; }
 .edge.miss { opacity:.05; }
 .actions { display:flex; gap:.5rem; margin:.2rem 0 .9rem; }
 .actions button { font:inherit; font-size:.8rem; padding:.3rem .7rem; border-radius:7px;
   border:1px solid var(--line); background:var(--bg); color:inherit; cursor:pointer; }
 .actions button:hover { border-color:var(--mut); }
 #graph.picking { cursor:crosshair; }
 .node.pick-old rect { stroke-dasharray:5 3; stroke-width:2.5px; }
</style></head><body>
<header>
  <h1>__TITLE__</h1><span class="count" id="count"></span>
  <input type="search" id="q" placeholder="filter by id, tag, kind, finding…">
  <label class="legend" id="implabel" style="display:none;cursor:pointer"><input type="checkbox" id="imponly"> ★ important only (<span id="impn"></span>)</label>
  <label class="legend" id="suplabel" style="display:none;cursor:pointer"><input type="checkbox" id="showsup"> show superseded (<span id="supn"></span>)</label>
  <span class="legend" id="legend"></span>
</header>
<main>
  <div id="graph"><svg id="svg"></svg><div id="hint">drag to pan · scroll to zoom · click a node</div></div>
  <aside id="side" class="empty"><div>Select an experiment to read its README.</div></aside>
</main>
<script>
const DATA = __DATA__;
// LIVE: rendered by `lab-exp dag --serve` — the server that produced this page also accepts
// POST /supersede and /undo, so the panel grows write buttons. A static render stays read-only.
const LIVE = __LIVE__;
const NODES = DATA.nodes, EDGES = DATA.edges;
const byId = new Map(NODES.map(n => [n.id, n]));
const COLORS = { planned:"--planned", running:"--running", ran:"--ran", done:"--ran", superseded:"--superseded",
                 failed:"--failed" };
const cssv = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const statusColor = s => cssv(COLORS[s] || "--other");

/* ---- adjacency ------------------------------------------------------------------------- */
const parents = new Map(), children = new Map();
NODES.forEach(n => { parents.set(n.id, []); children.set(n.id, []); });
for (const e of EDGES) {
  if (!byId.has(e.child) || !byId.has(e.parent)) continue;   // dangling edge: registry pruned it
  parents.get(e.child).push(e.parent);
  children.get(e.parent).push(e.child);
}

/* ---- layered layout -------------------------------------------------------------------- */
// Longest-path layering: depth = 1 + max(depth of parents). Iterative with a cap rather than
// recursive, so a malformed based_on cycle degrades to a drawing instead of a stack overflow.
function layout(ids) {
  const set = new Set(ids);
  const par = id => parents.get(id).filter(p => set.has(p));
  const depth = new Map(ids.map(i => [i, 0]));
  for (let pass = 0; pass < ids.length + 1; pass++) {
    let moved = false;
    for (const id of ids) {
      const ps = par(id);
      const want = ps.length ? Math.max(...ps.map(p => depth.get(p))) + 1 : 0;
      if (want > depth.get(id)) { depth.set(id, want); moved = true; }
    }
    if (!moved) break;
  }
  const layers = [];
  for (const id of ids) (layers[depth.get(id)] ||= []).push(id);
  // ids sort chronologically (YYYYMMDD-slug), a sane starting order; then barycenter passes pull
  // children under their parents to cut edge crossings.
  layers.forEach(l => l.sort());
  for (let it = 0; it < 6; it++) {
    for (let li = 1; li < layers.length; li++) {
      const above = new Map(layers[li-1].map((id, i) => [id, i]));
      layers[li].sort((a, b) => bary(a, above) - bary(b, above));
    }
  }
  function bary(id, above) {
    const ps = par(id).map(p => above.get(p)).filter(v => v !== undefined);
    return ps.length ? ps.reduce((s, v) => s + v, 0) / ps.length : 1e9;
  }
  const W = 210, H = 62, GAPX = 26, GAPY = 54, SUBGAP = 16, pos = new Map();
  // WRAP wide layers into sub-rows. Experiments often carry no --based-on, so "one layer holding
  // most of the graph" is the common case rather than an edge case: 9 roots laid out as a single
  // row is ~2100px, which zoom-to-fit renders at k≈0.35 — 13px labels become 4.6px slivers. Nodes
  // keep their depth (DAG semantics unchanged); only their placement wraps.
  const maxLayer = Math.max(...layers.map(l => (l ? l.length : 0)));
  const perRow = Math.max(1, Math.ceil(Math.sqrt(maxLayer * 1.6)));   // ~1.6:1 target aspect
  const full = Math.min(maxLayer, perRow) * (W + GAPX) - GAPX;
  let y = 0;
  layers.forEach(l => {
    if (!l) return;
    for (let i = 0; i < l.length; i += perRow) {
      const row = l.slice(i, i + perRow);
      const rowW = row.length * (W + GAPX) - GAPX;
      row.forEach((id, j) => pos.set(id, { x: (full - rowW) / 2 + j * (W + GAPX), y, w: W, h: H }));
      y += H + SUBGAP;
    }
    y += GAPY - SUBGAP;                                               // gap BETWEEN layers
  });
  return { pos, width: full, height: Math.max(H, y - GAPY) };
}

/* ---- render ---------------------------------------------------------------------------- */
const svg = document.getElementById("svg");
const NS = "http://www.w3.org/2000/svg";
// The graph is laid out ONCE over every node and never re-laid-out. Search highlights in place:
// removing non-matches would reflow the DAG on each keystroke, so a node moved out from under the
// cursor and the lineage that gives a match its meaning vanished with it. `matched` is null when
// the box is empty, which means "no search lens active" (distinct from "nothing matched").
let view = { x: 0, y: 0, k: 1 }, selected = null, matched = null;
const ALL_IDS = NODES.map(n => n.id);
// Superseded experiments are HIDDEN by default -- they were valid once and stay in the registry
// (append-only), but they answer "what did I do", not "what is true now". The checkbox restores
// them; navigating to one from a visible node's parent/child list restores them automatically.
const SUP = new Set(NODES.filter(n => n.status === "superseded").map(n => n.id));
// 'important' is a plain token in the ordinary tags field -- the DAG just gives it a filter and
// (when live) a toggle; lab-exp important <id> is the CLI spelling.
const isImp = id => (byId.get(id).tags || "").split(",").map(t => t.trim()).includes("important");
const impCount = () => ALL_IDS.filter(isImp).length;
let showSup = false, impOnly = false;
const shownIds = () => ALL_IDS.filter(id => (showSup || !SUP.has(id)) && (!impOnly || isImp(id)));

function el(t, a = {}, kids = []) {
  const n = document.createElementNS(NS, t);
  for (const [k, v] of Object.entries(a)) n.setAttribute(k, v);
  for (const c of [].concat(kids)) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  return n;
}
const esc = s => String(s ?? "");

let POS = null;   // node id -> {x,y,w,h}; kept from the single layout so search can frame matches

function draw() {
  const ids = shownIds(), SH = new Set(ids);
  const { pos, width, height } = layout(ids);
  POS = pos;
  svg.replaceChildren();
  const gEdges = el("g"), gNodes = el("g");

  for (const e of EDGES) {
    if (!SH.has(e.parent) || !SH.has(e.child)) continue;
    const a = pos.get(e.parent), b = pos.get(e.child);
    const x1 = a.x + a.w / 2, y1 = a.y + a.h, x2 = b.x + b.w / 2, y2 = b.y;
    const m = (y1 + y2) / 2;
    gEdges.appendChild(el("path", {
      class: "edge", "data-c": e.child, "data-p": e.parent,
      d: `M${x1},${y1} C${x1},${m} ${x2},${m} ${x2},${y2}`,
      fill: "none", stroke: cssv("--line"), "stroke-width": 1.4, "marker-end": "url(#arrow)"
    }));
  }
  for (const id of ids) {
    const n = byId.get(id), p = pos.get(id), c = statusColor(n.status);
    const g = el("g", { class: "node", "data-id": id, transform: `translate(${p.x},${p.y})`,
                        style: "cursor:pointer" });
    g.appendChild(el("rect", { width: p.w, height: p.h, rx: 9, fill: cssv("--panel"), stroke: c }));
    g.appendChild(el("rect", { width: 4, height: p.h, rx: 2, fill: c }));
    const slug = id.replace(/^\d{8}-/, ""), date = (id.match(/^(\d{4})(\d{2})(\d{2})/) || []).slice(1).join("-");
    const label = (isImp(id) ? "★ " : "") + slug;
    g.appendChild(el("text", { x: 14, y: 23, "font-size": 13, "font-weight": 600, fill: cssv("--fg") },
                     label.length > 24 ? label.slice(0, 23) + "…" : label));
    if ((n.reports || []).length) g.appendChild(el("text", { x: p.w - 16, y: 15, "font-size": 10,
                                             fill: cssv("--running") }, "▤"));
    g.appendChild(el("text", { x: 14, y: 41, "font-size": 11, fill: cssv("--mut") },
                     [date, n.kind, n.status].filter(Boolean).join("  ·  ")));
    g.addEventListener("click", ev => { ev.stopPropagation(); nodeClick(id); });
    gNodes.appendChild(g);
  }
  const defs = el("defs");
  defs.appendChild(el("marker", { id: "arrow", viewBox: "0 0 10 10", refX: 9, refY: 5,
    markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" },
    [el("path", { d: "M0,0 L10,5 L0,10 z", fill: cssv("--line") })]));
  svg.append(defs, gEdges, gNodes);
  svg.setAttribute("width", "100%"); svg.setAttribute("height", "100%");
  fit(width, height);
  if (selected) highlight(selected);
}

// ONE copy of the framing policy: pad, then floor the zoom at a LEGIBILITY limit rather than
// always fitting — below ~0.55 the 13px labels stop being readable, and an unreadable overview is
// worse than one you have to pan. Content beyond the viewport stays reachable by drag/scroll.
function frameBox(x0, y0, x1, y1, pad, maxK) {
  const r = document.getElementById("graph").getBoundingClientRect();
  const w = Math.max(x1 - x0, 1), h = Math.max(y1 - y0, 1);
  const k = Math.max(0.55, Math.min(maxK, (r.width - pad) / w, (r.height - pad) / h));
  view = { k, x: r.width / 2 - k * (x0 + x1) / 2,
              y: Math.max(pad / 2, r.height / 2 - k * (y0 + y1) / 2) };
  apply();
}
const fit = (w, h) => frameBox(0, 0, w, h, 60, 1);
const apply = () => svg.setAttribute("viewBox",
  `${-view.x / view.k} ${-view.y / view.k} ${svg.clientWidth / view.k} ${svg.clientHeight / view.k}`);

/* ---- selection + relatives ------------------------------------------------------------- */
// DIRECT neighbours only: the transitive ancestry cone lit up half the graph on well-connected
// nodes and read as clutter. Deeper lineage stays one click away (the panel's parent/child links
// walk it hop by hop) and `lab-exp lineage` prints it whole.
function highlight(id) {
  const hot = new Set([id, ...parents.get(id), ...children.get(id)]);
  svg.querySelectorAll(".node").forEach(g =>
    g.classList.toggle("dim", !hot.has(g.dataset.id)));
  svg.querySelectorAll(".edge").forEach(p => {
    const on = (p.dataset.c === id && hot.has(p.dataset.p)) ||
               (p.dataset.p === id && hot.has(p.dataset.c));
    p.classList.toggle("dim", !on);
    p.classList.toggle("hot", on);
    p.setAttribute("stroke", on ? statusColor(byId.get(id).status) : cssv("--line"));
  });
}
function clearHighlight() {
  svg.querySelectorAll(".node,.edge").forEach(x => x.classList.remove("dim", "hot"));
  svg.querySelectorAll(".edge").forEach(p => p.setAttribute("stroke", cssv("--line")));
  applySearch();   // deselecting must not wipe an active search's highlighting
}
// Highlighting in place is only useful if you can SEE the highlights: this graph is routinely wider
// than the viewport, so a search can report "29 / 190 match" with every match off-screen. Pan (and
// zoom out, never past the legibility floor) to bring them into view -- but ONLY when none is
// already visible, so typing doesn't yank a view you are reading out from under you.
function frameMatches() {
  if (!matched || !matched.size || !POS) return;
  const r = document.getElementById("graph").getBoundingClientRect();
  const vx = -view.x / view.k, vy = -view.y / view.k;
  const vw = svg.clientWidth / view.k, vh = svg.clientHeight / view.k;
  const boxes = [...matched].map(id => POS.get(id)).filter(Boolean);
  if (!boxes.length) return;
  if (boxes.some(b => b.x + b.w > vx && b.x < vx + vw && b.y + b.h > vy && b.y < vy + vh)) return;
  frameBox(Math.min(...boxes.map(b => b.x)), Math.min(...boxes.map(b => b.y)),
           Math.max(...boxes.map(b => b.x + b.w)), Math.max(...boxes.map(b => b.y + b.h)),
           80, view.k);
}
// Search and selection are two lenses over the SAME drawing, both driven by classes rather than by
// rebuilding: `hit`/`miss` belong to search, `hot`/`dim` to the selected node's lineage. The most
// recent interaction wins, which is what makes clicking a result behave the way you expect.
function applySearch() {
  svg.querySelectorAll(".node").forEach(g => {
    const on = !matched || matched.has(g.dataset.id);
    g.classList.toggle("hit", !!matched && on);
    g.classList.toggle("miss", !!matched && !on);
  });
  svg.querySelectorAll(".edge").forEach(p => {
    const on = !matched || (matched.has(p.dataset.c) && matched.has(p.dataset.p));
    p.classList.toggle("miss", !!matched && !on);
  });
}

const side = document.getElementById("side");
/* ---- live supersede (only when served by `lab-exp dag --serve`) ------------------------- */
let picking = null;    // {old} while waiting for a successor click
const hint = document.getElementById("hint");
async function api(path, body) {
  try {
    const r = await fetch(path, { method: "POST", headers: {"Content-Type": "application/json"},
                                  body: JSON.stringify(body) });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || "request failed");
    return j;
  } catch (e) { alert("supersede failed: " + e.message); return null; }
}
function setPicking(p) {
  picking = p;
  document.getElementById("graph").classList.toggle("picking", !!p);
  svg.querySelectorAll(".node").forEach(g => g.classList.toggle("pick-old", !!p && g.dataset.id === p.old));
  hint.textContent = p ? "click the SUPERSEDING experiment — Esc to cancel"
                       : "drag to pan · scroll to zoom · click a node";
}
function applyLocal(id, status, by) {
  const n = byId.get(id);
  n.status = status; n.superseded_by = by;
  if (status === "superseded") SUP.add(id); else SUP.delete(id);
  const lab = document.getElementById("suplabel");
  lab.style.display = SUP.size ? "" : "none";
  document.getElementById("supn").textContent = SUP.size;
  draw();
  document.getElementById("count").textContent = countText();
  select(id);
}
async function doSupersede(oldId, byId_) {
  const why = window.prompt("Why is it superseded? (optional — goes in the README)", "");
  if (why === null) { setPicking(null); return; }        // Cancel aborts
  const res = await api("/supersede", { old: oldId, by: byId_, why });
  setPicking(null);
  if (res) applyLocal(oldId, "superseded", res.by || "");
}
function nodeClick(id) {
  if (picking) {
    if (id !== picking.old) doSupersede(picking.old, id);
    return;
  }
  select(id);
}

function select(id) {
  if (SUP.has(id) && !showSup) {           // parent/child link into hidden territory: reveal it
    const cb = document.getElementById("showsup");
    cb.checked = true; cb.dispatchEvent(new Event("change"));
  }
  selected = id; highlight(id);
  const n = byId.get(id);
  const rel = (ids, label) => ids.length ? `<div class="meta" style="margin-top:.6rem">${label}</div>
    <div class="rel">${ids.map(i => `<a href="#" data-go="${esc(i)}">${esc(i)}</a>`).join("")}</div>` : "";
  const kv = [["kind", n.kind], ["status", n.status], ["date", n.date], ["agent", n.agent],
              ["host", n.host], ["git", n.git_sha], ["metrics", n.metrics], ["dir", n.dir],
              ["superseded by", (n.superseded_by || "").trim()]]
    .filter(([, v]) => v).map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("");
  side.className = "";
  side.innerHTML = `
    <h2>${esc(id.replace(/^\d{8}-/, ""))}</h2>
    <div class="meta">${esc(id)}</div>
    ${LIVE ? `<div class="actions">${picking && picking.old === id
        ? `<button id="btn-nosucc">supersede with NO successor</button><button id="btn-cancel">cancel</button>`
        : n.status === "superseded"
          ? `<button id="btn-undo">undo supersede</button>`
          : `<button id="btn-sup">mark superseded…</button>`}<button id="btn-imp">${isImp(id) ? "☆ unmark important" : "★ mark important"}</button></div>` : ""}
    ${(n.reports || []).length ? `<div class="actions" style="flex-wrap:wrap">${n.reports.map(rp =>
        `<a href="${LIVE ? "/report/" + esc(id) + "/" + esc(rp) : esc(n.dir) + "/out/" + esc(rp)}"
            target="_blank" style="font-size:.85rem">▤ ${esc(rp.replace(/\.html$/, ""))}</a>`).join("")}</div>` : ""}
    ${n.finding ? `<p style="font-size:.9rem">${esc(n.finding)}</p>` : ""}
    <div class="chips">${(n.tags || "").split(",").filter(Boolean)
        .map(t => `<span class="chip">${esc(t.trim())}</span>`).join("")}</div>
    <dl class="kv">${kv}</dl>
    ${rel(parents.get(id), "parents")}${rel(children.get(id), "children")}
    <div class="md">${n.readme ? md(n.readme) : "<p class='meta'>(no README.md)</p>"}</div>`;
  side.querySelectorAll("[data-go]").forEach(a =>
    a.addEventListener("click", ev => { ev.preventDefault(); select(a.dataset.go); }));
  const on = (bid, fn) => { const b = document.getElementById(bid); if (b) b.addEventListener("click", fn); };
  on("btn-sup",    () => { setPicking({ old: id }); select(id); });
  on("btn-cancel", () => { setPicking(null); select(id); });
  on("btn-nosucc", () => doSupersede(id, ""));
  on("btn-undo",   async () => { if (await api("/undo", { id })) applyLocal(id, "done", ""); });
  on("btn-imp",    async () => {
    const on_ = !isImp(id);
    if (!await api("/important", { id, on: on_ })) return;
    const n2 = byId.get(id);
    const toks = (n2.tags || "").split(",").map(t => t.trim()).filter(t => t && t !== "important");
    if (on_) toks.push("important");
    n2.tags = toks.join(",");
    refreshImp(); draw(); select(id);
  });
  side.scrollTop = 0;
}

/* ---- minimal markdown ------------------------------------------------------------------ */
// Deliberately small: experiment READMEs are headings, prose, lists, code and links. Escaping
// happens FIRST, so README content can never inject markup into this page.
function md(src) {
  let s = src.replace(/^---\n[\s\S]*?\n---\n/, "");            // drop the frontmatter block
  s = s.replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  const fences = [];
  s = s.replace(/```[\w-]*\n([\s\S]*?)```/g, (_, c) => `@@FENCE:${fences.push(c) - 1}@@`);
  s = s.replace(/^### (.*)$/gm, "<h3>$1</h3>").replace(/^## (.*)$/gm, "<h2>$1</h2>")
       .replace(/^# (.*)$/gm, "<h1>$1</h1>").replace(/^---$/gm, "<hr>");
  s = s.replace(/`([^`\n]+)`/g, "<code>$1</code>")
       .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
       .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" rel="noopener">$1</a>');
  s = s.replace(/(?:^[-*] .*(?:\n|$))+/gm, m =>
        "<ul>" + m.trim().split("\n").map(l => `<li>${l.replace(/^[-*] /, "")}</li>`).join("") + "</ul>");
  s = s.split(/\n{2,}/).map(b =>
        /^\s*<(h\d|ul|hr|pre)/.test(b) ? b : (b.trim() ? `<p>${b.trim()}</p>` : "")).join("\n");
  return s.replace(/@@FENCE:(\d+)@@/g, (_, i) => `<pre><code>${fences[+i]}</code></pre>`);
}

/* ---- filter, pan, zoom ----------------------------------------------------------------- */
const q = document.getElementById("q");
q.addEventListener("input", () => {
  const t = q.value.trim().toLowerCase();
  matched = !t ? null : new Set(NODES.filter(n => (showSup || !SUP.has(n.id)) && (!impOnly || isImp(n.id))).filter(n =>
    [n.id, n.kind, n.status, n.tags, n.finding].join(" ").toLowerCase().includes(t)).map(n => n.id));
  const nShown = shownIds().length;
  const hits = matched ? matched.size : nShown;
  document.getElementById("count").textContent =
    matched ? `${hits} / ${nShown} match` : countText();
  // A search supersedes the selected node's lineage highlighting, but keeps the side panel — you
  // are usually searching for the NEXT thing to open, not discarding what you just read.
  clearHighlight();   // also re-applies the search classes
  frameMatches();
});
// Escape clears the search from anywhere — otherwise a stray query leaves the graph dimmed with no
// obvious way back except selecting the text.
addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if (picking) { setPicking(null); if (selected) select(selected); return; }
  if (q.value) { q.value = ""; q.dispatchEvent(new Event("input")); }
});
const gdiv = document.getElementById("graph");
let drag = null, dragged = false;
// Capture is taken LAZILY, only once the pointer has actually moved past a threshold. Capturing on
// pointerdown redirects every subsequent event to this div, so the browser dispatches `click` here
// instead of on the node under the cursor — which made nodes completely unclickable while looking
// correct in every isolated test. A few px of slop also stops a shaky click from reading as a drag.
const DRAG_SLOP = 4;
gdiv.addEventListener("pointerdown", e => {
  if (e.button !== 0) return;
  drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, captured: false };
  dragged = false;
});
gdiv.addEventListener("pointermove", e => {
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  if (!drag.captured) {
    if (Math.hypot(dx, dy) < DRAG_SLOP) return;
    drag.captured = dragged = true;
    gdiv.classList.add("drag");
    try { gdiv.setPointerCapture(e.pointerId); } catch (err) {}
  }
  view.x = drag.vx + dx; view.y = drag.vy + dy; apply();
});
const endDrag = e => {
  if (drag && drag.captured && e && e.pointerId !== undefined) {
    try { gdiv.releasePointerCapture(e.pointerId); } catch (err) {}
  }
  drag = null; gdiv.classList.remove("drag");
};
gdiv.addEventListener("pointerup", endDrag);
gdiv.addEventListener("pointercancel", endDrag);
gdiv.addEventListener("wheel", e => {
  e.preventDefault();
  const r = gdiv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  const f = Math.exp(-e.deltaY * 0.0015), k = Math.min(3, Math.max(0.15, view.k * f));
  view.x = mx - (mx - view.x) * (k / view.k); view.y = my - (my - view.y) * (k / view.k);
  view.k = k; apply();
}, { passive: false });
// Background click clears the selection — but NOT when it is the tail of a pan, or every drag
// would deselect whatever you were reading.
svg.addEventListener("click", () => {
  if (dragged) { dragged = false; return; }
  selected = null; clearHighlight();
  side.className = "empty"; side.innerHTML = "<div>Select an experiment to read its README.</div>";
});
addEventListener("resize", () => apply());

document.getElementById("legend").innerHTML =
  [...new Set(NODES.map(n => n.status).filter(Boolean))].sort()
    .map(s => `<span><i style="background:${statusColor(s)}"></i>${esc(s)}</span>`).join("");
const countText = () => (showSup || !SUP.size ? `${shownIds().length} experiments`
  : `${shownIds().length} experiments (${SUP.size} superseded hidden)`)
  + (impOnly ? " · important only" : "");
function refreshImp() {
  const n = impCount();
  const lab = document.getElementById("implabel");
  lab.style.display = (n || LIVE) ? "" : "none";   // live pages show it once marking is possible
  document.getElementById("impn").textContent = n;
}
if (SUP.size) {
  document.getElementById("suplabel").style.display = "";
  document.getElementById("supn").textContent = SUP.size;
  document.getElementById("showsup").addEventListener("change", ev => {
    showSup = ev.target.checked;
    if (selected && SUP.has(selected) && !showSup) { selected = null; }
    draw();
    q.dispatchEvent(new Event("input"));   // re-runs the search AND recomputes the count
  });
}
refreshImp();
document.getElementById("imponly").addEventListener("change", ev => {
  impOnly = ev.target.checked;
  if (selected && impOnly && !isImp(selected)) selected = null;
  draw();
  q.dispatchEvent(new Event("input"));   // re-runs the search AND recomputes the count
});
document.getElementById("count").textContent = countText();
draw();
</script>
</body></html>
"""


if __name__ == "__main__":
    sys.exit(main())
