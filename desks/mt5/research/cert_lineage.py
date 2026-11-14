#!/usr/bin/env python3
"""CERTIFICATE LINEAGE FOR EVERY LIVE WINDOW: which canon certificate a funded row stands on.

    python desks/mt5/research/cert_lineage.py            # print; writes only on the box / --out
    python scripts/check_cert_lineage.py --require-state  # the fence (FAIL on the trading box)

WHY (2026-10-20). The gold rows in `data/sleeves.json` (gold_asia_v2..v4, gold_london_am_v*,
gold_afternoon_v*) carry NO certificate field, the gateway's gold book sizes `gold_asia` by
WINDOW NAME from `data/CERT_BOOK_LIVE.json` (fusion 0.082, e8 0.01), and `decision_core.roster`
emits every GOLD_WINDOWS window LIVE unless GOLD_RETIRED names it. So a window that trades has no
traceable certificate: nothing joins the money to the ten-gate verdict that justified it.

LINEAGE IS IDENTITY (audit CERT_LINEAGE_1b89d5176, M1/M2). A certificate is the lineage of a
window only when the cell it certified IS the bracket the gateway trades. `resolve()` names it
from the row's own explicit fields first and from the canon second, and NEVER GUESSES:

  1. `principal_certificate`, then `certificate` (a dict's `cell`, or a string other than the
     non-canon marker `forward_clock`) -- what the writer itself recorded. NOT `cert_id`: that is
     this module's own stamp, and reading it back would make a lineage confirm itself;
  2. a cert-book key named by `PRINCIPAL_PROMOTIONS.json` (`book_key` -> `certificate`);
  3. the canon's `shadow_spec` join on (symbol, family, selector) over BOTH `survivors` and
     `pending_rejudge` (a certificate held back for re-judging keeps its name; it reads
     PENDING_REJUDGE, never UNRESOLVED) -- a window row is the session_range_breakout family on
     its window, exactly as `promoter.artifact_of` reads it.

EVERY candidate, however found, is then checked against what is traded. For a gold window the
traded bracket is read from ONE reader, `research.gold_window_params.traded_params` (shared with
the replication lane and the as-traded cells): rr, the trigger's life (signal hour to
`window_end_hour`), the force-close at CLOSE_HOUR, the EWM ATR over 400 H1 bars with its 5.0
floor and the stops_level padding, and the position_manager ratchet. A certificate whose
`params["as_traded"]` equals every one of those is the traded cell: RESOLVED (or PENDING_REJUDGE
while it waits). Any other certificate is the family's own bracket, which differs from the traded
one on the entry window, the exit, the stop and the management, so the best it can be is
NEAREST_CERT -- reported with `differing_fields`, never lineage. Among several candidates the
nearest is the one carrying the traded rr; none or several such is AMBIGUOUS. A certificate named
explicitly whose shadow_spec disagrees with the row (symbol, family, window, a declared param, or
the traded rr of a gold window) is EXPLICIT_MISMATCH. A row stamped on an earlier pass whose
`cert_spec_hash` no longer equals its certificate's is SPEC_DRIFT. Only RESOLVED is lineage.

`stamp_rows()` writes `cert_id`, `cert_spec_hash`, `cert_gated_at` and `cert_lineage` onto every
LIVE or STANDBY row; `cert_id` is set only when the lineage is RESOLVED (a nearest certificate is
recorded inside `cert_lineage`). They are ADDITIVE fields: no door, sizer or retirement reads
them, and this module changes no status, fraction or certificate. The writer of sleeves.json is
the sealed promoter; the hook that calls `stamp_rows` ships as a patch, and the gateway change
that excludes these four fields from its strategy-state identity must land BEFORE that hook.

CADENCE, STATED (not "hourly"). The report is written by `scripts/check_cert_lineage.py` when the
box's MT5-LawGate task (hourly at :40) runs `run_law_gate.py --rotate`: a 1800 s budget spent on
the fences OLDEST-FIRST, so this fence runs when it reaches the head of that queue -- at least
once inside the 48 h rotation window or the gate records it as never run (L1.49) -- and on every
full-mode battery. It writes CERT_LINEAGE.json only on the trading box or to an explicit --out:
an off-box run reads another machine's copies and must not overwrite the tracked report.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:  # pragma: no cover - import plumbing
        sys.path.insert(0, _p)

from libs.research.trade_identity import spec_hash  # noqa: E402

DATA = DESK / "data"
SLEEVES = DATA / "sleeves.json"
CANON = DATA / "UNIVERSAL_SURVIVORS.canon.json"
CERT_BOOK = DATA / "CERT_BOOK_LIVE.json"
PROMOTIONS = DATA / "PRINCIPAL_PROMOTIONS.json"
GOLD_RETIRED = DATA / "GOLD_RETIRED.json"
OUT = DESK / "reports" / "CERT_LINEAGE.json"

RESOLVED, AMBIGUOUS, UNRESOLVED = "RESOLVED", "AMBIGUOUS", "UNRESOLVED"
#: A canon certificate on the window that is NOT the traded cell: the closest one there is, with
#: what differs. Reported, never lineage (audit M2: lineage is identity).
NEAREST_CERT = "NEAREST_CERT"
#: An explicitly named certificate whose shadow_spec disagrees with the row it is named on.
EXPLICIT_MISMATCH = "EXPLICIT_MISMATCH"
#: A row's stamped cert_spec_hash no longer equals the hash of the certificate it names.
SPEC_DRIFT = "SPEC_DRIFT"
PENDING_REJUDGE, NOT_IN_CANON, UNMEASURED = "PENDING_REJUDGE", "NOT_IN_CANON", "UNMEASURED"
#: The lineage verdicts the fence accepts: identity only.
LINEAGE_OK = frozenset({RESOLVED})
#: The family a row that names only a window trades: the gold book's bracket, as the promoter's
#: own `artifact_of` defaults it.
WINDOW_FAMILY = "session_range_breakout"
GOLD_SYMBOL = "XAUUSD"
#: The marker a forward-clock-only row carries in `certificate`: not a canon key.
NON_CANON_MARKERS = frozenset({"", "forward_clock", "none", "None"})
STAMPED_STATUSES = ("LIVE", "STANDBY")
#: Canon blocks a certificate can be named from: a held-back one keeps its name (audit (c)).
CANON_BLOCKS = ("survivors", "pending_rejudge")
#: The traded parameter that picks the nearest candidate when none is the traded cell: the one
#: number the family's params and the gateway's bracket both name.
NEAREST_KEYS = ("rr",)
#: The session_range_breakout filters the traded bracket does not apply (their "off" values).
_UNFILTERED = {"spread_gate": False, "trend_filter": "none", "range_filter": "all",
               "vol_filter": "all", "midpoint_filter": "off"}


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _block(doc: Any, key: str) -> dict[str, Any]:
    v = doc.get(key) if isinstance(doc, dict) else None
    return v if isinstance(v, dict) else {}


def on_trading_box() -> bool:
    return os.name == "nt"


def _explicit(row: dict[str, Any]) -> tuple[str | None, str]:
    for field in ("principal_certificate", "certificate"):
        v = row.get(field)
        cell = v.get("cell") if isinstance(v, dict) else v
        if isinstance(cell, str) and cell not in NON_CANON_MARKERS:
            return cell, f"row field `{field}`"
    return None, ""


def _book_map(promotions: Any) -> dict[str, str]:
    rows = promotions.get("fusion") if isinstance(promotions, dict) else None
    out: dict[str, str] = {}
    for e in rows if isinstance(rows, list) else []:
        if isinstance(e, dict) and e.get("book_key") and e.get("certificate"):
            out[str(e["book_key"])] = str(e["certificate"])
    return out


def _spec_of(row: dict[str, Any]) -> tuple[str, str, str] | None:
    """(symbol, family, selector) a row declares, or None when it declares too little."""
    sym = str(row.get("symbol") or "").upper()
    window = row.get("window") or row.get("session") or row.get("selector")
    fam = str(row.get("family") or (WINDOW_FAMILY if row.get("window") else ""))
    if not sym or not fam or not window:
        return None
    return sym, fam, str(window)


def _window_of_key(key: str) -> dict[str, Any] | None:
    """A gateway gold-book window key (`gold_asia`, `gold_london_am`) as a row-shaped spec."""
    if key.startswith("gold_"):
        return {"symbol": GOLD_SYMBOL, "window": key[len("gold_"):]}
    return None


def _cert_row(cert_id: str, canon: Any) -> tuple[str | None, dict[str, Any]]:
    """(block, row) of a certificate in the canon, or (None, {})."""
    for block in CANON_BLOCKS:
        row = _block(canon, block).get(cert_id)
        if isinstance(row, dict):
            return block, row
    return None, {}


def _shadow(row: dict[str, Any]) -> dict[str, Any]:
    ss = row.get("shadow_spec")
    return ss if isinstance(ss, dict) else {}


def _params(row: dict[str, Any]) -> dict[str, Any]:
    p = _shadow(row).get("params")
    return p if isinstance(p, dict) else {}


def _canon_join(spec: tuple[str, str, str], canon: Any) -> list[str]:
    """Every certificate in `survivors` OR `pending_rejudge` whose shadow_spec is on `spec`."""
    sym, fam, sel = spec
    hits = set()
    for block in CANON_BLOCKS:
        for k, r in _block(canon, block).items():
            ss = _shadow(r) if isinstance(r, dict) else {}
            if (str(ss.get("symbol") or "").upper() == sym
                    and str(ss.get("family") or "") == fam
                    and str(ss.get("selector") or "") == sel):
                hits.add(str(k))
    return sorted(hits)


def traded_params(window: str | None) -> dict[str, Any]:
    """The bracket the gateway trades for a gold window: `research.gold_window_params` verbatim.

    ONE READER (2026-10-20): the replication lane, the as-traded cells and this join read the
    same function, which reads decision_core. {} means it cannot be read, or the window is not
    one decision_core places -- the caller treats that as UNMEASURED, never as a match.
    """
    try:
        from research.gold_window_params import traded_params as read
    except Exception:  # an unreadable source is UNMEASURED, never a filter that passes
        return {}
    return read(window)


def _family_defaults() -> dict[str, Any]:
    """The session_range_breakout family's own defaults, read from its signature."""
    try:
        from mt5desk.families import family_session_range_breakout as fam
    except Exception:
        return {}
    return {k: p.default for k, p in inspect.signature(fam).parameters.items()
            if p.default is not inspect.Parameter.empty}


