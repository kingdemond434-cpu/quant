"""Fit the probabilistic regime engine (HMM + GMM + Bayesian) on BTC history -> live regime feed.

Writes web/regime_engine.json (full detail for the dashboard) and MERGES the live
leverage_multiplier + confidence into data/crypto_regime.json so the executor sizes by regime (it
already reads that file). The multiplier only de-risks (<=1.0). Runs on the executor flywheel.

    python scripts/run_regime_engine.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from libs.data.crypto_source import fetch_klines
from libs.regime.engine import RegimeEngine

_WEB = Path("web/regime_engine.json")
_REGIME = Path("data/crypto_regime.json")


def main() -> None:
    df = fetch_klines("BTCUSDT", interval="1d")
    if df.empty or "close" not in df:
        raise SystemExit("no BTC klines")
    eng = RegimeEngine(n_states=3, seed=0).fit(df["close"].astype(float).reset_index(drop=True))
    cur = eng.current()
    states = [{"state": j, **ch} for j, ch in eng.hmm_char.items()]
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "model": "GaussianHMM(3) + GMM(3) cross-check + Bayesian filter",
        **cur,
        "states": states,
        "transition_matrix": [[round(float(v), 3) for v in row] for row in eng.hmm.transmat],
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(out, indent=2, default=str), "utf-8")

    # merge the live multiplier into the regime file the executor reads (preserve other keys)
    reg = {}
    if _REGIME.exists():
        try:
            reg = json.loads(_REGIME.read_text("utf-8"))
        except (OSError, ValueError):
            reg = {}
    reg.update({
        "hmm_regime": cur.get("regime"), "regime_confidence": cur.get("confidence"),
        "leverage_multiplier": cur.get("leverage_multiplier"),
        "hmm_gmm_agree": cur.get("hmm_gmm_agree"),
    })
    _REGIME.parent.mkdir(parents=True, exist_ok=True)
    _REGIME.write_text(json.dumps(reg, indent=2, default=str), "utf-8")
    print(f"regime: {cur.get('regime')} conf={cur.get('confidence')} "
          f"lev_mult={cur.get('leverage_multiplier')} gmm_agree={cur.get('hmm_gmm_agree')}")


if __name__ == "__main__":
    main()
