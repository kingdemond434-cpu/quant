"""A SMOOTHED REGIME LABEL MAY DESCRIBE HISTORY. IT MAY NEVER SIZE A POSITION.

`GaussianHMM.predict` is Viterbi, and Viterbi has a backward pass:

    states[-1] = argmax(delta[-1])
    for t in range(n - 2, -1, -1):
        states[t] = psi[t + 1, states[t + 1]]

The label at t is chosen by the label at t+1, so every historical entry it produces was assigned
using observations from after the day it describes. That is the standard public-HMM recipe and it
is a lookahead leak.

FOUND LIVE ON THIS TREE, 2026-09-12, by reading the Aurum desk's `regime_hmm.py`, whose docstring
names the trap exactly ("the standard recipe is model.fit(X) then model.predict(X), and predict is
Viterbi -- the most likely state SEQUENCE given the WHOLE series"). `pf_allocator` built its
`by_day` regime map from `eng.hmm_states`, and that map conditions the state growth curves that
SET HEAT. `regime_coverage` did the same for its coverage report. Measured on a synthetic
two-regime series: 27 of 1,200 days (2.2%) carried a label the desk could not have known that
day, concentrated -- as the arithmetic requires -- at the transitions, which is precisely where a
state-conditional number is doing the most work.

THE RULE IS NOT "VITERBI IS WRONG". Smoothed labels are the correct instrument for describing
history: `_characterise` asks what each latent state was really like, over the whole record, and
has no forward-looking consumer. The rule is that a smoothed label may not reach a number that
sizes a position. `RegimeEngine.filtered_states` -- argmax of P(state_t | x_1..t) -- is the label
a desk could actually have held on the day, and it is what every conditioning map now reads.

THIS FENCE IS A SOURCE CHECK BECAUSE BEHAVIOUR CANNOT CATCH IT. Both label arrays are the same
shape, the same dtype and agree on ~98% of days, so a test that merely ran the allocator would
pass with the leak restored. The only reliable signal is which attribute the sizing path names.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Modules whose output reaches sizing, allocation or a published coverage claim. A smoothed
#: label must not appear in any of them.
SIZING_PATHS = (
    "desks/mt5/research/pf_allocator.py",
    "desks/mt5/research/regime_coverage.py",
    "desks/mt5/mt5desk/decision_core.py",
    "desks/mt5/mt5desk/gateway.py",
    "libs/regime/asset_state.py",
)

#: Where a smoothed label is legitimately produced and described. `engine.py` computes both and
#: says which is which; `hmm.py` implements both.
ALLOWED = {"libs/regime/engine.py", "libs/regime/hmm.py"}

_SMOOTHED = re.compile(r"\bhmm_states\b")


def test_no_sizing_path_reads_the_smoothed_label() -> None:
    offenders: list[str] = []
    for rel in SIZING_PATHS:
        p = ROOT / rel
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            stripped = line.strip()
            # A comment ABOUT the leak is how the fix documents itself and must not be charged.
            if stripped.startswith("#") or stripped.startswith('"'):
                continue
            if _SMOOTHED.search(line):
                offenders.append(f"{rel}:{i}: {stripped[:100]}")
    assert not offenders, (
        "a sizing path reads `hmm_states`, which is the Viterbi SMOOTHED label and was assigned "
        "using observations from after the day it describes. Use `filtered_states` -- argmax of "
        "the forward filter -- which is the label the desk could have held on the day:\n  "
        + "\n  ".join(offenders))


def test_the_engine_still_publishes_both_and_says_which_is_causal() -> None:
    """The fix must not be 'delete Viterbi'. Both exist; only one is licensed for sizing."""
    src = (ROOT / "libs" / "regime" / "engine.py").read_text(encoding="utf-8")
    assert "self.filtered_states" in src, "the causal label is gone; nothing can condition safely"
    assert "self.hmm_states" in src, (
        "the smoothed label was deleted rather than demoted. It is the right instrument for "
        "describing history (`_characterise`), and removing it would push a future author back "
        "to `hmm.predict()` at the call site, which is the leak again with no name on it.")


def test_the_causal_label_is_derived_from_the_forward_filter() -> None:
    """Pin the derivation, not just the name -- `filtered_states = hmm.predict(x)` would pass a
    name check and reintroduce the leak silently."""
    src = (ROOT / "libs" / "regime" / "engine.py").read_text(encoding="utf-8")
    line = next((ln for ln in src.splitlines()
                 if "self.filtered_states" in ln and "=" in ln and "np.zeros" not in ln), "")
    assert "posteriors" in line, (
        f"filtered_states is not derived from the forward posterior: {line.strip()!r}. It must be "
        f"argmax over P(state_t | x_1..t), never anything that has seen the future.")
