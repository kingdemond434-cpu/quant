"""WRITTEN REPLICATION SPECS for four families the spec book never covered (pass 10, rank 22).

    hourly leg `replication_spec_entries` -> reports/REPLICATION_SPEC_ENTRIES.json: whether
    the book validates, and any implementation whose file changed since its spec was written

REPLICATION.json (2026-10-14 02:39Z, still true at 2026-10-20 16:43Z) reports every certificate
of cross_asset_residual, macro_conditional, carry, clock_transition and formula UNMEASURED with
"no written specification in the spec book". Those five families held 871 of the 974
certificates the queue row counted. Since then the live SPEC_BOOK took up `carry`, so its row is
dropped here (2026-11-14): a second written rule beside the lane's own would be two contracts for
one family. This file stores the written rule for each of the other four in the
lane's own `RuleSpec` shape (family, text, defaults, selector_params, external_cell, native,
peers_key) as DATA, in `replication_specs/written_specs_p10.json`.

WHAT THIS IS NOT. It is not a verdict and it is not a builder. A spec is the contract a second
implementation is written from; `replication_civilization.py` alone writes REPLICATED, MISMATCH
or UNMEASURED after its own rebuild runs. This module refuses any row whose status is not
WRITTEN, and it imports neither the lane nor the original implementations (the tests do, to
check the defaults against the implementation's own signature).

How the lane takes these up is in the pass-10 APPLY.md: the builders (the lane's own reading of
each text) are on the 2026-10-14 `claude/replication-spec-book` bundles.

NO SCRIPT ENTRY GUARD (birth-obligation law, scripts/check_birth_obligations.py).
The hourly leg `replication_spec_entries` (research/hourly_cycle.py) calls `main()`
in-process. By hand, from the repo root:
    python -c "import sys; sys.path[:0]=['desks/mt5'];
        from research import replication_spec_entries as M; M.main()"
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
SPEC_FILE = DESK / "research" / "replication_specs" / "written_specs_p10.json"

#: `carry` is NOT here: replication_civilization.SPEC_BOOK already holds it on live.
FAMILIES: tuple[str, ...] = ("formula", "clock_transition", "cross_asset_residual",
                             "macro_conditional")
ROW_KEYS = frozenset({"family", "text", "defaults", "selector_params", "external_cell", "native",
                      "peers_key", "status", "implementation", "certificates_at_write",
                      "builder"})
#: The only status a spec row may carry. Verdicts belong to the replication lane.
ALLOWED_STATUS = "WRITTEN"
FORBIDDEN_WORDS = ("REPLICATED", "MISMATCH")


class SpecError(ValueError):
    """A spec file that is not a set of written specifications."""


def load(path: Path = SPEC_FILE) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SpecError(f"unreadable spec file {path.name}: {type(exc).__name__}") from exc
    validate(doc)
    out: dict[str, Any] = doc
    return out


def validate(doc: Any) -> None:
    """Raise SpecError unless `doc` is a book of WRITTEN specs in the RuleSpec shape."""
    if not isinstance(doc, dict):
        raise SpecError("spec file is not an object")
    contract = doc.get("cell_contract")
    if not isinstance(contract, str) or "EXTERNAL CELL CONTRACT" not in contract:
        raise SpecError("cell_contract missing")
    rows = doc.get("families")
    if not isinstance(rows, list):
        raise SpecError("families is not a list")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SpecError("a family row is not an object")
        fam = row.get("family")
        missing = ROW_KEYS - set(row)
        if missing:
            raise SpecError(f"{fam}: missing {sorted(missing)}")
        if fam in seen:
            raise SpecError(f"{fam}: written twice")
        seen.add(str(fam))
        if row["status"] != ALLOWED_STATUS:
            raise SpecError(f"{fam}: status {row['status']!r}; a spec is only ever WRITTEN")
        if not isinstance(row["text"], str) or len(row["text"]) < 200:
            raise SpecError(f"{fam}: the written rule is missing or too short to replicate from")
        if not isinstance(row["defaults"], dict) or not row["defaults"]:
            raise SpecError(f"{fam}: no defaults")
        if not isinstance(row["native"], list):
            raise SpecError(f"{fam}: native is not a list")
        # Case-insensitive: "replicated" in a note is the same claim as "REPLICATED".
        rest = json.dumps({k: v for k, v in row.items() if k != "text"}).upper()
        for word in FORBIDDEN_WORDS:
            if word in rest:
                raise SpecError(f"{fam}: a spec row carries the verdict word {word}")
    if set(FAMILIES) - seen:
        raise SpecError(f"families not written: {sorted(set(FAMILIES) - seen)}")
    if seen - set(FAMILIES):
        raise SpecError(f"families not in this book's charge: {sorted(seen - set(FAMILIES))}")


def full_text(doc: dict[str, Any], family: str) -> str:
    """The rule text exactly as the lane would hold it: the family's text + the cell contract."""
    row = next(r for r in doc["families"] if r["family"] == family)
    return str(row["text"]) + (str(doc["cell_contract"]) if row.get("external_cell") else "")


