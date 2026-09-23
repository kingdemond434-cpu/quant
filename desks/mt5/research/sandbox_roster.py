"""THE SANDBOX ROSTER -- one generated table that answers "are they all there and working".

Every federated system the desk knows, in one row each: the 123 seeds of
`libs/research/external_federation.SEEDS`, the 58 adapters of `libs/research/adapters.SPECS`, and
the desk's own REBUILT cells under `research/sandboxes/`. Nothing here is hand-written and
nothing is asserted -- every column is read from the artifact that owns it:

  disposition       DIRECT / WRAPPED / REBUILT from the roster row, with the licence reading's
                    verdict when `licence_reader` has read one (REJECTED_WITH_EVIDENCE keeps its
                    evidence string); ADAPTER_ONLY for an adapter with no seed row.
  licence           `data/external_federation.json` where a reading landed, UNVERIFIED with the
                    expected id otherwise. Never asserted from memory (LAWS 5h).
  capability family `adapters.FAMILY_OF` / the cell's own CAPABILITY_FAMILY.
  runs here         the install ledger (`data/sandbox_install_ledger.json`): INSTALLED means the
                    module IMPORTED in the shared venv; PERMANENTLY_UNAVAILABLE carries the exact
                    pip error and the cover that took over the capability.
  last run          `data/sandbox_runner_state.json` -- the run the rotation actually gave it,
                    with its age, so a dark system is visible by name.
  produced          runs, candidates, information gain and the last packet's status.
  breadth           marginal independent breadth from `sandbox_rotation.breadth`: the drop in the
                    federation's effective rank when this system's donated cells are removed.

ARTIFACT `reports/SANDBOX_ROSTER.json`, rendered to `docs/research/SANDBOX_ROSTER.md` (DERIVED --
never edit the Markdown). CONSUMERS: `scripts/check_sandbox_liveness.py` (names the dark and the
stalled), `research/federation_ops.py`, and any session asking whether the federation is real.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import adapters as A  # noqa: E402
from libs.research import external_federation as fed  # noqa: E402
from libs.research import sandbox_rotation as ROT  # noqa: E402
from research import sandboxes as CELLS  # noqa: E402

GENERATOR = "sandbox_roster"
REPORT = DESK / "reports" / "SANDBOX_ROSTER.json"
MARKDOWN = ROOT / "docs" / "research" / "SANDBOX_ROSTER.md"
RUNNER_STATE = DESK / "data" / "sandbox_runner_state.json"
RUNNER_REPORT = DESK / "reports" / "SANDBOX_RUNNER.json"
INSTALL_LEDGER = DESK / "data" / "sandbox_install_ledger.json"
FED_STATE = DESK / "data" / "external_federation.json"
LAW = ("LAWS 5h: every federated system is named with its disposition, its licence as READ, and "
       "what it actually produced. A system nobody can name is a system nobody can check.")


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _age_h(last_at: Any) -> float | None:
    age = ROT.age_s(last_at)
    return None if age == float("inf") else round(age / 3600.0, 2)


def cell_rows() -> dict[str, dict[str, Any]]:
    """The desk's own REBUILT cells: they are federation members, not a footnote."""
    out: dict[str, dict[str, Any]] = {}
    for name in CELLS.CELLS:
        sid = CELLS.system_id(name)
        try:
            module = CELLS.load_cell(name)
        except Exception as exc:
            out[sid] = {"system_id": sid, "name": name, "kind": "cell",
                        "disposition": "REBUILT", "licence": "desk (own code)",
                        "capability_family": "UNMEASURED", "upstream": "desk",
                        "runs_here": False,
                        "why": f"cell import failed: {type(exc).__name__}: {exc}"[:200]}
            continue
        d = CELLS.describe(module)
        out[sid] = {"system_id": sid, "name": name, "kind": "cell", "disposition": "REBUILT",
                    "licence": d.get("licence") or "desk (own code)",
                    "capability_family": d.get("capability_family") or "UNMEASURED",
                    "upstream": ", ".join(d.get("upstream") or []) or "desk",
                    "requirement": "", "weight": "light", "runs_here": True,
                    "why": f"desk code; fallback: {d.get('fallback')}",
                    "yields": ["candidates", "representations"]}
    return out


