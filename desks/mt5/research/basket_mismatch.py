"""BASKET_MISMATCH: certificates whose identity names a factor the certifier never had.

THE RULING (judge, 2026-10-20). Before ef11ff615 (2026-09-28 06:00:59Z) `external_gauntlet.
build_cell` built a residual cell from whichever named factors had bars and SILENTLY DROPPED the
rest. A factor that had no intraday bars in the lake therefore vanished from the model while its
name stayed in the certificate's identity: the 24 `['USDX', 'UST10Y']` cross_asset_residual
certificates were judged on USDX alone. Their identity is not what was certified, so:

  * they are marked BASKET_MISMATCH and can never promote; their forward clocks keep running
    under UNMEASURED_BASKET_MISMATCH, which is never evidence for the named identity;
  * their TRUE identity -- the same cell on the basket that was actually present -- is judged
    instead: LINKED to an existing verdict where that exact cell already exists, otherwise MINTED
    into the judge docket once, charged under the fixed N=5 bar. Nothing is replayed under the
    named identity.

DETECTION IS A RULE, NOT A LIST. A certificate is a mismatch when ALL of these hold:
  1. its family takes a factor basket (`cross_asset_residual`, `pca_residual`);
  2. it was certified before ef11ff615 landed;
  3. a factor named in its identity had no bars on the certificate's chart at certification.
     Evidence, strongest first: the registry row's `intraday_coverage[<tf>].bars == 0`, its
     `trade_mode` (not 4) or `tradeable: false`; else the measured close-only list
     (`data/universe/close_only_symbols.json`) -- `fetch_universe._fetch_intraday` writes no
     intraday file for a close-only symbol and `refresh_tail` never creates one. H1/H4/D1 are
     never claimed missing by this rule: the lake holds those for every registry symbol.

WHAT THIS WRITES
  reports/BASKET_MISMATCH.json          the hits, per-factor evidence, the true basket, and the
                                        re-judge disposition of each (tracked; read by
                                        shadow_forward and check_certificate_clock_law)
  data/hypotheses/basket_rejudge.json   the MINTED true-identity cells not emitted before, as a
                                        merge_hypotheses source (rewritten each run)
  data/hypotheses/basket_rejudge_minted.json   every cell ever emitted: charged ONCE, never
                                        re-emitted
  data/sleeves.json (--apply only)      a LIVE/STANDBY sleeve on a mismatch certificate is
                                        RETIRED with the ruling as its reason. The promoter never
                                        resurrects RETIRED (`promoter.py`: "RETIRED is a one-way
                                        door") and heal_silent_demotions never touches it.
Nothing is deleted.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "BASKET_MISMATCH.json"
REJUDGE = DESK / "data" / "hypotheses" / "basket_rejudge.json"
CLOCK_LAW = DESK / "reports" / "CERTIFICATE_CLOCK_LAW.json"
CLOSE_ONLY = DESK / "data" / "universe" / "close_only_symbols.json"
REGISTRY = DESK / "data" / "universe" / "universe.json"
SEEN_CELLS = DESK / "data" / "hypotheses" / "gauntlet_seen_cells.json"
VERDICT_INDEX = DESK / "data" / "hypotheses" / "gate_verdict_index.json"
SLEEVES = DESK / "data" / "sleeves.json"
#: Every true-identity cell this organ has handed the docket, with when. CHARGED ONCE: a cell in
#: here is never emitted again, so an hourly run cannot re-buy its trial.
MINTED_LEDGER = DESK / "data" / "hypotheses" / "basket_rejudge_minted.json"

#: ef11ff615 "block incomplete factor baskets from forward evidence", 2026-09-28 07:00:59 +0100.
PARTIAL_BASKET_FIXED_AT = datetime(2026, 9, 28, 6, 0, 59, tzinfo=UTC)
BASKET_FAMILIES = frozenset({"cross_asset_residual", "pca_residual"})
INTRADAY = frozenset({"M1", "M5", "M15", "M30"})
VERDICT = "BASKET_MISMATCH"
CLOCK_STATUS = "UNMEASURED_BASKET_MISMATCH"
SOURCE = "basket_mismatch_rejudge"

# ---- the PIT rates re-mint (judge, 2026-10-20 addendum) ----------------------------------------
#: `futures_state` (bundle futures_state_20c2bb473, lands after the freeze) writes the FRED
#: Treasury curve as `data/lake/series/fred_ust.parquet`: one `y_<FRED id>` column per tenor plus
#: the PIT envelope (`available_time` = the day after the close at 23:00 UTC, `event_time`,
#: `source_id`, `retrieval_time`).
PIT_SERIES = "fred_ust"
PIT_SERIES_DIR = DESK / "data" / "lake" / "series"
#: The rates leg each close-only factor is re-minted on, as a `<series>:<column>` factor name.
PIT_RATES_LEG = {"UST10Y": f"{PIT_SERIES}:y_DGS10", "UST05Y": f"{PIT_SERIES}:y_DGS5"}
PIT_SOURCE = "basket_mismatch_pit_remint"
PENDING = f"PENDING_SERIES:{PIT_SERIES}"


def bar_n() -> int:
    """The fixed N of the Tier S bar (T8 ruling: DSR at N=5). The guard module's constant when it
    is on this branch, otherwise the literal the ruling names."""
    try:
        from libs.research.trial_count_guard import BAR_N  # type: ignore[import-not-found]
        return int(BAR_N)
    except Exception:
        return 5


def _read(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _ts(raw: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


# ---------------------------------------------------------------- params from a clock key

def _param_names(family: str) -> list[str]:
    import inspect

    from mt5desk.family_inputs import IDENTITY_KEYS
    try:
        from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
        fn = ORTHOGONAL_FAMILIES.get(family)
        names = ([p for p in inspect.signature(fn).parameters if p != "df"]  # type: ignore[arg-type]
                 if fn else [])
    except Exception:
        names = []
    return sorted(set(names) | set(IDENTITY_KEYS), key=len, reverse=True)


def params_from_key(key: str, family: str) -> dict[str, Any] | None:
    """The params a `shadow_forward.sleeve_key` was built from, or None when ambiguous.

    The key is `SYM.family.sel[@TF]#k=v_k=v...` with keys sorted; values are `str()` of Python
    literals. Boundaries are found on the family's own parameter names, so an underscore inside a
    name (`beta_win`) is never mistaken for a separator. The caller verifies the result by
    recomputing the certificate's own cell id from it.
    """
    head, _, sig = key.partition("#")
    if sig.endswith(".SHORT"):
        sig = sig[: -len(".SHORT")]
    tf = head.split("@", 1)[1].upper() if "@" in head else "H1"
    names = _param_names(family)
    hits: list[tuple[int, str]] = []
    for n in names:
        for m in re.finditer(r"(?:^|_)" + re.escape(n) + "=", sig):
            start = m.start() + (1 if m.group(0).startswith("_") else 0)
            if not any(s <= start < s + len(o) + 1 for s, o in hits):
                hits.append((start, n))
    hits.sort()
    out: dict[str, Any] = {}
    for i, (s, n) in enumerate(hits):
        end = hits[i + 1][0] - 1 if i + 1 < len(hits) else len(sig)
        raw = sig[s + len(n) + 1:end]
        try:
            out[n] = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            out[n] = raw
    if tf != "H1":
        out["timeframe"] = tf
    return out or None


# ---------------------------------------------------------------- evidence

def no_bars_evidence(factor: str, tf: str, registry: dict[str, Any],
                     close_only: set[str]) -> str | None:
    """Why `factor` had no `tf` bars in the lake, or None when nothing says so."""
    if tf.upper() not in INTRADAY:
        return None
    got = registry.get(factor)
    row: dict[str, Any] = got if isinstance(got, dict) else {}
    cov = (row.get("intraday_coverage") or {}).get(tf.upper()) if isinstance(
        row.get("intraday_coverage"), dict) else None
    if isinstance(cov, dict) and int(cov.get("bars") or 0) == 0:
        return f"registry intraday_coverage[{tf}]: 0 bars ({cov.get('reason') or 'no reason'})"
    tm = row.get("trade_mode")
    if tm is not None and int(tm) != 4:
        return (f"registry trade_mode {tm} (not FULL): fetch_universe writes no intraday parquet "
                f"for it")
    if row.get("tradeable") is False:
        return "registry tradeable=false: fetch_universe writes no intraday parquet for it"
    if factor in close_only:
        return (f"close-only at Fusion ({CLOSE_ONLY.name}): fetch_universe._fetch_intraday wrote "
                f"no {tf} parquet (NOT_TRADEABLE) and refresh_tail never creates one")
    return None


def _registry() -> dict[str, Any]:
    doc = _read(REGISTRY, {}) or {}
    reg = doc.get("symbols", doc) if isinstance(doc, dict) else {}
    return reg if isinstance(reg, dict) else {}


def _close_only() -> set[str]:
    doc = _read(CLOSE_ONLY, {}) or {}
    return {str(s) for s in (doc.get("symbols") or [])} if isinstance(doc, dict) else set()


# ---------------------------------------------------------------- certificates

def certificates() -> tuple[list[dict[str, Any]], list[str]]:
    """Every basket-family certificate with its params, from the canon when this host holds it
    and from the clock-law artifact's published rows otherwise (params recovered from the clock
    key and VERIFIED against the certificate's own cell id)."""
    from research.frontier_identity import cell_id
    notes: list[str] = []
    out: dict[str, dict[str, Any]] = {}
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import check_certificate_clock_law as law  # type: ignore[import-not-found]
        canon, cnotes = law.certificates()
        keys, _kn = law.clock_keys(canon)
        for c in canon:
            if c["family"] in BASKET_FAMILIES:
                out[c["name"]] = {**c, "key": keys.get(c["name"])}
        notes.extend(cnotes[:3])
    except Exception as exc:
        notes.append(f"canon unreadable here ({type(exc).__name__}); using the clock-law rows")
    doc = _read(CLOCK_LAW, {}) or {}
    for r in doc.get("certificates") or []:
        if not isinstance(r, dict) or r.get("family") not in BASKET_FAMILIES:
            continue
        name = str(r.get("certificate") or "")
        if name in out or not r.get("key") or r.get("key") == "UNMEASURED":
            continue
        params = params_from_key(str(r["key"]), str(r["family"]))
        if params is None:
            notes.append(f"{name}: params not recoverable from its key")
            continue
        got = "external." + cell_id({"sym": r["symbol"], "family": r["family"],
                                     "params": params})
        verified = got == name
        if not verified:
            # The factor names in the key are still the identity's; only the re-judge needs the
            # exact params, so the row is detected and its re-judge refused, never guessed.
            notes.append(f"{name}: key round-trip gave {got}; re-judge refused rather than "
                         f"guessed")
        out[name] = {"name": name, "symbol": r["symbol"], "family": r["family"],
                     "selector": r.get("selector"), "side": r.get("side"), "params": params,
                     "certified_at": r.get("certified_at"), "key": r["key"],
                     "params_verified": verified}
    return list(out.values()), notes


