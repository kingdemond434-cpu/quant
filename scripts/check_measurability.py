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
    fill_cost         reports/FILL_HOUR_REPRICE.json (the owner) prices the cert at its own fill
                      hour; a cert in its `cost_never_charged` is UNMEASURED. Only without a
                      row there: data/cost_surface.json has a MEASURED spread hour for it
    tradability       reports/LIVE_TRADABILITY.json (the owner, #331) for a LIVE sleeve; else
                      data/universe/universe.json carries the symbol's contract terms
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
import os
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
#: The owners, read first when present (one truth per field): the fill-hour repricer (the
#: AUDCHF/promotion lane's `fill_hour_reprice` leg) and the live tradability check (#331).
FILL_REPRICE = DESK / "reports" / "FILL_HOUR_REPRICE.json"
LIVE_TRADABILITY = DESK / "reports" / "LIVE_TRADABILITY.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
CLOCK_LAW = DESK / "reports" / "CERTIFICATE_CLOCK_LAW.json"
CHAIN = DESK / "reports" / "attribution_chain.json"
MARKOUT = DESK / "reports" / "markout.json"   # counts only: its slip_r is not read (units)
REPORT = DESK / "reports" / "MEASURABILITY.json"
STATE = DESK / "data" / "measurability_state.json"

#: One hourly cycle plus its own runtime and the sync slot behind it.
GRACE_S = 2 * 3600.0
#: FRESHNESS (audit of #387). A field reads MEASURED only while the artifact that owns it is
#: younger than STALE_CADENCES of its own cadence, judged on the artifact's OWN stamp (never the
#: file's mtime, which a clone or a sync resets). Older reads STALE, which is dated and turns RED
#: exactly like UNMEASURED: a 21-day-old cost surface is a memory of a measurement, not one.
STALE_CADENCES = 3.0
CADENCE_S: dict[str, float] = {
    "novelty": 24 * 3600.0,        # style_novelty: a full stalest-first sweep a day
    "cost_surface": 24 * 3600.0,   # the cost_surfaces leg
    "fill_reprice": 3600.0,        # the hourly fill_hour_reprice leg
    "live_tradability": 3600.0,    # the hourly live_tradability leg
    "universe": 7 * 24 * 3600.0,   # contract terms: the universe refresh leg
    "clock_law": 3600.0,           # the hourly certificate_clock_law leg
    "attribution": 24 * 3600.0,    # daily_cycle writes markout.json and attribution_chain.json
}
STAMP_KEYS = ("generated_utc", "generated_at", "built_at", "at", "updated_at", "measured_at")
#: The clock law's verdicts that mean a clock is running and readable. Everything else --
#: NO_CLOCK, FROZEN_ROWS (rows stopped advancing), BLOCKED (IDENTITY_BROKEN, BLOCKED_NO_BARS),
#: UNMEASURED_* -- is a clock the desk cannot read forward evidence from.
CLOCK_MEASURED = frozenset({"ACCUMULATING", "WARMING", "DECIDED"})
CONTRACT_TERMS = ("volume_min", "volume_step", "contract_size", "tick_value")

CONVERTERS: dict[str, str] = {
    "certificate": ("the LIVE row names a certificate the canon does not hold: the promoter "
                    "re-derives it (research/promoter.py) or the canon seal re-publishes it"),
    "mechanism_class": ("declare the family's cause in desks/mt5/research/alpha_genome.py "
                        "MECHANISM_CLASS (the style library owner)"),
    "novelty": ("research/style_novelty.py on the host that holds the symbol's bars -- the "
                "box's hourly leg style_novelty; --force when the report predates the cert"),
    "fill_cost": ("the fill_hour_reprice leg prices the cert at its own fill hour (a cert in "
                  "cost_never_charged was judged on a cost it never paid); without it, "
                  "research/cost_surface.py on the box (it reads the symbol's spread column); a "
                  "symbol absent from the surface needs its bars collected first"),
    "tradability": ("scripts/check_live_tradability.py (hourly leg live_tradability) for LIVE "
                    "sleeves; for a certificate, refresh data/universe/universe.json from MT5 symbol_info on the box (the "
                    "universe refresh leg); a symbol the venue no longer lists is RETIRED "
                    "upstream, never left blank here"),
    "forward_clock": ("research/forward_enrolment.py (hourly, after the judge) enrols every "
                      "certificate; scripts/check_certificate_clock_law.py re-reads it. "
                      "FROZEN_ROWS: research/shadow_forward.py is not advancing the clock's "
                      "rows; BLOCKED: repair the clock's identity or collect the bars it lacks"),
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


def _stamp(doc: Any) -> datetime | None:
    """The artifact's own stamp, from the first STAMP_KEYS key that parses (naive = UTC)."""
    if not isinstance(doc, dict):
        return None
    for k in STAMP_KEYS:
        v = doc.get(k)
        if not v:
            continue
        try:
            t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            continue
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    return None


def staleness(doc: Any, owner: str, at: datetime) -> str | None:
    """None when `doc` is fresh for `owner`'s cadence, else why it is STALE."""
    limit = STALE_CADENCES * CADENCE_S[owner]
    t = _stamp(doc)
    if t is None:
        return f"{owner}: the artifact carries no readable stamp ({'/'.join(STAMP_KEYS)})"
    age = (at - t).total_seconds()
    if age < 0:
        return f"{owner}: stamped {t.isoformat()} in the future"
    if age > limit:
        return (f"{owner}: stamped {t.isoformat(timespec='seconds')}, {age / 3600.0:.1f}h old "
                f"against a {limit / 3600.0:.0f}h limit ({STALE_CADENCES:g} cadences)")
    return None


def _age_gate(f: dict[str, Any], stale: str | None) -> dict[str, Any]:
    """A MEASURED (or MEASURED_ZERO) field read from a stale artifact becomes STALE."""
    if stale and f.get("status") in ("MEASURED", "MEASURED_ZERO"):
        f = {**f, "status": "STALE", "why": f"{f.get('why')} -- but {stale}"}
    return f


def _reprice_row(reprice: Any, cid: str, cert: Mapping[str, Any]) -> tuple[str, Any]:
    """(state, row) from FILL_HOUR_REPRICE.json: ABSENT, NEVER_CHARGED, or ROW."""
    if not isinstance(reprice, dict):
        return "ABSENT", None
    raw = cert.get("shadow_spec")
    spec: dict[str, Any] = raw if isinstance(raw, dict) else {}
    # Exact identities only (audit of #387): SYM.family.selector is shared by up to 8 certs in
    # 11 groups, so a key built from it can hand one cert another's repricing.
    del spec
    keys = [cid, str(cert.get("cell") or "")]
    never = reprice.get("cost_never_charged")
    if isinstance(never, dict) and any(k and k in never for k in keys):
        return "NEVER_CHARGED", next(never[k] for k in keys if k and k in never)
    certs = reprice.get("certificates")
    if isinstance(certs, dict):
        for k in keys:
            if k and isinstance(certs.get(k), dict):
                return "ROW", certs[k]
    return "ABSENT", None


def cert_fields(cid: str, cert: Mapping[str, Any], *, classes: Mapping[str, str] | None,
                novelty: Any, surface: Any, universe: Any, clocks: Mapping[str, Any],
                reprice: Any = None, stale: Mapping[str, str | None] | None = None,
                at: datetime | None = None) -> dict[str, dict[str, Any]]:
    """Each field from its owner. `stale` maps an owner (CADENCE_S) to why its artifact is
    STALE (None = fresh); an owner absent from it is judged fresh (direct callers, tests)."""
    old = dict(stale or {})
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
        why = str((e or {}).get("why") or "the report has no row for it")
        f = _field(isinstance(v, (int, float)) and math.isfinite(float(v)),
                   ("novelty " + str(v)) if v is not None else why, value=v)
        if v is None and "usable signal" in why:
            # A cert that fires no usable signal on the bars this host holds cannot be projected:
            # no rerun of style_novelty fixes it, so the work order names the bars.
            f["converter"] = ("the certificate fires no usable signal on the bars this host "
                              "holds: collect its symbol's bars over its certified window (the "
                              "bar collector on the box), or the promoter re-derives the cert")
        out["novelty"] = _age_gate(f, old.get("novelty"))
    syms = (surface or {}).get("symbols") if isinstance(surface, dict) else None
    rstate, rrow = _reprice_row(reprice, cid, cert)
    if rstate == "NEVER_CHARGED":
        out["fill_cost"] = _field(False, "FILL_HOUR_REPRICE lists it in cost_never_charged: "
                                  "judged on a cost it never paid", source="fill_hour_reprice",
                                  detail=rrow)
    elif rstate == "ROW" and str(rrow.get("verdict") or "").upper() != "OUT_OF_SCOPE":
        v = str(rrow.get("verdict") or "")
        # The owner writes "UNMEASURED: <status>", so the test is a prefix, never equality.
        out["fill_cost"] = _age_gate(_field(bool(v) and not v.upper().startswith("UNMEASURED"),
                                            f"fill_hour_reprice verdict {v}",
                                            source="fill_hour_reprice", value=v),
                                     old.get("fill_reprice"))
    elif not isinstance(syms, dict):
        out["fill_cost"] = _field(False, "data/cost_surface.json absent or unreadable")
    else:
        hours = ((syms.get(sym) or {}).get("hours") or {}) if isinstance(syms.get(sym), dict) \
            else {}
        n = sum(1 for h in hours.values() if isinstance(h, dict)
                and h.get("status") == "MEASURED")
        out["fill_cost"] = _age_gate(_field(
            n > 0, f"{n} of {len(hours)} broker hours measured for {sym}"
            if hours else f"{sym} is absent from the cost surface",
            measured_hours=n, source="cost_surface (fallback)"
            + (" -- the repricer rules it OUT_OF_SCOPE" if rstate == "ROW" else "")),
            old.get("cost_surface"))
    row = (universe or {}).get(sym) if isinstance(universe, dict) else None
    if not isinstance(universe, dict):
        out["tradability"] = _field(False, "universe.json absent or unreadable")
    elif not isinstance(row, dict):
        out["tradability"] = _field(False, f"{sym} is absent from universe.json")
    else:
        missing = [k for k in CONTRACT_TERMS if row.get(k) in (None, "", 0)]
        bars = row.get("bars")
        ok = not missing and bool(bars)
        f = _field(ok, "contract terms and bars present" if ok else
                   f"missing {missing or []}{'' if bars else ' and bars'}")
        # Contract terms are dated per symbol (the refresh stamps each row), so each row is aged
        # on its own stamp.
        out["tradability"] = _age_gate(f, staleness(row, "universe", at) if at else None)
    c = clocks.get(cid)
    if not clocks:
        out["forward_clock"] = _field(False, "reports/CERTIFICATE_CLOCK_LAW.json absent")
    elif not isinstance(c, dict):
        out["forward_clock"] = _field(False, "the clock law has no row for this certificate")
    else:
        verdict, status = str(c.get("verdict") or ""), str(c.get("status") or "")
        ok = verdict in CLOCK_MEASURED and status != "UNMEASURED"
        out["forward_clock"] = _age_gate(
            _field(ok, f"verdict {verdict}, status {status}, n={c.get('n')}", value=verdict),
            old.get("clock_law"))
    return out


def sleeve_attribution(name: str, chain: Any, markout: Any,
                       stale: str | None = None) -> dict[str, Any]:
    """Attributed deals, else MEASURED_ZERO -- but only when markout is FRESH and left no deal
    unmatched: an unmatched deal could be this sleeve's, so with any outstanding the honest
    reading is NO_DEALS (unmeasured), never zero (audit of #387)."""
    rows = (chain or {}).get("chain") if isinstance(chain, dict) else None
    if isinstance(rows, list):
        n = sum(1 for r in rows if isinstance(r, dict) and str(r.get("sleeve")) == name)
        if n:
            return _age_gate(_field(True, f"{n} attributed deal(s)", deals=n), stale)
    if isinstance(markout, dict) and markout.get("n_deals") is not None:
        unmatched = markout.get("n_unmatched_deals")
        if stale:
            return {"status": "UNMEASURED", "deals": 0, "label": "NO_DEALS",
                    "why": f"no attributed deal, and markout cannot vouch for zero: {stale}"}
        if not isinstance(unmatched, (int, float)) or unmatched != 0:
            return {"status": "UNMEASURED", "deals": 0, "label": "NO_DEALS",
                    "why": f"no attributed deal, but markout holds {unmatched} unmatched account "
                           "deal(s) that could be this sleeve's"}
        return {"status": "MEASURED_ZERO", "deals": 0,
                "why": f"markout measured {markout.get('n_deals')} account deals, all matched, "
                       "none this sleeve's"}
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
    reprice = _json(FILL_REPRICE)
    clocks = {str(r.get("certificate")): r for r in ((law or {}).get("certificates") or [])
              if isinstance(r, dict)} if isinstance(law, dict) else {}
    lt = _json(LIVE_TRADABILITY)
    chain, markout = _json(CHAIN), _json(MARKOUT)
    stale: dict[str, str | None] = {
        "novelty": staleness(novelty, "novelty", at), "cost_surface":
        staleness(surface, "cost_surface", at), "fill_reprice": staleness(reprice, "fill_reprice",
                                                                          at),
        "clock_law": staleness(law, "clock_law", at),
        "live_tradability": staleness(lt, "live_tradability", at),
        "attribution": staleness(markout, "attribution", at)}
    doc["stale_owners"] = {k: v for k, v in stale.items() if v}
    subjects: dict[str, dict[str, Any]] = {}
    for cid, cert in sorted(certs.items()):
        subjects[f"cert:{cid}"] = {"kind": "certificate", "fields": cert_fields(
            cid, cert, classes=classes, novelty=novelty, surface=surface, universe=universe,
            clocks=clocks, reprice=reprice, stale=stale, at=at)}
    trad = {str(r.get("name")): r for r in ((lt or {}).get("sleeves") or [])
            if isinstance(r, dict)} if isinstance(lt, dict) else {}
    sl = _json(SLEEVES)
    live = [s for s in ((sl or {}).get("sleeves") or []) if isinstance(s, dict)
            and str(s.get("status")) == "LIVE"] if isinstance(sl, dict) else []
    for s in live:
        name = str(s.get("name"))
        cid = str((s.get("certificate") or {}).get("cell") or "")
        scert = certs.get(cid)
        fields = (cert_fields(cid, scert, classes=classes, novelty=novelty, surface=surface,
                              universe=universe, clocks=clocks, reprice=reprice, stale=stale,
                              at=at) if scert else
                  {"certificate": _field(False, f"certificate.cell {cid!r} is not in the canon")})
        own = trad.get(name)
        if own is not None:
            st = str(own.get("status") or "")
            fields["tradability"] = _age_gate(_field(
                bool(st) and not st.upper().startswith("UNMEASURED"), f"live_tradability {st}",
                value=st, source="LIVE_TRADABILITY.json"), stale["live_tradability"])
        fields["pnl_attribution"] = sleeve_attribution(name, chain, markout,
                                                       stale["attribution"])
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
            if f.get("status") not in ("UNMEASURED", "STALE"):
                continue
            key = f"{sid}|{fname}"
            since = first.get(key) or at.isoformat(timespec="seconds")
            keep[key] = since
            age = (at - datetime.fromisoformat(since)).total_seconds()
            f.update({"unmeasured_since": since, "age_h": round(age / 3600.0, 2),
                      "converter": f.get("converter")
                      or CONVERTERS.get(fname, "name the producer that owns it")})
            by_field[fname] = by_field.get(fname, 0) + 1
            (red if age > GRACE_S else unmeasured).append(key)
            f["red"] = age > GRACE_S
    doc.update({"red": sorted(red), "unmeasured": sorted(unmeasured),
                "unmeasured_by_field": dict(sorted(by_field.items(), key=lambda kv: -kv[1])),
                # counts, so the leg's experiment contract can read a number
                "n_subjects": len(doc["subjects"]), "n_red": len(red),
                "n_unmeasured": len(red) + len(unmeasured),
                "verdict": "RED" if red else ("UNMEASURED" if unmeasured else "OK")})
    return doc, {"first_unmeasured": keep, "updated_utc": at.isoformat(timespec="seconds")}


def _atomic(path: Path, text: str) -> None:
    """Temp file then os.replace: the hourly leg and the law gate both write the state, and a torn
    file would reset every first-unmeasured date (audit of #387)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now", help="ISO time to judge at (tests)")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)
    now = datetime.fromisoformat(args.now) if args.now else None
    if now is not None and now.tzinfo is None:
        now = now.replace(tzinfo=UTC)          # a naive --now is read as UTC, never a crash
    doc = measure(now)
    state = _json(STATE) or {}
    doc, new_state = judge(doc, state if isinstance(state, dict) else {}, now)
    if not args.no_write and doc.get("verdict") != "NOT_APPLICABLE":
        _atomic(REPORT, json.dumps(doc, indent=1, default=str))
        _atomic(STATE, json.dumps(new_state, indent=1))
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
