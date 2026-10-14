"""The family floor reaches the judge: quota only on what ships, never-judged families named and
fenced, and the tape families' input ceiling lifted (2026-10-14)."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_coverage as jc  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import check_judge_coverage as fence  # noqa: E402

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _desk_state_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.research import research_priors
    monkeypatch.setattr(jc, "UNRUNNABLE_BANK", tmp_path / "unrunnable_specs.json")
    monkeypatch.setattr(jc, "RATCHET", tmp_path / "judge_backlog_ratchet.json")
    monkeypatch.setattr(jc, "REPORT", tmp_path / "JUDGE_COVERAGE.json")
    monkeypatch.setattr(jc, "CONVERSION_HANDOFF", tmp_path / "conversion_handoff.json")
    monkeypatch.setattr(jc, "GATES_REPORT", tmp_path / "universal_gates_external.json")
    monkeypatch.setattr(jc, "TAPE_DIR", tmp_path / "no_tape")
    monkeypatch.setattr(research_priors, "STATE_DIR", tmp_path / "research_priors")
    monkeypatch.delenv("QUANT_LAWGATE_SOURCE_VIEW", raising=False)


def _rows(spec: dict[str, int], *, age_h: float = 100.0) -> list[dict]:
    seen = (NOW - timedelta(hours=age_h)).isoformat()
    return [{"symbol": f"S{i}", "family": fam, "params": {"rr": 1.0 + i}, "first_seen": seen}
            for fam, n in spec.items() for i in range(n)]


def _park(rows: list[dict], family: str, reason: str = "build_failed") -> int:
    """Write every row of `family` into the bank, exactly as `update_unrunnable_bank` would."""
    bank = {}
    for r in rows:
        if r["family"] != family:
            continue
        cid = jc._cell_id(r)
        assert cid, "the gauntlet's identity function must resolve in the test tree"
        bank[cid] = {"reason": reason, "sym": r["symbol"], "family": family, "tf": "H1",
                     "bar_bytes": 0, "why": f"{family} raised TypeError: unexpected 'chart'",
                     "parked_at": NOW.isoformat()}
    jc.UNRUNNABLE_BANK.write_text(json.dumps(bank), "utf-8")
    return len(bank)


# ------------------------------------------------------------------ quota is spent on what ships
def test_a_parked_family_gets_no_quota_and_is_named_not_starved(tmp_path: Path) -> None:
    rows = _rows({"alpha": 30, "cot_change_fade": 12})
    assert _park(rows, "cot_change_fade") == 12
    doc = jc.build(rows, ledger=tmp_path / "no.jsonl", ratchet=tmp_path / "no.json", now=NOW)
    cot = doc["families"]["cot_change_fade"]
    assert cot["unjudged"] == 12, "a parked defect is still owed (audit of PR #290)"
    assert cot["shippable"] == 0 and cot["parked_unrunnable"] == 12
    assert cot["parked_by_reason"] == {"build_failed": 12}
    assert doc["quota"].get("cot_change_fade") is None, "no hour is promised to an unshipped cell"
    assert cot["queued"] == 0, "the published head is the docket that ships"
    assert "cot_change_fade" not in doc["starved"], "held by the bank with a reason, not starved"
    assert doc["families"]["alpha"]["quota"] > 0
    assert doc["totals"]["parked_unrunnable_total"] == 12
    assert doc["totals"]["shippable_total"] == 30


def test_the_quota_matches_what_order_docket_ships(tmp_path: Path) -> None:
    rows = _rows({"alpha": 20, "beta": 8})
    _park(rows, "beta")
    ordered, doc = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    shipped = {r["family"] for r in ordered}
    assert shipped == {"alpha"}, "the bank filter removes the parked family from the docket"
    assert set(doc["quota"]) == shipped, "and the allocation now describes exactly that docket"


# ------------------------------------------------------------------ never judged, named
def test_a_never_judged_family_is_published_with_its_reasons(tmp_path: Path) -> None:
    rows = _rows({"alpha": 10, "cot_net_fade": 5, "orderflow_imbalance": 6})
    _park(rows, "cot_net_fade")
    jc.GATES_REPORT.write_text(json.dumps({"verdicts": [
        {"cell": "x1", "family": "orderflow_imbalance", "sym": "S0", "passed": None,
         "terminal_gate": "UNKNOWN", "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED"},
        {"cell": "x2", "family": "orderflow_imbalance", "sym": "S1", "passed": False,
         "unmeasured": True, "terminal_gate": "UNKNOWN", "unknown_reason": "no_series"},
    ]}), "utf-8")
    tape = tmp_path / "tape"
    for sym, n in (("EURUSD", 45), ("XAUUSD", 20)):
        (tape / sym).mkdir(parents=True)
        for d in range(n):
            (tape / sym / f"2026-08-{d:02d}.parquet").write_bytes(b"")
    jc.TAPE_DIR = tape
    ledger = tmp_path / "gate.jsonl"
    ledger.write_text(json.dumps({"at": NOW.isoformat(), "cell": "S0.alpha.p=x",
                                  "family": "alpha", "passed": False,
                                  "terminal_gate": "in_sample_screen"}) + "\n", "utf-8")
    doc = jc.build(rows, ledger=ledger, ratchet=tmp_path / "no.json", now=NOW)
    nj = doc["never_judged"]
    assert set(nj) == {"cot_net_fade", "orderflow_imbalance"}, "alpha holds a real verdict"
    assert "build_failed=5" in nj["cot_net_fade"]["reason"]
    assert "unexpected 'chart'" in nj["cot_net_fade"]["reason"], "the bank's own why is carried"
    of = nj["orderflow_imbalance"]["reason"]
    assert "NOT_RUN_BUILD_BUDGET_DEFERRED=1" in of and "no_series=1" in of
    assert "tick tape" in of and "max 45" in of and "0 of 2 symbols reach it" in of
    assert doc["families"]["orderflow_imbalance"]["never_judged_reason"] == of
    assert doc["totals"]["families_never_judged"] == 2


def test_never_judged_says_unmeasured_when_the_judge_report_is_absent(tmp_path: Path) -> None:
    doc = jc.build(_rows({"beta": 3}), ledger=tmp_path / "no.jsonl",
                   ratchet=tmp_path / "no.json", now=NOW)
    assert "UNMEASURED" in doc["never_judged"]["beta"]["reason"]


def test_the_judge_report_is_read_once_per_pass(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    jc.GATES_REPORT.write_text(json.dumps({"verdicts": []}), "utf-8")
    reads: list[str] = []
    real = Path.read_text

    def counting(self: Path, *a: object, **k: object) -> str:
        if self.name == jc.GATES_REPORT.name:
            reads.append(str(self))
        return real(self, *a, **k)                                       # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", counting)
    jc.build(_rows({"beta": 3}), ledger=tmp_path / "no.jsonl", ratchet=tmp_path / "no.json",
             now=NOW)
    assert len(reads) == 1, reads
    assert jc._GATES_MEMO is None, "nothing stays resident after the pass"


# ------------------------------------------------------------------ the fence
def _report(tmp_path: Path, **row: object) -> Path:
    base: dict[str, object] = {"mined": 49_108, "unjudged": 49_108, "shippable": 49_108,
                               "queued": 244, "quota": 244, "judged_window": 0,
                               "judged_total": 0, "window_h": 200.0,
                               "oldest_unjudged_age_h": 782.6}
    base.update(row)
    p = tmp_path / "JUDGE_COVERAGE.json"
    p.write_text(json.dumps({
        "at": NOW.isoformat(), "families": {"orderflow_imbalance": base},
        "never_judged": {"orderflow_imbalance": {"reason": "last sweep: UNKNOWN=20434"}},
        "totals": {}}), "utf-8")
    return p


def test_fence_fails_a_never_judged_family_on_the_box(tmp_path: Path) -> None:
    doc = fence.judge(_report(tmp_path), require_state=True, now=NOW)
    nj = next(c for c in doc["checks"] if c["metric"] == "never_judged")
    assert nj["state"] == "FAIL" and doc["verdict"] == "FAIL"
    assert "orderflow_imbalance" in nj["why"] and "UNKNOWN=20434" in nj["why"]
    assert nj["families"][0]["reason"] == "last sweep: UNKNOWN=20434"


def test_fence_only_warns_on_a_source_view_copy(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """A laws-only run reads the box's published copy: published, never a permanent CI red."""
    monkeypatch.setenv("QUANT_LAWGATE_SOURCE_VIEW", "1")
    doc = fence.judge(_report(tmp_path), now=NOW)
    nj = next(c for c in doc["checks"] if c["metric"] == "never_judged")
    assert nj["state"] == "WARN" and doc["verdict"] == "PASS"
    # --require-state binds even when the caller inherits the source-view flag.
    assert fence.judge(_report(tmp_path), require_state=True, now=NOW)["verdict"] == "FAIL"


