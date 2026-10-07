"""ARCH-05: poisoned optimizer, agent and forecast output through the real decision path.

The battery itself is the drill; these tests pin that it reaches every poison the delivery check
names, that no case is a live-path BYPASS on this tree, that every LATENT case names its proof of
unreachability and the patch, that the patch applies, and that `recovery_drills` grades the
artifact (absent -> UNMEASURED, bypass -> FAIL, clean -> PASS)."""
from __future__ import annotations

import json
import math
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import adversarial_risk as ar  # noqa: E402
from research import recovery_drills as rd  # noqa: E402

NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)


@pytest.fixture(scope="module")
def doc() -> dict:
    return ar.build(NOW)


def test_every_named_poison_is_driven(doc: dict) -> None:
    ids = {c["case"] for c in doc["cases"]}
    for p in ("nan", "inf", "negative", "huge"):
        assert f"book_fraction_{p}" in ids and f"book_weight_{p}" in ids
    for must in ("heat_stale_forecast", "unknown_symbol_sizing", "unknown_symbol_heat",
                 "order_door_volume_max_checked", "volume_max_desk_side",
                 "order_door_margin_checked", "margin_above_free", "venue_loss_bar",
                 "release_gate_unsealed", "order_door_duplicate_resend"):
        assert must in ids, must
    # wrong sign: a negative fraction is the wrong-sign poison on every fraction input
    assert any(c["poison"] == "negative" for c in doc["cases"])


def test_no_live_path_bypass_and_nothing_unmeasured(doc: dict) -> None:
    bad = [c for c in doc["cases"] if c["verdict"] in (ar.BYPASS, ar.UNMEASURED)]
    assert not bad, bad
    assert doc["verdict"] == "PASS" and doc["completed_work"] == doc["n"]


def test_latent_cases_carry_their_proof_and_the_patch(doc: dict) -> None:
    for c in doc["cases"]:
        if c["verdict"] == ar.LATENT:
            assert c.get("unreachable_because") and c.get("fix") == ar.PATCH, c


def test_a_sovereign_allocator_sends_nothing_for_a_non_size(doc: dict) -> None:
    by = {c["case"]: c for c in doc["cases"]}
    for p in ("nan", "negative", "neg_inf", "string", "none"):
        assert by[f"book_fraction_{p}"]["lot"] == 0.0


def test_the_patch_applies_to_this_tree() -> None:
    patch = _ROOT / ar.PATCH
    assert patch.is_file()
    r = subprocess.run(["git", "apply", "--check", str(patch)], cwd=_ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, f"the ARCH-05 patch no longer applies: {r.stderr[:400]}"


def test_nan_budget_is_latent_not_live(doc: dict) -> None:
    by = {c["case"]: c for c in doc["cases"]}
    # cap_by_heat trusts its tuple ...
    assert by["cap_by_heat_direct_nan"]["verdict"] in (ar.LATENT, ar.HELD)
    # ... and the only live producer of that tuple refuses every non-finite heat
    for p in ("total_nan", "total_inf", "ceiling_nan", "ceiling_inf", "growth_nan"):
        c = by[f"heat_{p}"]
        assert c["verdict"] == ar.HELD
        assert c["budget"] is None or math.isfinite(c["budget"])


def _put(p: Path, doc: dict, at: datetime = NOW) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({**doc, "generated_utc": at.isoformat()}), "utf-8")


def test_recovery_drills_grades_the_battery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                            doc: dict) -> None:
    p = tmp_path / "ADVERSARIAL_RISK.json"
    monkeypatch.setattr(rd, "ADVERSARIAL", p)
    assert rd._independent_controls(NOW)["verdict"] == rd.UNMEASURED
    _put(p, doc)
    row = rd._independent_controls(NOW)
    assert row["verdict"] == rd.PASS
    assert (row.get("gap") is not None) == bool(doc["latent"])
    _put(p, {**doc, "bypasses": ["book_fraction_inf"], "verdict": "FAIL"})
    assert rd._independent_controls(NOW)["verdict"] == rd.FAIL
    _put(p, doc, NOW - timedelta(hours=5))
    assert rd._independent_controls(NOW)["verdict"] == rd.UNMEASURED
    assert "independent_controls" in {d[0] for d in rd.DRILLS}
