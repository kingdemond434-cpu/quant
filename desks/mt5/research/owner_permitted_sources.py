"""Collector for the seven owner-attested sources (2026-11-17), one hourly pass.

The owner attested that seven publishers granted automated use (governance/
owner-permission-attestation-2026-11-17.md): HKEX Stock Connect, BoJ ETF holdings, Korea NPS,
BoJ JGB operations, SNB sight deposits, the Chicago Fed NFCI/ANFCI (chicagofed.org only, never
FRED), and the Cboe delayed SPX option chain (options OI/gamma). Each has its own flag in
``data/owner_permissions.json``; this organ consults ``libs.data.owner_permissions`` for every
request, so flipping a flag to false re-fences that source on the next pass with its
missed_growth line, and an unreadable file fences all seven.

WHAT A PASS DOES, per source:
  * refused (flag false, no row, unreadable file, hard-refused host): no request; the row in the
    report carries ``BLOCKED_ON_TERMS`` and the source's missed_growth line.
  * permitted: robots.txt read FAILING CLOSED, then one honest GET per endpoint, no retry;
    401/403/429/451 is a hard stop. The raw bytes land under ``data/owner_permitted/<id>/``
    (repo root ``data/`` is gitignored: publisher bytes never enter the public repo) with a
    ``.meta.json`` sidecar carrying ``permission=owner_attestation_2026-11-17``.
  * 401/403/429/451 HOLDS the source for 24h (``libs.data.owner_permissions.HOLDS``, gitignored
    ``data/``): while held it is skipped (status HELD) with its missed_growth line and nothing
    is requested.
  * the Cboe chain is also reduced to one dealer-gamma observation appended to
    ``data/owner_permitted/cboe_options/cboe_spx_options.jsonl`` (GITIGNORED: Cboe-derived rows
    never reach the public repo; the file GammaExposureAdapter and shadow_institutional's
    ``cboe_delayed_surface`` read), stamped with the same provenance.
    Parsing the other six is downstream (status NEEDS_PARSER, said, never hidden).

ARTIFACT: ``reports/owner_permitted_sources.json`` -- metadata only, every row stamped.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
REPO = BASE.parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from libs.data import owner_permissions as op  # noqa: E402

REPORT = BASE / "reports" / "owner_permitted_sources.json"
RAW = REPO / "data" / "owner_permitted"
GEX_FILE = op.CBOE_GEX_FILE
GEX_SOURCE = "exchange_options_gamma"
#: The seven the attestation names. A row deleted from the file still shows here, refused.
ATTESTED: tuple[str, ...] = ("hkex_stock_connect", "boj_etf_purchases", "korea_nps_flows",
                             "boj_jgb_operations", "snb_sight_deposits", "chicagofed_nfci",
                             GEX_SOURCE)
_EXT = {"json": ".json", "csv": ".csv", "javascript": ".js", "html": ".html", "xml": ".xml",
        "spreadsheetml": ".xlsx", "excel": ".xls", "pdf": ".pdf"}


def last_weekday(today: date | None = None) -> date:
    d = (today or datetime.now(UTC).date()) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def render(endpoint: str, today: date | None = None) -> str:
    d = last_weekday(today)
    return endpoint.replace("{yyyymmdd}", d.strftime("%Y%m%d"))


def _ext(ctype: str, url: str) -> str:
    low = (ctype or "").lower()
    for k, v in _EXT.items():
        if k in low:
            return v
    tail = url.rsplit("/", 1)[-1]
    return "." + tail.rsplit(".", 1)[-1][:5] if "." in tail else ".bin"


def store_raw(source: str, f: op.Fetched, root: Path = RAW) -> dict[str, Any]:
    """Raw bytes under their content hash (never overwritten) plus a provenance sidecar."""
    digest = hashlib.sha256(f.body).hexdigest()
    d = root / source
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{digest[:16]}{_ext(f.content_type, f.url)}"
    if not p.exists():
        p.write_bytes(f.body)
    meta = {**f.meta, **op.provenance(source), "url": f.url, "sha256": digest,
            "bytes": len(f.body), "content_type": f.content_type, "fetched_at": f.fetched_at}
    p.with_suffix(p.suffix + ".meta.json").write_text(json.dumps(meta, indent=1), "utf-8")
    return {"path": str(p), "sha256": digest, "bytes": len(f.body)}


def _gex_parser() -> Callable[[bytes, datetime], dict[str, Any]]:
    """The one GEX reduction the desk owns (scripts/fetch_free_observables.py)."""
    path = REPO / "scripts" / "fetch_free_observables.py"
    spec = importlib.util.spec_from_file_location("_fetch_free_observables", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.fetch_cboe_options  # type: ignore[no-any-return]


def append_gex(f: op.Fetched, out: Path = GEX_FILE) -> dict[str, Any]:
    """One dealer-gamma observation from the chain, stamped with the attestation."""
    row = _gex_parser()(f.body, datetime.now(UTC))
    row.update(op.provenance(GEX_SOURCE, url=f.url))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return {"observable": str(out), "net_gex": row.get("net_gex"),
            "contracts": row.get("contracts")}


def run(*, path: Path | None = None, transport: op.Transport | None = None,
        today: date | None = None, raw_root: Path = RAW, gex_file: Path = GEX_FILE,
        budget_s: float = 300.0, holds: Path | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    rows, why = op.load(path)
    ids = list(ATTESTED) + [i for i in rows if i not in ATTESTED]
    out: list[dict[str, Any]] = []
    for sid in ids:
        row = rows.get(sid) or {}
        refused = op.refusal(sid, None, path)
        rec: dict[str, Any] = {"source": sid, "name": row.get("name"),
                               "targets": row.get("targets") or [], **op.provenance(sid)}
        if refused:
            rec.update({"status": "BLOCKED_ON_TERMS", "why": refused,
                        "missed_growth": row.get("missed_growth") or
                        f"missed_growth: {sid} is UNMEASURED while it is refused"})
            rec.pop("permission", None)       # nothing was fetched under the attestation
            rec.pop("provenance", None)
            out.append(rec)
            continue
        fetches: list[dict[str, Any]] = []
        for ep in row.get("endpoints") or []:
            if time.monotonic() - t0 >= budget_s:
                fetches.append({"url": ep, "status": "budget", "why": "pass budget spent"})
                break
            url = render(str(ep), today)
            f = op.permitted_get(sid, url, transport=transport, path=path, holds=holds)
            one: dict[str, Any] = {"url": url, "status": f.status, "why": f.why,
                                   "http": f.http, "fetched_at": f.fetched_at}
            if f.ok:
                one.update(store_raw(sid, f, raw_root))
                if sid == GEX_SOURCE:
                    try:
                        one.update(append_gex(f, gex_file))
                    except Exception as exc:
                        one["parse"] = f"{type(exc).__name__}: {str(exc)[:120]}"
                one.update(op.provenance(sid))
            fetches.append(one)
            if f.status in ("hard_stop", "held") or (
                    f.status == "robots_refused" and f.http in op.HARD_STOP):
                break
        ok = any(x.get("status") == "ok" for x in fetches)
        rec.update({"status": ("FETCHED" if ok and sid == GEX_SOURCE else
                               "FETCHED_NEEDS_PARSER" if ok else
                               "HARD_STOP" if any(x.get("status") == "hard_stop"
                                                  for x in fetches) else
                               "HELD" if any(x.get("status") == "held" for x in fetches) else
                               "ROBOTS_REFUSED" if any(x.get("status") == "robots_refused"
                                                       for x in fetches) else
                               "UNREACHED"),
                    "fetches": fetches})
        if not ok:
            rec["missed_growth"] = row.get("missed_growth")
        out.append(rec)
    doc = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
           "basis": op.BASIS, "governance": op.GOVERNANCE, "permissions_file": why,
           "rule": ("each source fetches only while its owner_permissions row is enabled; "
                    "robots fails closed; 401/403/429/451 is a hard stop; hard-refused hosts "
                    "are never unlocked by a row"),
           "counts": {s: sum(1 for r in out if r["status"] == s)
                      for s in sorted({r["status"] for r in out})},
           "sources": out}
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the default)")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--dry-run", action="store_true", help="no network: report the gate only")
    a = ap.parse_args(argv)
    if a.dry_run:
        def _none(url: str, headers: Any, timeout: float) -> tuple[None, bytes, str, str, str]:
            return None, b"", url, "", "dry run: no network"
        doc = run(transport=_none, budget_s=a.budget_s)
    else:
        doc = run(budget_s=a.budget_s)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"owner_permitted_sources: {doc['counts']} -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
