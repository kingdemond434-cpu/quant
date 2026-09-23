"""THE ALPHA REPLENISHMENT TARGET (Tier-5 mandate 134): decay-rate-driven required survivors per
week against what the factory achieved, published hourly.

The mandate's number is new alpha value minus decayed/retired alpha value, with a positive net
as the target. This organ derives the REQUIRED arrival rate from the live book's own measured
decay and compares it with the ACHIEVED rate from the desk's ledgers:

    required/week = n_live x (1 - exp(-7 / half_life_days))      half-life from POSTERIOR_ALPHA
                    (decay_p per sleeve; UNMEASURED sleeves contribute no half-life, and a book
                    whose decay is entirely unmeasured has an UNMEASURED target, not a zero one)
    achieved/week = certificates gated in the last 7d (UNIVERSAL_SURVIVORS gated_at)
                  + sleeves promoted LIVE in the last 7d (sleeves.json promoted_at)
    retired/week  = decay_live actions_taken in the last 7d
    net           = promoted - retired;  gap = required - promoted

`research_auction` reads `gap`: a positive gap raises the discovery and validate bids, which is
the replenishment target reaching compute rather than sitting in a report. Nothing here sizes,
retires or caps anything.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "ALPHA_REPLENISHMENT.json"
POSTERIOR = BASE / "reports" / "POSTERIOR_ALPHA.json"
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
SLEEVES = BASE / "data" / "sleeves.json"
DECAY = BASE / "data" / "decay_live.json"
WINDOW_DAYS = 7.0


def _lst(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _dct(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _ts(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except ValueError:
        return None


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def half_lives(posterior: dict[str, Any]) -> tuple[list[float], int]:
    """Half-life in days per sleeve from the posterior's decay reading. Accepts `half_life_days`,
    `decay_lambda` (per day) or `decay_p` (per-trade survival -> per-day with `n` over `days`
    when both present). Returns (half_lives, n_unmeasured)."""
    rows = _lst(posterior.get("sleeves"))
    out: list[float] = []
    unmeasured = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        hl = _num(r.get("half_life_days"))
        if hl is None:
            lam = _num(r.get("decay_lambda"))
            if lam is not None and lam > 0:
                hl = math.log(2.0) / lam
        if hl is None:
            p = _num(r.get("decay_p"))
            if p is not None and 0.0 < p < 1.0:
                hl = math.log(2.0) / -math.log(p)   # per-trade hazard read as per-day
        if hl is None or hl <= 0:
            unmeasured += 1
        else:
            out.append(hl)
    return out, unmeasured


def _recent(stamps: list[Any], now: datetime, days: float = WINDOW_DAYS) -> int:
    cut = now - timedelta(days=days)
    n = 0
    for s in stamps:
        d = _ts(s)
        if d is not None and d >= cut:
            n += 1
    return n


def build(now: datetime | None = None, posterior: dict[str, Any] | None = None,
          survivors: dict[str, Any] | None = None, sleeves: dict[str, Any] | None = None,
          decay: dict[str, Any] | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    posterior = posterior if posterior is not None else _read(POSTERIOR)
    survivors = survivors if survivors is not None else _read(SURVIVORS)
    sleeves = sleeves if sleeves is not None else _read(SLEEVES)
    decay = decay if decay is not None else _read(DECAY)
    rows = _lst(sleeves.get("sleeves"))
    live = [r for r in rows if isinstance(r, dict) and str(r.get("status")) == "LIVE"]
    hls, hl_unmeasured = half_lives(posterior)
    sv = survivors.get("survivors")
    items = list(sv.values()) if isinstance(sv, dict) else (sv if isinstance(sv, list) else [])
    certified_7d = _recent([s.get("gated_at") for s in items if isinstance(s, dict)], now)
    promoted_7d = _recent([r.get("promoted_at") for r in live], now)
    actions = _lst(decay.get("actions_taken"))
    retired_7d = _recent([a.get("at") or a.get("time") for a in actions if isinstance(a, dict)],
                         now) if actions else 0
    required: float | None = None
    median_hl: float | None = None
    if hls:
        median_hl = statistics.median(hls)
        required = len(live) * (1.0 - math.exp(-WINDOW_DAYS / median_hl))
    net = promoted_7d - retired_7d
    gap = (required - promoted_7d) if required is not None else None
    status = ("UNMEASURED" if required is None else
              ("MET" if promoted_7d >= required else "SHORT"))
    doc: dict[str, Any] = {
        "at": now.isoformat(timespec="seconds"), "window_days": WINDOW_DAYS,
        "n_live": len(live),
        "n_forward": len([r for r in rows if isinstance(r, dict)
                          and str(r.get("status")) == "STANDBY"]),
        "decay": {"n_half_lives": len(hls), "n_unmeasured": hl_unmeasured,
                  "median_half_life_days": round(median_hl, 2) if median_hl else None},
        "required_per_week": round(required, 3) if required is not None else None,
        "achieved": {"certified_7d": certified_7d, "promoted_live_7d": promoted_7d,
                     "retired_7d": retired_7d, "net_replenishment": net},
        "gap": round(gap, 3) if gap is not None else None,
        "status": status,
        "consumer": "research_auction (gap raises discovery/validate bids), research_dashboard",
        "rule": ("required arrivals follow the live book's measured decay; a book whose decay is "
                 "unmeasured has an UNMEASURED target, and the achieved side is reported either "
                 "way; nothing here retires, caps or sizes"),
    }
    doc["headline"] = (f"{status}: required {doc['required_per_week']}/wk vs promoted "
                       f"{promoted_7d}, certified {certified_7d}, retired {retired_7d} "
                       f"(net {net:+d}); half-life from {len(hls)} sleeve(s), "
                       f"{hl_unmeasured} unmeasured")
    return doc


def publish(doc: dict[str, Any], out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        from libs.moat import registry
        registry.kpi(doc["at"][:10], "alpha_replenishment_net",
                     float(doc["achieved"]["net_replenishment"]),
                     {"gap": doc.get("gap"), "status": doc.get("status")})
    except Exception as exc:
        doc.setdefault("unmeasured", []).append(f"registry kpi not written: {exc}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    doc = build()
    doc["elapsed_s"] = round(time.monotonic() - t0, 3)
    doc["budget_s"] = a.budget_s
    publish(doc, a.out)
    print(f"alpha replenishment: {doc['headline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
