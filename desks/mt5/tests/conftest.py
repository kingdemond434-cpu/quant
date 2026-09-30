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

_REPO_DEPTH = 3


@pytest.fixture(autouse=True)
def _tier_s_state_stays_out_of_the_checkout(monkeypatch: pytest.MonkeyPatch,
                                            tmp_path_factory: pytest.TempPathFactory) -> None:
    """A test never appends to the live Tier S ledgers. `blinding.record` (which `publish` calls)
    and the promotion door's block ledger write under the checkout by default, so a suite run on
    the box would add fake rows to `desks/mt5/data/tier_s/`. Writes aimed inside the checkout are
    redirected to a temp root; a test that points them at its own tmp_path is untouched."""
    from libs.tiers import blinding
    from libs.tiers import promotion_authority as pa

    repo = Path(__file__).resolve().parents[_REPO_DEPTH]
    sink = tmp_path_factory.mktemp("tier_s_sink")
    real_record = blinding.record

    def record(root: Path, rep: Any, ledger: str = blinding.RUNTIME_LEDGER) -> None:
        target = (Path(root) / ledger).resolve()
        if target.is_relative_to(repo):
            root, ledger = sink, str(target.relative_to(repo))
        real_record(root, rep, ledger)

    monkeypatch.setattr(blinding, "record", record)
    if Path(pa.LEDGER).resolve().is_relative_to(repo):
        monkeypatch.setattr(pa, "LEDGER", sink / "promotion_blocks.jsonl")