def _norm(v: Any) -> Any:
    return json.loads(json.dumps(v, default=str))


def _eq(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
            and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) < 1e-9
    return bool(_norm(a) == _norm(b))


def _cert_rr(params: dict[str, Any]) -> Any:
    at = params.get("as_traded")
    if isinstance(at, dict) and "rr" in at:
        return at["rr"]
    return params.get("rr", _family_defaults().get("rr"))


def differing_fields(params: dict[str, Any], tp: dict[str, Any]) -> dict[str, Any]:
    """What the certified cell does that the traded bracket does not. {} = it IS the traded cell.

    A cell that carries `as_traded` (research/traded_gold_cells) is compared key by key with
    `tp`. Any other cell is the family's own bracket, compared structurally on the places the
    audit names: rr, the range, the entry window, the exit, the stop, the management, filters.
    """
    at = params.get("as_traded")
    if isinstance(at, dict):
        return {k: {"cert": _norm(at.get(k)), "traded": _norm(v)} for k, v in tp.items()
                if not _eq(at.get(k), v)}
    d = {**_family_defaults(), **params}
    out: dict[str, Any] = {}
    if not _eq(d.get("rr"), tp["rr"]):
        out["rr"] = {"cert": d.get("rr"), "traded": tp["rr"]}
    rng = tp.get("rng")
    traded_rng = ({"range_start": tp["sig_hour"], "range_end": None, "signal_at": None}
                  if not rng else {"range_start": rng[0], "range_end": rng[1],
                                   "signal_at": tp["sig_hour"]})
    cert_rng = {k: d.get(k) for k in traded_rng}
    if not _eq(cert_rng, traded_rng):
        out["range"] = {"cert": cert_rng, "traded": traded_rng}
    if not _eq(d.get("wait_bars"), tp["trigger_life_h1_bars"]):
        out["entry_window"] = {"cert": {"wait_bars": d.get("wait_bars")},
                               "traded": {"h1_bars": tp["trigger_life_h1_bars"],
                                          "trigger_dies_at_server_hour": tp["window_end"]}}
    out["exit"] = {"cert": {"ttl_bars": d.get("ttl_bars")},
                   "traded": {"force_close_server_hour": tp["close_hour"]}}
    out["stop"] = {"cert": {"atr": f"rolling-mean ATR({d.get('atr_n')})",
                            "dist": "max(1.2*atr, span)", "atr_floor": None,
                            "stops_level_pad": None},
                   "traded": {"atr": f"EWM ATR({tp['atr_n']}) over {tp['gateway_h1_bars']} H1 "
                                     "bars incl. the forming bar",
                              "dist": f"max({tp['atr_mult']}*atr, span)",
                              "atr_floor": tp["atr_floor"],
                              "stops_level_pad": f"trade_stops_level or "
                                                 f"{tp['stops_level_default']} points"}}
    out["management"] = {"cert": "fixed stop and target",
                         "traded": "position_manager.ratchet (trail, breakeven) + OCO cancel"}
    filters = {k: d[k] for k in _UNFILTERED if k in d}
    if any(not _eq(v, _UNFILTERED[k]) for k, v in filters.items()):
        out["filters"] = {"cert": filters, "traded": "none"}
    return out


