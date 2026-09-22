"""THE ACTIVE DATA-ACQUISITION SCIENTIST (LAWS 5m; RESEARCH 11).

WHAT IT DECIDES. Which MISSING dataset has the highest expected research value:

    EV = P(independent forward survivor) x expected diversification value
         / (data cost + compute + engineering) x 1[legally permitted]

read from four registers that already name holes -- the coverage tensor's frontier, the residual
hunt's open targets, the missed-trade parents (when that organ has published any) and the
country packs' datasets DECLARED ABSENT -- plus the data scout's needs. Candidates are merged by
dataset, measured for redundancy against what the desk already holds (`data_scout`'s held marks),
priced off the scout's catalogue where a route is declared, and gated by a DatasetContract whose
`admissible()` is the LEGALITY HARD GATE: the indicator is a multiplier of zero, never a term
traded against value, and a page whose terms forbid machine extraction is REGISTERED and never
fetched.

WHAT IT BUILDS. For the top admissible candidates with a public URL route it takes a SMALL LAWFUL
SAMPLE through the desk's existing fetch path (`acquire_datasets._fetch` behind
`asia_collector._robots_allows`; never a new scraper), content-hashes it into a Vintage and a
LineageRecord, and records a `dataset_request` discovery in `data/intelligence/<seat>/` carrying
the contract and the expected value. Report: `reports/DATA_ACQUISITION.json`. Runs as the hourly
leg `data_acquisition_scientist` (data department, information layer), 600 s. `--dry-run`
writes nothing at all.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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

try:
    from research import data_scout as DS
except ImportError:                                                          # pragma: no cover
    import data_scout as DS  # type: ignore[no-redef]
from libs.data.pit import stamp as pit_stamp  # noqa: E402
from libs.moat import registry as REG  # noqa: E402
from libs.research import access_classifier as AC  # noqa: E402
from libs.research import data_contract as DC  # noqa: E402

SEAT = "data_acquisition_scientist"
COVERAGE = DESK / "reports" / "COVERAGE_TENSOR.json"
RESIDUAL = DESK / "reports" / "RESIDUAL_HUNT.json"
#: The missed-trade archaeologist's artifact, read tolerantly by either name; absent = UNMEASURED.
MISSED: tuple[Path, ...] = (DESK / "reports" / "MISSED_TRADES.json",
                            DESK / "reports" / "MISSED_TRADE_ARCHAEOLOGY.json")
OUT = DESK / "reports" / "DATA_ACQUISITION.json"
STORE = DESK / "data" / "data_acquisition"
STATE = STORE / "requests.json"
SAMPLES = STORE / "samples"
INTEL = DESK / "data" / "intelligence" / SEAT

UNMEASURED = "UNMEASURED"
BUDGET_S = 600.0
TOP_K = 25
MAX_SAMPLES = 3
MAX_SAMPLE_BYTES = 256 * 1024
MAX_SAMPLE_ROWS = 200
MAX_HOLES = 400
MAX_TARGETS = 200
MAX_PACK_ROWS = 600
MAX_NEEDS = 400
RE_REQUEST_H = 24.0
EV_CHANGE_TO_REREQUEST = 0.25
#: Declared terms of the formula. Every one is named in the artifact beside the number it made.
PRIOR_P_SURVIVOR = 0.05          # base rate for a dataset nobody has judged a neighbour of
COMPUTE_COST = 1.0
DEFAULT_DATA_COST = 2.0          # no catalogue route: declared, flagged cost_unmeasured
DEFAULT_ENGINEERING = 3.0
PACK_ABSENT_VALUE = 0.25         # coverage debt: a dataset a pack names absent
MISSED_PARENT_VALUE = 0.5
FORMULA = ("EV = p_survivor x information_gain x independence / (data_cost + compute + "
           "engineering) x legal (1 or 0); information_gain sums the EVIG of the coverage-tensor "
           "holes and the residual effect sizes the dataset would explain")
RULE = ("the scientist ranks missing datasets by expected research value, samples lawfully "
        "through existing fetchers where a public route exists, contracts every request, and "
        "never lets legality be traded against value: an inadmissible contract is EV 0")

_WS = re.compile(r"[^a-z0-9]+")
_URL = re.compile(r"https?://[^\s\"'<>)]+")


# ---------------------------------------------------------------------------------- helpers
def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _slug(text: Any) -> str:
    return _WS.sub("_", str(text or "").strip().lower()).strip("_")[:96]


def _words(text: Any) -> set[str]:
    return {w for w in _WS.split(str(text or "").lower()) if len(w) > 2}


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def jeffreys(positive: float, n: float) -> float:
    return (float(positive) + 0.5) / (float(n) + 1.0)


def _code_version() -> str:
    try:
        head = (ROOT / ".git" / "HEAD").read_text("utf-8").strip()
        if head.startswith("ref: "):
            ref = ROOT / ".git" / head[5:]
            return ref.read_text("utf-8").strip()[:12] if ref.exists() else UNMEASURED
        return head[:12]
    except OSError:
        return UNMEASURED


# ------------------------------------------------------------------------- the registers
def _candidate(key: str, observable: str, *, register: str, ref: str, p: float | None,
               value: float, why: str, mechanisms: list[str] | None = None,
               assets: list[str] | None = None, country: str = "", url: str = "",
               licence: str = "", machine_use_allowed: bool | None = None,
               how_to_fetch: str = "", source_class: str = "", revisions: str = "",
               pit_feasible: bool | None = None) -> dict[str, Any]:
    return {"dataset": key, "observable": observable,
            "named_by": [{"register": register, "ref": ref, "p_survivor": p, "value": value,
                          "why": why}],
            "mechanisms": sorted({m for m in (mechanisms or []) if m})[:12],
            "assets": sorted({a for a in (assets or []) if a})[:12], "country": country,
            "url": url, "licence": licence, "machine_use_allowed": machine_use_allowed,
            "how_to_fetch": how_to_fetch, "source_class": source_class,
            "revisions": revisions, "pit_feasible": pit_feasible}


def from_coverage_holes(path: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = path or COVERAGE
    doc = _read_json(path, None)
    top = (doc.get("frontier") or {}).get("top") if isinstance(doc, dict) else None
    if not isinstance(top, list):
        return [], {"status": UNMEASURED, "why": f"{path.name} absent or has no frontier.top",
                    "measured_by": "the hourly coverage_tensor leg"}
    out: list[dict[str, Any]] = []
    for hole in top[:MAX_HOLES]:
        if not isinstance(hole, dict):
            continue
        values = hole.get("values") if isinstance(hole.get("values"), dict) else {}
        state = str(hole.get("state") or "")
        if state not in ("UNOBSERVED", "SOURCE_HUNT", "UNSEEN", "DISCOVERED"):
            continue
        what = str(values.get("information_type") or values.get("source_class")
                   or values.get("mechanism") or "observation")
        country = str(values.get("country") or "")
        asset = str(values.get("asset") or "")
        key = _slug(f"{what}:{country}")
        judged = (hole.get("breakdown") or {}).get("judged_neighbours") or {}
        n = float(judged.get("n_neighbours") or 0)
        p = jeffreys(float(judged.get("positive") or 0), n) if n > 0 else None
        out.append(_candidate(
            key, f"{what} for {country or 'global'}", register="coverage_hole",
            ref=str(hole.get("key") or key), p=p, value=float(hole.get("score") or 0.0),
            why=f"tensor {hole.get('tensor')} cell in state {state}: EVIG {hole.get('score')}",
            mechanisms=[str(values.get("mechanism") or "")], assets=[asset], country=country))
    return out, {"status": "measured", "holes": len(top), "candidates": len(out)}


def from_residual_targets(path: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = path or RESIDUAL
    doc = _read_json(path, None)
    targets = doc.get("targets") if isinstance(doc, dict) else None
    if isinstance(targets, dict):
        targets = list(targets.values())
    if not isinstance(targets, list):
        return [], {"status": UNMEASURED, "why": f"{path.name} absent or has no targets",
                    "measured_by": "the hourly residual_hunt leg"}
    out: list[dict[str, Any]] = []
    for target in targets[:MAX_TARGETS]:
        if not isinstance(target, dict):
            continue
        cell = target.get("cell") if isinstance(target.get("cell"), dict) else {}
        evidence = target.get("evidence") if isinstance(target.get("evidence"), dict) else {}
        symbol = str(cell.get("symbol") or target.get("symbol") or "")
        horizon = str(cell.get("horizon") or "")
        session = str(cell.get("session") or "")
        effect = abs(float(evidence.get("effect_sd") or 0.0))
        p_mean = evidence.get("p_mean")
        p = None if p_mean is None else min(0.5, PRIOR_P_SURVIVOR * (1.0 + effect) *
                                            (1.0 - float(p_mean)))
        key = _slug(f"residual_explainer:{symbol}:{horizon}:{session}")
        out.append(_candidate(
            key, f"an explainer of the {symbol} {horizon} {session} residual",
            register="residual_target", ref=str(target.get("cluster_id") or key), p=p,
            value=effect, why=str(target.get("question") or "")[:240],
            assets=[symbol]))
    return out, {"status": "measured", "targets": len(targets), "candidates": len(out)}


def from_missed_trade_parents(paths: tuple[Path, ...] | None = None
                              ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths = paths or MISSED
    for path in paths:
        doc = _read_json(path, None)
        if not isinstance(doc, dict):
            continue
        rows = doc.get("parents") or doc.get("missed") or doc.get("rows")
        if not isinstance(rows, list):
            continue
        out: list[dict[str, Any]] = []
        for row in rows[:MAX_TARGETS]:
            if not isinstance(row, dict):
                continue
            what = str(row.get("missing_data") or row.get("dataset") or row.get("what") or "")
            if not what:
                continue
            value = row.get("missed_elogw", row.get("value"))
            out.append(_candidate(
                _slug(what), what, register="missed_trade_parent",
                ref=str(row.get("parent_id") or row.get("id") or what),
                p=(float(row["p_survivor"]) if row.get("p_survivor") is not None else None),
                value=(abs(float(value)) if value is not None else MISSED_PARENT_VALUE),
                why=str(row.get("why") or "a missed trade named this dataset as its parent"),
                assets=[str(s) for s in (row.get("symbols") or [])[:6]]))
        return out, {"status": "measured", "path": str(path), "rows": len(rows),
                     "candidates": len(out)}
    return [], {"status": UNMEASURED,
                "why": "no missed-trade artifact on this box (" + ", ".join(
                    p.name for p in paths) + ")",
                "measured_by": "the missed-trade archaeologist, when it runs"}


def load_packs() -> tuple[dict[str, Any], list[str]]:
    """Every country pack on disk, through the transmission engine's own loader."""
    try:
        from research import transmission_engine as TE
    except ImportError:                                                      # pragma: no cover
        import transmission_engine as TE  # type: ignore[no-redef]
    packs, notes = TE.load_packs()
    return dict(packs), list(notes)


