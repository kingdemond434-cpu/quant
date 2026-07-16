"""Forecast calibration -- log every probability forecast, score it when the outcome resolves.

The constitution (Phase 9) requires continuously calibrating forecasts of Engineering ROI, alpha
survival, and deployment success via Bayesian updating, and detecting systematic bias. This is the
persistent scoring layer: each forecast (engineering-task p_success, alpha survival prob, leverage
confidence) is stored by id; when the outcome later resolves (task done, alpha survived/killed)
it is scored. Calibration = Brier score + a Beta(a,b) posterior over hit-rate + a bias term
(mean forecast - mean outcome). Until enough outcomes resolve it honestly reports insufficient data
-- no fabricated calibration. Pure/deterministic; the store is data/forecast_log.json.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOG = Path("data/forecast_log.json")


def _load() -> dict[str, Any]:
    try:
        return json.loads(_LOG.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"forecasts": {}}


def _save(d: dict[str, Any]) -> None:
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    _LOG.write_text(json.dumps(d, indent=2), "utf-8")


def log_forecast(key: str, p: float, kind: str) -> None:
    """Record (or refresh, while unresolved) a probability forecast keyed by a stable id."""
    d = _load()
    f = d["forecasts"].get(key, {})
    if f.get("resolved"):
        return                                            # never overwrite a scored forecast
    f.update({"p": round(float(p), 4), "kind": kind,
              "updated": datetime.now(tz=UTC).isoformat()})
    d["forecasts"][key] = f
    _save(d)


def resolve(key: str, outcome: bool) -> None:
    """Mark a forecast's outcome (True = the predicted event happened). Idempotent."""
    d = _load()
    f = d["forecasts"].get(key)
    if not f or f.get("resolved"):
        return
    f["resolved"] = True
    f["outcome"] = 1.0 if outcome else 0.0
    f["resolved_at"] = datetime.now(tz=UTC).isoformat()
    _save(d)


def report() -> dict[str, Any]:
    """Calibration over resolved forecasts: Brier, hit-rate posterior, bias. N-gated (honest)."""
    d = _load()
    res = [f for f in d["forecasts"].values() if f.get("resolved")]
    n = len(res)
    if n < 5:
        return {"n_resolved": n, "status": f"insufficient outcomes ({n}/5) -- accumulating",
                "brier": None, "reliability": None, "bias": None, "hit_rate_posterior": None}
    brier = sum((f["p"] - f["outcome"]) ** 2 for f in res) / n
    bias = sum(f["p"] - f["outcome"] for f in res) / n     # + = over-confident, - = under-confident
    hits = sum(1 for f in res if (f["p"] >= 0.5) == (f["outcome"] >= 0.5))
    # Beta(1,1) prior updated with hits/misses -> posterior mean hit-rate
    a, b = 1 + hits, 1 + (n - hits)
    return {
        "n_resolved": n, "status": "calibrated",
        "brier": round(brier, 4), "reliability": round(1 - brier, 4),
        "bias": round(bias, 4),
        "bias_label": ("over-confident" if bias > 0.05 else
                       "under-confident" if bias < -0.05 else "well-calibrated"),
        "hit_rate_posterior": round(a / (a + b), 3),
        "note": ("Brier lower=better; reliability=1-Brier; bias>0 means forecasts were too high. "
                 "Applied as a shrinkage on future p_success when |bias| is material."),
    }
