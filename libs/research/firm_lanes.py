"""FIRM LANES: the research roles of a top systematic shop, each as an always-on AI lane.

zuck, 2026-11-18: "how do we replicate 100s of rentechs quant researchers ... all roles they
have fr edge discoveries", widened the same hour to Two Sigma, D. E. Shaw, the Chinese quant
shops and Asian retail communities, plus Citadel's pod drawdown discipline and job listings as
a role-map source. The template is Medallion: many weak, independent signals, one book,
compounded on own capital.

What this module adds (pure functions; the hourly leg `desks/mt5/research/firm_lanes.py` does
the I/O):

* ROSTER -- `firm_lanes_roster.json` maps each real role to the lane that does it here, with the
  code that implements it and the artifacts that prove it ran. `liveness` measures each lane:
  LIVE / STALE / NO_ARTIFACT / NOT_ON_BRANCH / CODE_ONLY. A role whose code exists only in an
  open PR is NOT_ON_BRANCH, which is the honest answer, not "exists".
* SHARED SIGNAL LIBRARY -- one append-only record of every (family, symbol, params) identity any
  lane has sent to the judge or the judge has certified. Lanes read it before proposing, so no
  two lanes pay the multiple-testing charge for the same rule.
* HYPOTHESIS QUEUE PER LANE -- dedup against the queue and the library, drained at a fixed
  per-pass rate into the normal compiler intake (`data/intelligence/firm_lanes/`).
* ASSET x HORIZON GRID -- RenTech / High-Flyer staff one researcher per square. Empty squares
  are filled first; Asian-origin priority routes JP to FX, CN to commodities, metals, energy and
  softs, and KR/TW/HK/IN to indices (zuck 2026-11-18 01:26Z).
* MULTIPLE TESTING -- every certified survivor's SPA p-value replayed through the desk's own
  online FDR (LORD++ and e-LOND, `libs.tiers.online_fdr`), reported as the share certified
  outside the lifetime budget. Every queued row is charged as a trial on donation.
* POD STOPS (Citadel / Millennium) -- per-sleeve drawdown in R units against a hard stop sized
  so that every pod hitting its stop at once still uses only half of the tightest prop firm's
  drawdown. SHADOW ONLY: it writes recommendations; nothing here reaches sizing or orders.
* CAREERS SCOUT -- themes read from firms' own careers pages, diffed against the last read, and
  mapped to lanes as research topics.

LLMs propose only and never size; nothing in this module is read by the money path.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROSTER_PATH = Path(__file__).with_name("firm_lanes_roster.json")

#: MT5 registry asset_class -> grid bucket. Equities are absent on purpose: single names are
#: event-lane only (CLAUDE.md, TWO LANES), so the statistical grid never mints them.
ASSET_BUCKET: dict[str, str] = {
    "Forex": "fx", "Forex Exotics": "fx", "Commodities": "metals_commodities",
    "Energy": "energy", "Soft Commodity": "softs", "Indices": "indices", "Bonds": "bonds",
    "Crypto": "crypto_cfd",
}

#: Price-only families the compiler admits from a `{"kind": "hypothesis", "family": ...}` row
#: with family defaults, by holding period. calendar_month is left out: without a month in the
#: text it is not a recipe, and the grid would only manufacture refusals.
FAMILY_HORIZON: dict[str, str] = {
    "session_range_breakout": "intraday", "failed_breakout": "intraday",
    "london_close_momentum": "intraday", "asia_momentum": "intraday",
    "volume_spike": "intraday", "pin_bar_reversal": "intraday",
    "engulfing_reversal": "intraday", "ict_fvg": "intraday", "volatility_squeeze": "intraday",
    "spread_state": "intraday",
    "overnight_gap_decay": "daily", "overnight_drift": "daily", "monday_gap": "daily",
    "mean_reversion_rsi": "daily", "mean_reversion_bollinger": "daily",
    "range_reversion": "daily", "pullback_entry": "daily", "level_breakout": "daily",
    "drawdown_conditional": "daily", "vol_mean_reversion": "daily", "vol_transition": "daily",
    "momentum_volgate": "daily", "trend_ma_cross": "daily", "retail_overlap_reversal": "daily",
    "dow_effect": "weekly_monthly", "turn_of_month": "weekly_monthly",
}
HORIZONS = ("intraday", "daily", "weekly_monthly")

#: Origin -> the asset buckets tried FIRST for that origin's exact ports (zuck 01:26Z, and
#: 01:27Z "theyre js examples this is overall"). ORDERING ONLY, NEVER A FILTER: any country's
#: strategy that maps onto anything tradable on MT5 is ported exactly, and every bucket stays
#: open to every region.
REGION_PRIORITY: dict[str, tuple[str, ...]] = {
    "jp": ("fx",), "cn": ("metals_commodities", "energy", "softs"),
    "kr": ("indices",), "tw": ("indices",), "hk": ("indices",), "in": ("indices", "fx"),
    "sg": ("fx",), "vn": ("indices",), "id": ("metals_commodities", "softs"),
}


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def load_roster(path: Path = ROSTER_PATH) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(path.read_text("utf-8"))
    return doc


# ------------------------------------------------------------------------------------------
# Roster liveness
# ------------------------------------------------------------------------------------------

def liveness(roster: Mapping[str, Any], repo_root: Path, desk_root: Path,
             now: datetime | None = None, stale_h: float = 26.0) -> list[dict[str, Any]]:
    """One row per lane. The verdict is measured from the tree and the artifacts, never read
    from the roster's own `status` (which only says where the code is meant to be)."""
    now = now or now_utc()
    rows: list[dict[str, Any]] = []
    for lane in roster.get("lanes", []):
        mods = [str(m) for m in lane.get("modules", [])]
        missing = [m for m in mods if not (repo_root / m).exists()]
        ages: list[float] = []
        for a in lane.get("artifacts", []):
            p = desk_root / str(a)
            if p.exists():
                ages.append((now.timestamp() - p.stat().st_mtime) / 3600.0)
        if missing:
            verdict = "NOT_ON_BRANCH"
        elif not lane.get("artifacts"):
            verdict = "CODE_ONLY"
        elif not ages:
            verdict = "NO_ARTIFACT"
        elif min(ages) > stale_h:
            verdict = "STALE"
        else:
            verdict = "LIVE"
        rows.append({"id": lane["id"], "role": lane.get("role", ""),
                     "firms": lane.get("firms", []), "status": lane.get("status", ""),
                     "prs": lane.get("prs", []), "verdict": verdict,
                     "missing_modules": missing,
                     "freshest_artifact_h": round(min(ages), 2) if ages else None})
    return rows


