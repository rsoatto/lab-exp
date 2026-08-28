# lab-exp — structured, reproducible ML experimentation for agents and humans

A single-file, stdlib-only CLI that turns a research repo into an append-only,
reproducible experiment ledger — designed so LLM agents and humans share one
source of truth.

- **Experiments are append-only dirs** (`experiments/<date>-<slug>/`): README
  (hypothesis/method), `run.py`, `out/`. Fork with `--based-on`; never edit a
  finished one.
- **`lab-exp run` stamps reproducibility**: git SHA (refuses a dirty tree, and
  refuses if run.py imports untracked code — including .gitignore'd modules git
  status can't see), exact command, host, GPUs. `--allow-dirty` records the
  diff + untracked imports so SHA+patch still reconstructs the tree.
- **The registry TSV is the truth**: id · kind · status · tags · SHA · metrics
  · finding. Concurrent-safe (flock). `done` records the finding; `supersede`
  marks overridden results without deleting; `important` stars key ones.
- **`lab-exp dag`** renders the whole experiment DAG as one self-contained
  interactive HTML page (search, superseded hiding, per-experiment reports
  from `out/*.html`). `--serve` makes it live: click to supersede/star.
- **Shared code lives in ONE package**; `lab-exp index` generates an INDEX of
  its public functions and flags script-shaped modules, orphans, and giant
  files so the package stays a library, not a junk drawer.

## Install
Python ≥ 3.11, Linux/macOS. Copy `bin/lab-exp` and `bin/_exp-dag.py` onto your
PATH (they must sit in the same directory).

## Start
    cd your-research-repo
    lab-exp init                 # writes .lab-exp.toml — EDIT IT (scratch path, kinds)
    lab-exp new my-idea --kind analysis
    lab-exp run <id>
    lab-exp done <id> --finding "..."
    lab-exp dag --serve

`docs/GUIDE.md` is the full manual (written as an LLM-agent skill — drop it
into your agent's context if you use one). `lab-exp init` defaults (scratch
location, site names) reflect the author's cluster; edit the generated
`.lab-exp.toml` per project. The optional SLURM launcher shells out to a
`lab-slurm` wrapper you'd replace with your own; `launcher = "local"` needs
nothing.
