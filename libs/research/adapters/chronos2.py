"""Chronos-2 adapter -- zero-shot quantile forecasts from a time-series foundation model.
Weights come from the LOCAL Hugging Face cache only (HF_HUB_OFFLINE is forced): a sandbox
fetches nothing. The quantile path is a REPRESENTATION of the model's belief, never a
forecast to act on.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "chronos2"
CAPABILITY_FAMILY = "foundation_model"
LICENCE_EXPECTED = "Apache-2.0"
MODEL_IDS = ("amazon/chronos-2", "amazon/chronos-bolt-tiny", "amazon/chronos-t5-tiny")
MAX_SYMBOLS = 4
CONTEXT = 512
H = 24


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    chronos = A.library("chronos")
    torch = A.library("torch")
    if chronos is None or torch is None:
        return A.unmeasured(SYSTEM, bundle, "chronos-forecasting (or torch) is not importable "
                                            "here (pip install chronos-forecasting==2.3.2)")
    import numpy as np
    pipe = None
    tried: list[str] = []
    for mid in MODEL_IDS:
        try:
            pipe = chronos.BaseChronosPipeline.from_pretrained(mid, device_map="cpu",
                                                               local_files_only=True)
            break
        except Exception as exc:
            tried.append(f"{mid}: {type(exc).__name__}")
    if pipe is None:
        return A.unmeasured(SYSTEM, bundle, "no Chronos weights in the local HF cache "
                                            f"({'; '.join(tried)[:200]}); the sandbox fetches "
                                            "nothing")
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired() or len(f) < CONTEXT + 1:
            continue
        trials += 1
        c = np.asarray(f.close[-CONTEXT:], dtype=float)
        try:
            q, _ = pipe.predict_quantiles(context=torch.tensor(c), prediction_length=H,
                                          quantile_levels=[0.1, 0.5, 0.9])
            qa = np.asarray(q[0], dtype=float)
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        reps.append({"kind": "foundation_quantiles", "symbol": f.symbol, "horizon_bars": H,
                     "q10_rel": (qa[:, 0] / c[-1] - 1.0), "q50_rel": (qa[:, 1] / c[-1] - 1.0),
                     "q90_rel": (qa[:, 2] / c[-1] - 1.0), "context": CONTEXT,
                     "representation": "the model's belief over the next path; width is an "
                                       "uncertainty state for the forge"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
