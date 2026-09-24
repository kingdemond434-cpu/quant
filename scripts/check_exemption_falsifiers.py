#!/usr/bin/env python3
"""NO EXEMPTION WITHOUT A FALSIFIER -- an excuse that cannot expire is a permanent excuse.

    python scripts/check_exemption_falsifiers.py                 # schema + the measured half
    python scripts/check_exemption_falsifiers.py --schema-only   # the portable half (law gate)
    python scripts/check_exemption_falsifiers.py --report-only   # print, always exit 0
    python scripts/check_exemption_falsifiers.py --json

THE DEFECT THIS CLOSES. `desks/mt5/research/module_rent.py` retires a module that burns compute
and produces no cells -- unless it carries a declared EXEMPTION. The exemption schema was a
token -> reason map: a sentence, with no condition under which the sentence stops being true. So
21 declarations (plus two borrowed registries, ~30 more keys) could excuse an organ from the
rent ledger FOREVER, and the one structure on this desk whose entire purpose is that no module
exists for free was itself the thing that could never be wrong.

The desk already had the rule and had written it down in the neighbouring ledger --
`docs/research/productivity_blockers.json`: *"an EXEMPTION here is PERMANENT only while it stays
true: every row carries `retire_if`, the condition that deletes it, so a declaration cannot
outlive the fact it was declared on."* Nothing enforced it there either: `check_producer_yield`
accepts an exemption on `exempt` + `produces` + `consumer` and never looks at `retire_if`, so a
new row could be added without one and nothing would say so. This fence holds BOTH registries to
the same rule, which is the only reason it is worth having: a law enforced in one of the two
places it applies is a law with a documented way around it.

WHAT IT CHECKS, in two halves that fail differently on purpose:

  SCHEMA (rc=2, portable -- source and docs only, so it means the same in CI, a fresh clone and
  on the box). Every declaration in `module_rent.EXEMPTIONS` and `module_rent.INHERITED` carries
  a non-empty `retire_if` over the length bar, names checks that `RETIRE_CHECKS` actually
  measures, and is dated. `EXEMPT_TOKENS` must remain DERIVED from `EXEMPTIONS` rather than a
  dict literal, which is what stops the old falsifier-less shape being reintroduced by someone
  who only reads the bottom of the file. Every `exempt: true` row in productivity_blockers.json
  carries a `retire_if` of its own.

  MEASURED (rc=1, needs the desk's own artifact). Reads the `exemptions` census that the daily
  `module_rent_research` leg writes into desks/mt5/reports/MODULE_RENT_RESEARCH.json and names
  every declaration whose falsifier has ARRIVED -- RETIRE (it fired for every module the row
  still covers: delete the declaration) and PARTIAL (it fired for some: those modules are no
  longer shielded). A missing report is UNMEASURED and never a pass: it is said, with the path.

NOTHING IS DELETED HERE, and nothing is throttled. A fired falsifier already stops shielding in
the pass that measures it -- that happens in module_rent, not here -- and removing the
declaration from the source is a person's act made against this report. No organ's cadence, heat
or compute budget is touched by anything in this file: the point is to delete stale excuses, not
to cap work.

Registered in `scripts/run_law_gate.py` (_LAW_FENCES) with --schema-only, so the portable half
gates every commit, every push and the hourly gate; the measured half is published every day by
the module_rent leg and printed in full by a bare run.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RENT = ROOT / "desks" / "mt5" / "research" / "module_rent.py"
BLOCKERS = ROOT / "docs" / "research" / "productivity_blockers.json"
REPORT = ROOT / "desks" / "mt5" / "reports" / "MODULE_RENT_RESEARCH.json"
ARTIFACT = ROOT / "desks" / "mt5" / "reports" / "EXEMPTION_FALSIFIERS.json"

#: The bar a falsifier has to clear to be a condition rather than a mood. Kept in step with
#: `module_rent.MIN_RETIRE_IF_CHARS`; the fence asserts they agree rather than assuming it.
MIN_RETIRE_IF_CHARS = 40


def _load_rent() -> Any:
    """Import the rent module the way the desk imports it (bare name, desk on sys.path)."""
    for p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import module_rent

    return module_rent


def check_module_schema() -> tuple[list[str], dict[str, Any]]:
    """The exemption registry, as DATA and as SOURCE.

    Two passes, because they catch different things. The data pass walks the live registry and
    asks each declaration for its falsifier -- that is what the constructor already refuses, and
    walking it turns an exception nobody sees into a line a fence prints. The source pass is the
    one that matters over time: it asserts `EXEMPT_TOKENS` is still DERIVED, so the old
    `{token: reason}` literal cannot come back as a second, unfenced way to write an exemption.
    """
    problems: list[str] = []
    census: dict[str, Any] = {"n_declared": 0, "n_inherited": 0, "checks": [],
                              "min_retire_if_chars": MIN_RETIRE_IF_CHARS}
    try:
        rent = _load_rent()
    except Exception as exc:                        # ANY import failure is reported, never hidden
        return ([f"module_rent is not importable ({type(exc).__name__}: {exc}), so the exemption "
                 "registry cannot be verified at all -- UNMEASURED never buys a pass (L1.28a)"],
                census)

    census["n_declared"] = len(rent.EXEMPTIONS)
    census["n_inherited"] = len(rent.INHERITED)
    census["checks"] = sorted(rent.RETIRE_CHECKS)
    if int(rent.MIN_RETIRE_IF_CHARS) != MIN_RETIRE_IF_CHARS:
        problems.append(f"module_rent.MIN_RETIRE_IF_CHARS is {rent.MIN_RETIRE_IF_CHARS}, this "
                        f"fence holds {MIN_RETIRE_IF_CHARS}: two bars for one law")
    problems += [f"module_rent.{p}" for p in rent.validate_exemptions()]

    derived = {tok: ex.why for tok, ex in rent.EXEMPTIONS.items()}
    if dict(rent.EXEMPT_TOKENS) != derived:
        problems.append("module_rent.EXEMPT_TOKENS is not derived from EXEMPTIONS: a second "
                        "exemption surface with no falsifier on it")

    try:
        tree = ast.parse(RENT.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        problems.append(f"{RENT} unreadable ({exc}): the source shape cannot be verified")
        return problems, census
    for node in ast.walk(tree):
        target = getattr(node, "target", None)
        if not isinstance(node, ast.AnnAssign) or getattr(target, "id", "") != "EXEMPT_TOKENS":
            continue
        if isinstance(node.value, ast.Dict):
            problems.append(
                "module_rent.EXEMPT_TOKENS is a dict LITERAL again: that is the falsifier-less "
                "shape this law exists to refuse. Declare exemptions as Exemption(...) rows in "
                "EXEMPTIONS and leave EXEMPT_TOKENS derived from them")
    return problems, census


def check_blockers() -> tuple[list[str], dict[str, Any]]:
    """`docs/research/productivity_blockers.json`: the desk's OTHER exemption registry.

    Its own note already promises every exemption carries `retire_if`; `check_producer_yield`
    never reads the field, so the promise was kept by hand. An absent file is UNMEASURED with
    the path -- this fence does not invent a registry that is not there, and does not pass on
    its absence either.
    """
    problems: list[str] = []
    census: dict[str, Any] = {"path": BLOCKERS.relative_to(ROOT).as_posix(),
                              "n_rows": 0, "n_exempt": 0, "measured": False}
    try:
        doc = json.loads(BLOCKERS.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        census["why"] = f"{BLOCKERS} unreadable ({type(exc).__name__}): UNMEASURED, not clean"
        return problems, census
    rows = doc.get("blockers")
    if not isinstance(rows, dict):
        census["why"] = "no `blockers` object: UNMEASURED, not clean"
        return problems, census
    census["measured"] = True
    census["n_rows"] = len(rows)
    for key, row in sorted(rows.items()):
        if not isinstance(row, dict) or not row.get("exempt"):
            continue
        census["n_exempt"] += 1
        cond = str(row.get("retire_if") or "").strip()
        if not cond:
            problems.append(f"productivity_blockers[{key}]: an EXEMPTION with no `retire_if` -- "
                            "a permanent excuse; name the condition that deletes the row")
        elif len(cond) < MIN_RETIRE_IF_CHARS:
            problems.append(f"productivity_blockers[{key}]: retire_if is {len(cond)} chars, "
                            f"under the {MIN_RETIRE_IF_CHARS}-char bar for a condition")
    return problems, census


def measured_half() -> dict[str, Any]:
    """Which declarations have OUTLIVED the fact they were declared on, from the rent report."""
    try:
        doc = json.loads(REPORT.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"measured": False,
                "why": (f"{REPORT.relative_to(ROOT).as_posix()} absent or unreadable "
                        f"({type(exc).__name__}): which exemptions have expired is UNMEASURED on "
                        "this host, which is a verdict and not a pass (L1.28a). The daily "
                        "`module_rent_research` leg writes it."),
                "retire": [], "partial": [], "covers_nothing": [], "n_modules_unshielded": 0}
    census = doc.get("exemptions")
    if not isinstance(census, list):
        return {"measured": False,
                "why": ("the rent report carries no `exemptions` census: it was written by a "
                        "build from before the falsifier schema landed"),
                "retire": [], "partial": [], "covers_nothing": [], "n_modules_unshielded": 0}
    def pick(verdict: str) -> list[dict[str, Any]]:
        return [{"key": r.get("key"), "kind": r.get("kind"),
                 "why_verdict": r.get("why_verdict"), "n_covered": r.get("n_covered"),
                 "n_fired": r.get("n_fired"),
                 "fired_modules": [m.get("module") for m in (r.get("fired_modules") or [])]}
                for r in census if isinstance(r, dict) and r.get("verdict") == verdict]

    summary = doc.get("exemptions_summary") or {}
    return {"measured": True, "at": doc.get("at"), "n_declarations": len(census),
            "retire": pick("RETIRE"), "partial": pick("PARTIAL"),
            "covers_nothing": [r.get("key") for r in census
                               if isinstance(r, dict) and r.get("verdict") == "COVERS_NOTHING"],
            "n_modules_unshielded": int(summary.get("n_modules_unshielded") or 0),
            "schema_problems_at_build": list(doc.get("exemption_schema_problems") or [])}


def build_report() -> dict[str, Any]:
    mod_problems, mod_census = check_module_schema()
    blk_problems, blk_census = check_blockers()
    problems = mod_problems + blk_problems
    measured = measured_half()
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "law": ("NO EXEMPTION WITHOUT A FALSIFIER: every declared excuse from a retire "
                    "verdict carries `retire_if` and the measured checks behind it, so a "
                    "declaration cannot outlive the fact it was declared on"),
            "status": "BREACH" if problems else ("OWED" if measured.get("retire") or
                                                 measured.get("partial") else
                                                 ("UNMEASURED" if not measured["measured"]
                                                  else "OK")),
            "schema_problems": problems,
            "module_rent": mod_census, "productivity_blockers": blk_census,
            "expired": measured}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--schema-only", action="store_true",
                    help="the portable half: source and docs, no desk artifacts (the law gate's "
                         "invocation -- it means the same in CI and in a fresh clone)")
    ap.add_argument("--report-only", action="store_true", help="print everything, exit 0")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep = build_report()

    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        mc, bc = rep["module_rent"], rep["productivity_blockers"]
        print(f"exemption falsifiers: {rep['status']} -- {mc['n_declared']} declared + "
              f"{mc['n_inherited']} inherited in module_rent, {bc['n_exempt']} in "
              f"productivity_blockers; checks {', '.join(mc['checks'])}")
        for p in rep["schema_problems"]:
            print(f"  BREACH: {p}")
        exp = rep["expired"]
        if not exp["measured"]:
            print(f"  UNMEASURED: {exp['why']}")
        else:
            print(f"  expired census at {exp['at']}: {len(exp['retire'])} RETIRE, "
                  f"{len(exp['partial'])} PARTIAL, {len(exp['covers_nothing'])} COVERS_NOTHING; "
                  f"{exp['n_modules_unshielded']} module(s) no longer shielded")
            for r in exp["retire"]:
                print(f"    RETIRE  {r['key']}: {r['why_verdict']}")
            for r in exp["partial"]:
                print(f"    PARTIAL {r['key']}: fired on "
                      f"{', '.join(r['fired_modules'][:4]) or '(unnamed)'}")
            if exp["covers_nothing"]:
                print(f"    COVERS_NOTHING: {', '.join(str(k) for k in exp['covers_nothing'])}")

    try:
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT.write_text(json.dumps(rep, indent=1), "utf-8")
    except OSError:
        pass

    if a.report_only:
        return 0
    if rep["schema_problems"]:
        return 2
    if a.schema_only:
        return 0
    # A declaration that outlived its fact is OWED, not a breach of the schema: it is named,
    # every pass, until a person deletes the row. Nothing is disabled and no cadence is touched.
    return 1 if (rep["expired"]["retire"] or rep["expired"]["partial"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
