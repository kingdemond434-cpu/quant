"""U3 -- THE FUSED GLOBAL POSTERIOR, THE CONDITIONAL SLEEVE BOOK, AND WHAT EVERY LIVE TRADE
ACTUALLY PAID FOR.

`research/world_model.py` LANDED the 24/7 world model: forward log returns of the hypothesis
lane at 1h/4h/1d/5d from every point-in-time series the desk holds, with per-dataset credit and
a published residual. Its own measured gap, written into `reports/WORLD_MODEL.json`, names three
things it does not do:

    absent: the fused GLOBAL posterior over the named macro states, conditional SLEEVE
    distributions for the allocator, and counterfactual attribution of every live trade.

THIS ORGAN IS THOSE THREE, AND NOTHING ELSE.

(1) THE FUSED GLOBAL POSTERIOR over the fourteen states the principal named -- liquidity, rates,
    inflation, growth, China demand, industrial cycle, commodity supply, carry, funding stress,
    risk appetite, volatility, positioning, regional risk, event proximity. Each state is a
    probability that it is ELEVATED against its own history. Every source the desk already
    publishes is read, converted to a probability, and fused IN LOGIT SPACE weighted by its own
    precision:

        logit_mean = sum(l_i / sd_i^2) / sum(1 / sd_i^2)      sd = sqrt(1 / sum(1 / sd_i^2))

    A source that publishes its own band (a shadow latent's `sd`, MACRO_VIEW's confidence and
    freshness) carries it through the delta method; a source that publishes none says so in
    `sd_basis: "declared"` and is widened so it cannot outvote one that measured. A state NO
    source measures is UNMEASURED with the reason and what would measure it -- never 0.5 dressed
    as knowledge (L1.28a).

(2) CONDITIONAL SLEEVE DISTRIBUTIONS. For every sleeve on the roster (`data/sleeves.json`) and
    every forward sleeve with a ledger (`reports/shadow/ledger_*.json`), the sleeve's own trade
    history is bucketed by the value the conditioning state held AT ENTRY -- against that state's
    EXPANDING median, so the split is knowable at the time and not with today's median applied to
    2019. Per bucket: mean, sd, n, and the shrunk mean. THE SHRINKAGE IS MEASURED, NOT INVENTED:
    DerSimonian-Laird on the bucket means gives tau^2, and n0 = pooled within-bucket variance /
    tau^2 is the prior sample size the DATA implies. tau^2 = 0 means no between-bucket signal was
    measured, so the bucket is fully shrunk to the unconditional mean and says so. The E[log W]
    contribution is published as its GRADIENT (dE[log W]/df at f=0 = the mean R), because the
    level needs a risk fraction that only the allocator owns.

(3) COUNTERFACTUAL ATTRIBUTION OF EVERY CLOSED LIVE TRADE in `data/live_ledger.jsonl`. Realised R
    is decomposed into four terms that sum back to it exactly:

        R = unconditional + conditional + execution + residual

    `unconditional` is the sleeve's mean over its own trades STRICTLY BEFORE this one (no
    lookahead); `conditional` is the shrunk bucket mean minus that; `execution` is the modelled
    cost minus the realised one (commission and swap off the deal, entry slippage off
    `order_intents.jsonl` where the ticket joins, the model off `data/cost_surface.json` at the
    deal's own hour); `residual` is what is left, which is the part the desk cannot explain.
    Three counterfactuals are answered because three are measurable: the same rule in the
    OPPOSITE state bucket, the same rule at the MODELLED cost, and the trade NOT TAKEN (R = 0).

    The unexplained residual is routed to `residual_queue`'s producer contract. The queue reads
    `data/unknown_unknowns_queue.jsonl` and dispatches on `kind`; a realised cost that came in a
    multiple of the modelled one is a `cost_shock`, which is the slot that already exists and
    already means this. The full normalised set (built with `residual_queue.item` itself, so the
    shape and the stable id are the queue's own) is published in the artifact under
    `residual_rows` for the day a producer line is added to its plan. `residual_queue.py` is NOT
    edited by this organ.

IT ALLOCATES NOTHING AND CAPS NOTHING. Tier-1 row P1 -- routing the gold book through the
allocator's fraction -- is REFUSED by the principal's standing order that the desk never reduces
its aggressiveness, so nothing here is fed to a sizer, no veto is added, no shrink is applied to
capital, and `allocates_capital` is published false on every pass. The shrinkage in section (2)
is a shrinkage of an ESTIMATE toward its own unconditional mean, which is how a conditional mean
is estimated honestly; it is not a shrink of a position. This is evidence the allocator MAY read.

    python desks/mt5/research/counterfactual_attribution.py [--once] [--budget-s N] [--dry-run]
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
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

WORLD_MODEL = DESK / "reports" / "WORLD_MODEL.json"
MACRO_VIEW = DESK / "reports" / "MACRO_VIEW.json"
REGIME_ROUTER = DESK / "reports" / "REGIME_ROUTER.json"
STATE_VECTOR = DESK / "data" / "state_vector.json"
MACRO_STATE = DESK / "data" / "macro_state.json"
WORLD_STATE = DESK / "data" / "world_state.json"
AXES = DESK / "data" / "axes"
SLEEVES = DESK / "data" / "sleeves.json"
LIVE_LEDGER = DESK / "data" / "live_ledger.jsonl"
SHADOW = DESK / "reports" / "shadow"
COST_SURFACE = DESK / "data" / "cost_surface.json"
ORDER_INTENTS = DESK / "data" / "order_intents.jsonl"
EVENT_LEDGER = DESK / "data" / "macro" / "event_ledger.jsonl"
UNKNOWN_QUEUE = DESK / "data" / "unknown_unknowns_queue.jsonl"
OUT = DESK / "reports" / "COUNTERFACTUAL_ATTRIBUTION.json"

SOURCE = "counterfactual_attribution"
RULE = ("R = unconditional + conditional + execution + residual; the global posterior is fused "
        "in logit space by each source's own precision; UNMEASURED is a verdict, not 0.5")
BUDGET_S = 600.0

#: The fourteen states, in the principal's own order. A name here with no readable source is
#: UNMEASURED with the reason -- the list never shrinks to what happens to be measurable today.
STATE_NAMES = ("liquidity", "rates", "inflation", "growth", "china_demand", "industrial_cycle",
               "commodity_supply", "carry", "funding_stress", "risk_appetite", "volatility",
               "positioning", "regional_risk", "event_proximity")

#: What a source that publishes NO band is worth, in logit units. Not small: a z-score with no
#: stated sample size is one number from an unstated history, and giving it the same precision as
#: a latent that publishes a measured ensemble sd would let it outvote the thing that measured.
DECLARED_LOGIT_SD = 1.0
#: A categorical source ("risk: off") is real knowledge with no band at all, so it is widened
#: further. It moves the posterior; it cannot dominate it.
CATEGORICAL_LOGIT_SD = 1.6
#: The floor under a source's own published precision, so a source claiming a zero band cannot
#: take the whole weight. Stated, and reported per source as `sd_floor_bound`.
MIN_LOGIT_SD = 0.15
#: Probabilities are held off the ends: logit(0) is not a number and a source is never certain.
P_EPS = 1e-4

#: Trades a sleeve needs before its unconditional mean is a mean rather than an anecdote, and
#: trades a bucket needs before it is a bucket. Both are stated in the report.
MIN_SLEEVE_N = 6
MIN_BUCKET_N = 3
#: The prior trades a live deal needs before its unconditional term is MEASURED.
MIN_PRIOR_N = 3
#: Realised cost over modelled cost at or above this is a `cost_shock` in the residual queue's
#: own vocabulary. Below it, the excess is attribution, not an anomaly worth a queue row.
COST_SHOCK_MULTIPLE = 1.5
#: Published rows can never fall below this many, whatever the machine reports as free.
ROW_FLOOR = 2_000

#: The conditioning state used for the per-trade decomposition, DECLARED in advance and in this
#: order, so the bucket is never chosen by looking at which one flatters the answer.
PRIMARY_CONDITIONING = ("risk_appetite", "industrial_cycle", "positioning", "carry", "rates",
                        "regional_risk", "commodity_supply", "volatility")

#: What a categorical reading is worth as a probability. Declared, wide-banded, and argued with
#: here rather than reverse-engineered out of the call sites.
RISK_P = {"off": 0.25, "on": 0.75, "neutral": 0.5, "mid": 0.5}
LIQ_P = {"THIN": 0.2, "QUIET": 0.35, "NORMAL": 0.5, "NEWS": 0.6, "DEEP": 0.8, "OPEN": 0.65}
EVENT_P = {"PRE_EVENT": 0.85, "EVENT": 0.9, "POST_EVENT": 0.6, "PRICE_DISCOVERY": 0.35,
           "QUIET": 0.2}

#: state -> the sources that measure it. `invert` means a HIGH reading of the source is a LOW
#: reading of the state. Every entry says what it measures and where it stops.
SOURCES: dict[str, tuple[dict[str, Any], ...]] = {
    "liquidity": (
        {"kind": "axis_latent", "id": "shadow_usd_liquidity",
         "why": "the shadow USD liquidity latent: reserves, TGA, RRP, cross-currency basis"},
        {"kind": "state_vector", "path": "liquidity.state", "map": LIQ_P,
         "why": "the state vector's own liquidity phase off the broker tape"},
        {"kind": "macro_states", "id": "LIQUIDITY_STATE",
         "why": "the FRED macro state's liquidity composite"},
    ),
    "rates": (
        {"kind": "macro_series", "id": "DGS10", "why": "US 10y yield z against its own history"},
        {"kind": "macro_series", "id": "DFF", "why": "the effective fed funds rate z"},
        {"kind": "axis_rows", "file": "bis", "field": "base_rate",
         "why": "the BIS policy-rate panel: the cross-sectional mean policy rate, dated by its "
                "own knowable_at, so the level is global and not one country's"},
        {"kind": "axis_series", "file": "ecb", "series": "eur_aaa_10y",
         "why": "the euro-area AAA 10y, the desk's only non-US curve point with a history"},
    ),
    "inflation": (
        {"kind": "macro_series", "id": "CPIAUCSL", "why": "headline CPI z"},
        {"kind": "macro_series", "id": "CPILFESL", "why": "core CPI z"},
        {"kind": "macro_states", "id": "INFLATION_STATE",
         "why": "the FRED macro state's inflation composite"},
    ),
    "growth": (
        {"kind": "macro_series", "id": "INDPRO", "why": "industrial production z"},
        {"kind": "macro_series", "id": "PAYEMS", "why": "non-farm payrolls z"},
        {"kind": "macro_series", "id": "UNRATE", "invert": True,
         "why": "unemployment z, inverted: a high rate is low growth"},
        {"kind": "macro_states", "id": "GROWTH_STATE",
         "why": "the FRED macro state's growth composite"},
    ),
    "china_demand": (
        {"kind": "axis_latent", "id": "shadow_china_activity",
         "why": "the shadow China activity latent: customs, power, ports, PMI"},
    ),
    "industrial_cycle": (
        {"kind": "axis_latent", "id": "shadow_industrial_cycle",
         "why": "the shadow industrial-cycle latent"},
        {"kind": "macro_series", "id": "INDPRO",
         "why": "industrial production z -- the same print the growth state reads, declared "
                "twice on purpose: the two states genuinely share this observation"},
    ),
    "commodity_supply": (
        {"kind": "axis_rows", "file": "cot", "field": "comm_pct_oi",
         "symbols": ("CORN", "COTTON", "SOYBEAN", "SUGAR", "WHEAT", "XTIUSD", "XNGUSD",
                     "XCUUSD"),
         "why": "COMMERCIAL hedger positioning across grains, softs, energy and copper: the "
                "producer's hedge is the supply side's own print. It measures hedging pressure, "
                "NOT inventories -- the desk holds no inventory series"},
    ),
    "carry": (
        {"kind": "axis_rows", "file": "bis", "field": "carry_differential", "abs": True,
         "why": "the BIS panel's own base-minus-quote policy differential, mean absolute across "
                "every mapped pair: how much carry there is to earn anywhere"},
    ),
    "funding_stress": (
        {"kind": "rank", "id": "T10Y2Y", "invert": True,
         "why": "MACRO_VIEW's 10y-2y rank, inverted: a flat or inverted curve is funding stress"},
        {"kind": "macro_series", "id": "SOFR", "why": "SOFR z"},
        {"kind": "macro_series", "id": "T10Y2Y", "invert": True, "why": "the curve z, inverted"},
    ),
    "risk_appetite": (
        {"kind": "axis_latent", "id": "shadow_global_risk_appetite",
         "why": "the shadow global risk-appetite latent: cross-asset breadth, gold/equity, the "
                "JPY carry proxy"},
        {"kind": "rank", "id": "VIXCLS", "invert": True,
         "why": "MACRO_VIEW's VIX rank, inverted: high vol is low appetite"},
        {"kind": "router", "key": "risk", "map": RISK_P,
         "why": "the regime router's own risk state off US500"},
    ),
    "volatility": (
        {"kind": "rank", "id": "VIXCLS", "why": "MACRO_VIEW's VIX rank"},
        {"kind": "router", "key": "vol", "map": {"low": 0.2, "mid": 0.5, "high": 0.8},
         "why": "the regime router's realised-vol tercile off the pre-trade tape"},
    ),
    "positioning": (
        {"kind": "axis_rows", "file": "cot", "field": "net_pct_oi", "abs": True,
         "why": "CFTC non-commercial net as a share of open interest, mean absolute across "
                "every mapped market: how stretched speculative positioning is"},
        {"kind": "axis_latent", "id": "shadow_retail_crowding",
         "why": "the shadow retail-crowding latent"},
    ),
    "regional_risk": (
        {"kind": "axis_series", "file": "ecb", "series": "eur_aaa_10y",
         "why": "the euro-area AAA 10y against its own history. It measures the EA-vs-history "
                "rate level, which is ONE component of regional risk and not the whole of it: "
                "the desk holds no peripheral spread series"},
        {"kind": "macro_series", "id": "DGS10", "invert": True,
         "why": "the US 10y inverted, so the pair reads as EA-relative-to-US"},
    ),
    "event_proximity": (
        {"kind": "state_vector", "path": "event.phase", "map": EVENT_P,
         "why": "the state vector's own event phase off the calendar"},
        {"kind": "event_ledger", "hours": 48,
         "why": "rows in the macro event ledger inside 48 h of now, against the ledger's own "
                "daily history of how many land in a window that size"},
    ),
}

_NOT_A_SLEEVE = re.compile(r"^\s*\[")
_HASH_SUFFIX = re.compile(r"_p_[0-9a-f]+$")


# --------------------------------------------------------------------------------- plumbing
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _f(value: Any) -> float | None:
    """A finite float, or None. NaN and inf are absences, not measurements."""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if x == x and -math.inf < x < math.inf else None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _read_rows(path: Path, limit: int = 200_000) -> list[dict[str, Any]]:
    try:
        lines = path.read_text("utf-8-sig", "replace").splitlines()[:limit]
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        try:
            row = json.loads(line) if line.strip() else None
        except ValueError:
            row = None
        if isinstance(row, dict):
            out.append(row)
    return out


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _sd(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-min(x, 700.0)))
    e = math.exp(max(x, -700.0))
    return e / (1.0 + e)


def _logit(p: float) -> float:
    q = min(max(p, P_EPS), 1.0 - P_EPS)
    return math.log(q / (1.0 - q))


def _phi(z: float) -> float:
    """The standard normal CDF: the probability the state sits below this reading."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _npdf(z: float) -> float:
    return math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)


