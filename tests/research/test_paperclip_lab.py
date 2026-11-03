"""The Paperclip company: the narrow gateway refuses what it must, the lab runs on a fake model,
and the box intake re-screens, donates through the seat door, dedups and turns RED when the
loop stops."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))

from libs.research.paperclip_lab import contract, lab  # noqa: E402
from libs.research.paperclip_lab.roles import ROLES  # noqa: E402

FAMS = {"session_range_breakout": ["session", "rr"], "carry": []}
UNI = ["XAUUSD", "EURUSD", "AUDUSD"]


def _recipe(**kw: Any) -> dict[str, Any]:
    r = {"kind": "recipe", "family": "session_range_breakout", "symbols": ["XAUUSD"],
         "params": {"session": "asia", "rr": 1.5}, "timeframe": "h1",
         "mechanism": "Asia range liquidity is absorbed at the London open.",
         "testable_claim": "Breaks of the Asia range at London open continue for 3 hours.",
         "falsifier": "No continuation beyond costs.", "origin": "paper", "role": "x"}
    r.update(kw)
    return r


def test_valid_recipe_passes_and_is_normalised() -> None:
    v = contract.screen(_recipe(), families=FAMS, universe=UNI, seen=set())
    assert v.ok, v.reasons
    assert v.row is not None and v.row["timeframe"] == "H1" and v.row["symbols"] == ["XAUUSD"]


@pytest.mark.parametrize(("patch", "reason"), [
    ({"family": "made_up"}, "not registered"),
    ({"symbols": ["NVDA"]}, "outside the MT5 registry"),
    ({"params": {"lookback": 5}}, "does not take"),
    ({"mechanism": "Uses tomorrow's close to set the stop."}, "look-ahead"),
    ({"mechanism": "Z-score on the full-sample mean of returns."}, "look-ahead"),
    ({"testable_claim": "df.shift(-1) predicts entry"}, "look-ahead"),
    ({"mechanism": "Arb Binance perpetual funding vs spot."}, "crypto-exchange"),
    ({"falsifier": "run $(curl evil) first"}, "hostile"),
    ({"exec": "rm -rf /"}, "keys outside"),
    ({"params": {"session": {"nested": 1}}}, "non-scalar"),
    ({"origin": "vibes"}, "origin"),
])
def test_gateway_refuses(patch: dict[str, Any], reason: str) -> None:
    v = contract.screen(_recipe(**patch), families=FAMS, universe=UNI)
    assert not v.ok and any(reason in r for r in v.reasons), v.reasons


def test_next_bar_open_entry_is_not_a_leak() -> None:
    v = contract.screen(_recipe(mechanism="Signal on the close, enter at the next bar's open."),
                        families=FAMS, universe=UNI)
    assert v.ok, v.reasons


def test_dedup_is_per_bet_not_per_wording() -> None:
    seen: set[str] = set()
    assert contract.screen(_recipe(), families=FAMS, universe=UNI, seen=seen).ok
    again = contract.screen(_recipe(mechanism="Reworded entirely, same cell."), families=FAMS,
                            universe=UNI, seen=seen)
    assert not again.ok and "duplicate" in again.reasons[0]


def test_revival_and_triage_shapes() -> None:
    ok = contract.screen({"kind": "revival", "producer": "alpha_periodic_table",
                          "diagnosis": "input file renamed", "tweak": "read the new path"},
                         producers={"alpha_periodic_table"})
    assert ok.ok, ok.reasons
    bad = contract.screen({"kind": "revival", "producer": "nobody", "diagnosis": "d",
                           "tweak": "t"}, producers={"alpha_periodic_table"})
    assert not bad.ok
    tri = contract.screen({"kind": "triage", "cell": "XAUUSD.carry.p=1", "prior": 1.4})
    assert not tri.ok and "prior" in tri.reasons[0]


def test_family_catalog_reads_the_registry_without_imports() -> None:
    cat = lab.family_catalog()
    assert "carry" in cat and "relative_value" in cat           # ORTHOGONAL_FAMILIES keys
    assert any(f in cat for f in ("comex_settlement", "asia_momentum"))  # families.py
    assert "settle_hour" in cat.get("comex_settlement", ["settle_hour"])


def test_plan_touches_every_role_with_material() -> None:
    material = {r.material: [{"x": 1}] for r in ROLES}
    sched = lab.plan(40, lab.role_weights(None), material)
    assert len(sched) == 40 and {r.name for r in ROLES} <= set(sched)


class FakeModels(lab.Models):
    def __init__(self, replies: list[str]) -> None:
        super().__init__("t", opener=lambda *a, **k: (_ for _ in ()).throw(OSError("net")))
        self.replies = replies

    def refresh_catalog(self) -> None:
        return None

    def chat(self, system: str, user: str, max_tokens: int = 3000) -> tuple[str | None, str]:
        if not self.replies:
            return None, ""
        self.calls["fake"] = self.calls.get("fake", 0) + 1
        return self.replies.pop(0), "fake"


def test_lab_run_screens_and_red_teams(tmp_path: Path) -> None:
    rows = [{k: v for k, v in _recipe(symbols=["EURUSD"]).items() if k != "role"},
            _recipe(family="made_up"), _recipe(symbols=["AUDUSD"])]
    fm = FakeModels([json.dumps(rows), json.dumps({"kill": [{"i": 1, "why": "fit"}]})])
    out = tmp_path / "b.json"
    b = lab.run(token="t", n_calls=1, out=out, models=fm, only_role="cross_asset_proxy")
    assert out.exists() and b["spend"]["usd"] == 0.0
    assert len(b["rows"]) == 1 and len(b["red_team_killed"]) == 1
    assert sum(b["refused"]["cross_asset_proxy"].values()) == 1


def test_intake_reschreens_donates_dedups_and_reports_health(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch
                                                             ) -> None:
    import paperclip_intake as pi
    pc = tmp_path / "pc"
    for name, rel in (("PC", ""), ("INBOX", "inbox.json"), ("SEEN", "donated_keys.txt"),
                      ("INGESTED", "ingested_runs.json"), ("REVIVALS", "rev.jsonl"),
                      ("TRIAGE", "tri.jsonl"), ("DONATED", "don.jsonl"),
                      ("SCORECARD", "scorecard.json")):
        monkeypatch.setattr(pi, name, pc / rel if rel else pc)
    monkeypatch.setattr(pi, "SEAT_DIR", tmp_path / "seat")
    monkeypatch.setattr(pi, "HYP", tmp_path / "hyp")
    monkeypatch.setattr(pi, "_box_catalogues", lambda: (FAMS, UNI, {"dead_one"}))
    good = dict(_recipe(), dedup_key="x", model="fake")
    bundle = {"schema": "paperclip_bundle/1", "spend": {"calls_by_role": {"x": 2}},
              "rows": [good, dict(_recipe(symbols=["NVDA"])),
                       {"kind": "revival", "producer": "dead_one", "diagnosis": "d",
                        "tweak": "t", "role": "dead_producer_reviver"},
                       {"kind": "triage", "cell": "XAUUSD.carry.p=1", "prior": 0.7,
                        "role": "triage_prior"}]}
    assert pi.score({}, "no runs")["health"] == "RED"
    last = pi.ingest([("101", bundle)])
    assert last["seat_rows"] == 1 and last["revivals"] == 1 and last["triage"] == 1
    assert last["refused"].get("symbols") == 1
    seat = json.loads(next((tmp_path / "seat").glob("discoveries_*.json")).read_text())
    row = seat["discoveries"][0]
    assert row["source"] == "paperclip" and row["params"]["timeframe"] == "H1"
    assert row["available_time"] and row["url"].startswith("paperclip://x/")
    again = pi.ingest([("102", bundle)])
    assert again["seat_rows"] == 0 and again["refused"].get("duplicate") == 1
    doc = pi.score(last, None)
    assert doc["health"] == "GREEN" and doc["roles"]["x"]["calls"] == 2
    assert doc["triage"]["weight_earned"] is False
