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

IT FAILS CLOSED (audit, 2026-10-06). A malformed state file reads EXHAUSTED, a missing one is
rebuilt from the register (never refilled), and a pass whose charge cannot be written answers
nothing. THE REGISTER IS THE LEDGER: an append-only file beside the state
(`register_path`, tracked, on the box's state wire) records every study opened, every charge
and every epoch rotated, and a study's budget is the SMALLER of what the state and the register
say -- so restoring either file from git, deleting the state, or an older snapshot of it can
never refill a study. A missing or unreadable register answers nothing.
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
    """The append-only register beside the state file: every study opened, every charge, every
    epoch rotated. Tracked (a stub ships) and under desks/mt5/data/, so it rides the box's state
    wire; the state file is only a cache of what the register already proves."""
    return state_path.with_name(state_path.stem + "_studies.jsonl")


def _register(state_path: Path) -> list[dict[str, Any]] | None:
    """The register's rows, or None when it is missing or unreadable (callers fail closed)."""
    try:
        rows = [json.loads(ln) for ln in register_path(state_path).read_text("utf-8").splitlines()
                if ln.strip()]
    except (OSError, ValueError):
        return None
    return [r for r in rows if isinstance(r, dict)]


def _append(state_path: Path, row: Mapping[str, Any]) -> None:
    reg = register_path(state_path)
    with reg.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({**row, "at": datetime.now(tz=UTC).isoformat(timespec="seconds")})
                 + "\n")


def _register_left(rows: list[dict[str, Any]], study: str, budget: int) -> tuple[int, bool]:
    """(budget left by the register's own charges, whether the study was ever opened)."""
    opened = [r for r in rows if r.get("study") == study]
    b = next((int(r["budget"]) for r in opened if isinstance(r.get("budget"), int)), budget)
    spent = sum(int(r.get("spent") or 0) for r in rows if r.get("charge") == study)
    return b - spent, bool(opened)


def init_state(path: Path | None = None) -> bool:
    """Create the state file and its register once. Never overwrites an existing file."""
    p = path or STATE
    made = False
    stamp = datetime.now(tz=UTC).isoformat(timespec="seconds")
    if not p.exists():
        _save(p, {"_created": stamp})
        made = True
    reg = register_path(p)
    if not reg.exists():
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text(json.dumps({"_created": stamp}) + "\n", encoding="utf-8")
        made = True
    return made


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

    def closed(why: str, asked: int | None = None) -> dict[str, Any]:
        return {"study": study, "answers": dict.fromkeys(queries), "overfit": [],
                "budget_left": 0, "budget": budget, "questions_total": asked,
                "status": "EXHAUSTED", "state_error": why}
    reg = _register(path)
    if reg is None:
        return closed(f"{register_path(path).name} missing or unreadable: the budget fails "
                      "closed (the register, not the state file, proves what was spent)")
    loaded = _load(path)
    if loaded is None and path.exists():
        return closed(f"{path.name} malformed: the budget fails closed")
    doc = loaded or {}                      # a missing state file is recreated from the register
    reg_left, opened = _register_left(reg, study, budget)
    if not opened:
        try:
            _append(path, {"study": study, "budget": budget})
        except OSError as exc:
            return closed(f"register unwritable ({type(exc).__name__}): not opened blind")
    st = dict(doc.get(study) or {})
    # THE SMALLER OF THE TWO WITNESSES: an older state snapshot cannot refill what the register
    # recorded as spent, and a register restored to its stub cannot refill what the state holds.
    left = min(int(st.get("budget_left", budget)), reg_left)
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
        # The charge lands in the register FIRST: an uncharged answer is a free look at the
        # holdout, so a pass whose charge cannot be written answers nothing.
        _append(path, {"charge": study, "spent": len(overfit), "asked": len(queries)})
        _save(path, doc)
    except OSError as exc:
        return closed(f"{type(exc).__name__}: {exc}", asked)
    return {"study": study, "answers": answers, "overfit": overfit, "budget_left": left,
            "budget": budget, "questions_total": asked,
            "status": "EXHAUSTED" if left <= 0 else "VALID", "state_error": None}


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
        _append(path, {"rotate": base, "epoch": n,
                       "retired_keys": sorted(str(k) for k in used_keys)})
    except OSError:
        return None
    return f"{base}@{n}"
