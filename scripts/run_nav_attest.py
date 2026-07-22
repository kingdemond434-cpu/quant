"""Daily NAV attestation -- an allocator-grade, tamper-evident track record from inception.

Appends one hash-chained line per UTC day to data/nav_attestation.jsonl: each record embeds the
SHA-256 of the previous record, and the file is committed by the daily git snapshot (pushed to
GitHub), so any later edit breaks the chain AND the git history. Self-reported spreadsheets are
worth nothing in allocator diligence; a hash-chained series with third-party (GitHub) timestamps
from day 1 is the cheapest credible track record a solo desk can build -- and it cannot be
started retroactively, which is why it runs NOW, on paper equity, for continuity through go-live.

Reads only existing state files; writes only its own artifact. Freeze-safe.

    python scripts/run_nav_attest.py
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

_OUT = Path("data/nav_attestation.jsonl")
_POS = Path("data/cashcarry_positions.json")
_LIVE = Path("data/live_combined_state.json")


def _book() -> tuple[float, int, float, float]:
    """(deployed_notional, n_carries, realized_spot_pnl, start_futures_equity) from state."""
    st = json.loads(_POS.read_text("utf-8"))
    pos = st.get("positions", {})
    dep = sum(float(p["spot_qty"]) * float(p["spot_cost"]) for p in pos.values())
    return (round(dep, 2), len(pos), round(float(st.get("realized_spot_pnl", 0.0)), 2),
            round(float(st.get("start_futures_equity", 0.0)), 2))


def _equity() -> float | None:
    """Combined marked equity from the molded feed (venue-truth lives in the deadman's file)."""
    try:
        d = json.loads(_LIVE.read_text("utf-8"))
        mc = d.get("mcurve") or []
        return round(float(mc[-1][1]), 2) if mc else None
    except (OSError, json.JSONDecodeError, IndexError, TypeError, ValueError):
        return None


def main() -> None:
    today = datetime.now(tz=UTC).date().isoformat()
    prev_hash = "GENESIS"
    if _OUT.exists():
        lines = _OUT.read_text("utf-8").strip().splitlines()
        if lines:
            last = json.loads(lines[-1])
            if last.get("date") == today:
                print(f"nav-attest: {today} already recorded")
                return
            prev_hash = hashlib.sha256(lines[-1].encode("utf-8")).hexdigest()
    dep, n, rsp, seq = _book()
    rec = {
        "date": today,
        "ts": datetime.now(tz=UTC).isoformat(),
        "equity_marked": _equity(),
        "deployed_notional": dep,
        "n_carries": n,
        "realized_spot_pnl": rsp,
        "start_futures_equity": seq,
        "mode": "PAPER (testnet) -- pre-Gate-0",
        "prev_sha256": prev_hash,
    }
    with _OUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    print(f"nav-attest: {today} equity={rec['equity_marked']} deployed=${dep} "
          f"chain={prev_hash[:12]}..")


if __name__ == "__main__":
    main()
