#!/usr/bin/env python3
"""THE PRINCIPAL'S EXPERIMENTS, IN THEIR OWN LEDGER AND THEIR OWN BUDGET (Tier-1 audit #18).

THE PRINCIPAL: "Separate human/principal experiments into an explicitly labelled experimental
budget with its own ledger; never rewrite certificate/admission rules for a desired trade."

WHERE PRINCIPAL EXPERIMENTS LIVE TODAY, measured 2026-09-29:
  * data/sleeves.json -- twelve rows carry a `principal_override` block (by, why, sometimes a
    `reverts_if`): the three XAUUSD scalp sleeves admitted on a corrected Sharpe, and nine extra
    gold brackets (asia/london_am/afternoon v2..v4) that are second copies of the same signal.
    Six of them are LIVE at 0.5882% heat each, inside the institutional book, sized by the same
    allocator as certified sleeves and indistinguishable from them in every heat total.
  * code -- `PRINCIPAL OVERRIDE` blocks in organ source (pf_allocator's plausibility fence,
    certificate_truth's protection of override symbols). A rule rewritten for a desired trade
    is exactly what the item forbids, so each is LISTED here with whether it sits on a
    certificate/admission path.
  * data/live_sleeve_policy.json -- the principal's live-account policy (LAWS 5j), when present.

WHAT THIS ORGAN DOES, every hour:
  1. the EXPERIMENTAL SLEEVE LEDGER: data/experimental_ledger.jsonl, append-only, one row each
     time an override row APPEARS, CHANGES (content hash) or is REMOVED -- so the history of what
     the principal put into the book, and when, survives the row being edited or deleted;
  2. the BUDGET ACCOUNTING: experimental heat (LIVE override rows) against institutional heat,
     realised live R per experimental sleeve, and the declared budget from
     data/experimental_budget.json (`{"max_heat": ..., "by": ..., "at": ...}`). With no declared
     budget the budget reads UNDECLARED -- a number only the principal can set -- and the usage
     is still measured;
  3. the SEPARATED BOOK, AS A SHADOW: the institutional book with the experimental rows taken
     out. `SEPARATE_EXPERIMENTAL_BOOK = False`: nothing reads it. Moving the override sleeves out
     of the institutional book changes what the allocator funds, so it is NEEDS-PRINCIPAL-GO.

    -> reports/EXPERIMENTAL_BUDGET.json

    python desks/mt5/research/experimental_budget.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent

SLEEVES = DESK / "data" / "sleeves.json"
LEDGER = DESK / "data" / "live_ledger.jsonl"
BUDGET = DESK / "data" / "experimental_budget.json"
POLICY = DESK / "data" / "live_sleeve_policy.json"
EXP_LEDGER = DESK / "data" / "experimental_ledger.jsonl"
OUT = DESK / "reports" / "EXPERIMENTAL_BUDGET.json"
#: Source roots scanned for code-level principal overrides.
CODE_ROOTS = (DESK / "research", DESK / "mt5desk", ROOT / "libs")
#: Files on the certificate / admission / sizing path: an override here is a rule rewritten.
RULE_PATH = ("promoter", "universal_gate", "gate_policy", "decision_core", "live_policy",
             "certificate_truth", "pf_allocator", "state_admission", "heat_policy", "gateway")
_MARK = re.compile(r"PRINCIPAL OVERRIDE", re.IGNORECASE)

#: THE SWITCH. Off: the separated book is published and fed nowhere.
SEPARATE_EXPERIMENTAL_BOOK = False


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _rows() -> list[dict[str, Any]]:
    doc = _read(SLEEVES)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    return [r for r in rows or [] if isinstance(r, dict) and r.get("name")]


def _hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _heat(r: dict[str, Any]) -> float:
    try:
        v = float(r.get("risk_frac") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return v if str(r.get("status", "")).upper() == "LIVE" else 0.0


def _last_state(path: Path) -> dict[str, str]:
    """name -> content hash as the ledger last recorded it (REMOVED rows drop out)."""
    state: dict[str, str] = {}
    try:
        lines = path.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return state
    for ln in lines:
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(d, dict) or not d.get("sleeve"):
            continue
        if d.get("event") == "REMOVED":
            state.pop(str(d["sleeve"]), None)
        else:
            state[str(d["sleeve"])] = str(d.get("hash") or "")
    return state


def ledger_events(rows: list[dict[str, Any]], prev: dict[str, str],
                  now: datetime) -> list[dict[str, Any]]:
    """The transitions since the ledger's last recorded state. Pure."""
    at = now.isoformat(timespec="seconds")
    cur = {str(r["name"]): r for r in rows if r.get("principal_override")}
    out: list[dict[str, Any]] = []
    for name, r in sorted(cur.items()):
        h = _hash({"override": r.get("principal_override"), "status": r.get("status"),
                   "risk_frac": r.get("risk_frac")})
        if name not in prev or prev[name] != h:
            out.append({"at": at, "event": "APPEARED" if name not in prev else "CHANGED",
                        "sleeve": name, "hash": h, "status": r.get("status"),
                        "risk_frac": r.get("risk_frac"), "symbol": r.get("symbol"),
                        "certificate": r.get("certificate"),
                        "override": r.get("principal_override")})
    for name in sorted(set(prev) - set(cur)):
        out.append({"at": at, "event": "REMOVED", "sleeve": name, "hash": "",
                    "why": "the row no longer carries a principal_override (or is gone)"})
    return out


