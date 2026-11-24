"""LLM SIZING SHADOW: does a committee of free models, allowed to resize a live gold trade, grow
the account faster than today's fixed sizing? Measured FORWARD, in shadow, never on orders.

PRINCIPAL 2026-11-03 (zuck), after the "AI investment committee" video: a red-team veto that may
only SHRINK size "can make it timid tho". So three versions run side by side on every live gold
signal, and only growth decides:

    baseline     today's sizing, multiplier 1.0
    shrink_only  min(1, median model multiplier): the committee may cut, never add
    symmetric    clip(median, 0, SYMMETRIC_MAX): it may cut OR add, inside a fixed ceiling

WHY FORWARD AND NOT A BACKTEST. A language model has read about the markets it would be judged
on. Its "view" of a 2024 gold session is contaminated by knowing how 2024 went, so any
historical score flatters it and proves nothing. A deliberation counts here only if it was
written BEFORE its trade closed (`deliberated_at < exit_time`), on a packet that holds bars
strictly before the order was sent and no calendar date.

WHAT IS STORED. `data/llm_sizing/transcripts.jsonl` (append-only): one row per signal, keyed to
the trade, with every model's multiplier, stance and arguments. The loss loop reads the scored
form (`argument_scores` in the report): which model's stance and which side's arguments matched
the realised R.

THE VERDICT. Per variant, per trade: d = log(1 + f*m*R) - log(1 + f*R) at the sleeve's smallest
live risk f. KEEP needs n >= MIN_N and the mean of d above zero by Z standard errors (alpha split
over the two variants: they are two charged trials). DROP when it is below zero by the same bound,
or when shrink_only has a negative mean at n >= MIN_N (a timid veto that costs growth is dropped
without waiting for significance). Otherwise ACCRUING.

THE FENCE. Nothing here reads an account, a key or a ticket into a packet, and nothing writes a
sizing file. The principal's ruling of 2026-09-30 keeps LLMs out of live sizing; a KEEP verdict
is a report row for the principal, never an adoption. Free seats only (`llm_seat`).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
DATA = DESK / "data"
OUT_DIR = DATA / "llm_sizing"
TRANSCRIPTS = OUT_DIR / "transcripts.jsonl"
REPORT = DESK / "reports" / "LLM_SIZING_SHADOW.json"
INTENTS = DATA / "order_intents.jsonl"
FUSION_LEDGER = DATA / "live_ledger.jsonl"
PROP_LEDGER = DATA / "live_ledger_prop.jsonl"

#: Gold window sleeves this shadow deliberates on (the live book).
SLEEVES = ("gold_asia", "gold_london_am", "gold_afternoon")
VARIANTS = ("baseline", "shrink_only", "symmetric")
#: A ceiling on the size-up, well inside the per-trade cap in `mt5desk/sizing.py`
#: (MAX_RISK_FRAC 0.10): 1.5 x the largest live gold risk (FTMO 0.009) is 1.35%.
SYMMETRIC_MAX = 1.5
MULT_RANGE = (0.0, 2.0)
#: The smallest live risk on the gold sleeves (E8 0.006), so growth is never flattered.
RISK_FRAC = 0.006
PANEL = 3
MAX_PER_PASS = 3
#: An intent older than this is not deliberated: its trade may already be running long enough
#: for the bars after the send to leak into "recent" context on a later read.
MAX_AGE = timedelta(hours=6)
CONTEXT_BARS = 48
MIN_N = 30
#: One-sided z at alpha 0.05 / 2 variants.
Z = 1.96

SYSTEM = (
    "You sit on a trading desk's risk committee. A rule-based strategy has already decided to "
    "take the trade below; you decide only how big it should be relative to normal size. "
    "Reply with JSON only: {\"size_multiplier\": number between 0 and 2 (1 = normal size, 0 = "
    "skip), \"stance\": \"cut\"|\"hold\"|\"add\", \"arguments\": [{\"claim\": short text, "
    "\"direction\": \"for\"|\"against\"}]} where direction says whether the claim argues the "
    "trade will work (for) or fail (against). At most five arguments.")


# ------------------------------------------------------------------------------------- io

def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text("utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for ln in text.splitlines():
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def _ts(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        t = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def signal_key(sleeve: str, t: datetime) -> str:
    """One key per sleeve per UTC day: a gold window signals at most once a day, and the books
    that copy it (E8, FTMO, Fusion) share one deliberation and one outcome."""
    return f"{sleeve}|{t.astimezone(UTC).date().isoformat()}"


# ------------------------------------------------------------------------------- packets

def _side(intent: dict[str, Any]) -> int:
    s = str(intent.get("side") or "").lower()
    return 1 if s.startswith("buy") else -1 if s.startswith("sell") else 0


def packet(intent: dict[str, Any], bars: Any = None) -> dict[str, Any] | None:
    """The sanitized question. No account, ticket, lot, server or calendar date ever enters it,
    and only bars that CLOSED before the order was sent."""
    side = _side(intent)
    raw = (intent.get("intended"), intent.get("sl"), intent.get("tp"))
    if not side or not all(isinstance(x, (int, float)) for x in raw):
        return None
    entry, sl, tp = (float(x) for x in raw)  # type: ignore[arg-type]
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    out: dict[str, Any] = {
        "symbol": str(intent.get("symbol") or ""),
        "window": str(intent.get("sleeve") or "").replace("gold_", ""),
        "direction": "long" if side > 0 else "short",
        "order": "stop entry" if "stop" in str(intent.get("side") or "") else "market",
        "target_r": round(abs(tp - entry) / risk, 2),
        "stop_distance_pct": round(100 * risk / entry, 3),
    }
    t = _ts(intent.get("sent_at")) or _ts(intent.get("time"))
    if bars is not None and t is not None:
        try:
            idx = bars.index
            naive = getattr(idx, "tz", None) is None
            limit = t.astimezone(UTC).replace(tzinfo=None) if naive else t
            tail = bars[(idx + timedelta(hours=1)) <= limit].tail(CONTEXT_BARS)
            last = float(tail["close"].iloc[-1])
            out["recent_h1_bars_pct_of_last_close"] = [
                [round(100 * (float(getattr(r, c)) / last - 1), 3)
                 for c in ("open", "high", "low", "close")]
                for r in tail.itertuples()]
            out["entry_vs_last_close_pct"] = round(100 * (entry / last - 1), 3)
        except Exception:
            pass
    return out


def _parse(text: str) -> dict[str, Any] | None:
    s = text.strip()
    a, b = s.find("{"), s.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        d = json.loads(s[a:b + 1])
    except ValueError:
        return None
    m = d.get("size_multiplier")
    if isinstance(m, bool) or not isinstance(m, (int, float)) or not math.isfinite(m):
        return None
    args = [{"claim": str(x.get("claim") or "")[:300],
             "direction": "for" if str(x.get("direction")) == "for" else "against"}
            for x in (d.get("arguments") or [])[:5] if isinstance(x, dict)]
    stance = str(d.get("stance") or "")
    return {"size_multiplier": min(max(float(m), MULT_RANGE[0]), MULT_RANGE[1]),
            "stance": stance if stance in ("cut", "hold", "add") else "hold",
            "arguments": args}


def multipliers(median: float) -> dict[str, float]:
    return {"baseline": 1.0, "shrink_only": min(1.0, median),
            "symmetric": min(max(median, 0.0), SYMMETRIC_MAX)}


# --------------------------------------------------------------------------- deliberation

def _panel() -> list[tuple[str, Callable[[str], tuple[str, str | None]]]]:
    """One chat callable per free model vendor, via the lab's own vendor rotation."""
    from libs.ops import llm_seat
    seat = llm_seat.primary_seat()
    if seat is None:
        return []
    try:
        from research.scientist_tournament import _role_seats
        seats = _role_seats(seat, PANEL)
    except Exception:
        seats = [seat]
    seen: dict[str, Any] = {}
    for s in seats:
        seen.setdefault(s.model, s)

    def _mk(s: Any) -> Callable[[str], tuple[str, str | None]]:
        return lambda p: llm_seat.chat(p, system=SYSTEM, seat=s, max_tokens=1500,
                                       timeout=120.0, temperature=0.2)
    return [(m or "default", _mk(s)) for m, s in seen.items()]


