"""A model ranks the whole universe at once, and the ranking is scored, not trusted.

WHY CROSS-SECTIONAL, AND WHY THAT IS THE WHOLE DESIGN

Inference is a FIXED cost per call. Realised return scales with how many
decisions the call informs. One read per instrument on 22 instruments is 22
calls to inform 22 decisions; one read OVER 22 instruments is one call to
inform the same 22. The cost per decision falls by a factor of 22 and nothing
about the information is worse -- if anything a ranker sees more, because
relative attractiveness is the thing a portfolio actually needs and it is
exactly what a per-instrument read cannot express.

It also matches where the value is. The fundamental law says IR ~ IC * sqrt(B).
Measured effective breadth across this universe is 5.64 independent axes, not
22 -- the JPY crosses move together and pretending otherwise is how a desk
believes it has four times the diversification it owns. A ranker is a bet on
the SPREAD between the top and the bottom of a list, which is the quantity
breadth actually multiplies.

EVERY NUMBER IN THE BRIEF IS A RATIO

Gold at 4,500 and EURUSD at 1.08 have to be comparable in one list or the
ranking is meaningless. So the brief carries moves in ATRs, ranges against
their own trailing medians, and positions within their own recent range --
never a price and never a pip. This is the same discipline as trendday.py and
for the same reason.

THE PART THAT MATTERS MOST: IT IS FALSIFIABLE

An LLM ranker that nobody can score is a very expensive random number
generator, and it will feel insightful the entire time it loses money. So:

  A DETERMINISTIC BASELINE ships alongside it and costs nothing. The model is
  not competing against zero, it is competing against `BaselineRanker`, which
  ranks on measured trend strength. Beating nothing is not a result.

  EVERY READ IS RECORDED with the brief that produced it, so a different model
  can be replayed over identical states. Comparing two models on whatever
  markets each happened to see is not a comparison.

  THE BRIEF IS LEAK-TESTED. tests/ corrupts every bar after i and requires the
  brief built at i to be byte-identical. A ranker fed one forward-looking field
  will post a spectacular IC and cost real money.

  A READ THAT DOES NOT PARSE IS AN ERROR. Never a partial ranking, never a
  default, never "no opinion" silently recorded as flat.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, Sequence

import numpy as np
import pandas as pd

from .trendday import atr, read as trend_read

__all__ = ["InstrumentState", "RankBrief", "Pick", "RankRead", "Ranker",
           "BaselineRanker", "ClaudeCodeRanker", "build_brief", "RankError"]


class RankError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstrumentState:
    """One row of the cross-section. Dimensionless throughout."""
    symbol: str
    strength: float          # 0..1 trendiness
    direction: int           # -1 / 0 / +1
    dying: bool
    er: float                # efficiency ratio
    expansion: float         # ATR vs its own trailing median
    ret_1: float             # last bar's move, in ATRs
    ret_6: float             # 6-bar move, in ATRs
    ret_24: float            # 24-bar move, in ATRs
    pos_in_range: float      # 0 = at the 20-bar low, 1 = at the 20-bar high
    vol_pct: float           # ATR's percentile in its own trailing history

    def render(self) -> str:
        return (f"{self.symbol:<8} str={self.strength:.2f} dir={self.direction:+d} "
                f"{'DYING ' if self.dying else '      '}"
                f"er={self.er:.2f} exp={self.expansion:.2f} "
                f"r1={self.ret_1:+.2f} r6={self.ret_6:+.2f} r24={self.ret_24:+.2f} "
                f"pos={self.pos_in_range:.2f} volpct={self.vol_pct:.2f}")


@dataclass(frozen=True)
class RankBrief:
    as_of: pd.Timestamp
    rows: tuple[InstrumentState, ...]
    top_n: int = 5

    def symbols(self) -> tuple[str, ...]:
        return tuple(r.symbol for r in self.rows)

    def render(self) -> str:
        head = (
            f"UTC {self.as_of.isoformat()}\n"
            f"{len(self.rows)} instruments, H1. Every field is dimensionless so "
            f"they are directly comparable: moves are in ATRs, exp is ATR "
            f"against its own trailing median, pos is position in the 20-bar "
            f"range (0=low, 1=high), volpct is this ATR's percentile in its own "
            f"history. No prices appear on purpose.\n\n")
        body = "\n".join(r.render() for r in self.rows)
        tail = (
            f"\n\nRank the {self.top_n} instruments with the strongest expected "
            f"move over the next 24 bars, best first. For each give side "
            f"(LONG or SHORT) and conviction 1-5. You may return fewer than "
            f"{self.top_n} if fewer are worth taking; returning none is a valid "
            f"and sometimes correct answer. Judge them against each other, not "
            f"against zero.")
        return head + body + tail


@dataclass(frozen=True)
class Pick:
    symbol: str
    side: int            # +1 long, -1 short
    conviction: int      # 1..5


@dataclass(frozen=True)
class RankRead:
    picks: tuple[Pick, ...]
    ranker: str
    model: str
    latency_ms: float = 0.0
    usage: dict = field(default_factory=dict)
    note: str = ""

    def as_weights(self, symbols: Sequence[str]) -> np.ndarray:
        """Signed conviction per symbol, normalised to unit gross exposure.

        Unit GROSS, not unit net: a ranker that likes three longs and two shorts
        is expressing a spread, and normalising by net would silently lever it
        up as the book approached market-neutral -- which is precisely when a
        cross-sectional signal is at its most useful and least risky.
        """
        w = np.zeros(len(symbols), float)
        idx = {s: i for i, s in enumerate(symbols)}
        for p in self.picks:
            if p.symbol in idx:
                w[idx[p.symbol]] = p.side * p.conviction
        gross = np.abs(w).sum()
        return w / gross if gross > 0 else w


# ------------------------------------------------------------------- brief

def build_brief(frames: dict[str, pd.DataFrame], i: int, *, top_n: int = 5,
                lookback: int = 240) -> RankBrief:
    """The cross-section at bar `i`, using bars at or before `i` only.

    `frames` must be index-aligned; the caller owns that, because silently
    reindexing here would paper over a data bug that matters far more than this
    function does.
    """
    rows: list[InstrumentState] = []
    as_of = None
    for sym in sorted(frames):
        df = frames[sym]
        if i >= len(df) or i < 30:
            continue
        w = df.iloc[:i + 1]
        h = w["high"].to_numpy(float)
        l = w["low"].to_numpy(float)
        c = w["close"].to_numpy(float)
        a = atr(h, l, c)
        if not np.isfinite(a[-1]) or a[-1] <= 0:
            continue
        tr = trend_read(w)
        as_of = w.index[-1]
        lo20, hi20 = float(l[-20:].min()), float(h[-20:].max())
        span = hi20 - lo20
        hist = a[np.isfinite(a)][-lookback:]
        rows.append(InstrumentState(
            symbol=sym,
            strength=float(tr.strength[-1]),
            direction=int(tr.direction[-1]),
            dying=bool(tr.dying[-1]),
            er=float(tr.er[-1]) if np.isfinite(tr.er[-1]) else 0.0,
            expansion=float(tr.expansion[-1]) if np.isfinite(tr.expansion[-1]) else 1.0,
            ret_1=float((c[-1] - c[-2]) / a[-1]),
            ret_6=float((c[-1] - c[-7]) / a[-1]) if len(c) > 7 else 0.0,
            ret_24=float((c[-1] - c[-25]) / a[-1]) if len(c) > 25 else 0.0,
            pos_in_range=float((c[-1] - lo20) / span) if span > 0 else 0.5,
            vol_pct=float((hist < a[-1]).mean()) if len(hist) > 10 else 0.5,
        ))
    if as_of is None:
        raise RankError(f"no instrument had usable data at index {i}")
    return RankBrief(as_of=as_of, rows=tuple(rows), top_n=top_n)


# ----------------------------------------------------------------- rankers

class Ranker(Protocol):
    name: str
    model: str

    def rank(self, brief: RankBrief) -> RankRead: ...


class BaselineRanker:
    """Free, deterministic, and the thing the model has to beat.

    Ranks on measured trend strength in the detected direction, skipping
    anything the detector calls dying. This is not a strawman: strength is the
    one property already shown to predict forward move across 22 instruments.
    A language model that cannot beat it is not paying for itself, and without
    this the comparison would be against zero, which flatters everything.
    """

    name = "baseline"
    model = "trend-strength"

    def rank(self, brief: RankBrief) -> RankRead:
        live = [r for r in brief.rows if r.direction != 0 and not r.dying]
        live.sort(key=lambda r: r.strength, reverse=True)
        picks = tuple(
            Pick(r.symbol, r.direction,
                 int(np.clip(round(1 + 4 * r.strength), 1, 5)))
            for r in live[:brief.top_n])
        return RankRead(picks=picks, ranker=self.name, model=self.model,
                        note=f"{len(live)} instruments trending, top "
                             f"{len(picks)} taken")


_SCHEMA = ('{"picks":[{"symbol":"<one of the symbols above>",'
           '"side":"LONG|SHORT","conviction":1}],"note":"<one short sentence>"}')


class ClaudeCodeRanker:
    """The model, reached through the Claude Code CLI so a subscription pays.

    The CLI has no structured-output mode and returns its answer inside a
    markdown fence even when told not to -- both observed against 2.1.235, not
    inferred -- so the schema is asked for in-band, the fence is stripped, and
    the result is validated. Anything that does not validate raises.
    """

    name = "claudecode"

    _SYSTEM = (
        "You are a systematic cross-sectional ranker on an FX/metals/crypto "
        "universe. You are given dimensionless state for every instrument and "
        "you rank them against each other. You output JSON and nothing else.\n"
        "Rules you must not break:\n"
        "- Only symbols present in the input may appear in the output.\n"
        "- Returning fewer picks, or none, is correct when the cross-section "
        "is flat. Do not manufacture conviction to fill slots.\n"
        "- conviction is 1-5 and must reflect the SPREAD between this "
        "instrument and the rest of the list, not your confidence in a "
        "narrative about it.\n"
        "- You cannot see prices, news or dates. Do not pretend to.")

    def __init__(self, model: str = "claude-opus-5", binary: str = "claude",
                 timeout_s: float = 300.0, billed: Optional[bool] = None,
                 runner: Any = None):
        self.model, self.binary, self.timeout_s = model, binary, timeout_s
        self._billed, self._runner = billed, runner

    def billed(self) -> bool:
        if self._billed is not None:
            return self._billed
        return bool((os.environ.get("ANTHROPIC_API_KEY") or "").strip())

    @staticmethod
    def _unfence(t: str) -> str:
        s = t.strip()
        if not s.startswith("```"):
            return s
        s = s.split("\n", 1)[1] if "\n" in s else ""
        return s.rsplit("```", 1)[0].strip() if "```" in s else s.strip()

    def _argv(self) -> list[str]:
        return [self.binary, "-p", "--output-format", "json",
                "--model", self.model, "--system-prompt", self._SYSTEM,
                "--allowed-tools", "", "--max-turns", "1"]

    def _env(self) -> dict:
        env = dict(os.environ)
        if not self.billed():
            env.pop("ANTHROPIC_API_KEY", None)
            env.pop("ANTHROPIC_AUTH_TOKEN", None)
        return env

    def _invoke(self, prompt: str) -> dict:
        if self._runner is not None:
            return self._runner(self._argv(), prompt)
        try:
            p = subprocess.run(self._argv(), input=prompt, env=self._env(),
                               capture_output=True, text=True,
                               timeout=self.timeout_s)
        except FileNotFoundError as e:
            raise RankError(f"{self.binary!r} not found; install Claude Code "
                            f"and log in once, or use BaselineRanker") from e
        except subprocess.TimeoutExpired as e:
            raise RankError(f"claude timed out after {self.timeout_s}s") from e
        if p.returncode != 0:
            raise RankError(f"claude exited {p.returncode}: "
                            f"{(p.stderr or p.stdout)[:300]}")
        try:
            return json.loads(p.stdout)
        except json.JSONDecodeError as e:
            raise RankError(f"claude did not return JSON: {p.stdout[:300]!r}") from e

    def rank(self, brief: RankBrief) -> RankRead:
        import time
        prompt = (f"Return ONLY JSON of exactly this shape, no prose, no "
                  f"markdown fences:\n{_SCHEMA}\n\n{brief.render()}")
        t0 = time.monotonic()
        env = self._invoke(prompt)
        dt = (time.monotonic() - t0) * 1000
        if env.get("is_error") or env.get("subtype") not in (None, "success"):
            raise RankError(f"claude reported failure: {env.get('subtype')}")
        if env.get("permission_denials"):
            raise RankError(f"claude wanted a tool it does not have: "
                            f"{env['permission_denials']}")
        try:
            body = json.loads(self._unfence(str(env.get("result") or "")))
        except json.JSONDecodeError as e:
            raise RankError(f"result was not JSON: "
                            f"{str(env.get('result'))[:300]!r}") from e

        allowed = set(brief.symbols())
        picks: list[Pick] = []
        seen: set[str] = set()
        for p in (body.get("picks") or []):
            sym = str(p.get("symbol", ""))
            if sym not in allowed:
                # Refuses rather than dropping: a hallucinated symbol means the
                # read was not grounded in the brief, which taints the picks
                # that DID validate just as much as the one that did not.
                raise RankError(f"ranked {sym!r}, which was not in the brief")
            if sym in seen:
                raise RankError(f"ranked {sym!r} twice")
            seen.add(sym)
            side = str(p.get("side", "")).upper()
            if side not in ("LONG", "SHORT"):
                raise RankError(f"bad side {side!r} for {sym}")
            conv = p.get("conviction")
            if not isinstance(conv, int) or not 1 <= conv <= 5:
                raise RankError(f"bad conviction {conv!r} for {sym}")
            picks.append(Pick(sym, 1 if side == "LONG" else -1, conv))
        if len(picks) > brief.top_n:
            raise RankError(f"returned {len(picks)} picks, asked for at most "
                            f"{brief.top_n}")

        u = env.get("usage") or {}
        fresh = int(u.get("input_tokens") or 0)
        created = int(u.get("cache_creation_input_tokens") or 0)
        cached = int(u.get("cache_read_input_tokens") or 0)
        billed = self.billed()
        return RankRead(
            picks=tuple(picks), ranker=self.name, model=self.model,
            latency_ms=dt, note=str(body.get("note", ""))[:200],
            usage={"in": fresh + created + cached, "cache_read": cached,
                   "out": int(u.get("output_tokens") or 0), "billed": billed,
                   "cost_usd_api_equivalent": env.get("total_cost_usd"),
                   "cost_usd": env.get("total_cost_usd") if billed else 0.0})
