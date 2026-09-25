"""THE COVERAGE TENSORS, BUILT FROM THE DESK'S OWN EVIDENCE, AND THE FRONTIER ENGINE ON THEM.

LAWS 5f makes the two tensors AUTHORITATIVE. `libs/research/coverage.py` is the algebra (axes,
ladders, sparse storage, monotone `advance`, `marginals`, `holes`, EVIG, `covered`, `ratchet`);
this organ is the half that MEASURES -- it reads what the desk already holds, assigns every cell
the highest ladder state its evidence supports, enumerates the highest-value holes and hands them
to the machine as work.

WHERE EVERY STATE COMES FROM (and an absent source is named UNMEASURED, never read as zero):

    SOURCE_HUNT / DISCOVERED  registry `sources` rows and the country packs' declared sources
    VERIFIED                  a `sources` row that was actually fetched (`last_crawled`), or a
                              pack source row flagged verified
    INGESTED                  `research/ingestion_ledger.py`'s ledger and report, the broker bar
                              estate, the axis series
    REPRESENTED               `reports/REPRESENTATION_FORGE.json`
    CANDIDATES                registry `research_candidates`
    TESTING / FAILED          registry `trials_ledger` and `data/hypotheses/gate_verdict_ledger`
    FORWARD                   `data/forward_reconcile.json`, `reports/forward_reconcile.json`
    CERTIFIED                 `data/certificates/*`, `reports/UNIVERSAL_SURVIVORS.json`, cards
    LIVE                      `data/sleeves.json` LIVE/STANDBY rows
    DECAYED                   retired sleeves, retired cards, `data/GOLD_RETIRED.json`

THE HOLE IS THE PRODUCT. Each pass projects both tensors onto the next axis subset in a ROTATION
(the cursor lives in `data/coverage_cursor.json`, so successive passes cover different faces of a
ten-dimensional object rather than re-ranking one face forever), ranks the coordinates still at
the floor by EVIG, and writes the top ones TWICE: as `frontier_map` rows in the canonical registry
(the durable record) and as DISCOVERIES of kind `coverage_gap` in state UNPROCESSED, whose payload
names the cell AND THE ONE MOVE that raises it a rung -- which source to hunt, which dataset to
ingest, which representation to build, which candidate to compile. The scouts, the forests and
`discovery_compiler` consume discoveries; nothing here compiles, judges or sizes anything.

IDEMPOTENCE IS BY CONTENT HASH, not by a timestamp. A discovery is keyed on
(source_id, mechanism, assets, exact_rule) and the exact_rule carries the cell key and the rung
being asked for, so the same hole re-enumerated next hour returns the existing discovery id and
records nothing new. `frontier_map` is an UPSERT on `cell`.

WHAT THIS ORGAN DELIBERATELY DOES NOT WRITE. `frontier_map.chao1_unseen`, `n_distinct`,
`n_singletons` and `n_doubletons` are left NULL on the rows it owns. Those columns are
`source_frontier`'s Chao1 estimate of unseen source classes, and `global_research_os.unseen_mass`
divides by their sum: writing a measured-looking 0 would tell the global OS that a country's
ground is exhausted when this organ measured no such thing. Its rows are prefixed `coverage:` so
they never collide with the scout swarm's.

    python desks/mt5/research/coverage_tensor.py --once --budget-s 900
    python desks/mt5/research/coverage_tensor.py --once --dry-run
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.research import coverage as CV  # noqa: E402

#: Module globals, not frozen constants: the tests point the whole organ at a tmp desk.
DATA = BASE / "data"
REPORTS = BASE / "reports"
UNIVERSE_JSON = DATA / "universe" / "universe.json"
UNIVERSE_DIR = DATA / "universe"
SLEEVES = DATA / "sleeves.json"
CERT_DIR = DATA / "certificates"
SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
GATE_LEDGER = DATA / "hypotheses" / "gate_verdict_ledger.jsonl"
FORWARD_DATA = DATA / "forward_reconcile.json"
FORWARD_REPORT = REPORTS / "forward_reconcile.json"
SHADOW_STATE = REPORTS / "shadow" / "shadow_state.json"
INGESTION_REPORT = REPORTS / "INGESTION_LEDGER.json"
INGESTION_EXPLOIT = REPORTS / "INGESTION_EXPLOITATION.json"
INGESTION_JSONL = DATA / "ingestion_ledger.jsonl"
FORGE_REPORT = REPORTS / "REPRESENTATION_FORGE.json"
FORGE_MODULE = BASE / "research" / "representation_forge.py"
GOLD_RETIRED = DATA / "GOLD_RETIRED.json"
AXES_DIR = DATA / "axes"
COUNTRIES_DIR = BASE / "research" / "countries"
CURSOR = DATA / "coverage_cursor.json"
FLOORS = DATA / "coverage_floors.json"
OUT = REPORTS / "COVERAGE_TENSOR.json"

BUDGET_S = 900.0
TOP_K = 24                   # holes ranked per axis subset
MAX_DISCOVERIES = 40         # holes handed to the machine per pass
MAX_FRONTIER_ROWS = 120
MAX_GATE_LINES = 400_000
MAX_REGISTRY_ROWS = 20_000
MAX_ENUMERATE = 120_000
#: Faces of the tensor ranked per pass. The rotation exists so ten axes are covered ACROSS
#: passes; ranking every subset every hour would re-rank one static picture and never
#: advance the cursor at all.
SUBSETS_PER_PASS = 2
SOURCE_TYPE = "coverage_tensor"
ORIGIN = "DESK"              # `registry.origin_of` vocabulary: MOAT | EXTERNAL | DESK
GAP_KIND = "coverage_gap"
UNMEASURED = CV.UNMEASURED
ANY = CV.ANY

#: The rotation. Each pass takes the next subset for each tensor; the cursor is durable, so ten
#: axes are covered across passes instead of one face being re-ranked forever.
WORLD_ROTATION: tuple[tuple[str, ...], ...] = (
    ("country", "sector", "information_type"),
    ("country", "mechanism", "asset"),
    ("sector", "mechanism", "session"),
    ("country", "asset", "session", "regime"),
    ("information_type", "representation", "mechanism"),
    ("mechanism", "horizon", "execution"),
    ("country", "sector", "asset"),
    ("asset", "session", "regime", "horizon"),
)
FOREST_ROTATION: tuple[tuple[str, ...], ...] = (
    ("country", "source_class"),
    ("country", "language", "source_class"),
    ("source_class", "sector", "mechanism"),
    ("country", "sector", "asset_transmission"),
    ("language", "source_class", "freshness"),
    ("country", "source_class", "accessibility"),
)

#: THE REGIME ROUTER'S OWN VOCABULARY. `regime_router` writes its bucket labels as inline strings
#: (`vol` low/mid/high, `risk` on/off/flat, `usd` up/down/flat) rather than as constants, so they
#: are mirrored here in the SAME spelling and the router's `AXES` tuple is read at run time to
#: prove the axis set still matches. `unconditional` is always admissible: a mechanism that pays
#: in every state is a stronger claim than one that pays in one.
ROUTER_LABELS: dict[str, tuple[str, ...]] = {
    "vol": ("low", "mid", "high"), "risk": ("on", "off", "flat"), "usd": ("up", "down", "flat"),
}
REGIME_FALLBACK: tuple[str, ...] = ("unconditional", "vol_low", "vol_mid", "vol_high", "risk_on",
                                    "risk_off", "usd_up", "usd_down")

#: The transforms the representation forge is specified to produce (LAWS 5c.2). Used ONLY when the
#: forge's own report is absent AND its module cannot be read -- and then the axis is reported
#: UNMEASURED beside it, because a vocabulary is not a measurement.
REPRESENTATION_FALLBACK: tuple[str, ...] = (
    "level", "delta", "acceleration", "surprise", "percentile", "zscore", "relative_to_history",
    "cross_country_spread", "residual", "revision_surprise", "diffusion", "rolling_beta",
    "regime_transition", "abnormality", "embedding", "interaction")

#: What raises a cell ONE RUNG, per ladder state. This is the sentence the discovery carries.
NEXT_MOVE: dict[str, dict[str, str]] = {
    CV.WORLD: {
        "UNOBSERVED": "hunt a source: run the country/sector source scouts for this cell and "
                      "register what they find in the registry's `sources` table",
        "SOURCE_HUNT": "ingest the dataset a registered source serves for this cell, through "
                       "research/ingestion_ledger.py, with its PIT stamps",
        "INGESTED": "build the representation this cell needs in the representation forge "
                    "(level/delta/surprise/percentile/residual/...) with a PIT stamp",
        "REPRESENTED": "compile a candidate: the discovery compiler turns this representation x "
                       "mechanism x asset x session x regime x horizon into an exact rule",
        "CANDIDATES": "queue the compiled cell into the gauntlet docket so a trial is run",
        "TESTING": "let the gauntlet finish judging this cell and record the terminal gate",
        "FAILED": "the cell lost: mine the failure for a sibling mechanism, never a "
                  "re-parameterisation of what already lost here",
        "FORWARD": "let the forward clock accrue until its certificate is decidable",
        "CERTIFIED": "enrol the certificate on a forward clock and let the promoter judge it",
        "LIVE": "the cell is funded; watch its decay",
        "DECAYED": "the cell decayed: record the negative knowledge and retire its clock",
    },
    CV.FOREST: {
        "UNSEEN": "hunt this ground: native-language queries for this country x layer, in the "
                  "country's own script, and register every root found",
        "SOURCE_HUNT": "fetch a registered root so the source becomes DISCOVERED rather than a "
                       "typed wish",
        "DISCOVERED": "verify the source: FETCH IT (every label off the five refused acts is "
                      "mined -- LAWS 5e, 2026-09-23), classify its access label, and record the "
                      "terms note that routes its redistribution",
        "VERIFIED": "ingest this source's series/documents with PIT stamps",
        "INGESTED": "build representations over what this source serves",
        "REPRESENTED": "compile candidates from this source's mechanism into the executable "
                       "instrument its transmission names",
        "CANDIDATES": "run the gauntlet on this source's cells",
        "TESTED": "enrol the survivors on forward clocks",
        "FORWARD": "let the forward evidence accrue",
        "LIVE": "the lineage is funded; pay delayed credit back to this source",
        "FAILED": "negative knowledge: this source's mechanism lost; reduce its budget, keep its "
                  "scout (LAWS 5f: never to zero)",
    },
}

RULE = ("the two coverage tensors are authoritative (LAWS 5f); every hole is an explicit frontier "
        "row with a state, an EVIG breakdown and the ONE move that raises it a rung; no country is "
        "covered because five obvious sources were added; floors ratchet up only")


# --------------------------------------------------------------------------------- small helpers
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _tok(value: Any) -> str:
    text = " ".join(str(value or "").strip().lower().replace("-", " ").replace("_", " ").split())
    return text.replace(" ", "_")



def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _write_atomic(path: Path, payload: Any) -> None:
    """Atomic where the filesystem allows it; `os.replace` onto a read-only destination is legal
    on POSIX and raises WinError 5 on Windows, and this organ runs on the Windows trading box."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        with contextlib.suppress(OSError):
            path.chmod(0o644)
        os.replace(tmp, path)


