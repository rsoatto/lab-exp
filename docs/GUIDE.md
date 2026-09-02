---
name: lab-experiments
description: "How to structure and run experiments in any project managed with `lab-exp` (a `.lab-exp.toml` at the project root marks one). Use whenever you are about to train a model, run an ablation/sweep/analysis, write a plot, or add a method to a research codebase: check the registry and INDEX first, create experiments with `lab-exp new` (never ad-hoc scripts), launch with `lab-exp run` (stamps git SHA/command/hardware for reproducibility; submits via SLURM on the CW cell), record outcomes with `lab-exp done`, mark overridden results with `lab-exp supersede` (never delete; 'mark as superseded/obsolete/defunct/replaced' means this), flag key results with `lab-exp important <id>` (a plain tag the DAG can star and filter to), and visualize through the shared `<pkg>/viz/` layer (`lab-exp viz` / `serve`). Core rules: experiments are APPEND-ONLY; shared code lives in ONE package (promotion ratchet: a second LINEAGE needs it → promote, generalized; within a lineage, load the ancestor's helper); never rewrite a method or visualizer that already exists — grep INDEX.md first. Also covers adopting lab-exp in a new/existing project (`lab-exp init`, see migration.md). Claude Code / codex on any lab machine."
---

# lab-experiments — structured agentic experimentation

A lab-exp project separates **shared code** (one importable package: methods, models, training
loops, visualizers) from **experiments** (append-only directories, each one reproducible from its
own README). The registry TSV is the agent-facing truth; wandb is the human live-metrics layer;
`lab-report` pages compose visualizer renders. `lab-exp` is on PATH everywhere.

```
project/
  .lab-exp.toml            # per-project knobs (site, package, scratch, launcher, wandb) — edit, never guess
  <pkg>/                   # THE shared package. All reusable code lives here, nowhere else.
    INDEX.md               #   auto-generated map of methods + visualizers — READ THIS FIRST
    viz/                   #   visualizers: declare REQUIRES/MATCH/KIND, implement render()/serve()
  experiments/
    _registry.tsv          # id · kind · status · tags · git SHA · metrics · finding · wandb — the truth
    _templates/<kind>/     # per-kind scaffolds used by `lab-exp new` (optional; built-ins otherwise)
    20260720-slug/         # ONE experiment: README.md (hypothesis/method/how-to-run) + run.py + out/
```

## The four rules

1. **Registry before running.** `lab-exp list` (and the lineage in `based_on`) — has this
   experiment, or its answer, already been run? Don't repeat work; fork it with `--based-on`.
2. **INDEX + lineage before writing.** Before writing any non-trivial helper: (a) grep
   `<pkg>/INDEX.md` (everything already shared), then (b) grep your **ancestor experiments** —
   `lab-exp lineage <id>` prints the transitive `based_on` ancestry + dirs (cheap: your fork, not
   all experiments — that is where reuse concentrates). If an ancestor already has the helper,
   LOAD it from there (`load_ancestor`, below) — do NOT copy it, and do NOT rewrite the ancestor
   (its local copy is part of its frozen, reproducible record; editing it breaks its recorded SHA).
   It moves into `<pkg>/` when a SECOND lineage needs it.

   **The unit of promotion is a FUNCTION or CLASS, never a file.** Copying run.py (or any script)
   into `<pkg>/` satisfies the letter of this rule while producing a junk drawer: main guards,
   argparse, and top-level execution do not belong in the package — that wiring stays in the
   experiment. Promote by extracting the reusable functions into the module that OWNS the topic
   (extend an existing module before creating one; a new module needs a docstring naming its one
   topic), and leave the experiment's script as a thin caller. `lab-exp index` and `doctor` flag
   script-shaped modules (main guard / argparse), modules nothing imports, and >600-line files —
   treat those warnings as YOUR refactoring queue, not noise, and fix the ones your promotion
   introduced before finishing the task.

   **A second use means a second LINEAGE.** A retry, a bug-fix rerun, or a `--based-on`
   descendant of the same question is NOT a second use — it is the same question again. Promoting
   on that basis is how packages fill with single-question code (an audit found a third of one
   package promoted exactly this way). Reuse has two directions: **within a lineage, import your
   ANCESTOR** — keep helpers in `<exp>/lib.py` (main-free) and load them from a descendant with
   the template's `load_ancestor("<based_on id>")`; ancestors are frozen, so this couples you to
   something immutable. **Across lineages, promote** — and promotion means generalizing (parameters,
   not experiment ids or paths in code), never relocating. Never import a sibling or unrelated
   experiment: `lab-exp run` refuses references to non-ancestor experiment ids, and `index`/`doctor`
   flag package modules consumed by only one lineage or reaching experiment ids in code.

   Experiments form a **DAG**: `--based-on a,b` gives multiple parents. Query it in code (not by
   reading files): `lab-exp graph <id> --up|--down [--kind K] [--files] [--json]` returns
   ancestors/descendants (kind-filterable, with files); `lab-exp graph` dumps the whole DAG as
   JSON (`--dot` for graphviz) for arbitrary graph searches. For a HUMAN, `lab-exp dag` renders the
   whole DAG as one self-contained interactive HTML page — click a node to read its README, with
   ancestors/descendants highlighted — which is what to produce when the user asks to *see* the
   lineage. Pipe it straight to a shareable URL: `lab-exp dag --out - | lab-report publish
   /dev/stdin --title "<project> — experiment DAG"`. `lab-exp dag --serve` serves it LIVE on
   localhost instead: reloads re-read the registry, and the page gains mark-superseded / undo
   buttons that write it (same locked code path as `lab-exp supersede`) — offer this when the user
   wants to review and mark experiments interactively.