# ---------------------------------------------------------------- the ruling

def _verdict_of(cell: str, index: Any, certs: set[str], seen: Any) -> dict[str, Any] | None:
    if f"external.{cell}" in certs:
        return {"verdict": "CERTIFIED", "certificate": f"external.{cell}"}
    if isinstance(index, dict) and cell in index:
        v = index[cell]
        return {"verdict": v.get("verdict") if isinstance(v, dict) else v,
                "source": VERDICT_INDEX.name}
    if isinstance(seen, dict) and cell in seen:
        return {"verdict": "JUDGED", "judged_at": seen[cell], "source": SEEN_CELLS.name}
    return None


def detect(certs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The ruling applied by rule: hits, evidence, and each hit's true-identity disposition."""
    from research.frontier_identity import cell_id
    notes: list[str] = []
    if certs is None:
        certs, notes = certificates()
    registry, close_only = _registry(), _close_only()
    all_certs = {str(c.get("certificate") or "") for c in
                 ((_read(CLOCK_LAW, {}) or {}).get("certificates") or [])} | {
        str(c["name"]) for c in certs}
    index, seen = _read(VERDICT_INDEX), _read(SEEN_CELLS)
    hits: list[dict[str, Any]] = []
    for c in certs:
        if c.get("family") not in BASKET_FAMILIES:
            continue
        at = _ts(c.get("certified_at"))
        if at is None or at >= PARTIAL_BASKET_FIXED_AT:
            continue
        params = dict(c.get("params") or {})
        tf = str(params.get("timeframe") or "H1").upper()
        names = [str(f) for f in (params.get("factor_symbols") or [])]
        missing = [{"factor": f, "evidence": ev} for f in names
                   if (ev := no_bars_evidence(f, tf, registry, close_only))]
        if not missing:
            continue
        gone = {m["factor"] for m in missing}
        true_basket = [f for f in names if f not in gone]
        entry: dict[str, Any] = {
            "certificate": c["name"], "key": c.get("key"), "symbol": c["symbol"],
            "family": c["family"], "timeframe": tf, "certified_at": c.get("certified_at"),
            "named_basket": names, "missing_factors": missing, "true_basket": true_basket,
            "status": VERDICT, "clock_status": CLOCK_STATUS, "may_promote": False,
            "params": params if c.get("params_verified") is not False else None}
        if not true_basket:
            entry["rejudge"] = {"status": "NOT_JUDGEABLE",
                                "why": "no named factor had bars: the family returned no signals"}
        elif c.get("params_verified") is False:
            entry["rejudge"] = {"status": "NOT_JUDGEABLE",
                                "why": "params not recoverable from the clock key (cell id "
                                       "round-trip failed); re-judge needs the canon row"}
        else:
            q = dict(params, factor_symbols=true_basket)
            cell = cell_id({"sym": c["symbol"], "family": c["family"], "params": q})
            linked = _verdict_of(cell, index, all_certs, seen)
            entry["rejudge"] = ({"status": "LINKED", "cell": cell, "verdict": linked,
                                 "charged": 0}
                                if linked else
                                {"status": "MINTED", "cell": cell, "params": q,
                                 "charged_trials": 1, "bar_n": bar_n()})
        hits.append(entry)
    hits.sort(key=lambda e: str(e["certificate"]))
    n_minted = sum(1 for h in hits if h["rejudge"]["status"] == "MINTED")
    n_linked = sum(1 for h in hits if h["rejudge"]["status"] == "LINKED")
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "ruling": ("judge 2026-10-20: identity names a factor the certifier never had -> "
                   "BASKET_MISMATCH, never promotes, clock runs as UNMEASURED_BASKET_MISMATCH; "
                   "the true basket is re-judged (linked or minted once at the fixed N bar)"),
        "rule": {"families": sorted(BASKET_FAMILIES),
                 "certified_before": PARTIAL_BASKET_FIXED_AT.isoformat(),
                 "fix_commit": "ef11ff615",
                 "no_bars_evidence": ["registry intraday_coverage", "registry trade_mode",
                                      "registry tradeable", CLOSE_ONLY.name]},
        "n_hits": len(hits), "n_linked": n_linked, "n_minted": n_minted,
        "bar_n": bar_n(),
        "keys": sorted(str(h["key"]) for h in hits if h.get("key")),
        "certificates": [h["certificate"] for h in hits],
        "hits": hits, "notes": notes,
    }


