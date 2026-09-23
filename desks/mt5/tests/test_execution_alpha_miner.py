"""The execution-tape miner against a tape planted second by second, and a registry in /tmp.

EVERY ASSERTION IS ABOUT A PLANTED NUMBER, NOT A SHAPE. The synthetic day is built so the answer
is known before the code runs: the wide-spread Asian block is a period-60 sine, which makes the
30-second momentum sign a CONTRARIAN indicator and drives its adverse-move rate far above the
day's unconditional baseline; the mid-spread London block is a period-40 sine whose amplitude sits
UNDER its own half spread, so almost nothing there counts as adverse while an entry delayed ten
seconds still beats an immediate one by basis points. A green test therefore means the two
searches found what was buried, not that the plumbing ran.

THREE OF THESE TESTS EXIST BECAUSE THE FIRST LIVE RUN FAILED THEM. The block bootstrap drew one
block from one legal start on a short cell and returned a ZERO-WIDTH interval that "excluded zero"
trivially; the fill join priced 134 deals that share one bulk-reconciliation second; and a
`session=all` cell was handed a `session_avoid` instruction nobody can carry out. Each is pinned
here so it cannot come back.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry  # noqa: E402
from research import execution_alpha_miner as eam  # noqa: E402
from research import moat_series as mos  # noqa: E402

DAYS = ("2026-05-04", "2026-05-05", "2026-05-06")
SYMS = ("PLANTA", "PLANTB")

#: The three planted blocks, each EXACTLY a third of the day so the spread and velocity terciles
#: land strictly between the planted values instead of on top of one (the first version planted
#: them on the tercile boundaries and float noise split one block across two buckets):
#: (start hour, end hour, quoted spread in bps, mid shape, amplitude in bps).
WIDE = (0, 5, 6.0, "sine60", 20.0)    # period 60 == 2x the momentum window -> contrarian, adverse
MIDB = (5, 10, 3.0, "sine40", 0.8)    # delayed entry wins; amplitude UNDER its own half spread
TIGHT = (10, 15, 0.5, "walk", 20.0)   # an unconditioned random walk, the tightest spread
BLOCKS = (WIDE, MIDB, TIGHT)
#: A 75-second hole inside the wide block: long enough that its tail is stale, short enough that
#: no whole minute loses every quote (an empty minute would collapse the velocity tercile).
GAP = (7225, 7300)
STALE_SEC = 7290


def _mid_shape(shape: str, sec: np.ndarray, amp_bps: float, rng: np.random.Generator) -> np.ndarray:
    if shape == "sine60":
        return amp_bps * 1e-4 * np.sin(2.0 * np.pi * sec / 60.0)
    if shape == "sine40":
        return amp_bps * 1e-4 * np.sin(2.0 * np.pi * sec / 40.0)
    return np.cumsum(rng.normal(0.0, amp_bps * 1e-6, sec.size))


def planted_day(day: str, *, seed: int = 5, base: float = 1.2500,
                gap: bool = False) -> pd.DataFrame:
    """One tape day in the two writers' shared column set, one quote every 1-3 seconds.

    The quote RATE is stepped by minute (20 / 30 / 60 a minute) so the velocity tercile has three
    genuinely different buckets rather than one degenerate one.
    """
    rng = np.random.default_rng(seed)
    day0 = int(np.datetime64(f"{day}T00:00", "s").astype("int64"))
    secs, mids, spreads = [], [], []
    for lo, hi, spread_bps, shape, amp in BLOCKS:
        sec = np.arange(lo * 3600, hi * 3600, dtype="int64")
        step = np.where(sec // 60 % 3 == 0, 3, np.where(sec // 60 % 3 == 1, 2, 1))
        sec = sec[sec % step == 0]
        if gap:
            sec = sec[(sec < GAP[0]) | (sec >= GAP[1])]
        secs.append(sec)
        mids.append(base * (1.0 + _mid_shape(shape, sec, amp, rng)))
        spreads.append(np.full(sec.size, spread_bps, dtype="float64"))
    sec = np.concatenate(secs)
    mid = np.concatenate(mids)
    half = np.concatenate(spreads) / 2e4 * mid
    ms = (day0 + sec) * 1000
    return pd.DataFrame({"time": ms // 1000, "bid": mid - half, "ask": mid + half,
                         "last": 0.0, "volume": 0, "time_msc": ms, "flags": 6,
                         "volume_real": 0.0})


def _plant(root: Path, symbol: str, day: str, frame: pd.DataFrame) -> Path:
    out = root / symbol / f"{day.replace('-', '')}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out, index=False)
    return out


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """A whole desk in a tmp tree: two planted instruments, three days, an empty moat store, empty
    ledgers, and a registry file of this test's own with the moat backup pointed at nothing."""
    ticks, store, reports = tmp_path / "ticks", tmp_path / "moat", tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    for i, sym in enumerate(SYMS):
        for d in DAYS:
            _plant(ticks, sym, d, planted_day(d, seed=7 + i))
    monkeypatch.setattr(mos, "TICKS", ticks)
    monkeypatch.setattr(mos, "STORE", store)
    monkeypatch.setattr(mos, "UNIVERSE", tmp_path / "universe.json")
    for name, value in (("LIVE_LEDGER", tmp_path / "live_ledger.jsonl"),
                        ("FILL_CORPUS", tmp_path / "fill_corpus.jsonl"),
                        ("ORDER_INTENTS", tmp_path / "order_intents.jsonl"),
                        ("REPORTS", reports), ("REPORT", reports / "EXECUTION_ALPHA.json")):
        monkeypatch.setattr(eam, name, value)
    monkeypatch.setattr(registry, "BACKUP", tmp_path / "no_such_backup")
    registry.set_path(tmp_path / "registry.sqlite")
    try:
        yield {"tmp": tmp_path, "ticks": ticks, "store": store, "reports": reports,
               "report": reports / "EXECUTION_ALPHA.json"}
    finally:
        registry.set_path(None)