3. **Experiments are append-only.** When a later experiment overrides an earlier one's result,
   `lab-exp supersede <old> --by <new>` — a status change (record, dir, and finding stay; the DAG
   hides superseded nodes behind a toggle). Never delete. `--undo` restores.
   **Append-only, continued.** Never edit a finished experiment's run.py to "try something
   else" — `lab-exp new --based-on <id>` and change ONE thing. The README must state hypothesis,
   method, and how-to-run well enough that a stranger (or you, in 6 months) can rerun it.
4. **Run through the wrapper; record the outcome.** `lab-exp run <id>` stamps
   `out/run-meta.json` (git SHA — commit first, dirty trees are flagged — exact command, host,
   GPUs) and sets all wandb env vars (your code just calls `wandb.init()` bare). When it finishes:
   `lab-exp done <id> --finding "..." --metrics k=v,...` — an experiment without a recorded
   finding is unfinished. If the experiment warrants human-facing reports (figures, writeups),
   write them as SELF-CONTAINED HTML under `out/` — `out/report.html` for the primary one,
   `out/viz/<name>.html` for additional views. The DAG page surfaces every .html at out/ top level
   or one subdir deep (▤ marker on the node, links in the panel, primary first). (A published
   lab-report page can simply also be saved there.) Reproduce an old experiment at its recorded SHA via `git worktree`.

## Workflow

```bash
lab-exp list                                   # what exists? (filters: --kind --tag --status)
lab-exp new my-idea --kind training --tags arch:foo --based-on 20260701-baseline
# ... write README Hypothesis+Method, implement run.py (import from <pkg>/) ...
lab-exp run 20260720-my-idea                   # local box: runs+logs; CW cell: submits via lab-slurm
lab-exp done 20260720-my-idea --finding "X improves Y by 12%" --metrics acc=0.91
lab-exp supersede 20260701-old --by 20260720-my-idea --why "..."   # overridden, NOT deleted
lab-exp doctor                                 # drift check — run when things look off
```
**`run` REFUSES on a dirty git tree.** The stamped SHA would not reproduce the run, and the
experiment record is append-only — there is no fixing it afterwards. Commit first. If you genuinely
need to run uncommitted code, `--allow-dirty` saves `git diff HEAD` to `out/dirty.patch`, so
SHA + patch still reconstructs the tree; run-meta records `git_dirty`, the patch path, and any
**untracked** files, which are in neither the SHA nor the patch. Declare legitimately-untracked
mess in `[run] dirty_ok = ["scratch/", "*.log"]` so those paths never count; a repo mid-migration,
where the mess is larger than `dirty_ok` can enumerate, can set `[run] require_clean = false` to
opt out wholesale.

**`run` also REFUSES if run.py imports untracked code.** It walks run.py's static import closure
and requires every in-repo file in it to be git-tracked — this catches the case `git status` cannot:
a **.gitignore'd** module reads as a clean tree while the stamped SHA silently omits code the run
executes. Fix by `git add`-ing the listed files (use `-f` if ignored). `dirty_ok` deliberately does
NOT excuse imported code; `--allow-dirty` archives the files to `out/untracked-code/` and lists
them in run-meta as `untracked_imports`. Limit: the walk is static, so dynamically imported modules
(importlib on a computed name) are not seen.