def _in_canon(cert_id: str, canon: Any) -> dict[str, Any]:
    if canon is None:
        return {"lineage": UNMEASURED, "why": "canon absent or unreadable"}
    block, row = _cert_row(cert_id, canon)
    if block == "survivors":
        ss = _shadow(row)
        return {"lineage": RESOLVED, "cert_spec_hash": spec_hash(ss) if ss else None,
                "cert_gated_at": row.get("gated_at")}
    if block == "pending_rejudge":
        return {"lineage": PENDING_REJUDGE,
                "why": "in the canon's pending_rejudge: awaiting a fresh judge verdict"}
    return {"lineage": NOT_IN_CANON, "why": "not a canon survivor"}


def _gold(spec: tuple[str, str, str] | None) -> bool:
    return spec is not None and spec[0] == GOLD_SYMBOL and spec[1] == WINDOW_FAMILY


def _explicit_mismatch(row: dict[str, Any], spec: tuple[str, str, str] | None,
                       cert: dict[str, Any], tp: dict[str, Any]) -> dict[str, Any]:
    """Fields the row declares (or trades) that the named certificate's shadow_spec contradicts."""
    ss, params = _shadow(cert), _params(cert)
    bad: dict[str, Any] = {}
    declared = {"symbol": str(row.get("symbol") or "").upper() or None,
                "family": row.get("family") or (spec[1] if spec else None),
                "selector": spec[2] if spec else None}
    for k, v in declared.items():
        got = ss.get(k)
        if v and got is not None and str(got).upper() != str(v).upper():
            bad[k] = {"row": v, "cert": got}
    rp = row.get("params")
    for k, v in (rp.items() if isinstance(rp, dict) else ()):
        if k in params and not _eq(params[k], v):
            bad[f"params.{k}"] = {"row": v, "cert": params[k]}
    if _gold(spec) and tp and not _eq(_cert_rr(params), tp["rr"]):
        bad["traded.rr"] = {"traded": tp["rr"], "cert": _cert_rr(params)}
    return bad


