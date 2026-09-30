"""THE SUBSYSTEM ADMISSION RULE (principal, 2026-09-29): no new subsystem because it sounds
sophisticated. A subsystem ships only if it carries a MEASURABLE CONTRACT naming at least one of
eight gains, the artifact field that measures it, and the direction that counts as better.

    ALPHA_DISCOVERY      increased effective independent-alpha discovery
    FALSIFICATION        increased falsification power
    INFO_PER_COMPUTE     increased information gain per compute
    FDR_REDUCTION        reduced false-discovery rate
    CALIBRATION          improved live/backtest calibration
    EXECUTION_CAPTURE    improved execution capture
    OPERATIONAL_RISK     reduced operational risk
    PRODUCTIVITY         measurable improvement to research productivity

`evaluate()` turns a contract plus the metric's history into one of three verdicts:

    ADMITTED     the metric moved the declared way by more than its noise, or holds a positive
                 level the contract declares as its bar
    REJECTED     enough history and the metric did not move (or moved the wrong way)
    UNMEASURED   not enough history yet -- a verdict, never a pass and never a reject

A contract is checked twice: statically, by `scripts/check_tier_s_program.py` (every layer row
must carry a well-formed contract, or the law gate fails), and at runtime, by the Tier S organ,
which reads the metric out of the artifact every hour and records the verdict. The self-model
(`libs/tiers/self_model.py`) ranks REJECTED and UNMEASURED layers as the desk's deficiencies.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Gain(StrEnum):
    ALPHA_DISCOVERY = "ALPHA_DISCOVERY"
    FALSIFICATION = "FALSIFICATION"
    INFO_PER_COMPUTE = "INFO_PER_COMPUTE"
    FDR_REDUCTION = "FDR_REDUCTION"
    CALIBRATION = "CALIBRATION"
    EXECUTION_CAPTURE = "EXECUTION_CAPTURE"
    OPERATIONAL_RISK = "OPERATIONAL_RISK"
    PRODUCTIVITY = "PRODUCTIVITY"


class Verdict(StrEnum):
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    UNMEASURED = "UNMEASURED"


#: History needed before a flat metric may be called REJECTED.
MIN_HISTORY = 6


@dataclass(frozen=True)
class Contract:
    gain: Gain
    #: dotted path into the artifact JSON, e.g. "summary.immune_score"
    metric: str
    #: "up" or "down"
    better: str
    #: optional absolute bar: a level at or beyond it counts as ADMITTED on its own
    bar: float | None = None

    @staticmethod
    def parse(raw: Mapping[str, Any]) -> Contract:
        gain = Gain(str(raw["gain"]))
        better = str(raw.get("better", "up"))
        if better not in ("up", "down"):
            raise ValueError(f"contract.better must be up/down, got {better!r}")
        metric = str(raw.get("metric") or "")
        if not metric:
            raise ValueError("contract.metric is required")
        bar = raw.get("bar")
        return Contract(gain, metric, better, None if bar is None else float(bar))


def problems(raw: Any) -> list[str]:
    """Static validation used by the law-gate checker."""
    if not isinstance(raw, Mapping):
        return ["contract missing"]
    out: list[str] = []
    try:
        Contract.parse(raw)
    except (KeyError, ValueError) as exc:
        out.append(f"contract invalid: {exc}")
    return out


def read_metric(doc: Any, path: str) -> float | None:
    cur: Any = doc
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    if isinstance(cur, bool):
        return float(cur)
    if isinstance(cur, (int, float)) and math.isfinite(float(cur)):
        return float(cur)
    return None


def evaluate(contract: Contract, history: Sequence[float]) -> dict[str, Any]:
    """Verdict from the metric's history (oldest first), with the BASELINE it was judged against.

    The baseline is the mean of the earliest half of the readings (the layer's own "before"),
    and `delta_vs_baseline` is the latest reading minus it, signed so positive is better."""
    xs = [float(x) for x in history if x is not None and math.isfinite(float(x))]
    out = _evaluate(contract, xs)
    if xs:
        base = xs[: max(1, len(xs) // 2)]
        b = sum(base) / len(base)
        out["baseline"] = round(b, 8)
        out["delta_vs_baseline"] = round((1.0 if contract.better == "up" else -1.0)
                                         * (xs[-1] - b), 8)
    else:
        out["baseline"] = None
        out["delta_vs_baseline"] = None
    return out


def _evaluate(contract: Contract, xs: list[float]) -> dict[str, Any]:
    sign = 1.0 if contract.better == "up" else -1.0
    if xs and contract.bar is not None and sign * (xs[-1] - contract.bar) >= 0:
        return {"verdict": str(Verdict.ADMITTED), "why": f"latest {xs[-1]:.6g} meets bar "
                f"{contract.bar:.6g}", "n": len(xs)}
    if len(xs) < 2:
        return {"verdict": str(Verdict.UNMEASURED), "why": f"{len(xs)} reading(s)", "n": len(xs)}
    half = len(xs) // 2
    early, late = xs[:half], xs[half:]
    m0, m1 = sum(early) / len(early), sum(late) / len(late)
    pooled = [x - m0 for x in early] + [x - m1 for x in late]
    sd = math.sqrt(sum(p * p for p in pooled) / max(1, len(pooled) - 2)) if len(pooled) > 2 \
        else 0.0
    se = sd * math.sqrt(1 / len(early) + 1 / len(late)) if sd > 0 else 0.0
    delta = sign * (m1 - m0)
    if delta > 0 and (se == 0.0 or delta > 2 * se):
        return {"verdict": str(Verdict.ADMITTED), "why": f"moved {delta:+.6g} ({contract.better})"
                f" beyond 2se={2 * se:.3g}", "n": len(xs)}
    if len(xs) < MIN_HISTORY:
        return {"verdict": str(Verdict.UNMEASURED), "why": f"{len(xs)} < {MIN_HISTORY} readings "
                "and no significant move yet", "n": len(xs)}
    return {"verdict": str(Verdict.REJECTED), "why": f"no significant {contract.better} move "
            f"over {len(xs)} readings (delta {delta:+.6g}, 2se {2 * se:.3g})", "n": len(xs)}