def build(*, state_path: Path = RUNNER_STATE, report_path: Path = RUNNER_REPORT,
          ledger_path: Path = INSTALL_LEDGER, fed_state_path: Path = FED_STATE
          ) -> dict[str, Any]:
    state = _read(state_path, {}) or {}
    rows_state = {str(k): v for k, v in (state.get("systems") or {}).items()
                  if isinstance(v, dict)}
    runner = _read(report_path, {}) or {}
    ledger = {str(k): v for k, v in ((_read(ledger_path, {}) or {}).get("systems") or {}).items()
              if isinstance(v, dict)}
    fed_rows = {str(k): v for k, v in ((_read(fed_state_path, {}) or {}).get("systems")
                                       or {}).items() if isinstance(v, dict)}
    planned = {str(r.get("system_id")): r for r in (runner.get("systems_tried") or [])
               if isinstance(r, dict) and r.get("system_id")}
    b = ROT.breadth(ROT.cells_of(rows_state))
    marginal = b["marginal"]

    rows: dict[str, dict[str, Any]] = {}
    for sid, seed in fed.SEED_BY_ID.items():
        spec = A.SPECS.get(sid)
        row = fed_rows.get(sid) or {}
        licence = str(row.get("licence") or seed.licence or "UNVERIFIED")
        expected = A.LICENCE_EXPECTED.get(sid, "UNVERIFIED")
        rows[sid] = {
            "system_id": sid, "name": seed.name, "kind": "adapter" if spec else "seed",
            "upstream": seed.upstream, "role": seed.role,
            "disposition": str(row.get("disposition") or seed.integration),
            "disposition_why": str(row.get("why") or seed.notes or ""),
            "licence": licence,
            "licence_basis": str(row.get("licence_basis") or ""),
            "licence_expected": expected,
            "capability_family": A.FAMILY_OF.get(sid, "") or (seed.capabilities[0]
                                                              if seed.capabilities else ""),
            "capabilities": list(seed.capabilities), "region": seed.region,
            "requirement": spec.requirement if spec else "",
            "weight": spec.weight if spec else "",
            "yields": list(spec.yields) if spec else [],
            "has_adapter": spec is not None,
        }
    for sid, spec in A.SPECS.items():
        rows.setdefault(sid, {
            "system_id": sid, "name": sid, "kind": "adapter", "upstream": f"public:{sid}",
            "role": "adapter-only system", "disposition": "ADAPTER_ONLY",
            "disposition_why": "an adapter with no roster seed row", "licence": "UNVERIFIED",
            "licence_basis": "", "licence_expected": A.LICENCE_EXPECTED.get(sid, "UNVERIFIED"),
            "capability_family": A.FAMILY_OF.get(sid, ""), "capabilities": [],
            "region": "global", "requirement": spec.requirement, "weight": spec.weight,
            "yields": list(spec.yields), "has_adapter": True})
    rows.update({sid: {**rows.get(sid, {}), **row} for sid, row in cell_rows().items()})

    for sid, row in rows.items():
        inst = ledger.get(sid) or {}
        st = rows_state.get(sid) or {}
        plan_row = planned.get(sid) or {}
        install_status = str(inst.get("status") or ("N/A" if row.get("kind") == "cell"
                                                    else "NOT_ATTEMPTED"))
        runs_here = bool(row.get("runs_here")) or install_status == "INSTALLED" \
            or str(plan_row.get("status") or "") == "RUNNABLE"
        row.update({
            "install_status": install_status,
            "install_version": str(inst.get("version") or ""),
            "install_error": str(inst.get("error") or "")[:400],
            "install_why": str(inst.get("why") or ""),
            "cover": str(inst.get("cover") or ""),
            "planned_status": str(plan_row.get("status") or "NOT_PLANNED"),
            "planned_why": str(plan_row.get("why") or "")[:240],
            "runs_here": runs_here,
            "runs": int(st.get("runs") or 0),
            "last_run_at": st.get("last_at"),
            "last_run_age_h": _age_h(st.get("last_at")),
            "last_status": str(st.get("last_status") or "NEVER_RUN"),
            "candidates": int(st.get("candidates") or 0),
            "information_gain": float(st.get("information_gain") or 0.0),
            "compute_spent_s": float(st.get("compute_spent") or 0.0),
            "roi": st.get("roi"),
            "n_cells": len(st.get("cells") or []),
            "breadth_marginal": float(marginal.get(sid, 0.0)),
            "produced": bool(int(st.get("candidates") or 0)
                             or float(st.get("information_gain") or 0.0) > 0),
        })
        #: A ROSTER SEED WITH NO ADAPTER IS THE OTHER HALF OF "are they all there". It is not
        #: refused, not unavailable and not idle -- there is simply no code that can run it yet,
        #: and saying so by name is the whole point of a generated table. Never silent.
        if row.get("kind") not in ("cell",) and not row.get("has_adapter"):
            row["needs_adapter"] = True
            row["planned_why"] = (
                f"NO ADAPTER: libs/research/adapters/{sid}.py does not exist, so nothing can "
                f"run this seed. The task is to write the adapter (run(bundle) -> "
                f"ExternalResearchPacket) and pin its requirement in adapters.SPECS")
        else:
            row["needs_adapter"] = False
    ordered = sorted(rows.values(), key=lambda r: (not r["runs_here"],
                                                   -float(r["breadth_marginal"]),
                                                   -int(r["candidates"]), r["system_id"]))
    counts = {
        "seeds": len(fed.SEED_BY_ID), "adapters": len(A.SPECS), "cells": len(CELLS.CELLS),
        "rows": len(ordered),
        "runs_here": sum(1 for r in ordered if r["runs_here"]),
        "produced": sum(1 for r in ordered if r["produced"]),
        "ever_ran": sum(1 for r in ordered if r["runs"] > 0),
        "installed": sum(1 for r in ordered if r["install_status"] == "INSTALLED"),
        "permanently_unavailable": sum(1 for r in ordered
                                       if r["install_status"] == "PERMANENTLY_UNAVAILABLE"),
        "no_distribution_pinned": sum(1 for r in ordered
                                      if r["install_status"] == "NO_DISTRIBUTION_PINNED"),
        "not_attempted": sum(1 for r in ordered if r["install_status"] == "NOT_ATTEMPTED"),
        "licence_read": sum(1 for r in ordered
                            if r["licence"] not in ("UNVERIFIED", "", "UNMEASURED")),
        "candidates_total": sum(int(r["candidates"]) for r in ordered),
        "needs_adapter": sum(1 for r in ordered if r.get("needs_adapter")),
    }
    by_disposition: dict[str, int] = {}
    for r in ordered:
        key = str(r["disposition"])
        by_disposition[key] = by_disposition.get(key, 0) + 1
    return {
        "at": now(), "generator": GENERATOR, "law": LAW, "counts": counts,
        "by_disposition": dict(sorted(by_disposition.items())),
        "breadth": {"total_effective_rank": b["total"], "columns": b["columns"],
                    "basis": b["basis"]},
        "rotation": {k: v for k, v in (runner.get("rotation") or {}).items()
                     if k in ("window_s", "scouts", "n_scout_slots", "scout_budget_s",
                              "exploit_budget_s", "rule")},
        "systems": ordered,
        "rule": ("every seed, every adapter and every cell has a row; every column is read from "
                 "the artifact that owns it; a system that runs nowhere says why and names what "
                 "covers its capability"),
    }