def _judge_candidate(cert_id: str, canon: Any, spec: tuple[str, str, str] | None,
                     tp: dict[str, Any], basis: str) -> dict[str, Any]:
    """One named certificate against the traded bracket: RESOLVED/PENDING only on identity."""
    found = _in_canon(cert_id, canon)
    if found["lineage"] not in (RESOLVED, PENDING_REJUDGE) or not _gold(spec):
        return {"cert_id": cert_id, "basis": basis, **found}
    if not tp:
        return {"lineage": UNMEASURED, "cert_id": None, "nearest_cert": cert_id, "basis": basis,
                "why": f"the traded bracket of {spec} cannot be read (gold_window_params): "
                       "identity is unmeasured"}
    diff = differing_fields(_params(_cert_row(cert_id, canon)[1]), tp)
    if not diff:
        return {"cert_id": cert_id, "basis": f"{basis}; the certified cell IS the traded bracket",
                "traded_params": tp, **found}
    return {"lineage": NEAREST_CERT, "cert_id": None, "nearest_cert": cert_id,
            "nearest_cert_state": found["lineage"], "basis": basis, "traded_params": tp,
            "differing_fields": diff,
            "why": ("the certified cell is not the bracket the gateway trades ("
                    + ", ".join(sorted(diff)) + "); lineage is identity, so this is the "
                    "nearest certificate, not the window's lineage")}


