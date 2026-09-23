"""TimesFM adapter -- point and quantile forecasts from Google's time-series foundation model,
loaded from the LOCAL HF cache only. The 3.0 weights are non-commercial by their terms: the
adapter donates a research REPRESENTATION and nothing that trades.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "timesfm"
CAPABILITY_FAMILY = "foundation_model"
LICENCE_EXPECTED = "Apache-2.0"
MAX_SYMBOLS = 4
CONTEXT = 512
H = 24


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    tfm_mod = A.library("timesfm")
    if tfm_mod is None:
        return A.unmeasured(SYSTEM, bundle, "timesfm is not importable here (pip install "
                                            "timesfm==3.0.2)")
    import numpy as np
    model: Any = None
    api = ""
    try:
        if hasattr(tfm_mod, "TimesFM_2p5_200M_torch"):
            model = tfm_mod.TimesFM_2p5_200M_torch.from_pretrained(
                "google/timesfm-2.5-200m-pytorch")
            model.compile(tfm_mod.ForecastConfig(max_context=CONTEXT, max_horizon=H,
                                                 normalize_inputs=True))
            api = "timesfm>=3 TimesFM_2p5_200M_torch"
        else:
            model = tfm_mod.TimesFm(
                hparams=tfm_mod.TimesFmHparams(backend="cpu", per_core_batch_size=1,
                                               horizon_len=H, context_len=CONTEXT),
                checkpoint=tfm_mod.TimesFmCheckpoint(
                    huggingface_repo_id="google/timesfm-2.0-500m-pytorch"))
            api = "timesfm 1.x/2.x TimesFm"
    except Exception as exc:
        return A.unmeasured(SYSTEM, bundle, f"TimesFM weights not loadable offline: "
                                            f"{type(exc).__name__}: {exc}"[:220])
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired() or len(f) < CONTEXT + 1:
            continue
        trials += 1
        c = np.asarray(f.close[-CONTEXT:], dtype=float)
        try:
            out = model.forecast([c]) if api.startswith("timesfm>=3") else model.forecast(
                [c], freq=[0])
            point = np.asarray(out[0][0], dtype=float)
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        reps.append({"kind": "foundation_point_path", "symbol": f.symbol, "api": api,
                     "horizon_bars": H, "path_rel": (point[:H] / c[-1] - 1.0),
                     "terms": "research representation only (3.0 weights: non-commercial)"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