def render(doc: dict[str, Any]) -> str:
    c = doc["counts"]
    lines = [
        "# SANDBOX ROSTER -- every federated system, generated",
        "",
        "> DERIVED ARTIFACT. Generated by `desks/mt5/research/sandbox_roster.py` from",
        "> `reports/SANDBOX_ROSTER.json`. Never edit this file: edit the organs that write the",
        "> artifacts it reads.",
        "",
        f"Generated {doc['at']}. {c['rows']} rows: {c['seeds']} roster seeds, {c['adapters']} "
        f"adapters, {c['cells']} rebuilt cells.",
        "",
        f"- **Runs on this host:** {c['runs_here']} / {c['rows']}",
        f"- **Has ever run:** {c['ever_ran']}  |  **has produced:** {c['produced']}  |  "
        f"**candidates donated:** {c['candidates_total']}",
        f"- **Library installed and imported:** {c['installed']}  |  "
        f"**permanently unavailable (with evidence):** {c['permanently_unavailable']}  |  "
        f"**no wheel pinned:** {c['no_distribution_pinned']}  |  "
        f"**not yet attempted:** {c['not_attempted']}",
        f"- **Licence read at a pin:** {c['licence_read']} / {c['rows']}",
        f"- **Roster seeds still waiting for an adapter:** {c['needs_adapter']} (named in the "
        f"table; nothing can run them until one exists)",
        f"- **Federation effective rank (independent cells spanned):** "
        f"{doc['breadth']['total_effective_rank']} over {doc['breadth']['columns']} cells",
        "",
        "Disposition census: "
        + ", ".join(f"{k} {v}" for k, v in doc["by_disposition"].items()),
        "",
        "## Every system",
        "",
        "| system | disposition | licence | capability family | runs here | last run (h) | "
        "runs | candidates | breadth | status / why |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in doc["systems"]:
        why = (r.get("install_why") or r.get("planned_why") or r.get("disposition_why") or "")
        if r.get("install_status") == "PERMANENTLY_UNAVAILABLE":
            why = f"{why} -- covered by: {r.get('cover')}"
        age = r["last_run_age_h"]
        lines.append(
            f"| `{r['system_id']}` | {r['disposition']} | {r['licence']} | "
            f"{r['capability_family'] or '-'} | {'yes' if r['runs_here'] else 'NO'} | "
            f"{age if age is not None else '-'} | {r['runs']} | {r['candidates']} | "
            f"{r['breadth_marginal']:.3f} | {r['last_status']}: "
            f"{str(why)[:150].replace('|', '/')} |")
    lines += ["", "## What each column means", "",
              "- **disposition** -- DIRECT/WRAPPED run upstream code in the sandbox; REBUILT "
              "reproduces the mechanism in desk code; REJECTED_WITH_EVIDENCE carries the "
              "licence reading that refused it; ADAPTER_ONLY is an adapter with no seed row.",
              "- **runs here** -- the module imported in the shared sandbox venv, or the system "
              "is desk code. NO is never silent: the status column names the exact reason.",
              "- **breadth** -- marginal independent breadth: how much of the federation's "
              "effective rank disappears if this system stops donating (participation ratio of "
              "the system x cell indicator matrix).",
              "- **last run (h)** -- hours since the rotation last gave it the hour; `-` means "
              "it has never run. `scripts/check_sandbox_liveness.py` fails on any runnable "
              "system past its rotation window.", ""]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--render", action="store_true", help="also write the Markdown view")
    a = ap.parse_args(argv)
    doc = build()
    if not a.dry_run:
        _write(REPORT, doc)
        MARKDOWN.parent.mkdir(parents=True, exist_ok=True)
        MARKDOWN.write_text(render(doc), encoding="utf-8")
    c = doc["counts"]
    print(f"sandbox roster: {c['rows']} rows | runs here {c['runs_here']} | ever ran "
          f"{c['ever_ran']} | produced {c['produced']} | installed {c['installed']} | "
          f"permanent {c['permanently_unavailable']} | licence read {c['licence_read']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
