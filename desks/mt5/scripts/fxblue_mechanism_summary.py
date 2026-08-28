"""Summarise the FX Blue track-record corpus into MECHANISM structure (RESEARCH §4).

WHAT THIS IS AND IS NOT. The population is maximally survivorship-biased and self-selected
(§4, master 23), so NOTHING here is evidence of an edge and no output may be read as one.
Two different kinds of statement are produced and they are kept apart on purpose:

  ACTIVITY (defensible): when and what this population TRADES. Survivorship selects which
    accounts remain visible; it does not manufacture the clock or the instrument mix of
    retail MT5 flow. This is a positioning/flow prior and is the useful half.

  PERFORMANCE (hypothesis-only): where this population MAKES money. Conditioned on survival,
    so it is a pointer at a mechanism to preregister, never a measured edge. Reported with
    the survivor share alongside so the bias is never invisible.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SRC = BASE / "data" / "intelligence" / "fxblue" / "track_records.jsonl"


def main() -> int:
    # READ EVERY WAVE, AND RE-DERIVE LIVENESS FROM CONTENT (repair 2026-08-28).
    # This consumer read ONE file and filtered on `status == "has_data"`. The first-generation
    # harvest predates that vocabulary and labels the same records `live`, so the summary
    # printed `n=0 accounts` over a corpus of 120 -- and reported it as a result rather than as
    # an unreadable input. The producer's distinction is honoured by RE-COMPUTING it: a record
    # is mineable iff some mechanism chart carries a non-zero number, which is what the miner
    # itself means by has_data. A stored label is never trusted over the data behind it.
    if len(sys.argv) > 1:
        paths = [Path(a) for a in sys.argv[1:]]
    else:
        paths = sorted(SRC.parent.glob("track_records*.jsonl"))
    recs = []
    seen: set[str] = set()
    for path in paths:
        for ln in path.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            r = json.loads(ln)
            key = str(r.get("user", ""))
            if key in seen:  # waves overlap at the edges; an account counted twice is one
                continue     # account's habits weighted double, which is a fake population.
            seen.add(key)
            recs.append(r)

    def _mineable(r: dict) -> bool:
        for parsed in (r.get("charts") or {}).values():
            for _, value in (parsed.get("rows") or []):
                if value:
                    return True
        ov = r.get("overview") or {}
        return bool(ov.get("closed_profit") or ov.get("balance"))

    live = [r for r in recs if _mineable(r)]
    print(f"sources: {[p.name for p in paths]}")
    from collections import Counter as _C
    print(f"records={len(recs)} " + " ".join(f"{k}={v}" for k, v in sorted(_C(r.get("status") for r in recs).items())))

    # --- ACTIVITY: hour-of-day trade counts, per-account normalised so one whale cannot
    #     dictate the clock (an unnormalised sum measures the biggest account, not the flow).
    hour_share: dict[str, float] = defaultdict(float)
    hour_n = 0
    for r in live:
        rows = (r.get("charts", {}).get("ch_hourtrades") or {}).get("rows") or []
        tot = sum(v for _, v in rows)
        if tot <= 0:
            continue
        hour_n += 1
        for label, v in rows:
            hour_share[str(label)] += v / tot

    # --- ACTIVITY: instrument mix, counted as ACCOUNTS-TRADING not volume (same reason).
    sym_accounts: dict[str, int] = defaultdict(int)
    for r in live:
        rows = (r.get("charts", {}).get("ch_symboltrades") or {}).get("rows") or []
        for label, v in rows:
            if v > 0 and str(label).lower() != "archived":
                sym_accounts[str(label).upper()] += 1

    # --- PERFORMANCE (hypothesis-only): sign agreement per hour across accounts.
    #     A share far from 0.5 is a pointer; it is NOT a t-test and is not called one.
    hour_pos: dict[str, int] = defaultdict(int)
    hour_tot: dict[str, int] = defaultdict(int)
    for r in live:
        rows = (r.get("charts", {}).get("ch_hourprofit") or {}).get("rows") or []
        for label, v in rows:
            hour_tot[str(label)] += 1
            hour_pos[str(label)] += v > 0

    def hkey(x: str) -> int:
        try:
            return int(str(x).split(":")[0])
        except ValueError:
            return 99

    print(f"\nACTIVITY -- hour-of-day trade share (per-account normalised, n={hour_n} accounts)")
    for h in sorted(hour_share, key=hkey):
        share = hour_share[h] / max(hour_n, 1)
        print(f"  {h:>6}  {share*100:5.2f}%  {'#' * int(share * 400)}")

    print(f"\nACTIVITY -- instrument mix (accounts trading each symbol, n={len(live)} live)")
    for s, c in sorted(sym_accounts.items(), key=lambda kv: -kv[1])[:20]:
        print(f"  {s:<12} {c:4d}  {c/max(len(live),1)*100:5.1f}% of live accounts")

    print("\nPERFORMANCE (HYPOTHESIS-ONLY, survivorship-conditioned) -- share of accounts profitable by hour")
    for h in sorted(hour_tot, key=hkey):
        n = hour_tot[h]
        if n < 5:
            continue
        print(f"  {h:>6}  {hour_pos[h]/n*100:5.1f}% of {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