def deliberate(intent: dict[str, Any], *, now: datetime, bars: Any = None,
               panel: list[tuple[str, Callable[[str], tuple[str, str | None]]]] | None = None
               ) -> dict[str, Any] | None:
    pk = packet(intent, bars)
    if pk is None:
        return None
    panel = _panel() if panel is None else panel
    prompt = "Trade:\n" + json.dumps(pk, separators=(",", ":"))
    seats = []
    for model, call in panel:
        text, err = call(prompt)
        got = None if err else _parse(text or "")
        seats.append({"model": model, "error": (err or ("unparsed" if got is None else None)),
                      **(got or {})})
    ok = [s["size_multiplier"] for s in seats if "size_multiplier" in s]
    t = _ts(intent.get("sent_at")) or _ts(intent.get("time")) or now
    row = {
        "key": signal_key(str(intent.get("sleeve")), t),
        "intent_id": intent.get("intent_id"),
        "sleeve": intent.get("sleeve"),
        "intent_at": t.isoformat(timespec="seconds"),
        "deliberated_at": now.isoformat(timespec="seconds"),
        "packet_sha": hashlib.sha256(json.dumps(pk, sort_keys=True).encode()).hexdigest()[:16],
        "packet": pk,
        "seats": seats,
        "median": statistics.median(ok) if ok else None,
        "multipliers": multipliers(statistics.median(ok)) if ok else None,
    }
    return row


