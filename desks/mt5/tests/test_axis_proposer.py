"""A SYNTHETIC DESK WITH ONE AXIS PLANTED IN IT, and the organ has to find exactly that one.

An organ that proposes new coordinates for the search space is the last place a lucky number may
pass for a discovery: whatever it registers becomes an extra tag on every cell the desk ever
judges. So the tape here is built with ONE known structure -- a liquidity state, in blocks, whose
PREVIOUS day shifts the mean of the next day's residual -- and every test asserts the organ
recovered that and refused everything else.

The other half of the contract, which matters as much: a candidate with no planted effect FAILS
rather than being talked up, a relabelling of `session` is REDUNDANT however well it scores, one
pass is never enough (PASS -> pending -> REGISTERED on the second consecutive run), the evidence
ledger is append-only, an absent series is UNMEASURED with its reason rather than a clean zero,
the live-loss gate is APPLIED when the residual queue carries a strategy_loss row, and `--dry-run`
writes nothing at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import axis_proposer as ap  # noqa: E402
from research import universe_policy as up  # noqa: E402

N_DAYS = 520
HOURS = (0, 3, 6, 9, 12, 15, 18, 21)
BASKET = ("EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCAD", "USDCHF")
TARGETS = ("EURNOK", "GBPSEK", "AUDCAD", "CADCHF", "NZDCAD")
#: The planted effect on the residual mean, per liquidity state of the PREVIOUS day.
PLANT = {0: -0.0020, 1: 0.0, 2: 0.0020}
NOISE = 0.0035


def _days() -> pd.DatetimeIndex:
    return pd.date_range("2023-01-02", periods=N_DAYS, freq="D", tz="UTC")


def _states() -> np.ndarray:
    """Liquidity state in ten-day blocks -- persistent, which is exactly what makes the i.i.d.
    null wrong and the block null necessary."""
    return np.repeat(np.arange(N_DAYS // 10 + 2) % 3, 10)[:N_DAYS]


def _bars_frame(rets: np.ndarray, spread: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    """H1 bars whose close-to-close daily return is EXACTLY `rets`, with the day's move parked in
    a rotating hour so the day's peak session is not always the same one."""
    days = _days()
    stamps, close, spr = [], [], []
    price = 100.0
    for d, day in enumerate(days):
        parts = rng.normal(0.0, 1e-4, len(HOURS))
        parts[d % len(HOURS)] += float(rets[d]) - float(parts.sum())
        for hour, part in zip(HOURS, parts, strict=True):
            price *= float(np.exp(part))
            stamps.append(day + pd.Timedelta(hours=int(hour)))
            close.append(price)
            spr.append(float(spread[d]))
    c = np.asarray(close, dtype="float64")
    frame = pd.DataFrame({"open": np.concatenate([[c[0]], c[:-1]]), "high": c * 1.0005,
                          "low": c * 0.9995, "close": c, "tick_volume": 1000.0,
                          "spread": spr, "real_volume": 0.0},
                         index=pd.DatetimeIndex(stamps, name="time"))
    frame["high"] = frame[["open", "high", "close"]].max(axis=1)
    frame["low"] = frame[["open", "low", "close"]].min(axis=1)
    return frame


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """One synthetic desk: a dollar factor, gold, an equity index, five targets that load on all
    three, and a liquidity state planted into the targets' spread and their residual mean."""
    rng = np.random.default_rng(11)
    uni = tmp_path / "universe"
    uni.mkdir(parents=True)
    state = _states()
    plant = np.asarray([PLANT[int(state[max(d - 1, 0)])] for d in range(N_DAYS)])
    usd = rng.normal(0.0, 0.005, N_DAYS)
    gold = rng.normal(0.0, 0.008, N_DAYS)
    equity = rng.normal(0.0, 0.010, N_DAYS)
    flat = np.full(N_DAYS, 10.0)

    for sym, weight in zip(BASKET, (-1, -1, -1, 1, 1, 1), strict=True):
        rets = usd / weight + rng.normal(0.0, 0.001, N_DAYS)
        _bars_frame(rets, flat, rng).to_parquet(uni / f"{sym}_H1.parquet")
    _bars_frame(gold, flat, rng).to_parquet(uni / "XAUUSD_H1.parquet")
    _bars_frame(equity, flat, rng).to_parquet(uni / "US500_H1.parquet")
    # THE PLANT. The spread carries the state on day d; the residual mean carries it on day d+1,
    # because every label in this organ is lagged to the previous close.
    spread = 10.0 * (1.0 + state)
    for sym in TARGETS:
        rets = (0.4 * usd + 0.2 * gold + 0.1 * equity + plant
                + rng.normal(0.0, NOISE, N_DAYS))
        _bars_frame(rets, spread, rng).to_parquet(uni / f"{sym}_H1.parquet")

    registry = {s: {"asset_class": "forex"} for s in (*BASKET, *TARGETS)}
    registry["XAUUSD"] = {"asset_class": "metals"}
    registry["US500"] = {"asset_class": "indices"}
    (tmp_path / "universe.json").write_text(json.dumps(registry), "utf-8")
    monkeypatch.setattr(up, "UNIVERSE", tmp_path / "universe.json")
    up._registry.cache_clear()

    days = _days()
    (tmp_path / "axes").mkdir()
    (tmp_path / "axes" / "ecb.json").write_text(json.dumps({"series": {"test_rate": {"points": [
        {"d": str(d.date()), "v": float(v)} for d, v in
        zip(days, rng.normal(0.0, 1.0, N_DAYS).cumsum(), strict=True)]}}}), "utf-8")
    (tmp_path / "forced_flow.json").write_text(json.dumps({"events": [
        {"date": str(d.date()), "instruments": list(TARGETS)} for d in days[::2]]}), "utf-8")
    (tmp_path / "sleeves.json").write_text(
        json.dumps({"sleeves": [{"symbol": s, "status": "LIVE"} for s in TARGETS]}), "utf-8")
    (tmp_path / "STANDING_QUESTIONS.json").write_text(json.dumps({"questions": {"Q3": {
        "findings": [{"symbol": TARGETS[0], "axis": "ecb:test_rate", "corr": 0.3, "p_bonf": 0.0},
                     {"symbol": TARGETS[1], "axis": "ecb:absent_rate", "corr": 0.3,
                      "p_bonf": 0.0}]}}}), "utf-8")
    (tmp_path / "REPRESENTATION_DISCOVERY.json").write_text(json.dumps(
        {"directional": [{"name": "composite::zscore(ret)/atr", "excess_nats": 0.01}]}), "utf-8")
    (tmp_path / "RESIDUAL_QUEUE.json").write_text(json.dumps({"top": []}), "utf-8")

    for name, value in (("UNIVERSE", uni), ("AXES_DIR", tmp_path / "axes"),
                        ("FORCED_FLOW", tmp_path / "forced_flow.json"),
                        ("SLEEVES", tmp_path / "sleeves.json"),
                        ("LIVE_LEDGER", tmp_path / "live_ledger.jsonl"),
                        ("STANDING", tmp_path / "STANDING_QUESTIONS.json"),
                        ("REPRESENTATION", tmp_path / "REPRESENTATION_DISCOVERY.json"),
                        ("RESIDUAL_REPORT", tmp_path / "RESIDUAL_QUEUE.json"),
                        ("RESIDUAL_LEDGER", tmp_path / "residual_queue.jsonl"),
                        ("OUT_REPORT", tmp_path / "AXIS_PROPOSER.json"),
                        ("PROPOSALS", tmp_path / "axis_proposals.jsonl"),
                        ("EXTENSIONS", tmp_path / "axis_registry_extensions.json")):
        monkeypatch.setattr(ap, name, value)
    ap._BARS.clear()
    ap._CACHE.clear()
    return tmp_path


