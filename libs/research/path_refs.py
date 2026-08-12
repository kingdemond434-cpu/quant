"""WHO READS A STORE, AND WHO WRITES IT -- resolved from the syntax tree, not from line text.

R0356. `max_audit.check_phantom_paths` hunts the desk's most prolific defect class: a path some
organ reads that NOTHING ever writes, which does not crash but takes the empty branch and reports
a plausible zero. The detector was right about the class and wrong about half its instances --
its own docstring says a fence at 50% noise "gets acknowledged into silence", and it was measured
at 26 reported paths / 7 genuine on 2026-08-05 and 108 reported on 2026-08-12.

Every one of its blind spots is the same root cause: it matched LINE TEXT, and a path in Python is
an EXPRESSION. All four were verified in the wild before this module was written.

1. SPLIT LITERALS. `_OUT = _ROOT / "reports" / "permutation_null.json"` never matches a regex
   requiring `reports/` inside one string, so the name is never bound and its writer is invisible.
   Live in scripts/measure_permutation_null.py:48 and scripts/run_real_campaign.py:37.

2. A PATH WRITTEN THROUGH A PARAMETER. `_merge_ramp(rep, _RAMP)` where the callee does
   `path.write_text(...)`. The old alias rule only understood `def f(p=CONST)`, never a positional
   argument. Live in scripts/run_cost_identification.py:430 -- and `data/ramp_state.json` is
   exactly the file L1.55 was written about, so the fence was reporting a phantom whose producer
   had been built.

3. ALIASES WHOSE RHS DOES NOT START WITH THE NAME. `out = root / _REPORT_REL` was not seen as
   binding `out`, because the pattern anchored the name immediately after `=`.

4. A PROVENANCE LABEL COUNTED AS A READ. `"source": "reports/real_campaign.json"` inside a dict
   that gets serialised into a report opens nothing. Live in scripts/audit_reality_check.py:201.
   A label cannot take the empty branch, so it cannot exhibit the failure the fence detects.

WHICH DIRECTION THE REMAINING ERROR RUNS, WHICH IS THE PART THAT MATTERS FOR A DETECTOR. Resolving
MORE writers can only ever REMOVE a phantom report, and reclassifying a label can only remove a
reader. Both are precision repairs, and neither can hide a genuine read-without-writer: a real
reader still reads, and a path with no writer anywhere still has none. What this module must never
do is invent a writer, so `_resolve` returns None on anything it cannot evaluate rather than
guessing -- an unresolvable expression leaves the path REPORTED, which is the safe direction for a
fence whose entire job is noticing absence.

KNOWN AND DELIBERATE LIMITS, recorded because an unstated limit reads as coverage: propagation into
a callee is ONE hop (enough for every instance measured here), a path built inside a comprehension
or an f-string is not resolved, and a write through a container element is not tracked. Each of
those fails toward REPORTING a phantom.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

#: Durable stores a reader can be wrong about. Logs are deliberately absent: cron writes them by
#: shell redirection, so every one would read as a phantom and the fence would be switched off.
EXTS: tuple[str, ...] = (".json", ".jsonl", ".db", ".sqlite", ".csv", ".pkl", ".parquet")

#: Only desk-owned store roots. A path outside these is somebody else's filesystem.
PREFIXES: tuple[str, ...] = ("data/", "reports/")

#: Methods that PRODUCE the path they are called on. `unlink`/`rename`/`replace` count because a
#: file the desk deletes or moves is a file the desk owns the lifecycle of -- it had a producer.
WRITE_METHODS: frozenset[str] = frozenset({
    "write_text", "write_bytes", "to_csv", "to_json", "to_parquet", "to_pickle", "to_feather",
    "to_hdf", "touch", "mkdir", "unlink", "rename", "replace", "savefig", "write_parquet",
})

#: `f(..., path, ...)` forms where a path argument is the destination.
WRITE_FUNCS: frozenset[str] = frozenset({
    "savefig", "copyfile", "copy2", "save", "savez", "imwrite", "connect",
})


@dataclass
class Scan:
    """Every desk store the tree mentions, split by how it is actually used."""

    reads: dict[str, set[str]] = field(default_factory=dict)
    writes: dict[str, set[str]] = field(default_factory=dict)
    labels: dict[str, set[str]] = field(default_factory=dict)

    def phantoms(self, root: Path, *,
                 allowed: frozenset[str] | set[str] = frozenset()) -> list[str]:
        """Paths a reader consumes that nothing produces and that are not on disk."""
        return sorted(
            p for p in self.reads
            if p not in allowed and not self.writes.get(p) and not (root / p).exists()
        )


def is_store(s: str) -> bool:
    """A concrete desk store -- not a glob, not a format template.

    `data/*.jsonl` and `data/{name}.json` are SHAPES, not files: nothing can write "the path with
    a star in it", so every one of them would report as an eternal phantom. The old regex excluded
    them only by accident of its character class, and resolving expressions properly is what made
    them reachable, so the exclusion has to be stated rather than inherited.
    """
    return (s.startswith(PREFIXES) and s.endswith(EXTS)
            and not any(c in s for c in "*?{}[]%"))


class _Module:
    """One file's path bindings, resolved structurally.

    Held as a class rather than a function because the passes are genuinely ordered: names must be
    bound before a call's arguments can be resolved, and arguments must be resolved before a
    callee's body can be scanned for writes through its parameter.
    """

    def __init__(self, tree: ast.AST) -> None:
        self.tree = tree
        #: Walked ONCE and reused. The passes below need four traversals, and re-walking a
        #: 6000-line module four times cost 23.8s across the tree -- enough to time out the
        #: harness that runs every registered check in one subprocess. Materialising the node
        #: list changes no verdict and is the whole difference.
        self.nodes: list[ast.AST] = list(ast.walk(tree))
        self.names: dict[str, str] = {}          # module/function-local name -> path
        self.attrs: dict[str, str] = {}          # "self.x" -> path
        self.funcs: dict[str, ast.FunctionDef] = {}
        self.reads: set[str] = set()
        self.writes: set[str] = set()
        self.label_only: set[str] = set()

    # -- resolution ------------------------------------------------------------------------
    def _resolve(self, node: ast.AST | None) -> str | None:
        """Evaluate an expression to a desk-relative path, or None when it cannot be evaluated.

        None is load-bearing: it means "unknown", and an unknown writer must never suppress a
        phantom report. Only literal structure is trusted.
        """
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            lhs, rhs = self._resolve(node.left), self._resolve(node.right)
            if rhs is None:
                return None
            # An unresolvable LEFT is the ROOT ANCHOR case -- `_ROOT / "data" / "x.json"`, where
            # `_ROOT` is a Path nobody needs to know the value of. The prefix filter is what keeps
            # this honest: a suffix that does not begin data/ or reports/ is discarded anyway, so
            # treating an unknown anchor as empty cannot manufacture a desk store.
            #
            # An ABSOLUTE left is the same case wearing a value. `Path("/srv/desk") / "data/x.json"`
            # is anchored at a checkout root, and keeping the prefix yields "srv/desk/data/x.json",
            # which matches no desk store and silently drops the reference. Found by this module's
            # own tests, where every fixture anchored on Path("/desk") and reported nothing at all.
            if lhs and lhs.startswith("/"):
                lhs = ""
            return f"{lhs}/{rhs}".lstrip("/") if lhs else rhs
        if isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, "id", None) or getattr(fn, "attr", None)
            if name in {"Path", "PosixPath"} and node.args:
                return self._resolve(node.args[0])
            if name in {"joinpath", "with_suffix", "resolve", "expanduser", "absolute"}:
                base = self._resolve(getattr(fn, "value", None))
                parts = [self._resolve(a) for a in node.args]
                if base is not None and all(p is not None for p in parts):
                    return "/".join([base, *[p for p in parts if p]]).lstrip("/")
            return None
        if isinstance(node, ast.Name):
            return self.names.get(node.id)
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                return self.attrs.get(f"self.{node.attr}")
            return None
        return None

    def _bind(self, target: ast.AST, value: ast.AST) -> None:
        got = self._resolve(value)
        if got is None or not is_store(got):
            return
        if isinstance(target, ast.Name):
            self.names[target.id] = got
        elif (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                and target.value.id == "self"):
            self.attrs[f"self.{target.attr}"] = got

    # -- passes ----------------------------------------------------------------------------
    def run(self) -> None:
        for node in self.nodes:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                self.funcs[node.name] = node                    # type: ignore[assignment]
        # Two binding sweeps: a constant defined below its first use still binds, which is normal
        # in a module whose functions run after import.
        for _ in range(2):
            for node in self.nodes:
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        self._bind(t, node.value)
                elif isinstance(node, ast.AnnAssign) and node.value is not None:
                    self._bind(node.target, node.value)
                # A default argument binds its parameter: `def append(*, path=LEDGER)`.
                elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    a = node.args
                    for arg, dflt in zip(a.args[len(a.args) - len(a.defaults):], a.defaults,
                                         strict=False):
                        got = self._resolve(dflt)
                        if got is not None and is_store(got):
                            self.names[arg.arg] = got
                    for kwarg, kwdflt in zip(a.kwonlyargs, a.kw_defaults, strict=False):
                        got = self._resolve(kwdflt) if kwdflt is not None else None
                        if got is not None and is_store(got):
                            self.names[kwarg.arg] = got
        self._propagate_into_callees()
        self._collect()

    def _propagate_into_callees(self) -> None:
        """BLIND SPOT 2: a path handed to a local helper that writes through the parameter.

        One hop only. Every instance measured on this tree is one hop, and each further hop widens
        the chance of binding a parameter that is not the path -- which would invent a writer, the
        one error direction this module may not take.
        """
        for node in self.nodes:
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            fn = self.funcs.get(node.func.id)
            if fn is None:
                continue
            params = [a.arg for a in fn.args.args]
            for i, arg in enumerate(node.args):
                got = self._resolve(arg)
                if got is not None and is_store(got) and i < len(params):
                    self.names.setdefault(params[i], got)
            for kw in node.keywords:
                got = self._resolve(kw.value)
                if got is not None and is_store(got) and kw.arg:
                    self.names.setdefault(kw.arg, got)

    def _collect(self) -> None:
        """Classify every mention: WRITE beats READ, and a dict-value-only mention is a LABEL."""
        mentioned: set[str] = set()
        non_label: set[str] = set()

        for node in self.nodes:
            # -- writes
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Attribute) and fn.attr in WRITE_METHODS:
                    got = self._resolve(fn.value)
                    if got is not None and is_store(got):
                        self.writes.add(got)
                        non_label.add(got)
                name = getattr(fn, "id", None) or getattr(fn, "attr", None)
                if name == "open":
                    tgt = self._resolve(fn.value if isinstance(fn, ast.Attribute) else
                                        (node.args[0] if node.args else None))
                    mode = ""
                    if not isinstance(fn, ast.Attribute) and len(node.args) > 1:
                        mode = self._resolve(node.args[1]) or ""
                    elif isinstance(fn, ast.Attribute) and node.args:
                        mode = self._resolve(node.args[0]) or ""
                    for kw in node.keywords:
                        if kw.arg == "mode":
                            mode = self._resolve(kw.value) or mode
                    if tgt is not None and is_store(tgt):
                        non_label.add(tgt)
                        if any(c in mode for c in "wax+"):
                            self.writes.add(tgt)
                if name in WRITE_FUNCS:
                    for a in node.args:
                        got = self._resolve(a)
                        if got is not None and is_store(got):
                            self.writes.add(got)
                            non_label.add(got)
                # Any path used as a call ARGUMENT is genuinely in play, not a label.
                for a in [*node.args, *(k.value for k in node.keywords)]:
                    got = self._resolve(a)
                    if got is not None and is_store(got):
                        non_label.add(got)

            # -- a path bound to a NAME is in play whatever happens to it next
            if isinstance(node, ast.Assign | ast.AnnAssign):
                got = self._resolve(node.value)
                if got is not None and is_store(got):
                    non_label.add(got)

            # -- BLIND SPOT 4: a bare literal sitting in a dict VALUE opens nothing
            if isinstance(node, ast.Dict):
                for v in node.values:
                    if isinstance(v, ast.Constant) and isinstance(v.value, str) and is_store(
                            v.value):
                        mentioned.add(v.value)

            if isinstance(node, ast.Constant) and isinstance(node.value, str) and is_store(
                    node.value):
                mentioned.add(node.value)

        self.reads = (mentioned | non_label) - (mentioned - non_label)
        self.label_only = mentioned - non_label


def scan_file(path: Path) -> tuple[set[str], set[str], set[str]]:
    """(reads, writes, labels) for one module. Unparseable files yield nothing, never a guess."""
    try:
        text = path.read_text("utf-8", errors="ignore")
    except OSError:
        return set(), set(), set()
    # PARSING IS THE WHOLE COST (10.4s of 13.8s across the tree), so the cheapest real saving is
    # not parsing at all. SOUND, not a heuristic: every resolvable store begins with a `data` or
    # `reports` STRING COMPONENT, so a file whose source contains neither token cannot contribute
    # one however it assembles its paths. 264 of 1092 files qualify. The substring is deliberately
    # `data`, not `data/` -- the split-literal form this module exists for writes `"data"` alone.
    if "data" not in text and "reports" not in text:
        return set(), set(), set()
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return set(), set(), set()
    m = _Module(tree)
    m.run()
    return m.reads, m.writes, m.label_only


def scan(root: Path, subdirs: tuple[str, ...] = ("scripts", "libs")) -> Scan:
    """Walk the tree and resolve every desk-store reference in it."""
    out = Scan()
    for sub in subdirs:
        base = root / sub
        if not base.is_dir():
            continue
        for py in sorted(base.rglob("*.py")):
            rel = str(py.relative_to(root))
            reads, writes, labels = scan_file(py)
            for p in reads:
                out.reads.setdefault(p, set()).add(rel)
            for p in writes:
                out.writes.setdefault(p, set()).add(rel)
            for p in labels:
                out.labels.setdefault(p, set()).add(rel)
    # A path written anywhere is written, even if another file only labels it.
    for p in out.writes:
        out.reads.setdefault(p, set())
    return out
