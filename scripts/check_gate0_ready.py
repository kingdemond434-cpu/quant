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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_OUT = _ROOT / "data/gate0_readiness.json"

#: The executor's published book state (run_cashcarry_executor.py:43). NOT cashcarry_state.json,
#: which no organ has ever written -- see _load_state.
_STATE_REL = "data/cashcarry_positions.json"

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
        loaded: dict[str, Any] = json.loads(
            (_ROOT / "data/cashcarry_config.json").read_text("utf-8"))
        return loaded
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


def _load_state() -> tuple[dict[str, Any] | None, str]:
    """The executor's published book state, with the failure NAMED (R0333).

    This board read data/cashcarry_state.json -- a path nothing writes -- inside one broad
    `except (ImportError, OSError, ValueError, TypeError, KeyError)` that reported the single
    detail "state unreadable on this box". Every box on earth hit it, so `_ruin_rail` could
    never reach READY and the one board the desk consults on launch day had a criterion that was
    structurally unmeasurable. Absent / unparseable / schema-missing-key are now three distinct
    verdicts -- all still BLOCKED-UNKNOWN, because UNMEASURED never reads as OK.
    """
    p = _ROOT / _STATE_REL
    try:
        raw = p.read_text("utf-8")
    except FileNotFoundError:
        return None, f"absent: {_STATE_REL} has never been written on this box"
    except OSError as exc:
        return None, f"unreadable: {type(exc).__name__} on {_STATE_REL}"
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, (f"unparseable: {_STATE_REL} is not valid JSON "
                      f"(line {exc.lineno} col {exc.colno}) -- torn write, not an empty book")
    if not isinstance(loaded, dict):
        return None, f"unparseable: {_STATE_REL} holds a {type(loaded).__name__}, not an object"
    state: dict[str, Any] = loaded
    return state, "ok"


def _ruin_rail() -> dict[str, Any]:
    """Not an S1 criterion, but it is the thing that actually stops the book trading, and on
    2026-07-30 it was in an absorbing state that no amount of good performance could clear."""
    try:
        from libs.risk import capital_events, risk_controls
    except ImportError as exc:
        return _row("ruin_rail_clear", None, f"risk libraries unimportable: {exc}",
                    DESK, _STATE_REL, "run from a checkout with libs/risk importable")
    st, verdict = _load_state()
    if st is None:
        return _row("ruin_rail_clear", None, f"executor state {verdict}",
                    DESK, _STATE_REL, "run from the box that holds the executor state")
    try:
        raw = float(st["start_futures_equity"])
        # SAME RULER (R0333). `last_combined_equity` is combined futures+spot equity and
        # `peak_combined_equity` is ITS high-water mark; the old read fell back to the inception
        # for equity and passed max(eff, eq) as the peak -- an inception standing in for a peak,
        # which understates every drawdown the book has already taken. A state that publishes an
        # inception but no combined equity is UNMEASURED, not "equity == inception".
        eq = float(st["last_combined_equity"])
        peak = max(float(st.get("peak_combined_equity", raw)), raw, eq)
    except KeyError as exc:
        return _row("ruin_rail_clear", None,
                    f"schema-missing-key: {exc.args[0]!r} absent from {_STATE_REL} -- the "
                    "executor has not published this book's equity ruler yet",
                    DESK, _STATE_REL, "let the executor complete one tick on this box")
    except (TypeError, ValueError) as exc:
        return _row("ruin_rail_clear", None,
                    f"non-numeric equity in {_STATE_REL}: {exc}",
                    DESK, _STATE_REL, "restore the executor state from the live box")
    eff = float(capital_events.effective_start_equity(raw))
    if eff <= 0:
        return _row("ruin_rail_clear", None, "no inception recorded yet (fresh book)",
                    DESK, _STATE_REL, "")
    d = risk_controls.evaluate(eq, eff, peak, 0.0, ruin_cap_lev=8.0)
    ok = d.action != "flatten"
    return _row("ruin_rail_clear", ok,
                f"{eq / eff - 1.0:+.1%} from inception ${eff:,.0f} "
                f"({eq / peak - 1.0:+.1%} from peak ${peak:,.0f}) -> {d.action.upper()}",
                PRINCIPAL, "data/capital_events.jsonl",
                "" if ok else "record the funding deposit: "
                              "scripts/record_capital_event.py --deposit <usd> --by ... ")


