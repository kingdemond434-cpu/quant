"""THE BRAZIL LANE: BCB SGS, the Olinda Focus survey and CVM fund flow, held as VINTAGES.

    python -m research.countries.br.data_plane --catalogue
    python -m research.countries.br.data_plane --fixtures DIR --realtime 2024-02-15 --dry-run
    python -m research.countries.br.data_plane --fetch          # the ONLY way to reach the network

WHAT THIS LANE IS FOR. `read_pit(series, morning)` answers with what the desk COULD HAVE KNOWN on
that morning and never with the current revision. Every fetch is written as a NEW vintage file
stamped with its realtime date, a stored vintage is never rewritten, and a read truncates twice:
to the newest vintage whose realtime date is on or before the morning, and then to the
observations that existed by that morning. A morning older than every stored vintage is
UNMEASURED with the word "lookahead" in its reason -- never a value, because a revised series
labelled point-in-time is a silent lookahead in every backtest that touches it.

THE TWO BRAZILIAN PARSING TRAPS. SGS dates are DD/MM/YYYY and SGS values are STRINGS; a parser
that trusts either sorts February before January or sums text. Olinda's Focus survey is the one
natively point-in-time series in the command: every row carries its own survey date, so its
vintage is exact rather than inferred from the fetch day.

CVM IS AGGREGATED BEFORE IT IS STORED (the two-lane order, 2026-09-06). `cvm_sensors` is the only
public door to the fund file, it emits industry and class aggregates, and a class held by fewer
than two funds is SUPPRESSED by name -- a class share of one fund is that fund's position.

THIS COMMAND ALSO CARRIES MEXICO'S BANXICO ROWS, because Mexico has no lane of its own yet and a
silent Mexican row would be read as "no data" rather than "no key". Brazil needs no credential;
Banxico needs `banxico_token` in `data/secrets/latam_apis.json`, reported by PRESENCE only.

THE SHARED LANE ENGINE LIVES HERE. `Series`, `Provider`, `Lane`, `read_pit`, `vintages` and the
CLI parser are used by the Chilean and Argentine lanes too, so the vintage rule is written once:
three lanes with three stores and one definition of "point in time".

NO NETWORK UNLESS ASKED. `no_fetch=True` is the default everywhere; the network branch is
`--fetch` on the command line or `no_fetch=False` from code. As a country-lab custom miner
(`fn(pack, ctx)`) the lane only READS its store -- the scheduler never reaches a provider by
accident.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[3]
LANE = "br"
STORE = DESK / "data" / "latam" / LANE
REPORT = DESK / "reports" / "SOUTH_AMERICA_BR_PLANE.json"
SECRETS = DESK / "data" / "secrets" / "latam_apis.json"

OK, UNMEASURED = "ok", "UNMEASURED"
PIT_FIELDS: tuple[str, ...] = ("observation_date", "realtime_date")
#: Provider status codes that mark a PROVISIONAL observation. A provisional value is kept: it IS
#: the point-in-time value, and dropping it would replace it with the later revision.
PROVISIONAL_CODES = frozenset({"PROV", "P", "PRELIM", "PRELIMINAR", "PROVISIONAL"})
USER_AGENT = "quant-desk-latam-lane/1.0"
HISTORY_DAYS = 3650          # SGS refuses a daily query wider than ten years
MIN_FUNDS_PER_CLASS = 2      # a class held by one fund is that fund's position


# =========================================================================== the shared engine
def today() -> str:
    return datetime.now(UTC).date().isoformat()


def iso(text: Any) -> str:
    """`text` as YYYY-MM-DD when it is exactly a valid ISO date (or starts with one), else ""."""
    s = str(text or "").strip()[:10]
    try:
        return date.fromisoformat(s).isoformat() if len(s) == 10 else ""
    except ValueError:
        return ""


def dmy(text: Any, sep: str) -> str:
    """DD<sep>MM<sep>YYYY -> YYYY-MM-DD, or "" -- parsed by hand so no naive datetime exists."""
    parts = str(text or "").strip().split(sep)
    if len(parts) != 3:
        return ""
    try:
        return date(int(parts[2]), int(parts[1]), int(parts[0])).isoformat()
    except ValueError:
        return ""


def to_float(value: Any) -> float | None:
    """A provider value as a finite float, or None. Strings are the norm, not the exception."""
    if value is None or isinstance(value, bool):
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        out = float(s)
    except ValueError:
        try:
            out = float(s.replace(",", "."))
        except ValueError:
            return None
    return out if math.isfinite(out) else None


def unmeasured(lane: str, series_id: str, why: str) -> dict[str, Any]:
    return {"series_id": series_id, "what": f"{lane}:{series_id}", "verdict": UNMEASURED,
            "why": why}


def is_lab_call(first: Any) -> bool:
    """True when `country_lab.run_lab` is calling an entry as `fn(pack, ctx)`."""
    return hasattr(first, "datasets") and hasattr(first, "code")


def lab_result(name: str, doc: Mapping[str, Any]) -> dict[str, Any]:
    """A lane reading in the shape `run_lab` records: a state, never a discovery by itself."""
    return {"outcome": doc.get("outcome", OK), "discoveries": 0, "miner": name,
            "why": str(doc.get("why") or ""), "readings": [dict(doc)],
            "network": "not touched: the lab reads the store; --fetch owns the network"}


def load_secrets(path: Path | str) -> dict[str, str]:
    """The secrets file's NON-EMPTY entries. Callers only ever test membership; no value is
    returned from this module in any report."""
    try:
        doc = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict):
        return {}
    return {str(k): str(v) for k, v in doc.items()
            if isinstance(v, (str, int)) and str(v).strip()}


def credential_why(missing: Sequence[str], path: Path | str) -> str:
    return (f"credential gap, not a data gap: {', '.join(missing)} absent from {path}; the "
            "provider publishes this series, this box cannot authenticate to it")


def decode(body: bytes) -> Any:
    """A provider response: JSON, or a zipped `;`-separated CSV (CVM) as a list of rows."""
    if body[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as zf:
                name = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
                if name is None:
                    raise ValueError("zip payload holds no CSV")
                text = zf.read(name).decode("latin-1")
        except zipfile.BadZipFile as exc:
            raise ValueError(f"bad zip payload: {exc}") from exc
        return list(csv.DictReader(io.StringIO(text), delimiter=";"))
    return json.loads(body.decode("utf-8-sig"))


def http_get(url: str, headers: Mapping[str, str], timeout: float) -> Any:
    """The ONE network call in the three lanes, through `urllib.request.urlopen` by attribute so
    a test that replaces it catches every lane."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return decode(resp.read())