def _sp(rig: dict, sym: str = SYMS[0], day: str = DAYS[0]) -> dict:
    return eam.second_path(rig["ticks"] / sym / f"{day.replace('-', '')}.parquet")


def _row(rows: list[dict], **match) -> dict:
    hits = [r for r in rows if all(r.get(k) == v for k, v in match.items())]
    assert hits, f"no row matching {match}"
    return hits[0]


# ------------------------------------------------------------------- the grid and the cells --

def test_the_second_path_is_dense_carries_staleness_and_agrees_with_the_planted_blocks(
        rig: dict) -> None:
    sp = _sp(rig)
    n = sp["mid"].size
    assert {"sec", "mid", "spread_bps", "hour", "qpm", "stale_s"} <= set(sp)
    assert all(sp[k].size == n for k in ("sec", "spread_bps", "hour", "qpm", "stale_s"))
    # Dense: one entry per second from the first quote to the last, no gaps in the index itself.
    assert np.array_equal(sp["sec"], np.arange(sp["sec"][0], sp["sec"][0] + n))
    assert sp["hour"].min() == 0 and sp["hour"].max() == 14
    # The planted spreads, read back off the grid rather than asserted from the constructor.
    for lo, _hi, spread_bps, _shape, _amp in BLOCKS:
        assert np.allclose(sp["spread_bps"][sp["hour"] == lo], spread_bps, atol=1e-6)
    # A contiguous tape has nothing stale in it; the hole is planted separately, below.
    assert eam.live_mask(sp).all() and sp["stale_s"].max() <= 3


def test_a_hole_in_the_tape_makes_its_tail_stale_and_no_longer_a_quote(rig: dict) -> None:
    _plant(rig["ticks"], SYMS[0], DAYS[0], planted_day(DAYS[0], seed=7, gap=True))
    sp = _sp(rig)
    live = eam.live_mask(sp)
    assert not live.all(), "the planted hole must leave stale seconds"
    stale_secs = sp["sec"][~live] - sp["sec"][0]
    assert stale_secs.min() > GAP[0] and stale_secs.max() < GAP[1]
    assert sp["stale_s"][~live].max() > eam.MAX_STALE_S
    assert not live[STALE_SEC]


