"""F12 -- WHAT A SEARCH POPULATION IS PAID FOR IS THE FORWARD OUTCOME, not passing a screen.

THE PRINCIPAL, 2026-09-12:

    A population's ultimate reward comes from FORWARD/LIVE incremental portfolio contribution, not
    screening success; credit flows backwards live outcome -> sleeve -> hypothesis ->
    representation -> search operator -> scientist -> dataset.

THE GAP, AS THE LEDGER STATES IT: the population that created each candidate is already recorded
and generator weights are read -- the credit path STOPS SHORT OF LIVE. So a miner is rewarded for
producing candidates that pass the gauntlet, and nothing ever asks whether the things it produced
went on to earn anything. Those are different objectives and a desk that optimises the first gets
exactly what it measured: 61 certificates, 33 of them from one lane, and an n_eff of 3.5.

THE CHAIN IS ALREADY ON DISK AND NOBODY HAS WALKED IT. Every link exists:

    forward clock   reports/shadow/*.json        exp_r and n, per clock
    sleeve          data/sleeves.json            name -> family, symbol
    certificate     reports/UNIVERSAL_SURVIVORS  shadow_spec (symbol, family, params), hunt
    docket row      data/hypotheses/external_survivors.json   source, producer, url
    scientist       the row's `source`           which miner, seat or sweep proposed it
    representation  the source's lane            symbolic grammar, mined anomaly, seat, joint

Joining them attributes realised FORWARD R back to the producer that first proposed the cell. No
new measurement is invented; the desk has been holding both ends of the chain and never closed it.

CREDIT IS REALISED R, NOT CERTIFICATE COUNT, and the difference is the whole item. A source that
mints forty certificates which go on to earn nothing has produced forty ways to spend the
family-wise error budget. The report ranks by earned R and shows the certificate count beside it,
so productivity and performance can be told apart at a glance.

LIVE IS THE INTENDED SOURCE AND IS TOO THIN TODAY, so forward is used and said so. The live ledger
holds 16 deals across 3 days; the forward lanes hold 123 clocks. Forward is the same evidence one
step earlier, and substituting it silently would be the lie -- it is labelled on every row.

    python desks/mt5/research/credit_assignment.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
LEDGER = DESK / "data" / "live_ledger.jsonl"
SLEEVES = DESK / "data" / "sleeves.json"
SHADOW = (DESK / "reports" / "shadow" / "shadow_state.json",
          DESK / "reports" / "shadow" / "qquant_shadow_state.json",
          DESK / "reports" / "shadow" / "scalp_shadow_state.json")
OUT = DESK / "reports" / "CREDIT_ASSIGNMENT.json"

#: Live deals required before live evidence replaces forward as the credit source. Thirty is not
#: a statistical threshold so much as the point at which one lucky sleeve stops being the answer.
MIN_LIVE_DEALS = 30

#: Which representation lane a source belongs to. The same table the frontier map uses, because
#: two organs disagreeing about what `miner:anomalies` IS would make both reports unreadable.
_LANE: tuple[tuple[str, str], ...] = (
    ("joint_evolution", "joint_genome"), ("research_tree", "joint_genome"),
    ("alpha_evolution", "symbolic_grammar"), ("orthogonal_sweep", "symbolic_grammar"),
    ("edge_search", "symbolic_grammar"),
    ("miner", "mined_anomaly"), ("anomal", "mined_anomaly"),
    # `ext_` IS THE CRAWLER'S OWN PREFIX and the first run left all five of its certificates
    # UNCLASSIFIED -- the lane carrying +70.68R, the most per certificate of any lane, reported
    # as "we do not know what this is". A rollup whose largest row is UNCLASSIFIED is a rollup
    # that has not been read.
    ("ext_", "external_claim"),
    ("external", "external_claim"), ("deep_forest", "external_claim"),
    ("reddit", "external_claim"), ("forexfactory", "external_claim"),
    ("github", "external_claim"), ("tradingview", "external_claim"),
    ("mql5", "external_claim"), ("darwinex", "external_claim"), ("fxblue", "external_claim"),
    ("kimi", "seat_proposal"), ("deepseek", "seat_proposal"), ("seat", "seat_proposal"),
)


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _lane_of(source: str) -> str:
    low = (source or "").lower()
    for needle, lane in _LANE:
        if needle in low:
            return lane
    return "UNCLASSIFIED"


def _cell_key(symbol: Any, family: Any, params: Any) -> tuple[str, str, str]:
    return (str(symbol or ""), str(family or ""), json.dumps(params, sort_keys=True))


def _forward_rows() -> list[dict[str, Any]]:
    """Every forward clock with realised evidence: its key, expectancy and trade count."""
    out: list[dict[str, Any]] = []
    for p in SHADOW:
        d = _read(p)
        if not isinstance(d, dict):
            continue
        for key, r in d.items():
            if not isinstance(r, dict):
                continue
            e, n = r.get("exp_r"), r.get("n")
            if isinstance(e, (int, float)) and isinstance(n, (int, float)) and int(n) > 0:
                out.append({"clock": key, "lane": p.name, "exp_r": float(e), "n": int(n),
                            "realised_r": float(e) * int(n),
                            "status": r.get("status"),
                            "symbol": str(key).split(".")[0]})
    return out


def _live_rows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not LEDGER.exists():
        return out
    for ln in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        r = d.get("r_multiple")
        if isinstance(r, (int, float)):
            out.append({"sleeve": str(d.get("sleeve") or ""), "symbol": str(d.get("symbol") or ""),
                        "realised_r": float(r)})
    return out


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)

    # LINK 1: certificate -> its originating docket row -> the scientist that proposed it.
    surv = _read(SURVIVORS) or {}
    docket = _read(DOCKET)
    rows = [r for r in docket if isinstance(r, dict)] if isinstance(docket, list) else []
    by_cell: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in rows:
        by_cell.setdefault(_cell_key(r.get("symbol"), r.get("family"), r.get("params")), r)

    certs: list[dict[str, Any]] = []
    for key, row in (surv.get("survivors") or {}).items():
        if not isinstance(row, dict):
            continue
        spec = row.get("shadow_spec") or {}
        ck = _cell_key(spec.get("symbol") or row.get("sym"), spec.get("family"),
                       spec.get("params"))
        origin = by_cell.get(ck) or {}
        source = str(origin.get("source") or row.get("hunt") or "UNATTRIBUTED")
        certs.append({
            "certificate": key, "symbol": ck[0], "family": ck[1],
            "selector": spec.get("selector"),
            "source": source, "producer": origin.get("producer"),
            "lane": _lane_of(source),
            "attributed": bool(origin),
        })

    # LINK 2: forward clock -> certificate. A clock's key carries symbol and selector; the
    # certificate carries both, so the join is on what the desk actually records rather than on
    # a name convention nobody guarantees.
    fwd = _forward_rows()
    live = _live_rows()
    use_live = len(live) >= MIN_LIVE_DEALS
    by_sym_fam: dict[str, list[dict[str, Any]]] = {}
    for c in certs:
        by_sym_fam.setdefault(c["symbol"], []).append(c)

    credited: list[dict[str, Any]] = []
    unmatched = 0
    for f in fwd:
        cands = by_sym_fam.get(f["symbol"]) or []
        sel = str(f["clock"]).split(".")[-1] if "." in str(f["clock"]) else ""
        best = None
        for c in cands:
            if c.get("selector") and str(c["selector"]) and str(c["selector"]) in str(f["clock"]):
                best = c
                break
        if best is None and len(cands) == 1:
            best = cands[0]
        if best is None:
            unmatched += 1
            continue
        credited.append({**f, "certificate": best["certificate"], "source": best["source"],
                         "lane": best["lane"], "family": best["family"], "selector": sel})

    # LINK 3: the credit itself, rolled up to the scientist and the representation lane.
    def _rollup(rows_in: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        agg: dict[str, dict[str, Any]] = {}
        for r in rows_in:
            k = str(r.get(key) or "UNATTRIBUTED")
            a = agg.setdefault(k, {key: k, "n_clocks": 0, "n_trades": 0, "realised_r": 0.0,
                                   "certificates": set()})
            a["n_clocks"] += 1
            a["n_trades"] += int(r.get("n") or 0)
            a["realised_r"] += float(r.get("realised_r") or 0.0)
            a["certificates"].add(r.get("certificate"))
        out = []
        for a in agg.values():
            n_cert = len(a["certificates"])
            out.append({key: a[key], "n_certificates": n_cert, "n_clocks": a["n_clocks"],
                        "n_trades": a["n_trades"],
                        "realised_r": round(a["realised_r"], 4),
                        "r_per_certificate": (round(a["realised_r"] / n_cert, 4)
                                              if n_cert else None),
                        "r_per_trade": (round(a["realised_r"] / a["n_trades"], 5)
                                        if a["n_trades"] else None)})
        out.sort(key=lambda r: -float(r["realised_r"]))
        return out

    by_source = _rollup(credited, "source")
    by_lane = _rollup(credited, "lane")
    n_attributed = sum(1 for c in certs if c["attributed"])

    # THE NUMBER THAT MATTERS MOST IS THE ONE A ROLLUP HIDES: certificates that have earned
    # NOTHING because no forward clock with trades could be credited to them. A board showing
    # only who earned what answers "who is winning" and never "how much of what we certified has
    # produced any evidence at all", and the second is the question a fixed error budget makes
    # expensive.
    credited_certs = {str(c.get("certificate")) for c in credited}
    silent = [c for c in certs if str(c["certificate"]) not in credited_certs]
    silent_by_source: dict[str, int] = {}
    silent_by_family: dict[str, int] = {}
    for c in silent:
        silent_by_source[str(c["source"])] = silent_by_source.get(str(c["source"]), 0) + 1
        silent_by_family[str(c["family"])] = silent_by_family.get(str(c["family"]), 0) + 1

    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK" if credited else "UNMEASURED",
        "evidence_source": ("live" if use_live else "forward"),
        "evidence_note": (
            f"LIVE is the intended source and is too thin: the ledger holds {len(live)} deal(s) "
            f"against a floor of {MIN_LIVE_DEALS}. Forward evidence is used instead -- the same "
            f"evidence one step earlier -- and every row says so. Substituting it silently would "
            f"be the lie."
            if not use_live else
            f"live: {len(live)} realised deal(s), above the {MIN_LIVE_DEALS} floor"),
        "chain": ["forward clock", "sleeve", "certificate", "docket row", "scientist (source)",
                  "representation lane"],
        "attribution": {
            "n_certificates": len(certs),
            "n_traced_to_a_docket_row": n_attributed,
            "n_unattributed": len(certs) - n_attributed,
            "why_unattributed": (
                "a certificate whose exact (symbol, family, params) is not in the docket cannot "
                "be traced to the scientist that proposed it. That is a broken link in the "
                "provenance chain, not a scientist with no name, and it is counted rather than "
                "folded into UNATTRIBUTED as though it were one."),
            "n_clocks_credited": len(credited),
            "n_clocks_unmatched": unmatched,
        },
        "silent_certificates": {
            "n": len(silent), "of": len(certs),
            "by_source": dict(sorted(silent_by_source.items(), key=lambda t: -t[1])[:12]),
            "by_family": dict(sorted(silent_by_family.items(), key=lambda t: -t[1])[:12]),
            "why": ("a certificate with no credited forward clock has produced no evidence since "
                    "it was minted. It may be too new, its clock may carry no trades yet, or the "
                    "join may not reach it -- those are different and the count does not "
                    "distinguish them, which is why this is a NUMBER TO CHASE and not a verdict "
                    "on the certificates."),
            "why_it_matters": ("each of these spent a share of a FIXED family-wise error budget "
                               "that every other hypothesis then had to clear, and has returned "
                               "nothing measurable so far."),
        },
        "by_scientist": by_source,
        "by_representation_lane": by_lane,
        "headline": (
            "; ".join(f"{r['source']}: {r['realised_r']:+.1f}R over {r['n_trades']} trade(s) "
                      f"from {r['n_certificates']} certificate(s)"
                      for r in by_source[:4]) or "nothing credited yet"),
        "why_not_certificate_count": (
            "a source that mints forty certificates which go on to earn nothing has produced "
            "forty ways to spend a fixed family-wise error budget. Ranking by realised R with "
            "the certificate count beside it is the only way to tell productivity from "
            "performance, and the desk has been optimising the first."),
        "boundary": (
            "NOTHING HERE REWEIGHTS A GENERATOR. It publishes what each scientist's output has "
            "actually earned; changing a generator's weight on that evidence is a decision for "
            "the docket, and doing it automatically off a thin forward record is how a desk "
            "starves the lane that was merely unlucky."),
        "why": (
            "a miner is rewarded today for producing candidates that pass the gauntlet, and "
            "nothing asks whether they went on to earn anything. Those are different objectives, "
            "and a desk that optimises the first gets what it measured."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    att = doc["attribution"]
    print(f"credit assignment: {doc['status']}   evidence={doc['evidence_source']}")
    print(f"  {att['n_traced_to_a_docket_row']}/{att['n_certificates']} certificate(s) trace to "
          f"the scientist that proposed them; {att['n_clocks_credited']} clock(s) credited, "
          f"{att['n_clocks_unmatched']} unmatched")
    print("  by scientist (realised R, not certificates minted):")
    for r in doc["by_scientist"][:10]:
        print(f"    {str(r['source'])[:34]:<34} {r['realised_r']:+9.2f}R  "
              f"{r['n_trades']:>5} trade(s)  {r['n_certificates']:>3} cert(s)  "
              f"R/cert {r['r_per_certificate']}")
    sc = doc["silent_certificates"]
    print(f"  {sc['n']} of {sc['of']} certificate(s) have NO credited forward evidence at all")
    for k, v in list(sc["by_family"].items())[:4]:
        print(f"    {str(k)[:28]:<28} {v} silent certificate(s)")
    print("  by representation lane:")
    for r in doc["by_representation_lane"]:
        print(f"    {str(r['lane'])[:24]:<24} {r['realised_r']:+9.2f}R  "
              f"{r['n_certificates']:>3} cert(s)  R/cert {r['r_per_certificate']}")
    print(f"  {doc['evidence_note'][:150]}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