def pit_series_ready(columns: list[str], root: Path | None = None) -> tuple[bool, str]:
    """Is `fred_ust` on this host WITH its point-in-time clock? (ready, why)

    Present means: the series file reads, every column the re-mint names is in it, and every row
    carries an `available_time` stamp that is AFTER its `event_time` -- the futures_state clock,
    not a calendar-day join. Anything less is a named pending follow-up and mints nothing.
    """
    from mt5desk.family_exogenous_conditioner import _load, series_path
    path = series_path(PIT_SERIES, root or PIT_SERIES_DIR)
    if path is None:
        return False, f"{PENDING}: no {PIT_SERIES} series under {(root or PIT_SERIES_DIR).name}/"
    df = _load(path)
    if df is None or df.empty:
        return False, f"{PENDING}: {path.name} is unreadable or empty"
    gone = [c for c in columns if c not in df.columns]
    if gone:
        return False, f"{PENDING}: {path.name} carries no {gone}"
    if "available_time" not in df.columns:
        return False, f"{PENDING}: {path.name} has no available_time (no PIT clock)"
    avail = pd.to_datetime(df["available_time"], errors="coerce", utc=True)
    if avail.isna().any():
        return False, f"{PENDING}: {int(avail.isna().sum())} row(s) carry no available_time"
    if "event_time" in df.columns:
        ev = pd.to_datetime(df["event_time"], errors="coerce", utc=True)
        if not (avail > ev).all():
            return False, (f"{PENDING}: available_time is not after event_time on every row -- "
                           f"a calendar-day join, not the futures_state PIT clock")
    return True, f"{path.name}: {len(df)} PIT-stamped row(s), last available {avail.max()}"


