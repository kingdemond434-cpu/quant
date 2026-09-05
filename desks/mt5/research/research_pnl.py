"""Research P&L: what each source of hypotheses, and each bandit arm, has earned per unit of cost.

The bandit schedules research directions on a Beta posterior of certification and a declared
cost table. What it did not have was the other half of the ledger -- the GROWTH the certificates
actually carry in the allocator's book -- joined to the trials that produced them:

    trials       hypotheses the graph holds from the source (last fate per node id)
    failed       FAILED or BURIED
    certified    CERTIFIED
    growth       expected_log_per_day x (sleeve weight / total_heat), summed over the funded
                 sleeves whose certificate names the source -- log-wealth per day
    cost         trials x sum(bandit.COST[arm]): DECLARED units (compute, data, latency,
                 multiplicity), not measured seconds -- the bandit's own table, so the two
                 halves of the ledger price a trial the same way
    roi          growth per declared cost unit
    worth        growth per source normalised to mean 1.0 over the sources with growth, floored

WHICH SOURCE A CERTIFICATE NAMES. The canon carries `hunt` (and `shadow_spec.hunt`); a
certificate carrying `source`, `kind` or `provenance` is read first, then `hunt`, else it is
attributed to "unknown" -- said, never guessed. `external_discoveries` is the graph's `external`
under another name and is aliased so the trials and the growth land on one row.

A SOURCE WITH ZERO CERTIFICATES BUT MANY TRIALS STILL HAS AN INFORMATION VALUE. Thirty thousand
buried external screens are the negative-knowledge index every proposer consults before it
re-proposes a region; the value of that is not on this ledger, and a worth of zero would tell the
bandit to stop buying it. Worth is therefore never set below 0.25: the exploration floor that
protects cold arms protects the informative-but-uncertified ones too. The consumer is the
bandit's `evidence(marginal_by_source=...)`, which reads a per-arm worth; `worth_by_arm` in
`data/research_marginal.json` is shaped for it. This module measures and writes; it does not
edit the bandit.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research.bandit import ARMS, COST, SOURCE_ARM, arm_of  # noqa: E402

CANON = _DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
FORECASTS = _DESK / "data" / "pf_forecast_log.jsonl"
REPORT = _DESK / "reports" / "RESEARCH_PNL.json"
MARGINAL = _DESK / "data" / "research_marginal.json"

#: Never below this: the exploration floor. A source or arm whose certificates carry no growth
#: yet is still buying negative knowledge, and the bandit's 20% uniform share is not a
#: substitute for a worth that says so.
WORTH_FLOOR = 0.25
#: Canon `hunt` names that are a graph source under another name.
SOURCE_ALIASES = {"external_discoveries": "external"}
UNKNOWN = "unknown"

RESEARCH_PNL_NOTE = (
    "A source with zero certificates but many trials still has an information value: every "
    "FAILED region it recorded is negative knowledge the compiler and the proposers consult "
    "before re-proposing, and that value is not priced on this ledger. Worth is therefore never "
    f"set below {WORTH_FLOOR}: the exploration floor that protects cold arms protects "
    "informative-but-uncertified sources too. Growth is normalised to mean 1.0 over the sources "
    "(arms) whose certificates carry growth in the book, matching the bandit's own "
    "_marginal_by_arm convention; everything else sits on the floor.")


def _json(path: Path) -> dict:
    try:
        d = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _graph_rows() -> tuple[list[dict], str | None]:
    try:
        from libs.research.hypothesis_graph import Graph
        rows = Graph().rows()
    except Exception as exc:
        return [], f"hypothesis graph unreadable: {type(exc).__name__}: {exc}"
    return rows, (None if rows else "hypothesis graph absent or empty on this host")


def census(rows: list[dict]) -> dict[str, dict]:
    """trials / failed / certified per source, from the LAST row of every node id."""
    latest: dict[str, dict] = {}
    for r in rows:
        if isinstance(r, dict) and r.get("id"):
            latest[str(r["id"])] = r
    out: dict[str, dict] = {}
    for r in latest.values():
        src = str(r.get("source") or UNKNOWN)
        c = out.setdefault(src, {"trials": 0, "failed": 0, "certified": 0, "arm": arm_of(src)})
        c["trials"] += 1
        fate = str(r.get("fate"))
        if fate in ("FAILED", "BURIED"):
            c["failed"] += 1
        elif fate == "CERTIFIED":
            c["certified"] += 1
    return out


def _book() -> tuple[dict[str, float], float, float, dict]:
    try:
        lines = [ln for ln in FORECASTS.read_text("utf-8").splitlines() if ln.strip()]
        last = json.loads(lines[-1])
    except (OSError, ValueError, IndexError):
        return {}, 0.0, 0.0, {"source": "pf_forecast_log absent on this host; growth is zero "
                                         "everywhere, which is a gap, not a measurement"}
    book = {str(k): float(v) for k, v in (last.get("book") or {}).items()
            if isinstance(v, (int, float)) and float(v) > 0}
    heat = float(last.get("total_heat") or sum(book.values()) or 0.0)
    elog = float(last.get("expected_log_per_day") or 0.0)
    return book, heat, elog, {"source": "pf_forecast_log (last line)", "t": last.get("t"),
                              "total_heat": heat, "expected_log_per_day": elog,
                              "n_funded": len(book)}


def cert_source(cert: dict) -> str:
    for key in ("source", "kind", "provenance", "hunt"):
        v = cert.get(key)
        if isinstance(v, str) and v:
            return SOURCE_ALIASES.get(v, v)
    v = (cert.get("shadow_spec") or {}).get("hunt") if isinstance(cert.get("shadow_spec"),
                                                                  dict) else None
    return SOURCE_ALIASES.get(str(v), str(v)) if v else UNKNOWN


def _sleeve_names(cert: dict) -> set[str]:
    """Every ledger / book name a certificate's shadow spec can appear under.

    `shadow_forward` names a session_range_breakout sleeve `{sym}_{window}` and every other
    family `{sym}_{family}_{window}`, with the condition appended when there is one; the legacy
    gold sleeve is `gold_asia`. Both spellings are offered so the join does not depend on which
    the allocator used.
    """
    spec = cert.get("shadow_spec") if isinstance(cert.get("shadow_spec"), dict) else {}
    sym = str(spec.get("symbol") or cert.get("sym") or "").upper()
    fam = str(spec.get("family") or "")
    win = str(spec.get("selector") or "")
    cond = spec.get("condition")
    if not sym or not win:
        return set()
    tail = f"{win}_{cond}" if cond else win
    names = {f"{sym}_{fam}_{tail}", f"{sym}_{tail}"}
    if sym == "XAUUSD":
        names.add(f"gold_{tail}")
    return names


def resolver(canon: dict) -> dict[str, dict]:
    """sleeve name -> {source, cert} for every certificate in the canon."""
    out: dict[str, dict] = {}
    for key, cert in (canon.get("survivors") or {}).items():
        if not isinstance(cert, dict):
            continue
        src = cert_source(cert)
        for name in _sleeve_names(cert):
            cur = out.get(name)
            if cur is None:
                out[name] = {"source": src, "cert": key, "n_certs": 1}
            else:
                cur["n_certs"] += 1
                if cur["source"] != src:
                    cur["source_conflict"] = sorted({cur["source"], src})
    return out


def attribute(book: dict[str, float], heat: float, elog: float,
              res: dict[str, dict]) -> dict[str, dict]:
    """Per funded sleeve: its share of the book's expected growth and the source it came from."""
    out: dict[str, dict] = {}
    for sleeve, w in book.items():
        share = (w / heat) if heat > 0 else 0.0
        hit = res.get(sleeve) or {}
        out[sleeve] = {"weight": w, "share_of_heat": round(share, 6),
                       "growth_per_day": round(elog * share, 8),
                       "source": hit.get("source", UNKNOWN), "cert": hit.get("cert"),
                       **({"source_conflict": hit["source_conflict"]}
                          if hit.get("source_conflict") else {})}
    return out


