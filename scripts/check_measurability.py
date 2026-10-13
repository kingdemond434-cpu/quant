#!/usr/bin/env python3
"""THE NEVER-UNMEASURED FENCE -- every certificate and every LIVE sleeve, every field, measured.

THE PRINCIPAL, 2026-10-13: "all sleeves must be able to be measureed all certs never unmeasured
excuse". UNMEASURED is an honest verdict (L1.28a) and an unacceptable END STATE: a field may read
UNMEASURED for one cycle while its producer catches up, never longer. So this fence keeps the
first time each (subject, field) was seen UNMEASURED and turns it RED once that is older than
GRACE_S, and every UNMEASURED row names the CONVERTER that measures it -- the organ to run, on
which host -- so a red row is a work order, never a shrug.

THE SUBJECTS. Every certificate in the canon (`data/UNIVERSAL_SURVIVORS.canon.json`, else the
reports copy) and every LIVE row of `data/sleeves.json`, joined to its certificate through
`certificate.cell`.

THE FIELDS, each read from the artifact that already owns it (this fence measures nothing
itself):
    mechanism_class   research/alpha_genome.MECHANISM_CLASS declares the family's cause
    novelty           reports/STYLE_NOVELTY.json per_certificate[cert].novelty is a number
    fill_cost         data/cost_surface.json has a MEASURED spread hour for the symbol
    tradability       data/universe/universe.json carries the symbol's contract terms
                      (volume_min, volume_step, contract_size, tick_value) and bars
    forward_clock     reports/CERTIFICATE_CLOCK_LAW.json: the certificate has a clock that is
                      neither NO_CLOCK nor UNMEASURED
    pnl_attribution   LIVE sleeves only: reports/attribution_chain.json attributes deals to the
                      sleeve, or markout.json measured the account and found none for it
                      (MEASURED_ZERO is a measurement)

WHAT IT NEVER DOES. Size, veto, retire, enrol or disable anything. It reads, it dates, it names
the converter. Off the box most artifacts are absent and the verdict is NOT_APPLICABLE -- a
statement about the host, never a pass -- which is why it is a STATE fence (run_law_gate
_STATE_FENCES) and an hourly leg, never a commit gate.

    OK              (exit 0) every field of every subject measured
    UNMEASURED      (exit 0) some field unmeasured, all inside their one-cycle grace
    RED             (exit 2) some field unmeasured for longer than GRACE_S
    NOT_APPLICABLE  (exit 0) no certificate canon on this host

Run: python scripts/check_measurability.py [--json] [--now ISO]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
CERTS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
SLEEVES = DESK / "data" / "sleeves.json"
NOVELTY = DESK / "reports" / "STYLE_NOVELTY.json"
COST_SURFACE = DESK / "data" / "cost_surface.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
CLOCK_LAW = DESK / "reports" / "CERTIFICATE_CLOCK_LAW.json"
CHAIN = DESK / "reports" / "attribution_chain.json"
MARKOUT = DESK / "reports" / "markout.json"
REPORT = DESK / "reports" / "MEASURABILITY.json"
STATE = DESK / "data" / "measurability_state.json"

#: One hourly cycle plus its own runtime and the sync slot behind it.
GRACE_S = 2 * 3600.0
CONTRACT_TERMS = ("volume_min", "volume_step", "contract_size", "tick_value")

CONVERTERS: dict[str, str] = {
    "certificate": ("the LIVE row names a certificate the canon does not hold: the promoter "
                    "re-derives it (research/promoter.py) or the canon seal re-publishes it"),
    "mechanism_class": ("declare the family's cause in desks/mt5/research/alpha_genome.py "
                        "MECHANISM_CLASS (the style library owner)"),
    "novelty": ("research/style_novelty.py on the host that holds the symbol's bars -- the "
                "box's hourly leg style_novelty; --force when the report predates the cert"),
    "fill_cost": ("research/cost_surface.py on the box (it reads the symbol's spread column); a "
                  "symbol absent from the surface needs its bars collected first"),
    "tradability": ("refresh data/universe/universe.json from MT5 symbol_info on the box (the "
                    "universe refresh leg); a symbol the venue no longer lists is RETIRED "
                    "upstream, never left blank here"),
    "forward_clock": ("research/forward_enrolment.py (hourly, after the judge) enrols every "
                      "certificate; scripts/check_certificate_clock_law.py re-reads it"),
    "pnl_attribution": ("research/daily_cycle.py writes markout.json and attribution_chain.json "
                        "from the account's deals; research/attribution_reconcile.py routes the "
                        "unattributed ones"),
}


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _classes() -> dict[str, str] | None:
    try:
        from research.alpha_genome import MECHANISM_CLASS  # type: ignore[import-not-found]
        return dict(MECHANISM_CLASS)
    except Exception:
        return None


def _certificates() -> tuple[dict[str, dict[str, Any]], str]:
    for p in (CANON, CERTS):
        doc = _json(p)
        surv = doc.get("survivors") if isinstance(doc, dict) else None
        if isinstance(surv, dict) and surv:
            return {str(k): v for k, v in surv.items() if isinstance(v, dict)}, str(p)
    return {}, "no certificate canon on this host"


def _spec(cert: Mapping[str, Any]) -> tuple[str, str]:
    raw = cert.get("shadow_spec")
    spec: dict[str, Any] = raw if isinstance(raw, dict) else {}
    sym = str(spec.get("symbol") or cert.get("sym") or "").upper()
    fam = str(spec.get("family") or cert.get("family") or "")
    if not fam:
        parts = str(cert.get("cell") or "").split(".")
        fam = parts[1] if len(parts) > 1 else ""
    return sym, fam


def _field(ok: bool | None, why: str, **extra: Any) -> dict[str, Any]:
    status = "MEASURED" if ok else "UNMEASURED"
    return {"status": status, "why": why, **extra}


def cert_fields(cid: str, cert: Mapping[str, Any], *, classes: Mapping[str, str] | None,
                novelty: Any, surface: Any, universe: Any, clocks: Mapping[str, Any]
                ) -> dict[str, dict[str, Any]]:
    sym, fam = _spec(cert)
    out: dict[str, dict[str, Any]] = {}
    if classes is None:
        out["mechanism_class"] = _field(False, "research/alpha_genome did not import here")
    else:
        cls = classes.get(fam)
        out["mechanism_class"] = _field(cls is not None, f"{fam} -> {cls}" if cls else
                                        f"family {fam!r} is not declared", value=cls)
    per = (novelty or {}).get("per_certificate") if isinstance(novelty, dict) else None
    if not isinstance(per, dict):
        out["novelty"] = _field(False, "reports/STYLE_NOVELTY.json absent or unreadable")
    else:
        e = per.get(cid) if isinstance(per.get(cid), dict) else None
        v = (e or {}).get("novelty")
        out["novelty"] = _field(isinstance(v, (int, float)) and math.isfinite(float(v)),
                                ("novelty " + str(v)) if v is not None else
                                str((e or {}).get("why") or "the report has no row for it"),
                                value=v)
    syms = (surface or {}).get("symbols") if isinstance(surface, dict) else None
    if not isinstance(syms, dict):
        out["fill_cost"] = _field(False, "data/cost_surface.json absent or unreadable")
    else:
        hours = ((syms.get(sym) or {}).get("hours") or {}) if isinstance(syms.get(sym), dict) \
            else {}
        n = sum(1 for h in hours.values() if isinstance(h, dict)
                and h.get("status") == "MEASURED")
        out["fill_cost"] = _field(n > 0, f"{n} of {len(hours)} broker hours measured for {sym}"
                                  if hours else f"{sym} is absent from the cost surface",
                                  measured_hours=n)
    row = (universe or {}).get(sym) if isinstance(universe, dict) else None
    if not isinstance(universe, dict):
        out["tradability"] = _field(False, "universe.json absent or unreadable")
    elif not isinstance(row, dict):
        out["tradability"] = _field(False, f"{sym} is absent from universe.json")
    else:
        missing = [k for k in CONTRACT_TERMS if row.get(k) in (None, "", 0)]
        bars = row.get("bars")
        ok = not missing and bool(bars)
        out["tradability"] = _field(ok, "contract terms and bars present" if ok else
                                    f"missing {missing or []}{'' if bars else ' and bars'}")
    c = clocks.get(cid)
    if not clocks:
        out["forward_clock"] = _field(False, "reports/CERTIFICATE_CLOCK_LAW.json absent")
    elif not isinstance(c, dict):
        out["forward_clock"] = _field(False, "the clock law has no row for this certificate")
    else:
        verdict, status = str(c.get("verdict") or ""), str(c.get("status") or "")
        ok = verdict not in ("", "NO_CLOCK") and status != "UNMEASURED"
        out["forward_clock"] = _field(ok, f"verdict {verdict}, status {status}, n={c.get('n')}")
    return out


def sleeve_attribution(name: str, chain: Any, markout: Any) -> dict[str, Any]:
    rows = (chain or {}).get("chain") if isinstance(chain, dict) else None
    if isinstance(rows, list):
        n = sum(1 for r in rows if isinstance(r, dict) and str(r.get("sleeve")) == name)
        if n:
            return _field(True, f"{n} attributed deal(s)", deals=n)
    if isinstance(markout, dict) and markout.get("n_deals") is not None:
        return {"status": "MEASURED_ZERO", "deals": 0,
                "why": f"markout measured {markout.get('n_deals')} account deals, none this "
                       "sleeve's"}
    return _field(False, "neither attribution_chain.json nor markout.json is readable here")


def measure(now: datetime | None = None) -> dict[str, Any]:
    at = now or _now()
    certs, source = _certificates()
    doc: dict[str, Any] = {"generated_utc": at.isoformat(timespec="seconds"), "source": source,
                           "grace_s": GRACE_S, "converters": CONVERTERS}
    if not certs:
        doc.update({"verdict": "NOT_APPLICABLE", "subjects": {}, "red": [], "unmeasured": []})
        return doc
    classes = _classes()
    novelty, surface, universe = _json(NOVELTY), _json(COST_SURFACE), _json(UNIVERSE)
    law = _json(CLOCK_LAW)
    clocks = {str(r.get("certificate")): r for r in ((law or {}).get("certificates") or [])
              if isinstance(r, dict)} if isinstance(law, dict) else {}
    subjects: dict[str, dict[str, Any]] = {}
    for cid, cert in sorted(certs.items()):
        subjects[f"cert:{cid}"] = {"kind": "certificate", "fields": cert_fields(
            cid, cert, classes=classes, novelty=novelty, surface=surface, universe=universe,
            clocks=clocks)}
    sl = _json(SLEEVES)
    chain, markout = _json(CHAIN), _json(MARKOUT)
    live = [s for s in ((sl or {}).get("sleeves") or []) if isinstance(s, dict)
            and str(s.get("status")) == "LIVE"] if isinstance(sl, dict) else []
    for s in live:
        name = str(s.get("name"))
        cid = str((s.get("certificate") or {}).get("cell") or "")
        scert = certs.get(cid)
        fields = (cert_fields(cid, scert, classes=classes, novelty=novelty, surface=surface,
                              universe=universe, clocks=clocks) if scert else
                  {"certificate": _field(False, f"certificate.cell {cid!r} is not in the canon")})
        fields["pnl_attribution"] = sleeve_attribution(name, chain, markout)
        subjects[f"sleeve:{name}"] = {"kind": "live_sleeve", "certificate": cid,
                                      "fields": fields}
    doc["subjects"] = subjects
    doc["n_certificates"], doc["n_live_sleeves"] = len(certs), len(live)
    return doc


def judge(doc: dict[str, Any], state: dict[str, Any], now: datetime | None = None
          ) -> tuple[dict[str, Any], dict[str, Any]]:
    """Date each UNMEASURED (subject, field), RED past grace, and the state to keep."""
    at = now or _now()
    if doc.get("verdict") == "NOT_APPLICABLE":
        return doc, state
    first: dict[str, str] = dict(state.get("first_unmeasured") or {})
    keep: dict[str, str] = {}
    red: list[str] = []
    unmeasured: list[str] = []
    by_field: dict[str, int] = {}
    for sid, subj in doc["subjects"].items():
        for fname, f in subj["fields"].items():
            if f.get("status") not in ("UNMEASURED",):
                continue
            key = f"{sid}|{fname}"
            since = first.get(key) or at.isoformat(timespec="seconds")
            keep[key] = since
            age = (at - datetime.fromisoformat(since)).total_seconds()
            f.update({"unmeasured_since": since, "age_h": round(age / 3600.0, 2),
                      "converter": CONVERTERS.get(fname, "name the producer that owns it")})
            by_field[fname] = by_field.get(fname, 0) + 1
            (red if age > GRACE_S else unmeasured).append(key)
            f["red"] = age > GRACE_S
    doc.update({"red": sorted(red), "unmeasured": sorted(unmeasured),
                "unmeasured_by_field": dict(sorted(by_field.items(), key=lambda kv: -kv[1])),
                "verdict": "RED" if red else ("UNMEASURED" if unmeasured else "OK")})
    return doc, {"first_unmeasured": keep, "updated_utc": at.isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now", help="ISO time to judge at (tests)")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)
    now = datetime.fromisoformat(args.now) if args.now else None
    doc = measure(now)
    state = _json(STATE) or {}
    doc, new_state = judge(doc, state if isinstance(state, dict) else {}, now)
    if not args.no_write and doc.get("verdict") != "NOT_APPLICABLE":
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(new_state, indent=1), "utf-8")
    if args.json:
        print(json.dumps({k: doc.get(k) for k in ("verdict", "n_certificates", "n_live_sleeves",
                                                  "unmeasured_by_field", "red")}, default=str))
    else:
        print(f"measurability: {doc.get('verdict')} -- {doc.get('n_certificates', 0)} certs, "
              f"{doc.get('n_live_sleeves', 0)} LIVE sleeves; unmeasured by field "
              f"{doc.get('unmeasured_by_field', {})}; red {len(doc.get('red') or [])}")
        for key in (doc.get("red") or [])[:15]:
            sid, fname = key.rsplit("|", 1)
            f = doc["subjects"][sid]["fields"][fname]
            print(f"   RED {sid[:70]:70} {fname:16} {f.get('age_h')}h -- {f.get('why')}")
    return 2 if doc.get("verdict") == "RED" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
