"""Summarise the FX Blue track-record corpus into MECHANISM structure (RESEARCH §4).

THE GRAVEYARD HALF (2026-10-06, Asia directive PART XIV, audit row 35). This file used to read
the living and drop the rest: `dead` pages (the statement is gone), emptied accounts and accounts
that stopped trading years ago were filtered out as "not mineable", which is survivorship bias
by construction. `genome_records()` now turns EVERY harvested record -- alive, dormant, emptied,
delisted -- into one structural genome row (provider_reverse.summary_signature), with its outcome
and lifespan, and `book_forensics` measures mechanism base rates over the whole population. The
report below prints the survivor-vs-graveyard contrast beside the old survivor-only view.

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

import gzip
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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
    # The RAW waves are gitignored (14MB each, re-harvestable); the committed artifact is the
    # gzipped digest. A fresh clone has the digest and nothing else, so read it when the raw
    # waves are absent -- a consumer that only works on the machine that mined is not wired.
    digest = SRC.parent / "mechanism_digest.jsonl.gz"
    if not paths and digest.exists():
        with gzip.open(digest, "rt", encoding="utf-8") as dh:
            lines = dh.read().splitlines()
        recs = [json.loads(ln) for ln in lines if ln.strip()]
        for r in recs:  # the digest hoists chart rows to the top level; restore the shape
            r["charts"] = {k: {"rows": v} for k, v in r.items() if k.startswith("ch_")}
        live = [r for r in recs if r.get("mineable")]
        print(f"sources: [{digest.name}]")
        return _report(recs, live)
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
    return _report(recs, live)


def _report(recs: list, live: list) -> int:
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


# --------------------------------------------------------------------------- genome rows

#: A statement whose last trading month ends this long before the harvest is DORMANT: the trader
#: stopped. Stated, not tuned; the genome reports the rule beside every count.
DORMANT_AFTER = timedelta(days=180)
#: Balance at or under this share of the implied starting capital is an EMPTIED account.
EMPTIED_SHARE = 0.05
#: Outcome vocabulary. Everything except ALIVE is the graveyard; SHELL never traded and is
#: excluded from the population (it never lived), but counted.
DEAD = ("DELISTED", "BLOWN", "EMPTIED", "DORMANT")


def _reverse() -> Any:
    spec = importlib.util.spec_from_file_location(
        "provider_reverse", BASE / "research" / "provider_reverse.py")
    if spec is None or spec.loader is None:
        return None
    mod = sys.modules.get("provider_reverse")
    if mod is not None and hasattr(mod, "summary_signature"):
        return mod
    mod = importlib.util.module_from_spec(spec)
    sys.modules["provider_reverse"] = mod
    spec.loader.exec_module(mod)
    return mod


def _rows(r: dict, chart: str) -> list:
    return list(((r.get("charts") or {}).get(chart) or {}).get("rows") or [])


def _num(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def _date(v: Any) -> datetime | None:
    s = str(v or "").strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y", "%Y/%m"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def clean_symbol(s: str) -> str:
    """Broker suffixes off (`EURUSD.p`, `AUDCAD#`, `EURJPY-cd`, `AUDUSDf`) -> the bare pair."""
    t = str(s or "").upper()
    for sep in (".", "#", "-", "_"):
        if sep in t and len(t.split(sep)[0]) >= 6:
            t = t.split(sep)[0]
    if len(t) == 7 and t[:6].isalpha() and t[6] in "FMCIRPE":
        t = t[:6]
    return t


def outcome_of(r: dict, harvested: datetime | None, active: list[str]) -> tuple[str, str]:
    """(outcome, why) for one statement, from its own published numbers only."""
    status = str(r.get("status") or "")
    ov = r.get("overview") or {}
    if status == "dead" and not ov:
        return "DELISTED", "the statement page is gone (harvester: dead)"
    if not active and not _rows(r, "ch_tradedurationprofit"):
        return "SHELL", "no trade was ever published"
    bal = _num(ov.get("balance"))
    cp = _num(ov.get("closed_profit"))
    if bal is not None and cp is not None:
        start = bal - cp
        if start > 0 and bal <= EMPTIED_SHARE * start and cp < 0:
            return "BLOWN", f"balance {bal:g} of an implied {start:g} start, closed P&L {cp:g}"
    if bal is not None and bal <= 1.0:
        return "EMPTIED", f"balance {bal:g}: closed out (blow-up or withdrawal, not separable)"
    last = _date(active[-1]) if active else _date(ov.get("last_update"))
    if harvested is not None and last is not None and harvested - last > DORMANT_AFTER:
        return "DORMANT", f"last active {last.date()}, harvested {harvested.date()}"
    return "ALIVE", "traded inside the dormancy window of its harvest"


def _load_records(paths: list[Path] | None = None) -> list[dict]:
    """Every wave, newest harvest per account. A dead page is a record, not a gap."""
    if paths is None:
        paths = sorted(SRC.parent.glob("track_records*.jsonl"))
    best: dict[str, dict] = {}
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for ln in lines:
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            key = str(r.get("user", ""))
            if not key:
                continue
            prev = best.get(key)
            stamp = str(r.get("harvested_utc", ""))
            if prev is None or stamp >= str(prev.get("harvested_utc", "")):
                best[key] = r
    return list(best.values())


def genome_records(paths: list[Path] | None = None) -> list[dict]:
    """One genome row per FX Blue account -- the living AND the graveyard.

    PIT: `published_time` is the statement's own last update (the latest instant its numbers
    describe and the earliest the public could have read them); `available_time` is the
    harvest. A row is knowable from `knowable_from` = the published time when the statement
    gives one, else the harvest -- never earlier.
    """
    rev = _reverse()
    out: list[dict] = []
    for r in _load_records(paths):
        harvested = _date(r.get("harvested_utc"))
        ov = r.get("overview") or {}
        months = [(str(m[0]), sum(_num(x) or 0.0 for x in m[1:]))
                  for m in _rows(r, "ch_lotstradedmonthly_bysymbol") if m]
        active = [m for m, v in months if v > 0]
        outcome, why = outcome_of(r, harvested, active)
        dur_pts = _rows(r, "ch_tradedurationprofit")
        dd = [_num(v) for _, v in _rows(r, "ch_balancedrawdown")]
        dd = [x for x in dd if x is not None]
        sym = {}
        for lab, v in _rows(r, "ch_symboltrades"):
            if str(lab).lower() in ("archived", "profit") or not _num(v):
                continue
            k = clean_symbol(str(lab))
            sym[k] = sym.get(k, 0.0) + float(_num(v) or 0.0)
        hours = {}
        for lab, v in _rows(r, "ch_hourtrades"):
            try:
                hours[int(str(lab).split(":")[0])] = float(_num(v) or 0.0)
            except ValueError:
                continue
        sig = rev.summary_signature(
            trade_profits=[_num(p) for _, p in dur_pts],
            trade_durations=[_num(d) for d, _ in dur_pts],
            hour_trades=hours, symbol_trades=sym,
            max_dd_pct=(min(dd) if dd else None),
            monthly_lots=[v for _, v in months]) if rev is not None and outcome != "DELISTED" \
            else {"tags": [], "n_trades_sampled": 0}
        first = _date(active[0]) if active else None
        last = _date(active[-1]) if active else None
        published = _date(ov.get("last_update"))
        if published is not None and harvested is not None and published > harvested:
            published = None                       # a stamp after the harvest is not a stamp
        top = sorted(sym.items(), key=lambda kv: -kv[1])[:5]
        out.append({
            "trader_id": f"fxblue:{r.get('user')}", "source": "fxblue", "culture": "global/en",
            "account_type": str(ov.get("account_type") or "") or None,
            "currency": ov.get("currency"),
            "market": "fx_cfd", "instruments": [k for k, _ in top],
            "outcome": outcome, "outcome_why": why,
            "dead": outcome in DEAD, "profitable": (_num(ov.get("closed_profit")) or 0.0) > 0
            if ov.get("closed_profit") is not None else None,
            "first_active": first.date().isoformat() if first else None,
            "last_active": last.date().isoformat() if last else None,
            "survival_days": (last - first).days if first and last else None,
            "published_time": published.isoformat() if published else None,
            "available_time": harvested.isoformat() if harvested else None,
            "knowable_from": (published or harvested).isoformat()
            if (published or harvested) else None,
            **{k: sig.get(k) for k in ("n_trades_sampled", "win_rate", "payoff_ratio", "skew",
                                       "tail_ratio", "median_hold_raw", "max_dd_pct",
                                       "top_symbol_share", "session", "session_share",
                                       "lot_escalation")},
            "hold_unit": "fxblue_chart_native (unit as published; not converted)",
            "session_clock": "statement broker clock",
            "style_tags": list(sig.get("tags") or []),
        })
    return out


def graveyard_contrast(rows: list[dict]) -> dict:
    """Survivor-only vs whole-population view of the same corpus, per style tag."""
    pop = [r for r in rows if r["outcome"] != "SHELL"]
    tags = sorted({t for r in pop for t in r["style_tags"]})
    out = {}
    for t in tags:
        have = [r for r in pop if t in r["style_tags"]]
        alive = [r for r in have if not r["dead"]]
        out[t] = {"n": len(have), "alive": len(alive),
                  "p_alive": round(len(alive) / len(have), 4) if have else None,
                  "survivor_only_profitable": round(
                      sum(1 for r in alive if r["profitable"]) / len(alive), 4) if alive else None,
                  "population_alive_and_profitable": round(
                      sum(1 for r in alive if r["profitable"]) / len(have), 4) if have else None}
    return out


if __name__ == "__main__":
    if "--genome" in sys.argv:
        g = genome_records()
        from collections import Counter as _Cn
        print(f"genome rows={len(g)} " + " ".join(
            f"{k}={v}" for k, v in sorted(_Cn(r['outcome'] for r in g).items())))
        for t, v in graveyard_contrast(g).items():
            print(f"  {t:22s} n={v['n']:4d} p_alive={v['p_alive']} "
                  f"survivor-only win={v['survivor_only_profitable']} "
                  f"population={v['population_alive_and_profitable']}")
        raise SystemExit(0)
    raise SystemExit(main())