def test_fence_is_armed_on_the_trading_host(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import host_identity

    class _Id:
        may_be_trading = True

    monkeypatch.setattr(host_identity, "identify", lambda *a, **k: _Id())
    assert fence._armed(False) is True
    monkeypatch.setenv("QUANT_LAWGATE_SOURCE_VIEW", "1")
    assert fence._armed(False) is False


@pytest.mark.parametrize("row", [{"oldest_unjudged_age_h": 47.0},
                                 {"judged_total": 1},
                                 {"mined": 0, "unjudged": 0, "shippable": 0, "queued": 0}])
def test_fence_does_not_fire_inside_its_terms(tmp_path: Path, row: dict) -> None:
    doc = fence.judge(_report(tmp_path, **row), require_state=True, now=NOW)
    nj = next(c for c in doc["checks"] if c["metric"] == "never_judged")
    assert nj["state"] == "OK"


def test_fence_and_organ_share_one_threshold() -> None:
    assert fence.NEVER_JUDGED_MAX_AGE_H == jc.NEVER_JUDGED_MAX_AGE_H == 48.0


def test_fully_parked_family_is_not_starved_and_takes_no_remainder_room(tmp_path: Path) -> None:
    p = tmp_path / "JUDGE_COVERAGE.json"
    p.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"cot_change_fade": {"unjudged": 7352, "shippable": 0, "queued": 0,
                                         "quota": 0, "judged_window": 0, "window_h": 1.0}},
        "value_ranking": [
            {"family": "cot_change_fade", "unjudged": 7352, "shippable": 0, "quota": 0,
             "remainder": 0},
            {"family": "alpha", "unjudged": 900, "shippable": 900, "quota": 500,
             "remainder": 256}],
        "totals": {}}), "utf-8")
    doc = fence.judge(p, now=NOW)
    states = {c["metric"]: c["state"] for c in doc["checks"]}
    assert states["families_starved"] == "OK"
    assert states["remainder_follows_ranking"] == "OK"


