"""DEEP FOREST, PROVED PER REGION -- what each regional forest actually produced, off the box.

Every regional forest (`libs/research/forests.REGIONAL_FORESTS`) is a 24/7 resident. Liveness
says nothing about whether it mines anything, and the evidence that it does -- the claims file,
the per-resident progress watermark, the forest's own run ledger -- lives only on the trading
box, so every reader off the box could only say UNMEASURED (principal 2026-11-18: judge every
job by production, never by liveness, per country, every pass).

This writes `desks/mt5/reports/DEEP_FOREST_REGIONS.json`, one row per regional forest:

  claims_total / claims_24h / claims_7d   deep-forest claims whose `region` is one of the
                                          forest's grounds (or, with no region, whose language
                                          is one of its languages)
  newest_claim_at                         the newest such claim's available/ingested time
  watermark_at / watermark_passes         the resident's progress watermark: written only when
                                          a pass COMPLETES
  last_run_at / last_run_new              the forest runner's newest ledger row and its new count
  verdict                                 PRODUCING (a claim or a completed pass in 24h),
                                          IDLE (evidence exists, none in 24h) or UNMEASURED
                                          (no evidence file on this host)

Counts and times only: no claim text, no URL, no path outside the repository. It streams the
claims file line by line so its memory is flat whatever the file's size.

    python ops/deep_forest_regions.py            # write the report
    python ops/deep_forest_regions.py --print    # and print one line per region
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
CLAIMS = DESK / "data" / "deep_forest_claims.jsonl"
RUNS = DESK / "data" / "forest_runs.jsonl"
WATERMARKS = DESK / "data" / "watermarks"
OUT = DESK / "reports" / "DEEP_FOREST_REGIONS.json"
TIME_KEYS = ("available_time", "ingested_time", "fetched_utc")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _parse(ts: Any) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def _jsonl(path: Path) -> Iterator[dict[str, Any]]:
    try:
        fh = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def _forests() -> list[Any]:
    from libs.research import forests as F
    return list(F.REGIONAL_FORESTS)


def _owner(forests: Iterable[Any]) -> tuple[dict[str, str], dict[str, str]]:
    """region code -> forest id, and language -> forest id (first owner wins)."""
    by_region: dict[str, str] = {}
    by_lang: dict[str, str] = {}
    for f in forests:
        for g in (*f.grounds, *f.countries):
            by_region.setdefault(str(g).lower(), f.id)
        for lang in f.languages:
            by_lang.setdefault(str(lang).lower(), f.id)
    return by_region, by_lang


def build(now: datetime | None = None, *, claims: Path = CLAIMS, runs: Path = RUNS,
          watermarks: Path = WATERMARKS) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    forests = _forests()
    by_region, by_lang = _owner(forests)
    rows: dict[str, dict[str, Any]] = {
        f.id: {"forest": f.id, "task": f.task, "claims_total": 0, "claims_24h": 0,
               "claims_7d": 0, "newest_claim_at": None, "watermark_at": None,
               "watermark_passes": None, "last_run_at": None, "last_run_new": None}
        for f in forests}
    newest: dict[str, datetime] = {}
    day, week = now - timedelta(days=1), now - timedelta(days=7)
    claims_seen = claims.exists()
    unowned = 0
    for row in _jsonl(claims):
        region = str(row.get("region") or "").lower()
        lang = str(row.get("language") or row.get("lang") or "").lower()
        fid = by_region.get(region) or (by_lang.get(lang) if not region else None)
        if fid is None:
            unowned += 1
            continue
        r = rows[fid]
        r["claims_total"] += 1
        at = next((d for d in (_parse(row.get(k)) for k in TIME_KEYS) if d), None)
        if at is None:
            continue
        if at >= day:
            r["claims_24h"] += 1
        if at >= week:
            r["claims_7d"] += 1
        if fid not in newest or at > newest[fid]:
            newest[fid] = at
    for fid, at in newest.items():
        rows[fid]["newest_claim_at"] = _iso(at)

    runs_seen = runs.exists()
    for row in _jsonl(runs):
        fid = str(row.get("forest") or "")
        if fid in rows:
            rows[fid]["last_run_at"] = row.get("at")
            rows[fid]["last_run_new"] = (row.get("totals") or {}).get("new")

    for fid, r in rows.items():
        try:
            wm = json.loads((watermarks / f"resident__dept_{fid}.json")
                            .read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if isinstance(wm, dict):
            r["watermark_at"] = wm.get("at") or wm.get("updated_at") or wm.get("ts")
            r["watermark_passes"] = wm.get("value")

    for r in rows.values():
        stamps = [_parse(r["newest_claim_at"]), _parse(r["watermark_at"]),
                  _parse(r["last_run_at"])]
        if not any(stamps) and not (claims_seen or runs_seen):
            r["verdict"] = "UNMEASURED"
        elif r["claims_24h"] or any(s and s >= day for s in stamps[1:]):
            r["verdict"] = "PRODUCING"
        else:
            r["verdict"] = "IDLE"
    counts: dict[str, int] = {}
    for r in rows.values():
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return {"at": _iso(now), "n_forests": len(rows), "verdicts": counts,
            "claims_file_present": claims_seen, "runs_ledger_present": runs_seen,
            "claims_unowned": unowned, "regions": list(rows.values()),
            "rule": ("PRODUCING needs a claim mined or a resident pass completed in the last 24h; "
                     "a live process with neither is IDLE, and no evidence file is UNMEASURED")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="per-region deep forest production")
    ap.add_argument("--print", action="store_true", dest="show")
    a = ap.parse_args(argv)
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(OUT)
    if a.show:
        for r in doc["regions"]:
            print(f"{r['forest']:14} {r['verdict']:10} claims 24h={r['claims_24h']} "
                  f"7d={r['claims_7d']} newest={r['newest_claim_at']} "
                  f"pass={r['watermark_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
