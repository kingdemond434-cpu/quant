#!/usr/bin/env python3
"""THE SEALED NOTIFIER (SEALED; NO_OWNER_EVER). The ROOT re-pin service (repin.py, SYSTEM) sends
the ROOT veto notice and its own alerts through THIS module and the copy of alert_channels.py
that install_repin.ps1 froze beside it in C:\\opt\\authority\\sealed, never through a command or
module from the live tree (a later CONTROLLER merge could rewrite those, and they would then run
as SYSTEM). The channel CONFIG is the sealed copy too (data\\secrets\\alert_channels.json under
the sealed folder, which install_repin.ps1 copies from the box once, Administrators and SYSTEM
only), and the delivery ledger is written there: a session that rewrites the live tree's channel
file cannot point a ROOT notice at itself and fake a receipt.

    send(title, body, live_tree) -> (0 if a channel delivered else 1, "armed A, delivered D")
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CHANNELS = "alert_channels.py"


def _channels(home: Path) -> Any:
    spec = importlib.util.spec_from_file_location("_sealed_alert_channels", home / CHANNELS)
    if spec is None or spec.loader is None:
        raise ImportError(CHANNELS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def send(title: str, body: str, live: Path, home: Path = HERE) -> tuple[int, str]:
    """Send one alert on every armed channel with the SEALED channel code and SEALED config
    (`live` is not read). Any error: (1, why)."""
    try:
        mod = _channels(home)
    except (OSError, ImportError, SyntaxError) as exc:
        return 1, f"armed 0, delivered 0 (no sealed channels: {type(exc).__name__})"
    before = os.getcwd()
    try:
        os.chdir(home)  # the SEALED channel config and ledger (relative paths in alert_channels)
        got = mod.send_all(title, body)
    except Exception as exc:  # a channel crash is "not delivered", never a pass
        return 1, f"armed 0, delivered 0 ({type(exc).__name__})"
    finally:
        os.chdir(before)
    armed, delivered = int(got.get("armed") or 0), int(got.get("delivered") or 0)
    return (0 if delivered > 0 else 1), f"armed {armed}, delivered {delivered}"
