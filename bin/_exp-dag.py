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
    args = sys.argv[1:]
    live = "--live" in args
    intents = args[args.index("--intents") + 1] if "--intents" in args and args.index("--intents") + 1 < len(args) else ""
    sys.stdout.write(
        TEMPLATE.replace("__TITLE__", title).replace("__LIVE__", "true" if live else "false")
                .replace("__INTENTS__", json.dumps(intents))
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
 #datef { align-items:center; gap:.4rem; }
 #datef select, #datef input[type=date] { font:inherit; font-size:.85rem; padding:.25rem .4rem; border:1px solid var(--line);
   border-radius:6px; background:var(--panel); color:inherit; }
 #datef input[type=date] { max-width:9.5rem; }
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
 @media (max-width: 640px) {
   header { padding:.5rem .8rem; gap:.35rem .7rem; }
   #legend { display:none; }               /* the status colours are on the nodes themselves */
   #hint { display:none; }                 /* touch has no scroll-to-zoom, and it overlapped the bottom row */
   main { flex-direction:column; }
   #graph { min-height:0; flex:1; }
   aside { width:auto; max-height:40vh; border-left:0; border-top:1px solid var(--line); padding:.9rem 1rem; }
   aside.empty { max-height:none; flex:0 0 auto; padding:.5rem; font-size:.85rem; }
 }
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
 .notes { border-top:1px solid var(--line); padding-top:.7rem; margin-bottom:.9rem; }
 .note { border-left:2px solid var(--line); padding:.25rem .6rem; margin:.35rem 0; font-size:.88rem; }
 .note .stamp { color:var(--mut); font-size:.78rem; display:flex; gap:.6rem; align-items:baseline; }
 .note .stamp a { margin-left:auto; color:var(--mut); text-decoration:none; font-size:.78rem; }
 .note .stamp a:hover { color:var(--fg); }
 .note .body { white-space:pre-wrap; overflow-wrap:anywhere; }
 .note.queued { border-left-color:var(--running); }
 .noteform textarea { width:100%; min-height:3.6rem; font:inherit; font-size:.88rem; padding:.4rem .5rem;
   border:1px solid var(--line); border-radius:7px; background:var(--bg); color:inherit; resize:vertical; }
 .noteform .row { display:flex; gap:.5rem; align-items:center; margin-top:.35rem; }
 .noteform .row .meta { margin:0; }
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
 /* Every node is always drawn. --status is set inline per node; the shapes read --c / --t1 / --t2,
    so a class recolours a node without fighting the inline style. Fading is done with COLOURS,
    never group opacity: an SVG group with opacity < 1 needs its own offscreen buffer, and a click
    that set that on 400 nodes at once (plus a transition) blinked the whole drawing. */
 .node { cursor:pointer; --c: var(--status); --t1: var(--fg); --t2: var(--mut); }
 .node rect.box { fill:var(--panel); stroke:var(--c); stroke-width:1.5px; transition: stroke .3s; }
 .node rect.acc { fill:var(--c); transition: fill .3s; }
 .node text.t1 { font-size:13px; font-weight:600; fill:var(--t1); transition: fill .3s; }
 .node text.t2 { font-size:11px; fill:var(--t2); transition: fill .3s; }
 .node text.rep { font-size:10px; fill:var(--t2); }
 /* OUT = fails a filter (superseded, important-only, date, search): greyed and laid out in the band
    ABOVE the focused nodes, but still drawn, so a focused node's lineage can be traced into it. */
 .node.out { --c: color-mix(in srgb, var(--mut) 45%, var(--bg)); --t1: color-mix(in srgb, var(--fg) 42%, var(--bg));
             --t2: color-mix(in srgb, var(--mut) 55%, var(--bg)); }
 /* selection lens: direct neighbours stay, everything else fades further (colours again) */
 .node.dim { --c: color-mix(in srgb, var(--mut) 22%, var(--bg)); --t1: color-mix(in srgb, var(--fg) 16%, var(--bg));
             --t2: color-mix(in srgb, var(--mut) 22%, var(--bg)); }
 .edge { stroke:var(--line); stroke-width:1.4px; fill:none; marker-end:url(#arrow);
         transition: stroke .3s, stroke-opacity .3s; }
 .edge.out { stroke-opacity:.35; marker-end:url(#arrow-faint); }
 .edge.dim { stroke-opacity:.12; marker-end:url(#arrow-faint); }
 .edge.hot { stroke:var(--hot, var(--fg)); stroke-width:2.2px; stroke-opacity:1; marker-end:url(#arrow-hot); }
 #arrow path { fill:var(--line); }
 #arrow-faint path { fill:color-mix(in srgb, var(--line) 35%, var(--bg)); }
 #arrow-hot path { fill:var(--hot, var(--fg)); }
 .band-line { stroke:var(--line); stroke-dasharray:7 6; stroke-width:1.2px; }
 .band-label { font-size:11px; fill:var(--mut); letter-spacing:.02em; }
 .bands { transition: opacity .35s ease; }
 .actions { display:flex; gap:.5rem; margin:.2rem 0 .9rem; }
 .actions button { font:inherit; font-size:.8rem; padding:.3rem .7rem; border-radius:7px;
   border:1px solid var(--line); background:var(--bg); color:inherit; cursor:pointer; }
 .actions button:hover { border-color:var(--mut); }
 #graph.picking { cursor:crosshair; }
 #intents[hidden] { display:none; }   /* the flex rule below would otherwise beat the hidden attribute */
 #intents { position:fixed; left:0; right:0; bottom:0; z-index:5; padding:.55rem 1rem; font-size:.85rem;
            background:var(--panel); border-top:1px solid var(--line); display:flex; gap:.6rem;
            align-items:center; flex-wrap:wrap; }
 #intents button { font:inherit; padding:.25rem .6rem; border:1px solid var(--line); border-radius:6px;
                   background:transparent; color:inherit; cursor:pointer; }
 #intents button:first-of-type { border-color:var(--running); color:var(--running); font-weight:600; }
 .node.pick-old rect.box { stroke-dasharray:5 3; stroke-width:2.5px; }
</style></head><body>
<header>
  <h1><a id="hubup" href="../" style="color:inherit;text-decoration:none" title="all projects">__TITLE__</a></h1><span class="count" id="count"></span>
  <input type="search" id="q" placeholder="filter by id, tag, kind, finding…">
  <span class="legend" id="datef"><select id="datepre" title="filter by experiment date">
      <option value="">all dates</option><option value="7">last 7 days</option><option value="30">last 30 days</option>
      <option value="90">last 90 days</option><option value="custom">custom range…</option></select>
    <span id="daterange" style="display:none"><input type="date" id="datefrom"> – <input type="date" id="dateto"></span></span>
  <label class="legend" id="implabel" style="display:none;cursor:pointer"><input type="checkbox" id="imponly"> ★ important only (<span id="impn"></span>)</label>
  <label class="legend" id="suplabel" style="display:none;cursor:pointer"><input type="checkbox" id="showsup"> include superseded (<span id="supn"></span>)</label>
  <span class="legend" id="legend"></span>
</header>
<main>
  <div id="graph"><svg id="svg"></svg><div id="hint">drag to pan · scroll to zoom · click a node</div></div>
  <aside id="side" class="empty"><div>Select an experiment to read its README.</div></aside>
</main>
<div id="intents" hidden><span><b id="intn"></b> queued change(s) — already shown here; the boxes apply them on
  the next publish (about half an hour).</span>
  <button id="int-send">Send to GitHub</button><button id="int-copy">Copy commands</button><button id="int-clear">Discard</button></div>
<script>
const DATA = __DATA__;
// LIVE: rendered by `lab-exp dag --serve` — the server that produced this page also accepts
// POST /supersede and /undo, so the panel grows write buttons. A static render stays read-only.
const LIVE = __LIVE__;
// INTENTS: a static page (the hub on GitHub Pages) cannot write, but it can QUEUE marks in the
// browser and hand them to the lab boxes as one GitHub issue the user submits (logged in on the
// phone); the hub publisher applies them with lab-exp on its next run. "" = read-only page.
const INTENTS = __INTENTS__;
const CAN_MARK = LIVE || !!INTENTS;
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
function layout(ids, parentMap) {
  const set = new Set(ids);
  const pm = parentMap || parents;
  const par = id => (pm.get(id) || []).filter(p => set.has(p));
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
  const sparse = [];
  for (const id of ids) (sparse[depth.get(id)] ||= []).push(id);
  const layers = sparse.filter(Boolean);           // depths need not be contiguous; holes would crash .sort()
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

/* ---- render state ---------------------------------------------------------------------- */
const svg = document.getElementById("svg");
const NS = "http://www.w3.org/2000/svg";
// EVERY node is always drawn. The filters (superseded, important-only, date, search) split the
// graph into a FOCUSED band and an OUT band: out nodes are greyed and laid out ABOVE the focused
// ones, and every edge stays drawn, so a focused node's lineage can be traced into the greyed band
// instead of vanishing (hiding them orphaned lineages; greying them in place buried the few you
// wanted among hundreds). A filter change lays both bands out again and ANIMATES nodes, edges and
// the camera to their new places; nothing is rebuilt, so the node under the cursor stays the same
// element. `matched` is null when the search box is empty (no search lens), else the match set.
let view = { x: 0, y: 0, k: 1 }, selected = null, matched = null;
const ALL_IDS = NODES.map(n => n.id);
// Superseded experiments are OUT by default -- they were valid once and stay in the registry
// (append-only), but they answer "what did I do", not "what is true now". The checkbox brings
// them into the focused band.
const SUP = new Set(NODES.filter(n => n.status === "superseded").map(n => n.id));
// 'important' is a plain token in the ordinary tags field -- the DAG just gives it a filter and
// (when live) a toggle; lab-exp important <id> is the CLI spelling.
const tagsOf = n => (n.tags || "").split(",").map(t => t.trim()).filter(Boolean);
const isImp = id => tagsOf(byId.get(id)).includes("important");
const impCount = () => ALL_IDS.filter(isImp).length;
let showSup = false, impOnly = false;
let dateFrom = "", dateTo = "";      // inclusive YYYY-MM-DD bounds; "" = open. Filters by experiment date.
const dateOf = n => (n.date || "").slice(0, 10)
  || ((m => m ? `${m[1]}-${m[2]}-${m[3]}` : "")(/^(\d{4})(\d{2})(\d{2})-/.exec(n.id)));
const inDate = id => {
  if (!dateFrom && !dateTo) return true;
  const d = dateOf(byId.get(id));
  return !!d && (!dateFrom || d >= dateFrom) && (!dateTo || d <= dateTo);
};

/* ---- README notes: the same grammar lab-exp's note_upsert() writes ----------------------- */
// `## Notes` holds `- **<ts>** (<author>): <text>` items, continuation lines indented by two
// spaces; the stamp is the note's identity. The page edits n.readme in memory with the same
// rules so a queued note shows immediately and reads back identically once the box applies it.
const NOTE_LINE = /^- \*\*(\S+)\*\*(?: \(([^)]*)\))?: ?(.*)$/;
function notesSplit(txt) {
  const m = /^## Notes[ \t]*\n/m.exec(txt || "");
  if (!m) return { before: txt || "", entries: [], after: "" };
  const start = m.index + m[0].length, rest = txt.slice(start);
  const m2 = /^#{1,2} /m.exec(rest);
  const end = start + (m2 ? m2.index : rest.length);
  const entries = [];
  for (const line of txt.slice(start, end).split("\n")) {
    const mm = NOTE_LINE.exec(line);
    if (mm) entries.push({ ts: mm[1], author: mm[2] || "", text: mm[3] });
    else if (line.startsWith("  ") && entries.length) entries[entries.length - 1].text += "\n" + line.slice(2);
  }
  return { before: txt.slice(0, m.index), entries, after: txt.slice(end) };
}
function notesRender(entries) {
  const lines = ["## Notes"];
  for (const e of entries) {
    const [first, ...rest] = (e.text || "").split("\n");
    lines.push(`- **${e.ts}**` + (e.author ? ` (${e.author})` : "") + `: ${first}`);
    for (const r of rest) lines.push("  " + r);
  }
  return lines.join("\n") + "\n";
}
function noteUpsertText(txt, ts, text, author, replace) {
  const { before, entries, after } = notesSplit(txt || "");
  text = (text || "").trim();
  if (replace) {
    const i = entries.findIndex(e => e.ts === replace);
    if (i < 0) return txt;
    if (text) { entries[i].text = text; if (author) entries[i].author = author; } else entries.splice(i, 1);
  } else {
    if (!text) return txt;
    entries.push({ ts, author, text });
  }
  const section = entries.length ? notesRender(entries) : "";
  return /^## Notes[ \t]*\n/m.test(txt || "") ? before + section + after : (txt || "").replace(/\n+$/, "") + "\n\n" + section;
}
const stripNotes = txt => { const { before, after } = notesSplit(txt || ""); return before + after; };
const noteStamp = () => new Date().toISOString().slice(0, 16) + "Z";

/* ---- queued marks (static pages with INTENTS) ------------------------------------------- */
// The view applies a mark immediately; the boxes apply it later. Reconciled on every load: a mark
// the published data already carries is dropped from the queue.
const IKEY = "labexp-intents:" + (DATA.project || "");
const OPP = { supersede: "unsupersede", unsupersede: "supersede", important: "unimportant", unimportant: "important" };
let PENDING = [];
try { PENDING = JSON.parse(localStorage.getItem(IKEY) || "[]"); } catch (e) { PENDING = []; }
const snapshot = (n, op) => op === "note" ? { readme: n.readme || "" }
  : op === "important" || op === "unimportant"
  ? { tags: n.tags || "" } : { status: n.status, superseded_by: n.superseded_by || "" };
function applyIntent(it) {
  const n = byId.get(it.id); if (!n) return;
  if (it.op === "supersede")   { n.status = "superseded"; n.superseded_by = it.by || ""; SUP.add(it.id); }
  if (it.op === "unsupersede") { n.status = "done"; n.superseded_by = ""; SUP.delete(it.id); }
  if (it.op === "important" || it.op === "unimportant") {
    const t = tagsOf(n).filter(x => x !== "important"); if (it.op === "important") t.push("important");
    n.tags = t.join(",");
  }
  if (it.op === "note") n.readme = noteUpsertText(n.readme, it.at, it.text, it.author || "", it.replace || "");
}
function revertIntent(it) {
  const n = byId.get(it.id); if (!n || !it.prev) return;
  Object.assign(n, it.prev);
  if (n.status === "superseded") SUP.add(it.id); else SUP.delete(it.id);
}
function reflected(it) {
  const n = byId.get(it.id); if (!n) return true;
  if (it.op === "supersede")   return n.status === "superseded" && (n.superseded_by || "").trim() === (it.by || "");
  if (it.op === "unsupersede") return n.status !== "superseded";
  if (it.op === "important")   return isImp(it.id);
  if (it.op === "unimportant") return !isImp(it.id);
  if (it.op === "note") {
    const e = notesSplit(n.readme || "").entries.find(x => x.ts === (it.replace || it.at));
    return it.text.trim() ? !!e && e.text === it.text.trim() : !e;   // published with this text (or gone, for a deletion)
  }
  return true;
}
PENDING = PENDING.filter(it => !reflected(it));
PENDING.forEach(it => { it.prev = snapshot(byId.get(it.id), it.op); applyIntent(it); });
function savePending() { try { localStorage.setItem(IKEY, JSON.stringify(PENDING)); } catch (e) {} refreshIntents(); }
function queueIntent(op, id, extra) {
  const n = byId.get(id);
  // notes: any number per node; a second edit of the SAME note (same stamp) replaces the queued one
  const same = op === "note"
    ? PENDING.filter(p => p.op === "note" && p.id === id && (p.replace || p.at) === (extra.replace || extra.at))
    : PENDING.filter(p => p.id === id && (p.op === op || p.op === OPP[op]));
  same.forEach(revertIntent);                              // at most one queued mark per family per node
  PENDING = PENDING.filter(p => !same.includes(p));
  if (!same.some(p => p.op === OPP[op])) {                 // the opposite of a queued mark just drops it
    const it = { op, id, ...(extra || {}), prev: snapshot(n, op), t: Date.now() };
    applyIntent(it); PENDING.push(it);
  }
  savePending();
}
const shq = s => '"' + String(s).replace(/[\r\n]+/g, " ").replace(/["\\]/g, "'") + '"';
const b64 = s => btoa(unescape(encodeURIComponent(s)));
const intentLines = () => PENDING.map(it => it.op === "supersede"
  ? `supersede ${it.id}` + (it.by ? ` --by ${it.by}` : "") + (it.why ? ` --why ${shq(it.why)}` : "")
  : it.op === "note"
  ? `note ${it.id} --at ${it.at}` + (it.replace ? ` --replace ${it.replace}` : "") + (it.author ? ` --author ${shq(it.author)}` : "")
    + ` --b64 ${b64(it.text)}`
  : `${it.op} ${it.id}`);
function refreshIntents() {
  const bar = document.getElementById("intents"); if (!bar) return;
  bar.hidden = !PENDING.length;
  const sent = PENDING.filter(it => it.sent).length;
  document.getElementById("intn").textContent = PENDING.length + (sent ? ` (${sent} sent)` : "");
  document.getElementById("int-send").textContent = sent && sent === PENDING.length ? "Send again" : "Send to GitHub";
}
function afterMark(id) {
  refreshSup(); refreshImp(); refreshNodeStyles(); refilter({ force: true });
  select(id);
}
// THE focus predicate -- the only definition. Every filter, search included, lives here; a new
// filter gets added here once.
const passes = id => (showSup || !SUP.has(id)) && (!impOnly || isImp(id)) && inDate(id)
                     && (!matched || matched.has(id));
const visible = passes;                          // older name, kept for callers
const shownIds = () => ALL_IDS.filter(passes);

function el(t, a = {}, kids = []) {
  const n = document.createElementNS(NS, t);
  for (const [k, v] of Object.entries(a)) n.setAttribute(k, v);
  for (const c of [].concat(kids)) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  return n;
}
const esc = s => String(s ?? "");

let POS = new Map();   // node id -> {x,y,w,h}: CURRENT positions (mid-animation included)
let FOCUS = null;      // the focused id set as of the last relayout
const W = 210, H = 62; // node box; layout() owns the gaps

/* ---- persistent DOM: built once, restyled and moved afterwards -------------------------- */
const world = el("g", { id: "world" });          // pan/zoom is ONE transform on this group
const gBands = el("g", { class: "bands" }), gEdges = el("g"), gNodes = el("g");
const NODE_EL = new Map(), EDGE_EL = [];
function buildDom() {
  const defs = el("defs");
  for (const mid of ["arrow", "arrow-faint", "arrow-hot"])
    defs.appendChild(el("marker", { id: mid, viewBox: "0 0 10 10", refX: 9, refY: 5,
      markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" },
      [el("path", { d: "M0,0 L10,5 L0,10 z" })]));
  for (const e of EDGES) {
    if (!byId.has(e.child) || !byId.has(e.parent) || e.child === e.parent) continue;   // dangling edge: registry pruned it
    const p = el("path", { class: "edge", "data-c": e.child, "data-p": e.parent });
    EDGE_EL.push({ el: p, parent: e.parent, child: e.child });
    gEdges.appendChild(p);
  }
  for (const id of ALL_IDS) {
    const g = el("g", { class: "node", "data-id": id });
    g.appendChild(el("rect", { class: "box", width: W, height: H, rx: 9 }));
    g.appendChild(el("rect", { class: "acc", width: 4, height: H, rx: 2 }));
    g.appendChild(el("text", { class: "t1", x: 14, y: 23 }));
    g.appendChild(el("text", { class: "rep", x: W - 16, y: 15 }, "▤"));
    g.appendChild(el("text", { class: "t2", x: 14, y: 41 }));
    g.addEventListener("click", ev => { ev.stopPropagation(); nodeClick(id); });
    NODE_EL.set(id, g);
    gNodes.appendChild(g);
  }
  gBands.appendChild(el("line", { class: "band-line", id: "band-line" }));
  gBands.appendChild(el("text", { class: "band-label", id: "band-top" }));
  gBands.appendChild(el("text", { class: "band-label", id: "band-bot" }));
  world.append(gBands, gEdges, gNodes);
  svg.append(defs, world);
  svg.setAttribute("width", "100%"); svg.setAttribute("height", "100%");
  refreshNodeStyles();
}
// Labels and colours come from the data, which marks (supersede, important) change in place.
function refreshNodeStyles() {
  for (const id of ALL_IDS) {
    const n = byId.get(id), g = NODE_EL.get(id);
    g.style.setProperty("--status", statusColor(n.status));
    const slug = id.replace(/^\d{8}-/, ""), date = dateOf(n);   // recorded date, else the id's
    const label = (isImp(id) ? "★ " : "") + slug;
    g.querySelector(".t1").textContent = label.length > 24 ? label.slice(0, 23) + "…" : label;
    g.querySelector(".t2").textContent = [date, n.kind, n.status].filter(Boolean).join("  ·  ");
    g.querySelector(".rep").style.display = (n.reports || []).length ? "" : "none";
  }
}

/* ---- two bands: greyed (out) above, focused below --------------------------------------- */
const BAND_GAP = 120;
function layoutBands(focus) {
  const inIds = ALL_IDS.filter(id => focus.has(id)), outIds = ALL_IDS.filter(id => !focus.has(id));
  const empty = { pos: new Map(), width: 0, height: 0 };
  const top = outIds.length ? layout(outIds) : empty, bot = inIds.length ? layout(inIds) : empty;
  const width = Math.max(top.width, bot.width, 1);
  const pos = new Map(), dxTop = (width - top.width) / 2, dxBot = (width - bot.width) / 2;
  top.pos.forEach((p, id) => pos.set(id, { x: p.x + dxTop, y: p.y, w: p.w, h: p.h }));
  const yBot = outIds.length ? top.height + BAND_GAP : 0;
  bot.pos.forEach((p, id) => pos.set(id, { x: p.x + dxBot, y: p.y + yBot, w: p.w, h: p.h }));
  return {
    pos, width, height: yBot + bot.height, nOut: outIds.length, nIn: inIds.length,
    bot: inIds.length ? { x0: dxBot, y0: yBot, x1: dxBot + bot.width, y1: yBot + bot.height } : null,
    divider: outIds.length && inIds.length ? top.height + BAND_GAP / 2 : null,
  };
}
function dividerOf(L) {
  if (L.divider === null) return null;
  // labels sit at the focused band's left edge, which is what the camera frames
  return { y: L.divider, lx: L.bot ? L.bot.x0 : 0, x0: -40, x1: L.width + 40, nOut: L.nOut, nIn: L.nIn };
}
function placeDivider() {
  gBands.style.opacity = DIV ? 1 : 0;
  if (!DIV) return;
  const line = document.getElementById("band-line");
  line.setAttribute("x1", DIV.x0); line.setAttribute("x2", DIV.x1);
  line.setAttribute("y1", DIV.y); line.setAttribute("y2", DIV.y);
  const t = document.getElementById("band-top"), b = document.getElementById("band-bot");
  const tgt = TARGET && TARGET.div ? TARGET.div : DIV;    // counts read from the destination
  t.setAttribute("x", DIV.lx); t.setAttribute("y", DIV.y - 9);
  t.textContent = `↑ ${tgt.nOut} greyed out by the current filters`;
  b.setAttribute("x", DIV.lx); b.setAttribute("y", DIV.y + 17);
  b.textContent = `↓ ${tgt.nIn} shown`;
}

/* ---- geometry from POS ------------------------------------------------------------------ */
// A parent normally sits above its child (bottom -> top). A focused parent whose child was greyed
// sits BELOW it; then the edge leaves the parent's top and enters the child's bottom, so the
// arrowhead still arrives from outside the box instead of piercing it.
function edgePath(a, b) {
  const down = b.y >= a.y + a.h;
  const x1 = a.x + a.w / 2, y1 = down ? a.y + a.h : a.y, x2 = b.x + b.w / 2, y2 = down ? b.y : b.y + b.h;
  const m = (y1 + y2) / 2;
  return `M${x1},${y1} C${x1},${m} ${x2},${m} ${x2},${y2}`;
}
function placeAll() {
  for (const [id, p] of POS) NODE_EL.get(id).setAttribute("transform", `translate(${p.x},${p.y})`);
  for (const e of EDGE_EL) {
    const a = POS.get(e.parent), b = POS.get(e.child);
    if (a && b) e.el.setAttribute("d", edgePath(a, b));
  }
  placeDivider();
  apply();
}

/* ---- animation: positions, divider and camera move together ----------------------------- */
let anim = null, TARGET = null, animGuard = null;   // TARGET = {pos, view, div} the motion is heading to
let DIV = null, DIV_FROM = null;                    // divider geometry: current, and where it started
const ease = u => u < .5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
const MOTION = matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 560;
const lerpDiv = (a, b, e) => (!a || !b) ? b : { y: a.y + (b.y - a.y) * e, lx: a.lx + (b.lx - a.lx) * e,
                                                 x0: a.x0 + (b.x0 - a.x0) * e, x1: a.x1 + (b.x1 - a.x1) * e };
// Finish a running motion instantly. Only while one runs: the camera target is stale as soon as
// the user pans by hand, so restoring it later would yank the view back.
function snapToTarget() {
  clearTimeout(animGuard);
  if (!anim) return;
  cancelAnimationFrame(anim.raf); anim = null;
  if (TARGET) { POS = new Map(TARGET.pos); view = { ...TARGET.view }; DIV = TARGET.div; placeAll(); }
}
document.addEventListener("visibilitychange", () => { if (document.hidden) snapToTarget(); });
function animateTo(targetPos, targetView, ms, targetDiv) {
  if (targetDiv === undefined) targetDiv = TARGET ? TARGET.div : DIV;
  clearTimeout(animGuard);
  // Same layout already in flight, only the camera target changed (a click landed mid-motion):
  // bend the camera path instead of restarting the whole motion -- a restart re-eases from rest,
  // which shows as a hitch.
  if (anim && ms && anim.posTarget === targetPos) {
    const e = anim.e;
    if (e < 1) anim.v0 = { k: (view.k - e * targetView.k) / (1 - e), x: (view.x - e * targetView.x) / (1 - e),
                           y: (view.y - e * targetView.y) / (1 - e) };
    TARGET = { pos: targetPos, view: targetView, div: targetDiv };
    animGuard = setTimeout(snapToTarget, anim.ms + 400);
    return;
  }
  if (anim) { cancelAnimationFrame(anim.raf); anim = null; }
  // a relayout that lands mid-animation starts from where things ARE, not where they were going
  const from = new Map(ALL_IDS.map(id => [id, POS.get(id) || targetPos.get(id)]));
  DIV_FROM = DIV;
  TARGET = { pos: targetPos, view: targetView, div: targetDiv };
  if (!ms) { POS = new Map(targetPos); view = { ...targetView }; DIV = targetDiv; placeAll(); return; }
  const a = anim = { raf: 0, t0: performance.now(), ms, from, v0: { ...view }, posTarget: targetPos, e: 0 };
  const step = now => {
    if (anim !== a) return;
    const u = Math.min(1, (now - a.t0) / a.ms), e = a.e = ease(u);
    const tp = TARGET.pos, tv = TARGET.view;
    for (const id of ALL_IDS) {
      const f = a.from.get(id), b = tp.get(id);
      POS.set(id, { x: f.x + (b.x - f.x) * e, y: f.y + (b.y - f.y) * e, w: b.w, h: b.h });
    }
    view = { k: a.v0.k + (tv.k - a.v0.k) * e, x: a.v0.x + (tv.x - a.v0.x) * e, y: a.v0.y + (tv.y - a.v0.y) * e };
    DIV = lerpDiv(DIV_FROM, TARGET.div, e);
    placeAll();
    if (u < 1) a.raf = requestAnimationFrame(step); else { anim = null; clearTimeout(animGuard); }
  };
  a.raf = requestAnimationFrame(step);
  animGuard = setTimeout(snapToTarget, ms + 400);   // frames stopped coming (hidden tab, throttling)
}

/* ---- framing ---------------------------------------------------------------------------- */
// ONE copy of the framing policy: pad, then floor the zoom at a LEGIBILITY limit rather than
// always fitting — below ~0.55 the 13px labels stop being readable, and an unreadable overview is
// worse than one you have to pan. Content beyond the viewport stays reachable by drag/scroll.
function frameFor(x0, y0, x1, y1, pad, maxK) {
  // An empty graph (every node filtered out) has no extent: frame a fixed box instead of NaN.
  if (![x0, y0, x1, y1].every(Number.isFinite)) { x0 = 0; y0 = 0; x1 = 400; y1 = 200; }
  const r = document.getElementById("graph").getBoundingClientRect();
  const w = Math.max(x1 - x0, 1), h = Math.max(y1 - y0, 1);
  const k = Math.max(0.55, Math.min(maxK, (r.width - pad) / w, (r.height - pad) / h));
  // A box taller than the viewport (zoom floored) is pinned by its TOP edge, wherever it sits in
  // the drawing; a box that fits is centred. (Clamping y to the padding, as before, silently
  // showed the top of the whole drawing instead of a focused band lower down.)
  const tall = k * h + pad > r.height;
  return { k, x: r.width / 2 - k * (x0 + x1) / 2,
              y: tall ? pad / 2 - k * y0 : r.height / 2 - k * (y0 + y1) / 2 };
}
function frameBox(x0, y0, x1, y1, pad, maxK) { view = frameFor(x0, y0, x1, y1, pad, maxK); apply(); }
// Camera = a transform on the world group. Rewriting the svg viewBox every frame instead made the
// browser re-lay-out every text label per frame on a 400-node page, which read as flicker.
const apply = () => world.setAttribute("transform", `translate(${view.x},${view.y}) scale(${view.k})`);
// Pan (at the current zoom) so a node you navigated to is on screen; a no-op when it already is.
// Pan by the SMALLEST amount that brings the node fully on screen (with a margin), at the current
// zoom; a no-op when it already is. While a relayout is in flight this is judged against where
// the layout and camera are HEADING, and the motion keeps heading there with a bent camera path;
// otherwise against the live view, which the user may have panned by hand.
function ensureVisible(id) {
  const running = !!anim;
  const pos = running ? TARGET.pos : POS, v = running ? TARGET.view : view;
  const p = pos.get(id); if (!p) return;
  const r = document.getElementById("graph").getBoundingClientRect(), M = 24;
  const sx0 = v.x + v.k * p.x - M, sy0 = v.y + v.k * p.y - M;            // node box in screen px
  const sx1 = v.x + v.k * (p.x + p.w) + M, sy1 = v.y + v.k * (p.y + p.h) + M;
  let dx = 0, dy = 0;
  if (sx0 < 0) dx = -sx0; else if (sx1 > r.width) dx = r.width - sx1;
  if (sy0 < 0) dy = -sy0; else if (sy1 > r.height) dy = r.height - sy1;
  if (!dx && !dy) return;
  animateTo(pos, { k: v.k, x: v.x + dx, y: v.y + dy }, MOTION);
}

/* ---- THE entry point after any filter change -------------------------------------------- */
// Recomputes the focus set, restyles, and — only when the set actually changed — lays the two
// bands out again and animates everything to its new place, framing the focused band.
function refilter(opts = {}) {
  const focus = new Set(shownIds());
  const changed = !FOCUS || focus.size !== FOCUS.size || [...focus].some(id => !FOCUS.has(id));
  FOCUS = focus;
  for (const [id, g] of NODE_EL) g.classList.toggle("out", !focus.has(id));
  for (const e of EDGE_EL) e.el.classList.toggle("out", !(focus.has(e.parent) && focus.has(e.child)));
  document.getElementById("count").textContent = countText();
  if (!picking) hint.textContent = focus.size ? "drag to pan · scroll to zoom · click a node"
                                              : "nothing matches the current filters — everything is greyed above";
  if (changed || opts.force) {
    const L = layoutBands(focus);
    const b = L.bot || { x0: 0, y0: 0, x1: L.width, y1: L.height };   // frame the focused band, else everything
    animateTo(L.pos, frameFor(b.x0, b.y0, b.x1, b.y1, 60, 1), opts.instant ? 0 : MOTION, dividerOf(L));
  }
  if (selected) highlight(selected);
}

/* ---- selection + relatives ------------------------------------------------------------- */
// DIRECT neighbours only: the transitive ancestry cone lit up half the graph on well-connected
// nodes and read as clutter. Deeper lineage stays one click away (the panel's parent/child links
// walk it hop by hop) and `lab-exp lineage` prints it whole.
function highlight(id) {
  const hot = new Set([id, ...(parents.get(id) || []), ...(children.get(id) || [])]);
  svg.style.setProperty("--hot", statusColor(byId.get(id).status));
  for (const [nid, g] of NODE_EL) g.classList.toggle("dim", !hot.has(nid));
  for (const e of EDGE_EL) {
    const on = (e.child === id && hot.has(e.parent)) || (e.parent === id && hot.has(e.child));
    e.el.classList.toggle("dim", !on);
    e.el.classList.toggle("hot", on);
  }
}
function clearHighlight() {
  svg.querySelectorAll(".node,.edge").forEach(x => x.classList.remove("dim", "hot"));
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
  } catch (e) { alert("request failed: " + e.message); return null; }
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
  refreshSup(); refreshNodeStyles(); refilter({ force: true });
  select(id);
}
async function doSupersede(oldId, byId_) {
  const why = window.prompt("Why is it superseded? (optional — goes in the README)", "");
  if (why === null) { setPicking(null); return; }        // Cancel aborts
  setPicking(null);
  if (!LIVE) { queueIntent("supersede", oldId, { by: byId_, why }); afterMark(oldId); return; }
  const res = await api("supersede", { old: oldId, by: byId_, why });
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
  selected = id; highlight(id); ensureVisible(id);   // greyed nodes are selectable too
  const n = byId.get(id);
  const rel = (ids, label) => ids.length ? `<div class="meta" style="margin-top:.6rem">${label}</div>
    <div class="rel">${ids.map(i => `<a href="#" data-go="${esc(i)}">${esc(i)}</a>`).join("")}</div>` : "";
  const kv = [["kind", n.kind], ["status", n.status], ["date", n.date], ["agent", n.agent],
              ["host", n.host], ["git", n.git_sha], ["metrics", n.metrics], ["dir", n.dir],
              ["notes", (n.notes || "").trim()],
              ["superseded by", (n.superseded_by || "").trim()]]
    .filter(([, v]) => v).map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("");
  side.className = "";
  side.innerHTML = `
    <h2>${esc(id.replace(/^\d{8}-/, ""))}</h2>
    <div class="meta">${esc(id)}</div>
    ${CAN_MARK ? `<div class="actions">${picking && picking.old === id
        ? `<button id="btn-nosucc">supersede with NO successor</button><button id="btn-cancel">cancel</button>`
        : n.status === "superseded"
          ? `<button id="btn-undo">undo supersede</button>`
          : `<button id="btn-sup">mark superseded…</button>`}<button id="btn-imp">${isImp(id) ? "☆ unmark important" : "★ mark important"}</button></div>` : ""}
    ${(n.reports || []).length ? `<div class="actions" style="flex-wrap:wrap">${n.reports.map(rp =>
        `<a href="${LIVE ? "report/" + esc(id) + "/" + esc(rp) : esc(n.dir) + "/out/" + esc(rp)}"
            target="_blank" style="font-size:.85rem">▤ ${esc(rp.replace(/\.html$/, ""))}</a>`).join("")}</div>` : ""}
    ${n.finding ? `<p style="font-size:.9rem">${esc(n.finding)}</p>` : ""}
    <div class="chips">${tagsOf(n).map(t => `<span class="chip">${esc(t)}</span>`).join("")}</div>
    <dl class="kv">${kv}</dl>
    ${rel(parents.get(id), "parents")}${rel(children.get(id), "children")}
    ${notesHtml(id, n)}
    <div class="md">${n.readme ? md(stripNotes(n.readme)) : "<p class='meta'>(no README.md)</p>"}</div>`;
  side.querySelectorAll("[data-go]").forEach(a =>
    a.addEventListener("click", ev => { ev.preventDefault(); select(a.dataset.go); }));
  const on = (bid, fn) => { const b = document.getElementById(bid); if (b) b.addEventListener("click", fn); };
  on("btn-sup",    () => { setPicking({ old: id }); select(id); });
  on("btn-cancel", () => { setPicking(null); select(id); });
  on("btn-nosucc", () => doSupersede(id, ""));
  on("btn-undo",   async () => {
    if (!LIVE) { queueIntent("unsupersede", id); afterMark(id); return; }
    if (await api("undo", { id })) applyLocal(id, "done", "");
  });
  wireNotes(id);
  on("btn-imp",    async () => {
    if (!LIVE) { queueIntent(isImp(id) ? "unimportant" : "important", id); afterMark(id); return; }
    const res = await api("important", { id, on: !isImp(id) });
    if (!res) return;
    byId.get(id).tags = res.tags;      // server returns the canonical string -- no client surgery
    refreshImp(); refreshNodeStyles(); refilter({ force: true }); select(id);
  });
  side.scrollTop = 0;
}

/* ---- notes UI: read anywhere, write where marks are possible ---------------------------- */
let noteEdit = null;      // { id, ts } while editing an existing note
function notesHtml(id, n) {
  const entries = notesSplit(n.readme || "").entries;
  const queued = new Set(PENDING.filter(p => p.op === "note" && p.id === id).map(p => p.replace || p.at));
  const rows = entries.map(e => `<div class="note${queued.has(e.ts) ? " queued" : ""}" data-ts="${esc(e.ts)}">
      <div class="stamp"><span>${esc(e.ts)}${e.author ? " · " + esc(e.author) : ""}${queued.has(e.ts) ? " · queued" : ""}</span>
        ${CAN_MARK ? `<a href="#" data-note-edit="${esc(e.ts)}">edit</a><a href="#" data-note-del="${esc(e.ts)}">delete</a>` : ""}</div>
      <div class="body">${esc(e.text)}</div></div>`).join("");
  if (!entries.length && !CAN_MARK) return "";
  const editing = noteEdit && noteEdit.id === id ? noteEdit.ts : "";
  const form = CAN_MARK ? `<div class="noteform"><textarea id="note-text" placeholder="add a note about this experiment…"></textarea>
      <div class="row"><button id="note-save">${editing ? "save edit" : "add note"}</button>
        ${editing ? `<button id="note-cancel">cancel</button><span class="meta">editing ${esc(editing)}</span>` : ""}</div></div>` : "";
  return `<div class="notes"><div class="meta">notes${entries.length ? ` (${entries.length})` : ""}</div>${rows}${form}</div>`;
}
async function submitNote(id, text, replace) {
  const author = "Renzo";
  if (!LIVE) { queueIntent("note", id, { at: replace || noteStamp(), replace, text, author }); noteEdit = null; afterMark(id); return; }
  const res = await api("note", { id, text, replace, author, at: noteStamp() });
  if (!res) return;
  byId.get(id).readme = res.readme;
  noteEdit = null; select(id);
}
function wireNotes(id) {
  const ta = document.getElementById("note-text");
  if (ta && noteEdit && noteEdit.id === id) {
    const e = notesSplit(byId.get(id).readme || "").entries.find(x => x.ts === noteEdit.ts);
    ta.value = e ? e.text : ""; ta.focus();
  }
  const on = (bid, fn) => { const b = document.getElementById(bid); if (b) b.addEventListener("click", fn); };
  on("note-save", () => {
    const text = (ta.value || "").trim();
    if (!text) { ta.focus(); return; }
    submitNote(id, text, noteEdit && noteEdit.id === id ? noteEdit.ts : "");
  });
  on("note-cancel", () => { noteEdit = null; select(id); });
  side.querySelectorAll("[data-note-edit]").forEach(a => a.addEventListener("click", ev => {
    ev.preventDefault(); noteEdit = { id, ts: a.dataset.noteEdit }; select(id);
  }));
  side.querySelectorAll("[data-note-del]").forEach(a => a.addEventListener("click", ev => {
    ev.preventDefault();
    if (!confirm("Delete this note?")) return;
    submitNote(id, "", a.dataset.noteDel);
  }));
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
let qTimer = null;
q.addEventListener("input", () => {
  clearTimeout(qTimer);
  qTimer = setTimeout(() => {
    const t = q.value.trim().toLowerCase();
    matched = !t ? null : new Set(NODES.filter(n =>
      [n.id, n.kind, n.status, n.tags, n.finding].join(" ").toLowerCase().includes(t)).map(n => n.id));
    refilter();
  }, 90);
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
  snapToTarget();                                   // grabbing the graph ends a running motion
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
  snapToTarget();
  const r = gdiv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  const f = Math.exp(-e.deltaY * 0.0015), k = Math.min(3, Math.max(0.15, view.k * f));
  view.x = mx - (mx - view.x) * (k / view.k); view.y = my - (my - view.y) * (k / view.k);
  view.k = k; apply();
}, { passive: false });
// Background click clears the selection — but NOT when it is the tail of a pan, or every drag
// would deselect whatever you were reading.
svg.addEventListener("click", () => {
  if (dragged) { dragged = false; return; }
  selected = null; clearHighlight(); setPicking(null);
  side.className = "empty"; side.innerHTML = "<div>Select an experiment to read its README.</div>";
});
addEventListener("resize", () => apply());
if (window.ResizeObserver) new ResizeObserver(() => apply()).observe(gdiv);

document.getElementById("legend").innerHTML =
  [...new Set(NODES.map(n => n.status).filter(Boolean))].sort()
    .map(s => `<span><i style="background:${statusColor(s)}"></i>${esc(s)}</span>`).join("");
const countText = () => {
  const n = FOCUS ? FOCUS.size : ALL_IDS.length, out = ALL_IDS.length - n, parts = [];
  parts.push(out ? `${n} of ${ALL_IDS.length} shown · ${out} greyed above` : `${n} experiments`);
  if (!showSup && SUP.size) parts.push(`${SUP.size} superseded`);
  if (impOnly) parts.push("important only");
  if (dateFrom || dateTo) parts.push(`${dateFrom || "…"} → ${dateTo || "…"}`);
  if (matched) parts.push(`matching “${q.value.trim()}”`);
  return parts.join(" · ");
};
function refreshSup() {
  document.getElementById("suplabel").style.display = SUP.size ? "" : "none";
  document.getElementById("supn").textContent = SUP.size;
}
function refreshImp() {
  const n = impCount();
  const lab = document.getElementById("implabel");
  lab.style.display = (n || CAN_MARK) ? "" : "none";   // show it wherever marking is possible
  document.getElementById("impn").textContent = n;
}
refreshSup();
if (SUP.size) {
  document.getElementById("showsup").addEventListener("change", ev => {
    showSup = ev.target.checked;
    refilter();
  });
}
refreshImp();
refreshIntents();
if (INTENTS) {
  document.getElementById("int-send").addEventListener("click", () => {
    if (!PENDING.length) return;
    const body = ["lab-exp intents v1", "project: " + (DATA.project || ""), ...intentLines()].join("\n");
    const title = `[lab-exp] ${DATA.project || "project"}: ${PENDING.length} change(s)`;
    PENDING.forEach(it => { it.sent = Date.now(); }); savePending();
    window.open(INTENTS + "?title=" + encodeURIComponent(title) + "&body=" + encodeURIComponent(body), "_blank");
  });
  document.getElementById("int-copy").addEventListener("click", async () => {
    const text = intentLines().map(l => "lab-exp " + l).join("\n");
    try { await navigator.clipboard.writeText(text); } catch (e) { window.prompt("copy these:", text); }
  });
  document.getElementById("int-clear").addEventListener("click", () => {
    PENDING.slice().reverse().forEach(revertIntent); PENDING = []; savePending();
    refreshSup(); refreshImp(); refreshNodeStyles(); refilter({ force: true });
    if (selected) select(selected);
  });
}
document.getElementById("imponly").addEventListener("change", ev => {
  impOnly = ev.target.checked;
  refilter();
});
function setDates(from, to) {
  dateFrom = from; dateTo = to;
  document.getElementById("datefrom").value = from;
  document.getElementById("dateto").value = to;
  refilter();
}
const isoDay = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
document.getElementById("datepre").addEventListener("change", ev => {
  const v = ev.target.value;
  document.getElementById("daterange").style.display = v === "custom" ? "" : "none";
  if (v === "custom") return;                        // bounds come from the two inputs
  if (!v) return setDates("", "");
  const from = new Date(); from.setDate(from.getDate() - Number(v) + 1);   // "last 7 days" includes today
  setDates(isoDay(from), "");
});
for (const id of ["datefrom", "dateto"])
  document.getElementById(id).addEventListener("change", () =>
    setDates(document.getElementById("datefrom").value, document.getElementById("dateto").value));
/* ---- deep links: ?days=7 | ?from=YYYY-MM-DD&to=YYYY-MM-DD | ?q=<text> | ?important=1 ----------
   So a note or a digest can link straight to "this week's experiments" or to one experiment. Applied
   to the filter STATE before the first paint, so the page opens already filtered instead of flashing
   the whole graph and animating away from it. Works behind the hub's lock page too: decryption
   rewrites the document, not the URL. */
(() => {
  const P = new URLSearchParams(location.search || location.hash.replace(/^#/, "?"));
  const sel = document.getElementById("datepre"), days = Number(P.get("days") || 0);
  if (days > 0) {
    const from = new Date(); from.setDate(from.getDate() - days + 1);
    dateFrom = isoDay(from); dateTo = "";
    if ([...sel.options].some(o => o.value === String(days))) sel.value = String(days);
    else { sel.value = "custom"; document.getElementById("daterange").style.display = ""; }
  } else if (P.get("from") || P.get("to")) {
    dateFrom = P.get("from") || ""; dateTo = P.get("to") || "";
    sel.value = "custom"; document.getElementById("daterange").style.display = "";
  }
  document.getElementById("datefrom").value = dateFrom;
  document.getElementById("dateto").value = dateTo;
  if (P.get("important") === "1") { impOnly = true; document.getElementById("imponly").checked = true; }
  if (P.get("q")) {
    q.value = P.get("q");
    const t = q.value.trim().toLowerCase();
    matched = new Set(NODES.filter(n => [n.id, n.kind, n.status, n.tags, n.finding].join(" ").toLowerCase().includes(t)).map(n => n.id));
  }
})();
buildDom();
refilter({ instant: true });
if (LIVE) {
  // A live page is a window onto the registry: coming back to the tab after a while shows what
  // landed meanwhile (the boxes keep recording). Fresh tabs (under a minute) are left alone.
  let hiddenAt = 0;
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) hiddenAt = Date.now();
    else if (hiddenAt && Date.now() - hiddenAt > 60000 && !PENDING.length && !picking) location.reload();
  });
  hint.textContent = "live · marks and notes are written immediately · reload for the latest";
}
if (location.pathname === "/") { const up = document.getElementById("hubup"); if (up) up.removeAttribute("href"); }   // one-project page: no hub above it
</script>
</body></html>
"""


if __name__ == "__main__":
    sys.exit(main())