def _net_of_fees_positive() -> dict[str, Any]:
    """Does the sleeve actually make money, net of fees, on its OWN realised fills?

    Every other Gate-0 criterion measures permission or plumbing -- keys, connector, caps, signoff.
    None would notice that the strategy loses money, which is the one fact deciding whether funding
    it is rational (L1.4 reality outranks simulation; L1.5 nothing counts until it survives real
    costs). On 2026-08-01 this gate read 5/6 READY while the desk's own tape showed every hold
    bucket negative net of fees, the worst at -712.71bps.

    STRICT: any populated bucket negative blocks. The asymmetry earns it -- a losing sleeve burns
    capital every hour it runs, while blocking a good one costs days of carry that evidence undoes.

    FAIL-CLOSED: missing or unreadable forensics reads BLOCKED-UNKNOWN, never READY.
    """
    art = "web/trade_forensics.json"
    try:
        d = json.loads((_ROOT / art).read_text("utf-8"))
        buckets = d.get("hold_buckets_net_of_fees") or {}
        if not isinstance(buckets, dict) or not buckets:
            return _row("net_of_fees_positive", None,
                        "no hold_buckets_net_of_fees in the forensics artifact", DESK, art,
                        "run scripts/run_trade_forensics.py to produce the buckets")
        pop = {k: v for k, v in buckets.items()
               if isinstance(v, dict) and int(v.get("n", 0) or 0) > 0}
        if not pop:
            return _row("net_of_fees_positive", None,
                        "no closed trades in any hold bucket -- nothing measured yet", DESK, art,
                        "accrue closes, then re-read")
        neg = {k: float(v.get("bps", 0.0)) for k, v in pop.items()
               if float(v.get("bps", 0.0)) < 0.0}
        n_tot = sum(int(v.get("n", 0)) for v in pop.values())
        if neg:
            worst = min(neg, key=lambda k: neg[k])
            return _row("net_of_fees_positive", False,
                        f"{len(neg)}/{len(pop)} hold buckets NEGATIVE net of fees over {n_tot} "
                        f"closes; worst {worst} at {neg[worst]:.2f}bps", DESK, art,
                        "the sleeve loses money net of fees on its own fills -- fix execution "
                        "cost or the edge before funding it; not a paperwork blocker")
        best = max(pop, key=lambda k: float(pop[k].get("bps", 0.0)))
        return _row("net_of_fees_positive", True,
                    f"all {len(pop)} populated buckets positive net of fees over {n_tot} closes; "
                    f"best {best} at {float(pop[best]['bps']):.2f}bps", DESK, art, "")
    except (OSError, ValueError, TypeError, KeyError):
        return _row("net_of_fees_positive", None, "forensics unreadable on this box", DESK, art,
                    "run from the box that holds the tape")


#: the soak floor. Seven days is the principal's rule (2026-08-01), and it is a FLOOR under the
#: evidence bar, not an alternative to it.
SOAK_DAYS = 7.0

#: capital events that do NOT break a clean soak. Funding the account is the act Gate 0 exists to
#: authorise -- a rule where depositing resets the principal's own soak timer would be incoherent.
#: Everything else counts as a break, including kinds added later that nobody classified here.
_BENIGN_EVENTS = {"DEPOSIT", "WITHDRAWAL", "TOPUP", "TRANSFER"}


def _soak_clean_7d() -> dict[str, Any]:
    """Seven continuous days of clean operation -- a FLOOR under the evidence bar, not a trigger.

    Gate 0 was purely evidence-based, so a lucky three-day stretch could open it; on a book taking
    ~3 closes a day that sits well inside noise. Time in testnet is NECESSARY and never sufficient,
    and the two criteria fail in opposite directions: without this floor a short run of luck
    promotes, without net_of_fees_positive a full week of losses promotes on the calendar alone.

    CLEAN means no rail event in the window. The clock RESTARTS on a dead-man fire, a kill-file
    freeze, or a recorded re-baseline -- a week the rails interrupted is not evidence the desk runs
    unattended, it is evidence of the opposite, which is the very claim promotion rests on. The
    2026-07-27 churn fire is the case in point: the book kept running while burning $1,746.

    Deposits are exempt (see _BENIGN_EVENTS). Unreadable state reads BLOCKED-UNKNOWN, never READY:
    a soak nobody can verify has not happened.
    """
    art = "data/capital_events.jsonl"
    now = datetime.now(tz=UTC)

    # A currently-latched rail means the soak has not begun at all -- check before the clock, since
    # a latch that fired seconds ago still leaves a stale "6.9d clean" reading in the ledger.
    for latch, label in ((_ROOT / "data" / "DEADMAN_FIRED", "dead-man latch"),
                         (_ROOT / "data" / "CASHCARRY_KILL", "kill-file freeze")):
        if latch.exists():
            return _row("soak_clean_7d", False,
                        f"{label} is CURRENTLY LATCHED -- the soak has not begun", DESK,
                        f"data/{latch.name}", "clear the latch, then run seven clean days")

    marks: list[tuple[str, datetime]] = []
    try:
        for ln in (_ROOT / art).read_text("utf-8").splitlines():
            if not ln.strip():
                continue
            row = json.loads(ln)
            kind = str(row.get("kind", "UNCLASSIFIED")).upper()
            if kind in _BENIGN_EVENTS:
                continue
            ts = row.get("at") or row.get("ts") or row.get("recorded")
            if ts:
                d = datetime.fromisoformat(str(ts))
                marks.append((kind, d if d.tzinfo else d.replace(tzinfo=UTC)))
    except (OSError, ValueError, TypeError) as exc:
        return _row("soak_clean_7d", None, f"capital-events ledger unreadable: {exc}", DESK, art,
                    "run from the box that holds the state")

    if not marks:
        return _row("soak_clean_7d", None, "no inception event -- the soak clock has no start",
                    DESK, art, "record a capital event to anchor the clock")

    kind, last = max(marks, key=lambda kv: kv[1])
    days = (now - last).total_seconds() / 86400.0
    return _row("soak_clean_7d", days >= SOAK_DAYS,
                f"{days:.1f}d clean since {kind} at {last.isoformat()[:16]}Z "
                f"(floor {SOAK_DAYS:.0f}d)", DESK, art,
                "" if days >= SOAK_DAYS else
                f"run clean until {(last + timedelta(days=SOAK_DAYS)).isoformat()[:16]}Z "
                f"({SOAK_DAYS - days:.1f}d left); any rail fire restarts the clock, because a week "
                "the rails interrupted is not evidence the desk runs unattended")


def build() -> dict[str, Any]:
    rows = [_principal_signoff(), _capital_fraction(), _symbol_count(),
            _keys_present(), _connector_verified(), _ruin_rail(),
            _net_of_fees_positive(), _soak_clean_7d()]
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
