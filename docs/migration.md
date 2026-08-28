# Migrating an existing project to lab-exp

Adoption is **additive** — nothing is moved or rewritten on day one. The framework wraps what
exists; cleanup happens incrementally through the promotion ratchet, not as a big-bang refactor.

## Step 0 — decide the boundaries (5 minutes, before touching anything)

- **The package**: which directory is (or will become) the ONE shared importable package? If the
  project already has one (`import mypkg` works), use it. If code is loose scripts, you still
  init with a fresh `lib/` and promote into it lazily — do NOT pre-emptively move everything.
- **The site**: exxact / cw / mac. Cross-site note: the exxact and CW filesystems are not
  mutually visible, so a research line spanning both is **two project instances** with their own
  registries; cross-site synthesis lives in the wiki, not the registry.
- **Kinds + tag keys**: list the 2–4 lifecycle kinds this project actually has (training,
  analysis, data-prep, ...) and the structured tag keys worth filtering on (arch, objective, ...).
  Start minimal; adding later is cheap, renaming later is not.

## Step 1 — init

```bash
cd <project-root>          # must be the git root (stamping records git SHA from here)
lab-exp init --package <existing-pkg>     # omit --package to auto-detect / create lib/
$EDITOR .lab-exp.toml      # set: scratch, env.activate, kinds, tag_keys, [run] launcher,
                           #      [run.slurm] defaults (CW), [wandb] enabled+entity
lab-exp index              # generate the INDEX from the existing package
git add -A && git commit   # the framework files are part of the project history
```

## Step 2 — backfill ONLY what earns it

Do **not** retro-create an experiment directory for every historical run. Backfill a run only if
it is (a) a result you still cite, or (b) a baseline future experiments will fork from:

```bash
lab-exp new legacy-baseline --kind training --tags arch:...
# README: Hypothesis = what it established; Method = pointer to the original command/script;
#         How to run = the ACTUAL original invocation, verbatim (even if it was a raw sbatch line);
#         add `backfilled: true` to the frontmatter so doctor knows out/ is legitimately unstamped
lab-exp done 20260720-legacy-baseline --status done --finding "<the known result>" --metrics ...
```
This gives history a citable, forkable record without pretending it was stamped. If the original
artifacts still exist (checkpoints, metrics), copy or symlink them into the experiment's `out/`
so visualizers can reach them; note in the README that the run predates stamping.

## Step 3 — hard cutover for NEW work

From init onward, every new run goes through `lab-exp new` + `lab-exp run`. No new loose scripts
in `scripts/`, no ad-hoc sbatch lines: if it produces a result, it is an experiment; if it's
reusable logic, it belongs in the package. `scripts/` is frozen legacy — never add to it, and
when you need something from it a second time, promote it into the package (ratchet) instead of
calling it in place.

## Step 4 — visualizers

Move/wrap existing plotting code into `<pkg>/viz/` modules with REQUIRES/MATCH/KIND declarations
as you next need each plot (not all at once). Delete the per-experiment copies it replaces.

## Step 5 — verify

```bash
lab-exp doctor        # should be clean (or explain exactly what legacy state remains)
lab-exp list          # registry reflects reality
```

## Ongoing hygiene (what `doctor` will nag about)

- out/ artifacts with no `run-meta.json` → someone bypassed `lab-exp run`
- status `ran` → finished run with no recorded finding
- status `running` >48h → dead job or forgotten `done`
- undeclared kinds/tag keys → typo or missing declaration in `.lab-exp.toml`
- stale INDEX.md → run `lab-exp index`

The messier the project, the MORE valuable steps 2–3 discipline is — resist the urge to clean
everything first. Adopt, cut over, let the ratchet drain the legacy.
