"""READ-ONLY diagnostic probe for the gate-optimality defect. Writes NOTHING (no DB, no reports).

Reconstructs the exact 420-candidate campaign matrix the autodiscovery lab built, then pushes a
SYNTHETIC candidate with a KNOWN true Sharpe through libs.autodiscovery.validation.validate() --
the identical per-candidate gauntlet the 420 traversed.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from libs.autodiscovery.crypto_adapter import COST_PER_SIDE, DEFAULT_FAMILIES, load_universe
from libs.autodiscovery.generators import net_returns, planned_hypotheses
from libs.autodiscovery.prioritization import prioritize
from libs.data.timeframe import Timeframe

CACHE = Path("_audit_prepared.pkl")


def rebuild() -> list:
    symbols, provider = load_universe(Timeframe.D1, limit=30)
    plan = prioritize(planned_hypotheses(symbols, families=list(DEFAULT_FAMILIES)))
    prepared = []
    cache: dict = {}
    for hyp, spec in plan:
        if hyp.symbol not in cache:
            cache[hyp.symbol] = provider(hyp.symbol)
        series = cache[hyp.symbol]
        if series is None or len(series) < 250:
            continue
        try:
            pos = spec.fn(series, dict(hyp.params))
            rets = net_returns(series, pos, cost=COST_PER_SIDE)
        except Exception:
            continue
        if len(rets) >= 250:
            prepared.append((str(hyp.family), hyp.subtype, hyp.symbol, rets))
    return prepared


if __name__ == "__main__":
    if CACHE.exists():
        # S301 suppressed deliberately: CACHE is written by this same script two lines below
        # and never leaves the box, so these bytes are our own, not untrusted input.
        prepared = pickle.loads(CACHE.read_bytes())  # noqa: S301
    else:
        prepared = rebuild()
        CACHE.write_bytes(pickle.dumps(prepared))
    print(f"prepared={len(prepared)}")
    fams: dict[str, int] = {}
    for f, _s, _y, _r in prepared:
        fams[f] = fams.get(f, 0) + 1
    print(json.dumps(fams, indent=1))
    lens = [len(r) for *_x, r in prepared]
    print("len min/max", min(lens), max(lens))
