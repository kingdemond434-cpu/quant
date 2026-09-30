"""Shared fixtures for the MT5 desk suite.

`fresh_tier_s_door`: the Tier S promotion door (`libs/tiers/promotion_authority.py`) FAILS
CLOSED -- its four hourly verdict files must be present and fresh, or every new LIVE row is
withheld with DOOR_ERROR. A promoter test that is not about the door would otherwise read the
real repository's `desks/mt5/reports/REPLICATION.json`, which a fresh clone or CI runner does
not have, and every promotion it asserts would be withheld.

This does NOT stub the door. It writes clean, fresh verifier artifacts -- a replication run
with no mismatch, an online-FDR replay with nothing over budget, an immune reading that did not
fall, a door-verdict file with no row against anything -- into `tmp_path` at the same
repo-relative paths the box uses, and points the door at that root. Every check still runs,
the firewall still judges the same relative paths, and a test that writes a MISMATCH or a DROP
into one of these files still sees the door withhold.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest


def write_fresh_door_inputs(root: Path, *, at: str | None = None) -> dict[str, Path]:
    """Clean verifier artifacts under `root`, at the door's repo-relative paths. Returns
    {door attribute: path} so a test can overwrite one with a verdict against a certificate."""
    now = at or datetime.now(UTC).isoformat()
    desk = root / "desks" / "mt5"
    docs: dict[str, tuple[Path, dict[str, Any]]] = {
        "REPLICATION": (desk / "reports" / "REPLICATION.json",
                        {"at": now, "verdicts": []}),
        "FDR_ROWS": (desk / "reports" / "tier_s" / "ONLINE_FDR_ROWS.json",
                     {"generated_utc": now, "rows": []}),
        "FREEZE": (desk / "data" / "tier_s" / "PROMOTION_FREEZE.json",
                   {"at": now, "verdict": "OK", "why": ""}),
        "DOOR_VERDICTS": (desk / "data" / "tier_s" / "door_verdicts.json",
                          {"generated_utc": now, "rows": {}}),
    }
    out: dict[str, Path] = {}
    for attr, (path, doc) in docs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc), "utf-8")
        out[attr] = path
    return out


@pytest.fixture
def fresh_tier_s_door(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[dict[str, Path]]:
    """Point the Tier S door at fresh, clean verifier artifacts in `tmp_path` (see module doc)."""
    from libs.tiers import promotion_authority as pa

    root = tmp_path / "door_root"
    paths = write_fresh_door_inputs(root)
    desk = root / "desks" / "mt5"
    monkeypatch.setattr(pa, "ROOT", root)
    for attr, path in paths.items():
        monkeypatch.setattr(pa, attr, path)
    monkeypatch.setattr(pa, "LEDGER", desk / "data" / "tier_s" / "promotion_blocks.jsonl")
    monkeypatch.setattr(pa, "LIVE_DOOR", desk / "data" / "tier_s" / "live_door.json")
    # the constitution and ratifications keep their repo-relative names; absent = sealed default
    monkeypatch.setattr(pa, "CONSTITUTION", root / "docs" / "research" / "tier_s_constitution.json")
    monkeypatch.setattr(pa, "RATIFICATIONS",
                        root / "docs" / "research" / "tier_s_ratifications.jsonl")
    required = dict(pa.REQUIRED)
    for key, (path, stamp, writer) in pa.REQUIRED.items():
        for new in paths.values():
            if path.name == new.name:
                required[key] = (new, stamp, writer)
    monkeypatch.setattr(pa, "REQUIRED", required)
    yield paths


def write_measured_dsr_inputs(root: Path, *, variance: float = 0.0002, n: int = 200,
                              family: str = "fixture") -> Path:
    """A REAL measured `DSR_INPUTS.json` under `root`, written by the organ's own `run` from a
    synthetic sweep of `n` judged cells whose Sharpes have sample variance exactly `variance`.

    The sealed judge (with `tier_s_dsr_measured_variance.patch`) fails closed without a fresh,
    verified DSR_INPUTS -- every cell UNKNOWN, `dsr_inputs_unmeasured`. A test that is not about
    the DSR inputs points the judge's door here. Nothing is stubbed: the document is harvested,
    measured and hashed exactly as the hourly leg does it, and the judge verifies it. The
    fixture family is not a real family, so every real family reads the POOLED variance and no
    measured effective-trial count (the judge's other charges apply unchanged)."""
    import math

    from libs.research import dsr_inputs

    a = math.sqrt(variance * (n - 1) / n)             # +-a alternating: ddof=1 variance exact
    verdicts = [{"cell": f"FIX{i}.{family}.p={i}", "family": family, "sym": f"FIX{i % 7}",
                 "days": 300, "stages": {"in_sample_screen": {"sharpe": a if i % 2 else -a}}}
                for i in range(n)]
    root.mkdir(parents=True, exist_ok=True)
    sweep = root / "fixture_sweep.json"
    sweep.write_text(json.dumps({"hunt": "fixture", "swept_at": datetime.now(UTC).isoformat(),
                                 "verdicts": verdicts}), "utf-8")
    out = root / "DSR_INPUTS.json"
    doc = dsr_inputs.run(report_path=sweep, ledger_path=root / "dsr_trial_sharpes.jsonl",
                         out=out)
    assert doc["status"] == dsr_inputs.MEASURED, doc.get("why")
    return out


@pytest.fixture
def measured_dsr_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the judge's DSR-inputs door at a fresh measured document (see the writer above)."""
    from libs.research import dsr_inputs

    path = write_measured_dsr_inputs(tmp_path / "dsr_inputs")
    monkeypatch.setattr(dsr_inputs, "REPORT", path)
    return path


@pytest.fixture(scope="module")
def measured_dsr_inputs_module(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """`measured_dsr_inputs` for a module-scoped fixture that runs the real judge once."""
    from libs.research import dsr_inputs

    path = write_measured_dsr_inputs(tmp_path_factory.mktemp("dsr_inputs"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(dsr_inputs, "REPORT", path)
        yield path
