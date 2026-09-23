"""MOMENT adapter -- foundation-model embeddings of the last 512 H1 closes per symbol, from
the LOCAL HF cache only. The embedding (and its drift against the previous window) is a
REPRESENTATION for the forge.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "moment"
CAPABILITY_FAMILY = "foundation_model"
LICENCE_EXPECTED = "MIT"
MAX_SYMBOLS = 4
WINDOW = 512


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    mm = A.library("momentfm")
    torch = A.library("torch")
    if mm is None or torch is None:
        return A.unmeasured(SYSTEM, bundle, "momentfm (or torch) is not importable here (pip "
                                            "install momentfm==0.1.4)")
    import numpy as np
    try:
        model = mm.MOMENTPipeline.from_pretrained("AutonLab/MOMENT-1-small",
                                                  model_kwargs={"task_name": "embedding"},
                                                  local_files_only=True)
        model.init()
    except Exception as exc:
        return A.unmeasured(SYSTEM, bundle, f"MOMENT weights not in the local HF cache: "
                                            f"{type(exc).__name__}: {exc}"[:220])
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired() or len(f) < 2 * WINDOW:
            continue
        trials += 1
        try:
            embs = []
            for a, b in ((-2 * WINDOW, -WINDOW), (-WINDOW, None)):
                c = np.asarray(f.close[a:b], dtype=float)
                x = (c - c.mean()) / max(c.std(), 1e-12)
                out = model(x_enc=torch.tensor(x, dtype=torch.float32).reshape(1, 1, -1))
                embs.append(np.asarray(out.embeddings.detach().numpy(), dtype=float).reshape(-1))
            cos = float(np.dot(embs[0], embs[1]) / max(np.linalg.norm(embs[0])
                                                        * np.linalg.norm(embs[1]), 1e-12))
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        reps.append({"kind": "foundation_embedding", "symbol": f.symbol, "window": WINDOW,
                     "dim": int(embs[1].shape[0]), "head": embs[1][:8],
                     "cosine_to_previous_window": cos,
                     "representation": "a drop in cosine similarity between consecutive "
                                       "windows is a regime-change state for the forge"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