# --------------------------------------------------------------------------- vintage store
def vintages(series_id: str, root: Path | str | None = None) -> tuple[str, ...]:
    """Every stored realtime date of `series_id`, oldest first."""
    folder = Path(root if root is not None else STORE) / series_id
    if not folder.is_dir():
        return ()
    return tuple(sorted(p.stem for p in folder.glob("*.json") if iso(p.stem) == p.stem))


def store_vintage(root: Path | str, series_id: str, realtime: str,
                  rows: Sequence[Mapping[str, Any]], *, source: str,
                  provider_id: str) -> tuple[Path, bool]:
    """Write ONE vintage. An existing vintage is never rewritten: the first capture of a day is
    what the desk knew that day, and a second one would silently move it."""
    path = Path(root) / series_id / f"{realtime}.json"
    if path.exists():
        return path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"series_id": series_id, "realtime_date": realtime, "provider_id": provider_id,
           "source": source, "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
           "n_rows": len(rows), "rows": [dict(r) for r in rows]}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    tmp.replace(path)
    return path, True


def _known_by(row: Mapping[str, Any], cut: str) -> bool | None:
    """Did this observation exist by `cut`? A row's own realtime date wins (Focus); otherwise
    its observation date. None when neither is a date -- such a row cannot be placed in time."""
    rt = iso(row.get("realtime_date"))
    if rt:
        return rt <= cut
    ob = iso(row.get("observation_date"))
    return (ob <= cut) if ob else None


