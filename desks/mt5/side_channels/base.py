"""Base classes and constants for side_channels package."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from enum import Enum

import yaml

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data" / "intelligence"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class SideChannelAxis(Enum):
    """Independent information axes for alpha generation."""
    FLOW = "flow"
    EVENT = "event"
    RELATIVE_VALUE = "relative_value"
    LIQUIDITY = "liquidity"
    EXECUTION = "execution"
    SEASONALITY = "seasonality"
    POSITIONING = "positioning"
    MACRO = "macro"
    MICROSTRUCTURE = "microstructure"


@dataclass
class SideChannelHypothesis:
    """A hypothesis generated from a side-channel source."""
    id: str                              # SC-XXXXXX
    axis: SideChannelAxis
    source: str                          # e.g., "operational_calendar", "leadership_atlas"
    mechanism: str                       # economic rationale
    symbols: list[str]                   # affected instruments
    timing: dict                         # when edge is active
    falsifier: str                       # what would disprove
    expected_horizon: str                # 1m, 5m, 15m, 1h, 4h, 1d, etc.
    capacity_estimate: str               # "institutional" | "small" | "micro"
    status: str = "DISCOVERED"           # DISCOVERED | VALIDATED | SHADOW | PROMOTED | RETIRED
    metadata: dict = field(default_factory=dict)


def generate_id(prefix: str = "SC") -> str:
    """Generate unique side-channel hypothesis ID."""
    existing = list(DATA_DIR.glob(f"{prefix}-*.yaml")) if (DATA_DIR / "hypotheses").exists() else []
    return f"{prefix}-{len(existing)+1:06d}"


def save_hypothesis(h: SideChannelHypothesis) -> Path:
    """Save hypothesis to YAML."""
    hyp_dir = DATA_DIR / "hypotheses"
    hyp_dir.mkdir(parents=True, exist_ok=True)
    path = hyp_dir / f"{h.id}.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(h.__dict__, f, sort_keys=False)
    return path


def load_hypotheses() -> list[SideChannelHypothesis]:
    """Load all side-channel hypotheses."""
    hypotheses = []
    hyp_dir = DATA_DIR / "hypotheses"
    if not hyp_dir.exists():
        return []
    for path in hyp_dir.glob("SC-*.yaml"):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        data["axis"] = SideChannelAxis(data["axis"])
        hypotheses.append(SideChannelHypothesis(**data))
    return hypotheses