def _run(symbols: int = 5) -> dict:
    """One full pass, written the way the CLI writes it."""
    report, extensions = ap.build(symbols, 120)
    ap.write(report, extensions)
    return report


def _row(report: dict, axis_id: str) -> dict:
    return next(r for r in report["tested"] if r["axis_id"] == axis_id)


# --------------------------------------------------------------- the planted axis is found
def test_planted_axis_passes_out_of_sample_on_the_first_run(desk):
    report = _run()
    row = _row(report, "liquidity_state")
    assert row["verdict"] == "PASS", row
    assert row["instruments_passed"] >= ap.MIN_INSTRUMENTS
    assert row["oos_share_median"] > 0.0
    assert row["p_median"] < ap.P_MAX
    # It is NOT registered yet, and the report says so in the field that exists for saying so.
    assert report["registered"] == []
    assert "liquidity_state" in report["pending_second_pass"]
    assert json.loads((desk / "axis_registry_extensions.json").read_text("utf-8"))["axes"] == []


def test_a_second_consecutive_pass_registers_it_with_its_evidence(desk):
    first = _run()
    assert "liquidity_state" in first["pending_second_pass"]
    second = _run()
    assert _row(second, "liquidity_state")["verdict"] == "PASS"
    assert second["registered"] == ["liquidity_state"]
    assert second["newly_registered"] == ["liquidity_state"]
    assert "liquidity_state" not in second["pending_second_pass"]
    # The ontology's bare `spread` is the SAME planted state under another name. It is refused as
    # a twin rather than registered as a second tag for one fact.
    twin = _row(second, "mechanism::spread")
    assert twin["verdict"] == "REDUNDANT" and twin["resembles"] == "liquidity_state"

    doc = json.loads((desk / "axis_registry_extensions.json").read_text("utf-8"))
    entry = doc["axes"][0]
    assert entry["axis_id"] == "liquidity_state"
    assert entry["definition"]["kind"] == "own_observable"
    assert entry["registered_at"] == second["at"]
    assert entry["evidence"]["instruments_passed"] >= ap.MIN_INSTRUMENTS
    assert entry["evidence"]["p_median"] < ap.P_MAX
    assert doc["contract"] == ap.CONTRACT and doc["rule"] == ap.RULE
    # The contract is cashable, not prose: the registry can read the tag without importing this
    # organ's internals, and an axis nobody registered is UNMEASURED rather than invented.
    assert [a["axis_id"] for a in ap.extension_axes()] == ["liquidity_state"]
    assert ap.axis_tag("liquidity_state", TARGETS[0]) in ("deep", "mid", "thin")
    assert ap.axis_tag("no_such_axis", TARGETS[0]) == "UNMEASURED"


