"""EXPECTED INFORMATION GAIN PER SOURCE -- what to fetch NEXT, priced before it is fetched.

THE GAP THE LEDGER NAMED (Tier-1 B14): *"sources are registered by hand and value is measured
after the fact; no expected-information-gain pricing of the next source to acquire."*
`feature_roi` prices a feature the desk ALREADY has, `source_registry` prices a ground by what it
ALREADY produced, and `value_of_data` prices the missing observation for a hypothesis already
posed. All three are backward-looking by construction: none of them can rank the eighty-nine rows
of `data/asia_sources.json` by what fetching one would be WORTH, which is the only question the
collector's budget actually asks every hour.

THE RATIO, and every term is measured or declared, never invented:

    EVIG(s) = U(s) x N(s) x P(usable | s) x W(lag) / cost(s)

    U(s)   PRIOR UNCERTAINTY on what s speaks about: the mean posterior SD the desk carries on
           the instruments s declares in `targets`, read from POSTERIOR_ALPHA when it exists.
           Absent -> 1.0 and the row is stamped UNMEASURED_PRIOR: a flat prior is the honest
           default for a source about an instrument the desk has no posterior for, and it is
           marked so nobody reads the ranking as more measured than it is.
    N(s)   NOVELTY: the share of s's declared targets that NO successfully-collected source
           already covers. A second feed of a number the desk already has is worth its
           redundancy, not its content.
    P      P(usable): Beta(1+ok, 1+fail) posterior mean from the source's OWN collection history
           in `lake/collector_state.json`. A portal that has answered every time is worth more
           per attempt than one that has never parsed.
    W(lag) PIT DECAY: a monthly release published 20 days after its reference month carries less
           of its information to the moment it can be acted on. exp(-lag_days / 30).
    cost   MEASURED seconds when the state carries them, else the declared cadence's unit cost
           plus a fetch constant. Never zero -- a free source would rank infinitely.

WHAT IT CHANGES. `asia_collector` orders its due list by this rank, so when the pass budget is
spent the sources that get DEFERRED are the cheapest-value ones rather than whichever happened to
sit late in a hand-written file. Nothing is dropped, no source is refused, and the registry is not
rewritten: this is an ORDERING and a published price, which is the only shape an acquisition brain
may take here (the principal's never-reduce-aggressiveness order; L1.60 -- a screen may not apply
a bar of its own in either direction).

PROPOSALS ARE DRAWN FROM DECLARED GROUND ONLY. The top-ranked rows the collector has never
successfully read, plus the endpoints the parser itself handed back under
`data/intelligence/asia_endpoints`, are published as `proposals` with their price. Nothing here
invents a URL, bypasses an access control or touches a page whose registry row says
`machine_use_allowed: false` -- acquisition of new ground stays a declared act, and what this
organ adds is the PRICE that act was previously taken without.

    python desks/mt5/research/source_evig.py --once --budget-s 120
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTRY = DESK / "data" / "asia_sources.json"
STATE = DESK / "data" / "lake" / "collector_state.json"
FOUND = DESK / "data" / "intelligence" / "asia_endpoints"
POSTERIOR = DESK / "reports" / "POSTERIOR_ALPHA.json"
OUT = DESK / "reports" / "SOURCE_EVIG.json"

#: Declared cadence -> the seconds of desk attention one attempt costs, before measured seconds
#: replace it. A daily portal is attempted thirty times more often than a monthly one, so the
#: same wall clock per attempt is thirty times the standing cost.
CADENCE_COST: dict[str, float] = {
    "realtime": 60.0, "intraday": 40.0, "daily": 25.0, "weekly": 12.0,
    "monthly": 8.0, "quarterly": 6.0, "irregular": 10.0,
}
FETCH_COST_S = 6.0          # the floor: no source is free to ask for
OK_STATUSES = ("COLLECTED", "UNCHANGED", "NOT_MODIFIED")


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _sources() -> list[dict[str, Any]]:
    reg = _read(REGISTRY, {})
    rows = reg.get("sources") if isinstance(reg, dict) else None
    return [r for r in (rows or []) if isinstance(r, dict) and r.get("id")]


def _derived() -> list[dict[str, Any]]:
    """Endpoints the parser handed back, as candidate rows. Declared ground, never invented."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        files = sorted(FOUND.glob("endpoints_*.json"), reverse=True)[:6]
    except OSError:
        return out
    for f in files:
        doc = _read(f, {})
        rows = doc.get("endpoints") if isinstance(doc, dict) else doc
        for r in rows or []:
            if not isinstance(r, dict):
                continue
            sid = str(r.get("id") or r.get("url") or "")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            out.append({"id": sid, "url": r.get("url"), "targets": r.get("targets") or [],
                        "cadence": r.get("cadence") or "irregular", "plane": r.get("plane"),
                        "access": r.get("access") or "public", "derived": True,
                        "machine_use_allowed": r.get("machine_use_allowed")})
    return out


