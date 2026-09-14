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


if __name__ == "__main__":
    unittest.main()