def resolve(row: dict[str, Any] | None, canon: Any, promotions: Any = None,
            book_key: str | None = None,
            traded: dict[str, Any] | None = None) -> dict[str, Any]:
    """The certificate lineage of `row` (or of a cert-book key when `row` is None).

    `traded` overrides `traded_params(window)` (tests); None reads gold_window_params, and {}
    means the traded bracket is unreadable (UNMEASURED for a gold window).
    """
    row = row if isinstance(row, dict) else {}
    spec = _spec_of(row) or _spec_of(_window_of_key(book_key or str(row.get("name") or ""))
                                     or {})
    tp = traded if traded is not None else (traded_params(spec[2])
                                             if spec is not None and _gold(spec) else {})
    cert_id, basis = _explicit(row)
    if cert_id is None and book_key:
        mapped = _book_map(promotions).get(book_key)
        if mapped:
            cert_id, basis = mapped, f"PRINCIPAL_PROMOTIONS book_key `{book_key}`"
    if cert_id is not None:
        block, cert = _cert_row(cert_id, canon)
        if block is not None:
            bad = _explicit_mismatch(row, spec, cert, tp)
            if bad:
                return {"lineage": EXPLICIT_MISMATCH, "cert_id": None, "named_cert": cert_id,
                        "basis": basis, "mismatch": bad,
                        "why": f"{basis} names {cert_id}, whose shadow_spec contradicts the "
                               f"row on {sorted(bad)}"}
        return _drift(row, _judge_candidate(cert_id, canon, spec, tp, basis))
    if spec is None:
        return {"lineage": UNRESOLVED, "cert_id": None,
                "why": "no certificate field, no principal mapping, and no symbol/family/"
                       "window to join the canon on"}
    if _gold(spec) and not tp:
        return {"lineage": UNMEASURED, "cert_id": None, "join": list(spec),
                "why": f"the traded bracket of {spec} cannot be read (gold_window_params): "
                       "no candidate can be judged"}
    hits = _canon_join(spec, canon)
    if not hits:
        return {"lineage": UNRESOLVED, "cert_id": None, "join": list(spec), "candidates": [],
                "why": f"no canon survivor or pending certificate matches {spec}"}
    if not _gold(spec):
        return _join_declared(row, spec, hits, canon)
    # M1: every join is judged, a unique one included. The traded cell first (identity) ...
    exact = [k for k in hits if not differing_fields(_params(_cert_row(k, canon)[1]), tp)]
    if len(exact) == 1:
        got = _judge_candidate(exact[0], canon, spec, tp,
                               f"canon shadow_spec join on {spec}, {len(hits)} candidate(s)")
        return _drift(row, {**got, "candidates": hits})
    if len(exact) > 1:
        return {"lineage": AMBIGUOUS, "cert_id": None, "join": list(spec), "candidates": hits,
                "traded_match": exact, "traded_params": tp,
                "why": f"{len(exact)} certificates on {spec} are each the traded cell; a lineage "
                       "is one certificate, never a pick"}
    # ... then the nearest: the one candidate carrying the traded rr, reported as NEAREST_CERT.
    kept = filter_by_traded(hits, canon, tp)
    if len(kept) != 1:
        return {"lineage": AMBIGUOUS if len(hits) > 1 else UNRESOLVED, "cert_id": None,
                "join": list(spec), "candidates": hits, "traded_params": tp,
                "traded_match": kept,
                "why": (f"{len(hits)} canon certificate(s) on {spec}, none is the traded cell, "
                        f"and {len(kept)} carry the traded {list(NEAREST_KEYS)}; a lineage is "
                        "one certificate, never a pick")}
    got = _judge_candidate(kept[0], canon, spec, tp,
                           f"canon shadow_spec join on {spec}: {len(hits)} candidate(s), one "
                           f"carries the traded {list(NEAREST_KEYS)}")
    return {**got, "candidates": hits, "traded_match": kept}


