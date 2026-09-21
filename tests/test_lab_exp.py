"""lab-exp behaviour tests. Run:  python3 -m unittest -v tests/test_lab_exp.py   (pytest also works)

Each test builds a throwaway project (with its own git repo and HOME) and drives the real CLI
via subprocess, so what is tested is exactly what an agent runs."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LAB_EXP = Path(__file__).resolve().parents[1] / "bin" / "lab-exp"


def read_tsv(path):
    lines = path.read_text().splitlines()
    cols = lines[0].split("\t")
    return {r.split("\t")[0]: dict(zip(cols, (r.split("\t") + [""] * len(cols))[:len(cols)]))
            for r in lines[1:] if r.strip()}


def front(readme):
    out = {}
    lines = readme.read_text().splitlines()
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def toks(csv):
    return {t.strip() for t in re.split(r"[,\s]+", csv or "") if t.strip() and t.strip() != "none"}


class Project:
    """A temp lab-exp project: git repo, isolated HOME, helpers to run the CLI."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="labexp-test-"))
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.root = self.tmp / "proj"
        self.root.mkdir()
        self.env = {**os.environ, "HOME": str(self.home), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "WANDB_MODE": "offline"}
        self.git("init", "-q")
        self.git("commit", "-q", "--allow-empty", "-m", "root")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, env=self.env, capture_output=True, text=True, check=True)

    def commit_all(self, msg="wip"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg, "--allow-empty")

    def run(self, *args, check=True):
        r = subprocess.run([sys.executable, str(LAB_EXP), *args], cwd=self.root, env=self.env,
                           capture_output=True, text=True)
        if check and r.returncode != 0:
            raise AssertionError(f"lab-exp {' '.join(args)} failed rc={r.returncode}\n{r.stdout}\n{r.stderr}")
        return r

    def init(self):
        self.run("init", "--site", "mac")

    def new(self, slug, kind="training", **kw):
        args = ["new", slug, "--kind", kind]
        for k, v in kw.items():
            args += [f"--{k.replace('_', '-')}", v]
        out = self.run(*args).stdout
        return re.search(r"created experiments/(\S+)/", out)[1]

    @property
    def tsv(self):
        return self.root / "experiments" / "_registry.tsv"

    def readme(self, eid):
        return self.root / "experiments" / eid / "README.md"

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class LabExpTests(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.cleanup)

    # ---- 1. registry derived from READMEs ------------------------------------------------------

    def test_init_gitignores_the_cache(self):
        self.p.init()
        gi = (self.p.root / ".gitignore").read_text().splitlines()
        self.assertIn("experiments/_registry.tsv", gi)
        self.assertIn("experiments/_registry.tsv.lock", gi)

    def test_writes_mirror_into_frontmatter(self):
        self.p.init()
        a = self.p.new("base")
        b = self.p.new("child", based_on=a, tags="arch:x")
        self.assertEqual(front(self.p.readme(a))["status"], "planned")
        self.p.run("done", b, "--finding", "child beats base: 0.9 vs 0.8", "--metrics", "acc=0.9,n=3")
        fm = front(self.p.readme(b))
        self.assertEqual(fm["status"], "done")
        self.assertEqual(fm["finding"], "child beats base: 0.9 vs 0.8")
        self.assertEqual(fm["metrics"], "acc=0.9,n=3")
        self.p.run("important", b)
        self.assertIn("important", toks(front(self.p.readme(b))["tags"]))
        self.p.run("important", b, "--undo")
        self.assertNotIn("important", toks(front(self.p.readme(b))["tags"]))
        self.p.run("supersede", a, "--by", b, "--why", "replaced")
        self.assertEqual(front(self.p.readme(a))["superseded_by"], b)
        self.p.run("supersede", a, "--undo")
        self.assertNotIn("superseded_by", front(self.p.readme(a)))
        self.assertEqual(front(self.p.readme(a))["status"], "done")
        # the body (hypothesis/method text) is untouched by all of the above
        self.assertIn("## Hypothesis", self.p.readme(a).read_text())

    def test_roundtrip_registry_to_readmes_to_rebuild(self):
        """A legacy project whose facts live only in the TSV: sync pushes them into READMEs,
        rebuild regenerates the TSV from READMEs alone, and every row comes back identical."""
        self.p.init()
        a = self.p.new("base", tags="arch:lin, data:d1")
        b = self.p.new("child", based_on=a, tags="arch:mlp")
        self.p.run("done", a, "--finding", "baseline works", "--metrics", "acc=0.8")
        self.p.run("done", b, "--finding", "mlp: 0.9 vs 0.8", "--metrics", "acc=0.9")
        self.p.run("important", b)
        self.p.run("supersede", a, "--by", b)
        before = read_tsv(self.p.tsv)
        # Emulate READMEs written before mirroring existed: strip every mirrored key.
        for eid in (a, b):
            rm = self.p.readme(eid)
            lines = rm.read_text().splitlines(keepends=True)
            end = lines.index("---\n", 1)
            keep = [l for l in lines[1:end] if l.split(":", 1)[0] not in
                    ("status", "date", "agent", "host", "git_sha", "metrics", "finding", "wandb", "superseded_by")]
            keep = [re.sub(r"^tags:.*", "tags: " + ", ".join(t for t in toks(front(rm)["tags"]) if t != "important"), l)
                    for l in keep]
            rm.write_text("".join(lines[:1] + keep + lines[end:]))
        dry = self.p.run("registry", "--rebuild", "--dry-run").stdout
        self.assertIn("would write", dry)
        self.assertTrue(read_tsv(self.p.tsv) == before, "dry-run must not touch the cache")
        self.p.run("registry", "--rebuild")
        after = read_tsv(self.p.tsv)
        self.assertEqual(set(after), set(before))
        for eid in before:
            for col in before[eid]:
                if col == "tags":
                    self.assertEqual(toks(before[eid][col]), toks(after[eid][col]), (eid, col))
                else:
                    self.assertEqual(before[eid][col], after[eid][col], (eid, col))
        # every reader agrees after a rebuild
        self.assertIn("mlp: 0.9 vs 0.8", self.p.run("list").stdout)

    def test_no_tsv_still_lists_and_graphs(self):
        self.p.init()
        a = self.p.new("base")
        b = self.p.new("child", based_on=a)
        self.p.tsv.unlink()
        out = self.p.run("list").stdout
        self.assertIn(a, out)
        self.assertIn(b, out)
        self.assertIn(a, self.p.run("lineage", b).stdout)

    # ---- 3. doctor tolerates hand-made experiments --------------------------------------------

    def _foreign(self, eid, with_result=True, metrics=None):
        d = self.p.root / "experiments" / eid
        (d / "out").mkdir(parents=True)
        (d / "README.md").write_text(
            f"---\nid: {eid}\ntitle: hand made\nkind: training\ntags: arch:lin, data:d1\n"
            f"based_on: none\nproduces: comparison.json\ncommand: bash submit.sh\n---\n\n# hand made\n\n"
            + ("## Result\nIt worked: 0.7 vs 0.6.\n" if with_result else "## Result\n<!-- pending -->\n"))
        (d / "submit.sh").write_text("#!/bin/bash\necho hi\n")
        (d / "out" / "comparison.json").write_text("{}")
        if metrics is not None:
            (d / "out" / "metrics.json").write_text(json.dumps(metrics))
        return d

    def test_foreign_experiment_is_visible_and_doctor_stays_clean(self):
        self.p.init()
        self.p.new("mine")
        self._foreign("20260908-hand-made", metrics={"acc": 0.7, "note": "str", "flag": True})
        self._foreign("20260909-hand-pending", with_result=False)
        out = self.p.run("list").stdout
        self.assertRegex(out, r"20260908-hand-made\s+training\s+done\s+.*acc=0.7")
        self.assertRegex(out, r"20260909-hand-pending\s+training\s+unknown")
        r = self.p.run("doctor", check=False)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("2 experiment(s) not in the registry cache", r.stdout)
        self.assertNotIn("WARN", r.stdout)
        # a rebuild writes them into the cache; doctor then has nothing to note
        self.p.run("registry", "--rebuild")
        self.assertIn("20260908-hand-made", read_tsv(self.p.tsv))
        self.assertNotIn("not in the registry cache", self.p.run("doctor", check=False).stdout)

    def test_sync_never_touches_a_hand_made_readme(self):
        """A rebuild caches DERIVED facts for a collaborator's experiment; the next sync must not
        write them back into the README as if lab-exp had recorded them."""
        self.p.init()
        self.p.new("mine")
        d = self._foreign("20260908-hand-made", metrics={"acc": 0.7})
        before = (d / "README.md").read_bytes()
        self.p.run("registry", "--rebuild")
        self.p.run("registry", "--rebuild")          # second pass syncs from the now-populated cache
        self.p.run("registry", "--sync")
        self.assertEqual((d / "README.md").read_bytes(), before)
        # while a fact lab-exp DID record still reaches a README that lacks it
        eid = self.p.new("recorded")
        self.p.run("done", eid, "--status", "failed", "--finding", "broke")
        rm = self.p.readme(eid)
        rm.write_text("\n".join(l for l in rm.read_text().splitlines() if not l.startswith(("status:", "finding:"))) + "\n")
        self.p.run("registry", "--sync")
        fm = front(rm)
        self.assertEqual(fm["status"], "failed")
        self.assertEqual(fm["finding"], "broke")

    def test_missing_frontmatter_is_still_a_warning(self):
        self.p.init()
        d = self.p.root / "experiments" / "20260101-bare"
        d.mkdir()
        (d / "README.md").write_text("# no front-matter\n")
        r = self.p.run("doctor", check=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no frontmatter", r.stdout)

    # ---- 2. command: override ------------------------------------------------------------------

    def test_command_override_in_run(self):
        self.p.init()
        eid = self.p.new("mine")
        self.p.commit_all()
        default = self.p.run("run", eid, "--dry-run").stdout
        self.assertIn(f"python experiments/{eid}/run.py", default)
        rm = self.p.readme(eid)
        rm.write_text(rm.read_text().replace("\n---\n\n", "\ncommand: bash submit.sh\n---\n\n", 1))
        (self.p.root / "experiments" / eid / "submit.sh").write_text("#!/bin/bash\necho hi\n")
        self.p.commit_all()
        out = self.p.run("run", eid, "--dry-run", "--", "--epochs", "3").stdout
        expdir = (self.p.root / "experiments" / eid).resolve()   # macOS: /var -> /private/var
        self.assertIn(f"cd '{expdir}' && set -o pipefail; bash submit.sh '--epochs' '3'", out)
        self.assertNotIn("run.py", out.split("set -o pipefail")[1])
        self.assertIn("_stamp-hw", out)
        self.assertIn("tee -a", out)
        meta = json.loads((expdir / "out" / "run-meta.json").read_text())
        self.assertEqual(meta["command"], "bash submit.sh --epochs 3")
        self.assertEqual(meta["command_source"], "README front-matter")
        # the dirty-tree refusal still applies to a custom command
        (self.p.root / "junk.py").write_text("x = 1\n")
        r = self.p.run("run", eid, "--dry-run", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("DIRTY", r.stderr)


    # ---- promotion heuristic vs single-lineage projects ------------------------------------

    def test_single_lineage_project_gets_no_promotion_warning(self):
        self.p.init()
        (self.p.root / "lib" / "helper.py").write_text("def f():\n    return 1\n")
        a = self.p.new("base")
        b = self.p.new("child", based_on=a)
        for eid in (a, b):
            (self.p.root / "experiments" / eid / "run.py").write_text("from lib.helper import f\nf()\n")
        self.p.run("index")
        out = self.p.run("doctor", check=False).stdout
        self.assertNotIn("ONE lineage", out)
        c = self.p.new("other-root")                       # a second, unrelated lineage
        (self.p.root / "experiments" / c / "run.py").write_text("import os\n")
        (self.p.root / "experiments" / a / "run.py").write_text("from lib.helper import f\n")
        out = self.p.run("doctor", check=False).stdout
        self.assertIn("ONE lineage", out)                  # now a second lineage exists but does not use it


    # ---- hub: one static site for every project ----------------------------------------------

    def test_dag_page_reads_deep_link_params(self):
        # ?days=7 / ?q=<id> links from the notes and the weekly digest rely on this block
        self.p.init()
        self.p.new("base")
        site = self.p.tmp / "site_dl"
        self.p.run("hub", "--out", str(site))
        txt = (site / "proj" / "index.html").read_text()
        for needle in ('P.get("days")', 'P.get("q")', 'P.get("from")', 'P.get("important")'):
            self.assertIn(needle, txt)
        # deep links are applied to the state before the first paint (no unfiltered flash), and the
        # camera is one transform on a world group (no per-frame viewBox rewrite)
        self.assertLess(txt.index("URLSearchParams"), txt.index("buildDom();"))
        self.assertIn('el("g", { id: "world" })', txt)

    def test_hub_builds_index_dag_and_copies_reports(self):
        self.p.init()
        a = self.p.new("base")
        outd = self.p.root / "experiments" / a / "out"
        (outd / "report.html").write_text("<p>small report</p>")
        (outd / "viz").mkdir()
        (outd / "viz" / "big.html").write_text("x" * 2_000_000)
        self.p.run("done", a, "--finding", "it works: 1 vs 0")
        site = self.p.tmp / "site"
        out = self.p.run("hub", "--out", str(site), "--max-mb", "1").stdout
        self.assertIn("1 experiments, 1 reports, 1 over cap", out)
        idx = (site / "index.html").read_text()
        self.assertIn("proj", idx)                      # project card
        self.assertIn("it works: 1 vs 0", idx)          # recent finding on the card
        dag = site / "proj" / "index.html"
        self.assertTrue(dag.is_file() and "<svg" in dag.read_text().lower() or "graph" in dag.read_text().lower())
        self.assertEqual((site / "proj" / "experiments" / a / "out" / "report.html").read_text(), "<p>small report</p>")
        big = (site / "proj" / "experiments" / a / "out" / "viz" / "big.html").read_text()
        self.assertIn("above the hub", big)             # oversized report replaced by a pointer page
        # the DAG page composes report links as <dir>/out/<report> at runtime; both parts are in its payload
        txt = dag.read_text()
        self.assertIn(f"experiments/{a}", txt)
        self.assertIn("report.html", txt)


    # ---- notes: dated entries in the README, from the CLI, the hub's queue, or the live server ----

    def test_notes_add_edit_delete_via_cli_and_intents(self):
        import base64
        self.p.init()
        a = self.p.new("base")
        out = self.p.run("note", a, "--text", "first thought", "--author", "Renzo", "--at", "2026-09-21T10:00Z").stdout
        self.assertIn("note added (2026-09-21T10:00Z)", out)
        txt = self.p.readme(a).read_text()
        self.assertIn("## Notes\n- **2026-09-21T10:00Z** (Renzo): first thought\n", txt)
        # a second note (multi-line) appends; the first stays
        self.p.run("note", a, "--text", "line one\nline two", "--at", "2026-09-21T11:00Z")
        txt = self.p.readme(a).read_text()
        self.assertIn("- **2026-09-21T11:00Z**: line one\n  line two\n", txt)
        self.assertEqual(txt.count("- **2026-09-21T"), 2)
        self.assertIn("first thought", self.p.run("note", a, "--list").stdout)
        # edit by stamp, through the hub's queued-marks document (text base64 so quotes survive)
        b = base64.b64encode('edited "quoted" text'.encode()).decode()
        doc = self.p.tmp / "intents.txt"
        doc.write_text(f"lab-exp intents v1\nproject: proj\nnote {a} --at 2026-09-21T10:00Z --replace 2026-09-21T10:00Z --author Renzo --b64 {b}\n")
        out = self.p.run("intents", str(doc)).stdout
        self.assertIn("note edited", out)
        txt = self.p.readme(a).read_text()
        self.assertIn('- **2026-09-21T10:00Z** (Renzo): edited "quoted" text\n', txt)
        self.assertNotIn("first thought", txt)
        # delete = empty text with --replace; the section disappears with its last note
        self.p.run("note", a, "--replace", "2026-09-21T10:00Z", "--text", "")
        self.p.run("note", a, "--replace", "2026-09-21T11:00Z", "--text", "")
        txt = self.p.readme(a).read_text()
        self.assertNotIn("## Notes", txt)
        self.assertNotIn("line one", txt)
        # the rest of the README is untouched by all of that
        self.assertIn("## Hypothesis", txt)
        r = self.p.run("note", a, "--replace", "2026-01-01T00:00Z", "--text", "x", check=False)
        self.assertNotEqual(r.returncode, 0)

    def test_dag_page_has_notes_ui(self):
        self.p.init()
        a = self.p.new("base")
        self.p.run("note", a, "--text", "hello note", "--at", "2026-09-21T10:00Z")
        site = self.p.tmp / "site_notes"
        self.p.run("hub", "--out", str(site))
        txt = (site / "proj" / "index.html").read_text()
        for needle in ("function notesSplit", "function noteUpsertText", 'id="note-text"', "note-save", "--b64", "hello note"):
            self.assertIn(needle, txt)

    # ---- intents: marks queued on the hub, applied on a box -------------------------------------

    def test_intents_apply_and_exit_codes(self):
        self.p.init()
        a = self.p.new("base")
        b = self.p.new("child", based_on=a)
        doc = self.p.tmp / "intents.txt"
        doc.write_text(f"lab-exp intents v1\nproject: proj\nsupersede {a} --by {b} --why \"replaced by child\"\nimportant {b}\n")
        out = self.p.run("intents", str(doc)).stdout
        self.assertEqual(out.count("OK "), 2, out)
        self.assertEqual(front(self.p.readme(a))["superseded_by"], b)
        self.assertIn("replaced by child", self.p.readme(a).read_text())
        self.assertIn("important", toks(front(self.p.readme(b))["tags"]))
        doc.write_text(f"project: proj\nunsupersede {a}\nunimportant {b}\n")
        self.p.run("intents", str(doc))
        self.assertNotIn("superseded_by", front(self.p.readme(a)))
        self.assertNotIn("important", toks(front(self.p.readme(b))["tags"]))
        # a project that is not on this machine: nothing applied, exit 4 (the other site's publisher owns it)
        doc.write_text("project: elsewhere\nimportant 20260101-x\n")
        r = self.p.run("intents", str(doc), check=False)
        self.assertEqual(r.returncode, 4)
        self.assertIn("SKIP", r.stdout)
        # a bad id: reported per line, exit 3, the good line still applied
        doc.write_text(f"project: proj\nimportant 20260101-nope\nimportant {a}\n")
        r = self.p.run("intents", str(doc), check=False)
        self.assertEqual(r.returncode, 3)
        self.assertIn("FAIL important 20260101-nope", r.stdout)
        self.assertIn("important", toks(front(self.p.readme(a))["tags"]))

    def test_hub_intents_url_reaches_the_page(self):
        self.p.init()
        self.p.new("base")
        site = self.p.tmp / "site"
        self.p.run("hub", "--out", str(site), "--intents", "https://github.com/x/y/issues/new")
        self.assertIn('const INTENTS = "https://github.com/x/y/issues/new";', (site / "proj" / "index.html").read_text())
        self.p.run("hub", "--out", str(site))
        self.assertIn('const INTENTS = "";', (site / "proj" / "index.html").read_text())


    # ---- hub change signal ---------------------------------------------------------------------

    def test_registry_writes_signal_the_hub(self):
        self.p.init()
        dirty = self.p.home / ".config" / "lab" / "hub.dirty"
        self.assertTrue(dirty.is_file())
        t0 = dirty.read_text()
        a = self.p.new("base")
        t1 = dirty.read_text()
        self.assertNotEqual(t0, t1)
        self.p.run("done", a, "--finding", "works")
        self.assertNotEqual(t1, dirty.read_text())
        self.p.run("list")                                  # reads never signal
        self.assertEqual(self.p.run("list").stdout, self.p.run("list").stdout)


    # ---- reports: skeleton + doctor's mechanical checks ------------------------------------------

    def test_report_skeleton_and_doctor_checks(self):
        self.p.init()
        a = self.p.new("base", title="Does X beat Y?")
        self.p.run("done", a, "--finding", "X beats Y: 0.9 vs 0.8", "--metrics", "acc=0.9")
        out = self.p.run("report", a).stdout
        self.assertIn("wrote", out)
        rp = self.p.root / "experiments" / a / "out" / "report.html"
        txt = rp.read_text()
        for needle in ("<title>Does X beat Y?</title>", "X beats Y: 0.9 vs 0.8", "<b>0.9</b>", "acc", a,
                       'name="viewport"', "prefers-color-scheme", "data-todo"):
            self.assertIn(needle, txt)
        r = self.p.run("report", a, check=False)                      # refuses to overwrite
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--force", r.stderr)
        self.p.run("report", a, "--out", "viz/extra.html")
        self.assertTrue((self.p.root / "experiments" / a / "out" / "viz" / "extra.html").is_file())
        # doctor: placeholders left behind are flagged
        d = self.p.run("doctor", check=False).stdout
        self.assertIn("skeleton placeholders", d)
        # a finished, self-contained report is clean
        rp.write_text('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                      '<title>ok</title><script src="https://cdn.jsdelivr.net/npm/vega@5"></script></head>'
                      '<body><img src="data:image/png;base64,AAAA"><a href="#top">top</a><a href="../other/out/report.html">x</a></body></html>')
        (self.p.root / "experiments" / a / "out" / "viz" / "extra.html").unlink()
        d = self.p.run("doctor", check=False).stdout
        self.assertNotIn("report ", d)
        # a report leaning on sibling files, fetches, or the size cap is flagged
        rp.write_text('<!doctype html><html><head><title>t</title></head><body><img src="fig.png">'
                      '<link rel="stylesheet" href="style.css"><script>fetch("data.json")</script></body></html>')
        d = self.p.run("doctor", check=False).stdout
        self.assertIn("fig.png", d)
        self.assertIn("style.css", d)
        self.assertIn("fetch/iframe", d)
        self.assertIn("no viewport meta", d)
        (self.p.root / "experiments" / a / "out" / "big.html").write_bytes(b"x" * (26 * 1048576))
        r = self.p.run("doctor", check=False)
        self.assertIn("note", r.stdout.split("26 MB > 25 MB hub cap")[0].splitlines()[-1])   # a note, not an issue


    # ---- [links] hub card, notes front-matter, ## Follow-ups ----------------------------------

    def test_hub_links_render_as_sibling_not_nested(self):
        """The card is itself an <a>, so [links] anchors can't nest inside it (invalid HTML) --
        they must render as a sibling row, still on the card."""
        self.p.init()
        self.p.new("base")
        with open(self.p.root / ".lab-exp.toml", "a") as fh:
            fh.write('\n[links]\nnotes = "obsidian://open?vault=Obsidian%20Vault&file=ALS"\n'
                     'bad = "javascript:alert(1)"\n')
        site = self.p.tmp / "site"
        self.p.run("hub", "--out", str(site))
        idx = (site / "index.html").read_text()
        self.assertIn('<a href="obsidian://open?vault=Obsidian%20Vault&amp;file=ALS">notes</a>', idx)
        self.assertNotIn("javascript:", idx)                 # disallowed scheme silently skipped
        card = re.search(r'<a class="card"[^>]*>.*?</a>', idx, re.S)
        self.assertIsNotNone(card)
        self.assertNotIn("<a href=\"obsidian:", card.group(0))   # links anchor is NOT nested inside it

    def test_new_notes_flows_to_registry_on_rebuild(self):
        self.p.init()
        a = self.p.new("base", notes="[[ALS/Experiment Journal]]")
        self.assertEqual(front(self.p.readme(a))["notes"], "[[ALS/Experiment Journal]]")
        self.assertEqual(read_tsv(self.p.tsv)[a]["notes"], "[[ALS/Experiment Journal]]")
        self.p.run("registry", "--rebuild")
        self.assertEqual(read_tsv(self.p.tsv)[a]["notes"], "[[ALS/Experiment Journal]]")
        # notes is README-owned: a sync never writes it back (nothing to write -- it's already there)
        self.p.run("registry", "--sync")
        self.assertEqual(front(self.p.readme(a))["notes"], "[[ALS/Experiment Journal]]")

    def test_old_registry_row_without_notes_pads_on_read(self):
        """A TSV cached before the `notes` column existed has 13 fields; reg_read must pad it
        instead of choking, and round-trip the rest of the row untouched."""
        self.p.init()
        a = self.p.new("base")
        old_cols = ["id", "date", "kind", "status", "agent", "host", "git_sha",
                    "based_on", "tags", "metrics", "finding", "wandb", "superseded_by"]
        row = read_tsv(self.p.tsv)[a]
        self.p.tsv.write_text("\t".join(old_cols) + "\n" + "\t".join(row.get(c, "") for c in old_cols) + "\n")
        self.p.run("done", a, "--finding", "works")
        after = read_tsv(self.p.tsv)[a]
        self.assertEqual(after["notes"], "")
        self.assertEqual(after["status"], "done")
        self.assertEqual(after["finding"], "works")

    def test_done_follow_up_appends_and_dedupes(self):
        self.p.init()
        a = self.p.new("base")
        self.p.run("done", a, "--follow-up", "check X", "--follow-up", "check Y")
        txt = self.p.readme(a).read_text()
        self.assertIn("## Follow-ups", txt)
        self.assertIn("- [ ] check X", txt)
        self.assertIn("- [ ] check Y", txt)
        self.assertLess(txt.index("## Follow-ups"), txt.index("- [ ] check X"))
        # repeating the same call must not duplicate either line
        self.p.run("done", a, "--follow-up", "check X", "--follow-up", "check Y")
        txt2 = self.p.readme(a).read_text()
        self.assertEqual(txt2.count("- [ ] check X"), 1)
        self.assertEqual(txt2.count("- [ ] check Y"), 1)


if __name__ == "__main__":
    unittest.main()