def read_pit(series_id: str, as_of: str | date, root: Path | str | None = None
             ) -> dict[str, Any]:
    """What the desk could have known about `series_id` on the morning of `as_of`."""
    cut = iso(as_of.isoformat() if isinstance(as_of, date) else as_of)
    base = {"series_id": series_id, "as_of": cut or str(as_of), "vintage": None, "rows": [],
            "n_provisional": 0}
    if not cut:
        return {**base, "outcome": UNMEASURED, "stored_vintages": [],
                "why": f"as_of {as_of!r} is not a date"}
    folder = Path(root if root is not None else STORE)
    stored = list(vintages(series_id, folder))
    base["stored_vintages"] = stored
    if not stored:
        return {**base, "outcome": UNMEASURED,
                "why": f"not fetched: no vintage of {series_id} under {folder}"}
    usable = [v for v in stored if v <= cut]
    if not usable:
        return {**base, "outcome": UNMEASURED,
                "why": (f"every stored vintage of {series_id} is later than {cut} (first "
                        f"{stored[0]}); answering from it would be lookahead")}
    chosen = usable[-1]
    try:
        doc = json.loads((folder / series_id / f"{chosen}.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {**base, "outcome": UNMEASURED, "vintage": chosen,
                "why": f"vintage {chosen} unreadable: {type(exc).__name__}"}
    rows, undated = [], 0
    for row in doc.get("rows") or []:
        known = _known_by(row, cut)
        if known is None:
            undated += 1
        elif known:
            rows.append(row)
    n_prov = sum(str(r.get("status_code") or "").upper() in PROVISIONAL_CODES for r in rows)
    out = {**base, "vintage": chosen, "rows": rows, "n_provisional": n_prov,
           "n_undated_dropped": undated, "source": doc.get("source")}
    if not rows:
        return {**out, "outcome": UNMEASURED,
                "why": f"vintage {chosen} holds no observation dated on or before {cut}"}
    return {**out, "outcome": OK,
            "why": f"vintage {chosen}, {len(rows)} observation(s) known by {cut}"}


# --------------------------------------------------------------------------- the catalogue
@dataclass(frozen=True)
class Provider:
    name: str
    label: str
    keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class Series:
    """One catalogue row. `provider_id=None` means UNRESOLVED: the row is carried, named and
    reported UNMEASURED, and never fetched under a guessed code -- a guessed code returns a real
    series that is the WRONG series, and nothing downstream can detect that."""
    series_id: str
    country: str
    provider: str
    name: str
    frequency: str
    publication_lag_days: float
    why: str
    parser: str
    provider_id: str | None = None
    lookup_why: str = ""
    pit_feasible: bool = True
    options: tuple[tuple[str, Any], ...] = ()

    def row(self, provider: Provider | None) -> dict[str, Any]:
        return {"series_id": self.series_id, "country": self.country,
                "provider": self.provider, "provider_id": self.provider_id,
                "resolved": self.provider_id is not None, "name": self.name,
                "frequency": self.frequency,
                "publication_lag_days": float(self.publication_lag_days),
                "pit_fields": list(PIT_FIELDS), "pit_feasible": bool(self.pit_feasible),
                "needs_key": bool(provider and provider.keys),
                "keys": list(provider.keys) if provider else [],
                "fixture": f"{self.series_id}.json", "why": self.why,
                **({"lookup_why": self.lookup_why} if self.provider_id is None else {})}


UrlFor = Callable[[Series, Mapping[str, str], date], tuple[str, dict[str, str]]]


@dataclass(frozen=True)
class Lane:
    code: str
    series: tuple[Series, ...]
    providers: tuple[Provider, ...]
    parsers: tuple[tuple[str, Callable[..., list[dict[str, Any]]]], ...]
    url_for: UrlFor

    def provider(self, name: str) -> Provider | None:
        return next((p for p in self.providers if p.name == name), None)

    def catalogue(self) -> list[dict[str, Any]]:
        return [s.row(self.provider(s.provider)) for s in self.series]

    def catalogue_status(self) -> dict[str, Any]:
        by_country: dict[str, dict[str, Any]] = {}
        for s in self.series:
            c = by_country.setdefault(s.country, {"n_rows": 0, "n_resolved": 0,
                                                  "needs_lookup": []})
            c["n_rows"] += 1
            if s.provider_id is None:
                c["needs_lookup"].append({"series_id": s.series_id, "provider": s.provider,
                                          "name": s.name, "why": s.lookup_why})
            else:
                c["n_resolved"] += 1
        return {"lane": self.code, "n_rows": len(self.series),
                "n_resolved": sum(c["n_resolved"] for c in by_country.values()),
                "needs_lookup": [r for c in by_country.values() for r in c["needs_lookup"]],
                "by_country": by_country,
                "rule": "an unresolved provider id is UNMEASURED by name, never guessed"}

    def key_status(self, secrets_path: Path | str) -> dict[str, Any]:
        path = Path(secrets_path)
        held = load_secrets(path)
        providers: dict[str, dict[str, Any]] = {}
        for p in self.providers:
            missing = [k for k in p.keys if k not in held]
            if not p.keys:
                outcome, why = OK, "no credential required"
            elif missing:
                outcome, why = UNMEASURED, credential_why(missing, path)
            else:
                outcome, why = OK, f"{len(p.keys)} credential(s) PRESENT; values never reported"
            providers[p.name] = {
                "label": p.label, "needs_key": bool(p.keys), "keys": list(p.keys),
                "present": [k for k in p.keys if k in held], "missing": missing,
                "outcome": outcome, "why": why,
                "series": [s.series_id for s in self.series if s.provider == p.name]}
        return {"lane": self.code, "secrets_path": str(path),
                "secrets_file": "present" if path.exists() else "absent",
                "providers": providers,
                "rule": "a credential is reported PRESENT or ABSENT; no value leaves the box"}

    def fetch(self, wanted: Iterable[str] | None, *, no_fetch: bool,
              fixtures: Path | str | None, root: Path | str, realtime: str | None,
              secrets_path: Path | str, timeout: float) -> dict[str, Any]:
        day = iso(realtime) if realtime else today()
        if not day:
            raise ValueError(f"realtime {realtime!r} is not a YYYY-MM-DD date")
        held = load_secrets(secrets_path)
        parsers = dict(self.parsers)
        by_id = {s.series_id: s for s in self.series}
        ids = list(wanted) if wanted else list(by_id)
        fetched: list[dict[str, Any]] = []
        missed: list[dict[str, Any]] = []
        for sid in ids:
            s = by_id.get(sid)
            if s is None:
                missed.append(unmeasured(self.code, sid, "not in this lane's catalogue"))
                continue
            if s.provider_id is None:
                missed.append(unmeasured(self.code, sid,
                                         f"provider id unresolved, never guessed: "
                                         f"{s.lookup_why}"))
                continue
            prov = self.provider(s.provider)
            gap = [k for k in (prov.keys if prov else ()) if k not in held]
            if gap:
                missed.append(unmeasured(self.code, sid, credential_why(gap, secrets_path)))
                continue
            try:
                if no_fetch:
                    fx = Path(fixtures) / f"{sid}.json" if fixtures else None
                    if fx is None or not fx.exists():
                        missed.append(unmeasured(
                            self.code, sid,
                            "no_fetch: the network branch was not asked for (--fetch) and no "
                            f"fixture {sid}.json was supplied"))
                        continue
                    payload = json.loads(fx.read_text("utf-8"))
                    source = f"fixture:{fx.name}"
                else:
                    url, headers = self.url_for(s, held, date.fromisoformat(day))
                    payload = http_get(url, headers, timeout)
                    source = f"network:{s.provider}"
                rows = parsers[s.parser](payload, **dict(s.options))
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                missed.append(unmeasured(self.code, sid,
                                         f"{type(exc).__name__}: {str(exc)[:200]}"))
                continue
            if not rows:
                missed.append(unmeasured(self.code, sid,
                                         "the payload parsed to zero observations"))
                continue
            path, written = store_vintage(root, sid, day, rows, source=source,
                                          provider_id=str(s.provider_id))
            fetched.append({"series_id": sid, "realtime_date": day, "n_rows": len(rows),
                            "first": rows[0].get("observation_date"),
                            "last": rows[-1].get("observation_date"), "source": source,
                            "written": written, "path": str(path),
                            **({} if written else
                               {"note": "vintage already stored; the first capture is kept"})})
        return {"lane": self.code, "realtime_date": day, "no_fetch": bool(no_fetch),
                "root": str(root), "requested": len(ids), "n_fetched": len(fetched),
                "fetched": fetched, "unmeasured": missed,
                "rule": "each fetch adds a vintage; no stored vintage is ever rewritten"}

    def store_summary(self, root: Path | str) -> dict[str, Any]:
        """What the store holds, for the lab: a lane with no fresh vintage says so by name."""
        rows, missed = [], []
        for s in self.series:
            got = vintages(s.series_id, root)
            if got:
                rows.append({"series_id": s.series_id, "n_vintages": len(got),
                             "latest_vintage": got[-1]})
            else:
                missed.append(unmeasured(self.code, s.series_id,
                                         s.lookup_why if s.provider_id is None
                                         else "no vintage stored; run the lane with --fetch"))
        return {"outcome": OK if rows else UNMEASURED, "lane": self.code, "stored": rows,
                "unmeasured": missed,
                "why": f"{len(rows)}/{len(self.series)} series hold at least one vintage"}


def write_report(doc: Mapping[str, Any], target: Path | str, dry_run: bool) -> None:
    if dry_run:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    tmp.replace(path)


def lane_parser(lane: str, doc: str | None) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog=f"research.countries.{lane}.data_plane",
                                 description=(doc or "").splitlines()[0] if doc else None)
    ap.add_argument("--catalogue", action="store_true", help="print the catalogue and exit")
    ap.add_argument("--keys", action="store_true", help="print credential PRESENCE and exit")
    ap.add_argument("--fetch", action="store_true",
                    help="reach the network (the default is --no-fetch)")
    ap.add_argument("--fixtures", default=None, help="read <series_id>.json payloads from here")
    ap.add_argument("--root", default=None, help="vintage store root")
    ap.add_argument("--realtime", default=None, help="the vintage date (default: today UTC)")
    ap.add_argument("--secrets", default=None, help="credentials file (presence only)")
    ap.add_argument("--series", nargs="*", default=None, help="restrict to these series ids")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and write no report")
    return ap


