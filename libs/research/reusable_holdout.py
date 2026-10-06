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

IT FAILS CLOSED (audit, 2026-10-06). A missing, unreadable or malformed state file reads as
EXHAUSTED -- deleting the file must never refill the budget -- and a pass whose charge cannot be
saved answers nothing. A study is opened once: the append-only register beside the state
(`register_path`) records every opening, so a state file restored to its tracked stub cannot
hand an old study a new budget. The state file is created once (`init_state`) and is tracked.
The noise is drawn from OS entropy: seeding it from the committed state made a repeated question
get an identical answer, which is exactly the leak the noise is there to close.

ROTATION, NOT A PERMANENT FREEZE. `rotate` retires the row keys an exhausted study was asked
about and opens the next epoch of the same study on rows it has never seen, with a fresh budget.
Epochs and retired keys live in the register too, so no restore can rewind them.
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


def _load(path: Path) -> dict[str, Any] | None:
    """The state, or None when it is missing, unreadable or malformed (callers fail closed)."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    for k, st in doc.items():
        if k.startswith("_"):
            continue
        if not isinstance(st, dict):
            return None
        for f in ("budget_left", "questions"):
            if f in st and (isinstance(st[f], bool) or not isinstance(st[f], int)):
                return None
    return doc


def register_path(state_path: Path) -> Path:
    """The append-only register of every study ever opened, beside the state file."""
    return state_path.with_name(state_path.stem + "_studies.jsonl")


def _open_study(state_path: Path, study: str) -> str | None:
    """Record `study` as opened. None on success; the reason when it must stay closed."""
    reg = register_path(state_path)
    try:
        seen = {json.loads(ln).get("study") for ln in reg.read_text("utf-8").splitlines()
                if ln.strip()}
    except FileNotFoundError:
        seen = set()
    except (OSError, ValueError, AttributeError) as exc:
        return f"{reg.name} unreadable ({type(exc).__name__}): no study is opened blind"
    if study in seen:
        return (f"{study} was opened before and its budget is gone from {state_path.name}: "
                "a restored or rewritten state file never refills a study")
    try:
        reg.parent.mkdir(parents=True, exist_ok=True)
        with reg.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"study": study, "opened_at": datetime.now(tz=UTC).isoformat(
                timespec="seconds")}) + "\n")
    except OSError as exc:
        return f"{reg.name} unwritable ({type(exc).__name__}): the opening is not recorded"
    return None


def init_state(path: Path | None = None) -> bool:
    """Create the state file once. Never overwrites: an existing file, valid or not, stays."""
    p = path or STATE
    if p.exists():
        return False
    _save(p, {"_created": datetime.now(tz=UTC).isoformat(timespec="seconds")})
    return True


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
    loaded = _load(path)
    if loaded is None and not path.exists() and _register(path) is not None:
        # A missing state file with a readable register is safe to recreate: every study the
        # register has seen stays closed below, so only a never-opened study gets a budget.
        loaded = {}
    if loaded is None:
        return {"study": study, "answers": dict.fromkeys(queries), "overfit": [],
                "budget_left": 0, "budget": budget, "questions_total": None,
                "status": "EXHAUSTED", "state_error": f"{path.name} malformed, or missing with "
                "its register unreadable: the budget fails closed"}
    doc = loaded
    if study not in doc:
        # A FRESH BUDGET ONLY FOR A STUDY NEVER OPENED. The state file can be restored from git
        # (its tracked stub parses and holds no study), so absence from it proves nothing; the
        # append-only register beside it does. A study the register has seen and the state has
        # lost reads EXHAUSTED; an unreadable register opens nothing.
        why = _open_study(path, study)
        if why:
            return {"study": study, "answers": dict.fromkeys(queries), "overfit": [],
                    "budget_left": 0, "budget": budget, "questions_total": None,
                    "status": "EXHAUSTED", "state_error": why}
    st = dict(doc.get(study) or {})
    left = int(st.get("budget_left", budget))
    asked = int(st.get("questions", 0))
    rng = np.random.default_rng(seed)               # None -> OS entropy
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
    except OSError as exc:
        # An uncharged answer is a free look at the holdout: the pass answers nothing.
        return {"study": study, "answers": dict.fromkeys(queries), "overfit": [],
                "budget_left": 0, "budget": budget, "questions_total": asked,
                "status": "EXHAUSTED", "state_error": f"{type(exc).__name__}: {exc}"}
    return {"study": study, "answers": answers, "overfit": overfit, "budget_left": left,
            "budget": budget, "questions_total": asked,
            "status": "EXHAUSTED" if left <= 0 else "VALID", "state_error": None}


def _register(state_path: Path) -> list[dict[str, Any]] | None:
    """The register's rows; [] when it does not exist yet, None when it cannot be read."""
    try:
        rows = [json.loads(ln) for ln in register_path(state_path).read_text("utf-8").splitlines()
                if ln.strip()]
    except FileNotFoundError:
        return []
    except (OSError, ValueError):
        return None
    return [r for r in rows if isinstance(r, dict)]


def epoch(base: str, state_path: Path | None = None) -> tuple[str, set[str]]:
    """(the current study name for `base`, the row keys earlier epochs retired). Read from the
    append-only register, so restoring the state file cannot rewind an epoch or un-retire a row."""
    rows = _register(state_path or STATE) or []
    rot = [r for r in rows if r.get("rotate") == base and isinstance(r.get("epoch"), int)]
    n = max((int(r["epoch"]) for r in rot), default=0)
    return f"{base}@{n}", {str(k) for r in rot for k in r.get("retired_keys") or []}


def rotate(base: str, used_keys: set[str], state_path: Path | None = None) -> str | None:
    """Retire `used_keys` and open the next epoch, appended to the register. Returns the new
    study name, or None when the register cannot be read or written (the study then stays
    exhausted -- closed, never reopened)."""
    path = state_path or STATE
    if _register(path) is None:
        return None
    name, _retired = epoch(base, path)
    n = int(name.rsplit("@", 1)[1]) + 1
    try:
        reg = register_path(path)
        reg.parent.mkdir(parents=True, exist_ok=True)
        with reg.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"rotate": base, "epoch": n,
                                 "retired_keys": sorted(str(k) for k in used_keys),
                                 "at": datetime.now(tz=UTC).isoformat(timespec="seconds")})
                     + "\n")
    except OSError:
        return None
    return f"{base}@{n}"