def pending(now: datetime, intents: list[dict[str, Any]] | None = None,
            done: set[str] | None = None) -> list[dict[str, Any]]:
    """Placed gold intents young enough to deliberate before their trade can have closed."""
    rows = _jsonl(INTENTS) if intents is None else intents
    done = {str(r.get("key")) for r in _jsonl(TRANSCRIPTS)} if done is None else done
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.get("sleeve") not in SLEEVES or r.get("ticket") in (None, 0) or r.get("status"):
            continue
        t = _ts(r.get("sent_at")) or _ts(r.get("time"))
        if t is None or not (now - MAX_AGE <= t <= now):
            continue
        k = signal_key(str(r["sleeve"]), t)
        if k not in done:
            out.setdefault(k, r)
    return list(out.values())


# -------------------------------------------------------------------------------- scoring

def outcomes(fusion: Path | None = None, prop: Path | None = None
             ) -> dict[str, dict[str, Any]]:
    """key -> {r, exit_time}: the mean realised R across every book that took the signal and
    the EARLIEST exit, so a deliberation must predate every copy's close."""
    acc: dict[str, dict[str, Any]] = {}
    for p in (fusion or FUSION_LEDGER, prop or PROP_LEDGER):
        for r in _jsonl(p):
            sl, rm = r.get("sleeve"), r.get("r_multiple")
            t, x = _ts(r.get("entry_time")) or _ts(r.get("time")), _ts(r.get("exit_time"))
            if (sl not in SLEEVES or t is None or x is None or r.get("r_unreconstructible")
                    or isinstance(rm, bool) or not isinstance(rm, (int, float))):
                continue
            a = acc.setdefault(signal_key(str(sl), t), {"rs": [], "exit": x})
            a["rs"].append(float(rm))
            a["exit"] = min(a["exit"], x)
    return {k: {"r": sum(v["rs"]) / len(v["rs"]), "exit_time": v["exit"]}
            for k, v in acc.items()}