def test_the_cells_are_spread_x_velocity_x_session_and_only_over_live_seconds(rig: dict) -> None:
    sp = _sp(rig)
    masks = eam.cell_masks(sp)
    assert masks, "the planted day must produce cells"
    live = eam.live_mask(sp)
    for name, m in masks.items():
        spread, vel, session = name.split("|")
        assert spread.split("=")[1] in eam.SPREAD_LABELS
        assert vel.split("=")[1] in eam.VELOCITY_LABELS
        assert session.split("=")[1] in {"all", *mos.SESSIONS}
        assert m.shape == sp["mid"].shape
        assert not (m & ~live).any(), f"{name} reaches a stale second"
    # All three spread terciles and all three velocity buckets are exercised by the plant.
    assert {n.split("|")[0].split("=")[1] for n in masks} == set(eam.SPREAD_LABELS)
    assert {n.split("|")[1].split("=")[1] for n in masks} == set(eam.VELOCITY_LABELS)
    # The WIDE tercile is the Asian block and nothing else: 6 bps against 3 and 0.5.
    wide = np.zeros(sp["mid"].shape, dtype=bool)
    for name, m in masks.items():
        if name.startswith("spread=wide"):
            wide |= m
    assert set(np.unique(sp["hour"][wide]).tolist()) <= set(range(WIDE[0], WIDE[1]))


def test_the_signal_proxy_is_the_momentum_sign_and_never_invents_a_side(rig: dict) -> None:
    sp = _sp(rig)
    side = eam.entry_side(sp["mid"])
    assert (side[: eam.MOMENTUM_S] == 0).all(), "no side before the lookback exists"
    assert set(np.unique(side).tolist()) <= {-1.0, 0.0, 1.0}
    k = eam.MOMENTUM_S + 500
    assert side[k] == np.sign(sp["mid"][k] - sp["mid"][k - eam.MOMENTUM_S])


# ----------------------------------------------------------------------- the block bootstrap --

def test_the_bootstrap_never_returns_a_zero_width_interval_on_a_short_cell() -> None:
    """THE DEFECT THE FIRST LIVE RUN SHIPPED. With the block taken as min(block, n) a 141-point
    cell had exactly one legal block start, every draw was the same series, and the interval came
    back `[+0.6027, +0.6027]` -- zero width, trivially excluding zero, a coincidence promoted to a
    discovery."""
    rng = np.random.default_rng(1)
    x = rng.normal(0.6, 1.0, 141)
    lo, hi = eam.block_bootstrap_ci(x, rng)
    assert np.isfinite(lo) and np.isfinite(hi)
    assert hi - lo > 1e-6
    # A sample below the floor is UNMEASURED, not certain.
    assert not np.isfinite(eam.block_bootstrap_ci(x[:10], rng)[0])
    assert not eam._excludes_zero(eam.block_bootstrap_ci(x[:10], rng))


def test_the_bootstrap_brackets_a_known_mean_and_excludes_zero_only_when_it_should() -> None:
    rng = np.random.default_rng(2)
    shifted = rng.normal(5.0, 1.0, 3000)
    lo, hi = eam.block_bootstrap_ci(shifted, rng)
    # The interval brackets the SAMPLE mean -- a resampling interval says nothing about a
    # population the sample did not see, and asserting on 5.0 would be asserting on luck.
    assert lo < shifted.mean() < hi and eam._excludes_zero((lo, hi))
    centred = rng.normal(0.0, 1.0, 3000)
    centred -= centred.mean()
    assert not eam._excludes_zero(eam.block_bootstrap_ci(centred, rng))
    assert eam._ci((float("nan"), 1.0)) == [None, 1.0]


# ------------------------------------------------------------------------- the two searches --

def test_the_planted_wide_spread_cell_is_more_adverse_than_the_random_entry_baseline(
        rig: dict) -> None:
    """The Asian block is a period-60 sine, so a 30-second momentum sign points the wrong way
    twice as often as chance; the mid-spread block's amplitude sits under its own half spread, so
    nothing there clears the adverse threshold at all. The baseline is the whole day pooled."""
    sp = _sp(rig)
    rows, pooled = eam.adverse_move_day(sp, eam.cell_masks(sp), np.random.default_rng(eam.SEED))
    assert rows and pooled
    wide = _row(rows, cell="spread=wide|vel=fast|session=asia", horizon_s=10)
    mid = _row(rows, cell="spread=mid|vel=fast|session=london", horizon_s=10)
    tight = _row(rows, cell="spread=tight|vel=fast|session=london", horizon_s=10)
    assert wide["p_adverse"] > wide["baseline"] + 0.20, wide
    assert wide["significant"] is True
    assert wide["p_adverse"] > tight["p_adverse"] > mid["p_adverse"]
    assert mid["p_adverse"] == 0.0, "a move under the half spread is not an adverse move"
    assert mid["significant"] is True, "being BELOW the baseline is a finding too"
    assert wide["n"] >= eam.MIN_CELL_ENTRIES
    assert pooled[("spread=wide|vel=fast|session=asia", 10)].size == wide["n"]
    # Every horizon is measured, and the baseline is one number per horizon, not per cell.
    for h in eam.HORIZONS_S:
        same = {r["baseline"] for r in rows if r["horizon_s"] == h}
        assert len(same) == 1, h


