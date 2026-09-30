"""THE ARGENTINE LANE: the BCRA official leg, three parallel legs, and the BRECHA as a regime.

    python -m research.countries.ar.data_plane --catalogue
    python -m research.countries.ar.data_plane --brecha --dry-run
    python -m research.countries.ar.data_plane --fetch          # the ONLY way to reach the network

THE BRECHA is the ratio of a parallel dollar to the official A3500 rate, minus one. It is a SET
of gaps, not one number -- blue (informal cash), MEP (bond bought in pesos, sold in dollars
onshore) and CCL (the same trade settled offshore) -- and each is published daily and free, which
makes capital-control intensity a continuous series rather than the dummy variable every
cross-country panel uses for it.

THE REGIME DETECTOR. `BANDS` cuts the whole real line into five declared states. A transition is
recorded only when `PERSISTENCE` consecutive observations sit in the same new band, and it is
DATED TO THE FIRST of them -- `confirmed_on` is the day the rule was satisfied, which is a
different and later day, and dating an event study to the confirmation instead would put every
effect after its cause. A one-day excursion across an edge is NOT a transition: a detector that
fires on noise dates every downstream event study to noise.

ONLY THE SELL SIDE. Every parallel leg is the tracker's `venta`. A brecha built from a bid on one
leg and an ask on the other is part spread, and the spread is exactly what changes when a market
gets thin. The MEP-CCL spread divides the peso out entirely: it is the pure price of settling
offshore under a control regime.

A MISSING LEG IS UNMEASURED BY NAME. A ratio with one leg is not a small brecha.

The tracker is PINNED: argentinadatos.com (the historical endpoint of the dolarapi family), one
source for all three parallel legs, so a gap between legs is never a gap between two trackers.
No credential is needed anywhere in this lane. The vintage store, `read_pit` and the CLI are the
shared engine in `countries/br/data_plane.py`.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[3]
if str(DESK) not in sys.path:                      # `python path/to/data_plane.py` still works
    sys.path.insert(0, str(DESK))

from research.countries.br import data_plane as E  # noqa: E402  (the shared lane engine)

LANE = "ar"
STORE = DESK / "data" / "latam" / LANE
REPORT = DESK / "reports" / "SOUTH_AMERICA_AR_PLANE.json"
SECRETS = E.SECRETS
OK, UNMEASURED = E.OK, E.UNMEASURED

OFFICIAL = "BCRA_A3500"
#: brecha kind -> the parallel leg's series id.
PARALLEL: dict[str, str] = {"blue": "AR_DOLAR_BLUE", "mep": "AR_DOLAR_MEP",
                            "ccl": "AR_DOLAR_CCL"}
#: (band, lower edge) in ascending order; the first band is open below, so every gap -- a
#: negative one included -- has exactly one band.
BANDS: tuple[tuple[str, float], ...] = (
    ("convertible", float("-inf")),
    ("managed", 0.05),
    ("cepo_light", 0.25),
    ("cepo_hard", 0.60),
    ("cepo_extreme", 1.50),
)
#: Consecutive observations in a new band before a transition is recorded.
PERSISTENCE = 3


# --------------------------------------------------------------------------- parsers
def parse_bcra(payload: Any, currency: str = "USD") -> list[dict[str, Any]]:
    """Both BCRA shapes: flat `{fecha, valor}` rows, and rows whose `detalle` holds either
    per-currency quotes (`codigoMoneda`, `tipoCotizacion`) or dated values (`fecha`, `valor`)."""
    results = payload.get("results") if isinstance(payload, Mapping) else payload
    out: dict[str, float] = {}
    for r in results if isinstance(results, list) else []:
        if not isinstance(r, Mapping):
            continue
        detail = r.get("detalle")
        if isinstance(detail, list):
            for d in detail:
                if not isinstance(d, Mapping):
                    continue
                if "codigoMoneda" in d:
                    if str(d.get("codigoMoneda")) != currency:
                        continue
                    day, val = E.iso(r.get("fecha")), E.to_float(d.get("tipoCotizacion"))
                else:
                    day, val = E.iso(d.get("fecha")), E.to_float(d.get("valor"))
                if day and val is not None:
                    out[day] = val
            continue
        day, val = E.iso(r.get("fecha")), E.to_float(r.get("valor"))
        if day and val is not None:
            out[day] = val
    return [{"observation_date": d, "value": out[d]} for d in sorted(out)]


def parse_tracker(payload: Any, casa: str = "blue") -> list[dict[str, Any]]:
    """A parallel-rate tracker -> the SELL side (`venta`) of one `casa`, by day."""
    items = [payload] if isinstance(payload, Mapping) else payload
    out: dict[str, float] = {}
    for r in items if isinstance(items, list) else []:
        if not isinstance(r, Mapping):
            continue
        if r.get("casa") not in (None, casa):
            continue
        day = E.iso(r.get("fecha") or r.get("fechaActualizacion"))
        val = E.to_float(r.get("venta"))
        if day and val is not None:
            out[day] = val
    return [{"observation_date": d, "value": out[d]} for d in sorted(out)]


# --------------------------------------------------------------------------- the brecha
def band_of(gap: float) -> str:
    name = BANDS[0][0]
    for band, lower in BANDS:
        if gap >= lower:
            name = band
    return name


def _by_day(rows: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in rows or []:
        if not isinstance(r, Mapping):
            continue
        day, val = E.iso(r.get("observation_date")), E.to_float(r.get("value"))
        if day and val is not None and val > 0:
            out[day] = val
    return out


def brecha(official: Iterable[Mapping[str, Any]], parallel: Iterable[Mapping[str, Any]],
           kind: str = "blue") -> dict[str, Any]:
    """The gap series on common days, its band path and its DATED regime transitions."""
    off, par = _by_day(official), _by_day(parallel)
    days = sorted(set(off) & set(par))
    if not days:
        return {"outcome": UNMEASURED, "kind": kind, "state": None, "n_obs": 0,
                "n_transitions": 0, "transitions": [],
                "why": (f"no common day between the official leg ({len(off)} obs) and the "
                        f"{kind} leg ({len(par)} obs); a ratio with one leg is not a small "
                        "brecha")}
    gaps = [(d, par[d] / off[d] - 1.0) for d in days]
    state = band_of(gaps[0][1])
    transitions: list[dict[str, Any]] = []
    run_band, run_start, run_len = None, "", 0
    for day, gap in gaps[1:]:
        band = band_of(gap)
        if band == state:
            run_band, run_start, run_len = None, "", 0
            continue
        if band == run_band:
            run_len += 1
        else:
            run_band, run_start, run_len = band, day, 1
        if run_len >= PERSISTENCE:
            transitions.append({"from": state, "to": band, "date": run_start,
                                "confirmed_on": day, "gap_at_date": round(dict(gaps)[run_start], 6),
                                "persistence": PERSISTENCE})
            state, run_band, run_start, run_len = band, None, "", 0
    last_day, last_gap = gaps[-1]
    return {"outcome": OK, "kind": kind, "state": state, "as_of": last_day,
            "gap": round(last_gap, 6), "band_of_last": band_of(last_gap),
            "pending": ({"band": run_band, "since": run_start, "observations": run_len}
                        if run_band else None),
            "n_obs": len(gaps), "n_transitions": len(transitions), "transitions": transitions,
            "bands": [{"band": b, "from": lo} for b, lo in BANDS], "persistence": PERSISTENCE,
            "why": f"{kind} brecha {last_gap:+.1%} on {last_day}: {state}"}


def brecha_state(root: Any = None, as_of: str | date | None = None,
                 kind: str = "blue") -> dict[str, Any]:
    """The brecha of `kind` from what the store held on the morning of `as_of`."""
    if E.is_lab_call(root):
        return E.lab_result("ar_brecha_state", brecha_state(STORE, E.today(), "blue"))
    store = root if root is not None else STORE
    day = as_of if as_of is not None else E.today()
    leg = PARALLEL.get(kind)
    if leg is None:
        return {"outcome": UNMEASURED, "kind": kind, "missing_legs": [],
                "why": f"unknown brecha kind {kind!r}; declared: {sorted(PARALLEL)}"}
    reads = {sid: E.read_pit(sid, day, store) for sid in (OFFICIAL, leg)}
    missing = [sid for sid, got in reads.items() if got["outcome"] != OK]
    if missing:
        return {"outcome": UNMEASURED, "kind": kind, "state": None, "missing_legs": missing,
                "why": "; ".join(f"{sid}: {reads[sid]['why']}" for sid in missing)
                       + " -- a ratio with one leg is not a small brecha"}
    got = brecha(reads[OFFICIAL]["rows"], reads[leg]["rows"], kind=kind)
    return {**got, "missing_legs": [],
            "vintages": {sid: r["vintage"] for sid, r in reads.items()}}


def mep_ccl_spread(mep: Iterable[Mapping[str, Any]], ccl: Iterable[Mapping[str, Any]]
                   ) -> dict[str, Any]:
    """CCL / MEP - 1 on common days: the price of settling offshore, with the peso divided out."""
    a, b = _by_day(mep), _by_day(ccl)
    days = sorted(set(a) & set(b))
    if not days:
        return {"outcome": UNMEASURED, "spread": None,
                "why": "the MEP-CCL spread needs both legs on a common day"}
    series = [{"observation_date": d, "value": round(b[d] / a[d] - 1.0, 6)} for d in days]
    return {"outcome": OK, "as_of": days[-1], "spread": b[days[-1]] / a[days[-1]] - 1.0,
            "n_obs": len(series), "series": series,
            "why": f"MEP-CCL spread on {days[-1]}"}


# --------------------------------------------------------------------------- the catalogue
def _url_for(s: E.Series, held: Mapping[str, str], day: date) -> tuple[str, dict[str, str]]:
    del held
    pid = str(s.provider_id)
    if s.provider == "bcra":
        start = day - timedelta(days=E.HISTORY_DAYS)
        return ("https://api.bcra.gob.ar/estadisticas/v3.0/monetarias/"
                f"{pid}?desde={start.isoformat()}&hasta={day.isoformat()}&limit=3000"), {}
    if s.provider == "ar_tracker":
        return f"https://api.argentinadatos.com/v1/cotizaciones/dolares/{pid}", {}
    raise ValueError(f"no URL rule for provider {s.provider}")


PROVIDERS: tuple[E.Provider, ...] = (
    E.Provider("bcra", "BCRA estadisticas API v3.0 (no key)"),
    E.Provider("ar_tracker", "argentinadatos.com parallel-rate history (no key, pinned)"),
)

_TRACKER_WHY = ("vintages start at the first capture; the tracker's own history is a backfill "
                "and a read before the first vintage is refused as lookahead")

SERIES: tuple[E.Series, ...] = (
    E.Series(OFFICIAL, "ar", "bcra", "Tipo de cambio mayorista de referencia (Com. A 3500)",
             "daily", 0.0, "the OFFICIAL leg of every brecha in this lane", "bcra", "5"),
    E.Series("BCRA_RESERVES", "ar", "bcra", "Reservas internacionales del BCRA (gross)",
             "daily", 1.0, "the reserve state a brecha regime change is priced against",
             "bcra", "1"),
    E.Series("AR_DOLAR_BLUE", "ar", "ar_tracker", "Dolar blue (informal), sell side",
             "daily", 0.0, f"the informal-cash leg of the brecha; {_TRACKER_WHY}", "tracker",
             "blue", options=(("casa", "blue"),)),
    E.Series("AR_DOLAR_MEP", "ar", "ar_tracker", "Dolar MEP (bolsa), sell side", "daily", 0.0,
             f"the onshore bond-trade leg and one side of the MEP-CCL spread; {_TRACKER_WHY}",
             "tracker", "bolsa", options=(("casa", "bolsa"),)),
    E.Series("AR_DOLAR_CCL", "ar", "ar_tracker", "Dolar contado con liqui, sell side", "daily",
             0.0, f"the offshore-settled leg of the MEP-CCL spread; {_TRACKER_WHY}", "tracker",
             "contadoconliqui", options=(("casa", "contadoconliqui"),)),
    E.Series("BCRA_POLICY_RATE", "ar", "bcra", "BCRA policy rate", "daily", 1.0,
             "the peso carry leg; the policy instrument itself changed in 2024", "bcra",
             lookup_why="the policy-rate variable changed with the 2024 framework; its id must "
                        "be read from the monetarias variable LIST endpoint, not assumed"),
    E.Series("INDEC_IPC", "ar", "indec", "INDEC IPC nivel general", "monthly", 13.0,
             "the inflation print the brecha is partly a forecast of; usable from 2016-04 only",
             "bcra", lookup_why="the datos.gob.ar series id is not confirmed on this box, and "
                                "no parser for its shape is carried here yet"),
)

_LANE = E.Lane(LANE, SERIES, PROVIDERS, (("bcra", parse_bcra), ("tracker", parse_tracker)),
               _url_for)


def catalogue() -> list[dict[str, Any]]:
    return _LANE.catalogue()


def catalogue_status() -> dict[str, Any]:
    return _LANE.catalogue_status()


def key_status(secrets_path: Path | str | None = None) -> dict[str, Any]:
    return _LANE.key_status(secrets_path if secrets_path is not None else SECRETS)


def vintages(series_id: str, root: Path | str | None = None) -> tuple[str, ...]:
    return E.vintages(series_id, root if root is not None else STORE)


def read_pit(series_id: str, as_of: str | date, root: Path | str | None = None
             ) -> dict[str, Any]:
    return E.read_pit(series_id, as_of, root if root is not None else STORE)


def fetch(series: Iterable[str] | None = None, *args: Any, no_fetch: bool = True,
          fixtures: Path | str | None = None, root: Path | str | None = None,
          realtime: str | None = None, secrets_path: Path | str | None = None,
          timeout: float = 30.0) -> dict[str, Any]:
    """Fetch (or, by default, read fixtures for) the lane and add one vintage per series."""
    if E.is_lab_call(series):
        return E.lab_result("ar_bcra_lane", _LANE.store_summary(STORE))
    return _LANE.fetch(series, no_fetch=no_fetch, fixtures=fixtures,
                       root=root if root is not None else STORE, realtime=realtime,
                       secrets_path=secrets_path if secrets_path is not None else SECRETS,
                       timeout=timeout)


def report(*, root: Path | str | None = None, fixtures: Path | str | None = None,
           no_fetch: bool = True, secrets_path: Path | str | None = None,
           realtime: str | None = None, series: Iterable[str] | None = None,
           dry_run: bool = False, timeout: float = 30.0, with_brecha: bool = True
           ) -> dict[str, Any]:
    store = root if root is not None else STORE
    got = fetch(series, no_fetch=no_fetch, fixtures=fixtures, root=store, realtime=realtime,
                secrets_path=secrets_path, timeout=timeout)
    as_of = got["realtime_date"]
    doc: dict[str, Any] = {
        "lane": LANE, "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "catalogue_status": catalogue_status(), "key_status": key_status(secrets_path),
        "fetch": got,
        "pit": {s.series_id: {k: v for k, v in read_pit(s.series_id, as_of, store).items()
                              if k != "rows"}
                for s in SERIES if s.provider_id is not None},
        "written_to": None if dry_run else str(REPORT)}
    if with_brecha:
        doc["brecha"] = {kind: brecha_state(store, as_of, kind) for kind in PARALLEL}
        mep, ccl = read_pit("AR_DOLAR_MEP", as_of, store), read_pit("AR_DOLAR_CCL", as_of, store)
        doc["mep_ccl_spread"] = {k: v for k, v in mep_ccl_spread(mep["rows"], ccl["rows"]).items()
                                 if k != "series"}
    E.write_report(doc, REPORT, dry_run)
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    ap = E.lane_parser(LANE, __doc__)
    ap.add_argument("--brecha", action="store_true",
                    help="add the three brecha states and the MEP-CCL spread to the report")
    args = ap.parse_args(argv)
    if args.catalogue:
        print(json.dumps({"lane": LANE, "status": catalogue_status(), "catalogue": catalogue()},
                         indent=1, default=str))
        return 0
    if args.keys:
        print(json.dumps(key_status(args.secrets), indent=1))
        return 0
    doc = report(root=args.root, fixtures=args.fixtures, no_fetch=not args.fetch,
                 secrets_path=args.secrets, realtime=args.realtime, series=args.series,
                 dry_run=args.dry_run, timeout=args.timeout, with_brecha=args.brecha)
    out = E.summary(doc)
    if args.brecha:
        out["brecha"] = {k: {"outcome": v.get("outcome"), "state": v.get("state"),
                             "n_transitions": v.get("n_transitions")}
                         for k, v in doc.get("brecha", {}).items()}
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
