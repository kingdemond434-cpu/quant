"""CULTURE ORTHOGONALITY -- does a different culture actually produce a different edge?

THE PRINCIPAL'S CLAIM, 2026-09-30, and the test that cashes it:

    "mine across cultures, then test whether the cultural difference produces actual
     return-stream orthogonality. That test is what converts broad mining into compounding
     growth. Without it, broad mining is just a bigger pile."

The desk mines Japanese, Korean, Chinese, Russian, Arabic, Brazilian ... grounds and maps every
claim to an MT5 instrument. The payoff of that breadth is NOT more candidates; it is candidates
whose failure modes differ -- a Korean momentum edge and a US momentum edge that share a factor
but not the other side of the trade. Fifty Japanese variants of one Tokyo-open fade are ONE edge,
and so is a Korean and a US version of the same mechanism if they lose on the same days. Until
this file, nothing measured which of the two the desk holds.

WHAT IT DOES, every hour inside the `occupancy_map` leg (no new leg):

  1. SURVIVORS. Every certified cell (`UNIVERSAL_SURVIVORS.canon.json`), every forward-enrolled
     clock (`reports/shadow/shadow_state.json`, ACTIVE / PROMOTION CANDIDATE) and every LIVE
     sleeve (`data/sleeves.json`), one row per identity, with its mechanism (the family -- on this
     desk the family IS the mechanism; a `discovered` cell takes its docket `mechanism_note`).
  2. CULTURE. Read `source_culture` / `participant_structure` / `failure_mode_hypothesis` where a
     row declares them (`culture_source: "declared"`). Otherwise DERIVE the culture from the
     provenance the docket already carries -- the `asia:<id>` seats against
     `data/asia_sources.json` countries, the source URL's host against the grounds in
     `data/deep_forest_sources.json`, then its country TLD, then the script of the source title
     (`culture_source: "derived"`). No provenance is `"UNMEASURED"`, never a default culture.
  3. PAIRS. Survivors that share a mechanism and differ in culture, measured on their LIVE plus
     FORWARD daily R over the SAME dates (the gateway's `live_ledger.jsonl` and the forward
     ledgers `reports/shadow/ledger_*.json` -- forward phase only; history never informs this):
       rho              Pearson on the common window, zero-filled on no-trade days
       co_loss_lift     P(both lose on a day) / (P(A loses) P(B loses)) -- 1.0 is chance
       dd_jaccard       share of underwater days the two spend underwater TOGETHER
       overlap_days     days in the common window on which either traded
  4. VERDICT per pair. SAME_EDGE when rho >= SAME_EDGE_RHO, or when rho >= TAIL_RHO_FLOOR and
     the losses AND the drawdowns coincide (co_loss_lift >= CO_LOSS_LIFT_SAME and dd_jaccard >=
     DD_JACCARD_SAME): tail dependence the average hides. DIVERGE otherwise. UNMEASURED below
     MIN_OVERLAP_DAYS overlap days or MIN_CO_ACTIVE_DAYS days both traded -- NEVER resolved to
     either side (L1.28a): absence is not independence and it is not redundancy.
  5. PUBLISH reports/CULTURE_ORTHOGONALITY.json: survivors, pairs, verdicts, `merge_groups`
     (union of SAME_EDGE pairs), per-culture effective independent-edge counts, and the survivor
     k_eff counted with every merge group as ONE.

THE THREE CONSUMERS:

  * `research/docket_keff.py` publishes the survivor k_eff with SAME_EDGE groups counted once and
    stamps each docket cell term with the merge group its (family, symbol) belongs to.
  * `research/pf_allocator.py` relabels the sleeves for the MECHANISM CAP and the structured
    correlation: a merge group is ONE family and ONE mechanism (so two names of one edge share
    one cap); a survivor whose every measured cross-culture pair DIVERGES gets its own
    `<family>@<culture>` family (so a proven-orthogonal culture is not capped with the edge it is
    independent of). TWO-SIDED and HEAT-NEUTRAL: it relabels, the resolved heat, the 20% floor
    and the floor fill are untouched, and the optimiser re-spends whatever a cap frees.
  * The CRO pass (docs/cro/CRO_CYCLE.md STEP 4B, duty D9) reads it beside k_eff.

    python desks/mt5/research/culture_orthogonality.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(ROOT), str(BASE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = BASE / "data"
REPORTS = BASE / "reports"
SHADOW = REPORTS / "shadow"
CANON = DATA / "UNIVERSAL_SURVIVORS.canon.json"
SLEEVES = DATA / "sleeves.json"
SHADOW_STATE = SHADOW / "shadow_state.json"
LIVE_LEDGER = DATA / "live_ledger.jsonl"
DOCKET = DATA / "hypotheses" / "external_survivors.json"
ASIA_SOURCES = DATA / "asia_sources.json"
FOREST_SOURCES = DATA / "deep_forest_sources.json"
GATE_LEDGER = DATA / "hypotheses" / "gate_verdict_ledger.jsonl"
REPORT = REPORTS / "CULTURE_ORTHOGONALITY.json"
#: CRO duty D20's counter (`culture_orthogonality_verdicts`), rewritten with REPORT every pass.
VERDICTS_REPORT = REPORTS / "CULTURE_ORTHOGONALITY_VERDICTS.json"
#: The breadth thread's per-culture summary (#139 `research/cell_culture_index.py`): cells and
#: judged cells by `source_culture`. Absent until #139 is on LIVE; then cells/judged read it.
CELL_CULTURE_SUMMARY = REPORTS / "CELL_CULTURE.json"
#: Jurisdictions of the crowded Western canon -- `libs/research/cell_culture.WESTERN` (#139),
#: copied so the counter runs before that module is on LIVE; the import wins when it is.
WESTERN = frozenset({"US", "CA", "GB", "EA", "EU", "DE", "FR", "IT", "ES", "NL", "BE", "AT",
                     "IE", "PT", "FI", "CH", "SE", "NO", "DK", "IS", "LU", "AU", "NZ"})
INDEX_ABSENT = "CELL_CULTURE_INDEX not yet on live (#139)"
#: The breadth thread's per-cell culture index (`libs/research/cell_culture.py`, hourly backfill),
#: keyed by cell id. First existing path wins; absent means every culture is derived here.
CELL_CULTURE_INDEX_PATHS = (DATA / "CELL_CULTURE_INDEX.jsonl",
                            REPORTS / "CELL_CULTURE_INDEX.jsonl",
                            DATA / "hypotheses" / "CELL_CULTURE_INDEX.jsonl",
                            DATA / "intelligence" / "CELL_CULTURE_INDEX.jsonl")
#: The breadth thread's schema (cell_culture.py), read exactly.
PARTICIPANT_STRUCTURES = frozenset({"retail_heavy", "institutional", "tax_driven",
                                    "policy_driven", "physical_flow", "broker_specific",
                                    "settlement_constrained", "mixed"})
CROWDING_PRIORS = ("low", "medium", "high")
#: Judged cells per crowding-prior bucket below which its survival rate is UNMEASURED.
MIN_CROWDING_N = 30

UNMEASURED = "UNMEASURED"
SAME_EDGE = "SAME_EDGE"
DIVERGE = "DIVERGE"

#: Days in the common window (either sleeve traded) below which a pair is UNMEASURED. Thirty
#: daily observations put the standard error of a zero correlation near 0.18 -- enough to tell a
#: 0.6 from a 0.0, which is the only distinction a verdict draws.
MIN_OVERLAP_DAYS = 30
#: Days on which BOTH traded. Two sleeves that never trade on the same day cannot have a
#: coincident loss measured at all, whatever the window says.
MIN_CO_ACTIVE_DAYS = 5
#: Linear dependence at which two names are one edge.
SAME_EDGE_RHO = 0.4
#: Below this Pearson no tail evidence merges a pair -- a coincidence rate on a handful of losing
#: days can lift by chance, and a merge is a claim.
TAIL_RHO_FLOOR = 0.2
#: Losing-day coincidence lift and shared-underwater share that, together, mark tail dependence.
CO_LOSS_LIFT_SAME = 1.75
DD_JACCARD_SAME = 0.5
#: The artifact the consumers read must be this fresh; older reads as UNMEASURED (no relabel).
MAX_AGE_H = 6.0
#: Pairs published in full; the counts cover all of them.
MAX_PAIRS_PUBLISHED = 5000

#: Shadow keys whose second token is a session window, not a family (the gold book's clocks).
_SESSIONS = frozenset({"asia", "london", "london_am", "london_pm", "afternoon", "new_york", "ny",
                       "overlap", "continuous", "all", "tokyo", "sydney", "europe"})
#: Two-letter TLDs that are generic in practice and name no jurisdiction.
_GENERIC_TLDS = frozenset({"io", "ai", "co", "me", "tv", "cc", "ly", "to", "fm", "gg", "so",
                           "xyz", "app", "dev", "eu", "ws", "fx"})
#: Seat / source-directory tokens that name a jurisdiction by themselves.
_SEAT_TOKENS = {"jp": "JP", "japan": "JP", "japanese": "JP", "minfx": "JP", "kr": "KR",
                "korea": "KR", "korean": "KR", "cn": "CN", "china": "CN", "chinese": "CN",
                "ru": "RU", "russia": "RU", "russian": "RU", "smartlab": "RU", "br": "BR",
                "brazil": "BR", "arab": "ARABIC", "arabic": "ARABIC", "tw": "TW", "taiwan": "TW",
                "hk": "HK", "india": "IN", "turkey": "TR", "vietnam": "VN", "indonesia": "ID"}
#: Countries whose sources publish in Arabic are one language culture for this test.
_ARABIC = frozenset({"AE", "SA", "QA", "EG", "KW", "BH", "OM", "JO", "MA", "DZ", "TN", "LB"})
#: asia_sources "country" values that are not jurisdictions.
_NOT_A_COUNTRY = frozenset({"INSTITUTIONAL", "GLOBAL", "", "NONE", "MULTI"})


# ------------------------------------------------------------------------------ small readers
def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        return []
    return out


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def norm(name: Any) -> str:
    """One spelling for every name a sleeve travels under (ledger file, comment, registry)."""
    return re.sub(r"[^a-z0-9]+", "_", str(name or "").lower()).strip("_")


def _day(v: Any) -> str | None:
    s = str(v or "").strip()
    return s[:10] if re.match(r"\d{4}-\d{2}-\d{2}", s) else None


def _country(code: Any) -> str | None:
    c = str(code or "").strip().upper()
    if c in _NOT_A_COUNTRY:
        return None
    if c == "UK":
        c = "GB"
    return "ARABIC" if c in _ARABIC else c


# ------------------------------------------------------------------------------ culture index
def culture_index(asia: Any = None, forest: Any = None) -> dict[str, dict[str, str]]:
    """{"seat": {asia source id: culture}, "host": {hostname: culture}} from the two registries."""
    asia = _read(ASIA_SOURCES) if asia is None else asia
    forest = _read(FOREST_SOURCES) if forest is None else forest
    seat: dict[str, str] = {}
    host: dict[str, str] = {}
    for src in (asia.get("sources") or []) if isinstance(asia, dict) else []:
        if not isinstance(src, dict):
            continue
        c = _country(src.get("country"))
        if not c:
            continue
        if src.get("id"):
            seat[str(src["id"]).lower()] = c
        h = urlparse(str(src.get("url") or "")).netloc.lower()
        if h:
            host.setdefault(h, c)
    for g in (forest.get("grounds") or []) if isinstance(forest, dict) else []:
        if not isinstance(g, dict):
            continue
        c = _country(g.get("region"))
        if not c:
            continue
        for u in [g.get("url"), *(g.get("alt") or [])]:
            h = urlparse(str(u or "")).netloc.lower()
            if h:
                host.setdefault(h, c)
    return {"seat": seat, "host": host}


def _tld_culture(hostname: str) -> str | None:
    labels = [p for p in hostname.lower().split(".") if p]
    if len(labels) < 2:
        return None
    tld = labels[-1]
    if len(tld) != 2 or tld in _GENERIC_TLDS:
        return None
    return _country(tld)


def _script_culture(text: str) -> str | None:
    """The culture a title's SCRIPT names. Kana before Han (Japanese uses both)."""
    if re.search(r"[぀-ヿ]", text):
        return "JP"
    if re.search(r"[가-힯]", text):
        return "KR"
    if re.search(r"[一-鿿]", text):
        return "CN"
    if re.search(r"[Ѐ-ӿ]", text):
        return "RU"
    if re.search(r"[؀-ۿ]", text):
        return "ARABIC"
    if re.search(r"[฀-๿]", text):
        return "TH"
    return None