def _jsonl(path: Path, max_lines: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with Path(path).open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if len(rows) >= max_lines:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except OSError:
        return []
    return rows


class Absent:
    """The UNMEASURED ledger: every evidence source this pass could not read, by name."""

    def __init__(self) -> None:
        self.rows: dict[str, str] = {}

    def note(self, name: str, why: str) -> None:
        self.rows.setdefault(name, why)

    def missing(self, name: str, path: Path, what: str) -> bool:
        """True when the path is absent; records the UNMEASURED line naming what measures it."""
        if Path(path).exists():
            return False
        self.note(name, f"{path} is not on this box: {what} is UNMEASURED, not zero")
        return True

    def to_json(self) -> dict[str, str]:
        return dict(sorted(self.rows.items()))


# ------------------------------------------------------------------------------- the vocabularies
def _country_lab() -> Any:
    try:
        from libs.research import country_lab as CL
    except Exception:                                                        # noqa: BLE001
        return None
    return CL


def countries(absent: Absent) -> dict[str, dict[str, Any]]:
    """code -> {region, languages, instruments, pack}. From `country_lab` when it is on the tree,
    else from the packs' own directory names and the two region mandates."""
    out: dict[str, dict[str, Any]] = {}
    CL = _country_lab()
    codes: list[str] = []
    if COUNTRIES_DIR.exists():
        codes = sorted(p.name for p in COUNTRIES_DIR.iterdir()
                       if p.is_dir() and not p.name.startswith(("_", ".")))
    else:
        absent.note("country_packs", f"{COUNTRIES_DIR} is absent: the country axis falls back to "
                                     "the region mandates only")
    for code in codes:
        pack = None
        if CL is not None:
            try:
                pack = CL.resolve_pack(code)
            except Exception:                                                # noqa: BLE001
                pack = None
        if pack is None:
            out[_tok(code)] = {"region": UNMEASURED, "languages": [], "instruments": [],
                               "pack": None, "why": "pack did not resolve"}
            continue
        out[_tok(getattr(pack, "code", code))] = {
            "region": str(getattr(pack, "region_command", UNMEASURED)),
            "languages": [str(x) for x in (getattr(pack, "native_languages", ()) or ())],
            "instruments": [str(x) for x in (getattr(pack, "executable_instruments", ()) or ())],
            "pack": pack,
            "transmission": [str(getattr(s, "asset", "") or "")
                             for s in (getattr(pack, "transmission_edges_seed", ()) or ())],
        }
    if CL is None:
        absent.note("libs.research.country_lab",
                    "country_lab is not importable: layer inventories and discovery rates are "
                    "UNMEASURED and every country reads MAPPING at best")
    for mod, code, region in (("japan.mandate", "jp", "asia"),
                              ("macro_region.mandate", "global", "macro")):
        if code in out:
            continue
        try:
            m = __import__(f"research.{mod}", fromlist=["x"])
        except Exception:                                                    # noqa: BLE001
            absent.note(f"research.{mod}", "region mandate not importable")
            continue
        langs = list(getattr(m, "NATIVE_LANGUAGES", ()) or getattr(m, "LANGUAGES", ()) or ())
        out[code] = {"region": region, "languages": [str(x) for x in langs], "instruments": [],
                     "pack": None, "why": f"from research.{mod}"}
    return out


def mechanisms(absent: Absent, conn: Any) -> list[str]:
    """The mechanism vocabulary: the hypothesis graph's families' mechanisms, the transformation
    miners' CONTRACTS and the registry's `mechanisms` table, unioned and deduplicated."""
    got: list[str] = []
    try:
        from research import axis_registry as AX
        got.extend(str(m) for m in AX.MECHANISM_ACTOR if str(m) != "unknown")
    except Exception:                                                        # noqa: BLE001
        absent.note("research.axis_registry", "the mechanism-actor table is unreadable")
    try:
        from research import transformation_miners as TM
        got.extend(str(m) for m in TM.CONTRACTS)
    except Exception:                                                        # noqa: BLE001
        absent.note("research.transformation_miners", "the mechanism CONTRACTS are unreadable")
    try:
        rows = conn.execute("SELECT mechanism_id, mechanism FROM mechanisms LIMIT ?",
                            (MAX_REGISTRY_ROWS,)).fetchall()
        got.extend(str(r["mechanism_id"] or r["mechanism"] or "") for r in rows)
    except Exception as exc:                                                 # noqa: BLE001
        absent.note("registry.mechanisms", f"unreadable: {type(exc).__name__}")
    else:
        if not rows:
            absent.note("registry.mechanisms", "the mechanisms table is EMPTY: the mechanism axis "
                                               "is the code's vocabulary, not the desk's record")
    return sorted({_tok(m) for m in got if m and _tok(m) != "unknown"})


def representations(absent: Absent) -> tuple[list[str], str]:
    """(vocabulary, basis). The forge's report first, its module's transform names second, and the
    specified transform list LAST -- with the axis reported UNMEASURED beside it."""
    doc = _read_json(FORGE_REPORT)
    if isinstance(doc, dict):
        names: list[str] = []
        for key in ("transforms", "representations", "families"):
            raw = doc.get(key)
            if isinstance(raw, Mapping):
                names.extend(str(k) for k in raw)
            elif isinstance(raw, list):
                names.extend(str(x.get("name") if isinstance(x, Mapping) else x) for x in raw)
        if names:
            return sorted({_tok(n) for n in names if n}), "REPRESENTATION_FORGE.json"
    forge = Path(FORGE_MODULE)
    if forge.exists():
        try:
            text = forge.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        names = []
        for line in text.splitlines():
            s = line.strip()
            if s.startswith('"') and s.endswith(('",', '"')) and 2 < len(s) < 40:
                names.append(_tok(s.strip('",')))
        if names:
            return sorted(set(names)), "representation_forge.py (module vocabulary)"
    absent.note("representation_forge",
                f"neither {FORGE_REPORT} nor a readable {FORGE_MODULE}: the "
                "representation axis is UNMEASURED and falls back to the LAWS 5c.2 transform list")
    return list(REPRESENTATION_FALLBACK), f"{UNMEASURED} (LAWS 5c.2 transform list)"


def assets(absent: Absent) -> dict[str, dict[str, Any]]:
    """symbol -> {asset_class, lane}. The hypothesis lane only; the event lane is reported."""
    doc = _read_json(UNIVERSE_JSON)
    if not isinstance(doc, dict):
        absent.note("universe.json", f"{UNIVERSE_JSON} unreadable: the asset axis is UNMEASURED")
        return {}
    try:
        from research import universe_policy as UP
    except Exception:                                                        # noqa: BLE001
        absent.note("research.universe_policy", "lane routing unavailable: no symbol is admitted "
                                                "to the hypothesis axis without it")
        return {}
    out: dict[str, dict[str, Any]] = {}
    for sym, row in doc.items():
        if not isinstance(row, Mapping):
            continue
        out[str(sym)] = {"asset_class": _tok(row.get("asset_class")), "lane": UP.lane(str(sym))}
    return out


def regimes(absent: Absent) -> list[str]:
    """The regime router's vocabulary: `unconditional` plus `<axis>_<label>` for its own axes."""
    try:
        from research import regime_router as RR
        axes = tuple(str(a) for a in RR.AXES)
    except Exception:                                                        # noqa: BLE001
        absent.note("research.regime_router",
                    "the router is unreadable: the regime axis falls back to its last known "
                    "vocabulary and is UNMEASURED against the live router")
        return list(REGIME_FALLBACK)
    out = ["unconditional"]
    for axis in axes:
        for label in ROUTER_LABELS.get(axis, ()):
            out.append(f"{axis}_{label}")
    if len(out) == 1:
        absent.note("regime_router.AXES",
                    f"the router declares axes {axes} and none carries a label table here")
        return list(REGIME_FALLBACK)
    return out


def languages(country_rows: Mapping[str, Mapping[str, Any]]) -> list[str]:
    out = {str(lang).lower() for row in country_rows.values()
           for lang in (row.get("languages") or ())}
    return sorted(out) or ["en"]


# ------------------------------------------------------------------------------- the observations
def _asset_country(country_rows: Mapping[str, Mapping[str, Any]]) -> dict[str, list[str]]:
    """symbol -> the countries whose pack names it executable or names it as a transmission
    target. A symbol nobody claims stays at country=ANY, which is a coordinate, not a wildcard."""
    out: dict[str, list[str]] = {}
    for code, row in country_rows.items():
        for sym in list(row.get("instruments") or ()) + list(row.get("transmission") or ()):
            if sym:
                out.setdefault(str(sym).upper(), []).append(code)
    return {k: sorted(set(v)) for k, v in out.items()}


def _world_coords(world: CV.Tensor, *, asset: str = ANY, mechanism: str = ANY,
                  information: str = ANY, session: str = ANY, regime: str = ANY,
                  horizon: str = ANY, execution: str = ANY, country: str = ANY,
                  sector: str = ANY, representation: str = ANY) -> tuple[str, ...]:
    return world.coordinates({
        "country": country or ANY, "sector": sector or ANY,
        "information_type": information or ANY, "mechanism": mechanism or ANY,
        "representation": representation or ANY, "asset": asset or ANY,
        "session": session or ANY, "regime": regime or ANY, "horizon": horizon or ANY,
        "execution": execution or ANY})


_HORIZON_BUCKET: dict[str, str] = {"intrabar": "1h", "sub_4h": "4h", "sub_1d": "1d",
                                   "multi_day": "5d", "minutes": "1h", "hourly": "4h",
                                   "daily": "1d", "multi_day_weekly": "20d", "weekly": "20d",
                                   "1h": "1h", "4h": "4h", "1d": "1d", "5d": "5d", "20d": "20d"}
_SESSION_MAP: dict[str, str] = {"asia": "asia", "tokyo": "asia", "tokyo_fix": "tokyo_fix",
                                "london": "london", "london_am": "london",
                                "london_fix": "london_fix", "ny": "ny", "new_york": "ny",
                                "afternoon": "ny", "overlap": "overlap", "close": "close",
                                "gotobi": "gotobi", "holiday": "holiday", "all": ANY,
                                "continuous": ANY, "off": ANY}


def _horizon(value: Any) -> str:
    return _HORIZON_BUCKET.get(_tok(value), ANY)


def _session(value: Any) -> str:
    return _SESSION_MAP.get(_tok(value), ANY)


def _regime(value: Any) -> str:
    tok = _tok(value)
    if not tok or tok in ("none", "unknown", "any"):
        return ANY
    return tok


def observe_world(world: CV.Tensor, conn: Any, absent: Absent,
                  country_rows: Mapping[str, Mapping[str, Any]],
                  asset_rows: Mapping[str, Mapping[str, Any]], at: str) -> dict[str, int]:
    """Every world-tensor cell the desk's evidence supports, at the highest lawful state."""
    counts: dict[str, int] = {}
    owner = _asset_country(country_rows)

    def hit(state: str, **kw: Any) -> None:
        ev = kw.pop("evidence", None)
        world.observe(_world_coords(world, **kw), state, ev, at=at)
        counts[state] = counts.get(state, 0) + 1

    # INGESTED -- the broker's bar estate is the desk's largest ingested surface.
    if UNIVERSE_DIR.exists():
        for p in sorted(UNIVERSE_DIR.glob("*.parquet")):
            sym, _, chart = p.stem.rpartition("_")
            row = asset_rows.get(sym)
            if not row or row.get("lane") != "hypothesis":
                continue
            for cc in owner.get(sym.upper(), [ANY]):
                hit("INGESTED", asset=sym, information="market_data", country=cc,
                    horizon=_horizon(chart),
                    evidence={"source": str(p.name), "why": "broker bars on this box"})
    else:
        absent.missing("universe_bars", UNIVERSE_DIR, "the bar estate")
    if AXES_DIR.exists():
        for p in sorted(AXES_DIR.glob("*.json"))[:200]:
            hit("INGESTED", information="official_macro", representation="level",
                evidence={"source": f"data/axes/{p.name}", "why": "axis series on this box"})
    else:
        absent.missing("axis_series", AXES_DIR, "the macro axis series")

    # INGESTED -- the ingestion ledger, when the sibling organ has run.
    ing = None
    for path in (INGESTION_REPORT, INGESTION_EXPLOIT):
        doc = _read_json(path)
        if isinstance(doc, dict):
            ing = (path, doc)
            break
    if ing is None:
        rows = _jsonl(INGESTION_JSONL, 5000)
        if rows:
            ing = (INGESTION_JSONL, {"units": rows})
        else:
            absent.note("ingestion_ledger",
                        f"neither {INGESTION_REPORT} nor {INGESTION_EXPLOIT} nor "
                        f"{INGESTION_JSONL}: the ingested UNITS are UNMEASURED and the INGESTED "
                        "rung is measured from the bar estate and the axis series alone")
    if ing is not None:
        path, doc = ing
        units = doc.get("units") if isinstance(doc.get("units"), list) else []
        for unit in units[:5000]:
            if not isinstance(unit, Mapping):
                continue
            sym = str(unit.get("symbol") or "")
            hit("INGESTED", asset=sym or ANY, information=_tok(unit.get("kind")) or ANY,
                evidence={"source": str(path.name), "why": "ingestion ledger unit"})

    # REPRESENTED -- the representation forge's own report.
    forge = _read_json(FORGE_REPORT)
    if isinstance(forge, dict):
        for row in (forge.get("series") or forge.get("representations") or [])[:5000]:
            if not isinstance(row, Mapping):
                continue
            hit("REPRESENTED", asset=str(row.get("symbol") or ANY),
                representation=_tok(row.get("transform") or row.get("representation")),
                information=_tok(row.get("information")) or ANY,
                evidence={"source": "REPRESENTATION_FORGE.json",
                          "why": "a PIT-stamped representation series exists"})
    else:
        absent.missing("representation_forge_report", FORGE_REPORT,
                       "the REPRESENTED rung of the world tensor")

    # CANDIDATES / TESTING / FAILED / CERTIFIED -- the registry's candidate chain.
    try:
        cands = conn.execute(
            "SELECT symbol, asset_class, mechanism, information, session, horizon, regime, "
            "status, terminal_gate, survived FROM research_candidates LIMIT ?",
            (MAX_REGISTRY_ROWS,)).fetchall()
    except Exception as exc:                                                 # noqa: BLE001
        cands = []
        absent.note("registry.research_candidates", f"unreadable: {type(exc).__name__}: {exc}")
    for row in cands:
        sym = str(row["symbol"] or "")
        status = str(row["status"] or "")
        state = {"queued": "CANDIDATES", "donated": "CANDIDATES", "claimed": "TESTING",
                 "judged": "FAILED", "survived": "CERTIFIED"}.get(status, "CANDIDATES")
        ev = {"source": "registry.research_candidates",
              "why": f"candidate {status}" + (f" at {row['terminal_gate']}"
                                              if row["terminal_gate"] else "")}
        for cc in owner.get(sym.upper(), [ANY]):
            hit(state, asset=sym or ANY, mechanism=_tok(row["mechanism"]) or ANY,
                information=_tok(row["information"]) or ANY, session=_session(row["session"]),
                regime=_regime(row["regime"]), horizon=_horizon(row["horizon"]), country=cc,
                evidence=ev)
    if not cands:
        absent.note("registry.research_candidates",
                    "no candidate rows: the CANDIDATES rung is UNMEASURED, not empty ground")

    # TESTING / FAILED -- trials and the gate verdict ledger.
    try:
        trials = conn.execute("SELECT symbol, family, terminal_gate, passed FROM trials_ledger "
                              "ORDER BY seq DESC LIMIT ?", (MAX_REGISTRY_ROWS,)).fetchall()
    except Exception:                                                        # noqa: BLE001
        trials = []
    # THE TWO VERDICT SOURCES ARE NOT THE SAME SHAPE, and the loop below reads them as if they
    # were. `libs/moat/registry` sets `conn.row_factory = sqlite3.Row`, so `trials` arrives as
    # sqlite3.Row -- which indexes and has .keys() but has NO .get() -- while `_jsonl` returns
    # plain dicts. Line-for-line the reader calls `row.get("symbol")`, so every pass with a
    # non-empty trials ledger died on the first trial row:
    #
    #     AttributeError: 'sqlite3.Row' object has no attribute 'get'
    #
    # Measured 2026-09-23: 18 of 18 ledger rows in 26h were exit_code=1 and COVERAGE_TENSOR.json
    # had never been written on this box -- the whole coverage grid absent, reported as an organ
    # with nothing to say rather than an organ that crashed. Normalising at the JOIN is the fix:
    # both sources become dicts here, the declared Mapping type becomes true rather than
    # aspirational, and `row.get("sym")` on a column the SELECT does not name returns None
    # instead of raising.
    verdicts: list[Mapping[str, Any]] = [dict(r) for r in trials]
    if GATE_LEDGER.exists():
        verdicts.extend(_jsonl(GATE_LEDGER, MAX_GATE_LINES))
    else:
        absent.missing("gate_verdict_ledger", GATE_LEDGER, "the FAILED rung's verdicts")
    if not trials:
        absent.note("registry.trials_ledger",
                    "the trials ledger is empty on this box: verdicts come from the gate ledger")
    fam_mech = _family_mechanisms()
    for row in verdicts[:MAX_GATE_LINES]:
        sym = str(row.get("symbol") or row.get("sym") or "")
        fam = _tok(row.get("family"))
        passed = row.get("passed")
        state = "TESTING" if passed is None else ("CERTIFIED" if passed else "FAILED")
        ev = {"source": "gate_verdict_ledger/trials_ledger",
              "why": f"terminal gate {row.get('terminal_gate') or UNMEASURED}"}
        mech, info = fam_mech.get(fam, (ANY, ANY))
        for cc in owner.get(sym.upper(), [ANY]):
            hit(state, asset=sym or ANY, mechanism=mech, information=info, country=cc,
                evidence=ev)

    # FORWARD -- the forward lane's roster.
    fwd = _read_json(FORWARD_DATA)
    if not isinstance(fwd, dict):
        fwd = _read_json(FORWARD_REPORT)
        if not isinstance(fwd, dict):
            absent.note("forward_reconcile",
                        f"neither {FORWARD_DATA} nor {FORWARD_REPORT}: the FORWARD rung is "
                        "UNMEASURED")
            fwd = {}
    clocks = ((fwd.get("family_budget") or {}).get("clocks") or {}) if fwd else {}
    if not isinstance(clocks, Mapping):
        clocks = {}
    shadow = _read_json(SHADOW_STATE)
    keys: list[str] = [str(k) for k in clocks]
    if isinstance(shadow, Mapping):
        keys.extend(str(k) for k in shadow)
    elif not keys:
        absent.missing("shadow_state", SHADOW_STATE, "the forward clocks")
    for key in keys:
        sym, _, rest = key.partition(".")
        fam, _, sess = rest.partition(".")
        mech, info = fam_mech.get(_tok(fam), (ANY, ANY))
        for cc in owner.get(sym.upper(), [ANY]):
            hit("FORWARD", asset=sym or ANY, mechanism=mech, information=info,
                session=_session(sess.split("#")[0]), country=cc,
                evidence={"source": "forward_reconcile/shadow_state",
                          "why": f"forward clock {key[:80]}"})

    # CERTIFIED -- certificates on disk, the survivor ledger, and certified cards.
    certs: list[Mapping[str, Any]] = []
    if CERT_DIR.exists():
        for p in sorted(CERT_DIR.glob("*.json"))[:2000]:
            doc = _read_json(p)
            if isinstance(doc, Mapping):
                certs.append(doc)
    else:
        absent.missing("certificates_dir", CERT_DIR,
                       "certificates on disk (the survivor ledger is read instead)")
    surv = _read_json(SURVIVORS)
    if isinstance(surv, Mapping) and isinstance(surv.get("survivors"), Mapping):
        certs.extend(v for v in surv["survivors"].values() if isinstance(v, Mapping))
    elif not certs:
        absent.missing("universal_survivors", SURVIVORS, "the CERTIFIED rung")
    for doc in certs:
        spec = doc.get("shadow_spec") if isinstance(doc.get("shadow_spec"), Mapping) else {}
        sym = str(doc.get("sym") or doc.get("symbol") or spec.get("symbol") or "")
        fam = _tok(spec.get("family") or doc.get("family"))
        mech, info = fam_mech.get(fam, (ANY, ANY))
        for cc in owner.get(sym.upper(), [ANY]):
            hit("CERTIFIED", asset=sym or ANY, mechanism=mech, information=info,
                session=_session(spec.get("selector") or doc.get("session")), country=cc,
                evidence={"source": "UNIVERSAL_SURVIVORS.json/certificates",
                          "why": "ten-gate certificate"})

    # LIVE and DECAYED -- the sleeve registry and the retirements.
    sleeves = _read_json(SLEEVES)
    rows = (sleeves.get("sleeves") if isinstance(sleeves, Mapping) else sleeves) or []
    if not rows:
        absent.missing("sleeves", SLEEVES, "the LIVE rung")
    for s in rows if isinstance(rows, list) else []:
        if not isinstance(s, Mapping):
            continue
        status = str(s.get("status") or "").upper()
        sym = str(s.get("symbol") or "")
        fam = _tok(s.get("family"))
        mech, info = fam_mech.get(fam, (ANY, ANY))
        kw: dict[str, Any] = {"asset": sym or ANY, "mechanism": mech, "information": info,
                              "session": _session(s.get("session")),
                              "execution": _tok(s.get("exec")).replace("family_", "")
                              .replace("scalp_", "") or ANY}
        if status in ("LIVE", "STANDBY"):
            for cc in owner.get(sym.upper(), [ANY]):
                hit("LIVE", country=cc, evidence={"source": "sleeves.json",
                                                  "why": f"sleeve {s.get('name')} {status}"}, **kw)
        elif status:
            for cc in owner.get(sym.upper(), [ANY]):
                hit("DECAYED", country=cc,
                    evidence={"source": "sleeves.json", "why": f"sleeve {s.get('name')} {status}",
                              "retired": status}, **kw)
    retired = _read_json(GOLD_RETIRED)
    if isinstance(retired, Mapping) and retired:
        for key, why in retired.items():
            sym, _, rest = str(key).partition(".")
            hit("DECAYED", asset=sym or ANY, session=_session(rest),
                evidence={"source": "GOLD_RETIRED.json",
                          "why": str(why)[:200] or "retired gold window"})
    elif not isinstance(retired, Mapping):
        absent.missing("gold_retired", GOLD_RETIRED, "the gold windows' retirements")
    return dict(sorted(counts.items()))


def _family_mechanisms() -> dict[str, tuple[str, str]]:
    """family -> (mechanism, information), from the desk's own family table."""
    try:
        from research import axis_registry as AX
        return {_tok(f): (_tok(m), _tok(i)) for f, (m, i, _s) in AX.FAMILY_TABLE.items()}
    except Exception:                                                        # noqa: BLE001
        return {}


def observe_forest(forest: CV.Tensor, conn: Any, absent: Absent,
                   country_rows: Mapping[str, Mapping[str, Any]], at: str) -> dict[str, int]:
    """The forest tensor from the registry's `sources` table and the packs' declared layers."""
    counts: dict[str, int] = {}
    CL = _country_lab()
    untagged = 0

    def hit(state: str, values: Mapping[str, str], evidence: Mapping[str, Any]) -> None:
        forest.observe(values, state, evidence, at=at)
        counts[state] = counts.get(state, 0) + 1

    # The packs: a declared source is DISCOVERED, a verified one VERIFIED, a declared absence is
    # mapped ground and enters as VERIFIED with its reason (the layer needs no further hunt).
    for code, row in country_rows.items():
        pack = row.get("pack")
        if pack is None or CL is None:
            continue
        try:
            inv = CL.layer_inventory(code, pack=pack)
        except Exception:                                                    # noqa: BLE001
            continue
        langs = [str(x).lower() for x in (row.get("languages") or [])] or [ANY]
        for layer, sources in inv.items():
            if layer not in CV.SOURCE_LAYERS:
                # A pack source line the framework could not tag lands in UNTAGGED. It is COUNTED
                # rather than bucketed: guessing its layer would make the forest's coverage a
                # description of the parser instead of of the country.
                untagged += len([x for x in sources if isinstance(x, Mapping)])
                continue
            for src in sources:
                if not isinstance(src, Mapping):
                    continue
                verified = bool(src.get("verified"))
                absent_reason = str(src.get("absent_reason") or "")
                state = "VERIFIED" if (verified or absent_reason) else "DISCOVERED"
                why = (f"layer declared ABSENT: {absent_reason}" if absent_reason
                       else f"pack source {src.get('id')}"
                            + (" (fetched)" if verified else " (declared, never fetched)"))
                for lang in langs:
                    hit(state, {"country": code, "language": lang, "source_class": layer,
                                "accessibility": "PUBLIC" if not absent_reason else ANY},
                        {"source": f"countries/{code}/pack.py", "why": why})

    # The registry's own `sources` rows: a fetched row is VERIFIED, a registered one DISCOVERED.
    try:
        rows = conn.execute("SELECT source_id, kind, language, country, status, last_crawled, "
                            "licence_note, meta_json FROM sources LIMIT ?",
                            (MAX_REGISTRY_ROWS,)).fetchall()
    except Exception as exc:                                                 # noqa: BLE001
        rows = []
        absent.note("registry.sources", f"unreadable: {type(exc).__name__}: {exc}")
    if not rows:
        absent.note("registry.sources",
                    "the sources table is empty: DISCOVERED/VERIFIED are measured from the "
                    "country packs alone and the discovery rate is zero for every country")
    for r in rows:
        meta = _read_meta(r["meta_json"])
        layer = _tok(meta.get("layer")) if isinstance(meta, Mapping) else ""
        if layer not in CV.SOURCE_LAYERS:
            layer = _layer_of_kind(str(r["kind"] or ""))
        access = str((meta or {}).get("access_label") or "").upper()
        state = "VERIFIED" if str(r["last_crawled"] or "") else "DISCOVERED"
        hit(state, {"country": _tok(r["country"]) or ANY,
                    "language": str(r["language"] or ANY).lower() or ANY,
                    "source_class": layer or ANY,
                    "accessibility": access if access in CV.ACCESS_LABELS else ANY},
            {"source": "registry.sources", "why": f"{r['source_id']} ({r['status']})"})
    if untagged:
        absent.note("pack_sources_untagged",
                    f"{untagged} declared pack source(s) carry no `layer=` tag: their source "
                    "class is UNMEASURED and they hold no forest cell until the pack tags them")
    counts["untagged_pack_sources"] = untagged
    return dict(sorted(counts.items()))


_KIND_LAYER: dict[str, str] = {
    "paper_index": "academic", "working_paper": "academic", "repository": "academic",
    "blog": "practitioner", "forum": "retail_ecology", "app": "app_ecosystem",
    "news": "media", "wire": "media", "archive": "archive", "dataset": "official",
    "official": "official", "exchange": "institutional", "bank": "institutional",
    "region": "official", "shipping": "physical_economy", "port": "physical_economy",
    "code_repository": "academic", "citation": "source_graph",
}


def _layer_of_kind(kind: str) -> str:
    return _KIND_LAYER.get(_tok(kind), "")


def _read_meta(raw: Any) -> Mapping[str, Any]:
    if isinstance(raw, Mapping):
        return raw
    try:
        doc = json.loads(str(raw or "{}"))
    except ValueError:
        return {}
    return doc if isinstance(doc, Mapping) else {}


# ------------------------------------------------------------------------------ country coverage
def country_coverage(country_rows: Mapping[str, Mapping[str, Any]], conn: Any,
                     absent: Absent) -> dict[str, Any]:
    """`coverage.covered` per country, from the packs' layer inventories and the measured
    discovery rate. Both conditions are reported, so a MAPPING verdict says which layers."""
    CL = _country_lab()
    out: dict[str, Any] = {}
    for code, row in country_rows.items():
        inv: dict[str, list[dict[str, Any]]] = {}
        rate: Any = None
        if CL is not None and row.get("pack") is not None:
            try:
                inv = CL.layer_inventory(code, pack=row["pack"])
            except Exception:                                                # noqa: BLE001
                inv = {}
            try:
                rate = CL.discovery_rate(code, conn)
            except Exception as exc:                                         # noqa: BLE001
                rate = {"measured": False, "why": f"{type(exc).__name__}: {exc}"}
        verdict = CV.covered(code, inv, rate)
        verdict["region"] = row.get("region") or UNMEASURED
        out[code] = verdict
    if not out:
        absent.note("country_coverage", "no country pack resolved: every country's coverage is "
                                        "UNMEASURED")
    return out


def by_region(per_country: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for code, row in per_country.items():
        region = str(row.get("region") or UNMEASURED)
        bucket = out.setdefault(region, {"countries": [], "states": {}, "covered": 0})
        bucket["countries"].append(code)
        state = str(row.get("state"))
        bucket["states"][state] = int(bucket["states"].get(state, 0)) + 1
        bucket["covered"] += int(bool(row.get("covered")))
    for bucket in out.values():
        bucket["countries"].sort()
        bucket["n"] = len(bucket["countries"])
    return dict(sorted(out.items()))


# ------------------------------------------------------------------------------------- the holes
def _cursor() -> dict[str, int]:
    doc = _read_json(CURSOR)
    if isinstance(doc, Mapping):
        return {CV.WORLD: int(doc.get(CV.WORLD) or 0), CV.FOREST: int(doc.get(CV.FOREST) or 0)}
    return {CV.WORLD: 0, CV.FOREST: 0}


def _capacity_of(asset_rows: Mapping[str, Mapping[str, Any]],
                 live_by_class: Mapping[str, int]):
    """A capacity PROXY for EVIG, never a cap on anything: a hole in an asset class already
    carrying many funded sleeves buys less incremental breadth than one in an empty class. It
    ranks research only -- no allocator, heat or lot size reads it (LAWS: never reduce
    aggressiveness)."""

    def proxy(values: Mapping[str, str]) -> float | None:
        sym = str(values.get("asset") or "")
        if not sym or sym == ANY:
            return None
        klass = str(asset_rows.get(sym, {}).get("asset_class") or "")
        n = int(live_by_class.get(klass, 0))
        return 1.0 / (1.0 + n)

    return proxy


def rank_holes(tensor: CV.Tensor, subsets: Sequence[tuple[str, ...]], cursor: int, *,
               k: int, budget_end: float, capacity_of: Any = None,
               vocabulary: Mapping[str, Sequence[str]] | None = None) -> dict[str, Any]:
    """Rank the holes on the next axis subset(s) of the rotation, within the budget."""
    used: list[dict[str, Any]] = []
    holes: list[CV.Hole] = []
    i = cursor
    for _ in range(min(SUBSETS_PER_PASS, len(subsets))):
        if time.monotonic() > budget_end and used:
            break
        axes = subsets[i % len(subsets)]
        scorer = tensor.evig_scorer(axes, capacity_of=capacity_of)
        got = tensor.holes(axes, k, scorer, vocabulary=vocabulary, max_enumerate=MAX_ENUMERATE)
        used.append({"axes": list(axes), **tensor.last_scan})
        holes.extend(got)
        i += 1
        if time.monotonic() > budget_end:
            break
    holes.sort(key=lambda h: (-h.score, h.coordinates))
    return {"cursor_next": i % max(len(subsets), 1), "scans": used, "holes": holes}


# ------------------------------------------------------------------------------------- the writes
def _gap_payload(hole: CV.Hole) -> dict[str, Any]:
    state = hole.state
    move = NEXT_MOVE.get(hole.tensor, {}).get(state, "advance this cell one rung")
    ladder = CV.ladder_of(hole.tensor)
    return {"kind": GAP_KIND, "tensor": hole.tensor, "cell": hole.key,
            "axes": list(hole.axes), "values": hole.values(), "state": state,
            "next_state": ladder.next_state(state), "next_move": move,
            "evig": round(float(hole.score), 6), "evig_breakdown": hole.breakdown,
            "law": "LAWS 5f: the coverage tensors are authoritative; this is an explicit research "
                   "frontier row, not a blind spot",
            "rule": RULE}


def write_gaps(holes: Sequence[CV.Hole], conn: Any, *, dry_run: bool, limit: int) -> dict[str, Any]:
    """Each hole becomes a `coverage_gap` discovery (UNPROCESSED) and a `frontier_map` row.

    Idempotent by content hash: `record_discovery` keys on (source_id, mechanism, assets,
    exact_rule) and the exact_rule carries the cell key and the rung asked for, so the same hole
    next hour returns the existing id and creates nothing.
    """
    out = {"discoveries_recorded": 0, "discoveries_seen": 0, "frontier_rows": 0,
           "dry_run": bool(dry_run)}
    rows = list(holes)[:max(int(limit), 0)]
    for hole in rows:
        payload = _gap_payload(hole)
        values = hole.values()
        mech = str(values.get("mechanism") or ANY)
        asset = str(values.get("asset") or values.get("asset_transmission") or ANY)
        rule = f"{hole.tensor}:{hole.key} -> {payload['next_state']}"
        if dry_run:
            out["discoveries_seen"] += 1
            continue
        try:
            _, created = R.record_discovery(
                source_id=f"{SOURCE_TYPE}:{hole.tensor}", source_type=SOURCE_TYPE,
                mechanism=mech, origin=ORIGIN, generator=SOURCE_TYPE, conn=conn,
                information=str(values.get("information_type") or ANY),
                economic_rationale=str(payload["next_move"])[:800],
                assets=[asset] if asset != ANY else [],
                sessions=[values["session"]] if values.get("session") else [],
                regimes=[values["regime"]] if values.get("regime") else [],
                horizons=[values["horizon"]] if values.get("horizon") else [],
                exact_rule_if_known=rule, novelty=float(hole.breakdown.get("novelty") or 1.0),
                confidence=float(hole.breakdown.get("prior_p_edge") or CV.PRIOR),
                falsifier="the cell is tested and the mechanism does not separate forward returns",
                payload=payload)
        except Exception:                                                    # noqa: BLE001
            continue
        out["discoveries_recorded" if created else "discoveries_seen"] += 1
    if not dry_run:
        out["frontier_rows"] = _write_frontier_rows(rows[:MAX_FRONTIER_ROWS], conn)
    return out


def _write_frontier_rows(holes: Sequence[CV.Hole], conn: Any) -> int:
    """UPSERT the holes into `registry.frontier_map`, leaving the Chao1 columns NULL.

    Those columns are `source_frontier`'s unseen-mass estimate and `global_research_os` divides by
    their sum; a 0 written here would read as "this country's ground is exhausted", which this
    organ has not measured.
    """
    n = 0
    stamp = _now()
    for hole in holes:
        values = hole.values()
        cell = f"coverage:{hole.tensor}:{hole.key}"
        try:
            conn.execute(
                "INSERT INTO frontier_map(cell, language, country, source_type, asset_class, "
                "mechanism_class, n_sources, n_leads, n_distinct, n_singletons, n_doubletons, "
                "chao1_unseen, last_scouted, cold, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,NULL,NULL,NULL,NULL,?,?,?) "
                "ON CONFLICT(cell) DO UPDATE SET language=excluded.language, "
                "country=excluded.country, source_type=excluded.source_type, "
                "asset_class=excluded.asset_class, mechanism_class=excluded.mechanism_class, "
                "n_sources=excluded.n_sources, n_leads=excluded.n_leads, cold=excluded.cold, "
                "updated_at=excluded.updated_at",
                (cell, values.get("language") or ANY, values.get("country") or ANY,
                 values.get("source_class") or SOURCE_TYPE,
                 values.get("asset") or values.get("asset_transmission") or ANY,
                 values.get("mechanism") or ANY, 0, 0, stamp, 1, stamp))
            n += 1
        except Exception:                                                    # noqa: BLE001
            continue
    with contextlib.suppress(Exception):
        conn.commit()
    return n


# ---------------------------------------------------------------------------------------- the run
def build(*, budget_s: float = BUDGET_S, dry_run: bool = False, top_k: int = TOP_K,
          conn: Any = None) -> dict[str, Any]:
    """One pass: build both tensors from evidence, rank the holes, hand them over, report."""
    t0 = time.monotonic()
    budget_end = t0 + max(float(budget_s), 1.0)
    at = _now()
    absent = Absent()
    own_conn = conn is None
    try:
        c = conn if conn is not None else R.connect()
    except Exception as exc:                                                 # noqa: BLE001
        c = None
        absent.note("registry", f"the canonical registry is unreachable: {type(exc).__name__}")
    try:
        country_rows = countries(absent)
        asset_rows = assets(absent)
        reps, rep_basis = representations(absent)
        mech = mechanisms(absent, c) if c is not None else []
        regime_vocab = regimes(absent)
        hypothesis_assets = sorted(s for s, r in asset_rows.items()
                                   if r.get("lane") == "hypothesis")
        event_assets = sorted(s for s, r in asset_rows.items() if r.get("lane") == "event")
        unclassified = sorted(s for s, r in asset_rows.items()
                              if r.get("lane") == "unclassified")

        world_vocab: dict[str, Sequence[str]] = {
            "country": sorted(country_rows), "sector": list(CV.SECTORS),
            "information_type": list(CV.INFORMATION_TYPES), "mechanism": mech,
            "representation": reps, "asset": hypothesis_assets, "session": list(CV.SESSIONS),
            "regime": regime_vocab, "horizon": list(CV.HORIZONS),
            "execution": list(CV.EXECUTIONS)}
        forest_vocab: dict[str, Sequence[str]] = {
            "country": sorted(country_rows), "language": languages(country_rows),
            "source_class": list(CV.SOURCE_LAYERS), "sector": list(CV.SECTORS),
            "mechanism": mech, "asset_transmission": hypothesis_assets,
            "freshness": list(CV.FRESHNESS), "accessibility": list(CV.ACCESS_LABELS)}
        world = CV.Tensor(CV.WORLD, vocabulary=world_vocab)
        forest = CV.Tensor(CV.FOREST, vocabulary=forest_vocab)

        world_obs = observe_world(world, c, absent, country_rows, asset_rows, at) if c is not None \
            else {}
        forest_obs = observe_forest(forest, c, absent, country_rows, at) if c is not None else {}
        for cell in CV.example_cells():
            (world if cell.tensor == CV.WORLD else forest).frontier(cell.coordinates, at=at)

        live_by_class: dict[str, int] = {}
        for cell in world.cells():
            if cell.state == "LIVE":
                klass = str(asset_rows.get(cell.value("asset"), {}).get("asset_class") or "")
                live_by_class[klass] = live_by_class.get(klass, 0) + 1
        cap = _capacity_of(asset_rows, live_by_class)

        cursor = _cursor()
        wr = rank_holes(world, WORLD_ROTATION, cursor[CV.WORLD], k=top_k,
                        budget_end=budget_end, capacity_of=cap)
        fr = rank_holes(forest, FOREST_ROTATION, cursor[CV.FOREST], k=top_k,
                        budget_end=budget_end)
        holes = sorted(list(wr["holes"]) + list(fr["holes"]),
                       key=lambda h: (-h.score, h.tensor, h.coordinates))
        handed = (write_gaps(holes, c, dry_run=dry_run, limit=MAX_DISCOVERIES) if c is not None
                  else {"discoveries_recorded": 0, "why": "no registry"})

        per_country = country_coverage(country_rows, c, absent)
        covered_n = sum(1 for v in per_country.values() if v.get("covered"))
        measure = {
            "world_cells": len(world), "forest_cells": len(forest),
            "world_at_or_above_candidates": sum(
                1 for x in world.cells() if world.ladder.at_or_above(x.state, "CANDIDATES")),
            "forest_at_or_above_verified": sum(
                1 for x in forest.cells() if forest.ladder.at_or_above(x.state, "VERIFIED")),
            "countries_covered": covered_n,
            "countries_mapped_or_better": sum(
                1 for v in per_country.values() if v.get("state") in ("COVERED", "STALLED")),
            "source_layers_verified": sum(
                int(layer.get("verified", 0)) for v in per_country.values()
                for layer in (v.get("layers") or {}).values()),
        }
        floors = CV.ratchet(_read_json(FLOORS) or {}, measure)
        doc = {
            "at": at, "elapsed_s": round(time.monotonic() - t0, 2),
            "budget_s": float(budget_s), "dry_run": bool(dry_run),
            "law": "LAWS 5f -- the coverage tensors are authoritative", "rule": RULE,
            "tensors": {
                CV.WORLD: {"axes": list(CV.WORLD_AXES), "ladder": list(CV.WORLD_LADDER),
                           "n_cells": len(world), "histogram": world.histogram(),
                           "observations": world_obs,
                           "vocabulary_sizes": {a: len(v) for a, v in world_vocab.items()}},
                CV.FOREST: {"axes": list(CV.FOREST_AXES), "ladder": list(CV.FOREST_LADDER),
                            "n_cells": len(forest), "histogram": forest.histogram(),
                            "observations": forest_obs,
                            "source_layers": list(CV.SOURCE_LAYERS),
                            "vocabulary_sizes": {a: len(v) for a, v in forest_vocab.items()}},
            },
            "coverage": {"by_country": per_country, "by_region": by_region(per_country),
                         "n_countries": len(per_country), "n_covered": covered_n,
                         "rule": CV.COVERAGE_RULE},
            "frontier": {
                "rotation": {CV.WORLD: [list(a) for a in WORLD_ROTATION],
                             CV.FOREST: [list(a) for a in FOREST_ROTATION]},
                "cursor": cursor,
                "cursor_next": {CV.WORLD: wr["cursor_next"], CV.FOREST: fr["cursor_next"]},
                "scans": {CV.WORLD: wr["scans"], CV.FOREST: fr["scans"]},
                "n_holes": len(holes), "handed_to_the_machine": handed,
                "top": [h.to_json() for h in holes[:top_k]],
                "named_examples": _named_examples(world, forest),
            },
            "floors": floors,
            "lanes": {"hypothesis_assets": len(hypothesis_assets),
                      "event_lane_assets": len(event_assets),
                      "unclassified_assets": unclassified[:20],
                      "why": "single-name equities are the event lane and are never hunted for "
                             "statistical hypotheses (two-lane order 2026-09-06)"},
            "representation_basis": rep_basis,
            "unmeasured": absent.to_json(),
        }
        if not dry_run:
            _write_atomic(OUT, doc)
            _write_atomic(CURSOR, {CV.WORLD: wr["cursor_next"], CV.FOREST: fr["cursor_next"],
                                   "at": at})
            _write_atomic(FLOORS, floors["floors"])
        return doc
    finally:
        if own_conn and c is not None:
            with contextlib.suppress(Exception):
                c.close()


def _named_examples(world: CV.Tensor, forest: CV.Tensor) -> list[dict[str, Any]]:
    """The three frontier rows LAWS 5f names, with the state each is actually in today."""
    out: list[dict[str, Any]] = []
    for row in CV.EXAMPLE_FRONTIER_ROWS:
        tensor = world if row["tensor"] == CV.WORLD else forest
        cell = tensor.get(row["values"])
        state = cell.state if cell is not None else tensor.ladder.floor
        out.append({"label": row["label"], "story": row["story"], "tensor": row["tensor"],
                    "values": dict(row["values"]), "state": state,
                    "next_move": NEXT_MOVE.get(str(row["tensor"]), {}).get(state, "")})
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the authoritative coverage tensors and the frontier "
                                             "engine (LAWS 5f)")
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled shape)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    ap.add_argument("--top", type=int, default=TOP_K)
    a = ap.parse_args(list(argv) if argv is not None else None)
    doc = build(budget_s=a.budget_s, dry_run=a.dry_run, top_k=a.top)
    w, f = doc["tensors"][CV.WORLD], doc["tensors"][CV.FOREST]
    print(f"coverage tensor: world {w['n_cells']} cells {w['histogram']}", flush=True)
    print(f"                 forest {f['n_cells']} cells {f['histogram']}", flush=True)
    cov = doc["coverage"]
    print(f"  countries {cov['n_countries']}, covered {cov['n_covered']}; holes "
          f"{doc['frontier']['n_holes']}, handed {doc['frontier']['handed_to_the_machine']}")
    for hole in doc["frontier"]["top"][:5]:
        print(f"  EVIG {hole['score']:.5f}  {hole['state']:11s} {hole['key'][:96]}")
    if doc["unmeasured"]:
        print(f"  UNMEASURED: {', '.join(sorted(doc['unmeasured']))}")
    if a.dry_run:
        print("  --dry-run: nothing written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
