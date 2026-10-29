"""The mechanics drift fence: read-only, UNMEASURED passes, a measured breach fails."""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_mechanics_drift",
                                               ROOT / "scripts" / "check_mechanics_drift.py")
assert _spec and _spec.loader
drift = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drift)


def _root(tmp_path: Path, pages: dict | None) -> Path:
    (tmp_path / "libs" / "mining").mkdir(parents=True)
    shutil.copy(ROOT / drift.MAP_REL, tmp_path / drift.MAP_REL)
    facts = tmp_path / drift.FACTS_REL
    facts.parent.mkdir(parents=True)
    facts.write_text(json.dumps({"generated_at": "2026-09-30T00:00:00+00:00",
                                 "pages": pages or {}}), "utf-8")
    # the declared side is the real code: link desks/mt5 so the imports resolve
    (tmp_path / "desks" / "mt5" / "mt5desk").symlink_to(ROOT / "desks" / "mt5" / "mt5desk")
    return tmp_path


def _declared() -> dict:
    return drift.declared_profiles(ROOT)["e8-one-8pct"]


def test_unmeasured_facts_pass_and_say_so(tmp_path: Path) -> None:
    root = _root(tmp_path, None)
    assert drift.main(["--root", str(root)]) == 0
    rep = json.loads((root / drift.OUT_REL).read_text("utf-8"))
    assert rep["facts_status"] == "UNMEASURED"
    assert rep["rows"] and all(r["state"] == "UNMEASURED" for r in rep["rows"])


def test_agreeing_published_terms_pass(tmp_path: Path) -> None:
    d = _declared()
    root = _root(tmp_path, {"a": {"source_id": "prop_rules",
                                  "source_uri": "https://e8markets.com/e8-one",
                                  "prop_rules": {"max_drawdown_pct": d["max_drawdown_limit"] * 100,
                                                 "profit_target_pct": d["profit_target"] * 100}}})
    assert drift.main(["--root", str(root)]) == 0
    rows = [r for r in drift.check(root)["rows"] if r.get("profile") == "e8-one-8pct"]
    assert {r["state"] for r in rows} == {"AGREES"}


def test_measured_prop_drift_is_a_breach(tmp_path: Path) -> None:
    root = _root(tmp_path, {"a": {"source_id": "prop_rules",
                                  "source_uri": "https://e8markets.com/e8-one",
                                  "prop_rules": {"max_drawdown_pct": 6.0}}})
    assert drift.main(["--root", str(root)]) == 1
    rep = drift.check(root)
    assert rep["breaches"] == 1


def test_commission_drift_is_reported_never_a_breach(tmp_path: Path) -> None:
    root = _root(tmp_path, {"f": {"source_id": "broker_specs",
                                  "source_uri": "https://fusionmarkets.com/en/trading-conditions",
                                  "cost": {"commission_per_lot": 99.0}}})
    assert drift.main(["--root", str(root)]) == 0
    rep = drift.check(root)
    assert rep["drift_reported"] == 1 and rep["breaches"] == 0