def row_culture(row: Mapping[str, Any], idx: Mapping[str, Mapping[str, str]]
                ) -> tuple[str | None, str, str]:
    """(culture, culture_source, how) for one provenance-bearing row.

    Precedence: a DECLARED `source_culture` (the breadth thread's field), then the seat registry,
    then the URL host's registered ground, then its country TLD, then the title's script.
    """
    declared = _culture_code(row.get("source_culture"))
    if declared:
        return declared, "declared", "source_culture"
    seats = [str(s) for s in (row.get("contributing_sources") or []) if s]
    src = str(row.get("source") or "")
    if src.startswith("miner:"):
        seats.append(src[len("miner:"):])
    for s in seats:
        if s.startswith("asia:"):
            c = idx.get("seat", {}).get(s[len("asia:"):].lower())
            if c:
                return c, "derived", f"seat {s} -> data/asia_sources.json country"
    for s in seats:
        for tok in re.split(r"[^a-z]+", s.lower()):
            if tok in _SEAT_TOKENS:
                return _SEAT_TOKENS[tok], "derived", f"seat {s} names {tok}"
    for u in (row.get("source_url"), row.get("url")):
        h = urlparse(str(u or "")).netloc.lower()
        if not h:
            continue
        c = idx.get("host", {}).get(h)
        if c:
            return c, "derived", f"host {h} -> registered ground"
        c = _tld_culture(h)
        if c:
            return c, "derived", f"host {h} country TLD"
    c = _script_culture(str(row.get("source_title") or row.get("claim") or ""))
    if c:
        return c, "derived", "source title script"
    return None, UNMEASURED, "no provenance names a culture"