# ------------------------------------------------------------------ and everything else is not
def test_a_candidate_with_no_planted_effect_fails(desk, monkeypatch):
    """A rule that buckets the same days at random explains nothing out of sample, and FAIL is
    what that must be called -- not 'inconclusive', not a smaller number quietly reported."""
    rng = np.random.default_rng(3)
    noise = pd.Series(np.repeat(rng.integers(0, 3, N_DAYS // 5 + 1), 5)[:N_DAYS].astype(float),
                      index=_days())

    def _random(symbol, defn, index):
        return noise.reindex(index), ""

    monkeypatch.setitem(ap.LABELLERS, "planted_noise", _random)
    monkeypatch.setattr(ap, "DECLARED", [{
        "axis_id": "pure_noise", "name": "a rule with nothing behind it", "source": "declared",
        "definition": {"kind": "planted_noise", "buckets": ["a", "b", "c"]}}])
    report = _run()
    row = _row(report, "pure_noise")
    assert row["verdict"] == "FAIL"
    assert row["instruments_passed"] < ap.MIN_INSTRUMENTS
    assert "pure_noise" not in report["pending_second_pass"]
    assert "pure_noise" not in report["registered"]


def test_a_relabelling_of_session_is_refused_as_redundant(desk, monkeypatch):
    """However well it scores. An axis the desk already has costs multiplicity budget twice and
    buys no new ground, and this is the only verdict that says so."""
    def _echo_session(symbol, defn, index):
        return ap.reference_labels(symbol, index).get("session"), ""

    monkeypatch.setitem(ap.LABELLERS, "echo_session", _echo_session)
    monkeypatch.setattr(ap, "DECLARED", [{
        "axis_id": "session_by_another_name", "name": "session, relabelled", "source": "declared",
        "definition": {"kind": "echo_session"}}])
    report = _run()
    row = _row(report, "session_by_another_name")
    assert row["verdict"] == "REDUNDANT"
    assert row["resembles"] == "session"
    assert row["resemblance"] > ap.REDUNDANT_AT
    assert "session_by_another_name" not in report["pending_second_pass"]
    assert "session_by_another_name" not in report["registered"]


def test_an_absent_series_is_unmeasured_and_never_a_failure(desk):
    """Q3 named two correlates; one is published under data/axes and one is not. The published one
    is judged, the missing one is UNMEASURED BY NAME -- absence never resolves to a verdict."""
    report = _run()
    absent = _row(report, "q3_correlate::ecb:absent_rate")
    assert absent["verdict"] == "UNMEASURED"
    assert absent["instruments_tested"] == 0
    assert "not published under data/axes" in report["unmeasured"]["q3_correlate::ecb:absent_rate"]
    assert _row(report, "q3_correlate::ecb:test_rate")["verdict"] in ("FAIL", "PASS")
    # The learned lane names a composite this organ cannot rebuild; that is recorded, not skipped.
    assert "cannot rebuild" in report["unmeasured"]["REPRESENTATION_DISCOVERY.json"]


def test_no_priced_universe_is_an_unmeasured_run_rather_than_an_empty_one(desk, monkeypatch):
    monkeypatch.setattr(ap, "UNIVERSE", desk / "nothing_here")
    ap._BARS.clear()
    ap._CACHE.clear()
    report, extensions = ap.build(5, 30)
    assert report["status"] == "UNMEASURED"
    assert report["tested"] == [] and report["registered"] == []
    assert "dollar basket" in report["unmeasured"]["residual"]
    assert extensions["axes"] == []


# ------------------------------------------------------------------------------ the machinery
def test_the_permutation_null_is_the_test_and_not_decoration():
    """Three properties the null has to have, or every persistent label looks significant: a real
    effect bottoms the p out, pure noise does not, and a block permutation moves labels around
    without inventing or losing any."""
    rng = np.random.default_rng(5)
    days = _days()
    state = _states()
    labels = pd.Series([["a", "b", "c"][int(s)] for s in state], index=days, dtype=object)

    planted = pd.Series(np.asarray([PLANT[int(s)] for s in state])
                        + rng.normal(0.0, NOISE, N_DAYS), index=days)
    hit = ap.test_labels(planted, labels, np.random.default_rng(ap.SEED))
    assert hit["status"] == "OK"
    assert hit["oos_share"] > 0.05
    assert hit["p_perm"] == pytest.approx(1.0 / (ap.NULL_DRAWS + 1.0), abs=1e-6)
    assert hit["buckets"] == 3 and hit["n"] == N_DAYS

    noise = pd.Series(rng.normal(0.0, NOISE, N_DAYS), index=days)
    miss = ap.test_labels(noise, labels, np.random.default_rng(ap.SEED))
    assert miss["status"] == "OK"
    assert miss["p_perm"] > ap.P_MAX
    assert miss["oos_share"] < hit["oos_share"]

    codes = np.asarray(state, dtype=np.int64)
    shuffled = ap._block_permute(codes, ap.NULL_BLOCK, np.random.default_rng(1))
    assert len(shuffled) == len(codes)
    assert sorted(np.bincount(shuffled).tolist()) == sorted(np.bincount(codes).tolist())
    assert not np.array_equal(shuffled, codes)


def test_one_bucket_and_a_short_series_are_unmeasured_not_scored():
    days = _days()
    y = pd.Series(np.random.default_rng(2).normal(0.0, NOISE, N_DAYS), index=days)
    one = pd.Series(["always"] * N_DAYS, index=days, dtype=object)
    flat = ap.test_labels(y, one, np.random.default_rng(ap.SEED))
    assert flat["status"] == "UNMEASURED" and "buckets nothing" in flat["why"]

    short = ap.test_labels(y.iloc[:40], one.iloc[:40], np.random.default_rng(ap.SEED))
    assert short["status"] == "UNMEASURED" and f"{ap.MIN_DAYS} needed" in short["why"]
    assert ap.test_labels(y, None, np.random.default_rng(ap.SEED))["status"] == "UNMEASURED"


def test_the_evidence_ledger_is_append_only(desk):
    first = _run()
    before = (desk / "axis_proposals.jsonl").read_text("utf-8")
    rows = [json.loads(line) for line in before.splitlines()]
    assert len(rows) == len(first["tested"])
    assert {r["axis_id"] for r in rows} == {r["axis_id"] for r in first["tested"]}
    assert all({"at", "verdict", "per_instrument", "definition"} <= set(r) for r in rows)

    _run()
    after = (desk / "axis_proposals.jsonl").read_text("utf-8")
    assert after.startswith(before)
    assert len(after.splitlines()) == 2 * len(rows)


# ------------------------------------------------------------------------- the live-loss gate
def test_the_live_loss_gate_is_applied_when_the_queue_carries_a_strategy_loss(desk):
    """The residual that matters. An axis that sorts the tape and not the desk's own unexplained
    P&L has explained somebody else's problem."""
    sym = TARGETS[0]
    (desk / "RESIDUAL_QUEUE.json").write_text(json.dumps({"top": [
        {"level": "strategy_loss", "symbol": sym, "key": f"unexplained_loss:{sym}"}]}), "utf-8")
    rng = np.random.default_rng(23)
    state = _states()
    rows = []
    for d, day in enumerate(_days()[:300]):
        r = PLANT[int(state[max(d - 1, 0)])] * 400.0 + float(rng.normal(0.0, 0.5))
        rows.append({"time": day.isoformat(), "symbol": sym, "sleeve": "planted",
                     "r_multiple": round(r, 5)})
    (desk / "live_ledger.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    ap._CACHE.clear()

    report = _run()
    row = _row(report, "liquidity_state")
    assert report["live_loss_symbols"] == [sym]
    assert row["live_loss_tested"] == 1
    assert row["live_loss_passed"] == 1
    assert row["verdict"] == "PASS"


def test_an_unmeasurable_live_loss_stands_the_gate_down_by_name(desk):
    """Strategy_loss rows exist and no sleeve has enough realised P&L to score. The gate does not
    quietly pass and does not quietly block: it says UNMEASURED and names the floor."""
    (desk / "RESIDUAL_QUEUE.json").write_text(json.dumps({"top": [
        {"level": "strategy_loss", "symbol": TARGETS[0], "key": "unexplained_loss"}]}), "utf-8")
    (desk / "live_ledger.jsonl").write_text(json.dumps(
        {"time": "2024-01-02T00:00:00+00:00", "symbol": TARGETS[0], "r_multiple": -1.0}) + "\n",
        "utf-8")
    ap._CACHE.clear()
    report = _run()
    assert report["live_loss_symbols"] == []
    assert f"{ap.MIN_LIVE_DAYS} needed" in report["unmeasured"][f"live_loss:{TARGETS[0]}"]
    assert "stands down" in report["unmeasured"]["live_loss_gate"]
    assert _row(report, "liquidity_state")["verdict"] == "PASS"


# ------------------------------------------------------------------------------------- the CLI
def test_cli_dry_run_writes_nothing_and_a_real_run_writes_all_three(desk, capsys):
    assert ap.main(["--dry-run", "--symbols", "5", "--budget-s", "120"]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN: nothing written" in out
    assert len(out.strip().splitlines()) == 7
    for name in ("AXIS_PROPOSER.json", "axis_proposals.jsonl",
                 "axis_registry_extensions.json"):
        assert not (desk / name).exists(), name

    assert ap.main(["--symbols", "5", "--budget-s", "120"]) == 0
    report = json.loads((desk / "AXIS_PROPOSER.json").read_text("utf-8"))
    assert report["rule"] == ap.RULE
    assert set(report) >= {"at", "n_candidates", "tested", "registered", "pending_second_pass",
                           "unmeasured", "rule"}
    assert report["n_candidates"] == len(report["tested"])
    assert all(set(r) >= {"axis_id", "name", "instruments_passed", "oos_share_median", "p_median",
                          "verdict", "resembles"} for r in report["tested"])
    assert all(r["verdict"] in ap.VERDICTS for r in report["tested"])
    # Verdicts are ordered PASS first, so the reader meets the finding before the filing.
    assert [ap.VERDICTS.index(r["verdict"]) for r in report["tested"]] == sorted(
        ap.VERDICTS.index(r["verdict"]) for r in report["tested"])
    assert (desk / "axis_proposals.jsonl").exists()
    assert (desk / "axis_registry_extensions.json").exists()


def test_every_declared_candidate_is_reachable_and_the_library_is_well_formed(desk):
    """The declared library is the part a human wrote, so it is the part that rots silently: a
    definition naming a labeller that no longer exists would simply never be tested again."""
    assert {c["axis_id"] for c in ap.DECLARED} == {
        "liquidity_state", "positioning_extreme", "information_diffusion_speed",
        "balance_sheet_constraint"}
    for cand in ap.DECLARED:
        assert cand["definition"]["kind"] in ap.LABELLERS, cand["axis_id"]
        assert cand["definition"]["why"] and cand["name"]
    report = _run()
    tested = {r["axis_id"] for r in report["tested"]}
    assert {c["axis_id"] for c in ap.DECLARED} <= tested
    # Positioning has no COT file on this synthetic desk; that is UNMEASURED, by name, not a FAIL.
    assert _row(report, "positioning_extreme")["verdict"] == "UNMEASURED"
    assert "CFTC does not report" in report["unmeasured"]["positioning_extreme"]
    # Month-end is 2 days in 30, so on 520 days its bucket does not reach the per-bucket floor in
    # both halves: UNMEASURED with the floor named, never a FAIL that claims the desk looked.
    cal = _row(report, "balance_sheet_constraint")
    assert cal["verdict"] == "UNMEASURED"
    assert "in BOTH" in report["unmeasured"]["balance_sheet_constraint"]
    # Diffusion speed IS measurable here on every instrument and carries no planted effect.
    diffusion = _row(report, "information_diffusion_speed")
    assert diffusion["instruments_tested"] == len(TARGETS)
    assert diffusion["verdict"] == "FAIL"
