# Reports on the hub — style guide

A report is **one self-contained HTML file** in the experiment's `out/` directory: `out/report.html`
is the primary; further views go to `out/viz/<name>.html`. The hub copies exactly those files and
links them from the experiment's node in the DAG. Nothing else in `out/` travels with them, and the
page is read on a phone as often as on a laptop.

Start from **`lab-exp report <id>`**: it writes a skeleton with the house CSS and the provenance
filled in (id, title, finding, metrics, git SHA, date, command). **`lab-exp doctor`** checks every
report against the mechanical rules in section 6.

## 1. Who it is for

The reader was not there. Usually that is the user weeks later, on a phone, between meetings;
sometimes a collaborator who has never seen the codebase. They want the answer, the evidence for
it, and enough method to trust it, in that order. They do not want a log of what you did.

Rule 5 of the guide applies in full: plain sentences, full words, one idea per sentence; a
project-specific term is defined the first time it appears or avoided; headings are questions or
conclusions, never variable names. The test: could that collaborator read the page top to bottom
and say what was asked, what was done, and what was found, without opening the code?

## 2. Shape of the page

1. **Title**: the question, or the conclusion. "Does removing the size covariate change the top-20
   genes?" or "Ridge is the ceiling for DepMap-conditioned predictors". Never an experiment id or a
   filename.
2. **Answer first**, two to four sentences: the finding as recorded with `lab-exp done`, with the
   number that supports it, its comparison, and n. A reader who stops here has the result.
3. **Key numbers** as two to five KPI cards: value, label, comparison ("0.91 AUROC · baseline 0.87 ·
   5 seeds"). Only the numbers the conclusion hinges on, not every metric.
4. **Evidence**: one figure or table per claim, each with a caption, in the order the argument
   needs. Every claim in the answer should be checkable against one of them.
5. **Method**, one short paragraph: what was run, the ONE thing that changed relative to the parent
   experiment, the settings the result hinges on. Name package functions in code font. The full
   configuration lives in run.py and run-meta.json, not here.
6. **Caveats**: what would change the conclusion, what was not controlled, known leaks or confounds.
   This is where doubt goes; the answer section states, it does not hedge.
7. **Provenance footer**: experiment id, git SHA, date, command, host. The skeleton fills it from
   the README front-matter and `out/run-meta.json`.

Length: a report that fits two phone screens beats one that needs ten. Extra views go to
`out/viz/<name>.html`, each self-contained with its own title and caption, rather than into the
primary page.

## 3. Figures

- One message per figure, stated in the caption: what to look at and what it shows. "Each dot is a
  held-out set; points above the line have a training twin. 23 of 116 lie above it."
- Axes labeled with units; a log scale says so; compared panels share axes; the baseline is drawn,
  not implied.
- At most six series. A colorblind-safe palette (Okabe–Ito, or Vega's `tableau10`), and the same
  color for the same thing across figures.
- Uncertainty and n are visible: error bars, intervals, or "5 seeds" in the caption. Never a bare
  mean.
- Vega-Lite for anything that benefits from tooltips or hover; inline SVG or a data-URI PNG for
  anything static. Width at most 700 px, and legible at 375 px (a phone): short tick labels,
  legends below rather than beside.
- When the reader will look up exact values, use a table instead.

## 4. Tables

- At most eight columns, sorted by the column the reader cares about, the key comparison in the
  first two data columns.
- Sensible precision (three significant figures unless the difference needs more), units in the
  header not the cells, thousands separators.
- Long tables scroll inside the page (the skeleton's `.table-wrap`); they never widen it.

## 5. Numbers and words

- Every number carries a comparison or a denominator: "0.445 (was 0.435 at 60k steps)", "23 of 116".
- Percent versus percentage points: say which.
- No metric names pasted from code: `val_gene_pearson` is "validation Pearson per gene".
- No filler ("interestingly", "it seems that", "as expected"). If it is expected, say what predicted it.

## 6. Technical rules (`lab-exp doctor` checks these)

- **One file.** Everything the page needs is inside it: CSS inline, images as data URIs or inline
  SVG, chart data inside the Vega spec. The hub copies only the `.html`, so `<img src="fig.png">`
  is a broken image on the phone.
- **Libraries from a CDN are fine** (`cdn.jsdelivr.net` for vega, vega-lite, vega-embed;
  `cdn.plot.ly` for Plotly): the page is decrypted into a real document, so scripts run. Pin major
  versions as the skeleton does.
- **Under 25 MB, and preferably under 2 MB.** Above the cap the hub shows a pointer instead of the
  report. Downsample the data behind a chart; a multi-megabyte base64 PNG is a smell.
- **No loading-time fetches**: no `fetch()`, no `<link>` or `<iframe>` to local files, no forms.
- **Responsive**: `max-width` on the body, tables in a horizontally scrolling wrapper, images
  `max-width:100%`, light and dark via `prefers-color-scheme`. The skeleton does all of this.
- `<title>` is the page title; a viewport meta tag is present.
- No skeleton placeholders left behind (`data-todo` markers).

## 7. The skeleton

`lab-exp report <id>` writes `out/report.html` with, in order: title · answer · KPI cards · one
evidence figure with a caption (a Vega-Lite spec to replace) · method · caveats · provenance. Each
placeholder is marked `data-todo`; replace them all. `--out viz/<name>.html` writes a secondary
view with the same CSS. It refuses to overwrite an existing report unless `--force`.