def _join_declared(row: dict[str, Any], spec: tuple[str, str, str], hits: list[str],
                   canon: Any) -> dict[str, Any]:
    """A non-gold row joined to the canon: what it trades is what it DECLARES (`params`).

    Exactly one candidate whose params equal every declared param is the row's cell; a row that
    declares nothing cannot prove identity, so a unique join is only its nearest certificate.
    """
    rp = row.get("params") if isinstance(row.get("params"), dict) else {}
    if not rp:
        if len(hits) == 1:
            return {"lineage": NEAREST_CERT, "cert_id": None, "nearest_cert": hits[0],
                    "join": list(spec), "candidates": hits,
                    "why": "a unique join, but the row declares no params to prove the "
                           "certified cell is the one it trades"}
        return {"lineage": AMBIGUOUS, "cert_id": None, "join": list(spec), "candidates": hits,
                "why": f"{len(hits)} canon certificates match {spec} and the row declares no "
                       "params to separate them"}
    match = [k for k in hits if all(p in _params(_cert_row(k, canon)[1])
                                    and _eq(_params(_cert_row(k, canon)[1])[p], v)
                                    for p, v in rp.items())]
    if len(match) != 1:
        return {"lineage": AMBIGUOUS if match else UNRESOLVED, "cert_id": None,
                "join": list(spec), "candidates": hits, "traded_match": match,
                "why": f"{len(match)} of {len(hits)} canon certificates on {spec} carry every "
                       "param the row declares"}
    got = _judge_candidate(match[0], canon, spec, {},
                           f"canon shadow_spec join on {spec}, every declared param equal")
    return _drift(row, {**got, "candidates": hits})


def filter_by_traded(hits: list[str], canon: Any, traded: dict[str, Any]) -> list[str]:
    """The candidates whose params EQUAL the traded value of every NEAREST_KEYS key.

    A candidate that does not name a key is not kept on it (a family default is not a claim the
    certificate made); an empty `traded` keeps nothing.
    """
    keys = [k for k in NEAREST_KEYS if k in traded]
    out = []
    for k in hits:
        params = _params(_cert_row(k, canon)[1])
        if keys and all(p in params and _eq(params[p], traded[p]) for p in keys):
            out.append(k)
    return out


