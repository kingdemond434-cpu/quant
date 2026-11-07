"""One tree, three spellings, one rule (2026-11-05). A GBPCHF formula certificate carried its expr
as the list's Python repr ("['neg', ['delta', 'spread', 3]]"); the family read it as a bare
terminal name, failed `is_valid` and fired nothing. The prefix list, the rendered call and the repr
must hand the family the same tree and trade the same signals."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research.alpha_grammar import coerce_expr, to_str  # noqa: E402

TREE = ["neg", ["delta", "close", 3]]


def _bars() -> pd.DataFrame:
    rng = np.random.default_rng(5)
    idx = pd.date_range("2024-01-01", periods=2000, freq="h", tz="UTC")
    c = 1.2 + np.cumsum(rng.normal(0, 1e-3, len(idx)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + 5e-4,
                         "low": np.minimum(o, c) - 5e-4, "close": c,
                         "tick_volume": rng.integers(50, 500, len(idx)),
                         "spread": rng.integers(5, 30, len(idx))}, index=idx)


def test_every_spelling_coerces_to_the_same_tree() -> None:
    assert coerce_expr(TREE) == TREE
    assert coerce_expr(to_str(TREE)) == TREE
    assert coerce_expr(str(TREE)) == TREE
    assert coerce_expr("close") == "close"
    assert coerce_expr("['neg', [broken") == "['neg', [broken"
    assert coerce_expr("[1, 2]") == [1, 2]                    # still invalid downstream
    assert coerce_expr("{'a': 1}") == "{'a': 1}"


def test_the_family_trades_the_same_signals_for_every_spelling() -> None:
    from mt5desk.family_formula import family_formula
    df = _bars()
    runs = [family_formula(df, expr=e, norm=120, entry_z=1.0)
            for e in (TREE, to_str(TREE), str(TREE))]
    assert runs[0], "the planted bars must fire"
    key = [[(s.time, s.side) for s in r] for r in runs]
    assert key[0] == key[1] == key[2]
