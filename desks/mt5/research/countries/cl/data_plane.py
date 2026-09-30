"""THE ANDEAN LANE: BCCh (Chile) and BCRP (Peru) in one vintage store, and the copper state.

    python -m research.countries.cl.data_plane --catalogue
    python -m research.countries.cl.data_plane --keys           # PRESENT / ABSENT, never a value
    python -m research.countries.cl.data_plane --fetch          # the ONLY way to reach the network

WHY CHILE AND PERU SHARE ONE LANE. The BCCh statistical API (SieteRestWS) needs a registered user
and password; BCRP's needs nothing. Without `bcch_user` and `bcch_pass` in
`data/secrets/latam_apis.json` every Chilean row is UNMEASURED BY NAME as a CREDENTIAL gap -- not
a data gap, because the series exists and is published -- while the Peruvian half still runs.
Split into two lanes, a missing Chilean key would read as a missing Andean lane.

THE TWO PARSERS AND THEIR TRAPS. BCCh dates are DD-MM-YYYY, a missing observation is the STRING
"NaN", and each row carries a `statusCode`; a provisional row is KEPT and counted, because a
provisional value is exactly what the desk could have known on that morning. BCRP names its
periods in Spanish ("Ene.2024", "02.Ene.24", "T1.24") and writes "n.d." for unavailable.

THE COPPER STATE is discrete (expanding / flat / contracting) with its acceleration beside it, and
it REFUSES a series too short to measure acceleration rather than inventing one.

The vintage store, `read_pit` and the CLI are the shared engine in `countries/br/data_plane.py`:
one definition of point-in-time for the three lanes.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[3]
if str(DESK) not in sys.path:                      # `python path/to/data_plane.py` still works
    sys.path.insert(0, str(DESK))

from research.countries.br import data_plane as E  # noqa: E402  (the shared lane engine)

LANE = "cl"
STORE = DESK / "data" / "latam" / LANE
REPORT = DESK / "reports" / "SOUTH_AMERICA_CL_PLANE.json"
SECRETS = E.SECRETS
OK, UNMEASURED = E.OK, E.UNMEASURED

#: Copper momentum is the change over `COPPER_WINDOW` observations; its acceleration is the
#: change in that momentum over the next window back, so it needs 2 * window + 1 observations.
COPPER_WINDOW = 3
COPPER_FLAT_BAND = 0.01
COPPER_SERIES = "BCCH_COPPER_PRICE"

_MONTHS = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8,
           "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12}


# --------------------------------------------------------------------------- parsers
def parse_bcch(payload: Any) -> list[dict[str, Any]]:
    """SieteRestWS GetSeries -> rows with the provider's `status_code`; "NaN" is dropped."""
    if not isinstance(payload, Mapping):
        return []
    code = payload.get("Codigo")
    if code not in (None, 0, "0"):
        raise ValueError(f"BCCh refused the request (Codigo {code}): "
                         f"{str(payload.get('Descripcion') or '')[:120]}")
    obs = (payload.get("Series") or {}).get("Obs") or []
    out: dict[str, dict[str, Any]] = {}
    for r in obs:
        if not isinstance(r, Mapping):
            continue
        day, val = E.dmy(r.get("indexDateString"), "-"), E.to_float(r.get("value"))
        if day and val is not None:
            out[day] = {"observation_date": day, "value": val,
                        "status_code": str(r.get("statusCode") or "")}
    return [out[d] for d in sorted(out)]


def _two_digit_year(text: str) -> int:
    y = int(text)
    if y < 100:
        y += 2000 if y < 70 else 1900
    return y


def bcrp_period(name: Any) -> str:
    """A BCRP period label as an ISO date: "Ene.2024" / "02.Ene.24" / "T1.24" / "2024"."""
    parts = [p for p in str(name or "").strip().split(".") if p]
    try:
        if len(parts) == 1 and parts[0].isdigit():
            return date(int(parts[0]), 1, 1).isoformat()
        if len(parts) == 2 and parts[0][:1] in {"T", "t"} and parts[0][1:].isdigit():
            return date(_two_digit_year(parts[1]), 3 * int(parts[0][1:]) - 2, 1).isoformat()
        if len(parts) == 2:
            month = _MONTHS.get(parts[0][:3].lower())
            return date(_two_digit_year(parts[1]), month, 1).isoformat() if month else ""
        if len(parts) == 3:
            month = _MONTHS.get(parts[1][:3].lower())
            return (date(_two_digit_year(parts[2]), month, int(parts[0])).isoformat()
                    if month else "")
    except ValueError:
        return ""
    return ""