def _posterior_sd() -> tuple[dict[str, float], str]:
    """Mean posterior SD per symbol from POSTERIOR_ALPHA, or empty with the reason."""
    doc = _read(POSTERIOR, {})
    if not isinstance(doc, dict):
        return {}, "POSTERIOR_ALPHA.json unreadable"
    rows = doc.get("rows") or doc.get("sleeves") or []
    acc: dict[str, list[float]] = {}
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        sym = str(r.get("symbol") or "").upper()
        sd = r.get("mu_sd", r.get("sd"))
        try:
            v = float(sd)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if sym and math.isfinite(v) and v > 0:
            acc.setdefault(sym, []).append(v)
    if not acc:
        return {}, "no POSTERIOR_ALPHA row carries a symbol and a posterior sd"
    return {k: sum(v) / len(v) for k, v in acc.items()}, ""


def _history(state: dict[str, Any], sid: str) -> tuple[int, int, float | None]:
    """(ok, fail, measured seconds) from the collector's own state row."""
    row = state.get(sid)
    if not isinstance(row, dict):
        return 0, 0, None
    ok = int(row.get("ok_count") or (1 if str(row.get("last_status")) in OK_STATUSES else 0))
    fail = int(row.get("fail_count")
               or (1 if str(row.get("last_status") or "") not in (*OK_STATUSES, "") else 0))
    secs = row.get("seconds", row.get("ms"))
    try:
        s: float | None = float(secs) / (  # type: ignore[arg-type]
            1000.0 if "ms" in row and "seconds" not in row else 1.0)
    except (TypeError, ValueError):
        s = None
    return ok, fail, (s if s and math.isfinite(s) and s > 0 else None)


def _lag_weight(row: dict[str, Any]) -> float:
    pit = row.get("pit") if isinstance(row.get("pit"), dict) else {}
    try:
        lag = float((pit or {}).get("publication_lag_days") or 0.0)
    except (TypeError, ValueError):
        lag = 0.0
    return round(math.exp(-max(lag, 0.0) / 30.0), 6)


def price(sources: list[dict[str, Any]], state: dict[str, Any],
          sd: dict[str, float]) -> list[dict[str, Any]]:
    """One priced row per source, highest EVIG first. Pure: no I/O, so the test can drive it."""
    covered: dict[str, int] = {}
    for s in sources:
        ok, _f, _s = _history(state, str(s.get("id")))
        if ok > 0:
            for t in s.get("targets") or []:
                key = str(t).upper()
                covered[key] = covered.get(key, 0) + 1
    rows: list[dict[str, Any]] = []
    for s in sources:
        sid = str(s.get("id"))
        targets = [str(t).upper() for t in (s.get("targets") or []) if str(t).strip()]
        ok, fail, secs = _history(state, sid)
        novel = ([t for t in targets if covered.get(t, 0) == 0] if targets else [])
        # A row that declares no instrument cannot claim novelty it has not named. Registered
        # rows keep the neutral 0.5; a parser-derived endpoint with no declared target sits
        # below every source that named one, so the collector never spends its budget on an
        # unlabelled CDN URL before a central bank release it has a mechanism for.
        n_share = ((len(novel) / len(targets)) if targets
                   else (0.1 if s.get("derived") else 0.5))
        prior: list[float] = [float(sd[t]) for t in targets if sd.get(t)]
        u = (sum(prior) / len(prior)) if prior else 1.0
        p_usable = (1.0 + ok) / (2.0 + ok + fail)
        w = _lag_weight(s)
        cost = secs if secs is not None else (
            CADENCE_COST.get(str(s.get("cadence") or "irregular").lower(), 10.0))
        cost = max(float(cost) + FETCH_COST_S, 1.0)
        evig = u * max(n_share, 0.05) * p_usable * w / cost
        rows.append({
            "id": sid, "plane": s.get("plane"), "cadence": s.get("cadence"),
            "access": s.get("access"), "role": s.get("role") or "mechanism",
            "derived": bool(s.get("derived")),
            "targets": targets, "novel_targets": novel,
            "u_prior_sd": round(u, 6), "u_status": ("MEASURED" if prior
                                                    else "UNMEASURED_PRIOR"),
            "novelty": round(n_share, 4), "p_usable": round(p_usable, 4),
            "lag_weight": w, "cost_s": round(cost, 3),
            "cost_basis": ("measured seconds" if secs is not None else "declared cadence"),
            "ok": ok, "fail": fail,
            "never_collected": ok == 0,
            "evig": round(evig, 9),
        })
    rows.sort(key=lambda r: (-float(r["evig"]), str(r["id"])))
    for i, r in enumerate(rows):
        r["rank"] = i
    return rows


