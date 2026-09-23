"""Pipeline Stage 1: Discovery — generate candidate hypotheses from economic mechanisms."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

BASE = Path(__file__).resolve().parent.parent.parent
EXPERIMENTS_DIR = BASE / "experiments"
HYPOTHESES_DIR = BASE / "hypotheses"
STRATEGIES_DIR = BASE / "strategies"


@dataclass
class Hypothesis:
    """A testable trading hypothesis with economic mechanism."""
    id: str                          # HXXXXXX
    family: str                      # strategy family name
    symbols: list[str]               # universe subset
    sessions: list[str]              # trading sessions
    side: str                        # LONG / SHORT / BOTH
    parameters: dict[str, Any]       # parameter grid
    mechanism: str                   # economic rationale (required)
    falsifier: str                   # what would disprove this (required)
    status: str = "DISCOVERED"       # DISCOVERED | SCREENED | VALIDATED | SHADOW | PROMOTED | RETIRED


def load_hypothesis(path: Path) -> Hypothesis:
    """Load hypothesis from YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Hypothesis(**data)


def save_hypothesis(h: Hypothesis, path: Path | None = None) -> Path:
    """Save hypothesis to YAML file."""
    if path is None:
        path = HYPOTHESES_DIR / f"{h.id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(h.__dict__, f, sort_keys=False)
    return path


def discover_from_mechanism(mechanism: str, universe: list[str]) -> list[Hypothesis]:
    """Generate hypotheses from a named economic mechanism.

    This replaces the old run_huntN.py parameter sweeps.
    Each mechanism maps to a strategy family with registered parameters.
    """
    from mt5desk import families

    mechanism_map = {
        "session_breakout": {"family": "session_range_breakout", "windows": ["asia", "london_am", "ny_open", "afternoon"]},
        "failed_breakout": {"family": "failed_breakout", "windows": ["asia", "london_am"]},
        "fair_value_gap": {"family": "fair_value_gap", "windows": ["asia", "london_am", "ny_open", "afternoon"]},
        "level_breakout": {"family": "level_breakout", "windows": ["london_am", "ny_open"]},
        "order_block": {"family": "order_block", "windows": ["asia", "london_am"]},
        "dow_effect": {"family": "dow_effect", "windows": ["asia"]},
        "monday_gap": {"family": "monday_gap", "windows": ["asia"]},
    }

    if mechanism not in mechanism_map:
        raise ValueError(f"Unknown mechanism: {mechanism}")

    spec = mechanism_map[mechanism]
    hypotheses = []

    for sym in universe:
        for win in spec["windows"]:
            # Check if family supports this symbol/window
            # (actual validation happens in screening stage)
            h = Hypothesis(
                id=f"H{len(list(HYPOTHESES_DIR.glob('*.yaml')))+1:06d}",
                family=spec["family"],
                symbols=[sym],
                sessions=[win],
                side="BOTH",
                parameters={"rr": [1.5, 2.0, 2.5]},
                mechanism=mechanism,
                falsifier=f"No positive expectancy in {win} session for {sym} after 100 forward trades",
            )
            hypotheses.append(h)

    return hypotheses


def run_discovery(mechanisms: list[str], universe: list[str]) -> list[Path]:
    """Run discovery for multiple mechanisms, save hypotheses."""
    HYPOTHESES_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for mech in mechanisms:
        hyps = discover_from_mechanism(mech, universe)
        for h in hyps:
            p = save_hypothesis(h)
            saved.append(p)
    return saved


if __name__ == "__main__":
    import sys
    mechanisms = sys.argv[1:] if len(sys.argv) > 1 else ["session_breakout", "failed_breakout"]
    universe = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
    paths = run_discovery(mechanisms, universe)
    print(f"Discovered {len(paths)} hypotheses")