def test_delayed_entry_wins_in_the_planted_session_with_a_ci_that_excludes_zero(
        rig: dict) -> None:
    sp = _sp(rig)
    rows, pooled = eam.delayed_vs_immediate_day(sp, eam.cell_masks(sp),
                                                np.random.default_rng(eam.SEED))
    planted = _row(rows, cell="spread=mid|vel=fast|session=london", delay_s=10, horizon_s=10)
    assert planted["diff_bps"] > 0.5, planted
    lo, hi = planted["ci"]
    assert lo is not None and hi is not None and lo > 0.0, planted
    assert hi > lo
    assert planted["significant"] is True
    assert planted["n"] == pooled[("spread=mid|vel=fast|session=london", 10, 10)].size
    assert {r["delay_s"] for r in rows} == set(eam.DELAYS_S)
    assert {r["horizon_s"] for r in rows} == set(eam.DVI_HORIZONS_S)


def test_the_suggestion_is_always_something_a_desk_could_actually_carry_out() -> None:
    allowed = {"delayed_entry", "limit_entry", "session_avoid", "spread_gate"}
    dvi_up = {"measure": "delayed_vs_immediate", "delay_s": 10, "horizon_s": 10, "diff_bps": 1.0}
    dvi_dn = {**dvi_up, "diff_bps": -1.0}
    assert eam._suggested("delayed_vs_immediate", dvi_up, "spread=mid|vel=fast|session=ny") \
        == "delayed_entry"
    assert eam._suggested("delayed_vs_immediate", dvi_dn, "spread=mid|vel=fast|session=ny") \
        in allowed
    worse = {"measure": "adverse_move", "horizon_s": 10, "p_adverse": 0.6, "baseline": 0.4}
    better = {**worse, "p_adverse": 0.2}
    ny = "spread=mid|vel=fast|session=ny"
    assert eam._suggested("adverse_move", worse, "spread=wide|vel=fast|session=ny") == "spread_gate"
    assert eam._suggested("adverse_move", worse, ny) == "session_avoid"
    assert eam._suggested("adverse_move", better, ny) == "limit_entry"
    # A cell on `all` is not a session and must never be handed `session_avoid` (shipped once).
    assert eam._suggested("adverse_move", worse, "spread=mid|vel=fast|session=all") == "spread_gate"


# ---------------------------------------------------------------------- the recurrence rule --

def test_one_instrument_can_never_produce_a_discovery_however_strong_the_effect(
        rig: dict) -> None:
    """MIN_INSTRUMENTS is the gate: a planted effect measured on three days of ONE instrument is
    still one instrument, and the registry must stay empty."""
    rep = eam.run(budget_s=120, days=3, symbols=[SYMS[0]])
    assert rep["delayed_vs_immediate_rows_total"] > 0
    assert any(r["days_significant"] >= eam.MIN_DAYS_SIGNIFICANT
               for r in rep["delayed_vs_immediate"]), "the plant must clear the per-day bar"
    assert rep["discoveries"] == [] and rep["discoveries_recorded"] == 0
    assert registry.discoveries(origin="MOAT") == []


