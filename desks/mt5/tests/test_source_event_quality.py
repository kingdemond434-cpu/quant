"""DATA-31: per (source, event class) confirmation, revision, unique information, latency,
lead/lag, false positives and incremental predictive value -- on synthetic ledgers."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro import attribution as at  # noqa: E402
from macro import source_event_quality as q  # noqa: E402

from libs.research import sensor_engines as se  # noqa: E402

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
NOW = T0 + timedelta(days=40)
WORDS = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india",
         "juliet", "kilo", "lima", "mike", "november", "oscar", "papa", "quebec", "romeo",
         "sierra", "tango", "uniform", "victor", "whiskey", "xray")


def _title(i: int) -> str:
    """Four words no other story index shares: distinct stories never cluster together."""
    return " ".join(f"{WORDS[(i * 4 + k) % len(WORDS)]}{i}" for k in range(4))


def _ev(eid: str, src: str, title: str, t: datetime, *, h: str | None = None,
        cat: str = "central_bank", pub: datetime | None = None, **kw: Any) -> dict[str, Any]:
    return {"event_id": eid, "source_id": src, "title": title, "category": cat,
            "received_at": t.isoformat(), "published_at": pub.isoformat() if pub else None,
            "content_hash": h or eid, **kw}


def _cell(doc: dict[str, Any], src: str, cls: str = "central_bank") -> dict[str, Any]:
    return next(c for c in doc["cells"] if c["source_id"] == src and c["event_class"] == cls)


def _story_rows(i: int) -> list[dict[str, Any]]:
    t = T0 + timedelta(days=i * 0.5)
    title = _title(i)
    return [_ev(f"a{i}", "WIRE", title, t, pub=t - timedelta(seconds=30)),
            # an independent second carrier one hour later
            _ev(f"b{i}", "PAPER", title, t + timedelta(hours=1),
                pub=t + timedelta(minutes=50)),
            # a verbatim syndicated copy of WIRE's story: same content hash
            _ev(f"c{i}", "AGGREGATOR", title, t + timedelta(minutes=30), h=f"a{i}")]


def test_unique_information_confirmation_and_the_speed_a_first_source_buys() -> None:
    rows = [r for i in range(8) for r in _story_rows(i)]
    doc = q.table(q.from_event_ledger(rows), now=NOW)
    wire, paper, agg = _cell(doc, "WIRE"), _cell(doc, "PAPER"), _cell(doc, "AGGREGATOR")
    assert doc["n_stories"] == 8
    assert wire["unique_information"]["value"] == 1.0
    assert paper["unique_information"]["value"] == 0.0
    assert agg["unique_information"]["value"] == 0.0           # a copy is never new information
    assert wire["confirmation_rate"]["value"] == 1.0           # PAPER is independent
    assert agg["confirmation_rate"]["value"] == 1.0
    assert wire["ipv_speed_s"]["value"] == 3600.0              # the copy does not count as later
    assert paper["ipv_speed_s"]["value"] == 0.0
    assert paper["lag_behind_first_s"]["value"] == 3600.0
    assert wire["latency_s"]["value"] == 30.0
    assert wire["false_positive_rate"]["value"] == 0.0


def test_a_copy_alone_confirms_nothing_and_an_unconfirmed_claim_is_a_false_positive() -> None:
    rows = []
    for i in range(6):
        t = T0 + timedelta(days=i)
        title = _title(i)
        rows += [_ev(f"a{i}", "RUMOUR", title, t),
                 _ev(f"c{i}", "MIRROR", title, t + timedelta(minutes=5), h=f"a{i}")]
    rows.append(_ev("late", "RUMOUR", _title(99), NOW - timedelta(hours=2)))
    doc = q.table(q.from_event_ledger(rows), now=NOW)
    r = _cell(doc, "RUMOUR")
    assert r["confirmation_rate"]["value"] == 0.0
    assert r["false_positive_rate"]["n"] == 6                  # the open window is not judged
    assert r["false_positive_rate"]["value"] == 1.0
    # contradicted, even when corroborated, is a false positive
    rows2 = [r for i in range(6) for r in _story_rows(i)]
    rows2[0]["contradicted_by"] = ["CENTRAL_BANK"]
    w = _cell(q.table(q.from_event_ledger(rows2), now=NOW), "WIRE")
    assert w["false_positive_rate"]["k"] == 1


def test_revision_rate_from_reissued_stories_and_sensor_vintages() -> None:
    rows = [r for i in range(6) for r in _story_rows(i)]
    rows.append(_ev("a0v2", "WIRE", rows[0]["title"], T0 + timedelta(hours=2), h="a0-changed"))
    w = _cell(q.table(q.from_event_ledger(rows), now=NOW), "WIRE")
    assert w["revision_rate"]["k"] == 1 and w["revision_rate"]["n"] == 6
    assert w["n_copies"] == 1
    sens = []
    for i in range(6):
        t = (T0 + timedelta(days=i)).isoformat()
        sens.append({"observation_id": f"o{i}", "source_id": "alfred:PAYEMS",
                     "sensor_class": "macro_release", "entity": "US", "metric": "NFP",
                     "event_time": f"2026-0{i + 1}-01", "received_at": t,
                     "publication_time": t})
    sens.append({"observation_id": "o0r", "revision_of": "o0", "source_id": "alfred:PAYEMS",
                 "sensor_class": "macro_release", "entity": "US", "metric": "NFP",
                 "event_time": "2026-01-01", "received_at": NOW.isoformat()})
    s = _cell(q.table(q.from_sensor_rows(sens), now=NOW), "alfred:PAYEMS", "macro_release")
    assert s["revision_rate"]["value"] == round(1 / 6, 4)
    assert s["latency_s"]["value"] == 0.0


def test_thin_cells_are_unmeasured_with_their_reason_never_zero() -> None:
    doc = q.table(q.from_event_ledger(_story_rows(0)), now=NOW)
    w = _cell(doc, "WIRE")
    for f in ("confirmation_rate", "false_positive_rate", "revision_rate", "unique_information"):
        assert w[f]["value"] == q.UNMEASURED and "< 5" in w[f]["why"]
    assert w["ipv_accuracy"]["verdict"] == se.UNMEASURED
    assert w["move_confirmation"]["value"] == q.UNMEASURED


def _ipv_rows(n: int, seed: int, skill: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = np.random.default_rng(seed)
    rows, atts = [], []
    for i in range(n):
        t = T0 + timedelta(hours=7 * i)
        up = bool(rng.random() < 0.5)
        right = bool(rng.random() < skill)
        sig = (1.0 if up else -1.0) * (1.0 if right else -1.0)
        rows.append(_ev(f"e{i}", "DESK_WIRE", _title(i), t,
                        forecasts=[{"symbol": "EURUSD", "expected_move_sigma": sig}]))
        atts.append({"event_id": f"e{i}", "leading_instrument": "EURUSD",
                     "leading_move_sigma": 1.5 if up else -1.5, "lead_s": 600.0,
                     "move_confirmed": right})
    return rows, atts


def test_incremental_accuracy_gain_for_a_skilled_source_and_none_for_a_coin() -> None:
    rows, atts = _ipv_rows(300, 3, 0.8)
    cell = _cell(q.table(q.from_event_ledger(rows, atts), now=NOW + timedelta(days=200)),
                 "DESK_WIRE")
    acc = cell["ipv_accuracy"]
    assert acc["verdict"] == se.GAIN and acc["logloss_reduction"] > 0
    assert cell["move_confirmation"]["value"] > 0.7
    assert cell["lead_to_move_s"]["value"] == 600.0
    rows, atts = _ipv_rows(300, 4, 0.5)
    coin = _cell(q.table(q.from_event_ledger(rows, atts), now=NOW + timedelta(days=200)),
                 "DESK_WIRE")["ipv_accuracy"]
    assert coin["verdict"] != se.GAIN


def test_persist_new_keeps_the_first_marking_and_build_reads_it(tmp_path: Path) -> None:
    path = tmp_path / "event_attribution.jsonl"
    a1 = at.Attribution("e1", "central_bank", "WIRE", "MEASURED", lead_s=60.0,
                        leading_instrument="EURUSD", leading_move_sigma=1.2,
                        move_confirmed=True)
    un = at.Attribution("e2", "central_bank", "WIRE", "UNMEASURED")
    assert at.persist_new([a1, un], path) == 1
    assert at.persist_new([a1], path) == 0                      # re-marking appends nothing
    ledger = tmp_path / "event_ledger.jsonl"
    ledger.write_text("\n".join(json.dumps(r) for r in [
        _ev("e1", "WIRE", "rates held", T0)]) + "\n", "utf-8")
    doc = q.build(now=NOW, ledger=ledger, attributions=path, sensors=tmp_path / "none")
    assert doc["inputs"]["attributions"]["rows"] == 1
    assert doc["inputs"]["sensor_ledger"]["value"] == q.UNMEASURED
    empty = q.build(now=NOW, ledger=tmp_path / "x.jsonl", attributions=tmp_path / "y.jsonl",
                    sensors=tmp_path / "none")
    assert empty["status"] == q.UNMEASURED and empty["n_cells"] == 0