def _pack_get(pack: Any, name: str) -> Any:
    if isinstance(pack, dict):
        return pack.get(name)
    return getattr(pack, name, None)


def _absent(text: str) -> bool:
    low = text.lower()
    return ("absent" in low or "no fetcher" in low or "not held" in low
            or "not collected" in low or "no source" in low)


def from_country_packs(packs: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out: list[dict[str, Any]] = []
    scanned = 0
    for code, pack in sorted(packs.items()):
        instruments = [str(s) for s in (_pack_get(pack, "executable_instruments") or [])][:12]
        for row in list(_pack_get(pack, "datasets") or [])[:MAX_PACK_ROWS]:
            if not isinstance(row, dict):
                continue
            scanned += 1
            blob = " ".join(str(row.get(k) or "") for k in ("name", "coverage", "how_to_fetch",
                                                            "source"))
            if not _absent(blob):
                continue
            name = str(row.get("name") or "")
            url_m = _URL.search(str(row.get("how_to_fetch") or "") + " " + str(row.get("source")
                                                                                or ""))
            out.append(_candidate(
                _slug(f"{code}:{name}"), name, register="country_pack",
                ref=f"{code}.datasets:{name}", p=None, value=PACK_ABSENT_VALUE,
                why=f"pack {code} names this dataset ABSENT: {row.get('coverage') or ''}"[:240],
                mechanisms=[str(m) for m in (row.get("mechanism_families") or [])],
                assets=[str(a) for a in (row.get("assets") or [])] or instruments,
                country=code, url=url_m.group(0) if url_m else "",
                licence=str(row.get("licence") or ""),
                how_to_fetch=str(row.get("how_to_fetch") or ""), source_class="official",
                revisions=str(row.get("revisions") or ""),
                pit_feasible=(bool(row["pit_feasible"]) if row.get("pit_feasible") is not None
                              else None)))
        for row in list(_pack_get(pack, "source_classes") or [])[:MAX_PACK_ROWS]:
            if not isinstance(row, dict) or not str(row.get("id") or "").startswith("absent_"):
                continue
            scanned += 1
            layer = str(row.get("layer") or "")
            out.append(_candidate(
                _slug(f"{code}:layer:{layer}"), f"{code} {layer} layer sources",
                register="country_pack", ref=f"{code}.source_classes:{row.get('id')}", p=None,
                value=PACK_ABSENT_VALUE, why=str(row.get("notes") or "")[:240], country=code,
                licence=str(row.get("licence") or ""),
                machine_use_allowed=(bool(row["machine_use_allowed"])
                                     if row.get("machine_use_allowed") is not None else None),
                assets=instruments, source_class=layer or "official"))
        for row in list(_pack_get(pack, "positioning_sources") or [])[:MAX_PACK_ROWS]:
            if not isinstance(row, dict):
                continue
            scanned += 1
            if not _absent(str(row.get("name") or "") + " " + str(row.get("covers") or "")):
                continue
            name = str(row.get("name") or "")
            out.append(_candidate(
                _slug(f"{code}:positioning:{row.get('id') or name}"), name,
                register="country_pack", ref=f"{code}.positioning_sources:{row.get('id')}",
                p=None, value=PACK_ABSENT_VALUE, why=str(row.get("note") or "")[:240],
                country=code, licence=str(row.get("licence") or ""), assets=instruments,
                source_class="official", how_to_fetch=str(row.get("root") or "")))
    note: dict[str, Any] = {"status": "measured" if packs else UNMEASURED, "packs": len(packs),
                            "rows_scanned": scanned, "candidates": len(out)}
    if not packs:
        note.update({"why": "no country pack loaded",
                     "measured_by": "desks/mt5/research/countries/<code>/pack.py"})
    return out, note


def from_needs(conn: Any, *, axes_dir: Path | None = None, value_path: Path | None = None
               ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        needs, registers = DS.gather(conn=conn, axes_dir=axes_dir, value_path=value_path)
    except Exception as exc:
        return [], {"status": UNMEASURED, "why": f"data_scout.gather raised "
                                                 f"{type(exc).__name__}: {exc}",
                    "measured_by": "the data_scout leg"}
    out: list[dict[str, Any]] = []
    for need in needs[:MAX_NEEDS]:
        observable = str(need.get("observable") or "")
        if not observable:
            continue
        blocked = int(need.get("blocked_hypotheses") or 0)
        value = need.get("value")
        out.append(_candidate(
            _slug(observable), observable, register=f"needs:{need.get('register')}",
            ref=observable, p=None,
            value=(float(value) if value is not None else DS.VALUE_PRIOR) * (1.0 + blocked / 10.0),
            why=str(need.get("why") or "")[:240],
            mechanisms=[str(m) for m in (need.get("mechanisms") or [])]))
    return out, {"status": "measured", "needs": len(needs), "registers": registers,
                 "candidates": len(out)}


# ------------------------------------------------------------------------------- merging
def merge(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """One candidate per dataset key; every register that named it is kept as evidence."""
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row["dataset"]
        have = out.get(key)
        if have is None:
            out[key] = {**row, "named_by": list(row["named_by"])}
            continue
        have["named_by"].extend(row["named_by"])
        for field in ("mechanisms", "assets"):
            have[field] = sorted(set(have[field]) | set(row[field]))[:12]
        for field in ("country", "url", "licence", "how_to_fetch", "source_class", "revisions"):
            have[field] = have[field] or row[field]
        for field in ("machine_use_allowed", "pit_feasible"):
            if have.get(field) is None:
                have[field] = row.get(field)
    return out


# -------------------------------------------------------------- redundancy, cost, legality
def redundancy(observable: str, marks: set[str]) -> tuple[float, str]:
    """1.0 when a held mark already answers the observable; else the share of its words held."""
    if not DS.is_missing(observable, marks):
        return 1.0, "a held mark answers this observable (data_scout.is_missing is False)"
    words = _words(observable)
    if not words:
        return 0.0, "no words to compare"
    held = {w for w in words if w in marks}
    return len(held) / len(words), f"{len(held)}/{len(words)} words already held"


def route_and_cost(cand: dict[str, Any], catalogue: Any) -> dict[str, Any]:
    need = {"observable": cand["observable"], "blocked_hypotheses": 1, "value": None}
    ranked = DS.rank_sources(need, catalogue)
    if ranked:
        best = ranked[0]
        return {"catalogue": best["source"], "how_to_fetch": best["how_to_fetch"],
                "access": best["access"], "pit_status": best["pit_status"],
                "cadence": best["cadence"], "data_cost": float(best["cost"]),
                "engineering": float(best["integration_effort"]), "cost_basis": "catalogue"}
    return {"catalogue": None, "how_to_fetch": cand.get("how_to_fetch") or "",
            "access": "free" if cand.get("url") else UNMEASURED, "pit_status": UNMEASURED,
            "cadence": UNMEASURED, "data_cost": DEFAULT_DATA_COST,
            "engineering": DEFAULT_ENGINEERING,
            "cost_basis": "declared default: no catalogue route; cost UNMEASURED"}


_JURISDICTION: tuple[tuple[str, str], ...] = (
    ("fred", "US"), ("treasury", "US"), ("cftc", "US"), ("federal reserve", "US"),
    ("eia", "US"), ("usda", "US"), ("ecb", "EU"), ("eurostat", "EU"), ("bis", "CH"),
    ("sge", "CN"), ("shanghai", "CN"), ("shfe", "CN"), ("dce", "CN"), ("boj", "JP"),
    ("tocom", "JP"), ("lme", "UK"), ("ice", "UK"), ("rba", "AU"), ("asx", "AU"),
    ("rbnz", "NZ"), ("nzx", "NZ"),
)


def jurisdiction_of(cand: dict[str, Any], route: dict[str, Any]) -> str:
    if cand.get("country"):
        return str(cand["country"]).upper()
    blob = f"{route.get('catalogue') or ''} {cand.get('observable')}".lower()
    for needle, code in _JURISDICTION:
        if needle in blob:
            return code
    return UNMEASURED


def revision_policy_of(cand: dict[str, Any], route: dict[str, Any]) -> str:
    """The source's revision behaviour, read off the catalogue's PIT note or the pack's own
    `revisions` field; UNMEASURED when neither says anything."""
    pit = str(route.get("pit_status") or "") if route.get("catalogue") else ""
    low = f"{pit} {cand.get('revisions') or ''}".strip().lower()
    if not low:
        return UNMEASURED
    if "vintage" in low or "first-released" in low or "first published" in low:
        return "IMMUTABLE_VINTAGES"
    if "never" in low or low.startswith("none") or "not revised" in low:
        return "NEVER_REVISED"
    if "revis" in low:
        return "REVISED_IN_PLACE"
    return "APPEND_ONLY"


def contract_for(cand: dict[str, Any], route: dict[str, Any], at: str
                 ) -> tuple[DC.DatasetContract, AC.AccessVerdict]:
    access = str(route.get("access") or "")
    licence = str(cand.get("licence") or "")
    meta: dict[str, Any] = {"source_id": cand["dataset"], "url": cand.get("url") or "",
                            "source_class": cand.get("source_class") or "",
                            "licence": licence or (f"declared {access}" if access else ""),
                            # the licence prose is also TERMS, so the hard boundary's markers
                            # (material non-public, leaked database, ...) are read off it
                            "terms": licence, "licence_note": licence}
    if cand.get("machine_use_allowed") is not None:
        meta["machine_use_allowed"] = bool(cand["machine_use_allowed"])
    if access == "free" or "public" in licence.lower() or "free" in licence.lower():
        meta["is_open_data"] = True
    verdict = AC.classify(meta)
    if verdict.refused or verdict.quarantine:
        label = verdict.access_label
    elif access == "licensed":
        label = "LICENSED"
    elif access == "free" or meta.get("is_open_data"):
        label = "OPEN_DATA" if cand.get("source_class") in ("official", "institutional") \
            else "PUBLIC"
    else:
        label = "ACCESS_UNCLEAR"
    public = label in ("PUBLIC", "PUBLIC_WITH_TERMS", "OPEN_DATA", "PUBLIC_ARCHIVE", "LICENSED")
    contract = DC.DatasetContract(
        dataset_id=cand["dataset"],
        source=str(route.get("catalogue") or cand.get("url") or cand["observable"]),
        owner=("the publisher named by the source" if public else UNMEASURED),
        acquisition_method=str(route.get("how_to_fetch") or (
            "existing fetch path (acquire_datasets._fetch behind robots.txt)" if cand.get("url")
            else UNMEASURED)),
        public_or_licensed=label,
        licence_version=(licence or (f"declared {access} in the data_scout catalogue"
                                     if route.get("catalogue") else UNMEASURED)),
        permitted_uses=(("research", "backtest") + (("live_signal",) if public else ())
                        if verdict.may("fetch_api") or verdict.may("machine_extract")
                        or verdict.may("read_manual") else ()),
        redistribution_rights=("NONE unless the licence grants it" if public else UNMEASURED),
        personal_data_status=("AGGREGATED" if "social" in str(cand.get("source_class"))
                              else "NONE"),
        mnpi_review_status=("NOT_APPLICABLE" if public and label != "LICENSED"
                            else ("PENDING" if label != "LICENSED" else "REVIEWED_CLEAR")),
        jurisdiction=jurisdiction_of(cand, route),
        point_in_time_timestamp=at,
        revision_policy=revision_policy_of(cand, route),
        retention_policy="INDEFINITE" if public else UNMEASURED,
        compliance_owner="principal",
        provenance_state=DC.provenance_from_verdict(refused=verdict.refused,
                                                    quarantine=verdict.quarantine),
        schema={"available_time": "iso8601", "period_time": "iso8601", "value": "float"},
        timestamp_semantics=("both" if route.get("catalogue") or cand.get("pit_feasible")
                             else ("period_time" if cand.get("pit_feasible") is False
                                   else UNMEASURED)),
        machine_use_allowed=bool(verdict.machine_use_allowed),
        notes=f"access verdict {verdict.access_label} ({verdict.basis}): {verdict.reason}")
    return contract, verdict


# --------------------------------------------------------------------------- the sample
def _robots_allows(url: str) -> tuple[bool, str]:
    try:
        from research import asia_collector as ACOL
    except ImportError:                                                      # pragma: no cover
        import asia_collector as ACOL  # type: ignore[no-redef]
    return ACOL._robots_allows(url)


def _fetch(url: str) -> tuple[bytes | None, str]:
    try:
        from research import acquire_datasets as AQ
    except ImportError:                                                      # pragma: no cover
        import acquire_datasets as AQ  # type: ignore[no-redef]
    return AQ._fetch(url)


def _rows_of(raw: bytes, url: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Rows from CSV/JSON bytes through the desk's own parser; the first MAX_SAMPLE_ROWS only."""
    try:
        from research import acquire_datasets as AQ
    except ImportError:                                                      # pragma: no cover
        import acquire_datasets as AQ  # type: ignore[no-redef]
    try:
        frame = AQ._parse(raw, url)
    except Exception:
        frame = None
    if frame is None or getattr(frame, "empty", True):
        return [], []
    head = frame.head(MAX_SAMPLE_ROWS)
    rows = [{str(k): (v if isinstance(v, (int, float, str)) or v is None else str(v))
             for k, v in rec.items()} for rec in head.to_dict("records")]
    return rows, [str(c) for c in head.columns]


def sample(cand: dict[str, Any], contract: DC.DatasetContract, verdict: AC.AccessVerdict, *,
           at: str, code: str, marks: set[str]) -> dict[str, Any]:
    """A small lawful sample, or the named reason there is none. NEVER a new scraper."""
    url = str(cand.get("url") or "")
    if not contract.admissible():
        return {"dataset": cand["dataset"], "status": "REFUSED_INADMISSIBLE",
                "why": "; ".join(contract.admission().reasons)}
    if not verdict.machine_use_allowed or not (verdict.may("machine_extract")
                                               or verdict.may("fetch_api")):
        return {"dataset": cand["dataset"], "status": "REGISTERED_NO_MACHINE_EXTRACTION",
                "why": "the terms forbid machine extraction: registered, never fetched"}
    if not url:
        return {"dataset": cand["dataset"], "status": "NO_PUBLIC_URL_ROUTE",
                "why": (f"route is {cand.get('how_to_fetch') or 'undeclared'}: no URL to sample "
                        f"through the existing fetch path; the request is donated unsampled")}
    allowed, robots_note = _robots_allows(url)
    if not allowed:
        return {"dataset": cand["dataset"], "status": "BLOCKED_BY_ROBOTS", "url": url,
                "why": robots_note}
    raw, ctype = _fetch(url)
    if raw is None:
        return {"dataset": cand["dataset"], "status": "UNREACHABLE", "url": url,
                "why": f"fetch returned nothing ({ctype})"}
    raw = raw[:MAX_SAMPLE_BYTES]
    rows, columns = _rows_of(raw, url)
    snap = DC.snapshot(contract, rows, at=at, code_version=code, transform="sample")
    held_cols = [c for c in columns if _slug(c) in marks]
    return {"dataset": cand["dataset"], "status": "SAMPLED", "url": url, "bytes": len(raw),
            "content_type": ctype, "rows": len(rows), "columns": columns[:24],
            "robots": robots_note, "vintage": snap.vintage.to_json(),
            "lineage": snap.lineage.to_json(),
            "redundancy_against_held": {"columns_held": held_cols,
                                        "share": (len(held_cols) / len(columns)) if columns
                                        else None,
                                        "basis": "column names against data_scout's held marks"}}


# ----------------------------------------------------------------------------- scoring
def score(cand: dict[str, Any], *, marks: set[str], catalogue: Any, at: str
          ) -> dict[str, Any]:
    named = cand["named_by"]
    measured_p = [float(n["p_survivor"]) for n in named if n.get("p_survivor") is not None]
    p_survivor = max(measured_p) if measured_p else PRIOR_P_SURVIVOR
    p_basis = ("max over measured registers" if measured_p
               else f"prior {PRIOR_P_SURVIVOR}: no judged neighbourhood")
    red, red_basis = redundancy(cand["observable"], marks)
    independence = 1.0 - red
    information_gain = sum(float(n["value"]) for n in named)
    diversification = information_gain * independence
    route = route_and_cost(cand, catalogue)
    denom = float(route["data_cost"]) + COMPUTE_COST + float(route["engineering"])
    contract, verdict = contract_for(cand, route, at)
    legal = 1 if contract.admissible() else 0
    # TWO TASKS, ONE GATE EACH. ACQUIRE (fetch, sample, use) needs the full contract admitted.
    # SOURCE_HUNT (ask the scouts to find a lawful public source for a dataset nobody has
    # located) needs only that the dataset is not BLOCKED: a hole in the coverage tensor has
    # no source yet, so its contract is incomplete by construction, and refusing to even look
    # for one would turn the legality gate into a brake on discovery.
    legal_hunt = 0 if (contract.provenance_state == "BLOCKED"
                       or contract.public_or_licensed in AC.REFUSED_LABELS
                       or contract.personal_data_status == "PERSONAL") else 1
    raw_ev = p_survivor * diversification / max(denom, 1e-9)
    ev = raw_ev * legal
    ev_hunt = raw_ev * legal_hunt
    task = "ACQUIRE" if legal else ("SOURCE_HUNT" if legal_hunt else "REFUSED")
    return {
        "dataset": cand["dataset"], "observable": cand["observable"], "country": cand["country"],
        "url": cand.get("url") or "", "ev": round(ev, 8), "ev_if_legal": round(raw_ev, 8),
        "ev_hunt": round(ev_hunt, 8), "task": task,
        "terms": {"p_survivor": round(p_survivor, 6), "p_basis": p_basis,
                  "information_gain": round(information_gain, 6),
                  "independence": round(independence, 6),
                  "diversification_value": round(diversification, 6),
                  "redundancy": round(red, 6), "redundancy_basis": red_basis,
                  "data_cost": route["data_cost"], "compute": COMPUTE_COST,
                  "engineering": route["engineering"], "cost_basis": route["cost_basis"],
                  "legal": legal, "legal_hunt": legal_hunt},
        "held_already": red >= 1.0,
        "n_registers": len(named), "named_by": named[:8],
        "mechanisms": cand["mechanisms"], "assets": cand["assets"],
        "route": route, "contract": contract.to_json(),
        "admission": DC.gate(contract, raw_ev).to_json(),
        "machine_use_allowed": verdict.machine_use_allowed,
        "_contract": contract, "_verdict": verdict,
    }


# ------------------------------------------------------------------------------- recording
def _request_rows(ranked: list[dict[str, Any]], samples: dict[str, dict[str, Any]], at: str
                  ) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in ranked:
        if r["task"] == "REFUSED" or r["held_already"] or r["ev_hunt"] <= 0.0:
            continue
        rows.append({
            "kind": "dataset_request", "source": SEAT, "needs_selector_work": True,
            "task": r["task"], "ev_acquire": r["ev"], "ev_hunt": r["ev_hunt"],
            "dataset": r["dataset"], "observable": r["observable"],
            "title": f"dataset request: {r['observable']}",
            "text": (f"The acquisition scientist ranks {r['observable']} at expected research "
                     f"value {r['ev']:.6f} ({FORMULA}); named by {r['n_registers']} register(s): "
                     + "; ".join(f"{n['register']} {n['ref']}" for n in r['named_by'][:4])
                     + ". A contract is attached; legality was a hard gate, not a term."),
            "expected_value": r["ev"] if r["task"] == "ACQUIRE" else r["ev_hunt"],
            "ev_terms": r["terms"], "contract": r["contract"],
            "named_by": r["named_by"], "mechanisms": r["mechanisms"], "symbols": r["assets"][:8],
            "url": r.get("url") or "", "country": r.get("country") or "",
            "machine_use_allowed": r.get("machine_use_allowed"),
            "route": {k: r["route"][k] for k in ("catalogue", "how_to_fetch", "access")},
            "sample": samples.get(r["dataset"]),
            "available_time": at, "event_time": at,
            "public_source": "desks/mt5/reports/DATA_ACQUISITION.json",
        })
    return rows


def _due(state: dict[str, Any], row: dict[str, Any], now: datetime) -> bool:
    have = state.get(row["dataset"])
    if not isinstance(have, dict):
        return True
    try:
        last = datetime.fromisoformat(str(have.get("last_donated_at")))
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return True
    old_ev = float(have.get("ev") or 0.0)
    changed = abs(float(row["expected_value"]) - old_ev) > EV_CHANGE_TO_REREQUEST * max(old_ev,
                                                                                      1e-9)
    return changed or (now - last).total_seconds() > RE_REQUEST_H * 3600.0


def donate(rows: list[dict[str, Any]], at: str, code: str) -> dict[str, Any]:
    stamped = [pit_stamp(dict(r), SEAT, source_version=code) for r in rows]
    INTEL.mkdir(parents=True, exist_ok=True)
    path = INTEL / f"discoveries_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M')}.json"
    _atomic(path, stamped)
    return {"rows": len(stamped), "path": str(path), "seat": f"data/intelligence/{SEAT}"}


def register_hunt(row: dict[str, Any], conn: Any) -> bool:
    """OPEN THE ACQUISITION TASK IN THE REGISTRY'S SOURCE-HUNT QUEUE: a `sources` row in status
    `candidate` (the scout swarm's crawl queue) carrying the URL, when the terms let a machine
    read it. A dataset with no URL, or whose terms forbid machine extraction, is registered as a
    dataset source by `data_scout._register_source` instead and never queued for a crawl."""
    url = str(row.get("url") or "")
    if not url or row.get("machine_use_allowed") is False or row.get("task") != "ACQUIRE":
        return False
    try:
        from research import source_frontier as SF
    except ImportError:                                                      # pragma: no cover
        import source_frontier as SF  # type: ignore[no-redef]
    return bool(SF.register_source(
        f"hunt:{row['dataset']}", url=url, kind="dataset_request",
        country=str(row.get("country") or ""), asset_classes=list(row.get("symbols") or []),
        discovered_from=SEAT, discovered_via="acquisition_request", status="candidate",
        licence_note=str(row["contract"].get("licence_version") or "")[:300],
        meta={"expected_value": row["expected_value"], "observable": row["observable"],
              "contract_hash": row["contract"].get("contract_hash")}, conn=conn))


def source_roi_of(source_id: str, conn: Any) -> dict[str, Any]:
    try:
        from research import source_frontier as SF
    except ImportError:                                                      # pragma: no cover
        import source_frontier as SF  # type: ignore[no-redef]
    try:
        return SF.source_roi(source_id, conn)
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"source_roi raised {type(exc).__name__}: {exc}"}


def source_roi_ledger(state: dict[str, Any], marks: set[str], conn: Any, now: str, *,
                      dry_run: bool = False) -> tuple[list[dict[str, Any]], bool]:
    """DELAYED SOURCE ROI: for every dataset ever requested, whether a held mark now answers it
    (acquired), how long that took from the first request, the EV claimed at request time, and
    what the registry's source-yield posteriors say its leads have earned since. The first time
    a request reads as acquired its source gets one lead, so the ROI posterior starts counting;
    a prior-only row is nobody's evidence and says so."""
    rows: list[dict[str, Any]] = []
    changed = False
    for key, have in sorted(state.items()):
        if not isinstance(have, dict):
            continue
        observable = str(have.get("observable") or key)
        acquired = not DS.is_missing(observable, marks)
        if acquired and not have.get("acquired_at") and not dry_run:
            have["acquired_at"] = now
            changed = True
            try:
                from research import source_frontier as SF
                SF.bump_source_yield(f"dataset:{key}", conn, leads=1.0)
            except Exception:
                pass
        delay_s: float | None = None
        first = have.get("first_requested_at")
        if have.get("acquired_at") and first:
            try:
                delay_s = (datetime.fromisoformat(str(have["acquired_at"]))
                           - datetime.fromisoformat(str(first))).total_seconds()
            except (TypeError, ValueError):
                delay_s = None
        rows.append({"dataset": key, "observable": observable, "first_requested_at": first,
                     "last_donated_at": have.get("last_donated_at"), "acquired": acquired,
                     "acquired_at": have.get("acquired_at"), "delay_s": delay_s,
                     "ev_at_request": have.get("ev"),
                     "roi": source_roi_of(f"dataset:{key}", conn)})
    return rows, changed


def record_registry(rows: list[dict[str, Any]], conn: Any) -> dict[str, Any]:
    new_disc = 0
    new_src = 0
    hunts = 0
    for r in rows:
        try:
            _, created = REG.record_discovery(
                source_id=f"dataset:{r['dataset']}", source_type="dataset_request",
                mechanism=(r["mechanisms"][0] if r["mechanisms"] else "missing dataset"),
                origin="DESK", generator=SEAT, assets=r["symbols"],
                required_data=[r["observable"]],
                economic_rationale=str(r["text"])[:300],
                payload={"expected_value": r["expected_value"], "ev_terms": r["ev_terms"],
                         "contract_hash": r["contract"].get("contract_hash")}, conn=conn)
            new_disc += int(created)
            new_src += int(DS._register_source({
                "source": r["observable"], "observable_class": r["route"].get("catalogue") or "",
                "cadence": UNMEASURED, "pit_status": r["contract"].get("timestamp_semantics"),
                "how_to_fetch": r["route"].get("how_to_fetch"), "cost": r["ev_terms"]["data_cost"],
                "integration_effort": r["ev_terms"]["engineering"], "access": r["route"].get(
                    "access"), "score": r["expected_value"]}, conn=conn))
            hunts += int(register_hunt(r, conn))
        except Exception as exc:
            return {"status": "ERROR", "why": f"{type(exc).__name__}: {exc}",
                    "discoveries_new": new_disc, "sources_new": new_src, "hunts_opened": hunts}
    return {"status": "OK", "discoveries_new": new_disc, "sources_new": new_src,
            "hunts_opened": hunts, "rows": len(rows)}


# ------------------------------------------------------------------------------- the pass
def build(*, budget_s: float = BUDGET_S, dry_run: bool = False, conn: Any = None,
          packs: dict[str, Any] | None = None, catalogue: Any = None,
          axes_dir: Path | None = None, value_path: Path | None = None,
          top_k: int = TOP_K, max_samples: int = MAX_SAMPLES) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + budget_s
    at = now_iso()
    code = _code_version()
    registers: dict[str, Any] = {}
    unmeasured: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for name, loader in (("coverage_holes", from_coverage_holes),
                         ("residual_targets", from_residual_targets),
                         ("missed_trade_parents", from_missed_trade_parents)):
        got, note = loader()
        rows.extend(got)
        registers[name] = note
        if note.get("status") == UNMEASURED:
            unmeasured.append({"register": name, **note})
    pack_notes: list[str] = []
    if packs is None and time.monotonic() < deadline:
        try:
            packs, pack_notes = load_packs()
        except Exception as exc:
            packs, pack_notes = {}, [f"load_packs raised {type(exc).__name__}: {exc}"]
    got, note = from_country_packs(packs or {})
    rows.extend(got)
    registers["country_packs"] = {**note, "notes": pack_notes[:10]}
    if note.get("status") == UNMEASURED:
        unmeasured.append({"register": "country_packs", **note})
    c = conn or REG.connect()
    try:
        got, note = from_needs(c, axes_dir=axes_dir, value_path=value_path)
        rows.extend(got)
        registers["needs"] = note
        if note.get("status") == UNMEASURED:
            unmeasured.append({"register": "needs", **note})
        merged = merge(rows)
        marks, _why = DS.held_observables(axes_dir)
        cat = catalogue if catalogue is not None else DS.CATALOGUE
        scored = [score(cand, marks=marks, catalogue=cat, at=at) for cand in merged.values()]
        scored.sort(key=lambda r: (-r["ev_hunt"], -r["ev"], r["dataset"]))
        held = [r for r in scored if r["held_already"]]
        blocked = [{"dataset": r["dataset"], "ev_if_legal": r["ev_if_legal"],
                    "reasons": r["admission"]["reasons"]}
                   for r in scored if not r["admission"]["admitted"]]
        no_machine = [r["dataset"] for r in scored if r["machine_use_allowed"] is False]
        top = [r for r in scored if r["ev_hunt"] > 0.0 and not r["held_already"]][:top_k]
        samples: dict[str, dict[str, Any]] = {}
        for r in [t for t in top if t["task"] == "ACQUIRE"]:
            if len(samples) >= max_samples or time.monotonic() >= deadline:
                break
            if dry_run:
                samples[r["dataset"]] = {"dataset": r["dataset"], "status": "SKIPPED_DRY_RUN",
                                         "why": "a dry run fetches nothing"}
                continue
            samples[r["dataset"]] = sample(r, r["_contract"], r["_verdict"], at=at, code=code,
                                           marks=marks)
        requests = _request_rows(top, samples, at)
        state = _read_json(STATE, {}) if STATE.exists() else {}
        if not isinstance(state, dict):
            state = {}
        now = datetime.now(tz=UTC)
        due = [r for r in requests if _due(state, r, now)]
        donation: dict[str, Any] = {"rows": 0, "path": None, "seat": f"data/intelligence/{SEAT}",
                                    "status": "SKIPPED_DRY_RUN" if dry_run else
                                    ("NOTHING_DUE" if not due else "WRITTEN")}
        registry: dict[str, Any] = {"status": "SKIPPED_DRY_RUN"}
        if not dry_run:
            if due:
                donation.update(donate(due, at, code))
                registry = record_registry(due, c)
                for r in due:
                    prior = state.get(r["dataset"])
                    prior = prior if isinstance(prior, dict) else {}
                    state[r["dataset"]] = {
                        "last_donated_at": at, "ev": r["expected_value"],
                        "task": r["task"], "observable": r["observable"],
                        "first_requested_at": prior.get("first_requested_at") or at,
                        "acquired_at": prior.get("acquired_at")}
            else:
                registry = {"status": "NOTHING_DUE"}
        # DELAYED SOURCE ROI over every request ever made, this pass's included.
        roi_rows, roi_changed = source_roi_ledger(state, marks, c, at, dry_run=dry_run)
        if not dry_run:
            if due or roi_changed:
                _atomic(STATE, state)
            for key, s in samples.items():
                if s.get("status") == "SAMPLED":
                    _atomic(SAMPLES / f"{_slug(key)}.json", s)
    finally:
        if conn is None:
            c.close()
    public = [{k: v for k, v in r.items() if not k.startswith("_")} for r in scored]
    report = {
        "at": at, "rule": RULE, "law": "LAWS 5m; RESEARCH 11", "formula": FORMULA,
        "budget_s": budget_s, "elapsed_s": round(time.monotonic() - started, 2),
        "dry_run": dry_run, "code_version": code,
        "registers": registers,
        "candidates": {"named": len(rows), "merged": len(merged), "held_already": len(held),
                       "held_examples": [r["dataset"] for r in held[:10]],
                       "scored": len(scored), "top_k": top_k},
        "ranked": [{**{k: v for k, v in r.items()
                       if k not in ("_contract", "_verdict", "contract", "named_by", "route")},
                    "route": {k: r["route"].get(k) for k in ("catalogue", "how_to_fetch",
                                                              "access")}}
                   for r in public[:top_k]],
        "legality": {"gate": DC.LEGALITY_RULE,
                     "admissible": sum(1 for r in scored if r["admission"]["admitted"]),
                     "blocked": blocked[:40], "n_blocked": len(blocked),
                     "registered_no_machine_extraction": no_machine[:40],
                     "by_task": {t: sum(1 for r in scored if r["task"] == t)
                                 for t in ("ACQUIRE", "SOURCE_HUNT", "REFUSED")},
                     "contract_fields": list(DC.CONTRACT_FIELDS)},
        "samples": list(samples.values()),
        "requests": {"built": len(requests), "due": len(due),
                     "by_task": {t: sum(1 for r in requests if r["task"] == t)
                                 for t in ("ACQUIRE", "SOURCE_HUNT")},
                     "datasets": [r["dataset"] for r in requests[:top_k]]},
        "donations": donation, "registry": registry,
        "source_roi": {"n": len(roi_rows), "acquired": sum(1 for r in roi_rows if r["acquired"]),
                       "rows": roi_rows[:60],
                       "rule": "delayed ROI: a request is scored again when a held mark answers "
                               "it, by the delay from first request and the source-yield "
                               "posteriors of what it then produced"},
        "state": {"path": str(STATE), "known_requests": len(state)},
        "unmeasured": unmeasured,
    }
    if not dry_run:
        _atomic(OUT, report)
    return report


def summary_lines(doc: dict[str, Any]) -> list[str]:
    c = doc["candidates"]
    top = doc["ranked"][:3]
    return [f"data_acquisition_scientist: {c['named']} named -> {c['merged']} datasets, "
            f"{c['held_already']} already held, {doc['legality']['admissible']} admissible, "
            f"{doc['legality']['n_blocked']} blocked by the legality gate; "
            f"requests built {doc['requests']['built']} due {doc['requests']['due']}; "
            f"samples {len(doc['samples'])}; top: "
            + ", ".join(f"{r['dataset']} ({r['ev']:.4f})" for r in top)
            + f"; {doc['elapsed_s']}s" + (" DRY-RUN" if doc.get("dry_run") else "")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--top-k", type=int, default=TOP_K)
    ap.add_argument("--max-samples", type=int, default=MAX_SAMPLES)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    doc = build(budget_s=args.budget_s, dry_run=args.dry_run, top_k=args.top_k,
                max_samples=args.max_samples)
    for line in summary_lines(doc):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