def fetch_order(ids: list[str]) -> list[str]:
    """THE CONSUMER'S DOOR. `asia_collector` hands its due ids here and fetches in the order
    that comes back: highest expected information gain first, so a spent budget defers the
    cheapest-value sources rather than whichever the registry happened to list last.

    Every id the ranking does not know is returned in its original order AFTER the ranked ones --
    an unpriced source is never dropped, only unordered (absence is not a demotion)."""
    doc = _read(OUT, {})
    rank: dict[str, int] = {}
    if isinstance(doc, dict):
        for r in doc.get("rows") or []:
            if isinstance(r, dict) and r.get("id") is not None:
                try:
                    rank[str(r["id"])] = int(r.get("rank", 10**6))
                except (TypeError, ValueError):
                    continue
    if not rank:
        return list(ids)
    known = sorted([i for i in ids if i in rank], key=lambda i: rank[i])
    return [*known, *[i for i in ids if i not in rank]]


def build(budget_s: float = 120.0) -> dict[str, Any]:
    t0 = time.monotonic()
    state = _read(STATE, {})
    state = state if isinstance(state, dict) else {}
    sd, sd_why = _posterior_sd()
    sources = [*_sources(), *_derived()]
    rows = price(sources, state, sd)
    proposals = [r for r in rows if r["never_collected"]][:20]
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": "OK" if rows else "UNMEASURED",
        "n_sources": len(rows), "n_registered": len(_sources()),
        "n_derived": sum(1 for r in rows if r["derived"]),
        "n_never_collected": sum(1 for r in rows if r["never_collected"]),
        "prior_basis": ("POSTERIOR_ALPHA mean mu_sd per symbol" if sd
                        else f"flat prior 1.0: {sd_why}"),
        "n_priors": len(sd),
        "formula": ("EVIG(s) = U(s) x novelty(s) x P(usable|s) x exp(-lag/30) / cost_s; U is the "
                    "desk's posterior sd on the instruments s declares, novelty the share of "
                    "those the collector has never successfully read from another source"),
        "unit": "posterior sd x usable share per second of collector attention",
        "rows": rows,
        "proposals": proposals,
        "seconds": round(time.monotonic() - t0, 3),
        "consumers": [
            "desks/mt5/research/asia_collector.py main() -> fetch_order(due ids): the pass "
            "collects in EVIG order, so a spent budget defers the cheapest-value sources",
            "the proposals list: the next ground to acquire, priced before it is fetched",
        ],
        "boundary": (
            "AN ORDERING AND A PRICE, NEVER A REFUSAL. No source is dropped, disabled or "
            "throttled by this rank, the registry is not rewritten, and no URL is invented: "
            "proposals are drawn only from rows already declared in data/asia_sources.json or "
            "handed back by the parser under data/intelligence/asia_endpoints."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=120.0)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        print(f"source evig: could not write {OUT}: {exc}")
        return 1
    print(f"source evig: {doc['n_sources']} source(s) priced "
          f"({doc['n_never_collected']} never collected, {doc['n_derived']} parser-derived); "
          f"prior basis: {doc['prior_basis']}")
    for r in doc["rows"][:8]:
        print(f"  {r['rank']:>3} {r['id'][:34]:<34} evig={r['evig']:.6g} "
              f"novelty={r['novelty']:.2f} p_usable={r['p_usable']:.2f} cost={r['cost_s']:.0f}s")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
