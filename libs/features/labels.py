"""Labels (targets).

Labels are *deliberately* forward-looking — a label at t encodes future outcomes. That is
why a label must never be registered as a feature: doing so is hindsight leakage, which the
feature leakage test rejects. Keep labels strictly on the target side of training.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.features.errors import FeatureError

LABEL_PREFIX = "label_"


def forward_log_return(bars: pd.DataFrame, *, horizon: int = 1) -> pd.Series:
    """The forward log return over ``horizon`` bars (a target; look-ahead by design)."""
    if horizon < 1:
        raise FeatureError("label horizon must be >= 1")
    future_close = bars["close"].shift(-horizon)
    label = np.log(future_close / bars["close"])
    label.name = f"{LABEL_PREFIX}fwd_logret_{horizon}"
    return label


def forward_direction(bars: pd.DataFrame, *, horizon: int = 1) -> pd.Series:
    """The sign of the forward return: +1 up, -1 down, 0 flat (a classification target)."""
    label = np.sign(forward_log_return(bars, horizon=horizon))
    label.name = f"{LABEL_PREFIX}fwd_dir_{horizon}"
    return label