# ------------------------------------------------------------------ the tape ceiling
def _write_tape(root: Path, sym: str, days: int) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    frames = []
    (root / sym).mkdir(parents=True)
    for day in range(days):
        start = pd.Timestamp("2026-07-01", tz="UTC") + pd.Timedelta(days=day)
        ts = start + pd.to_timedelta(np.sort(rng.choice(86_400_000, 400, replace=False)),
                                     unit="ms")
        mid = 1.1 + np.cumsum(rng.normal(0, 1e-5, 400))
        sp = np.abs(rng.normal(1e-4, 2e-5, 400))
        df = pd.DataFrame({"ts": ts, "bid": mid - sp / 2, "ask": mid + sp / 2})
        df.to_parquet(root / sym / f"{start.date()}.parquet")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


@pytest.mark.parametrize("tf,rule", [("H1", "60min"), ("M5", "5min"), ("D1", "1440min")])
def test_tape_series_reads_the_whole_tape_exactly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                  tf: str, rule: str) -> None:
    from research import orthogonal_sweep as osw
    raw = _write_tape(tmp_path, "EURUSD", 45)
    monkeypatch.setattr(osw, "TAPE", tmp_path)
    osw._tape_minutes.cache_clear()
    try:
        idx = pd.date_range("2026-06-25", "2026-08-20", freq=rule, tz="UTC")
        spread, flow = osw._tape_series("EURUSD", idx, tf)
    finally:
        osw._tape_minutes.cache_clear()
    t = raw.assign(ts=pd.to_datetime(raw["ts"], utc=True)).sort_values("ts").set_index("ts")
    want_s = (t["ask"] - t["bid"]).resample(rule).mean().reindex(idx).ffill()
    mid = (t["ask"] + t["bid"]) / 2.0
    want_f = np.sign(mid.diff()).fillna(0.0).resample(rule).sum().reindex(idx).ffill()
    assert np.allclose(spread.fillna(-1.0), want_s.fillna(-1.0), rtol=1e-9, atol=1e-15)
    assert (flow.fillna(-1.0) == want_f.fillna(-1.0)).all()
    # ALL 45 day files, not the last 30: the first tape day carries a spread.
    assert spread.loc["2026-07-01 12:00":"2026-07-01 13:00"].notna().all()


def test_no_tape_is_still_none() -> None:
    from research import orthogonal_sweep as osw
    assert osw._tape_series("NO_SUCH_SYMBOL_ANYWHERE", pd.DatetimeIndex([]), "H1") == (None, None)


# ------------------------------------------------------------------ the sealed patch, once applied
_spec = importlib.util.spec_from_file_location(
    "_gaunt_floor", ROOT / "desks" / "mt5" / "scripts" / "external_gauntlet.py")


def _gauntlet():
    assert _spec and _spec.loader
    g = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(g)
    return g


def test_floor_interleave_once_the_sealed_patch_lands(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skipped until `judging/floor_reach_sealed.patch` is applied by a principal-gated hand."""
    g = _gauntlet()
    if not hasattr(g, "_floor_interleave"):
        pytest.skip("sealed floor-reach patch not applied")
    monkeypatch.setattr(g, "_coverage_quota", lambda: {"big": 900, "of": 50, "liq": 50})
    takes = {"big": [{"sym": f"A{i // 5}", "family": "big"} for i in range(500)],
             "of": [{"sym": f"B{i // 2}", "family": "of"} for i in range(40)],
             "liq": [{"sym": "C", "family": "liq"} for _ in range(10)]}
    out = g._floor_interleave(takes)
    assert len(out) == 550 and all(sp in out for rows in takes.values() for sp in rows)
    assert {sp["family"] for sp in out[:100]} == {"big", "of", "liq"}, "every prefix reaches all"
    for fam, rows in takes.items():
        assert [sp for sp in out if sp["family"] == fam] == rows, "each family keeps its order"