def summary(doc: Mapping[str, Any]) -> dict[str, Any]:
    got = doc.get("fetch") or {}
    return {"lane": doc.get("lane"), "realtime_date": got.get("realtime_date"),
            "n_fetched": got.get("n_fetched"), "n_unmeasured": len(got.get("unmeasured") or []),
            "written": doc.get("written_to")}


# =========================================================================== Brazil (and Banxico)
def parse_sgs(payload: Any) -> list[dict[str, Any]]:
    """BCB SGS `[{"data": "DD/MM/YYYY", "valor": "11.75"}]` -> sorted ISO rows; a bad date or an
    empty value is dropped, never coerced."""
    out: dict[str, float] = {}
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, Mapping):
            continue
        day, val = dmy(item.get("data"), "/"), to_float(item.get("valor"))
        if day and val is not None:
            out[day] = val
    return [{"observation_date": d, "value": out[d]} for d in sorted(out)]


def parse_olinda(payload: Any, indicator: str | None = None) -> list[dict[str, Any]]:
    """Olinda Expectativas: each row's own survey date (`Data`) IS its realtime date, and the
    reference period (`DataReferencia`, or `Reuniao` for the Copom entity) is its observation."""
    rows = payload.get("value") if isinstance(payload, Mapping) else payload
    out: list[dict[str, Any]] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, Mapping):
            continue
        if indicator and r.get("Indicador") != indicator:
            continue
        if r.get("baseCalculo") not in (None, 0, "0"):
            continue
        rt, val = iso(r.get("Data")), to_float(r.get("Mediana"))
        ref = str(r.get("DataReferencia") or r.get("Reuniao") or "").strip()
        if not (rt and ref and val is not None):
            continue
        n = r.get("numeroRespondentes")
        out.append({"observation_date": ref, "realtime_date": rt, "value": val,
                    "respondents": int(n) if isinstance(n, (int, float)) else None})
    return sorted(out, key=lambda x: (x["realtime_date"], x["observation_date"]))