def _drift(row: dict[str, Any], got: dict[str, Any]) -> dict[str, Any]:
    """SPEC_DRIFT when this row was stamped with the same certificate under another spec hash.

    The only place the row's own stamp is read, and only to be compared, never as a basis.
    """
    stamped, was = row.get("cert_spec_hash"), row.get("cert_id")
    if got.get("lineage") == RESOLVED and stamped and was == got.get("cert_id") \
            and got.get("cert_spec_hash") and stamped != got["cert_spec_hash"]:
        return {**got, "lineage": SPEC_DRIFT, "stamped_spec_hash": stamped,
                "why": "the certificate this row was stamped with has a different spec hash now: "
                       "its cell changed under the row"}
    return got


def stamp_rows(rows: list[dict[str, Any]], canon: Any, promotions: Any = None) -> int:
    """Write the lineage fields onto every LIVE/STANDBY row in place. Returns rows stamped.

    Additive only: status, risk_frac and `certificate` are never touched. `cert_id` is set only
    on a RESOLVED lineage; a nearest certificate is recorded inside `cert_lineage`.
    """
    n = 0
    for row in rows:
        if not isinstance(row, dict) or str(row.get("status") or "").upper() \
                not in STAMPED_STATUSES:
            continue
        lin = resolve(row, canon, promotions)
        ok = lin.get("lineage") == RESOLVED
        row["cert_id"] = lin.get("cert_id") if ok else None
        row["cert_spec_hash"] = lin.get("cert_spec_hash") if ok else None
        row["cert_gated_at"] = lin.get("cert_gated_at") if ok else None
        row["cert_lineage"] = {k: lin.get(k) for k in (
            "lineage", "basis", "why", "candidates", "nearest_cert", "nearest_cert_state",
            "named_cert", "mismatch", "differing_fields") if lin.get(k) is not None}
        n += 1
    return n


def _book_keys(book: Any) -> list[tuple[str, str, float]]:
    """(venue, key, risk) for every positively sized cert-book key, when the book is enabled."""
    if not isinstance(book, dict) or book.get("enabled") is not True:
        return []
    out = []
    for venue in ("fusion", "e8"):
        for key, risk in _block(book, venue).items():
            try:
                r = float(risk)
            except (TypeError, ValueError):
                continue
            if r > 0:
                out.append((venue, str(key), r))
    return out


def roster_windows(retired: Any) -> list[dict[str, Any]] | None:
    """The gold windows the gateway emits LIVE: `decision_core.roster` itself. None = unreadable.

    Audit M3: roster() emits every GOLD_WINDOWS row unless GOLD_RETIRED names it, sized in the
    cert book or not, so the fence enumerates exactly what the gateway enumerates.
    """
    try:
        from mt5desk import decision_core as dc
        rows, _notes = dc.roster(retired if isinstance(retired, dict) else {}, [])
    except Exception:
        return None
    return [r for r in rows if str(r.get("name") or "").startswith("gold_")]


def build(*, sleeves: Path = SLEEVES, canon: Path = CANON, book: Path = CERT_BOOK,
          promotions: Path = PROMOTIONS, retired: Path = GOLD_RETIRED,
          now: datetime | None = None) -> dict[str, Any]:
    """Every LIVE/STANDBY row, every roster gold window and every sized cert-book key."""
    s_doc, c_doc, b_doc, p_doc = _read(sleeves), _read(canon), _read(book), _read(promotions)
    rows = s_doc.get("sleeves") if isinstance(s_doc, dict) else None
    out: dict[str, Any] = {"generated_utc": (now or datetime.now(UTC)).isoformat(
        timespec="seconds"), "canon_readable": c_doc is not None,
        "sleeves_readable": isinstance(rows, list), "rows": [], "windows": [],
        "roster_windows": []}
    by_name = {str(r.get("name")): r for r in rows or [] if isinstance(r, dict)}
    by_principal = {str(e.get("book_key")): str(e.get("name"))
                    for e in (p_doc or {}).get("fusion") or [] if isinstance(e, dict)}
    for r in rows or []:
        if isinstance(r, dict) and str(r.get("status") or "").upper() in STAMPED_STATUSES:
            out["rows"].append({"name": r.get("name"), "status": r.get("status"),
                                "risk_frac": r.get("risk_frac"),
                                **resolve(r, c_doc, p_doc)})
    for venue, key, risk in _book_keys(b_doc):
        row = by_name.get(by_principal.get(key, ""))
        out["windows"].append({"venue": venue, "key": key, "risk": risk,
                               **resolve(row, c_doc, p_doc, book_key=key)})
    roster = roster_windows(_read(retired))
    out["roster_readable"] = roster is not None
    for w in roster or []:
        name = str(w["name"])
        out["roster_windows"].append({"key": name, "window": w.get("window"),
                                      **resolve({"name": name, "symbol": w.get("symbol"),
                                                 "window": w.get("window")},
                                                c_doc, p_doc, book_key=name)})
    return finish(out, by_name)