def parse_bcrp(payload: Any) -> list[dict[str, Any]]:
    """BCRP series API `{"periods": [{"name", "values": [...]}]}`; "n.d." is dropped."""
    periods = payload.get("periods") if isinstance(payload, Mapping) else None
    out: dict[str, float] = {}
    for p in periods if isinstance(periods, list) else []:
        if not isinstance(p, Mapping):
            continue
        values = p.get("values") or []
        day = bcrp_period(p.get("name"))
        val = E.to_float(values[0]) if values else None
        if day and val is not None:
            out[day] = val
    return [{"observation_date": d, "value": out[d]} for d in sorted(out)]


# --------------------------------------------------------------------------- the copper state
def copper_state(rows: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Discrete copper state from the momentum over `COPPER_WINDOW` observations, with its
    acceleration. Fewer than 2 * window + 1 observations is UNMEASURED, not a guess."""
    if E.is_lab_call(rows):
        got = E.read_pit(COPPER_SERIES, E.today(), STORE)
        if got["outcome"] != OK:
            return E.lab_result("cl_copper_state", {**got, "state": None})
        return E.lab_result("cl_copper_state", copper_state(got["rows"]))
    clean = sorted(((E.iso(r.get("observation_date")), E.to_float(r.get("value")))
                    for r in rows if isinstance(r, Mapping)) if isinstance(rows, list) else [],
                   key=lambda t: t[0])
    pts = [(d, v) for d, v in clean if d and v is not None and v > 0]
    need = 2 * COPPER_WINDOW + 1
    if len(pts) < need:
        return {"outcome": UNMEASURED, "state": None, "n_obs": len(pts),
                "why": (f"{len(pts)} observation(s): momentum needs {COPPER_WINDOW + 1} and its "
                        f"acceleration needs {need}; a state without acceleration is not the "
                        "state this lane publishes")}
    v = [p[1] for p in pts]
    k = COPPER_WINDOW
    momentum = v[-1] / v[-1 - k] - 1.0
    prior = v[-1 - k] / v[-1 - 2 * k] - 1.0
    accel = momentum - prior
    if momentum > COPPER_FLAT_BAND:
        state = "expanding"
    elif momentum < -COPPER_FLAT_BAND:
        state = "contracting"
    else:
        state = "flat"
    return {"outcome": OK, "state": state, "as_of": pts[-1][0], "n_obs": len(pts),
            "momentum": round(momentum, 6), "acceleration": round(accel, 6),
            "accelerating": accel > 0.0, "window": k, "flat_band": COPPER_FLAT_BAND,
            "why": f"{state}: {momentum:+.2%} over {k} observations, acceleration {accel:+.2%}"}


# --------------------------------------------------------------------------- the catalogue
def _url_for(s: E.Series, held: Mapping[str, str], day: date) -> tuple[str, dict[str, str]]:
    start = day - timedelta(days=E.HISTORY_DAYS)
    pid = str(s.provider_id)
    if s.provider == "bcch_siete":
        # SieteRestWS takes the credential as query parameters -- the provider's design, not
        # ours. The URL is therefore never logged, stored or returned by this lane.
        q = urllib.parse.urlencode({"user": held.get("bcch_user", ""),
                                    "pass": held.get("bcch_pass", ""),
                                    "firstdate": start.isoformat(), "lastdate": day.isoformat(),
                                    "timeseries": pid, "function": "GetSeries"})
        return f"https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx?{q}", {}
    if s.provider == "bcrp":
        if s.frequency == "daily":
            lo, hi = start.isoformat(), day.isoformat()
        else:
            lo, hi = f"{start.year}-{start.month}", f"{day.year}-{day.month}"
        return (f"https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{pid}/json/"
                f"{lo}/{hi}"), {}
    raise ValueError(f"no URL rule for provider {s.provider}")


PROVIDERS: tuple[E.Provider, ...] = (
    E.Provider("bcch_siete", "BCCh SieteRestWS (registered user and password)",
               ("bcch_user", "bcch_pass")),
    E.Provider("bcrp", "BCRP estadisticas series API (no key)"),
)

SERIES: tuple[E.Series, ...] = (
    E.Series("BCCH_TPM", "cl", "bcch_siete", "Tasa de politica monetaria", "daily", 0.0,
             "the Chilean policy rate; the carry leg of every copper-to-CLP transmission",
             "bcch", "F022.TPM.TIN.D001.NO.Z.D"),
    E.Series("BCCH_DOLAR_OBSERVADO", "cl", "bcch_siete", "Dolar observado", "daily", 1.0,
             "the official CLP fixing; its value is the PREVIOUS session's average, which is a "
             "publication lag and not a revision", "bcch", "F073.TCO.PRE.Z.D"),
    E.Series("BCRP_REFERENCE_RATE", "pe", "bcrp", "BCRP reference rate", "daily", 0.0,
             "the Peruvian policy rate; the half of the lane that needs no credential",
             "bcrp", "PD04722MD"),
    E.Series("BCCH_IMACEC", "cl", "bcch_siete", "IMACEC (mining and non-mining)", "monthly",
             32.0, "the activity split that tells a copper shock from a domestic one", "bcch",
             lookup_why="the mining and non-mining IMACEC codes are not confirmed against the "
                        "BCCh SearchSeries catalogue on this box"),
    E.Series(COPPER_SERIES, "cl", "bcch_siete", "Copper price (BCCh external sector)", "daily",
             1.0, "the input to the copper state this lane publishes", "bcch",
             lookup_why="the BCCh copper-price series code is not confirmed against the "
                        "SearchSeries catalogue; the copper state stays UNMEASURED until it is"),
    E.Series("BCRP_TERMS_OF_TRADE", "pe", "bcrp", "Peruvian terms of trade", "monthly", 30.0,
             "export and import price indices separately, so copper and oil are not netted",
             "bcrp", lookup_why="the BCRP export/import price-index codes are not confirmed "
                                "against the BCRP series catalogue on this box"),
    E.Series("BCRP_COPPER_EXPORTS", "pe", "bcrp", "Peruvian copper export volume", "monthly",
             30.0, "the Andean supply leg of the copper state", "bcrp",
             lookup_why="the BCRP copper-export code is not confirmed on this box"),
    E.Series("BCRP_RESERVES", "pe", "bcrp", "Peruvian net international reserves", "daily",
             1.0, "the BCRP intervention capacity behind PEN stability", "bcrp",
             lookup_why="the BCRP reserves code is not confirmed on this box"),
)

_LANE = E.Lane(LANE, SERIES, PROVIDERS, (("bcch", parse_bcch), ("bcrp", parse_bcrp)),
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
        return E.lab_result("cl_bcch_lane", _LANE.store_summary(STORE))
    return _LANE.fetch(series, no_fetch=no_fetch, fixtures=fixtures,
                       root=root if root is not None else STORE, realtime=realtime,
                       secrets_path=secrets_path if secrets_path is not None else SECRETS,
                       timeout=timeout)


def report(*, root: Path | str | None = None, fixtures: Path | str | None = None,
           no_fetch: bool = True, secrets_path: Path | str | None = None,
           realtime: str | None = None, series: Iterable[str] | None = None,
           dry_run: bool = False, timeout: float = 30.0) -> dict[str, Any]:
    store = root if root is not None else STORE
    got = fetch(series, no_fetch=no_fetch, fixtures=fixtures, root=store, realtime=realtime,
                secrets_path=secrets_path, timeout=timeout)
    as_of = got["realtime_date"]
    copper = read_pit(COPPER_SERIES, as_of, store)
    doc = {"lane": LANE, "at": datetime.now(UTC).isoformat(timespec="seconds"),
           "catalogue_status": catalogue_status(), "key_status": key_status(secrets_path),
           "fetch": got,
           "pit": {s.series_id: {k: v for k, v in read_pit(s.series_id, as_of, store).items()
                                 if k != "rows"}
                   for s in SERIES if s.provider_id is not None},
           "copper_state": (copper_state(copper["rows"]) if copper["outcome"] == OK
                            else {"outcome": UNMEASURED, "state": None,
                                  "why": f"{COPPER_SERIES}: {copper['why']}"}),
           "written_to": None if dry_run else str(REPORT)}
    E.write_report(doc, REPORT, dry_run)
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    args = E.lane_parser(LANE, __doc__).parse_args(argv)
    if args.catalogue:
        print(json.dumps({"lane": LANE, "status": catalogue_status(), "catalogue": catalogue()},
                         indent=1, default=str))
        return 0
    if args.keys:
        print(json.dumps(key_status(args.secrets), indent=1))
        return 0
    doc = report(root=args.root, fixtures=args.fixtures, no_fetch=not args.fetch,
                 secrets_path=args.secrets, realtime=args.realtime, series=args.series,
                 dry_run=args.dry_run, timeout=args.timeout)
    print(json.dumps(E.summary(doc), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