def parse_banxico(payload: Any) -> list[dict[str, Any]]:
    """Banxico SIE `bmx.series[0].datos` -- DD/MM/YYYY, thousands commas, "N/E" when absent."""
    series = ((payload or {}).get("bmx") or {}).get("series") or []
    out: dict[str, float] = {}
    for item in (series[0].get("datos") or []) if series else []:
        day = dmy(item.get("fecha"), "/")
        val = to_float(str(item.get("dato") or "").replace(",", ""))
        if day and val is not None:
            out[day] = val
    return [{"observation_date": d, "value": out[d]} for d in sorted(out)]


def _num(row: Mapping[str, Any], *keys: str) -> float | None:
    for k in keys:
        if k in row:
            return to_float(row.get(k))
    return None


def cvm_sensors(rows: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """CVM INF_DIARIO rows -> DAILY INDUSTRY SENSORS. The only public door to the fund file.

    Per day: net flow (subscriptions minus redemptions), fund count, net assets, and each
    class's share of net assets and net flow -- for classes held by at least
    `MIN_FUNDS_PER_CLASS` funds. A thinner class is SUPPRESSED by name, and a day with fewer
    funds than that is suppressed whole. No fund identifier leaves this function.
    """
    if is_lab_call(rows):
        return lab_result("br_cvm_sensors",
                          read_pit("CVM_INF_DIARIO", today(), STORE))
    days: dict[str, dict[str, Any]] = {}
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, Mapping):
            continue
        day = iso(r.get("DT_COMPTC"))
        fund = str(r.get("CNPJ_FUNDO") or r.get("CNPJ_FUNDO_CLASSE") or "").strip()
        inflow, outflow = _num(r, "CAPTC_DIA"), _num(r, "RESG_DIA")
        aum = _num(r, "VL_PATRIM_LIQ")
        if not (day and fund) or inflow is None or outflow is None:
            continue
        cls = str(r.get("CLASSE") or r.get("TP_FUNDO_CLASSE") or r.get("TP_FUNDO")
                  or "unclassified").strip()
        d = days.setdefault(day, {"flow": 0.0, "aum": 0.0, "funds": set(), "classes": {}})
        d["flow"] += inflow - outflow
        d["aum"] += aum or 0.0
        d["funds"].add(fund)
        c = d["classes"].setdefault(cls, {"flow": 0.0, "aum": 0.0, "funds": set()})
        c["flow"] += inflow - outflow
        c["aum"] += aum or 0.0
        c["funds"].add(fund)
    series, dropped = [], []
    for day in sorted(days):
        d = days[day]
        if len(d["funds"]) < MIN_FUNDS_PER_CLASS:
            dropped.append(day)
            continue
        kept = {k: v for k, v in d["classes"].items() if len(v["funds"]) >= MIN_FUNDS_PER_CLASS}
        aum = d["aum"]
        series.append({
            "observation_date": day, "value": round(d["flow"], 6),
            "net_flow": round(d["flow"], 6), "aum": round(aum, 6), "n_funds": len(d["funds"]),
            "class_shares": {k: (round(v["aum"] / aum, 6) if aum else None)
                             for k, v in sorted(kept.items())},
            "class_net_flow": {k: round(v["flow"], 6) for k, v in sorted(kept.items())},
            "suppressed_classes": sorted(set(d["classes"]) - set(kept))})
    if not series:
        return {"outcome": UNMEASURED, "days": 0, "series": [], "suppressed_days": dropped,
                "why": "no CVM day with at least "
                       f"{MIN_FUNDS_PER_CLASS} funds -- nothing aggregates without naming a fund"}
    return {"outcome": OK, "days": len(series), "series": series, "suppressed_days": dropped,
            "min_funds_per_class": MIN_FUNDS_PER_CLASS,
            "why": f"{len(series)} day(s) aggregated; single-fund classes suppressed"}


