"""Per-symbol Binance funding-rate clamps -- the ceiling a CENSORED print is pinned against (R0293).

WHY THIS EXISTS. Binance clamps every funding print at a per-symbol minFundingRate/maxFundingRate.
A print sitting AT its clamp is CENSORED data: the venue is saying "at least this much", not "this
much", so reading it as a true extreme is a measurement error, not an edge (recommendation_ledger
R0293). `scripts/collect_tail_funding_divergence.py` studies the thin tail -- precisely the cohort
that pins -- so it needs the clamp for every symbol to label saturated observations instead of
recording them as extremes.

WHERE THE TRUTH LIVES. `GET /fapi/v1/fundingInfo` (keyless) lists every symbol whose cap/floor is
ADJUSTED away from the default -- fields `adjustedFundingRateCap` / `adjustedFundingRateFloor`.
Symbols absent from that list run at the venue default tier. `premiumIndex` carries the clamped
print itself but NOT the clamp, so fundingInfo is the one extra keyless call this module makes.

WHAT THIS BOX CAN SEE (measured 2026-08-04, browser UA via libs/data/venue_http, agent proxy):

    fapi.binance.com/fapi/v1/fundingInfo        -> HTTP 451 (geo-block; UA-independent)
    www.binance.com  + www.binance.info mirrors -> HTTP 451 (same block, same CDN)
    data-api.binance.vision                     -> HTTP 404 (spot-only host, no /fapi routes)

So from THIS container the live fetch deterministically fails, and that is honest: the code path
below still tries every mirror on each refresh (the 451 is a fact about the box, not the code),
then falls back to the newest cached fetch, then to the STATIC tier table. The VPS, where fapi
answers, runs the same `get_caps(refresh=True)` daily via the tail-funding collector -- that IS the
refresh mechanism: every collector run on a box that can reach Binance rewrites the cache with
venue truth, and boxes that cannot reach it inherit that cache via the repo's data/ tree.

THE STATIC TABLE IS A SEED, NOT VENUE TRUTH. It encodes the documented tier STRUCTURE -- majors at
+/-0.75%, the common tier at +/-1.0%, with a wider (+/-2.0% and up) tier that exists ONLY as the
fundingInfo adjustment list, which cannot be known statically. That is exactly why the refresh
exists. Using the static default errs on the side of a LOWER clamp for adjusted symbols, which can
only over-label censoring, never under-label it -- the conservative direction for a screen whose
failure mode is trusting a saturated print.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.data.venue_http import get_json

_ROOT = Path(__file__).resolve().parents[2]

#: Cache written on every successful live fetch; read wherever the live fetch is blocked.
CACHE_PATH = _ROOT / "data/funding_caps.json"

#: fundingInfo mirrors, tried in order. All 451 from this container (2026-08-04) -- kept anyway
#: because the block is per-box, and the VPS resolves the SAME list.
FUNDING_INFO_MIRRORS = (
    "https://fapi.binance.com/fapi/v1/fundingInfo",
    "https://www.binance.com/fapi/v1/fundingInfo",
    "https://www.binance.info/fapi/v1/fundingInfo",
)

#: Documented default tiers (see module docstring: seed, not venue truth).
DEFAULT_CAP_MAJOR = 0.0075       # +/-0.75% per interval -- BTC/ETH tier
DEFAULT_CAP_OTHER = 0.01         # +/-1.00% per interval -- the common tier
MAJORS = frozenset({"BTCUSDT", "ETHUSDT"})


@dataclass(frozen=True)
class FundingCaps:
    """Per-symbol funding clamps with tiered defaults for symbols the source did not enumerate.

    ``caps`` maps symbol -> (cap, floor) as SIGNED per-interval fractions (cap > 0 > floor), i.e.
    the ADJUSTED symbols from fundingInfo. Everything else falls to the tier defaults.
    """

    source: str                                  # "live:<url>" | "cache:<path>" | "static-defaults"
    fetched_at: str | None                       # ISO ts of the underlying live fetch, None=static
    caps: Mapping[str, tuple[float, float]] = field(default_factory=dict)

    def clamp_for(self, symbol: str, rate: float = 1.0) -> float:
        """The ABSOLUTE clamp binding a print of this sign: cap for rate>=0, |floor| for rate<0.

        Sidedness matters because fundingInfo caps can be asymmetric; a +0.9% print on a symbol
        clamped at [+1.0%, -2.0%] is 90% of the way to ITS wall, not 45%.
        """
        pair = self.caps.get(symbol)
        if pair is not None:
            cap, floor = pair
            return abs(cap) if rate >= 0 else abs(floor)
        return DEFAULT_CAP_MAJOR if symbol in MAJORS else DEFAULT_CAP_OTHER


def _parse_funding_info(payload: Any) -> dict[str, tuple[float, float]]:
    """fundingInfo rows -> {symbol: (cap, floor)}; malformed rows are skipped, not fatal."""
    out: dict[str, tuple[float, float]] = {}
    for row in payload if isinstance(payload, list) else []:
        if not isinstance(row, dict):
            continue
        try:
            sym = str(row["symbol"])
            cap = float(row["adjustedFundingRateCap"])
            floor = float(row["adjustedFundingRateFloor"])
        except (KeyError, TypeError, ValueError):
            continue
        out[sym] = (cap, floor)
    return out


def fetch_live_caps(get: Callable[[str], Any] | None = None) -> FundingCaps:
    """One keyless fundingInfo fetch, first mirror that answers. Raises if all refuse.

    The raise carries every mirror's verdict so a 451-blocked box records WHY it fell back
    instead of a bare failure -- the venue_http lesson about preserving wrong diagnoses.
    """
    fetch = get or (lambda url: get_json(url, tries=1, timeout=20))
    errors: list[str] = []
    for url in FUNDING_INFO_MIRRORS:
        try:
            payload = fetch(url)
        except Exception as exc:                              # verdict recorded, not swallowed
            errors.append(f"{url} :: {type(exc).__name__}: {str(exc)[:120]}")
            continue
        return FundingCaps(source=f"live:{url}",
                           fetched_at=datetime.now(tz=UTC).isoformat(),
                           caps=_parse_funding_info(payload))
    raise RuntimeError("no fundingInfo mirror reachable from this box -- "
                       + " | ".join(errors))


def _write_cache(caps: FundingCaps, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "fetched_at": caps.fetched_at,
        "source": caps.source,
        "caps": {s: [c, f] for s, (c, f) in caps.caps.items()},
        "note": ("per-symbol ADJUSTED Binance funding clamps from /fapi/v1/fundingInfo; symbols "
                 "absent here run the default tier (see libs/data/funding_caps.py, R0293)"),
    }, indent=1) + "\n", encoding="utf-8")


def load_cached_caps(path: Path = CACHE_PATH) -> FundingCaps | None:
    """The newest successful live fetch, or None. Unreadable cache is None, never a crash --
    the static tier table below is always available as the floor."""
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        caps = {str(s): (float(p[0]), float(p[1])) for s, p in dict(d["caps"]).items()}
        return FundingCaps(source=f"cache:{path.name}", fetched_at=d.get("fetched_at"), caps=caps)
    except Exception:
        return None


def get_caps(*, refresh: bool = True, cache_path: Path = CACHE_PATH,
             get: Callable[[str], Any] | None = None) -> FundingCaps:
    """Best available clamps: live (writes cache) -> cached -> static tier defaults.

    ``refresh=True`` is the refresh-on-VPS mechanism: callers that run daily on the VPS (the
    tail-funding collector) re-fetch venue truth every run; on a geo-blocked box the same call
    degrades in order, honestly labelled via ``.source``.
    """
    if refresh:
        try:
            live = fetch_live_caps(get)
        except Exception:
            pass                          # per-mirror verdicts already in the exception; degrade
        else:
            _write_cache(live, cache_path)
            return live
    cached = load_cached_caps(cache_path)
    if cached is not None:
        return cached
    return FundingCaps(source="static-defaults", fetched_at=None)


if __name__ == "__main__":                                    # manual refresh entry point
    got = get_caps(refresh=True)
    print(f"[funding-caps] source={got.source} adjusted_symbols={len(got.caps)} "
          f"fetched_at={got.fetched_at or 'n/a (static tier table)'}")