def test_two_instruments_carry_the_same_cell_and_it_becomes_an_unprocessed_discovery(
        rig: dict) -> None:
    rep = eam.run(budget_s=180, days=3, symbols=list(SYMS))
    assert rep["discoveries_recorded"] > 0
    assert rep["discoveries_new"] == rep["discoveries_recorded"]
    for d in rep["discoveries"]:
        assert d["instrument_days_significant"] >= eam.MIN_DAYS_SIGNIFICANT
        assert len(d["recurring_instruments"]) >= eam.MIN_INSTRUMENTS
        assert set(d) >= {"instrument", "cell", "effect", "ci", "n", "suggested"}
        assert d["suggested"] in {"delayed_entry", "limit_entry", "session_avoid", "spread_gate"}
    rows = registry.discoveries(state="UNPROCESSED", origin="MOAT", limit=5000)
    assert len(rows) == rep["discoveries_recorded"]
    assert {r["source_type"] for r in rows} == {"execution_tape"}
    assert {r["generator"] for r in rows} == {eam.GENERATOR}
    payload = json.loads(rows[0]["payload_json"])
    assert payload["cell"].startswith("spread=")
    # A research_memory row per instrument, and the miner's own yield line.
    mem = registry.memories(kind="execution_structure")
    assert {m["memory_key"] for m in mem} == {f"execution_structure:{s}" for s in SYMS}
    assert [g for g in registry.generator_yields() if g["generator"] == eam.GENERATOR]


def test_rerunning_the_same_tape_records_no_second_copy_of_anything(rig: dict) -> None:
    first = eam.run(budget_s=180, days=3, symbols=list(SYMS))
    n_disc = len(registry.discoveries())
    n_mem = len(registry.memories(kind="execution_structure"))
    second = eam.run(budget_s=180, days=3, symbols=list(SYMS))
    assert second["discoveries_recorded"] == first["discoveries_recorded"]
    assert second["discoveries_new"] == 0
    assert len(registry.discoveries()) == n_disc
    assert len(registry.memories(kind="execution_structure")) == n_mem
    # Deterministic seed: the same tape mined twice gives the same intervals, not fresh luck.
    assert second["delayed_vs_immediate"][0]["ci"] == first["delayed_vs_immediate"][0]["ci"]


# --------------------------------------------------------------------------------- the fills --

def _ledger_row(sym: str, day: str, sec: int, price: float, side: int) -> dict:
    """One closed deal at an absolute second of the day; `side` 0 is a buy deal, 1 a sell."""
    stamp = f"{day}T{sec // 3600:02d}:{sec // 60 % 60:02d}:{sec % 60:02d}+00:00"
    return {"time": stamp, "symbol": sym, "side": side, "fill_price": price, "sleeve": "t",
            "volume": 0.01, "pl_quote": 1.0, "r_multiple": 0.1, "deal": 1, "entry_price": price}


def _at(sp: dict, sec: int, *, bps: float) -> float:
    """A fill price planted `bps` away from the mid at that exact second, so the slippage the
    miner reports is the number this test buried and not an artefact of the sine moving.

    The planted day's first quote is at midnight, so the grid index IS the second of the day.
    """
    assert int(sp["sec"][0]) % 86400 == 0
    return float(sp["mid"][sec]) * (1.0 + bps * 1e-4)


def test_fills_are_unmeasured_by_name_when_the_desk_has_no_ledgers(rig: dict) -> None:
    rep = eam.run(budget_s=60, days=1, symbols=[SYMS[0]])
    assert rep["fills"] == "UNMEASURED"
    assert any("no live_ledger.jsonl" in u for u in rep["unmeasured"])