def _cvm_rows(payload: Any) -> list[dict[str, Any]]:
    """The stored CVM vintage is the AGGREGATE series -- no fund row ever reaches disk."""
    return list(cvm_sensors(payload).get("series") or [])


def _url_for(s: Series, held: Mapping[str, str], day: date) -> tuple[str, dict[str, str]]:
    start = day - timedelta(days=HISTORY_DAYS)
    pid = str(s.provider_id)
    if s.provider == "bcb_sgs":
        q = urllib.parse.urlencode({"formato": "json", "dataInicial": start.strftime("%d/%m/%Y"),
                                    "dataFinal": day.strftime("%d/%m/%Y")})
        return f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{pid}/dados?{q}", {}
    if s.provider == "bcb_olinda":
        entity, _, indicator = pid.partition(":")
        q = urllib.parse.urlencode({"$filter": f"Indicador eq '{indicator}'", "$format": "json",
                                    "$orderby": "Data desc", "$top": "20000"},
                                   quote_via=urllib.parse.quote)
        return ("https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
                f"{entity}?{q}"), {}
    if s.provider == "cvm_open":
        month = day.strftime("%Y%m")
        return ("https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/"
                f"inf_diario_fi_{month}.zip"), {}
    if s.provider == "banxico_sie":
        return (f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{pid}/datos",
                {"Bmx-Token": held.get("banxico_token", "")})
    raise ValueError(f"no URL rule for provider {s.provider}")