# ------------------------------------------------------------------------------ survivors
def _cell_id(row: Mapping[str, Any]) -> str | None:
    try:
        from research.frontier_identity import cell_id
    except Exception:                                                # pragma: no cover
        return None
    sym, fam = row.get("symbol") or row.get("sym"), row.get("family")
    if not sym or not fam:
        return None
    try:
        return cell_id({"sym": str(sym), "family": str(fam),
                        "params": dict(row.get("params") or {}),
                        "timeframe": row.get("timeframe")})
    except Exception:
        return None


def _strip_hunt(cell_key: str) -> str:
    """`external.EURCHF.discovered.p=...` -> `EURCHF.discovered.p=...` (the cell id)."""
    parts = str(cell_key).split(".", 1)
    if len(parts) == 2 and parts[0] and not parts[0].isupper():
        return parts[1]
    return str(cell_key)


def _blank(sid: str, symbol: str, family: str, selector: str) -> dict[str, Any]:
    return {"id": sid, "symbol": symbol.upper(), "family": family, "selector": selector,
            "stages": [], "names": [], "cert_cell": None, "mechanism": family,
            "declared": {}}


def _declared(row: Mapping[str, Any]) -> dict[str, Any]:
    return {k: row[k] for k in ("source_culture", "participant_structure",
                                "failure_mode_hypothesis", "mechanism")
            if row.get(k) not in (None, "")}


def build_survivors(canon: Any, sleeves: Any, shadow: Any) -> dict[str, dict[str, Any]]:
    """One row per identity across the certified, forward-enrolled and LIVE sets."""
    out: dict[str, dict[str, Any]] = {}
    by_cell: dict[str, str] = {}
    certs = canon.get("survivors") if isinstance(canon, dict) else None
    for key, rec in (certs or {}).items() if isinstance(certs, dict) else []:
        if not isinstance(rec, dict):
            continue
        raw = rec.get("shadow_spec")
        spec: dict[str, Any] = raw if isinstance(raw, dict) else {}
        sym = str(spec.get("symbol") or rec.get("sym") or "")
        fam = str(spec.get("family") or rec.get("family") or "")
        if not sym or not fam:
            continue
        sid = f"cert:{key}"
        s = _blank(sid, sym, fam, str(spec.get("selector") or ""))
        s["stages"].append("certified")
        s["cert_cell"] = _strip_hunt(str(rec.get("cell") or key))
        s["params"] = dict(spec.get("params") or {})
        s["names"] += [str(key), str(rec.get("cell") or ""),
                       f"{sym}_{fam}_{s['selector']}".strip("_")]
        s["declared"].update(_declared(rec))
        s["declared"].update(_declared(spec))
        out[sid] = s
        by_cell[norm(key)] = sid
        by_cell[norm(s["cert_cell"])] = sid
    rows = sleeves.get("sleeves") if isinstance(sleeves, dict) else sleeves
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict) or str(r.get("status") or "").upper() != "LIVE":
            continue
        rawc = r.get("certificate")
        cert: dict[str, Any] = rawc if isinstance(rawc, dict) else {}
        lsid = by_cell.get(norm(cert.get("cell"))) if cert.get("cell") else None
        if lsid is None:
            sym = str(r.get("symbol") or "")
            fam = str(r.get("family") or ("session_window" if r.get("window") else ""))
            if not sym:
                continue
            lsid = f"live:{r.get('name')}"
            out[lsid] = _blank(lsid, sym, fam or "unknown",
                              str(r.get("selector") or r.get("window") or r.get("session") or ""))
            if cert.get("cell"):
                out[lsid]["cert_cell"] = _strip_hunt(str(cert["cell"]))
        s = out[lsid]
        s["stages"].append("live")
        s["names"].append(str(r.get("name") or ""))
        s["declared"].update(_declared(r))
    for key, st in (shadow or {}).items() if isinstance(shadow, dict) else []:
        if not isinstance(st, dict):
            continue
        status = str(st.get("status") or "").upper()
        if status not in ("ACTIVE", "PROMOTION CANDIDATE", "PROMOTION_CANDIDATE"):
            continue
        head = str(key).split("#", 1)[0]
        parts = head.split(".")
        sym = parts[0]
        if len(parts) >= 3:
            fam, sel = parts[1], parts[2]
        elif len(parts) == 2 and parts[1].lower() not in _SESSIONS:
            fam, sel = parts[1], ""
        else:
            fam, sel = "session_window", parts[1] if len(parts) > 1 else ""
        sid = by_cell.get(norm(key)) or f"fwd:{key}"
        if sid not in out:
            out[sid] = _blank(sid, sym, fam, sel)
        s = out[sid]
        s["stages"].append("forward")
        s["names"] += [str(key), str(st.get("sleeve_id") or "")]
        s["declared"].update(_declared(st))
    for s in out.values():
        s["stages"] = sorted(set(s["stages"]))
        s["names"] = sorted({n for n in s["names"] if n})
    return out


def _culture_code(v: Any) -> str | None:
    """`"KR/ko"` -> `"KR"`; `"UNMEASURED"`, empty and non-strings -> None."""
    if not isinstance(v, str):
        return None
    head = v.strip().split("/", 1)[0].strip().upper()
    return None if not head or head == UNMEASURED else _country(head) or head


def load_culture_index(path: Path | None = None) -> tuple[dict[str, dict[str, Any]], str]:
    """({cell id: row}, where) from the breadth thread's CELL_CULTURE_INDEX.jsonl."""
    for p in ([path] if path else list(CELL_CULTURE_INDEX_PATHS)):
        if p is None or not p.exists():
            continue
        out: dict[str, dict[str, Any]] = {}
        for row in _read_jsonl(p):
            key = row.get("cell_id") or row.get("cell") or row.get("key") or row.get("id")
            if key:
                out[_strip_hunt(str(key))] = row
        return out, f"{p.relative_to(BASE) if p.is_relative_to(BASE) else p}: {len(out)} cells"
    return {}, "CELL_CULTURE_INDEX.jsonl absent on this host -- culture derived from provenance"