#: RuleSpec fields these rows need that the LIVE RuleSpec (replication_civilization.py:275-283,
#: at 677c8e58be) does not have. They arrive only with the 2026-10-14 replication-spec-book
#: RuleSpec (7db43ab66), which must be applied FIRST.
NEEDS_FIELDS = frozenset({"external_cell", "native", "peers_key"})
APPLY_ORDER = ("apply replication_spec_throughput_7db43ab66.bundle (its RuleSpec and the five "
               "builders) before passing these kwargs to RuleSpec")


def as_rulespec_kwargs(doc: dict[str, Any], rulespec_fields: Iterable[str] | None = None
                       ) -> dict[str, dict[str, Any]]:
    """{family: RuleSpec keyword arguments without `build`} -- what a wiring change passes to
    `replication_civilization.RuleSpec` together with that family's builder.

    Pass `rulespec_fields` (e.g. `dataclasses.fields(rc.RuleSpec)` names) and a RuleSpec that
    predates 7db43ab66 is refused here by name, instead of a TypeError at the call."""
    if rulespec_fields is not None:
        lacking = NEEDS_FIELDS - set(rulespec_fields)
        if lacking:
            raise SpecError(f"this RuleSpec lacks {sorted(lacking)}: {APPLY_ORDER}")
    out: dict[str, dict[str, Any]] = {}
    for row in doc["families"]:
        kw: dict[str, Any] = {"family": row["family"], "text": full_text(doc, row["family"]),
                              "defaults": dict(row["defaults"]),
                              "selector_params": bool(row["selector_params"]),
                              "external_cell": bool(row["external_cell"]),
                              "native": frozenset(row["native"])}
        if row.get("peers_key"):
            kw["peers_key"] = row["peers_key"]
        out[row["family"]] = kw
    return out


def drift(doc: dict[str, Any], root: Path = ROOT) -> dict[str, str]:
    """{family: why} for every implementation file whose git blob moved since the spec was
    written; a moved file means the text must be re-read against the code before it is trusted.
    An unreadable blob is reported, never treated as unchanged."""
    out: dict[str, str] = {}
    for row in doc["families"]:
        impl = row["implementation"]
        try:
            now = subprocess.check_output(["git", "-C", str(root), "rev-parse",
                                           f"HEAD:{impl['path']}"], text=True,
                                          stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            out[row["family"]] = f"UNMEASURED: cannot read the blob of {impl['path']}"
            continue
        if now != impl["git_blob_at_write"]:
            out[row["family"]] = (f"{impl['path']} moved {impl['git_blob_at_write'][:10]} -> "
                                  f"{now[:10]}; re-read {impl['function']} against the text")
    return out


OUT = DESK / "reports" / "REPLICATION_SPEC_ENTRIES.json"


def report(path: Path = SPEC_FILE, root: Path = ROOT) -> dict[str, Any]:
    """What the hourly leg publishes: whether the written book still validates, which families
    it holds, and which implementation moved since its spec was written. Never a verdict."""
    from datetime import UTC, datetime
    out: dict[str, Any] = {"generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                           "report_only": True, "spec_file": path.name,
                           "families_expected": list(FAMILIES)}
    try:
        doc = load(path)
    except SpecError as exc:            # our own message: names a family or a file NAME only
        return {**out, "status": "INVALID", "why": str(exc)}
    moved = drift(doc, root)
    return {**out, "status": "VALID",
            "families": [{"family": r["family"], "status": r["status"],
                          "defaults": len(r["defaults"]),
                          "certificates_at_write": r["certificates_at_write"],
                          "drift": moved.get(r["family"], "unchanged")}
                         for r in doc["families"]],
            "n_drifted": len(moved)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    rep = report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    tmp.replace(args.out)
    print(f"replication_spec_entries: {rep['status']} drifted={rep.get('n_drifted')}")
    return 0 if rep["status"] == "VALID" else 1