PROVIDERS: tuple[Provider, ...] = (
    Provider("bcb_sgs", "BCB SGS time-series API (no key)"),
    Provider("bcb_olinda", "BCB Olinda OData -- Focus Expectativas (no key)"),
    Provider("cvm_open", "CVM open data -- INF_DIARIO fund file (no key)"),
    Provider("banxico_sie", "Banxico SIE REST API (token)", ("banxico_token",)),
)

SERIES: tuple[Series, ...] = (
    Series("BCB_SGS_432", "br", "bcb_sgs", "Meta Selic", "per Copom meeting", 0.0,
           "the policy-rate leg of the BRL carry and of every Copom event study",
           "sgs", "432"),
    Series("BCB_SGS_1", "br", "bcb_sgs", "PTAX venda diaria (USD)", "daily", 0.0,
           "the official fixing USDBRL settles against; its four-window build is a session "
           "anchor", "sgs", "1"),
    Series("BCB_SGS_3546", "br", "bcb_sgs", "Reservas internacionais (total, monthly)",
           "monthly", 1.0, "the intervention-capacity state behind every BRL stress episode",
           "sgs", "3546"),
    Series("FOCUS_IPCA", "br", "bcb_olinda", "Focus median IPCA (monthly reference)",
           "weekly survey", 3.0,
           "natively point-in-time expectations: the surprise leg of every IPCA print",
           "olinda", "ExpectativaMercadoMensais:IPCA", options=(("indicator", "IPCA"),)),
    Series("FOCUS_SELIC", "br", "bcb_olinda", "Focus median Selic (annual reference)",
           "weekly survey", 3.0, "the expected policy path a Copom decision is a surprise to",
           "olinda", "ExpectativasMercadoAnuais:Selic", options=(("indicator", "Selic"),)),
    Series("FOCUS_CAMBIO", "br", "bcb_olinda", "Focus median exchange rate (annual reference)",
           "weekly survey", 3.0, "the expected BRL level; its revision is a positioning sensor",
           "olinda", "ExpectativasMercadoAnuais:Câmbio",
           options=(("indicator", "Câmbio"),)),
    Series("CVM_INF_DIARIO", "br", "cvm_open", "CVM daily fund file, aggregated to industry flow",
           "daily, monthly files", 32.0,
           "domestic fund flow as a cycle sensor; stored ONLY as aggregates", "cvm",
           "inf_diario_fi_{YYYYMM}"),
    Series("BCB_FLUXO_CAMBIAL", "br", "bcb_sgs", "Fluxo cambial contratado (comercial, financeiro)",
           "weekly", 5.0, "the commercial-versus-financial split of dollar flow", "sgs",
           lookup_why="the SGS code set for the two flow legs is not confirmed against the SGS "
                      "catalogue on this box"),
    Series("BCB_CREDIT", "br", "bcb_sgs", "Credit stock and default rate", "monthly", 25.0,
           "the domestic credit cycle under the Selic", "sgs",
           lookup_why="the exact SGS credit-aggregate codes are not resolved on this box"),
    Series("BANXICO_SF43718", "mx", "banxico_sie", "Tipo de cambio FIX", "daily", 0.0,
           "the peso fixing; USDMXN is a global-risk sensor for this command", "banxico",
           "SF43718"),
    Series("BANXICO_TARGET_RATE", "mx", "banxico_sie", "Tasa objetivo de Banxico",
           "per decision", 0.0, "the carry leg of the EM-hedge-proxy peso", "banxico",
           lookup_why="the pack names SF61745 only as a candidate; it must be confirmed "
                      "against the SIE catalogue endpoint before any fetch"),
)

