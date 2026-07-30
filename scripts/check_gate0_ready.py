"""GATE 0 READINESS -- every S1 entry criterion, measured, in one artifact (launch day).

`libs/execution/staging.py:s1_entry_met` is the gate that admits real capital. It takes an
`evidence` dict and answers yes/no -- but NOTHING assembled that dict from reality, so on launch
day the honest answer to "what is actually left?" required reading five subsystems by hand.

This assembles it. Each criterion is measured against the artifact that proves it, and each
carries WHO can clear it -- because the point of launch day is to separate what the desk still
owes from what only the principal can do (fund the account, hand over keys, deposit).

    python scripts/check_gate0_ready.py            # the board
    python scripts/check_gate0_ready.py --json

DESIGN NOTE, and it is the same rule the freeze-exit gate just failed on: a criterion that cannot
be measured reads BLOCKED-UNKNOWN, never "ready". An unmeasurable criterion silently counted as
satisfied is how a gate admits capital it should not.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_OUT = _ROOT / "data/gate0_readiness.json"

#: who can clear a criterion. The split is the whole point of the board on launch day.
DESK = "desk"            # the organism can close this by working
PRINCIPAL = "principal"  # only a human with money/credentials can close this


def _row(name: str, ready: bool | None, detail: str, owner: str, artifact: str,
         action: str) -> dict[str, Any]:
    status = "READY" if ready else ("BLOCKED-UNKNOWN" if ready is None else "NOT-READY")
    return {"criterion": name, "status": status, "owner": owner, "detail": detail,
            "artifact": artifact, "action": action}


def _keys_present() -> dict[str, Any]:
    d = _ROOT / "data/secrets"
    have = sorted(p.name for p in d.glob("*")) if d.exists() else []
    live = [k for k in have if "binance" in k.lower() or "api" in k.lower()]
    return _row("keys_present", bool(live),
                f"{len(live)} live-venue credential file(s) in data/secrets" if live
                else "no live-venue credential file in data/secrets",
                PRINCIPAL, "data/secrets/", "supply the Binance spot+perp API keys")


def _connector_verified() -> dict[str, Any]:
    """Verified means a real round-trip against the venue was recorded -- not that code exists."""
    tape = _ROOT / "data/moat/execution_tape/cashcarry_trades.jsonl"
    try:
        from libs.execution.execution_tape import coverage
        cov = coverage()
        n = int(cov.get("n", 0))
    except (ImportError, OSError, ValueError, TypeError):
        return _row("connector_verified", None, "execution tape unreadable on this box",
                    DESK, str(tape), "run from the box that holds the tape")
    return _row("connector_verified", n > 0,
                f"{n} recorded fills in the execution tape" if n else "zero recorded fills",
                PRINCIPAL, str(tape.relative_to(_ROOT)),
                "fund the account and let the executor take one real round trip")


def _cfg() -> dict[str, Any] | None:
    """The LIVE executor config -- read by the keys the executor ACTUALLY consumes.

    First draft of this file read `capital_fraction` and `symbols`, neither of which exists in
    data/cashcarry_config.json. Both would have defaulted to a failing value and reported
    NOT-READY forever for a reason that was never true -- which is precisely the phantom-artifact
    defect just removed from the freeze-exit gate, reproduced one file later. The executor reads
    `top` (max concurrent carries, run_cashcarry_executor.py:1215) and `capital` (absolute USD,
    :1217); those are the keys, so those are what this measures.
    """
    try:
        return json.loads((_ROOT / "data/cashcarry_config.json").read_text("utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def _capital_fraction() -> dict[str, Any]:
    """<=10% of equity at risk. The config carries an ABSOLUTE `capital`, so the fraction is
    computed against live equity rather than read from a key that does not exist."""
    cfg = _cfg()
    if cfg is None:
        return _row("capital_fraction_le_010", None, "config unreadable",
                    DESK, "data/cashcarry_config.json", "restore data/cashcarry_config.json")
    cap = float(cfg.get("capital", 0.0))
    try:
        from libs.autodiscovery.validation import _desk_equity_usd
        eq = float(_desk_equity_usd())
    except (ImportError, OSError, ValueError, TypeError):
        eq = 0.0
    if eq <= 0:
        return _row("capital_fraction_le_010", None,
                    f"capital ${cap:,.0f} configured but live equity is unknown on this box",
                    DESK, "data/cashcarry_config.json", "run from the box that holds the NAV chain")
    frac = cap / eq
    return _row("capital_fraction_le_010", frac <= 0.10,
                f"capital ${cap:,.0f} / equity ${eq:,.0f} = {frac:.1%}",
                PRINCIPAL, "data/cashcarry_config.json",
                "" if frac <= 0.10 else
                f"Gate 0 admits <=10%; set capital <= ${eq * 0.10:,.0f} for the launch tranche")


def _symbol_count() -> dict[str, Any]:
    """Gate 0 admits 4-5 concurrent names. The executor's knob is `top`."""
    cfg = _cfg()
    if cfg is None:
        return _row("symbol_count_4_5", None, "config unreadable",
                    DESK, "data/cashcarry_config.json", "restore data/cashcarry_config.json")
    n = int(cfg.get("top", 0))
    return _row("symbol_count_4_5", 4 <= n <= 5, f"top={n} concurrent carries configured",
                PRINCIPAL, "data/cashcarry_config.json",
                "" if 4 <= n <= 5 else f"Gate 0 admits 4-5 concurrent names; top is {n}")