def test_fills_are_measured_against_the_tape_when_a_ledger_exists(rig: dict) -> None:
    """Slippage is not read from a column -- it is the fill against the QUOTE at the deal's own
    second, which only a desk holding both sides can compute."""
    sp = _sp(rig)
    wide_secs = [3600 + 60 * m for m in (1, 3, 5, 7)]      # hour 1: the wide Asian block
    mid_secs = [9 * 3600 + 60 * m for m in (11, 13)]       # hour 9: the mid-spread London block
    rows = [_ledger_row(SYMS[0], DAYS[0], s, _at(sp, s, bps=2.0), 0) for s in wide_secs]
    rows += [_ledger_row(SYMS[0], DAYS[0], s, _at(sp, s, bps=-1.0), 1) for s in mid_secs]
    eam.LIVE_LEDGER.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    eam.ORDER_INTENTS.write_text("\n".join(json.dumps(
        {"symbol": SYMS[0], "time": f"{DAYS[0]}T0{h}:05:00+00:00", "retcode": c})
        for h, c in ((1, 10009), (1, 10016), (2, 10009), (9, 10009))) + "\n", encoding="utf-8")
    eam.FILL_CORPUS.write_text("\n".join(json.dumps(
        {"symbol": SYMS[0], "latency_decision_to_send_ms": v, "latency_send_to_ack_ms": None,
         "latency_ack_to_fill_ms": None}) for v in (80.0, 110.0, 140.0)) + "\n", encoding="utf-8")

    rep = eam.run(budget_s=120, days=1, symbols=[SYMS[0]])
    fills = rep["fills"]
    assert isinstance(fills, dict) and fills["measured"] is True
    assert fills["n_joined_to_tape"] == len(rows)
    assert fills["n_bulk_stamped_refused"] == 0
    # Planted 2 bps above the mid on a buy: positive slippage, and the quoted half spread is 3 bps.
    asia = fills["slippage_vs_quote_bps"]["session=asia"]
    assert asia["n"] == 4 and asia["mean"] == pytest.approx(2.0, abs=0.2)
    assert asia["half_spread_bps_mean"] == pytest.approx(3.0, abs=0.01)
    london = fills["slippage_vs_quote_bps"]["session=london"]
    # Planted 1 bp BELOW the mid on a sell deal: hitting the bid below mid is positive slippage.
    assert london["n"] == 2 and london["mean"] == pytest.approx(1.0, abs=0.05)
    assert fills["slippage_vs_quote_bps"]["spread=wide"]["n"] == 4
    assert fills["slippage_vs_quote_bps"]["spread=mid"]["n"] == 2
    assert all(fills["markout_bps"][str(h)]["n"] > 0 for h in eam.HORIZONS_S)
    assert fills["latency_ms"]["latency_decision_to_send_ms"] == {
        "n": 3, "mean": 110.0, "p50": 110.0, "p90": 134.0, "max": 140.0}
    for absent in ("latency_send_to_ack_ms", "latency_ack_to_fill_ms"):
        assert str(fills["latency_ms"][absent]).startswith("UNMEASURED")
        assert any(absent in u for u in rep["unmeasured"])
    assert fills["rejection"] == {**fills["rejection"], "n_intents": 4, "rejected": 1,
                                  "rate": 0.25}
    assert fills["rejection"]["by_spread_state"]["wide"]["n"] == 3
    assert fills["rejection"]["by_session"]["asia"]["rate"] == pytest.approx(1 / 3, abs=1e-3)


def test_deals_sharing_one_reconciliation_second_are_refused_not_priced(rig: dict) -> None:
    """MEASURED ON THE LIVE BOX: 134 of 151 ledger deals share a (symbol, second) stamp -- sixteen
    EURCHF at one instant, eleven XAUUSD with fill prices from 4351 to 4493. Pricing those against
    the quote at that second produced a -42 bps 'slippage' that measured the WRITE, not the venue.
    """
    sp = _sp(rig)
    good = [_ledger_row(SYMS[0], DAYS[0], 3720, _at(sp, 3720, bps=0.0), 0)]
    bulk = [_ledger_row(SYMS[0], DAYS[0], 4200, _at(sp, 4200, bps=100.0 * k), 0)
            for k in range(1, 6)]
    eam.LIVE_LEDGER.write_text("\n".join(json.dumps(r) for r in good + bulk) + "\n",
                               encoding="utf-8")
    fills = eam.run(budget_s=120, days=1, symbols=[SYMS[0]])["fills"]
    assert fills["n_bulk_stamped_refused"] == len(bulk)
    assert fills["n_joined_to_tape"] == len(good)


def test_a_deal_on_a_frozen_quote_is_unmeasured_rather_than_priced_off_a_stale_mid(
        rig: dict) -> None:
    """The planted hole carries no quotes. The one-second grid forward-fills it, so pricing a fill
    inside it reads a quote from before the hole -- the defect that returned a median 10-second
    markout of exactly 0.0 on 143 live deals."""
    _plant(rig["ticks"], SYMS[0], DAYS[0], planted_day(DAYS[0], seed=7, gap=True))
    sp = _sp(rig)
    assert not eam.live_mask(sp)[STALE_SEC]
    eam.LIVE_LEDGER.write_text(json.dumps(
        _ledger_row(SYMS[0], DAYS[0], STALE_SEC, _at(sp, STALE_SEC, bps=0.0), 0)) + "\n",
        encoding="utf-8")
    rep = eam.run(budget_s=120, days=1, symbols=[SYMS[0]])
    assert rep["fills"]["n_joined_to_tape"] == 0
    assert rep["fills"]["n_unjoinable_or_stale"] == 1
    assert any("older than" in u for u in rep["unmeasured"])


