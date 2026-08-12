"""#8 Factor Risk Model integration -- decompose sleeve risk into common factors + idiosyncratic.

Reuses libs/portfolio/factor_model.FactorRiskModel (orphaned). Takes the sleeve correlation matrix
the portfolio engine already produces, extracts the top principal factors (the systematic risk
directions), and reconstructs the structured covariance cov = B F B' + diag(specific) through the
factor model. Reports variance explained by common factors, each sleeve's factor exposure +
idiosyncratic share, the effective number of independent bets, and the condition number. Writes
web/factor_model.json. (Correlation-space / unit-variance; raw sleeve vols are not cached.)

    python scripts/run_factor_model.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.portfolio.factor_model import FactorRiskModel  # noqa: E402

_PORT = Path("web/crypto_portfolio.json")
_OUT = Path("web/factor_model.json")
_K = 2                                       # number of common factors to retain


def main() -> None:
    port = json.loads(_PORT.read_text("utf-8"))
    cmap = port.get("correlations", {})
    sleeves = [s for s in cmap if not str(s).startswith("portfolio")]
    n = len(sleeves)
    if n < 3:
        raise SystemExit("need >=3 sleeves for a factor model")
    c = np.array([[float(cmap[a].get(b, 1.0 if a == b else 0.0)) for b in sleeves]
                  for a in sleeves])
    c = 0.5 * (c + c.T)                       # symmetrise

    evals, evecs = np.linalg.eigh(c)
    order = np.argsort(evals)[::-1]
    evals, evecs = evals[order], evecs[:, order]
    total = float(evals.sum())
    k = min(_K, n)
    loadings = evecs[:, :k] * np.sqrt(np.clip(evals[:k], 0, None))   # B (asset x factor)

    exposures = {sleeves[i]: {f"F{j + 1}": float(loadings[i, j]) for j in range(k)}
                 for i in range(n)}
    factor_cov = np.eye(k)                    # factors orthonormalised into the loadings
    common_var = np.einsum("ij,ij->i", loadings, loadings)           # B F B' diagonal
    specific = {sleeves[i]: max(0.0, float(c[i, i] - common_var[i])) for i in range(n)}

    frm = FactorRiskModel([f"F{j + 1}" for j in range(k)])
    _assets, cov_hat = frm.build(exposures=exposures, factor_cov=factor_cov, specific_var=specific)
    recon_err = float(np.abs(cov_hat - c).mean())

    pct = (evals / total).clip(0, None)
    eff_bets = round(float(1.0 / np.sum(pct[pct > 0] ** 2)), 2)      # participation ratio
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "model": "PCA factor risk model (cov = B F B' + diag specific) via FactorRiskModel",
        "n_sleeves": n, "n_factors": k,
        "factor_variance_explained": [round(float(p), 3) for p in pct[:k]],
        "common_factor_share": round(float(pct[:k].sum()), 3),
        "effective_independent_bets": eff_bets,
        "condition_number": round(float(evals.max() / max(evals.min(), 1e-9)), 1),
        "reconstruction_error": round(recon_err, 4),
        "sleeves": [{
            "sleeve": sleeves[i],
            "factor_exposure": {f"F{j + 1}": round(float(loadings[i, j]), 3) for j in range(k)},
            "idiosyncratic_share": round(float(specific[sleeves[i]] / max(c[i, i], 1e-9)), 3),
        } for i in range(n)],
        "note": ("correlation-space (unit vol); top factor = common 'everything moves together' "
                 "risk; high idiosyncratic share = diversifying sleeve."),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"factor model: {k} factors explain {out['common_factor_share']:.0%} of sleeve risk; "
          f"effective bets {eff_bets}; recon err {out['reconstruction_error']}")


if __name__ == "__main__":
    main()