def realised_by_sleeve() -> dict[str, dict[str, float]]:
    acc: dict[str, list[float]] = defaultdict(list)
    try:
        lines = LEDGER.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    for ln in lines:
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        r = d.get("r_multiple") if isinstance(d, dict) else None
        if isinstance(r, (int, float)) and d.get("sleeve"):
            acc[str(d["sleeve"])].append(float(r))
    return {k: {"n": len(v), "sum_r": round(sum(v), 4), "mean_r": round(sum(v) / len(v), 4)}
            for k, v in acc.items()}


def code_overrides() -> list[dict[str, Any]]:
    """Every `PRINCIPAL OVERRIDE` block in organ source, and whether it sits on a rule path."""
    out: list[dict[str, Any]] = []
    for root in CODE_ROOTS:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.py")):
            if "tests" in p.parts or p.name == Path(__file__).name:
                continue
            try:
                lines = p.read_text("utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for i, ln in enumerate(lines, 1):
                if _MARK.search(ln) and ln.lstrip().startswith("#"):
                    out.append({"file": str(p.relative_to(ROOT)).replace("\\", "/"), "line": i,
                                "text": ln.strip()[:200],
                                "on_rule_path": any(k in p.stem for k in RULE_PATH)})
    return out


def build(now: datetime | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    now = now or datetime.now(tz=UTC)
    rows = _rows()
    exp = [r for r in rows if r.get("principal_override")]
    inst = [r for r in rows if not r.get("principal_override")]
    events = ledger_events(rows, _last_state(EXP_LEDGER), now)
    real = realised_by_sleeve()
    exp_heat = sum(_heat(r) for r in exp)
    inst_heat = sum(_heat(r) for r in inst)
    budget_doc = _read(BUDGET)
    max_heat = None
    if isinstance(budget_doc, dict):
        try:
            max_heat = float(budget_doc["max_heat"])
        except (KeyError, TypeError, ValueError):
            max_heat = None
    policy = _read(POLICY)
    code = code_overrides()
    sleeves = []
    for r in exp:
        ov = r.get("principal_override") or {}
        sleeves.append({
            "sleeve": r["name"], "symbol": r.get("symbol"), "status": r.get("status"),
            "heat": round(_heat(r), 6), "certificate": r.get("certificate"),
            "certified": bool(r.get("certificate")) and r.get("certificate") != "forward_clock",
            "by": ov.get("by") if isinstance(ov, dict) else None,
            "why": (str(ov.get("why"))[:300] if isinstance(ov, dict) and ov.get("why") else None),
            "reverts_if": ov.get("reverts_if") if isinstance(ov, dict) else None,
            "realised_live": real.get(str(r["name"])) or {"n": 0, "why": "no live deal yet"}})
    exp_real = [v for s in sleeves for v in [s["realised_live"]] if v.get("n")]
    n_exp_deals = sum(int(v["n"]) for v in exp_real)
    doc = {
        "at": now.isoformat(timespec="seconds"),
        "status": "MEASURED" if rows else "UNMEASURED",
        "why": (f"{len(exp)} principal-override sleeve(s) of {len(rows)}" if rows else
                f"{SLEEVES.relative_to(ROOT)} unreadable"),
        "budget": {
            "declared_max_heat": max_heat,
            "declared_by": budget_doc.get("by") if isinstance(budget_doc, dict) else None,
            "status": ("UNDECLARED" if max_heat is None else
                       "OVER" if exp_heat > max_heat + 1e-9 else "WITHIN"),
            "why": (f"no {BUDGET.relative_to(ROOT)}: the experimental budget is a number only "
                    "the principal can set; usage is measured regardless" if max_heat is None
                    else f"experimental heat {exp_heat:.4%} vs declared {max_heat:.4%}"),
        },
        "usage": {
            "experimental_heat": round(exp_heat, 6),
            "institutional_heat": round(inst_heat, 6),
            "experimental_share_of_live_heat": (round(exp_heat / (exp_heat + inst_heat), 4)
                                                if exp_heat + inst_heat > 0 else None),
            "n_experimental": len(exp),
            "n_experimental_live": sum(1 for r in exp if _heat(r) > 0),
            "n_experimental_certified": sum(1 for s in sleeves if s["certified"]),
            "experimental_live_deals": n_exp_deals,
            "experimental_realised_r": round(sum(float(v["sum_r"]) for v in exp_real), 4),
        },
        "sleeves": sleeves,
        "ledger": {"path": str(EXP_LEDGER.relative_to(ROOT)), "new_events": len(events),
                   "rule": "append-only: APPEARED / CHANGED (content hash) / REMOVED"},
        "code_overrides": {"n": len(code), "n_on_rule_path": sum(1 for c in code
                                                                if c["on_rule_path"]),
                           "rows": code,
                           "rule": ("the item forbids rewriting certificate/admission rules for a "
                                    "desired trade; each block is listed so the principal can see "
                                    "which rules carry an override and move it into this budget")},
        "live_sleeve_policy": ({"present": True, "keys": sorted(policy)[:20]}
                               if isinstance(policy, dict) else
                               {"present": False, "why": "no live_sleeve_policy.json on this "
                                                         "host; the gateway's fallback applies"}),
        "separated_book_shadow": {
            "feeds_live": SEPARATE_EXPERIMENTAL_BOOK,
            "institutional_book": {str(r["name"]): round(_heat(r), 6) for r in inst
                                   if _heat(r) > 0},
            "experimental_book": {str(r["name"]): round(_heat(r), 6) for r in exp
                                  if _heat(r) > 0},
            "why": ("moving the override sleeves out of the institutional book changes what the "
                    "allocator funds and how the heat law is filled: NEEDS-PRINCIPAL-GO. Set "
                    "SEPARATE_EXPERIMENTAL_BOOK only on the principal's explicit yes"),
        },
    }
    return doc, events


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    doc, events = build()
    if not args.dry_run:
        if events:
            EXP_LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with EXP_LEDGER.open("a", encoding="utf-8") as fh:
                for e in events:
                    fh.write(json.dumps(e, default=str) + "\n")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
    u = doc.get("usage") or {}
    print(f"experimental_budget: {doc['status']} -- {u.get('n_experimental')} experimental "
          f"sleeve(s), heat {u.get('experimental_heat')} vs institutional "
          f"{u.get('institutional_heat')}; budget {doc['budget']['status']}; "
          f"{len(events)} ledger event(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
