"""NO BAR EVER RISES WITH A TRIAL COUNT (principal, 2026-10-13).

    "make sure the bars never raise never ever penalty never inflation due to trials anything
     like that"  /  "yes and this should be permanently monitpred too js incase so it never
     inflates"

The Tier S bar is fixed by the owner's T8 ruling: deflated Sharpe at N = 5 with the per-cell
null variance 1/(T-1) (t about 2.84). `libs.research.trial_count_guard.bar_n` is the only
lawful source of a bar's N. This fence walks the tree and goes RED on:

1. UNPINNED BAR CALL. Any call to a bar function (deflate_t, deflated_sharpe_ratio,
   expected_max_sharpe, expected_max_z, deflation, trials_penalty) whose trial-count argument is
   not `bar_n(...)`, `BAR_N`, or a literal at or below BAR_N. A new file that brings its own
   trial count is caught here on its first commit.
2. LIFETIME UNION CHARGE in the sealed judge (`charged_lifetime_trials`). The sealed files cannot
   change without the laptop's re-sign, so a sealed site that the T8 patch owns is OWED: WARN
   until SEALED_DEADLINE, then FAIL. An owed sealed site with no named patch FAILs at once.
3. RE-RUN SHARE RISING after the ledger dedupe lands (marker `desks/mt5/data/TRIAL_DEDUPE_LANDED`):
   the share of charged trials that are repeats of an already-charged pass may not rise over the
   last reading. Before the dedupe it is MEASURED and published, never failed.

Writes `desks/mt5/reports/TRIAL_INFLATION.json` with --report; exits 1 on any FAIL.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.trial_count_guard import BAR_N, run_key, trial_id  # noqa: E402

DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "TRIAL_INFLATION.json"
DEDUPE_MARKER = DESK / "data" / "TRIAL_DEDUPE_LANDED"
RULE = "every bar's N comes from trial_count_guard.bar_n (fixed N=5, owner's T8 ruling)"

#: Bar function -> (positional index of its trial count, keyword spellings of it).
BAR_FUNCS: dict[str, tuple[int, tuple[str, ...]]] = {
    "deflate_t": (1, ("n_tests", "n", "n_trials")),
    "deflated_sharpe_ratio": (1, ("n_trials",)),
    "expected_max_sharpe": (0, ("n_trials", "n")),
    "expected_max_z": (0, ("n", "n_tests")),
    "deflation": (0, ("n_trials", "n")),
    "trials_penalty": (0, ("effective_trials",)),
    "deflated_t": (1, ("n_trials",)),
    "expected_max_t": (0, ("n_trials", "n")),
    "sr0": (0, ("n_trials",)),
}

#: Functions that compute a deflation ONLY TO REPORT IT beside the fixed bar, never to rule;
#: each is reviewed and named here, so a new one cannot arrive unnoticed.
REPORTED_ONLY: dict[tuple[str, str], str] = {
    ("desks/mt5/mt5desk/canonical.py", "deflation_pair"):
        "publishes SR0 at the raw and the deduplicated counts side by side; rules nothing",
}

#: Sealed sites the T8 sealed patch rewrites; they change only by the laptop's re-sign.
T8_PATCH = "/mnt/project-files/judging/trial_count_guard/sealed/tier_s_t8_combined.patch"
SEALED_OWED: dict[str, str] = {
    "desks/mt5/scripts/external_gauntlet.py": T8_PATCH,
    "desks/mt5/research/gate_policy.py": T8_PATCH,
    "desks/mt5/research/universal_gate.py": T8_PATCH,
    "desks/mt5/research/multiplicity.py": T8_PATCH,
    "desks/mt5/research/fragility.py": T8_PATCH,      # money path
    "desks/mt5/research/run_hunt12.py": T8_PATCH,     # money path
    # universal_gate's remote worker and its calibration twin: they change WITH universal_gate,
    # or the remote and local verdicts of one sealed gate would disagree.
    "desks/mt5/side_channels/ug_remote.py": T8_PATCH,
    "desks/mt5/side_channels/gate_calibration.py": T8_PATCH,
}
#: The owner's yes was 2026-10-13; the sealed half has fourteen days to reach the box.
SEALED_DEADLINE = datetime(2026, 10, 27, tzinfo=UTC)

#: Never scanned: tests pin behaviour with explicit counts; retired code never runs.
SKIP_PARTS = {".git", "tests", "_retired", "node_modules", "__pycache__", ".venv", "venv",
              "backups", "lesson_vault"}
RERUN_TOL = 0.005


def _callee(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def _pinned(arg: ast.expr, scope: ast.AST | None = None, depth: int = 0) -> bool:
    """bar_n(...), BAR_N, a literal count at or below BAR_N, a conditional whose every branch is
    pinned, or a local name whose every assignment in the enclosing function is pinned."""
    if isinstance(arg, ast.IfExp):
        return _pinned(arg.body, scope, depth) and _pinned(arg.orelse, scope, depth)
    if isinstance(arg, ast.Name) and scope is not None and depth < 3 and arg.id != "BAR_N":
        vals = [n.value for n in ast.walk(scope) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == arg.id for t in n.targets)]
        vals += [n.value for n in ast.walk(scope) if isinstance(n, ast.AnnAssign)
                 and isinstance(n.target, ast.Name) and n.target.id == arg.id and n.value]
        return bool(vals) and all(_pinned(v, scope, depth + 1) for v in vals)
    if isinstance(arg, ast.Call) and _callee(arg) == "bar_n":
        return True
    if isinstance(arg, ast.Name) and arg.id == "BAR_N":
        return True
    if isinstance(arg, ast.Attribute) and arg.attr == "BAR_N":
        return True
    return (isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float))
            and not isinstance(arg.value, bool) and arg.value <= BAR_N)


class _Scan(ast.NodeVisitor):
    def __init__(self, rel: str = "") -> None:
        self.rel = rel
        self.stack: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self.hits: list[tuple[int, str, str]] = []
        self.union = False

    def _fn(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if node.name == "charged_lifetime_trials":
            self.union = True
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = _fn
    visit_AsyncFunctionDef = _fn

    def _plumbing(self, arg: ast.expr) -> bool:
        """Inside a bar primitive's own body (a function named in BAR_FUNCS), passing its count
        on is plumbing: its CALLERS are the sites scanned."""
        return bool(self.stack) and self.stack[-1].name in BAR_FUNCS

    def visit_Call(self, node: ast.Call) -> None:
        name = _callee(node)
        if name in BAR_FUNCS:
            pos, kws = BAR_FUNCS[name]
            arg: ast.expr | None = node.args[pos] if len(node.args) > pos else None
            for kw in node.keywords:
                if kw.arg in kws:
                    arg = kw.value
            reported = bool(self.stack) and (self.rel, self.stack[-1].name) in REPORTED_ONLY
            scope = self.stack[-1] if self.stack else None
            if arg is not None and not _pinned(arg, scope) and not self._plumbing(arg) \
                    and not reported:
                self.hits.append((node.lineno, name, ast.unparse(arg)[:80]))
        self.generic_visit(node)


def _files(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS and not d.startswith(".")]
        out.extend(Path(dirpath) / f for f in filenames
                   if f.endswith(".py") and not f.startswith("test_"))
    return sorted(out)


def _pins_inside(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """The definition sends its count through bar_n itself, so no caller can raise its bar."""
    return any(isinstance(n, ast.Call) and _callee(n) == "bar_n" for n in ast.walk(fn))


def scan(root: Path = ROOT) -> dict[str, Any]:
    unpinned: list[dict[str, Any]] = []
    union: list[str] = []
    trees: list[tuple[str, ast.AST]] = []
    for p in _files(root):
        rel = p.relative_to(root).as_posix()
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not any(f in text for f in (*BAR_FUNCS, "charged_lifetime_trials")):
            continue                     # parse only files that can hold a bar call
        try:
            trees.append((rel, ast.parse(text)))
        except (SyntaxError, ValueError):
            continue
    # A bar function whose EVERY definition in the tree pins internally is safe to call with any
    # count; one unpinned definition anywhere keeps every caller under scan.
    defs: dict[str, list[bool]] = {}
    for _rel, tree in trees:
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in BAR_FUNCS:
                defs.setdefault(n.name, []).append(_pins_inside(n))
    safe = {k for k, v in defs.items() if v and all(v)}
    for rel, tree in trees:
        s = _Scan(rel)
        s.visit(tree)
        if s.union:
            union.append(rel)
        unpinned += [{"file": rel, "line": ln, "call": fn, "trials_arg": a}
                     for ln, fn, a in s.hits if fn not in safe]
    return {"unpinned": unpinned, "union_charge": union, "pinned_inside": sorted(safe)}


def _discovery_rerun_share(root: Path = ROOT) -> dict[str, Any]:
    """Share of discovery-file `tests_run` that repeats an already-charged pass."""
    raw = distinct = 0
    seen: set[str] = set()
    for f in sorted((root / "desks" / "mt5" / "data" / "intelligence").glob(
            "*/discoveries_*.json")):
        try:
            d = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict) or not isinstance(d.get("tests_run"), (int, float)):
            continue
        n = int(d["tests_run"])
        k = run_key(f.parent.name, n, sorted(trial_id(r) for r in d.get("discoveries") or []
                                             if isinstance(r, dict)))
        raw += n
        if k not in seen:
            seen.add(k)
            distinct += n
    if not raw:
        return {"status": "UNMEASURED", "why": "no discovery file with tests_run on this host"}
    return {"status": "MEASURED", "n_charged": raw, "n_distinct": distinct,
            "rerun_share": round((raw - distinct) / raw, 6)}


def judge(root: Path = ROOT, *, now: datetime | None = None,
          prior: dict[str, Any] | None = None) -> dict[str, Any]:
    at = now or datetime.now(tz=UTC)
    found = scan(root)
    checks: list[dict[str, Any]] = []
    owed = [h for h in found["unpinned"] if h["file"] in SEALED_OWED]
    free = [h for h in found["unpinned"] if h["file"] not in SEALED_OWED]
    checks.append({"metric": "unpinned_bar_calls",
                   "state": "FAIL" if free else "OK", "n": len(free), "sites": free[:50],
                   "why": ("every bar's N comes from bar_n" if not free else
                           f"{len(free)} bar call(s) take their own trial count")})
    sealed = owed + [{"file": f, "call": "charged_lifetime_trials", "line": None,
                      "trials_arg": "lifetime union"} for f in found["union_charge"]]
    late = at >= SEALED_DEADLINE
    unowned = [s for s in sealed if s["file"] not in SEALED_OWED]
    state = ("OK" if not sealed else "FAIL" if (late or unowned) else "WARN")
    checks.append({"metric": "sealed_trial_charge", "state": state, "n": len(sealed),
                   "sites": sealed[:50], "owner": T8_PATCH,
                   "deadline_utc": SEALED_DEADLINE.isoformat(),
                   "why": ("no sealed site charges a moving N" if not sealed else
                           f"{len(sealed)} sealed site(s) still charge a moving N or the "
                           f"lifetime union; owed by the T8 sealed re-sign "
                           f"({'PAST' if late else 'due'} {SEALED_DEADLINE.date()})")})
    rr = _discovery_rerun_share(root)
    landed = DEDUPE_MARKER.exists() if root == ROOT else (
        root / "desks" / "mt5" / "data" / "TRIAL_DEDUPE_LANDED").exists()
    was = (prior or {}).get("rerun_share")
    rr_state = "UNMEASURED" if rr["status"] != "MEASURED" else "OK"
    if (rr_state == "OK" and landed and isinstance(was, (int, float))
            and rr["rerun_share"] > float(was) + RERUN_TOL):
        rr_state = "FAIL"
    checks.append({"metric": "ledger_rerun_share", "state": rr_state, "dedupe_landed": landed,
                   "previous": was, **rr,
                   "why": rr.get("why") or (
                       f"{rr['n_charged']} trials charged, {rr['n_distinct']} distinct: "
                       f"{rr['rerun_share']:.1%} are re-runs"
                       + ("" if landed else " (published; ratcheted once the dedupe lands)"))})
    verdict = "FAIL" if any(c["state"] == "FAIL" for c in checks) else "PASS"
    return {"at": at.isoformat(timespec="seconds"), "rule": RULE, "bar_n": BAR_N,
            "verdict": verdict, "checks": checks,
            "rerun_share": rr.get("rerun_share")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true", help="write TRIAL_INFLATION.json")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        prior = json.loads(REPORT.read_text("utf-8"))
    except (OSError, ValueError):
        prior = None
    doc = judge(prior=prior if isinstance(prior, dict) else None)
    if a.report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_name(f"{REPORT.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1), "utf-8")
        os.replace(tmp, REPORT)
    if a.json:
        print(json.dumps(doc, indent=1))
    else:
        print(f"trial inflation: {doc['verdict']} (bar N={BAR_N})")
        for c in doc["checks"]:
            print(f"  [{c['state']}] {c['metric']}: {c.get('why', '')}")
            for s in (c.get("sites") or [])[:10]:
                print(f"      {s['file']}:{s['line']} {s['call']}({s['trials_arg']})")
    return 1 if doc["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