# ----------------------------------------------------------- the moat store, budget and CLI --

def test_an_empty_moat_store_is_named_as_empty_and_a_populated_one_is_read(rig: dict) -> None:
    rep = eam.run(budget_s=60, days=1, symbols=[SYMS[0]])
    assert rep["moat_series_store"].startswith("EMPTY")
    assert any("moat store" in u for u in rep["unmeasured"])
    path = mos.store_path("realised_spread_session", SYMS[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": list(DAYS), "symbol": SYMS[0],
                  "spread_bps_med_all": [6.0, 6.0, 6.0]}).to_parquet(path, index=False)
    assert not mos.series_frame("realised_spread_session", SYMS[0]).empty
    rep = eam.run(budget_s=60, days=1, symbols=[SYMS[0]])
    assert rep["moat_series_store"] == "READ"
    assert not any("moat store" in u for u in rep["unmeasured"])


def test_a_zero_budget_stops_the_pass_and_says_so_instead_of_reporting_nothing_found(
        rig: dict) -> None:
    rep = eam.run(budget_s=0.0, days=3, symbols=list(SYMS))
    assert rep["budget_stopped"] is True
    assert rep["instrument_days"] == 0
    assert rep["adverse_move"] == [] and rep["delayed_vs_immediate"] == []
    assert rep["discoveries_recorded"] == 0
    assert any("budget stopped" in u for u in rep["unmeasured"])
    # UNMEASURED is not "no edge here": nothing is written to the registry by a pass that stopped.
    assert registry.discoveries() == []


def test_the_cli_dry_run_measures_and_writes_absolutely_nothing(rig: dict) -> None:
    assert eam.main(["--symbols", ",".join(SYMS), "--days", "2", "--budget-s", "120",
                     "--dry-run"]) == 0
    assert not rig["report"].exists()
    assert registry.discoveries() == []
    assert registry.memories(kind="execution_structure") == []


def test_the_cli_writes_the_artifact_atomically_with_the_rule_and_the_next_gate(
        rig: dict) -> None:
    out = rig["tmp"] / "EXECUTION_ALPHA.json"
    assert eam.main(["--symbols", ",".join(SYMS), "--days", "2", "--budget-s", "180",
                     "--out", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["rule"] == eam.RULE and doc["next_gate"] == "gauntlet"
    assert doc["recurrence_rule"] == eam.RECURRENCE_RULE
    assert doc["instruments"] == sorted(SYMS)
    assert doc["days"] and doc["instrument_days"] == 2 * len(doc["days"])
    for row in doc["adverse_move"]:
        assert set(row) >= {"symbol", "cell", "horizon_s", "p_adverse", "baseline", "n"}
    for row in doc["delayed_vs_immediate"]:
        assert set(row) >= {"symbol", "delay_s", "diff_bps", "ci", "n"}
    assert doc["search_size"]["cells_tested"] == (doc["adverse_move_rows_total"]
                                                 + doc["delayed_vs_immediate_rows_total"])
    assert not list(out.parent.glob("*.tmp")), "the atomic write must leave no temp file"
    assert json.dumps(doc).count("NaN") == 0, "NaN is not JSON; an unmeasured bound is null"


def test_the_symbol_default_prefers_the_traded_instruments_and_always_holds_gold(
        rig: dict) -> None:
    index = mos.tape_index()
    assert set(index) == set(SYMS)
    eam.LIVE_LEDGER.write_text("\n".join(json.dumps({"symbol": SYMS[1], "time": "x"})
                                         for _ in range(5)) + "\n", encoding="utf-8")
    assert eam.select_symbols(index, 8)[0] == SYMS[1], "most-traded first"
    assert eam.select_symbols(index, 1) == [SYMS[1]]
    (rig["ticks"] / "XAUUSD").mkdir(parents=True, exist_ok=True)
    planted_day(DAYS[0]).to_parquet(rig["ticks"] / "XAUUSD" / "20260504.parquet", index=False)
    assert eam.select_symbols(mos.tape_index(), 8)[0] == "XAUUSD"