# ------------------------------------------------------------------------------------------
# Shared signal library and per-lane queues
# ------------------------------------------------------------------------------------------

def identity(family: str, symbol: str, params: Mapping[str, Any] | None = None) -> str:
    blob = json.dumps({"f": str(family), "s": str(symbol).upper(), "p": dict(params or {})},
                      sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def append_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    return len(rows)


class SignalLibrary:
    """Append-only. A row is {id, family, symbol, params, lane, state, at}; state is QUEUED,
    SENT or CERTIFIED. Latest state per id wins on read."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.rows: dict[str, dict[str, Any]] = {}
        for r in read_jsonl(path):
            if r.get("id"):
                self.rows[str(r["id"])] = r

    def has(self, ident: str) -> bool:
        return ident in self.rows

    def add(self, rows: Iterable[Mapping[str, Any]]) -> int:
        fresh = []
        for r in rows:
            ident = str(r["id"])
            prev = self.rows.get(ident)
            if prev is not None and prev.get("state") == r.get("state"):
                continue
            self.rows[ident] = dict(r)
            fresh.append(r)
        return append_jsonl(self.path, fresh)

    def counts(self) -> dict[str, Any]:
        by_state: dict[str, int] = {}
        by_lane: dict[str, int] = {}
        for r in self.rows.values():
            by_state[str(r.get("state"))] = by_state.get(str(r.get("state")), 0) + 1
            by_lane[str(r.get("lane"))] = by_lane.get(str(r.get("lane")), 0) + 1
        return {"n": len(self.rows), "by_state": by_state, "by_lane": by_lane}


def survivors_to_library(survivors: Mapping[str, Any], at: str) -> list[dict[str, Any]]:
    """Every certified survivor as a CERTIFIED library row, so no lane re-proposes it."""
    out = []
    for key, s in (survivors.get("survivors") or {}).items():
        if not isinstance(s, dict):
            continue
        spec = s.get("shadow_spec") or {}
        fam = str(spec.get("family") or str(s.get("cell", "")).split(".")[-1] or key)
        sym = str(spec.get("symbol") or s.get("sym") or "")
        params = {k: v for k, v in spec.items() if k not in ("symbol", "family", "is_universe",
                                                             "hunt")}
        out.append({"id": identity(fam, sym, params), "family": fam, "symbol": sym,
                    "params": params, "lane": "judge", "state": "CERTIFIED",
                    "survivor_key": key, "at": at})
    return out


@dataclass
class LaneQueue:
    path: Path

    def items(self) -> list[dict[str, Any]]:
        """Latest row per id; drained rows carry state SENT."""
        latest: dict[str, dict[str, Any]] = {}
        for r in read_jsonl(self.path):
            if r.get("id"):
                latest[str(r["id"])] = r
        return list(latest.values())

    def pending(self) -> list[dict[str, Any]]:
        rows = [r for r in self.items() if r.get("state") == "QUEUED"]
        return sorted(rows, key=lambda r: (-float(r.get("priority", 0.0)), str(r.get("at")),
                                           str(r["id"])))

    def push(self, rows: Iterable[Mapping[str, Any]], library: SignalLibrary) -> int:
        seen = {str(r["id"]) for r in self.items()}
        fresh = [dict(r, state="QUEUED") for r in rows
                 if str(r["id"]) not in seen and not library.has(str(r["id"]))]
        return append_jsonl(self.path, fresh)

    def mark_sent(self, rows: Iterable[Mapping[str, Any]], at: str) -> int:
        return append_jsonl(self.path, [dict(r, state="SENT", sent_at=at) for r in rows])


# ------------------------------------------------------------------------------------------
# Asset x horizon grid
# ------------------------------------------------------------------------------------------

def universe_buckets(universe: Mapping[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for sym, meta in universe.items():
        if not isinstance(meta, dict) or sym.startswith("_"):
            continue
        b = ASSET_BUCKET.get(str(meta.get("asset_class") or ""))
        if b:
            out.setdefault(b, []).append(str(sym))
    return {k: sorted(v) for k, v in out.items()}


def grid_coverage(buckets: Mapping[str, Sequence[str]], library: SignalLibrary
                  ) -> dict[str, dict[str, int]]:
    sym_bucket = {s: b for b, syms in buckets.items() for s in syms}
    grid = {b: dict.fromkeys(HORIZONS, 0) for b in buckets}
    for r in library.rows.values():
        b = sym_bucket.get(str(r.get("symbol", "")).upper()) or sym_bucket.get(
            str(r.get("symbol", "")))
        h = FAMILY_HORIZON.get(str(r.get("family")))
        if b and h:
            grid[b][h] += 1
    return grid


def grid_hypotheses(buckets: Mapping[str, Sequence[str]], library: SignalLibrary,
                    per_pass: int, at: str, priority_buckets: Sequence[str] = ()
                    ) -> list[dict[str, Any]]:
    """Fill the emptiest squares first. Within a square, family x symbol pairs are walked in a
    hash order so successive passes cover the square instead of re-picking the same corner."""
    grid = grid_coverage(buckets, library)
    squares = sorted(((b, h) for b in grid for h in HORIZONS),
                     key=lambda bh: (bh[0] not in priority_buckets, grid[bh[0]][bh[1]],
                                     bh[0], bh[1]))
    fams_by_h: dict[str, list[str]] = {}
    for f, h in FAMILY_HORIZON.items():
        fams_by_h.setdefault(h, []).append(f)
    out: list[dict[str, Any]] = []
    if per_pass <= 0:
        return out
    per_square = max(1, math.ceil(per_pass / max(1, len(squares))))
    for b, h in squares:
        pairs = [(f, s) for f in sorted(fams_by_h.get(h, [])) for s in buckets[b]]
        pairs.sort(key=lambda fs: identity(fs[0], fs[1]))
        took = 0
        for f, s in pairs:
            ident = identity(f, s)
            if library.has(ident):
                continue
            out.append({"id": ident, "lane": "asset_horizon_grid", "family": f, "symbol": s,
                        "params": {}, "bucket": b, "horizon": h, "at": at,
                        "priority": 1.0 / (1 + grid[b][h]) + (1.0 if b in priority_buckets
                                                              else 0.0),
                        "why": f"grid square {b} x {h} holds {grid[b][h]} identities"})
            took += 1
            if took >= per_square:
                break
        if len(out) >= per_pass:
            break
    return out[:per_pass]


def to_intake_row(q: Mapping[str, Any]) -> dict[str, Any]:
    """The compiler's STRUCTURED_HYPOTHESIS shape: a registered price-only family named outright
    and declared instruments. Prose carries the family name so the prose path agrees."""
    fam = str(q["family"])
    return {"kind": "hypothesis", "family": fam, "symbols": [str(q["symbol"])],
            "title": f"{fam.replace('_', ' ')} on {q['symbol']} ({q.get('lane')})",
            "mechanism": str(q.get("why") or ""), "lane": q.get("lane"),
            "firm_lane_id": q["id"]}


# ------------------------------------------------------------------------------------------
# Multiple testing over the certified stream
# ------------------------------------------------------------------------------------------

def fdr_summary(survivors: Mapping[str, Any], alpha: float | None = None) -> dict[str, Any]:
    """Replay every certified survivor's SPA p-value through LORD++ / e-LOND in gating order.
    `over_budget_share` is the share of certificates the lifetime FDR budget would NOT have
    admitted. A survivor with no p-value is counted, never assumed significant."""
    from libs.tiers import online_fdr as ofdr
    tests = []
    no_p = 0
    for key, s in (survivors.get("survivors") or {}).items():
        if not isinstance(s, dict):
            continue
        spa = ((s.get("gates") or {}).get("reality_check_spa") or {})
        p = spa.get("p_value")
        if not isinstance(p, (int, float)):
            no_p += 1
            continue
        fam = str((s.get("shadow_spec") or {}).get("family") or "")
        tests.append(ofdr.Test(test_id=str(key), at=str(s.get("gated_at") or ""),
                               p=float(p), family=fam, certified=True))
    if not tests:
        return {"status": "UNMEASURED", "why": "no certified survivor carries an SPA p-value",
                "no_p_value": no_p}
    rep = ofdr.replay(tests, alpha) if alpha is not None else ofdr.replay(tests)
    rep.pop("rows", None)
    rep["no_p_value"] = no_p
    rep["status"] = "MEASURED"
    return rep


# ------------------------------------------------------------------------------------------
# Pod stops (Citadel / Millennium discipline) -- shadow only
# ------------------------------------------------------------------------------------------

def pod_stop_r(firm_dd_pct: float, risk_pct: float, n_pods: int) -> float:
    """Hard stop per pod in R. All pods stopping at once may use at most HALF the firm's
    drawdown; independent pods rarely stop together, so the budget is split by sqrt(N), not N,
    and floored at 3R so a pod is never cut by ordinary noise."""
    if risk_pct <= 0 or firm_dd_pct <= 0:
        return 3.0
    total_r = 0.5 * firm_dd_pct / risk_pct
    return max(3.0, round(total_r / math.sqrt(max(1, n_pods)), 2))


def pod_stops(deals: Iterable[Mapping[str, Any]], firm_dd_pct: float, risk_pct: float,
              lookback_days: int = 30, now: datetime | None = None) -> dict[str, Any]:
    now = now or now_utc()
    per: dict[str, list[tuple[str, float]]] = {}
    for d in deals:
        sleeve = str(d.get("sleeve") or "")
        if not sleeve or sleeve.startswith("["):
            continue
        t = str(d.get("time") or "")
        try:
            ts = datetime.fromisoformat(t.replace("Z", "+00:00"))
        except ValueError:
            continue
        if (now - ts).days > lookback_days:
            continue
        pl = d.get("pl_quote")
        risk = d.get("risk_quote")
        if not isinstance(pl, (int, float)) or not isinstance(risk, (int, float)) or not risk:
            continue
        key = f"{d.get('account', '')}:{sleeve}"
        per.setdefault(key, []).append((t, float(pl) / abs(float(risk))))
    stop = pod_stop_r(firm_dd_pct, risk_pct, len(per))
    pods = []
    for key, seq in sorted(per.items()):
        seq.sort()
        eq = peak = dd = 0.0
        for _, r in seq:
            eq += r
            peak = max(peak, eq)
            dd = max(dd, peak - eq)
        cur_dd = peak - eq
        action = "STOP" if cur_dd >= stop else "CUT_HALF" if cur_dd >= 0.5 * stop else "OK"
        pods.append({"pod": key, "deals": len(seq), "net_r": round(eq, 2),
                     "max_dd_r": round(dd, 2), "current_dd_r": round(cur_dd, 2),
                     "stop_r": stop, "action": action})
    return {"mode": "SHADOW", "firm_dd_pct": firm_dd_pct, "risk_pct": risk_pct,
            "lookback_days": lookback_days, "n_pods": len(per), "stop_r": stop,
            "stops": [p["pod"] for p in pods if p["action"] == "STOP"],
            "cuts": [p["pod"] for p in pods if p["action"] == "CUT_HALF"], "pods": pods}


# ------------------------------------------------------------------------------------------
# Careers scout
# ------------------------------------------------------------------------------------------

#: theme -> (regex, lane it feeds). Matched case-insensitively against page text.
CAREER_THEMES: dict[str, tuple[str, str]] = {
    "alternative_data": (r"alternative data|alt[- ]data|satellite|geolocation|web[- ]scrap",
                         "global_alt_data"),
    "nlp_llm": (r"\bnlp\b|natural language|large language model|\bllm", "llm_research_lab"),
    "execution": (r"execution (research|trader|quant)|transaction cost|market impact",
                  "execution_cost"),
    "commodities": (r"commodit|energy trad|metals|agricultur", "asset_horizon_grid"),
    "fx_rates": (r"\bfx\b|foreign exchange|currenc|rates trad|fixed income", "asset_horizon_grid"),
    "asia": (r"china|chinese|japan|korea|hong kong|singapore|india|\bapac\b|asia",
             "asian_retail_forest"),
    "high_frequency": (r"high[- ]frequency|low[- ]latency|\bhft\b|fpga|market making",
                       "execution_cost"),
    "machine_learning": (r"machine learning|deep learning|reinforcement learning",
                         "factor_mining"),
    "risk": (r"risk (quant|manager|analyst)|portfolio construction", "portfolio_risk"),
    "data_engineering": (r"data engineer|data pipeline|data platform", "data_acquisition"),
    "options_vol": (r"options|volatility (trad|research)|derivativ", "asset_horizon_grid"),
}


def career_themes(text: str) -> dict[str, int]:
    low = re.sub(r"<[^>]+>", " ", text).lower()
    return {k: len(re.findall(rx, low)) for k, (rx, _) in CAREER_THEMES.items()
            if re.search(rx, low)}


def career_diff(prev: Mapping[str, Mapping[str, int]], cur: Mapping[str, Mapping[str, int]]
                ) -> list[dict[str, Any]]:
    """Themes that appeared or grew per firm since the last read; each names the lane it feeds."""
    out = []
    for firm, themes in cur.items():
        before = prev.get(firm, {})
        for theme, n in themes.items():
            if n > int(before.get(theme, 0)):
                out.append({"firm": firm, "theme": theme, "lane": CAREER_THEMES[theme][1],
                            "count": n, "was": int(before.get(theme, 0))})
    return out