def _principal_signoff() -> dict[str, Any]:
    f = _ROOT / "data/gate0_signoff.json"
    return _row("principal_signoff", f.exists(),
                "signoff recorded" if f.exists() else "no signoff on file",
                PRINCIPAL, "data/gate0_signoff.json",
                "record the go/no-go decision once the rows above are green")


def _ruin_rail() -> dict[str, Any]:
    """Not an S1 criterion, but it is the thing that actually stops the book trading, and on
    2026-07-30 it was in an absorbing state that no amount of good performance could clear."""
    try:
        from libs.risk import capital_events, risk_controls
        st = json.loads((_ROOT / "data/cashcarry_state.json").read_text("utf-8"))
        raw = float(st.get("start_futures_equity", 0.0))
        eff = capital_events.effective_start_equity(raw)
        eq = float(st.get("last_combined_equity", raw))
        if eff <= 0:
            return _row("ruin_rail_clear", None, "no inception recorded yet (fresh book)",
                        DESK, "data/cashcarry_state.json", "")
        d = risk_controls.evaluate(eq, eff, max(eff, eq), 0.0, ruin_cap_lev=8.0)
        ok = d.action != "flatten"
        return _row("ruin_rail_clear", ok,
                    f"{eq / eff - 1.0:+.1%} from inception ${eff:,.0f} -> {d.action.upper()}",
                    PRINCIPAL, "data/capital_events.jsonl",
                    "" if ok else "record the funding deposit: "
                                  "scripts/record_capital_event.py --deposit <usd> --by ... ")
    except (ImportError, OSError, ValueError, TypeError, KeyError):
        return _row("ruin_rail_clear", None, "state unreadable on this box",
                    DESK, "data/cashcarry_state.json", "run from the box that holds the state")


def build() -> dict[str, Any]:
    rows = [_principal_signoff(), _capital_fraction(), _symbol_count(),
            _keys_present(), _connector_verified(), _ruin_rail()]
    blocking = [r for r in rows if r["status"] != "READY"]
    desk_owes = [r for r in blocking if r["owner"] == DESK]
    principal_owes = [r for r in blocking if r["owner"] == PRINCIPAL]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "gate": "S1 entry (Gate 0) -- libs/execution/staging.py:s1_entry_met",
        "ready": not blocking,
        "n_ready": len(rows) - len(blocking), "n_criteria": len(rows),
        "desk_owes": [r["criterion"] for r in desk_owes],
        "principal_owes": [r["criterion"] for r in principal_owes],
        "rows": rows,
        "note": "An unmeasurable criterion reads BLOCKED-UNKNOWN, never READY. A gate that counts "
                "'could not measure' as satisfied is how capital gets admitted it should not.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
        return 0
    print(f"GATE 0 READINESS: {rep['n_ready']}/{rep['n_criteria']} ready"
          + ("  -- CLEAR TO ENTER S1" if rep["ready"] else ""))
    for r in rep["rows"]:
        print(f"  {r['status']:16} [{r['owner']:9}] {r['criterion']:26} {r['detail'][:52]}")
        if r["action"]:
            print(f"  {'':16} -> {r['action'][:104]}")
    print(f"\n  desk still owes:      {rep['desk_owes'] or 'nothing'}")
    print(f"  principal still owes: {rep['principal_owes'] or 'nothing'}")
    print(f"-> {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