def worth(growth: dict[str, float], keys: list[str]) -> dict[str, float]:
    """Normalise to mean 1.0 over the keys with positive growth; floor everything else."""
    pos = {k: v for k, v in growth.items() if v > 0}
    scale = (sum(pos.values()) / len(pos)) if pos else 0.0
    out = {}
    for k in keys:
        raw = growth.get(k, 0.0)
        out[k] = round(max(WORTH_FLOOR, raw / scale), 4) if scale > 0 and raw > 0 else WORTH_FLOOR
    return out


def run() -> dict:
    rows, gap = _graph_rows()
    gaps: dict[str, str] = {}
    if gap:
        gaps["hypothesis_graph"] = gap
    per_source = census(rows)
    canon = _json(CANON)
    if not canon.get("survivors"):
        gaps["canon"] = "survivors canon absent or empty on this host; growth attributed to unknown"
    book, heat, elog, book_ctx = _book()
    if not book:
        gaps["allocator_book"] = book_ctx["source"]
    res = resolver(canon)
    sleeves = attribute(book, heat, elog, res)

    growth_by_source: dict[str, float] = defaultdict(float)
    for s in sleeves.values():
        growth_by_source[s["source"]] += s["growth_per_day"]
    for src in growth_by_source:
        per_source.setdefault(src, {"trials": 0, "failed": 0, "certified": 0, "arm": arm_of(src)})
    # GROWTH NOBODY CAN CLAIM IS CREDITED TO NOBODY. A funded sleeve whose certificate is not in
    # this host's canon is reported as unattributed; it is not handed to the bandit's fallback
    # arm, where it would buy research from a direction that did not produce it.
    unattributed = float(growth_by_source.pop(UNKNOWN, 0.0))
    per_source.pop(UNKNOWN, None)
    for src, c in per_source.items():
        unit = float(sum(COST[c["arm"]]))
        g = float(growth_by_source.get(src, 0.0))
        cost = c["trials"] * unit
        c.update({"growth_per_day": round(g, 8), "cost_unit_per_trial": unit,
                  "cost_units": round(cost, 2),
                  "roi_growth_per_cost_unit": (round(g / cost, 10) if cost > 0 else None),
                  "certify_rate": (round(c["certified"] / c["trials"], 5) if c["trials"] else None),
                  "growth_per_certificate": (round(g / c["certified"], 8) if c["certified"]
                                             else None)})
    per_arm: dict[str, dict] = {a: {"trials": 0, "failed": 0, "certified": 0,
                                    "growth_per_day": 0.0, "cost_units": 0.0,
                                    "cost_unit_per_trial": float(sum(COST[a])), "sources": []}
                                for a in ARMS}
    for src, c in per_source.items():
        a = per_arm[c["arm"]]
        for k in ("trials", "failed", "certified", "growth_per_day", "cost_units"):
            a[k] += c[k]
        a["sources"].append(src)
    for a in per_arm.values():
        a["growth_per_day"] = round(a["growth_per_day"], 8)
        a["roi_growth_per_cost_unit"] = (round(a["growth_per_day"] / a["cost_units"], 10)
                                         if a["cost_units"] > 0 else None)
        a["sources"].sort()
    # Sources the bandit's declared table does not know fall to its "somebody on the internet
    # said" arm; they are listed so the mis-attribution is visible rather than silent.
    fallback = sorted(s for s, c in per_source.items()
                      if c["arm"] == "alt_data_hypothesis" and s.split(":")[0] not in SOURCE_ARM)
    worth_src = worth({s: c["growth_per_day"] for s, c in per_source.items()},
                      sorted(per_source))
    worth_arm = worth({a: c["growth_per_day"] for a, c in per_arm.items()}, list(ARMS))
    marginal = {"generated_utc": datetime.now(tz=UTC).isoformat(), "worth_by_arm": worth_arm,
                "worth_by_source": worth_src, "floor": WORTH_FLOOR,
                "consumer": "libs.research.bandit.evidence(marginal_by_source=worth_by_arm)"}
    MARGINAL.parent.mkdir(parents=True, exist_ok=True)
    MARGINAL.write_text(json.dumps(marginal, indent=1), "utf-8")
    doc = {"generated_utc": marginal["generated_utc"], "graph_rows": len(rows),
           "n_sources": len(per_source), "allocator_book": book_ctx, "gaps": gaps,
           "sources": dict(sorted(per_source.items())), "arms": per_arm, "sleeves": sleeves,
           "unattributed_growth_per_day": round(unattributed, 8),
           "unattributed_sleeves": sorted(k for k, s in sleeves.items()
                                          if s["source"] == UNKNOWN),
           "arm_fallback_sources": fallback,
           "worth_by_source": worth_src, "worth_by_arm": worth_arm,
           "research_pnl_note": RESEARCH_PNL_NOTE,
           "rule": ("growth = expected_log_per_day x weight / total_heat per funded sleeve, "
                    "attributed to the certificate's source; cost = trials x sum(bandit.COST[arm]) "
                    "in DECLARED units, not seconds; worth = growth normalised to mean 1.0 over "
                    f"sources with growth, never below {WORTH_FLOOR}")}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"RESEARCH PNL  {d['graph_rows']} graph rows, {d['n_sources']} sources, "
          f"book {d['allocator_book'].get('n_funded', 0)} funded, unattributed growth "
          f"{d['unattributed_growth_per_day']:+.6f}/day")
    for s, c in sorted(d["sources"].items(), key=lambda kv: -kv[1]["growth_per_day"])[:14]:
        print(f"  {s[:34]:34s} arm={c['arm'][:22]:22s} trials={c['trials']:6d} "
              f"cert={c['certified']:3d} growth={c['growth_per_day']:+.6f}/d "
              f"worth={d['worth_by_source'][s]:.2f}")
    for a, w in sorted(d["worth_by_arm"].items(), key=lambda kv: -kv[1]):
        print(f"  arm {a:24s} worth={w:.2f} growth={d['arms'][a]['growth_per_day']:+.6f}/d")
    for g, why in d["gaps"].items():
        print(f"  GAP {g}: {why}")
    print(f"written: {REPORT}  marginal: {MARGINAL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
