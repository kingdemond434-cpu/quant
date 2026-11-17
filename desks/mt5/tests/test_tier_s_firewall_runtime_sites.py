"""Tier S layer 12: every money-path site the ledger says consults the firewall at runtime does.

The ledger row S12 is BUILT on the strength of three runtime calls. `tier_s._firewall_runtime_sites`
re-reads them from source every pass; this pins that they hold on this tree, and that a site
which loses its call, or cannot be read, is reported as such rather than as a pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(ROOT / "scripts"), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s  # noqa: E402


def test_every_money_path_site_calls_the_firewall_on_this_tree() -> None:
    sites = tier_s._firewall_runtime_sites()
    assert set(sites) == {rel for rel, _ in tier_s.FIREWALL_RUNTIME_SITES}
    assert all(v is True for v in sites.values()), sites


def test_a_site_without_its_call_reads_false_and_an_absent_one_unmeasured(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "gate.py").write_text("def run():\n    return 1\n", "utf-8")
    monkeypatch.setattr(tier_s, "ROOT", tmp_path)
    monkeypatch.setattr(tier_s, "FIREWALL_RUNTIME_SITES",
                        (("gate.py", "judge_refusal("), ("absent.py", "lockbox_accepts(")))
    assert tier_s._firewall_runtime_sites() == {"gate.py": False, "absent.py": "UNMEASURED"}