def _fields_from(row: Mapping[str, Any], into: dict[str, Any]) -> None:
    for k in ("participant_structure", "failure_mode_hypothesis", "crowding_prior"):
        v = row.get(k)
        if v not in (None, "", UNMEASURED) and k not in into:
            if k == "participant_structure" and str(v) not in PARTICIPANT_STRUCTURES:
                continue
            if k == "crowding_prior" and str(v).lower() not in CROWDING_PRIORS:
                continue
            into[k] = str(v).lower() if k == "crowding_prior" else v


def attach_culture(survivors: dict[str, dict[str, Any]], docket: Iterable[Mapping[str, Any]],
                   idx: Mapping[str, Mapping[str, str]],
                   cell_index: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, int]:
    """Stamp culture, its source, the participant structure, the failure-mode hypothesis and the
    crowding prior on every survivor.

    Order: a field declared on the survivor's own row; the breadth thread's CELL_CULTURE_INDEX
    entry for its cell id; then DERIVED from the docket row(s) it came from -- the exact cell-id
    join first, then the (symbol, family) rows, used ONLY when every one of them that names a
    culture names the same one (a pooled guess across cultures is not a derivation).
    """
    cell_index = cell_index or {}
    want_cells = {s["cert_cell"] for s in survivors.values() if s.get("cert_cell")}
    want_pairs = {(s["symbol"], s["family"]) for s in survivors.values()}
    by_cell: dict[str, list[Mapping[str, Any]]] = {}
    by_pair: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in docket:
        if not isinstance(row, Mapping):
            continue
        pair = (str(row.get("symbol") or row.get("sym") or "").upper(),
                str(row.get("family") or ""))
        if pair not in want_pairs:
            continue
        by_pair.setdefault(pair, []).append(row)
        cid = _cell_id(row)
        if cid and cid in want_cells:
            by_cell.setdefault(cid, []).append(row)
    counts = {"declared": 0, "derived": 0, UNMEASURED: 0}
    for s in survivors.values():
        dec: dict[str, Any] = s.pop("declared", {})
        fields: dict[str, Any] = {}
        _fields_from(dec, fields)
        culture = _culture_code(dec.get("source_culture"))
        source, how = ("declared", "source_culture on the survivor's row") if culture \
            else (UNMEASURED, "no provenance names a culture")
        entry = cell_index.get(s.get("cert_cell") or "")
        if entry:
            _fields_from(entry, fields)
            ic = _culture_code(entry.get("source_culture"))
            if culture is None and ic:
                culture, source, how = ic, "declared", "CELL_CULTURE_INDEX source_culture"
        cultures: set[str] = {culture} if culture else set()
        mech_note: str | None = None
        exact = by_cell.get(s.get("cert_cell") or "") or []
        pooled = by_pair.get((s["symbol"], s["family"])) or []
        for rows, grade in ((exact, "exact cell"), (pooled, "symbol+family")):
            found: dict[str, list[str]] = {}
            for row in rows:
                c, src, h = row_culture(row, idx)
                if c:
                    found.setdefault(c, []).append(f"{src}: {h}")
                if mech_note is None and row.get("mechanism_note"):
                    mech_note = str(row["mechanism_note"])
                if grade == "exact cell":
                    _fields_from(row, fields)
            cultures |= set(found)
            if culture is not None or not found:
                continue
            if len(found) == 1 or grade == "exact cell":
                # An exact join naming several cultures takes the one most of its rows name.
                best = max(sorted(found), key=lambda c, f=found: len(f[c]))  # type: ignore[misc]
                culture = best
                source = "declared" if found[best][0].startswith("declared") else "derived"
                how = f"{grade}: {found[best][0]}"
            else:
                how = (f"symbol+family rows name {len(found)} cultures "
                       f"({', '.join(sorted(found))}) -- ambiguous, not derived")
        if s["family"] == "discovered" and mech_note:
            s["mechanism"] = f"discovered:{mech_note}"
        if dec.get("mechanism"):
            s["mechanism"] = str(dec["mechanism"])
        s["culture"] = culture or UNMEASURED
        s["culture_source"] = source
        s["culture_how"] = how
        s["cultures_seen"] = sorted(cultures)
        s["participant_structure"] = fields.get("participant_structure", UNMEASURED)
        s["failure_mode_hypothesis"] = fields.get("failure_mode_hypothesis")
        s["crowding_prior"] = fields.get("crowding_prior", UNMEASURED)
        counts[source if source in counts else UNMEASURED] += 1
    return counts