**Declaring input DATA:** data doesn't belong in git, so the SHA never covers it — declare it
instead. `lab-exp adopt <id> <path>` records source path + content hash (files: sha256; dirs: a
size manifest) in `out/adopted.json` and symlinks it into `out/`; `doctor` then verifies the source
still exists and still matches, so a run's inputs can't drift silently. Use it for every external
input a run depends on (datasets, frozen checkpoints, another project's outputs); `[paths] data`
in `.lab-exp.toml` is informational only and verifies nothing.

`run` on the CW cell prints a SLURM job id — **arm your watchdog** (per your standing directive)
and check it; a submitted job is not a finished job. `--gpus/--time/--partition` override the
`[run.slurm]` defaults; extra run.py args go after `--`.

Kinds and structured tag keys are declared in `.lab-exp.toml`. `kind` = lifecycle type (training,
analysis, ...) → picks the template; `tags` = what it is (`arch:x`, `objective:y`) → filtering,
wandb grouping, and visualizer MATCH.

## Visualizers — never rewrite a plot

All viz code lives in `<pkg>/viz/`, one module each, declaring what it applies to:

```python
"""One-line description (harvested into INDEX.md)."""
REQUIRES = ["metrics.json"]        # artifacts that must exist in out/ (globs ok). A bare name
                                   #   matches its basename at ANY depth (out/plots/curve.png);
                                   #   a pattern with '/' matches the out/-relative path
                                   #   ("plots/*.png"). run-meta.json/run.log/out/viz are excluded.
MATCH = {"arch": "foo"}            # structured-tag constraints ({} = any); values may be lists
KIND = "training"                  # or None = any kind

def render(exp_dir, out_dir) -> list:   # static: write .vl.json (Vega-Lite, preferred: drops
    ...                                 # straight into lab-report pages) or .png; return paths
def serve(exp_dirs, port):              # interactive: host an app on `port` (blocking); takes a
    ...                                 # LIST of experiments — comparison is half the point
```

```bash
lab-exp viz <id>                   # which visualizers apply to this experiment?
lab-exp viz <id> curve             # render -> experiments/<id>/out/viz/  (cache, not record —
                                   #   regenerable, never goes in the registry)
lab-exp serve act_browser <id> <id2>   # host interactive app in tmux; prints the ssh -L tunnel
lab-exp serve --list / --stop <port>   # manage; these are ephemeral microscopes, not daemons
```
For a **report**: filter the registry, call the applicable `render()`s, compose the outputs +
prose with the lab-report skill. Report = durable + phone-reachable; serve = ephemeral + live.
marimo is the house convention for serve() apps (a single .py that is both notebook and app).

## Durable shared computed artifacts: the cache root

`[paths] cache` in `.lab-exp.toml` is the home for the FOURTH data category: computed (not raw),
read by many experiments, durable + expensive to regenerate (so not scratch) — feature stores,
frozen judge caches, embeddings. `lab-exp run` exports it as **`$LAB_EXP_CACHE`** — code reads
that env var (one relocation knob, never a hardcoded path). Convention: one subdir per cache
(`$LAB_EXP_CACHE/<name>/`), each carrying a `PROVENANCE.md` naming the experiment that generated
it — `doctor` nags on missing/unknown provenance. Raw inputs stay in `data`, ephemera in
`scratch`, per-run results in the experiment's own `out/`.

## Adopting external artifacts (backfills done right)

```bash
lab-exp adopt <id> /path/to/results --as legacy-results   # symlink + hash-recorded reference
```
Records source path + content hash in `out/adopted.json` (files: sha256; dirs: fast size-manifest
hash) and drops a convenience symlink. The RECORD is the contract: `doctor` flags a source that
vanished or drifted from its hash, so a backfilled experiment is self-describing instead of
silently coupled to a mutable external dir. Artifact matching follows directory symlinks, so a
whole adopted tree is dispatchable. Convert to real copies later with `materialize`.

## Renames while the taxonomy is young

```bash
lab-exp rename kind training pretraining     # registry + READMEs + config, one command
lab-exp rename tag arch:hnet arch:h-net      # full token, or a bare key to rename the key
```
(Visualizer MATCH/KIND declarations referencing the old name must be edited by hand — rerun
`lab-exp index` after.)

## Making out/ self-contained

```bash
lab-exp materialize <id>                        # replace every symlink in out/ with a real copy
lab-exp materialize <id> --import PATH [--as SUB]  # copy an external file/dir into out/<SUB>
```
Backfills (see migration.md) symlink out/ at original artifacts — fine locally, but they break when
the experiment is archived, moved, or the source is deleted. `materialize` copies the real bytes in
so viz/reports/doctor keep working from a portable directory. `--import` pulls an external result
(a checkpoint dir, a plot tree) into out/ under a chosen subpath; nested layouts are fine — viz
REQUIRES matches them.

## wandb

Configured entirely by `lab-exp run` env vars: run name/id = experiment id, group = lineage root
(forks group together), tags = experiment tags + kind. Code calls `wandb.init()` with no args.
No auth on the box → automatic `WANDB_MODE=offline` (the user drops a key in
`~/.config/lab/wandb.env` to go online — never print or sync that file).

## Adopting lab-exp in a project

`lab-exp init` at the project root — additive, works on existing codebases (points `package` at
the existing importable package). Full steps for migrating an existing messy project:
[migration.md](migration.md) in this skill directory.

**Adoption is the user's call, not yours.** A project with no `.lab-exp.toml` is not lab-exp-managed
— it may be mid-migration, or deliberately unmanaged. Never run `lab-exp init` on it just to satisfy
a workflow: say what you found and ask. The same applies in reverse — if lab-exp genuinely doesn't
fit a case (a real limitation, not inconvenience), name the limitation and ask rather than quietly
working around it. Both are cheap to ask about and expensive to get wrong: an unwanted `init` writes
config into someone's repo, and a silent workaround produces exactly the vanishing, unreproducible
result the tool exists to prevent.