GAUNTLET = DESK / "scripts" / "external_gauntlet.py"


def gauntlet_reads_pit(path: Path = GAUNTLET) -> bool:
    """Does the (sealed) judge build a `<series>:<column>` factor? Until it does, a minted PIT
    cell would fail its build as an incomplete basket and spend its one trial on nothing."""
    try:
        return "is_pit_factor" in path.read_text(encoding="utf-8")
    except OSError:
        return False


def pit_remint(doc: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    """NEW cells for each mismatch whose missing factor has a PIT rates leg, gated on the series.

    The old certificates and clocks are never touched (they stay BASKET_MISMATCH); the new cell
    names the series in its identity, so it is a different cell, judged at the fixed N bar.
    """
    from research.frontier_identity import cell_id
    want = [h for h in doc.get("hits") or []
            if any(m["factor"] in PIT_RATES_LEG for m in h.get("missing_factors") or [])
            and h.get("params")]
    cols = sorted({PIT_RATES_LEG[m["factor"]].split(":", 1)[1] for h in want
                   for m in h["missing_factors"] if m["factor"] in PIT_RATES_LEG})
    if not want:
        return {"status": "NOTHING_TO_REMINT", "minted": 0, "rows": []}
    ready, why = pit_series_ready(cols, root)
    if not ready:
        return {"status": PENDING, "why": why, "minted": 0, "candidates": len(want),
                "follow_up": (f"when {PIT_SERIES} lands (futures_state), this leg mints "
                              f"{len(want)} new cell(s) with the rates leg on it"), "rows": []}
    if not gauntlet_reads_pit():
        return {"status": "PENDING_SEALED:external_gauntlet_pit_factor", "why": why,
                "minted": 0, "candidates": len(want),
                "follow_up": ("the series is present but scripts/external_gauntlet.py (sealed) "
                              "does not yet build a <series>:<column> factor; land the reported "
                              "patch, then this leg mints"), "rows": []}
    rows: dict[str, dict[str, Any]] = {}
    for h in want:
        basket = [PIT_RATES_LEG.get(f, f) for f in h["named_basket"]]
        q = dict(h["params"], factor_symbols=basket)
        cell = cell_id({"sym": h["symbol"], "family": h["family"], "params": q})
        h["pit_remint_cell"] = cell
        rows.setdefault(cell, {
            "symbol": h["symbol"], "family": h["family"], "params": q, "source": PIT_SOURCE,
            "mechanism_status": "NAMED",
            "mechanism_note": (f"{h['certificate']} re-minted as a NEW cell with its rates leg "
                               f"on the PIT series {PIT_SERIES} ({basket}); the original stays "
                               f"BASKET_MISMATCH and is never swapped in place"),
            "lineage": {"certificate": h["certificate"], "ruling": VERDICT,
                        "pit_series": PIT_SERIES},
            "trial_charge": {"bar_n": bar_n(), "charged_trials": 1, "once": True},
        })
    return {"status": "MINTED", "why": why, "minted": len(rows), "cells": sorted(rows),
            "rows": list(rows.values())}


def rejudge_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """The minted true-identity cells, in the docket's row shape (one per distinct cell)."""
    rows: dict[str, dict[str, Any]] = {}
    for h in doc.get("hits") or []:
        rj = h.get("rejudge") or {}
        if rj.get("status") != "MINTED" or rj["cell"] in rows:
            continue
        rows[rj["cell"]] = {
            "symbol": h["symbol"], "family": h["family"], "params": rj["params"],
            "source": SOURCE, "mechanism_status": "NAMED",
            "mechanism_note": (f"re-judge of {h['certificate']} under its true basket "
                               f"{h['true_basket']} (BASKET_MISMATCH: "
                               f"{', '.join(m['factor'] for m in h['missing_factors'])} had no "
                               f"{h['timeframe']} bars when it was certified)"),
            "lineage": {"certificate": h["certificate"], "ruling": VERDICT},
            "trial_charge": {"bar_n": rj["bar_n"], "charged_trials": 1, "once": True},
        }
    return list(rows.values())


def emit_once(rows: list[dict[str, Any]], ledger_path: Path = MINTED_LEDGER,
              now: str | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The rows never emitted before (charged now), and the updated ledger."""
    from research.frontier_identity import cell_id
    ledger = _read(ledger_path, {}) or {}
    got = ledger.get("cells")
    cells: dict[str, Any] = got if isinstance(got, dict) else {}
    stamp = now or datetime.now(UTC).isoformat(timespec="seconds")
    fresh = []
    for r in rows:
        cell = cell_id({"sym": r["symbol"], "family": r["family"], "params": r["params"]})
        if cell in cells:
            continue
        cells[cell] = {"minted_at": stamp, "certificate": r["lineage"]["certificate"]}
        fresh.append(r)
    return fresh, {"what": "true-identity cells handed to the docket by basket_mismatch; each "
                           "is charged once and never re-emitted", "cells": cells}


def retire_sleeves(doc: dict[str, Any], path: Path = SLEEVES,
                   apply: bool = False) -> list[dict[str, Any]]:
    """LIVE/STANDBY sleeves on a mismatch certificate, retired (on --apply) with the ruling."""
    certs = set(doc.get("certificates") or [])
    roster = _read(path, {}) or {}
    rows = roster.get("sleeves") if isinstance(roster, dict) else None
    if not isinstance(rows, list):
        return []
    out = []
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    for r in rows:
        cert = r.get("certificate") if isinstance(r, dict) else None
        cell = cert.get("cell") if isinstance(cert, dict) else None
        if cell not in certs or str(r.get("status") or "").upper() not in ("LIVE", "STANDBY"):
            continue
        out.append({"name": r.get("name"), "status": r.get("status"), "certificate": cell,
                    "risk_frac": r.get("risk_frac"),
                    "risk_frac_source": r.get("risk_frac_source")})
        if apply:
            r.update(status="RETIRED", risk_frac=0.0, risk_frac_source="none",
                     retired_at=stamp, retired_by="basket_mismatch",
                     retire_reason=(f"{VERDICT}: certificate {cell} names a factor the "
                                    f"certifier never had (judge ruling 2026-10-20); it can "
                                    f"never promote. The true basket is re-judged separately."))
    if apply and out:
        _atomic(path, roster)
    return out


GATE = "basket_mismatch"
UNMEASURED_EVIDENCE = "UNMEASURED"


def missed_growth_lines(retired: list[dict[str, Any]], doc: dict[str, Any], stamp: str,
                        previous: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """One missed-growth line per sleeve this gate moved LIVE/STANDBY -> RETIRED (a veto).

    GROWTH GOVERNANCE, Rule 1: every veto carries its bill. The forward evidence for a
    USDX+UST10Y identity is UNMEASURED BY CONSTRUCTION -- the certifier never had the named
    basket, so no forward reading can be evidence for it -- and the line says so rather than
    pricing the veto at zero. Lines are cumulative: a retirement fires once, so earlier lines
    are carried forward from the previous report, keyed by sleeve.
    """
    hits = {str(h.get("certificate")): h for h in doc.get("hits") or []}
    lines = {str(x.get("sleeve")): x for x in previous or []
             if isinstance(x, dict) and x.get("gate") == GATE}
    for r in retired:
        h = hits.get(str(r.get("certificate"))) or {}
        missing = [m.get("factor") for m in h.get("missing_factors") or []]
        named = h.get("named_basket") or []
        why = (f"identity {named} names {missing}, which the certifier never had (no bars on "
               f"the certificate's chart before ef11ff615): no forward reading is evidence for "
               f"this identity, so the veto's cost in forward E[log W] is UNMEASURED by "
               f"construction, not zero")
        lines[str(r.get("name"))] = {
            "gate": GATE, "sleeve": r.get("name"), "certificate": r.get("certificate"),
            "from_status": r.get("status"), "risk_frac_before": r.get("risk_frac"),
            "risk_frac_source_before": r.get("risk_frac_source"),
            "forward_evidence": {"status": UNMEASURED_EVIDENCE, "why": why},
            "verdict": UNMEASURED_EVIDENCE, "value": None, "why": why,
            "true_basket_rejudge": (h.get("rejudge") or {}).get("status"),
            "at": stamp}
    return [lines[k] for k in sorted(lines)]



def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=str)
    os.replace(tmp, path)


def overlay(path: Path = OUT) -> dict[str, dict[str, Any]]:
    """certificate name -> its hit row, for readers (clock law). Empty when absent."""
    doc = _read(path, {}) or {}
    return {str(h.get("certificate")): h for h in doc.get("hits") or [] if isinstance(h, dict)}


def clock_overlay(path: Path = OUT) -> dict[str, dict[str, Any]]:
    """clock key -> its hit row, for the forward engine. Empty when absent."""
    doc = _read(path, {}) or {}
    return {str(h.get("key")): h for h in doc.get("hits") or []
            if isinstance(h, dict) and h.get("key")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--apply", action="store_true",
                    help="retire LIVE/STANDBY sleeves on mismatch certificates")
    a = ap.parse_args(argv)
    doc = detect()
    remint = pit_remint(doc)
    rows = rejudge_rows(doc) + remint.pop("rows")
    doc["pit_remint"] = remint
    fresh, ledger = emit_once(rows, now=doc["at"])
    doc["minted_cells"] = sorted(ledger["cells"])
    doc["emitted_this_run"] = len(fresh)
    previous = (_read(OUT, {}) or {}).get("missed_growth")
    doc["sleeves_live_or_standby"] = retire_sleeves(doc, apply=a.apply)
    doc["sleeves_retired"] = bool(a.apply and doc["sleeves_live_or_standby"])
    doc["missed_growth"] = missed_growth_lines(
        doc["sleeves_live_or_standby"] if a.apply else [], doc, doc["at"],
        previous if isinstance(previous, list) else None)
    doc["n_missed_growth_lines"] = len(doc["missed_growth"])
    _atomic(OUT, doc)
    _atomic(REJUDGE, {"generated_at": doc["at"], "source": SOURCE, "hypotheses": fresh})
    _atomic(MINTED_LEDGER, ledger)
    print(f"BASKET_MISMATCH: {doc['n_hits']} certificate(s); re-judge linked {doc['n_linked']}, "
          f"minted {doc['n_minted']} ({len(rows)} distinct cell(s), {len(fresh)} emitted now); "
          f"PIT re-mint {remint['status']} ({remint['minted']}); missed-growth lines "
          f"{doc['n_missed_growth_lines']}; LIVE/STANDBY sleeves "
          f"{len(doc['sleeves_live_or_standby'])}"
          + (" -> RETIRED" if doc["sleeves_retired"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
