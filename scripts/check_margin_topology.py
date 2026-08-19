#!/usr/bin/env python3
"""MARGIN-TOPOLOGY FENCE (L1.64) -- was the book's capital structure ever DECIDED?

The deployed sleeve runs long spot + separately-margined USDT-M short, a construction inherited
from connector order, never chosen. This fence builds one row per construction available on the
venue(s) the desk already trades (see ``libs/portfolio/margin_topology`` for the full argument),
prices the gap between the inherited construction and the best measured alternative (L1.51), and
grades the live construction:

  DECIDED        (exit 0) -- a decision row names the running construction, made against >=1
                             MEASURED alternative, and equity has not doubled since.
  DECIDED-STALE  (exit 2) -- decided, but equity >= 2x the decision's equity (L1.28c).
  DIVERGED       (exit 2) -- the decision names a construction the book does not run (L1.61).
  INHERITED      (exit 2) -- no decision row exists. THE FAILING STATE THIS FENCE WAS BUILT FOR.
  UNMEASURED     (exit 2) -- no rows, or a decision against zero measured alternatives (L1.28a).

THE REPAIR IS A DECISION, NEVER A SILENT SWITCH. This fence sizes nothing and flips no account
mode; the switch is a principal-grade act that restarts forward evidence (L2.10), and
KEEP-CURRENT is a fully legitimate verdict -- what is illegitimate is running a book on a
construction nobody compared. Write data/margin_topology_decision.json with
{construction, decided_at, decided_by, equity_at_decision_usd, evidence}.

    python scripts/check_margin_topology.py [--report-only] [--json]
    python scripts/check_margin_topology.py --collect   # refresh venue terms (network; weekly)
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.input_provenance import (  # noqa: E402
    ABSENT,
    DEFAULTED,
    READ,
    STALE,
    UNREADABLE,
    InputRecord,
    Inputs,
)
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.portfolio.margin_topology import (  # noqa: E402
    CURRENT_CONSTRUCTION,
    build_rows,
    grade,
    level_table,
    price_uplift,
)

_OUT = _ROOT / "data" / "margin_topology.json"
_TERMS = _ROOT / "data" / "margin_topology_terms.json"
_DECISION = _ROOT / "data" / "margin_topology_decision.json"
_NAV = _ROOT / "data" / "nav_attestation.jsonl"
_PLAN = _ROOT / "web" / "capital_plan.json"
_PASSING = frozenset({"DECIDED"})

#: venue terms change on venue policy cadence, not market cadence -- a week of tolerance, then
#: the dependent rows degrade to UNMEASURED rather than run on a stale collateral table.
_TERMS_MAX_AGE_H = 21 * 24.0

#: Keyless public endpoints tried by --collect. Every attempt is RECORDED, hit or miss (L1.60):
#: an endpoint that answered and one that never existed must stay distinguishable on disk.
_ENDPOINTS: dict[str, str] = {
    "usdtm_exchange_info": "https://fapi.binance.com/fapi/v1/exchangeInfo",
    "coinm_exchange_info": "https://dapi.binance.com/dapi/v1/exchangeInfo",
    # Multi-Assets collateral-ratio table: no confirmed keyless endpoint; both candidates are
    # tried so the artifact records the venue's answer rather than this desk's assumption.
    "multi_assets_rate_a": "https://fapi.binance.com/fapi/v1/multiAssetsMarginAssetRate",
    "multi_assets_rate_b": "https://www.binance.com/bapi/futures/v1/public/future/common/multi-assets-margin",
}


def _fetch(url: str, timeout: float = 15.0) -> tuple[Any, str]:
    """(parsed-or-None, status). Failures are data, not exceptions."""
    req = urllib.request.Request(url, headers={"User-Agent": "quant-desk-terms/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # https, fixed hosts only
            return json.loads(r.read().decode("utf-8")), f"200 ({url})"
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code} ({url})"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        return None, f"{type(e).__name__}: {e} ({url})"


def _perp_bases(doc: Any, quote: str | None) -> list[str] | None:
    """TRADING perpetual base assets from an exchangeInfo payload; None when unparseable."""
    if not isinstance(doc, dict) or not isinstance(doc.get("symbols"), list):
        return None
    out = set()
    for s in doc["symbols"]:
        if not isinstance(s, dict) or s.get("contractType") != "PERPETUAL":
            continue
        if s.get("status") not in (None, "TRADING"):
            continue
        if quote is not None and s.get("quoteAsset") != quote:
            continue
        base = s.get("baseAsset")
        if isinstance(base, str) and base:
            out.add(base)
    return sorted(out)


def collect() -> dict[str, Any]:
    """Refresh data/margin_topology_terms.json from keyless public endpoints.

    Unfetchable terms stay null WITH their recorded refusals -- the comparator then refuses the
    dependent rows (L1.28a) and names this collector as the next action. PM terms have no keyless
    endpoint and are left for a dated keyed/manual read; that gap is recorded, not papered over.
    """
    fetch_log: dict[str, str] = {}
    usdtm_doc, fetch_log["usdtm_exchange_info"] = _fetch(_ENDPOINTS["usdtm_exchange_info"])
    coinm_doc, fetch_log["coinm_exchange_info"] = _fetch(_ENDPOINTS["coinm_exchange_info"])

    ma_table: dict[str, float] | None = None
    for key in ("multi_assets_rate_a", "multi_assets_rate_b"):
        doc, fetch_log[key] = _fetch(_ENDPOINTS[key])
        rows = doc.get("data") if isinstance(doc, dict) else doc
        if isinstance(rows, list) and rows:
            parsed: dict[str, float] = {}
            for r in rows:
                if not isinstance(r, dict):
                    continue
                asset = r.get("asset") or r.get("assetName") or r.get("collateralAsset")
                rate = r.get("collateralRate") or r.get("collateralRatio") or r.get("rate")
                try:
                    if isinstance(asset, str) and asset and rate is not None:
                        parsed[asset] = float(rate)
                except (TypeError, ValueError):
                    continue
            if parsed:
                ma_table = parsed
                break

    # PM terms have no keyless endpoint, so a human-recorded value is carried forward across
    # collects. The carry-forward's failure modes are RECORDED, not swallowed (L1.60): an absent
    # previous table is a first collect; an unreadable one is a torn write to go look at.
    prev: dict[str, Any] = {}
    try:
        prev = json.loads(_TERMS.read_text("utf-8"))
    except FileNotFoundError:
        fetch_log["previous_terms"] = "ABSENT (first collect) -- no PM terms to carry forward"
    except (OSError, json.JSONDecodeError) as e:
        fetch_log["previous_terms"] = (f"UNREADABLE ({type(e).__name__}) -- PM terms NOT "
                                       "carried forward; inspect the file")

    now = datetime.now(UTC).isoformat()
    terms: dict[str, Any] = {
        "as_of": now,
        "generated_at": now,  # the stamp key the freshness zoo reads; as_of is the human one
        "method": "check_margin_topology --collect (keyless public endpoints; every attempt "
                  "recorded in fetch_log; null means REFUSED-TO-GUESS, not zero)",
        "usdtm_perp_bases": _perp_bases(usdtm_doc, quote="USDT"),
        "coinm_perp_bases": _perp_bases(coinm_doc, quote=None),
        "multi_assets_collateral": ma_table,
        # PM terms are a dated keyed/manual read; carried forward if a human recorded them.
        "pm_npe": prev.get("pm_npe"),
        "pm_min_equity_usd": prev.get("pm_min_equity_usd"),
        "pm_source": prev.get("pm_source"),
        "fetch_log": fetch_log,
    }
    _TERMS.parent.mkdir(parents=True, exist_ok=True)
    _TERMS.write_text(json.dumps(terms, indent=2) + "\n", "utf-8")
    n_got = sum(1 for k in ("usdtm_perp_bases", "coinm_perp_bases", "multi_assets_collateral")
                if terms[k])
    print(f"terms: {n_got}/3 keyless term groups fetched -> {_TERMS.name}")
    for k, v in fetch_log.items():
        print(f"  {k}: {v}")
    return terms


def _read_jsonl_tail(inp: Inputs, path: Path, *, max_age_h: float,
                     required: bool) -> dict[str, Any] | None:
    """Last row of a JSONL artifact, with the read recorded exactly as read_json records."""
    try:
        rel = str(path.relative_to(_ROOT))
    except ValueError:
        rel = str(path)
    try:
        lines = [ln for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except FileNotFoundError:
        inp.records.append(InputRecord(rel, ABSENT, required=required,
                                       detail="no such file -- has any producer ever run?"))
        return None
    except OSError as e:
        inp.records.append(InputRecord(rel, UNREADABLE, required=required, detail=repr(e)))
        return None
    if not lines:
        inp.records.append(InputRecord(rel, UNREADABLE, required=required, detail="empty file"))
        return None
    try:
        row = json.loads(lines[-1])
    except json.JSONDecodeError as e:
        inp.records.append(InputRecord(rel, UNREADABLE, required=required,
                                       detail=f"last row did not parse: {e!r}"))
        return None
    age_h: float | None = None
    ts = row.get("ts") if isinstance(row, dict) else None
    if isinstance(ts, str):
        try:
            age_h = (datetime.now(UTC)
                     - datetime.fromisoformat(ts)).total_seconds() / 3600.0
        except ValueError:
            age_h = None
    status = STALE if (age_h is not None and age_h > max_age_h) else READ
    inp.records.append(InputRecord(rel, status, age_h=age_h, max_age_h=max_age_h,
                                   required=required))
    return row if isinstance(row, dict) else None


def build() -> dict[str, Any]:
    inp = Inputs("check_margin_topology.build")

    # The terms table is what makes the ALTERNATIVES measurable, but its absence must degrade
    # those rows to UNMEASURED rather than unmeasure the whole verdict: the inherited
    # construction's row and the INHERITED grading stand on the executor's own constants, so
    # the fence needs zero network and zero terms to do its core job.
    terms_doc = inp.read_json(_TERMS, default=None, max_age_h=_TERMS_MAX_AGE_H, required=False)
    terms: dict[str, Any] | None = terms_doc if isinstance(terms_doc, dict) else None
    if terms is None:
        inp.records.append(InputRecord("data/margin_topology_terms.json", DEFAULTED,
                                       required=False,
                                       detail="no terms on disk -- alternatives graded "
                                              "UNMEASURED; run --collect"))
    else:
        # The authoritative staleness check reads the table's OWN dated stamp (`as_of`); the
        # generic zoo (`generated_at`) is a backstop. An unstamped collateral table is an
        # assumption wearing a measurement's clothes (L1.46) and is refused outright.
        age_h: float | None = None
        stamp = terms.get("as_of") or terms.get("generated_at")
        if isinstance(stamp, str):
            try:
                age_h = (datetime.now(UTC)
                         - datetime.fromisoformat(stamp)).total_seconds() / 3600.0
            except ValueError:
                age_h = None
        if age_h is None or age_h > _TERMS_MAX_AGE_H:
            why_stale = ("terms carry no parseable as_of stamp" if age_h is None else
                         f"terms are {age_h:.0f}h old, beyond {_TERMS_MAX_AGE_H:.0f}h")
            inp.records.append(InputRecord("data/margin_topology_terms.json", DEFAULTED,
                                           required=False,
                                           detail=f"{why_stale} -- a stale collateral table "
                                                  "must not mint MEASURED rows (L1.44)"))
            terms = None

    # The decision file's ABSENCE is the measured subject, not a provenance failure.
    decision = inp.read_json(_DECISION, default=None, required=False)

    nav = _read_jsonl_tail(inp, _NAV, max_age_h=72.0, required=False)
    equity_now: float | None = None
    equity_basis = "UNMEASURED"
    if nav:
        try:
            equity_now = float(nav.get("equity_marked"))
        except (TypeError, ValueError):
            equity_now = None
        mode = str(nav.get("mode", ""))
        curve_note = str(nav.get("_note", ""))
        if "PAPER" in mode.upper() or "MOLDED" in curve_note.upper():
            equity_basis = f"MOLDED-PAPER ({mode or 'mode unknown'})"
        elif equity_now is not None:
            equity_basis = f"nav_attestation ({mode or 'mode unknown'})"

    plan = inp.read_json(_PLAN, default=None, max_age_h=72.0, required=False)
    cagr_validated = 0.0
    cagr_if_validated = 0.0
    if isinstance(plan, dict):
        try:
            cagr_validated = float(plan.get("validated_cagr_used") or 0.0)
        except (TypeError, ValueError):
            cagr_validated = 0.0
        try:
            lev = float(plan.get("leverage") or 0.0)
            cagr_if_validated = round(min(0.04 * lev, 0.25), 3)  # the plan's own formula
        except (TypeError, ValueError):
            cagr_if_validated = 0.0
    else:
        inp.defaulted("web/capital_plan.json", "plan unread -- uplift priced at 0 CAGR rungs")

    rows = build_rows(terms if isinstance(terms, dict) else None)
    status, why = grade(rows, decision if isinstance(decision, dict) else None,
                        equity_now_usd=equity_now, equity_basis=equity_basis)
    uplift = price_uplift(rows, equity_usd=equity_now, equity_basis=equity_basis,
                          cagr_validated=cagr_validated, cagr_if_validated=cagr_if_validated)

    n_measured = sum(1 for r in rows if r.status == "MEASURED")
    n_unmeasured = sum(1 for r in rows if r.status == "UNMEASURED")
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "why": why,
        "current_construction": CURRENT_CONSTRUCTION,
        "n_constructions": len(rows),
        "n_measured": n_measured,
        "n_unmeasured": n_unmeasured,
        "equity_now_usd": equity_now,
        "equity_basis": equity_basis,
        "uplift": uplift,
        "levels": level_table(rows),
        "constructions": [r.as_dict() for r in rows],
        "decision": decision if isinstance(decision, dict) else None,
        "provenance": inp.block(),
        "provenance_status": inp.status(),
        "next_action": (
            "read data/margin_topology.json, then either write the decision row "
            "(KEEP-CURRENT is legitimate) or run --collect to measure the unmeasured "
            "alternatives first" if status != "DECIDED" else
            "re-grades automatically; re-decide on NAV doubling"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--collect", action="store_true",
                    help="refresh data/margin_topology_terms.json from keyless endpoints "
                         "(network; weekly cadence)")
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0")
    ap.add_argument("--json", action="store_true", help="print the artifact")
    args = ap.parse_args()

    if args.collect:
        collect()

    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"margin topology (L1.64): {rep['status']} -- {rep['n_measured']} measured / "
              f"{rep['n_unmeasured']} unmeasured of {rep['n_constructions']} constructions; "
              f"book runs {rep['current_construction']}")
        for r in rep["constructions"]:
            npe = "npe=?" if r["notional_per_equity"] is None else f"npe={r['notional_per_equity']}"
            cov = ("cov=?" if r["universe_coverage"] is None
                   else f"cov={r['universe_coverage']:.0%}")
            print(f"  {r['status']:<18} {r['key']}: {npe} {cov} funding={r['funding_book']}")
        best = (rep["uplift"].get("alternatives") or [{}])[0]
        if best.get("structural_multiplier"):
            print(f"  best alternative: {best['construction']} x{best['structural_multiplier']} "
                  f"({best['liq_direction']})")
        print(f"  why:  {rep['why']}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # L1.57: the construction roster is this fence's denominator -- a verdict over zero rows is
    # refused rather than published as health.
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_constructions"],
                      of="margin constructions", fence="check_margin_topology.py")


if __name__ == "__main__":
    raise SystemExit(main())
