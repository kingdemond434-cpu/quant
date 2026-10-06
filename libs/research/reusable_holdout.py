"""THE REUSABLE HOLDOUT: a held-out half that can be asked many adaptive questions and still
mean something (Dwork, Feldman, Hardt, Pitassi, Reingold, Roth, "The reusable holdout",
Science 2015 -- Thresholdout).

THE DEFECT. An hourly organ that picks a winner from recorded rows asks the SAME rows the same
question every hour, and every answer shapes the next question. That is adaptive data analysis:
after enough rounds the winner is fitted to those rows' noise and the reported number is no
longer an estimate of anything. A lockbox opened once (`libs/research/lockbox.py`) protects one
final verdict; it does not protect a selection rule that runs forever.

THE MECHANISM. Each question is answered on the TRAINING half unless the holdout half disagrees
by more than a noisy threshold -- then the (noised) holdout value is returned and one unit of the
study's budget is spent. While the budget lasts, the answers are valid estimates whatever the
sequence of questions was; when it is gone the study is EXHAUSTED and says so, and the caller
must stop selecting on these rows (rotate in fresh ones), never quietly keep going.

STATE IS PER STUDY and persistent, so the budget is charged across passes, not per pass: a study
that reset its budget every hour would be a lockbox with the lock removed.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

STATE = Path(__file__).resolve().parents[2] / "desks" / "mt5" / "data" / "reusable_holdout.json"

#: Defaults from the paper's worked setting, as fractions of the quantity's own scale.
THRESHOLD = 0.04
SIGMA = 0.01
BUDGET = 64


def split(key: str) -> str:
    """'train' or 'holdout', fixed forever per row key: a row never changes side."""
    return "holdout" if int(hashlib.sha1(key.encode()).hexdigest(), 16) % 2 else "train"


def _load(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def thresholdout(study: str, queries: Mapping[str, tuple[float, float]], *, scale: float,
                 threshold: float = THRESHOLD, sigma: float = SIGMA, budget: int = BUDGET,
                 seed: int | None = None, state_path: Path | None = None) -> dict[str, Any]:
    """Answer each query (train_value, holdout_value) through Thresholdout.

    `scale` puts the threshold and noise in the quantity's own units (e.g. the mean of the train
    values). Returns {answers, overfit, budget_left, status} and charges the persistent budget."""
    path = state_path or STATE
    doc = _load(path)
    st = dict(doc.get(study) or {})
    left = int(st.get("budget_left", budget))
    asked = int(st.get("questions", 0))
    rng = np.random.default_rng(seed if seed is not None else asked + 7919 * left)
    s = abs(float(scale)) or 1.0
    t_hat = threshold * s + rng.laplace(0.0, 2 * sigma * s)
    answers: dict[str, float | None] = {}
    overfit: list[str] = []
    for name, (tr, ho) in queries.items():
        asked += 1
        if left <= 0:
            answers[name] = None
            continue
        if abs(float(tr) - float(ho)) > t_hat + rng.laplace(0.0, 4 * sigma * s):
            left -= 1
            overfit.append(name)
            answers[name] = float(ho) + float(rng.laplace(0.0, sigma * s))
            t_hat = threshold * s + rng.laplace(0.0, 2 * sigma * s)
        else:
            answers[name] = float(tr)
    st.update(budget_left=left, questions=asked, budget=budget,
              overfit_total=int(st.get("overfit_total", 0)) + len(overfit),
              last_at=datetime.now(tz=UTC).isoformat(timespec="seconds"))
    doc[study] = st
    try:
        _save(path, doc)
        err = None
    except OSError as exc:
        err = f"{type(exc).__name__}: {exc}"
    return {"study": study, "answers": answers, "overfit": overfit, "budget_left": left,
            "budget": budget, "questions_total": asked,
            "status": "EXHAUSTED" if left <= 0 else "VALID", "state_error": err}
