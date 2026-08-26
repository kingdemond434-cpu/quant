"""FORWARD RECONCILER -- every clock is certified or retired, nothing squats (principal
2026-08-26: "shouldn't all be tested for certification and retired if the 10 gates don't work").

WHAT THE PRINCIPAL CAUGHT. The desk showed 37-41 "forward clocks" against 21 certificates and
the arithmetic never closed. Measured tonight, the gap is TWO different defects wearing one
label, and the smaller one is the honest one:

  1. ORPHANS (26 of 36 rows). `shadow_forward` enrols exactly 10 sleeves per cycle. The other 26
     rows in shadow_state.json are residue from retired experiments -- fair_value_gap,
     monday_gap, dow_effect, conditioned MACRO_FAV/FAILED_BREAK variants -- that NOTHING runs any
     more. They still read `status: ACTIVE` with frozen `days_active` and `n` (one sits at
     days=7, n=1). They are not slow clocks, they are STOPPED clocks: at day 14 the verdict rule
     would fire on a single ancient trade. A stopped clock counted as forward evidence is worse
     than no clock, because it looks like progress on the dashboard and can promote.

  2. UNCERTIFIED ENROLMENTS (5 of the 10 that do run). Grandfathered hunt6 sleeves carrying
     `gate_reason: "missing exact original universal ten-gate pass"`. They accrue real evidence
     but the admission door refuses them for ever, so the evidence can never cash. That is a
     sleeve doing work it is structurally barred from being paid for.

THE RULE THIS ENFORCES (RESEARCH §6d, the one-door law). A live forward clock must be BOTH
enrolled by a running engine AND backed by a ten-gate certificate. Anything else is retired with
its reason recorded -- not deleted, never silently. Specifically:

  * orphan (no engine enrols it)          -> RETIRED_ORPHAN
  * enrolled, no certificate, gauntlet PASS -> certificate written, clock keeps running
  * enrolled, no certificate, gauntlet FAIL -> RETIRED_GATE_FAIL, with the failing gates named
  * cannot be reconstructed exactly         -> RETIRED_UNRECONSTRUCTIBLE (never guessed:
    `shadow_admission` forbids inventing lost parameters from a display name, and a gauntlet run
    on guessed parameters certifies a strategy nobody is actually trading)

EVIDENCE IS NEVER DESTROYED. Retiring sets a status and a reason on the row; ledgers, trade
lists and day counts stay exactly as they were, so a retired row remains auditable and a future
certificate can revive it through a FRESH forward window (never by inheriting the old clock --
that clock was measured under no pre-registration).
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

SHADOW = BASE / "reports" / "shadow"
CERTS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
OUT = BASE / "data" / "forward_reconcile.json"

TERMINAL = {"KILL", "KILLED", "PROMOTED", "DEAD", "REJECTED", "RETIRED",
            "RETIRED_ORPHAN", "RETIRED_GATE_FAIL", "RETIRED_UNRECONSTRUCTIBLE",
            "QUARANTINED_UNCERTIFIED"}


def _read(p: Path) -> dict:
    try:
        v = json.loads(p.read_text("utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def enrolled_keys() -> set[str]:
    """Exactly what the running engines will touch this cycle -- the only real clocks."""
    keys: set[str] = set()
    try:
        import shadow_forward as sf
        keys |= {f"{s}.{w}" for s, w in (sf.SLEEVES + sf.certified_sleeves())}
    except Exception as exc:
        print(f"  WARN: shadow_forward enrolment unreadable ({exc}); treating its rows as enrolled")
        return set()
    # qquant/scalp own their rows; this reconciler never calls another engine's rows orphaned.
    for f in ("qquant_shadow_state.json", "scalp_shadow_state.json"):
        d = _read(SHADOW / f)
        keys |= {k for k, v in d.items() if isinstance(v, dict)}
        keys |= set((d.get("sleeves") or {}).keys())
    return keys


def certified_pairs() -> set[tuple[str, str]]:
    try:
        from shadow_admission import authorized_specs
        return {(s[0], s[1]) for s in authorized_specs(BASE)}
    except Exception as exc:
        print(f"  WARN: admission unreadable ({exc}); refusing to retire anything this pass")
        return set()


def certified_ids() -> set[str]:
    """Exact certificate identities, including qquant's non-symbol display keys.

    A qquant state key starts ``qquant.<hunt>.<cell>``; splitting it at dots and
    treating the first two fields as ``symbol.selector`` turns a valid AUDNZD
    certificate into the fictitious pair ``qquant.hunt16``.  Prefer the frozen
    certificate id before falling back to the legacy pair-shaped identity.
    """
    try:
        from gate_policy import all_ten_pass, is_exact_policy
        doc = _read(CERTS)
        if not is_exact_policy(doc.get("gate_policy")):
            return set()
        return {
            str(key) for key, row in (doc.get("survivors") or {}).items()
            if isinstance(row, dict) and all_ten_pass(row.get("gates"))
        }
    except Exception as exc:
        print(f"  WARN: exact certificate ids unreadable ({exc}); using spec identity only")
        return set()


def gauntlet(cells: list[dict]) -> dict:
    """Run the canonical ten gates on reconstructed cells. Returns {key: verdict-row}."""
    if not cells:
        return {}
    sys.path.insert(0, str(BASE.parent.parent / "desks" / "mt5" / "scripts"))
    try:
        import external_gauntlet as eg
    except Exception as exc:
        print(f"  gauntlet unavailable ({exc}); no certification attempted this pass")
        return {}
    meta = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
    built, keys = [], []
    for c in cells:
        obj = eg.build_cell(c["sym"], c["family"], c["params"], meta)
        if obj is None:
            print(f"  SKIP {c['key']}: cell would not build (missing bars or bad params)")
            continue
        built.append(obj)
        keys.append(c["key"])
    if not built:
        return {}
    res = eg.run_gauntlet(built, "forward_reconcile", meta)
    out = {}
    for key, v in zip(keys, res.get("verdicts", []), strict=False):
        out[key] = v
    return out


def main() -> int:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    enrolled = enrolled_keys()
    certs = certified_pairs()
    cert_ids = certified_ids()
    if not certs:
        print("forward reconcile: admission unreadable -- FAIL SOFT, nothing changed")
        return 0

    actions: list[dict] = []
    to_gauntlet: list[dict] = []
    try:
        from shadow_forward import WINDOWS
    except Exception:
        WINDOWS = {}

    for fname in ("shadow_state.json", "qquant_shadow_state.json", "scalp_shadow_state.json"):
        path = SHADOW / fname
        data = _read(path)
        if not data:
            continue
        changed = False
        for key, row in data.items():
            if not isinstance(row, dict) or "status" not in row:
                continue
            if str(row.get("status") or "").upper() in TERMINAL:
                continue
            parts = key.split(".")
            sym, sel = parts[0], (parts[1] if len(parts) > 1 else "")
            certificate_id = str(row.get("certificate") or key)
            has_cert = certificate_id in cert_ids or any(
                sym == a and (sel == b or not sel) for a, b in certs
            )

            if enrolled and key not in enrolled:
                row["status"] = "RETIRED_ORPHAN"
                row["retired_at"] = now
                row["retire_reason"] = (
                    "no engine enrols this row; its day count and trade count are FROZEN. A "
                    "stopped clock counted as forward evidence would take a day-14 verdict on "
                    "stale trades. Evidence preserved; revive only through a fresh certificate "
                    "and a new pre-registered window.")
                actions.append({"key": key, "action": "RETIRED_ORPHAN"})
                changed = True
                continue

            if has_cert:
                continue

            # enrolled, running, no certificate -> it must face the gauntlet
            if sel in WINDOWS and len(parts) == 2:
                to_gauntlet.append({"key": key, "sym": sym, "family": "session_range_breakout",
                                    "params": dict(WINDOWS[sel]), "file": fname})
            else:
                row["status"] = "RETIRED_UNRECONSTRUCTIBLE"
                row["retired_at"] = now
                row["retire_reason"] = (
                    "running without a ten-gate certificate, and its exact parameters cannot be "
                    "reconstructed from the cell name. Guessing them is forbidden -- a gauntlet "
                    "run on guessed parameters certifies a strategy nobody is trading.")
                actions.append({"key": key, "action": "RETIRED_UNRECONSTRUCTIBLE"})
                changed = True
        if changed:
            path.write_text(json.dumps(data, indent=2), "utf-8")

    # --- certify or retire the reconstructible ones -------------------------------------------
    verdicts = gauntlet(to_gauntlet)
    if verdicts:
        doc = _read(CERTS)
        survivors = doc.get("survivors") or {}
        n_before = len(survivors)
        from gate_policy import ATTESTATION
        for spec in to_gauntlet:
            key = spec["key"]
            v = verdicts.get(key)
            path = SHADOW / spec["file"]
            data = _read(path)
            row = data.get(key)
            if v is None:
                continue
            if v.get("passed"):
                survivors[f"reconciled.{key}"] = {
                    "hunt": "forward_reconcile", "cell": key, "sym": spec["sym"],
                    "days": v.get("days"), "gates": v.get("stages"), "gated_at": now,
                    "shadow_spec": {"symbol": spec["sym"], "selector": key.split(".")[1],
                                    "family": "session_range_breakout", "is_universe": True,
                                    "hunt": "forward_reconcile", "condition": None},
                }
                actions.append({"key": key, "action": "CERTIFIED"})
                if isinstance(row, dict):
                    row.pop("gate_reason", None)
                    row["certified_at"] = now
            else:
                failed = [g for g, s in (v.get("stages") or {}).items()
                          if not (isinstance(s, dict) and s.get("passed") is True)]
                if isinstance(row, dict):
                    row["status"] = "RETIRED_GATE_FAIL"
                    row["retired_at"] = now
                    row["retire_reason"] = (
                        f"ran the canonical ten gates and failed: {', '.join(failed)}. Evidence "
                        f"preserved; a sleeve that cannot clear the one door does not hold a "
                        f"forward slot.")
                actions.append({"key": key, "action": "RETIRED_GATE_FAIL", "failed": failed})
            if isinstance(row, dict):
                path.write_text(json.dumps(data, indent=2), "utf-8")
        if len(survivors) > n_before:
            doc.update({"n": len(survivors), "gate_policy": ATTESTATION, "survivors": survivors,
                        "swept_at": now})
            CERTS.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
            CANON.write_text(json.dumps(doc, indent=2, default=str), "utf-8")

    OUT.write_text(json.dumps(
        {"checked_at": now, "enrolled": len(enrolled),
         "certified_pairs": len(certs), "actions": actions}, indent=1), "utf-8")
    counts: dict[str, int] = {}
    for a in actions:
        counts[a["action"]] = counts.get(a["action"], 0) + 1
    print(f"forward reconcile: {len(actions)} action(s) {counts or '{}'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