# ------------------------------------------------------------------------------ crowding prior
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials."""
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, mid - half), min(1.0, mid + half)


def crowding_survival(cell_index: Mapping[str, Mapping[str, Any]], judged: set[str] | None,
                      certified: set[str], *, min_n: int = MIN_CROWDING_N) -> dict[str, Any]:
    """Do cells with a LOW crowding prior survive the gauntlet at a higher rate than HIGH ones?

    Population: indexed cells with a crowding prior that were JUDGED (a real verdict in the gate
    ledger, or a certificate). Survival: a certificate. An unjudged cell is neither a survivor
    nor a failure, so without the judged set the test is UNMEASURED, not a rate over the backlog.
    """
    if not cell_index:
        return {"status": UNMEASURED, "why": "no CELL_CULTURE_INDEX on this host"}
    if judged is None:
        return {"status": UNMEASURED,
                "why": "gate_verdict_ledger.jsonl absent: the judged population is unknown"}
    buckets: dict[str, dict[str, Any]] = {}
    for cid, row in cell_index.items():
        cp = str(row.get("crowding_prior") or "").lower()
        if cp not in CROWDING_PRIORS:
            continue
        if cid not in judged and cid not in certified:
            continue
        b = buckets.setdefault(cp, {"n": 0, "survived": 0})
        b["n"] += 1
        b["survived"] += 1 if cid in certified else 0
    for b in buckets.values():
        lo, hi = wilson(b["survived"], b["n"])
        b["rate"] = round(b["survived"] / b["n"], 5) if b["n"] else None
        b["wilson_95"] = [round(lo, 5), round(hi, 5)]
        b["status"] = "MEASURED" if b["n"] >= min_n else UNMEASURED
    low, high = buckets.get("low"), buckets.get("high")
    if not low or not high or low["status"] != "MEASURED" or high["status"] != "MEASURED":
        verdict, why = UNMEASURED, (f"low n={low['n'] if low else 0}, high "
                                    f"n={high['n'] if high else 0}; each needs >= {min_n}")
    elif low["wilson_95"][0] > high["wilson_95"][1]:
        verdict, why = "LOW_SURVIVES_MORE", "low's Wilson lower bound clears high's upper bound"
    elif low["wilson_95"][1] < high["wilson_95"][0]:
        verdict, why = "HIGH_SURVIVES_MORE", "high's Wilson lower bound clears low's upper bound"
    else:
        verdict, why = "NO_DIFFERENCE_RESOLVED", "the two Wilson intervals overlap"
    return {"status": "MEASURED" if verdict != UNMEASURED else UNMEASURED, "verdict": verdict,
            "why": why, "min_n": min_n, "by_crowding_prior": dict(sorted(buckets.items()))}


def judged_cells(path: Path | None = None) -> set[str] | None:
    """Cell ids with a real gate verdict (the filter occupancy_map/judge_coverage apply)."""
    p = path or GATE_LEDGER
    if not p.exists():
        return None
    out: set[str] = set()
    for row in _read_jsonl(p):
        if str(row.get("downstream_status") or "").startswith("NOT_RUN"):
            continue
        if row.get("passed") in (None, "None") and not row.get("terminal_gate"):
            continue
        if row.get("cell"):
            out.add(_strip_hunt(str(row["cell"])))
    return out


# ------------------------------------------------------------------------------ return series
def load_series(shadow_dir: Path | None = None, live_ledger: Path | None = None
                ) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    """(forward {name: {day: R}}, live {name: {day: R}}) -- FORWARD PHASE and REAL FILLS only."""
    fwd: dict[str, dict[str, float]] = {}
    for path in sorted((shadow_dir or SHADOW).glob("ledger_*.json")):
        rows = _read(path)
        if not isinstance(rows, list):
            continue
        by: dict[str, float] = {}
        for r in rows:
            if not isinstance(r, dict) or str(r.get("phase") or "") != "forward":
                continue
            d = _day(r.get("closed_at") or r.get("exit_time") or r.get("entry_time")
                     or r.get("opened_at") or r.get("time"))
            v = _num(r.get("r_multiple") if "r_multiple" in r else r.get("r"))
            if d and v is not None:
                by[d] = by.get(d, 0.0) + v
        if by:
            fwd[norm(path.stem[len("ledger_"):])] = by
    live: dict[str, dict[str, float]] = {}
    for r in _read_jsonl(live_ledger or LIVE_LEDGER):
        name = str(r.get("sleeve") or "")
        if not name or name.startswith("["):
            continue                       # a bracket comment is the broker's, not a sleeve's
        d = _day(r.get("close_time") or r.get("time"))
        v = _num(r.get("r_multiple"))
        if not v:
            pl, risk = _num(r.get("pl_quote")), _num(r.get("risk_quote"))
            v = pl / abs(risk) if pl is not None and risk else v
        if d and v is not None:
            by2 = live.setdefault(norm(name), {})
            by2[d] = by2.get(d, 0.0) + v
    return fwd, live


def survivor_series(s: Mapping[str, Any], fwd: Mapping[str, Mapping[str, float]],
                    live: Mapping[str, Mapping[str, float]]) -> tuple[dict[str, float], str]:
    """A survivor's daily R: live fills where it has them, its forward clock on other days.

    The live ledger's sleeve comment is TRUNCATED by the terminal (27 characters), so a live name
    matches when it is a prefix of one of the survivor's names and at least 10 characters long.
    """
    names = [norm(n) for n in s.get("names") or [] if n]
    f: dict[str, float] = {}
    for n in names:
        if n in fwd:
            f = dict(fwd[n])
            break
    lv: dict[str, float] = {}
    for ln, series in live.items():
        if len(ln) >= 10 and any(n == ln or n.startswith(ln) for n in names):
            for d, v in series.items():
                lv[d] = lv.get(d, 0.0) + v
    if not f and not lv:
        return {}, "none"
    merged = {**f, **lv}
    return merged, "+".join(x for x, y in (("forward", f), ("live", lv)) if y)


# ------------------------------------------------------------------------------ the pair test
def measure_pair(a: Mapping[str, float], b: Mapping[str, float], *,
                 min_overlap: int = MIN_OVERLAP_DAYS,
                 min_co_active: int = MIN_CO_ACTIVE_DAYS) -> dict[str, Any]:
    """Dependence of two daily-R series over their COMMON window, and a verdict."""
    if not a or not b:
        return {"verdict": UNMEASURED, "overlap_days": 0, "co_active_days": 0,
                "why": "one side has no live or forward returns"}
    lo = max(min(a), min(b))
    hi = min(max(a), max(b))
    days = sorted(d for d in set(a) | set(b) if lo <= d <= hi)
    co = sum(1 for d in days if d in a and d in b)
    base = {"overlap_days": len(days), "co_active_days": co, "window": [lo, hi] if days else None}
    if len(days) < min_overlap or co < min_co_active:
        return {"verdict": UNMEASURED, **base,
                "why": (f"{len(days)} overlap day(s) (need {min_overlap}) and {co} co-active "
                        f"day(s) (need {min_co_active}) -- not resolved to either side")}
    x = [float(a.get(d, 0.0)) for d in days]
    y = [float(b.get(d, 0.0)) for d in days]
    n = len(days)
    mx, my = sum(x) / n, sum(y) / n
    vx = sum((v - mx) ** 2 for v in x)
    vy = sum((v - my) ** 2 for v in y)
    if vx <= 0 or vy <= 0:
        return {"verdict": UNMEASURED, **base, "why": "a constant series has no correlation"}
    rho = sum((p - mx) * (q - my) for p, q in zip(x, y, strict=True)) / math.sqrt(vx * vy)
    la = [v < 0 for v in x]
    lb = [v < 0 for v in y]
    pa, pb = sum(la) / n, sum(lb) / n
    both = sum(1 for p, q in zip(la, lb, strict=True) if p and q) / n
    lift = both / (pa * pb) if pa > 0 and pb > 0 else None

    def underwater(r: list[float]) -> list[bool]:
        eq = peak = 0.0
        out = []
        for v in r:
            eq += v
            peak = max(peak, eq)
            out.append(eq < peak - 1e-12)
        return out

    ua, ub = underwater(x), underwater(y)
    union = sum(1 for p, q in zip(ua, ub, strict=True) if p or q)
    inter = sum(1 for p, q in zip(ua, ub, strict=True) if p and q)
    jac = inter / union if union else None
    tail = (rho >= TAIL_RHO_FLOOR and lift is not None and lift >= CO_LOSS_LIFT_SAME
            and jac is not None and jac >= DD_JACCARD_SAME)
    if rho >= SAME_EDGE_RHO:
        verdict, why = SAME_EDGE, f"rho {rho:.2f} >= {SAME_EDGE_RHO}"
    elif tail:
        verdict, why = SAME_EDGE, (f"tail: rho {rho:.2f}, losses coincide {lift:.2f}x chance and "
                                   f"{jac:.0%} of underwater days are shared")
    else:
        verdict, why = DIVERGE, (f"rho {rho:.2f} < {SAME_EDGE_RHO} and no coincident-loss tail "
                                 f"(lift {None if lift is None else round(lift, 2)}, "
                                 f"dd share {None if jac is None else round(jac, 2)})")
    return {"verdict": verdict, **base, "rho": round(rho, 4),
            "co_loss_lift": None if lift is None else round(lift, 3),
            "dd_jaccard": None if jac is None else round(jac, 3),
            "loss_days": [int(sum(la)), int(sum(lb))], "why": why}


def merge_groups(pairs: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Connected components of the SAME_EDGE graph -- each is ONE edge under several names."""
    parent: dict[str, str] = {}

    def find(k: str) -> str:
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for p in pairs:
        if p.get("verdict") == SAME_EDGE:
            ra, rb = find(str(p["a"])), find(str(p["b"]))
            if ra != rb:
                parent[ra] = rb
    comps: dict[str, list[str]] = {}
    for k in parent:
        comps.setdefault(find(k), []).append(k)
    out = []
    for members in comps.values():
        if len(members) < 2:
            continue
        members.sort()
        gid = "cm_" + hashlib.sha1("|".join(members).encode()).hexdigest()[:10]
        out.append({"group_id": gid, "members": members})
    out.sort(key=lambda g: (-len(g["members"]), g["group_id"]))
    return out