_LANE = Lane(LANE, SERIES, PROVIDERS,
             (("sgs", parse_sgs), ("olinda", parse_olinda), ("cvm", _cvm_rows),
              ("banxico", parse_banxico)),
             _url_for)


def catalogue() -> list[dict[str, Any]]:
    return _LANE.catalogue()


def catalogue_status() -> dict[str, Any]:
    return _LANE.catalogue_status()


def key_status(secrets_path: Path | str | None = None) -> dict[str, Any]:
    return _LANE.key_status(secrets_path if secrets_path is not None else SECRETS)


def fetch(series: Iterable[str] | None = None, *args: Any, no_fetch: bool = True,
          fixtures: Path | str | None = None, root: Path | str | None = None,
          realtime: str | None = None, secrets_path: Path | str | None = None,
          timeout: float = 30.0) -> dict[str, Any]:
    """Fetch (or, by default, read fixtures for) the lane and add one vintage per series."""
    if is_lab_call(series):
        return lab_result("br_sgs_lane", _LANE.store_summary(STORE))
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
    doc = {"lane": LANE, "at": datetime.now(UTC).isoformat(timespec="seconds"),
           "catalogue_status": catalogue_status(), "key_status": key_status(secrets_path),
           "fetch": got,
           "pit": {s.series_id: {k: v for k, v in read_pit(s.series_id, as_of, store).items()
                                 if k != "rows"}
                   for s in SERIES if s.provider_id is not None},
           "written_to": None if dry_run else str(REPORT)}
    write_report(doc, REPORT, dry_run)
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    args = lane_parser(LANE, __doc__).parse_args(argv)
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
    print(json.dumps(summary(doc), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