def _day(stamp: Any) -> str:
    """The UTC calendar day of any stamp the desk writes, or "" if it is not one."""
    s = str(stamp or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return ""


def _parse(stamp: Any) -> datetime | None:
    s = str(stamp or "").strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def row_cap() -> tuple[int, str]:
    """How many rows this pass may publish, DERIVED from the memory this machine reports free.

    Never sized off a machine's claimed RAM: the trading box and the build box differ by an order
    of magnitude and a floor written for one starves the other (CLAUDE.md, measured twice).
    """
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except Exception:
        return ROW_FLOOR, f"psutil absent; the published floor of {ROW_FLOOR} rows stands"
    try:
        avail = int(psutil.virtual_memory().available)
    except Exception:
        return ROW_FLOOR, f"psutil could not read free memory; floor {ROW_FLOOR} rows"
    cap = int(avail * 0.05 / 2048)
    return max(cap, ROW_FLOOR), (f"5% of {avail // (1024 * 1024)} MB free at 2 KB per published "
                                 f"row, floored at {ROW_FLOOR}")


# ------------------------------------------------------------------- sources -> probabilities
def _src(spec: dict[str, Any], name: str, *, p: float | None = None, logit_sd: float = 0.0,
         sd_basis: str = "declared", status: str = "MEASURED", why: str = "",
         n: int = 0, last_at: str = "") -> dict[str, Any]:
    row: dict[str, Any] = {"source": name, "status": status,
                           "why": why or str(spec.get("why") or ""), "n": n, "last_at": last_at}
    if p is None or status != "MEASURED":
        row["status"] = "UNMEASURED" if status == "MEASURED" else status
        return row
    if bool(spec.get("invert")):
        p = 1.0 - p
    sd = max(float(logit_sd), MIN_LOGIT_SD)
    row.update({"p": round(min(max(p, P_EPS), 1.0 - P_EPS), 6), "logit": round(_logit(p), 6),
                "logit_sd": round(sd, 6), "sd_basis": sd_basis,
                "sd_floor_bound": logit_sd < MIN_LOGIT_SD, "inverted": bool(spec.get("invert"))})
    return row


def _from_history(spec: dict[str, Any], name: str, hist: list[tuple[str, float]],
                  sd_last: float | None) -> dict[str, Any]:
    """A dated series -> P(the latest reading is above its own history), with a real band.

    The band is the source's OWN published uncertainty carried through the delta method:
    z = (v - mu) / sigma, p = Phi(z), so d logit / d v = phi(z) / (p (1-p) sigma).
    """
    vals = [v for _, v in hist]
    if len(vals) < 8:
        return _src(spec, name, status="UNMEASURED",
                    why=f"{len(vals)} dated point(s); fewer than the 8 a z needs")
    mu, sigma = _mean(vals), _sd(vals)
    if sigma <= 0.0:
        return _src(spec, name, status="UNMEASURED",
                    why="the series does not vary: a constant has no elevated state")
    z = (vals[-1] - mu) / sigma
    p = _phi(z)
    band = sd_last if (sd_last is not None and sd_last > 0.0) else None
    if band is not None:
        grad = _npdf(z) / max(p * (1.0 - p), 1e-6) / sigma
        logit_sd, basis = grad * band, "measured"
    else:
        logit_sd, basis = DECLARED_LOGIT_SD, "declared"
    return _src(spec, name, p=p, logit_sd=logit_sd, sd_basis=basis, n=len(vals),
                last_at=hist[-1][0])


def _axis_doc(cache: dict[str, Any], stem: str) -> Any:
    key = f"axis:{stem}"
    if key not in cache:
        cache[key] = _read_json(AXES / f"{stem}.json")
    return cache[key]


def _points(doc: Any) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for pt in (doc.get("points") if isinstance(doc, dict) else None) or []:
        if not isinstance(pt, dict):
            continue
        d, v = _day(pt.get("knowable_at") or pt.get("d")), _f(pt.get("v"))
        if d and v is not None:
            out.append((d, v))
    out.sort(key=lambda r: r[0])
    return out


def read_source(spec: dict[str, Any], cache: dict[str, Any]) -> tuple[dict[str, Any],
                                                                     list[tuple[str, float]]]:
    """One source -> (its probability row, its dated history). The history is the only thing
    section (2) can bucket by, so a source with none simply does not condition anything."""
    kind = str(spec.get("kind") or "")

    if kind == "axis_latent":
        stem = str(spec.get("id"))
        name = f"axis:{stem}"
        doc = _axis_doc(cache, stem)
        if not isinstance(doc, dict):
            return _src(spec, name, status="ABSENT",
                        why=f"data/axes/{stem}.json absent on this host"), []
        if str(doc.get("status") or "") != "MEASURED":
            why = str(doc.get("equal_weight_reason") or "")[:220] or \
                f"the latent publishes status {doc.get('status') or 'unknown'}"
            return _src(spec, name, status="UNMEASURED", why=why), []
        hist = _points(doc)
        pts = doc.get("points") or []
        sd_last = _f(pts[-1].get("sd")) if isinstance(pts, list) and pts and \
            isinstance(pts[-1], dict) else None
        return _from_history(spec, name, hist, sd_last), hist

    if kind == "axis_series":
        stem, sid = str(spec.get("file")), str(spec.get("series"))
        name = f"axis:{stem}:{sid}"
        doc = _axis_doc(cache, stem)
        blk = (doc.get("series") if isinstance(doc, dict) else None) or {}
        series = blk.get(sid) if isinstance(blk, dict) else None
        if not isinstance(series, dict):
            return _src(spec, name, status="ABSENT",
                        why=f"data/axes/{stem}.json holds no series '{sid}'"), []
        hist = _points(series)
        return _from_history(spec, name, hist, None), hist

    if kind == "axis_rows":
        stem, field = str(spec.get("file")), str(spec.get("field"))
        name = f"axis:{stem}:{field}"
        doc = _axis_doc(cache, stem)
        rows = (doc.get("rows") if isinstance(doc, dict) else None) or []
        wanted = {str(s).upper() for s in (spec.get("symbols") or ())}
        use_abs = bool(spec.get("abs"))
        by_day: dict[str, list[float]] = {}
        for r in rows:
            if not isinstance(r, dict):
                continue
            if wanted and str(r.get("symbol") or "").upper() not in wanted:
                continue
            d, v = _day(r.get("knowable_at") or r.get("d")), _f(r.get(field))
            if d and v is not None:
                by_day.setdefault(d, []).append(abs(v) if use_abs else v)
        if not by_day:
            return _src(spec, name, status="ABSENT",
                        why=f"data/axes/{stem}.json holds no readable '{field}' row"
                            + (f" for {sorted(wanted)}" if wanted else "")), []
        hist = sorted((d, _mean(vs)) for d, vs in by_day.items())
        return _from_history(spec, name, hist, None), hist

    if kind in ("macro_series", "macro_states"):
        if "macro" not in cache:
            cache["macro"] = _read_json(MACRO_STATE)
        doc = cache["macro"]
        sid = str(spec.get("id"))
        name = f"macro_state:{sid}"
        if not isinstance(doc, dict):
            return _src(spec, name, status="ABSENT",
                        why="data/macro_state.json absent on this host"), []
        if kind == "macro_series":
            blk = (doc.get("series") or {}).get(sid)
            if not isinstance(blk, dict) or not blk.get("ok"):
                why = f"the FRED collector marks '{sid}' not ok" if isinstance(blk, dict) \
                    else f"data/macro_state.json holds no series '{sid}'"
                return _src(spec, name, status="UNMEASURED", why=why), []
            z = _f(blk.get("z"))
            last_at = str(blk.get("last_date") or "")
        else:
            z = _f((doc.get("states") or {}).get(sid))
            last_at = _day(doc.get("updated"))
        if z is None:
            return _src(spec, name, status="UNMEASURED",
                        why=f"'{sid}' carries no z on this pass"), []
        return _src(spec, name, p=_phi(z), logit_sd=DECLARED_LOGIT_SD, sd_basis="declared",
                    n=1, last_at=last_at,
                    why=str(spec.get("why") or "") + "; the collector publishes a z with no "
                        "sample size, so the band is declared"), []

    if kind == "rank":
        if "view" not in cache:
            cache["view"] = _read_json(MACRO_VIEW)
        doc = cache["view"]
        rid = str(spec.get("id"))
        name = f"macro_view:{rid}"
        if not isinstance(doc, dict):
            return _src(spec, name, status="ABSENT",
                        why="reports/MACRO_VIEW.json absent on this host"), []
        r = _f((doc.get("ranks") or {}).get(rid))
        if r is None:
            return _src(spec, name, status="UNMEASURED",
                        why=f"MACRO_VIEW publishes no rank for '{rid}'"), []
        conf = max((_f(doc.get("confidence")) or 0.0) * (_f(doc.get("freshness")) or 0.0), 0.05)
        return _src(spec, name, p=r, logit_sd=DECLARED_LOGIT_SD / conf,
                    sd_basis="declared_scaled_by_source_confidence", n=1,
                    last_at=str(doc.get("newest_print") or ""),
                    why=str(spec.get("why") or "")
                        + f"; widened by MACRO_VIEW's own confidence x freshness = {conf:.3f}"), []

    if kind == "router":
        if "router" not in cache:
            cache["router"] = _read_json(REGIME_ROUTER)
        doc = cache["router"]
        key = str(spec.get("key"))
        name = f"regime_router:{key}"
        if not isinstance(doc, dict):
            return _src(spec, name, status="ABSENT",
                        why="reports/REGIME_ROUTER.json absent on this host"), []
        raw_cur = doc.get("current_state")
        cur: dict[str, Any] = raw_cur if isinstance(raw_cur, dict) else {}
        raw: Any = cur.get(key)
        if raw is None and key == "vol":
            for s in (doc.get("sleeves") or [])[:1]:
                if isinstance(s, dict):
                    raw = str(s.get("current_bucket") or "").split("=")[-1] or None
        raw_map = spec.get("map")
        mapping: dict[str, Any] = raw_map if isinstance(raw_map, dict) else {}
        p = _f(mapping.get(str(raw)))
        if p is None:
            return _src(spec, name, status="UNMEASURED",
                        why=f"the router publishes '{raw}' for '{key}', which this table does "
                            "not map; an unmapped reading is not a probability"), []
        return _src(spec, name, p=p, logit_sd=CATEGORICAL_LOGIT_SD, sd_basis="declared", n=1,
                    last_at=_day(doc.get("at")),
                    why=str(spec.get("why") or "") + f"; reading '{raw}', categorical"), []

    if kind == "state_vector":
        if "sv" not in cache:
            cache["sv"] = _read_json(STATE_VECTOR) or _read_json(WORLD_STATE)
        doc = cache["sv"]
        path = str(spec.get("path"))
        name = f"state_vector:{path}"
        if not isinstance(doc, dict):
            return _src(spec, name, status="ABSENT",
                        why="neither data/state_vector.json nor data/world_state.json "
                            "is readable on this host"), []
        node: Any = doc
        for part in path.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        raw_map = spec.get("map")
        mapping = raw_map if isinstance(raw_map, dict) else {}
        p = _f(mapping.get(str(node)))
        if p is None:
            return _src(spec, name, status="UNMEASURED",
                        why=f"the state vector publishes '{node}' at '{path}', which this table "
                            "does not map"), []
        return _src(spec, name, p=p, logit_sd=CATEGORICAL_LOGIT_SD, sd_basis="declared", n=1,
                    last_at=_day(doc.get("at")),
                    why=str(spec.get("why") or "") + f"; reading '{node}', categorical"), []

    if kind == "event_ledger":
        name = "macro:event_ledger"
        rows = _read_rows(EVENT_LEDGER, limit=60_000)
        if not rows:
            return _src(spec, name, status="ABSENT",
                        why="data/macro/event_ledger.jsonl absent or empty on this host"), []
        hours = int(_f(spec.get("hours")) or 48.0)
        per_day: dict[str, int] = {}
        for r in rows:
            d = _day(r.get("at") or r.get("time") or r.get("date"))
            if d:
                per_day[d] = per_day.get(d, 0) + 1
        if not per_day:
            return _src(spec, name, status="UNMEASURED",
                        why="the event ledger carries no dated row"), []
        span = max(1, hours // 24)
        days = sorted(per_day)
        rolling = [(days[i], float(sum(per_day[d] for d in days[max(0, i - span + 1):i + 1])))
                   for i in range(len(days))]
        return _from_history(spec, name, rolling, None), rolling

    return _src(spec, f"unknown:{kind}", status="ABSENT",
                why=f"no reader for source kind '{kind}'"), []


def fuse(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Precision-weighted fusion in logit space. No source, no posterior."""
    live = [r for r in rows if r.get("status") == "MEASURED" and _f(r.get("logit")) is not None]
    if not live:
        return {"status": "UNMEASURED", "mean": None, "interval": None, "logit_mean": None,
                "logit_sd": None}
    wsum = sum(1.0 / (float(r["logit_sd"]) ** 2) for r in live)
    lm = sum(float(r["logit"]) / (float(r["logit_sd"]) ** 2) for r in live) / wsum
    ls = math.sqrt(1.0 / wsum)
    return {"status": "MEASURED", "mean": round(_sigmoid(lm), 6),
            "interval": [round(_sigmoid(lm - 1.96 * ls), 6), round(_sigmoid(lm + 1.96 * ls), 6)],
            "logit_mean": round(lm, 6), "logit_sd": round(ls, 6)}


def global_posterior(cache: dict[str, Any]) -> tuple[dict[str, Any],
                                                     dict[str, list[tuple[str, float]]]]:
    """Section (1). Returns the published block and, per state, the dated series that conditions
    it -- the longest history any of its sources published."""
    states: list[dict[str, Any]] = []
    series: dict[str, list[tuple[str, float]]] = {}
    for name in STATE_NAMES:
        rows: list[dict[str, Any]] = []
        best: list[tuple[str, float]] = []
        for spec in SOURCES.get(name, ()):
            row, hist = read_source(spec, cache)
            rows.append(row)
            if len(hist) > len(best):
                best = hist
        block = fuse(rows)
        if best:
            series[name] = best
        why = ""
        if block["status"] != "MEASURED":
            why = ("no source measures it on this host: "
                   + "; ".join(f"{r['source']} -- {r['why']}" for r in rows)[:400]) if rows else \
                  "no source is declared for this state"
        states.append({"state": name, **block, "n_sources": len(rows),
                       "n_sources_measured": sum(1 for r in rows if r["status"] == "MEASURED"),
                       "conditioning_points": len(best), "why": why, "sources": rows})
    n_ok = sum(1 for s in states if s["status"] == "MEASURED")
    return ({"states": states, "n_states": len(states), "n_measured": n_ok,
             "n_unmeasured": len(states) - n_ok,
             "fusion": "logit_mean = sum(l_i / sd_i^2) / sum(1 / sd_i^2); "
                       "sd = sqrt(1 / sum(1 / sd_i^2)); interval is +/- 1.96 sd through sigmoid",
             "declared_logit_sd": DECLARED_LOGIT_SD,
             "categorical_logit_sd": CATEGORICAL_LOGIT_SD,
             "min_logit_sd": MIN_LOGIT_SD}, series)


# ------------------------------------------------------------- conditional sleeve distributions
class Conditioner:
    """One state's dated series, with the EXPANDING median that splits it without lookahead."""

    def __init__(self, name: str, hist: list[tuple[str, float]]) -> None:
        self.name = name
        self.days = [d for d, _ in hist]
        self.values = [v for _, v in hist]
        self.medians: list[float] = []
        ordered: list[float] = []
        for v in self.values:
            bisect.insort(ordered, v)
            k = len(ordered)
            self.medians.append(ordered[k // 2] if k % 2 else
                                0.5 * (ordered[k // 2 - 1] + ordered[k // 2]))

    def bucket(self, stamp: Any) -> str | None:
        """"high"/"low" against what the median WAS on that day, or None before the series began."""
        d = _day(stamp)
        if not d or not self.days:
            return None
        i = bisect.bisect_right(self.days, d) - 1
        if i < 0:
            return None
        return "high" if self.values[i] >= self.medians[i] else "low"


def _shrunk(xs: list[float], n0: float | None, grand: float) -> float:
    """The bucket's mean pulled toward the unconditional one by the weight n0 the data implies."""
    lam = (len(xs) / (len(xs) + n0)) if (n0 is not None and n0 > 0 and xs) else 0.0
    return lam * _mean(xs) + (1.0 - lam) * float(grand)


def _dl_shrinkage(buckets: dict[str, list[float]], grand: float) -> dict[str, Any]:
    """DerSimonian-Laird: the prior sample size n0 the DATA implies, never one chosen here.

    tau^2 is the between-bucket variance left after the within-bucket noise is taken out. It can
    be zero, and zero is the honest answer "this state did not move this sleeve" -- the buckets
    are then fully shrunk to the unconditional mean and the report says so.
    """
    usable = {b: xs for b, xs in buckets.items() if len(xs) >= 2}
    if len(usable) < 2:
        return {"tau2": None, "n0": None, "basis": "UNMEASURED",
                "why": f"{len(usable)} bucket(s) with 2+ trades; a between-bucket variance needs 2"}
    dof = sum(len(xs) - 1 for xs in usable.values())
    pooled = sum((len(xs) - 1) * _sd(xs) ** 2 for xs in usable.values()) / dof if dof else 0.0
    if pooled <= 0.0:
        return {"tau2": None, "n0": None, "basis": "UNMEASURED",
                "why": "pooled within-bucket variance is zero; no noise scale to shrink against"}
    w = {b: len(xs) / pooled for b, xs in usable.items()}
    sw = sum(w.values())
    mbar = sum(w[b] * _mean(xs) for b, xs in usable.items()) / sw
    q = sum(w[b] * (_mean(xs) - mbar) ** 2 for b, xs in usable.items())
    denom = sw - sum(v * v for v in w.values()) / sw
    tau2 = max(0.0, (q - (len(usable) - 1)) / denom) if denom > 0 else 0.0
    if tau2 <= 0.0:
        return {"tau2": 0.0, "n0": None, "basis": "MEASURED",
                "why": "DerSimonian-Laird tau^2 = 0: no between-bucket signal survives the "
                       "within-bucket noise, so every bucket is fully shrunk to the "
                       f"unconditional mean {round(grand, 6)}"}
    return {"tau2": round(tau2, 8), "n0": round(pooled / tau2, 4), "basis": "MEASURED",
            "why": "n0 = pooled within-bucket variance / tau^2, both measured on this sleeve"}


def condition_sleeve(name: str, symbol: str, lane: str, trades: list[tuple[str, float]],
                     conds: dict[str, Conditioner]) -> list[dict[str, Any]]:
    """One row per (sleeve, state): the sleeve's forward R bucketed by the state at entry."""
    rs = [r for _, r in trades]
    grand, n = _mean(rs), len(rs)
    base = {"sleeve": name, "symbol": symbol, "lane": lane, "n": n,
            "unconditional_mean_r": round(grand, 6), "unconditional_sd_r": round(_sd(rs), 6)}
    if n < MIN_SLEEVE_N:
        return [{**base, "state": None, "status": "UNMEASURED",
                 "why": f"{n} trade(s); a conditional book needs {MIN_SLEEVE_N}"}]
    out: list[dict[str, Any]] = []
    for state, cond in conds.items():
        buckets: dict[str, list[float]] = {"low": [], "high": []}
        unplaced = 0
        for stamp, r in trades:
            b = cond.bucket(stamp)
            if b is None:
                unplaced += 1
            else:
                buckets[b].append(r)
        shrink = _dl_shrinkage(buckets, grand)
        n0 = _f(shrink.get("n0"))
        rows = []
        for b, xs in buckets.items():
            if len(xs) < MIN_BUCKET_N:
                rows.append({"bucket": b, "n": len(xs), "status": "UNMEASURED",
                             "why": f"{len(xs)} trade(s); a bucket needs {MIN_BUCKET_N}"})
                continue
            lam = (len(xs) / (len(xs) + n0)) if (n0 is not None and n0 > 0) else 0.0
            shrunk = _shrunk(xs, n0, grand)
            rows.append({"bucket": b, "n": len(xs), "status": "MEASURED",
                         "mean_r": round(_mean(xs), 6), "sd_r": round(_sd(xs), 6),
                         "shrunk_mean_r": round(shrunk, 6), "lambda": round(lam, 6),
                         "n_eff": round(lam * len(xs), 4),
                         "elog_gradient": round(shrunk, 6)})
        measured = [r for r in rows if r["status"] == "MEASURED"]
        means = [_f(r.get("shrunk_mean_r")) or 0.0 for r in measured]
        spread = (max(means) - min(means)) if len(means) > 1 else None
        out.append({**base, "state": state, "status": "MEASURED" if measured else "UNMEASURED",
                    "buckets": rows, "unplaced_trades": unplaced, "shrinkage": shrink,
                    "conditional_spread_r": round(spread, 6) if spread is not None else None,
                    "why": "" if measured else
                           f"no bucket reached {MIN_BUCKET_N} trades under '{state}'"})
    return out or [{**base, "state": None, "status": "UNMEASURED",
                    "why": "no state published a dated series to bucket by"}]


def _norm_sleeve(name: Any) -> str:
    s = str(name or "").strip().lower()
    return _HASH_SUFFIX.sub("", s)


def sleeve_histories(deadline: float) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Every sleeve the desk runs, with its own dated trade history.

    Two lanes and two shapes: `reports/shadow/ledger_*.json` carries `entry_time`/`r_multiple`
    per forward sleeve, `data/live_ledger.jsonl` carries `time`/`r_multiple` per closed deal.
    Names are normalised (lower-cased, the promoter's `_p_<hex>` suffix removed) so one sleeve is
    one sleeve across the two.
    """
    hist: dict[str, dict[str, Any]] = {}
    notes: dict[str, Any] = {"shadow_files": 0, "shadow_rows": 0, "live_rows": 0,
                             "roster_rows": 0, "not_a_sleeve": 0, "budget_stopped": False}
    roster = _read_json(SLEEVES)
    for s in (roster.get("sleeves") if isinstance(roster, dict) else roster) or []:
        if not isinstance(s, dict):
            continue
        key = _norm_sleeve(s.get("name"))
        if not key:
            continue
        notes["roster_rows"] += 1
        hist.setdefault(key, {"symbol": str(s.get("symbol") or ""), "lane": "roster",
                              "status": str(s.get("status") or ""), "trades": []})
        hist[key]["status"] = str(s.get("status") or hist[key].get("status") or "")
    if SHADOW.is_dir():
        for path in sorted(SHADOW.glob("ledger_*.json")):
            if time.monotonic() > deadline:
                notes["budget_stopped"] = True
                break
            notes["shadow_files"] += 1
            key = _norm_sleeve(path.stem[len("ledger_"):])
            rows = _read_json(path)
            if not isinstance(rows, list):
                continue
            blk = hist.setdefault(key, {"symbol": key.split("_")[0].upper(), "lane": "forward",
                                        "status": "", "trades": []})
            blk["lane"] = "forward" if blk["lane"] == "roster" else blk["lane"]
            for r in rows:
                if not isinstance(r, dict):
                    continue
                t, v = str(r.get("entry_time") or ""), _f(r.get("r_multiple"))
                if t and v is not None:
                    blk["trades"].append((t, v))
                    notes["shadow_rows"] += 1
    for r in _read_rows(LIVE_LEDGER):
        raw = str(r.get("sleeve") or "")
        if not raw or _NOT_A_SLEEVE.match(raw):
            notes["not_a_sleeve"] += 1
            continue
        key = _norm_sleeve(raw)
        v = _f(r.get("r_multiple"))
        if v is None:
            continue
        blk = hist.setdefault(key, {"symbol": str(r.get("symbol") or ""), "lane": "live",
                                    "status": "LIVE", "trades": []})
        blk["trades"].append((str(r.get("time") or ""), v))
        notes["live_rows"] += 1
    for blk in hist.values():
        blk["trades"].sort(key=lambda t: t[0])
    return hist, notes


# ------------------------------------------------------------------ live-trade counterfactuals
def _cost_model(cache: dict[str, Any]) -> dict[str, Any]:
    if "cost" not in cache:
        cache["cost"] = _read_json(COST_SURFACE)
    doc = cache["cost"]
    return doc if isinstance(doc, dict) else {}


def _half_spread_quote(cache: dict[str, Any], symbol: str, hour: int, volume: float,
                       contract: float) -> tuple[float | None, str]:
    """The modelled ROUND-TRIP spread cost in quote currency at this symbol's own hour."""
    surface = _cost_model(cache)
    blk = (surface.get("symbols") or {}).get(symbol) if surface else None
    if not isinstance(blk, dict):
        return None, f"data/cost_surface.json prices no symbol '{symbol}'"
    tick = _f(blk.get("tick_size"))
    cell = (blk.get("hours") or {}).get(str(hour))
    pts = _f(cell.get("p50")) if isinstance(cell, dict) else None
    if pts is None:
        pts = _f(blk.get("pooled_median_spread_pts"))
        basis = "pooled median spread: the surface measured no cell at this hour"
    else:
        basis = f"measured p50 spread at hour {hour}"
    if tick is None or pts is None:
        return None, f"the surface prices '{symbol}' with no tick size or spread"
    return abs(pts) * tick * abs(volume) * abs(contract), basis


def _intents(cache: dict[str, Any]) -> dict[int, float]:
    if "intents" not in cache:
        out: dict[int, float] = {}
        for r in _read_rows(ORDER_INTENTS, limit=100_000):
            t, p = r.get("ticket"), _f(r.get("intended"))
            if p is not None:
                try:
                    out[int(t)] = p  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
        cache["intents"] = out
    return dict(cache["intents"])


def _model_commission(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Commission per lot the desk's OWN tape shows, per symbol. Measured, not quoted."""
    by: dict[str, list[float]] = {}
    for r in rows:
        vol, com = _f(r.get("volume")), _f(r.get("commission"))
        if vol and com is not None and vol > 0:
            by.setdefault(str(r.get("symbol") or ""), []).append(abs(com) / vol)
    out: dict[str, float] = {}
    for sym, xs in by.items():
        xs.sort()
        out[sym] = xs[len(xs) // 2]
    return out


def attribute(live: list[dict[str, Any]], hist: dict[str, dict[str, Any]],
              cond: Conditioner | None, cache: dict[str, Any],
              deadline: float, cap: int) -> dict[str, Any]:
    """Section (3). Every closed live deal, decomposed and counterfactualled."""
    intents, commission = _intents(cache), _model_commission(live)
    rows: list[dict[str, Any]] = []
    tot = {"r": 0.0, "unconditional": 0.0, "conditional": 0.0, "execution": 0.0,
           "financing": 0.0, "residual": 0.0, "r_if_opposite_bucket": 0.0,
           "r_at_modelled_cost": 0.0, "r_if_not_taken": 0.0}
    counts = {"attributed": 0, "no_r": 0, "r_reconstructed": 0, "no_sleeve": 0, "no_prior": 0,
              "no_bucket": 0, "no_cost_model": 0, "slippage_measured": 0, "budget_stopped": 0}
    for deal in live:
        if time.monotonic() > deadline:
            counts["budget_stopped"] = 1
            break
        raw = str(deal.get("sleeve") or "")
        stamp = str(deal.get("time") or "")
        key = _norm_sleeve(raw)
        sym = str(deal.get("symbol") or "")
        # THE LEDGER'S OWN R IS NOT ALWAYS THE DEAL'S R, AND ITS `risk_quote` IS NOT ALWAYS IN
        # QUOTE CURRENCY. Measured 2026-09-22 on this box: 141 of 151 closed deals publish
        # `r_multiple: 0.0` beside a non-zero `pl_quote`, and on 87 of them `risk_quote` holds
        # |entry - sl| in PRICE units -- the writer did not multiply by volume x contract_size,
        # so the field is 0.00026 where the risk was 2.60. Summing those as "the trade returned
        # zero" posts a fabricated zero into every total, and dividing by the price-unit field
        # posts a -12,461 R. The risk is therefore RECOMPUTED from the four fields the row
        # always carries, the ledger's own figure is kept beside it, and a disagreement is named.
        r = _f(deal.get("r_multiple"))
        pl, risk = _f(deal.get("pl_quote")), _f(deal.get("risk_quote"))
        vol0, con0 = _f(deal.get("volume")), _f(deal.get("contract_size"))
        entry0, sl0 = _f(deal.get("entry_price")), _f(deal.get("sl"))
        risk_row: float | None = None
        if None not in (entry0, sl0, vol0, con0):
            cand = abs(float(entry0 or 0) - float(sl0 or 0)) * abs(vol0 or 0) * abs(con0 or 0)
            risk_row = cand if cand > 0 else None
        risk_led = abs(risk) if (risk is not None and risk != 0.0) else None
        risk_abs = risk_row if risk_row is not None else risk_led
        risk_basis = ("|entry_price - sl| x volume x contract_size, recomputed from the row"
                      if risk_row is not None else "the ledger's own |risk_quote|")
        risk_disagrees = (risk_row is not None and risk_led is not None
                          and not 0.2 < risk_row / risk_led < 5.0)
        if r is not None and r != 0.0:
            r_basis = "the ledger's own r_multiple"
        elif risk_abs is not None and pl is not None:
            r, r_basis = pl / risk_abs, ("reconstructed as pl_quote / risk: the ledger publishes "
                                         f"r_multiple 0.0 on this row; risk is {risk_basis}")
            counts["r_reconstructed"] += 1
        elif r is None:
            counts["no_r"] += 1
            continue
        else:
            r_basis = "the ledger's own r_multiple (zero, and no leg reconstructs it)"
        row: dict[str, Any] = {"deal": deal.get("deal"), "at": stamp, "sleeve": raw,
                               "sleeve_key": key, "symbol": sym, "r_realised": round(r, 6),
                               "r_basis": r_basis, "risk_quote_used": risk_abs,
                               "risk_basis": risk_basis, "unmeasured": []}
        if risk_disagrees:
            counts["risk_quote_disagrees"] = counts.get("risk_quote_disagrees", 0) + 1
            row["unmeasured"].append(
                f"risk: the ledger's risk_quote {risk} and the row's own "
                f"|entry - sl| x volume x contract_size {round(risk_row or 0.0, 6)} differ by "
                "more than 5x; the recomputed figure is used and this deal's R is not the "
                "producer's number")

        # --- the sleeve's unconditional expectation, from its trades BEFORE this one only
        blk = hist.get(key)
        prior = [(t, v) for t, v in (blk or {}).get("trades", []) if t and t < stamp] if blk \
            else []
        if _NOT_A_SLEEVE.match(raw) or not blk:
            counts["no_sleeve"] += 1
            row["unmeasured"].append("sleeve: the ledger's `sleeve` field is a broker comment, "
                                     "not a roster name; no history joins it")
        mu_unc: float | None = _mean([v for _, v in prior]) if len(prior) >= MIN_PRIOR_N else None
        if mu_unc is None and not row["unmeasured"]:
            counts["no_prior"] += 1
            row["unmeasured"].append(f"unconditional: {len(prior)} prior trade(s) on this sleeve, "
                                     f"fewer than the {MIN_PRIOR_N} a mean needs")
        row["n_prior"] = len(prior)

        # --- the conditional term, against the primary conditioning state at the deal's day
        bucket = cond.bucket(stamp) if cond else None
        cond_term: float | None = None
        opposite: float | None = None
        if cond is None:
            row["unmeasured"].append("conditional: no state published a dated series to bucket by")
        elif bucket is None:
            counts["no_bucket"] += 1
            row["unmeasured"].append(f"conditional: '{cond.name}' has no reading on or before "
                                     f"{_day(stamp) or 'this deal'}")
        elif mu_unc is not None:
            other = "low" if bucket == "high" else "high"
            by: dict[str, list[float]] = {"low": [], "high": []}
            for t, v in prior:
                b = cond.bucket(t)
                if b:
                    by[b].append(v)
            shrink = _dl_shrinkage(by, mu_unc)
            n0 = _f(shrink.get("n0"))
            here = _shrunk(by[bucket], n0, mu_unc)
            cond_term = here - mu_unc
            opposite = _shrunk(by[other], n0, mu_unc) - here
            row["bucket"] = bucket
            row["state"] = cond.name
            row["shrinkage"] = shrink
            if shrink.get("tau2") == 0.0:
                row["unmeasured"].append(f"conditional: tau^2 = 0 under '{cond.name}'; this "
                                         "sleeve's history shows no between-bucket signal, so "
                                         "the conditional term is measured at exactly zero")

        # --- the execution term, LIKE FOR LIKE. The realised side of a deal shows commission and
        # the entry slip against its own intent; the spread is already inside the fill price and
        # cannot be separated from the signal's move. So the MODELLED spread is only compared
        # when the realised slip that measures the same crossing exists -- otherwise both sides
        # carry commission alone. Comparing a modelled spread against a realised cost that has
        # none makes every fill look better than the model, which is how a cost report lies.
        # Swap is a real cost the surface models at all: it is its own term, never hidden.
        vol = _f(deal.get("volume")) or 0.0
        contract = _f(deal.get("contract_size")) or 0.0
        hour = (_parse(stamp) or _now()).hour
        full_spread, spread_why = _half_spread_quote(cache, sym, hour, vol, contract)
        slip_q: float | None = None
        slip_why = "no order intent joins this deal's entry order"
        intended = intents.get(int(_f(deal.get("entry_order")) or -1))
        entry = _f(deal.get("entry_price"))
        if intended is not None and entry is not None and contract > 0:
            slip_q = abs(entry - intended) * abs(vol) * abs(contract)
            slip_why = f"entry {entry} against intent {intended}"
            counts["slippage_measured"] += 1
        exec_term: float | None = None
        fin_term: float | None = None
        expected_cost: float | None = None
        r_net = r
        if risk_abs is not None:
            swap_q = abs(_f(deal.get("swap")) or 0.0)
            fin_term = -swap_q / risk_abs
            realised = abs(_f(deal.get("commission")) or 0.0) + (slip_q or 0.0)
            modelled = commission.get(sym, 0.0) * abs(vol)
            if slip_q is not None and full_spread is not None:
                modelled += 0.5 * full_spread
                basis = f"commission + one crossing of the {spread_why}"
            else:
                basis = ("commission only: " + (spread_why if full_spread is None else slip_why)
                         + ", so no crossing is compared on either side")
            expected_cost = -modelled / risk_abs
            exec_term = (modelled - realised) / risk_abs
            # THE LEDGER'S R IS GROSS: r_multiple = pl_quote / risk_quote, with commission and
            # swap in their own fields. The decomposition is of the R the account KEPT.
            r_net = r - realised / risk_abs - swap_q / risk_abs
            row["cost"] = {"realised_quote": round(realised, 6),
                           "modelled_quote": round(modelled, 6),
                           "realised_r": round(realised / risk_abs, 6),
                           "modelled_r": round(modelled / risk_abs, 6),
                           "multiple": round(realised / modelled, 4) if modelled > 0 else None,
                           "basis": basis, "spread_basis": spread_why,
                           "slippage_basis": slip_why,
                           "slippage_quote": round(slip_q, 6) if slip_q is not None else None,
                           "swap_quote": round(swap_q, 6),
                           "commission_model_per_lot": round(commission.get(sym, 0.0), 6)}
        else:
            counts["no_cost_model"] += 1
            row["unmeasured"].append("execution: the deal carries no non-zero risk_quote, so a "
                                     "cost cannot be put in units of R; the row's R is gross")

        known = ((mu_unc or 0.0) + (cond_term or 0.0) + (expected_cost or 0.0)
                 + (exec_term or 0.0) + (fin_term or 0.0))
        residual = r_net - known
        row.update({"r_net": round(r_net, 6),
                    "unconditional": round(mu_unc, 6) if mu_unc is not None else None,
                    "conditional": round(cond_term, 6) if cond_term is not None else None,
                    "expected_cost": round(expected_cost, 6) if expected_cost is not None
                    else None,
                    "execution": round(exec_term, 6) if exec_term is not None else None,
                    "financing": round(fin_term, 6) if fin_term is not None else None,
                    "residual": round(residual, 6),
                    "counterfactuals": {
                        "opposite_bucket_r": round(r_net + opposite, 6) if opposite is not None
                        else None,
                        "opposite_bucket_delta": round(opposite, 6) if opposite is not None
                        else None,
                        "modelled_cost_r": round(r_net - exec_term, 6) if exec_term is not None
                        else None,
                        "modelled_cost_delta": round(-exec_term, 6) if exec_term is not None
                        else None,
                        "not_taken_r": 0.0, "not_taken_delta": round(-r_net, 6)}})
        rows.append(row)
        counts["attributed"] += 1
        tot["r"] += r_net
        tot["r_gross"] = tot.get("r_gross", 0.0) + r
        tot["unconditional"] += mu_unc or 0.0
        tot["conditional"] += cond_term or 0.0
        tot["expected_cost"] = tot.get("expected_cost", 0.0) + (expected_cost or 0.0)
        tot["execution"] += exec_term or 0.0
        tot["financing"] += fin_term or 0.0
        tot["residual"] += residual
        tot["r_if_opposite_bucket"] += r_net + (opposite or 0.0)
        tot["r_at_modelled_cost"] += r_net - (exec_term or 0.0)
    return {"rows": rows[:cap], "n_rows": len(rows), "n_published": min(len(rows), cap),
            "totals": {k: round(v, 6) for k, v in tot.items()}, "counts": counts,
            "identity": "r_net = unconditional + conditional + expected_cost + execution + "
                        "financing + residual, exactly, per row. r_net is the R the account "
                        "kept: the ledger's gross r_multiple less realised commission, entry "
                        "slippage and swap. `expected_cost` is what the cost surface said the "
                        "fill should cost, `execution` is the surprise against it (positive = "
                        "the fill beat the model), `financing` is swap, which the surface does "
                        "not model at all. A term that is UNMEASURED is zero in the sum and "
                        "named in `unmeasured`, so the residual carries it and never hides it"}


# --------------------------------------------------------------------------- residual routing
def residual_rows(trades: dict[str, Any], posterior: dict[str, Any]) -> list[dict[str, Any]]:
    """The unexplained residual in `residual_queue`'s own row shape, built by its own `item`."""
    try:
        from research.residual_queue import item as _item
    except Exception:
        def _item(level: str, symbol: Any, key: str, magnitude: Any, unit: str, share: Any,
                  source: str, why: str, *, family: str | None = None,
                  params: dict[Any, Any] | None = None,
                  measured: bool = True) -> dict[Any, Any] | None:
            m = _f(magnitude)
            return None if m is None else {
                "residual_id": f"{level}|{str(symbol).upper()}|{key}", "level": level,
                "symbol": str(symbol or ""), "key": key, "magnitude": round(abs(m), 6),
                "magnitude_unit": unit, "unexplained_fraction": _f(share) or 0.5,
                "unexplained_measured": bool(measured), "source": source,
                "why": why, "family": family, "params": dict(params or {})}
    by: dict[str, dict[str, float]] = {}
    for row in trades.get("rows") or []:
        key = str(row.get("sleeve_key") or "")
        acc = by.setdefault(key, {"resid": 0.0, "explained": 0.0, "n": 0.0})
        acc["resid"] += _f(row.get("residual")) or 0.0
        # THE DENOMINATOR IS THE TRADE'S OWN EXPLAINED MAGNITUDE, not its realised R. A sleeve
        # whose deals net to zero R still has a residual, and dividing by zero R would drop it
        # out of the queue exactly when it is most interesting.
        acc["explained"] += sum(abs(_f(row.get(k)) or 0.0) for k in
                                ("unconditional", "conditional", "expected_cost", "execution",
                                 "financing"))
        acc["n"] += 1.0
    state = next((s["state"] for s in posterior.get("states") or []
                  if s.get("status") == "MEASURED"), "")
    out: list[dict[str, Any]] = []
    for key, acc in sorted(by.items(), key=lambda kv: -abs(kv[1]["resid"])):
        denom = abs(acc["resid"]) + acc["explained"]
        if acc["n"] < MIN_PRIOR_N or denom <= 0:
            continue
        share = min(max(abs(acc["resid"]) / denom, 0.0), 1.0)
        row = _item("strategy_loss", key.split("_")[0].upper(), f"cfa_residual:{key}",
                    acc["resid"], "R", share, SOURCE,
                    f"{int(acc['n'])} live deal(s) on '{key}' leave {round(acc['resid'], 4)} R "
                    f"that the sleeve's own unconditional mean, its conditional bucket under "
                    f"'{state or 'no measured state'}' and the modelled execution cost do not "
                    f"account for", measured=True)
        if row:
            out.append(row)
    return out


def cost_shock_rows(trades: dict[str, Any]) -> list[dict[str, Any]]:
    """The execution excess, in the vocabulary `residual_queue` ALREADY dispatches on.

    `residual_queue._unknown` maps `kind: "cost_shock"` to level `spread` with magnitude
    `multiple` in "x median" -- which is exactly what a realised cost over a modelled one is.
    """
    out: list[dict[str, Any]] = []
    for row in trades.get("rows") or []:
        cost = row.get("cost")
        mult = _f((cost or {}).get("multiple"))
        if mult is None or mult < COST_SHOCK_MULTIPLE:
            continue
        out.append({"kind": "cost_shock", "producer": SOURCE, "symbol": row.get("symbol"),
                    "at": row.get("at"), "multiple": round(mult, 4),
                    "question": (f"{SOURCE}: deal {row.get('deal')} on '{row.get('sleeve')}' paid "
                                 f"{(cost or {}).get('realised_quote')} where the cost surface "
                                 f"modelled {(cost or {}).get('modelled_quote')} "
                                 f"({(cost or {}).get('spread_basis')}); the excess is "
                                 f"{row.get('execution')} R off this trade")})
    return out


def route(rows: list[dict[str, Any]], *, apply: bool) -> dict[str, Any]:
    """Append to the producer inbox `residual_queue` already reads. Deduped by (producer, at,
    symbol) so a re-run of the same hour adds nothing, capped so one pass cannot bury it."""
    plan = {"path": str(UNKNOWN_QUEUE), "kind": "cost_shock", "n_candidates": len(rows),
            "n_written": 0, "applied": bool(apply),
            "contract": "residual_queue._unknown reads data/unknown_unknowns_queue.jsonl and "
                        "maps kind=cost_shock to level `spread`, magnitude `multiple`, unit "
                        "'x median'; residual_queue.py is not edited by this organ"}
    if not rows:
        return plan
    seen = {(str(r.get("producer")), str(r.get("at")), str(r.get("symbol")))
            for r in _read_rows(UNKNOWN_QUEUE)}
    fresh = [r for r in rows
             if (SOURCE, str(r.get("at")), str(r.get("symbol"))) not in seen][:120]
    plan["n_new"] = len(fresh)
    if not apply or not fresh:
        return plan
    try:
        UNKNOWN_QUEUE.parent.mkdir(parents=True, exist_ok=True)
        with UNKNOWN_QUEUE.open("a", encoding="utf-8") as fh:
            for r in fresh:
                fh.write(json.dumps(r, default=str) + "\n")
        plan["n_written"] = len(fresh)
    except OSError as exc:                                                  # pragma: no cover
        plan["error"] = f"{type(exc).__name__}: {exc}"
    return plan


# ----------------------------------------------------------------------------------- the pass
def _input_row(path: Path, why_absent: str) -> dict[str, Any]:
    ok = path.exists()
    return {"status": "present" if ok else "absent", "path": str(path),
            "why": "" if ok else why_absent}


def build(*, budget_s: float = BUDGET_S, apply: bool = True) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(float(budget_s), 1.0)
    cap, cap_why = row_cap()
    cache: dict[str, Any] = {}

    inputs = {
        "world_model": _input_row(WORLD_MODEL, "the hourly `world_model` leg has not run here"),
        "macro_view": _input_row(MACRO_VIEW, "the `fred_macro` leg has not published a view"),
        "regime_router": _input_row(REGIME_ROUTER, "the `regime_router` leg has not run here"),
        "state_vector": _input_row(STATE_VECTOR, "the `state_vector` leg has not run here"),
        "macro_state": _input_row(MACRO_STATE, "the FRED collector has not run here"),
        "axes": _input_row(AXES, "no PIT axis has been collected on this host"),
        "sleeves": _input_row(SLEEVES, "the gateway roster is absent on this host"),
        "live_ledger": _input_row(LIVE_LEDGER, "no live account has traded on this host"),
        "shadow_ledgers": _input_row(SHADOW, "the forward lane has written no ledger here"),
        "cost_surface": _input_row(COST_SURFACE, "the `cost_surface` leg has not run here"),
        "order_intents": _input_row(ORDER_INTENTS, "the gateway has logged no order intent"),
    }

    posterior, series = global_posterior(cache)
    conds = {name: Conditioner(name, hist) for name, hist in series.items() if len(hist) >= 8}
    primary = next((conds[n] for n in PRIMARY_CONDITIONING if n in conds), None)

    hist, notes = sleeve_histories(deadline)
    sleeve_rows: list[dict[str, Any]] = []
    for key, blk in sorted(hist.items()):
        if time.monotonic() > deadline:
            notes["budget_stopped"] = True
            break
        sleeve_rows.extend(condition_sleeve(key, str(blk.get("symbol") or ""),
                                            str(blk.get("lane") or ""), blk["trades"], conds))
    measured_sleeves = sum(1 for r in sleeve_rows if r.get("status") == "MEASURED")

    live = [r for r in _read_rows(LIVE_LEDGER) if _f(r.get("r_multiple")) is not None]
    trades = attribute(live, hist, primary, cache, deadline, cap)

    resid = residual_rows(trades, posterior)
    shocks = cost_shock_rows(trades)
    routed = route(shocks, apply=apply)

    unmeasured: list[dict[str, Any]] = [
        {"name": f"state:{s['state']}", "why": s["why"],
         "measured_by": "a source that publishes this state on a clock"}
        for s in posterior["states"] if s["status"] != "MEASURED"]
    if primary is None:
        unmeasured.append({"name": "conditional_sleeve_book",
                           "why": "no state published a dated series long enough to bucket by; "
                                  "every sleeve row is unconditional only",
                           "measured_by": "the axis collectors that write data/axes/*.json"})
    if not live:
        unmeasured.append({"name": "trade_attribution",
                           "why": "data/live_ledger.jsonl holds no closed deal with an R on this "
                                  "host; there is nothing to attribute, which is a verdict",
                           "measured_by": "the live account trading"})

    return {
        "at": _now().isoformat(timespec="seconds"), "rule": RULE, "source": SOURCE,
        "budget_s": round(float(budget_s), 3), "elapsed_s": round(time.monotonic() - t0, 3),
        "dry_run": not apply, "allocates_capital": False,
        "allocation_note": "evidence only. Tier-1 row P1 (route the gold book through the "
                           "allocator's fraction) is REFUSED by the principal's standing order "
                           "that the desk never reduces its aggressiveness, so nothing here is "
                           "fed to a sizer and no cap, veto or shrink on capital is created.",
        "inputs": inputs,
        "global_posterior": posterior,
        "sleeves": {"n_sleeves": len(hist), "n_rows": len(sleeve_rows),
                    "n_measured": measured_sleeves,
                    "conditioning_states": sorted(conds),
                    "primary_conditioning": primary.name if primary else None,
                    "primary_order": list(PRIMARY_CONDITIONING),
                    "min_sleeve_n": MIN_SLEEVE_N, "min_bucket_n": MIN_BUCKET_N,
                    "shrinkage": "DerSimonian-Laird tau^2 on the bucket means; "
                                 "n0 = pooled within-bucket variance / tau^2; "
                                 "lambda = n_b / (n_b + n0); n_eff = lambda * n_b",
                    "elog_note": "the E[log W] contribution is published as its GRADIENT "
                                 "(dE[log W]/df at f=0 = the mean R). The level needs a risk "
                                 "fraction, and the fraction belongs to the allocator.",
                    "notes": notes, "rows": sleeve_rows[:cap]},
        "trades": trades,
        "residual_rows": resid[:cap],
        "routed": routed,
        "unmeasured": unmeasured,
        "memory": {"row_cap": cap, "why": cap_why},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="the fused global posterior, the conditional sleeve book, and the "
                    "counterfactual attribution of every live trade")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode there is)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S,
                    help="wall-clock bound; the pass stops and still writes its artifact")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write no artifact and route no residual")
    a = ap.parse_args(argv)
    rep = build(budget_s=a.budget_s, apply=not a.dry_run)
    gp, sl, tr = rep["global_posterior"], rep["sleeves"], rep["trades"]
    print(f"counterfactual-attribution: {gp['n_measured']}/{gp['n_states']} macro state(s) "
          f"fused; {sl['n_measured']}/{sl['n_rows']} sleeve-state row(s) measured")
    top = sorted((s for s in gp["states"] if s["status"] == "MEASURED"),
                 key=lambda s: -abs(float(s["mean"]) - 0.5))[:3]
    for s in top:
        print(f"  {s['state']:<18} {s['mean']:.3f}  [{s['interval'][0]:.3f}, "
              f"{s['interval'][1]:.3f}]  from {s['n_sources_measured']}/{s['n_sources']} source(s)")
    t = tr["totals"]
    print(f"  trades    {tr['counts']['attributed']} attributed "
          f"({tr['counts']['r_reconstructed']} R reconstructed), net R {t['r']:+.3f} = "
          f"unconditional {t['unconditional']:+.3f} + conditional {t['conditional']:+.3f} + "
          f"expected cost {t.get('expected_cost', 0.0):+.3f} + execution {t['execution']:+.3f} + "
          f"financing {t['financing']:+.3f} + residual {t['residual']:+.3f}")
    print(f"  counterfactual  opposite bucket {t['r_if_opposite_bucket']:+.3f} R, "
          f"at modelled cost {t['r_at_modelled_cost']:+.3f} R, not taken 0.000 R")
    print(f"  residuals {len(rep['residual_rows'])} row(s); routed "
          f"{rep['routed']['n_written']}/{rep['routed']['n_candidates']} cost_shock(s) "
          f"-> {Path(rep['routed']['path']).name}")
    if not a.dry_run:
        _atomic(OUT, json.dumps(rep, indent=1, default=str))
        print(f"-> {OUT}")
    else:
        print("dry run: nothing written")
    return 0


if __name__ == "__main__":                                                  # pragma: no cover
    raise SystemExit(main())