def keff_merged(ids: Iterable[str], groups: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Survivor count with every merge group counted as ONE."""
    ids = set(ids)
    collapsed = 0
    for g in groups:
        inside = [m for m in g.get("members") or [] if m in ids]
        collapsed += max(0, len(inside) - 1)
    return {"nominal": len(ids), "merged": len(ids) - collapsed, "collapsed": collapsed}


def build(*, canon: Any = None, sleeves: Any = None, shadow: Any = None,
          docket: Iterable[Mapping[str, Any]] | None = None,
          fwd: Mapping[str, Mapping[str, float]] | None = None,
          live: Mapping[str, Mapping[str, float]] | None = None,
          idx: Mapping[str, Mapping[str, str]] | None = None,
          cell_index: Mapping[str, Mapping[str, Any]] | None = None,
          judged: set[str] | None = None,
          now: datetime | None = None) -> dict[str, Any]:
    at = now or datetime.now(tz=UTC)
    inputs: dict[str, str] = {}
    if canon is None:
        canon = _read(CANON)
        inputs["canon"] = "READ" if canon else "ABSENT"
    if sleeves is None:
        sleeves = _read(SLEEVES)
        inputs["sleeves"] = "READ" if sleeves else "ABSENT"
    if shadow is None:
        shadow = _read(SHADOW_STATE)
        inputs["shadow_state"] = "READ" if shadow else "ABSENT"
    if docket is None:
        raw = _read(DOCKET)
        docket = raw if isinstance(raw, list) else []
        inputs["docket"] = f"{len(docket)} rows" if docket else "ABSENT"
    if fwd is None or live is None:
        f2, l2 = load_series()
        fwd = f2 if fwd is None else fwd
        live = l2 if live is None else live
    idx = culture_index() if idx is None else idx
    if cell_index is None:
        cell_index, inputs["cell_culture_index"] = load_culture_index()
    if judged is None and cell_index:
        judged = judged_cells()
        inputs["gate_verdict_ledger"] = ("ABSENT" if judged is None
                                         else f"{len(judged)} judged cells")

    surv = build_survivors(canon, sleeves, shadow)
    grades = attach_culture(surv, docket, idx, cell_index)
    certified = {str(s["cert_cell"]) for s in surv.values()
                 if s.get("cert_cell") and "certified" in s["stages"]}
    crowding = crowding_survival(cell_index, judged, certified)
    series: dict[str, dict[str, float]] = {}
    for sid, s in surv.items():
        ser, src = survivor_series(s, fwd, live)
        s["returns"] = {"source": src, "days": len(ser),
                        "first": min(ser) if ser else None, "last": max(ser) if ser else None}
        if ser:
            series[sid] = ser

    by_mech: dict[str, list[str]] = {}
    for sid, s in surv.items():
        by_mech.setdefault(str(s["mechanism"]), []).append(sid)
    pairs: list[dict[str, Any]] = []
    for mech, ids in sorted(by_mech.items()):
        ids.sort()
        for i, a in enumerate(ids):
            ca = surv[a]["culture"]
            if ca == UNMEASURED:
                continue
            for b in ids[i + 1:]:
                cb = surv[b]["culture"]
                if cb in (UNMEASURED, ca):
                    continue
                m = measure_pair(series.get(a, {}), series.get(b, {}))
                pairs.append({"a": a, "b": b, "mechanism": mech, "cultures": [ca, cb], **m})
    groups = merge_groups(pairs)
    member_of = {m: g["group_id"] for g in groups for m in g["members"]}
    for g in groups:
        g["mechanisms"] = sorted({str(surv[m]["mechanism"]) for m in g["members"]})
        g["cultures"] = sorted({str(surv[m]["culture"]) for m in g["members"]})
        g["keys"] = sorted({f"{surv[m]['family']}|{surv[m]['symbol']}" for m in g["members"]})

    verdicts: dict[str, dict[str, int]] = {}
    for p in pairs:
        for sid in (p["a"], p["b"]):
            v = verdicts.setdefault(sid, {DIVERGE: 0, SAME_EDGE: 0, UNMEASURED: 0})
            v[p["verdict"]] += 1
    for sid, s in surv.items():
        v = verdicts.get(sid, {DIVERGE: 0, SAME_EDGE: 0, UNMEASURED: 0})
        s["pair_verdicts"] = v
        if sid in member_of:
            s["merge_group"] = member_of[sid]
            s["label"] = {"family": f"culture_merge:{member_of[sid]}",
                          "mechanism": f"culture_merge:{member_of[sid]}", "why": SAME_EDGE}
        elif v[DIVERGE] and not v[SAME_EDGE] and s["culture"] != UNMEASURED:
            s["label"] = {"family": f"{s['family']}@{s['culture']}",
                          "mechanism": f"{s['mechanism']} @{s['culture']}", "why": DIVERGE}

    per_culture: dict[str, dict[str, Any]] = {}
    for sid, s in surv.items():
        c = str(s["culture"])
        pc = per_culture.setdefault(c, {"survivors": 0, "with_returns": 0, "mechanisms": set(),
                                        "diverge": set(), "same": set(), "stages": {}})
        pc["survivors"] += 1
        pc["with_returns"] += 1 if sid in series else 0
        pc["mechanisms"].add(s["mechanism"])
        for st in s["stages"]:
            pc["stages"][st] = pc["stages"].get(st, 0) + 1
        v = s["pair_verdicts"]
        if v[SAME_EDGE]:
            pc["same"].add(s["mechanism"])
        elif v[DIVERGE]:
            pc["diverge"].add(s["mechanism"])
    cultures_pub: dict[str, Any] = {}
    for c, pc in sorted(per_culture.items()):
        mech = pc["mechanisms"]
        proven = pc["diverge"] - pc["same"]
        cultures_pub[c] = {
            "survivors": pc["survivors"], "with_returns": pc["with_returns"],
            "stages": dict(sorted(pc["stages"].items())),
            # "50 Japanese variants of one Tokyo-open fade are one edge": within a culture the
            # claim is one edge per MECHANISM until a within-culture measurement says otherwise.
            "independent_edges_claimed": len(mech),
            "independent_edges_proven": len(proven),
            "edges_shared_with_another_culture": len(pc["same"]),
            "edges_unmeasured": len(mech - proven - pc["same"]),
            "proven_mechanisms": sorted(proven)[:50],
        }
    counts = {DIVERGE: 0, SAME_EDGE: 0, UNMEASURED: 0}
    for p in pairs:
        counts[p["verdict"]] += 1
    k = keff_merged(surv.keys(), groups)
    status = ("MEASURED" if counts[DIVERGE] or counts[SAME_EDGE] else UNMEASURED)
    why = (f"{len(pairs)} cross-culture same-mechanism pair(s): {counts[DIVERGE]} DIVERGE, "
           f"{counts[SAME_EDGE]} SAME_EDGE, {counts[UNMEASURED]} UNMEASURED; "
           f"{grades[UNMEASURED]} of {len(surv)} survivor(s) carry no culture")
    return {
        "at": at.isoformat(timespec="seconds"),
        "status": status, "why": why,
        "rule": (f"pairs share a mechanism and differ in culture; live+forward daily R on the "
                 f"common window; SAME_EDGE if rho >= {SAME_EDGE_RHO}, or rho >= "
                 f"{TAIL_RHO_FLOOR} with co_loss_lift >= {CO_LOSS_LIFT_SAME} and dd_jaccard >= "
                 f"{DD_JACCARD_SAME}; DIVERGE otherwise; UNMEASURED below {MIN_OVERLAP_DAYS} "
                 f"overlap days or {MIN_CO_ACTIVE_DAYS} co-active days, never resolved"),
        "thresholds": {"min_overlap_days": MIN_OVERLAP_DAYS,
                       "min_co_active_days": MIN_CO_ACTIVE_DAYS, "same_edge_rho": SAME_EDGE_RHO,
                       "tail_rho_floor": TAIL_RHO_FLOOR, "co_loss_lift_same": CO_LOSS_LIFT_SAME,
                       "dd_jaccard_same": DD_JACCARD_SAME},
        "inputs": inputs,
        "survivors_total": len(surv),
        "survivors_with_returns": len(series),
        "culture_sources": grades,
        "pair_counts": {"total": len(pairs), **counts},
        "k_eff_survivors": k,
        "merge_groups": groups,
        "per_culture": cultures_pub,
        "crowding_prior_survival": crowding,
        "pairs": pairs[:MAX_PAIRS_PUBLISHED],
        "survivors": [surv[s] for s in sorted(surv)],
        "consumers": {
            "k_eff": "research/docket_keff.py score(): culture block, merge groups count once",
            "allocator": ("research/pf_allocator.py apply_culture_labels(): merge group = one "
                          "family and one mechanism for the cap and the structured correlation; "
                          "an all-DIVERGE survivor gets <family>@<culture>; heat-neutral"),
            "cro": "docs/cro/CRO_CYCLE.md STEP 4B duty D9"},
    }


# ------------------------------------------------------------------------------ consumers
def load(path: Path | None = None, *, now: datetime | None = None) -> tuple[Any, str]:
    """(doc, why): the published artifact when present and fresh, else (None, why)."""
    doc = _read(path or REPORT)
    if not isinstance(doc, dict):
        return None, "reports/CULTURE_ORTHOGONALITY.json is absent or unreadable"
    try:
        at = datetime.fromisoformat(str(doc.get("at")))
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
    except ValueError:
        return None, "reports/CULTURE_ORTHOGONALITY.json is undated"
    age_h = ((now or datetime.now(tz=UTC)) - at).total_seconds() / 3600.0
    if age_h > MAX_AGE_H:
        return None, (f"reports/CULTURE_ORTHOGONALITY.json is {age_h:.1f}h old "
                      f"(fresh means <= {MAX_AGE_H}h)")
    return doc, f"culture artifact {age_h:.2f}h old"


def allocator_labels(doc: Mapping[str, Any],
                     sleeves: Iterable[tuple[str, str, str, str]]) -> dict[str, dict[str, str]]:
    """{allocator sleeve name: {family, mechanism, why, survivor}} for sleeves the artifact
    relabels. Joined on (symbol, family, selector), then on (symbol, family) when that names ONE
    labelled survivor -- an ambiguous join relabels nothing."""
    exact: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    loose: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for s in doc.get("survivors") or []:
        if not isinstance(s, dict) or not isinstance(s.get("label"), dict):
            continue
        sym, fam = str(s.get("symbol") or "").lower(), str(s.get("family") or "").lower()
        exact.setdefault((sym, fam, str(s.get("selector") or "").lower()), []).append(s)
        loose.setdefault((sym, fam), []).append(s)
    out: dict[str, dict[str, str]] = {}
    for name, sym, fam, sel in sleeves:
        k2 = (str(sym).lower(), str(fam).lower())
        hits = exact.get((*k2, str(sel or "").lower())) or []
        labels = {json.dumps(h["label"], sort_keys=True) for h in hits}
        if len(labels) != 1:
            hits = loose.get(k2) or []
            labels = {json.dumps(h["label"], sort_keys=True) for h in hits}
        if len(labels) != 1:
            continue
        lab = hits[0]["label"]
        out[str(name)] = {"family": str(lab["family"]), "mechanism": str(lab["mechanism"]),
                          "why": str(lab.get("why") or ""), "survivor": str(hits[0]["id"])}
    return out


def docket_culture(doc: Any, why: str) -> dict[str, Any]:
    """The block docket_keff publishes: survivor k_eff with merge groups counted ONCE, and the
    (family|symbol) keys each merge group spans."""
    if not isinstance(doc, dict):
        return {"status": UNMEASURED, "why": why, "key_groups": {}}
    keys: dict[str, str] = {}
    for g in doc.get("merge_groups") or []:
        for k in g.get("keys") or []:
            keys.setdefault(str(k), str(g.get("group_id")))
    k = doc.get("k_eff_survivors") or {}
    return {"status": str(doc.get("status") or UNMEASURED), "why": why,
            "survivors_nominal": k.get("nominal"), "survivors_k_merged": k.get("merged"),
            "merge_groups": len(doc.get("merge_groups") or []),
            "pair_counts": doc.get("pair_counts"), "key_groups": keys}


# ------------------------------------------------------------------------------ CRO D20
def _western() -> frozenset[str]:
    try:
        from libs.research.cell_culture import WESTERN as w
        return frozenset(w)
    except Exception:
        return WESTERN


def _summary_counts(summary: Any, key: str) -> dict[str, int] | None:
    if not isinstance(summary, dict) or not isinstance(summary.get(key), dict):
        return None
    out: dict[str, int] = {}
    for c, n in summary[key].items():
        code = _culture_code(c) or UNMEASURED
        if isinstance(n, int):
            out[code] = out.get(code, 0) + n
    return out


def verdicts_counter(doc: Mapping[str, Any], summary: Any = None, *,
                     now: datetime | None = None) -> dict[str, Any]:
    """CRO duty D20, per source_culture: cells, judged, survivors, the orthogonality verdict
    against WESTERN-sourced survivors, and the non-Western share.

    Survivors and pair verdicts come from this organ's own pass (`doc`). Cells and judged come
    from #139's CELL_CULTURE.json summary; absent, they are UNMEASURED with INDEX_ABSENT, never
    0. A culture's verdict vs Western is read from its same-mechanism pairs with a Western
    survivor: ORTHOGONAL when every measured one DIVERGES, SAME_EDGE when every measured one is
    SAME_EDGE, MIXED otherwise, UNMEASURED when no such pair was measurable."""
    west = _western()
    if summary is None:
        summary = _read(CELL_CULTURE_SUMMARY)
    cells = _summary_counts(summary, "by_culture")
    judged = _summary_counts(summary, "judged_by_culture")
    have_index = cells is not None
    why_cells = "" if have_index else INDEX_ABSENT
    surv = {c: int(v.get("survivors") or 0) for c, v in (doc.get("per_culture") or {}).items()}
    vs: dict[str, dict[str, Any]] = {}
    for p in doc.get("pairs") or []:
        ca, cb = (list(p.get("cultures") or []) + [None, None])[:2]
        for mine, other in ((ca, cb), (cb, ca)):
            if mine is None or other not in west or mine in west:
                continue
            v = vs.setdefault(str(mine), {DIVERGE: 0, SAME_EDGE: 0, UNMEASURED: 0, "rho": []})
            key = str(p.get("verdict") or UNMEASURED)
            v[key] = v.get(key, 0) + 1
            if p.get("verdict") in (DIVERGE, SAME_EDGE) and _num(p.get("rho")) is not None:
                v["rho"].append(float(p["rho"]))
    cultures = sorted({*surv, *vs, *(cells or {}), *(judged or {})})
    rows: dict[str, Any] = {}
    for c in cultures:
        is_w = c in west
        v = vs.get(c)
        if is_w:
            verdict, why = "REFERENCE", "Western-sourced: the reference set"
        elif c == UNMEASURED:
            verdict, why = UNMEASURED, "no culture on these cells"
        elif not v or not (v[DIVERGE] or v[SAME_EDGE]):
            verdict = UNMEASURED
            why = (f"{v[UNMEASURED]} pair(s) with a Western survivor, none with enough "
                   f"overlap" if v else "no same-mechanism pair with a Western survivor")
        else:
            verdict = ("ORTHOGONAL" if not v[SAME_EDGE] else
                       SAME_EDGE if not v[DIVERGE] else "MIXED")
            why = f"{v[DIVERGE]} DIVERGE, {v[SAME_EDGE]} SAME_EDGE, {v[UNMEASURED]} UNMEASURED"
        rhos = sorted(v["rho"]) if v else []
        rows[c] = {
            "western": is_w if c != UNMEASURED else None,
            "cells": cells.get(c, 0) if cells is not None else UNMEASURED,
            "judged": judged.get(c, 0) if judged is not None else UNMEASURED,
            "survivors": surv.get(c, 0),
            "verdict_vs_western": verdict, "why": why,
            "pairs_vs_western": ({k: v[k] for k in (DIVERGE, SAME_EDGE, UNMEASURED)}
                                 if v else {DIVERGE: 0, SAME_EDGE: 0, UNMEASURED: 0}),
            "median_rho_vs_western": (round(rhos[len(rhos) // 2], 4) if rhos else UNMEASURED),
        }

    def share(counts: Mapping[str, int] | None) -> Any:
        if counts is None:
            return UNMEASURED
        known = {c: n for c, n in counts.items() if c not in (UNMEASURED, "GLOBAL")}
        tot = sum(known.values())
        return round(sum(n for c, n in known.items() if c not in west) / tot, 4) if tot \
            else UNMEASURED
    n_verdicts = sum(1 for r in rows.values()
                     if r["verdict_vs_western"] in ("ORTHOGONAL", SAME_EDGE, "MIXED"))
    return {
        "generated_at": (now or datetime.now(tz=UTC)).isoformat(timespec="seconds"),
        "organ": "culture_orthogonality", "duty": "D20",
        "metric": "culture_orthogonality_verdicts",
        "culture_orthogonality_verdicts": n_verdicts,
        "cultures_without_verdict": sorted(c for c, r in rows.items()
                                           if r["verdict_vs_western"] == UNMEASURED
                                           and c != UNMEASURED),
        "cells_source": (str(CELL_CULTURE_SUMMARY) if have_index else UNMEASURED),
        "cells_why": why_cells,
        "non_western_share": {"cells": share(cells) if have_index else UNMEASURED,
                              "judged": share(judged) if have_index else UNMEASURED,
                              "survivors": share(surv),
                              "basis": "of cells whose jurisdiction is known (GLOBAL excluded)"},
        "western": sorted(west),
        "pair_counts": doc.get("pair_counts"),
        "pairs_read": len(doc.get("pairs") or []),
        "pairs_cap": MAX_PAIRS_PUBLISHED,
        "per_culture": rows,
        "source_report": str(REPORT),
    }


# ------------------------------------------------------------------------------ writing
def write(doc: Mapping[str, Any], path: Path | None = None) -> Path:
    target = path or REPORT
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, target)
    return target


def run(*, docket: Iterable[Mapping[str, Any]] | None = None, dry_run: bool = False
        ) -> dict[str, Any]:
    doc = build(docket=docket)
    if not dry_run:
        write(doc)
        write(verdicts_counter(doc), VERDICTS_REPORT)
    return doc


def summary(doc: Mapping[str, Any]) -> str:
    pc = doc.get("pair_counts") or {}
    k = doc.get("k_eff_survivors") or {}
    return (f"culture orthogonality: {doc.get('status')} -- {doc.get('survivors_total')} "
            f"survivor(s), {doc.get('survivors_with_returns')} with live/forward R; pairs "
            f"{pc.get('total')} (DIVERGE {pc.get(DIVERGE)}, SAME_EDGE {pc.get(SAME_EDGE)}, "
            f"UNMEASURED {pc.get(UNMEASURED)}); k {k.get('nominal')} -> {k.get('merged')} "
            f"merged; cultures {sorted(doc.get('per_culture') or {})}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="cross-culture same-mechanism orthogonality test")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(dry_run=a.dry_run)
    print(summary(doc))
    print("  --dry-run: nothing written" if a.dry_run else f"-> {REPORT}")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