def _dlogw(r: float, m: float, f: float = RISK_FRAC) -> float:
    return math.log1p(max(f * m * r, -0.999)) - math.log1p(max(f * r, -0.999))


def score(transcripts: list[dict[str, Any]], outs: dict[str, dict[str, Any]]
          ) -> dict[str, Any]:
    scored = []
    stale = 0
    for row in transcripts:
        o = outs.get(str(row.get("key")))
        da = _ts(row.get("deliberated_at"))
        if not o or not row.get("multipliers") or da is None:
            continue
        if da >= o["exit_time"]:
            stale += 1          # written after the close: never evidence
            continue
        scored.append((row, o["r"]))
    variants: dict[str, Any] = {}
    for v in VARIANTS:
        ds = [_dlogw(r, float(row["multipliers"][v])) for row, r in scored]
        n = len(ds)
        mean = sum(ds) / n if n else None
        se = (statistics.stdev(ds) / math.sqrt(n)) if n >= 2 else None
        if v == "baseline":
            verdict = "REFERENCE"
        elif n < MIN_N or mean is None:
            verdict = "ACCRUING"
        elif se is not None and se > 0 and mean - Z * se > 0:
            verdict = "KEEP"
        elif (se is not None and mean + Z * se < 0) or (v == "shrink_only" and mean < 0):
            verdict = "DROP"
        else:
            verdict = "ACCRUING"
        variants[v] = {"n": n, "sum_dlogw": round(sum(ds), 6) if n else 0.0,
                       "mean_dlogw": round(mean, 7) if mean is not None else None,
                       "se": round(se, 7) if se is not None else None, "verdict": verdict}
    models: dict[str, dict[str, int]] = {}
    args = {"for": [0, 0], "against": [0, 0]}
    for row, r in scored:
        for s in row.get("seats") or []:
            if s.get("stance") in ("cut", "add"):   # a hold makes no call to score
                m = models.setdefault(str(s.get("model")), {"n": 0, "right": 0})
                m["n"] += 1
                m["right"] += int((s["stance"] == "add") == (r > 0))
            for a in s.get("arguments") or []:
                d = a.get("direction")
                if d in args:
                    args[d][0] += 1
                    args[d][1] += int((d == "for") == (r > 0))
    return {"scored": len(scored), "written_after_close": stale, "variants": variants,
            "argument_scores": {
                "by_model_stance": models,
                "by_direction": {d: {"n": n, "matched_outcome": k} for d, (n, k) in args.items()}}}


# ----------------------------------------------------------------------------------- pass

def _append(row: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with TRANSCRIPTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def run(now: datetime | None = None, *, panel: list[Any] | None = None,
        bars_loader: Callable[[str], Any] | None = None) -> dict[str, Any]:
    """Deliberate on new signals, score the closed ones, write the report. Never raises."""
    t = now or datetime.now(UTC)
    err = None
    new = 0
    try:
        todo = pending(t)[:MAX_PER_PASS]
        if todo:
            if bars_loader is None:
                from mt5desk.mass_screen_rules import load_bars
                bars_loader = load_bars
            if panel is None:
                panel = _panel()
            if not panel:
                err = "UNMEASURED: no free seat reachable"
            for intent in todo if panel else []:
                row = deliberate(intent, now=t, bars=bars_loader(str(intent.get("symbol"))),
                                 panel=panel)
                if row is not None:
                    _append(row)
                    new += 1
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"[:200]
    rows = _jsonl(TRANSCRIPTS)
    doc = {"at": t.isoformat(timespec="seconds"), "transcripts": len(rows),
           "deliberated_this_pass": new, "error": err, "risk_frac": RISK_FRAC,
           "symmetric_max": SYMMETRIC_MAX, "min_n": MIN_N, "trials_charged": 2,
           "live_effect": "NONE: shadow only; adoption needs the principal's word "
                          "(LLMs off live sizing, ruling 2026-09-30)",
           **score(rows, outcomes())}
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, REPORT)
    except OSError:
        pass
    return doc