def finish(out: dict[str, Any], by_name: dict[str, Any]) -> dict[str, Any]:
    """The counts and the violation list. A violation is a LIVE row, a roster gold window or a
    sized cert-book window whose lineage is not RESOLVED, or a roster that cannot be read."""
    bad = []
    for r in out["rows"]:
        if str(by_name.get(str(r["name"]), {}).get("status") or "").upper() == "LIVE" \
                and r.get("lineage") not in LINEAGE_OK:
            bad.append({"kind": "live_row", "name": r["name"], "lineage": r.get("lineage"),
                        "cert_id": r.get("cert_id"), "nearest_cert": r.get("nearest_cert"),
                        "why": r.get("why")})
    for w in out.get("roster_windows") or []:
        if w.get("lineage") not in LINEAGE_OK:
            bad.append({"kind": "roster_window", "key": w["key"], "lineage": w.get("lineage"),
                        "cert_id": w.get("cert_id"), "nearest_cert": w.get("nearest_cert"),
                        "candidates": w.get("candidates"), "why": w.get("why")})
    if out.get("roster_readable") is False:
        bad.append({"kind": "roster_window", "key": "*", "lineage": UNMEASURED,
                    "why": "decision_core.roster could not be read: the windows the gateway "
                           "emits are unmeasured"})
    for w in out["windows"]:
        if w.get("lineage") not in LINEAGE_OK:
            bad.append({"kind": "cert_book_window", "venue": w["venue"], "key": w["key"],
                        "risk": w["risk"], "lineage": w.get("lineage"),
                        "cert_id": w.get("cert_id"), "nearest_cert": w.get("nearest_cert"),
                        "candidates": w.get("candidates"), "why": w.get("why")})
    out["violations"] = bad
    out["n_violations"] = len(bad)
    out["rule"] = ("every LIVE sleeve row, every gold window decision_core.roster emits and every "
                   "positively sized CERT_BOOK_LIVE window names exactly one canon survivor that "
                   "IS the traded cell (cert_id, spec hash, gated_at); NEAREST_CERT, AMBIGUOUS, "
                   "UNRESOLVED, EXPLICIT_MISMATCH, SPEC_DRIFT, PENDING_REJUDGE, NOT_IN_CANON and "
                   "UNMEASURED are not lineage")
    return out


def write(doc: dict[str, Any], out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{out.name}.", dir=str(out.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, default=str)
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def out_path(explicit: Path | None) -> Path | None:
    """Where the report goes: an explicit --out, else OUT on the trading box, else nowhere."""
    if explicit is not None:
        return explicit
    return OUT if on_trading_box() else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=None,
                    help="write the report here (default: reports/CERT_LINEAGE.json on the "
                         "trading box only)")
    ap.add_argument("--sleeves", type=Path, default=SLEEVES)
    ap.add_argument("--canon", type=Path, default=CANON)
    a = ap.parse_args(argv)
    doc = build(sleeves=a.sleeves, canon=a.canon)
    dest = out_path(a.out)
    if dest is not None:
        write(doc, dest)
    print(json.dumps({**{k: doc[k] for k in ("n_violations", "canon_readable",
                                             "sleeves_readable", "roster_readable")},
                      "written": str(dest) if dest else None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
