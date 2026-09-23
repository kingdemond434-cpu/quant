"""Kymatio adapter -- the 1-D wavelet scattering transform of the last 1024 standardised
returns; first- and second-order energies and their ratio are a REPRESENTATION of
multi-scale structure (a rising second-order share is intermittency).
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "kymatio"
#: WHAT MUST IMPORT for this adapter to run, which is not the same as what pip installed:
#: `import kymatio` succeeds and `import kymatio.numpy` does not, because kymatio 0.3.0
#: reaches for `scipy.special.sph_harm`, removed in the scipy this desk runs. The
#: provisioner verifies THIS name, so the install ledger records the truth the adapter
#: meets rather than the truth pip reports.
IMPORT_TARGET = "kymatio.numpy"
CAPABILITY_FAMILY = "signal_scattering"
LICENCE_EXPECTED = "BSD-3-Clause"
MAX_SYMBOLS = 4
T = 1024
J = 6
Q = 8


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    km = A.library(IMPORT_TARGET)
    if km is None:
        return A.unmeasured(SYSTEM, bundle, "kymatio is not importable here (pip install "
                                            "kymatio==0.3.0)")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        r = f.log_returns()
        if deadline.expired() or r.shape[0] < T:
            continue
        x = r[-T:]
        x = (x - x.mean()) / max(x.std(), 1e-12)
        trials += 1
        try:
            S = km.Scattering1D(J=J, shape=(T,), Q=Q)
            Sx = np.asarray(S(x), dtype=float)
            order = np.asarray(S.meta()["order"])
            e1 = float(np.mean(Sx[order == 1] ** 2)) if (order == 1).any() else 0.0
            e2 = float(np.mean(Sx[order == 2] ** 2)) if (order == 2).any() else 0.0
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        reps.append({"kind": "scattering_coefficients", "symbol": f.symbol, "J": J, "Q": Q,
                     "order1_energy": e1, "order2_energy": e2,
                     "order2_share": e2 / max(e1 + e2, 1e-18),
                     "representation": "second-order share is intermittency (vol clustering) "
                                       "across scales; a state for the forge"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
