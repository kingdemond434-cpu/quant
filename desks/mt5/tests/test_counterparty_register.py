"""Counterparty register (IDEA_QUEUE row 227): hazard maths, the payout-cap schedule, the
withdraw-now versus hold E[log W] delta, UNMEASURED with reasons, and the login scrub. Fake
registers only, except one read of the committed seed to check its shape."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys as _sys
from pathlib import Path
from pathlib import Path as _Path

import pytest

_DESK = _Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parents[1])):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from research import counterparty_register as cr  # noqa: E402

SEED = Path(cr.__file__).resolve().parents[1] / "data" / "counterparty_register.json"


def _register(accounts, w0=100_000.0, priors=None):
    return {
        "p_default_prior": {"values": priors or {"Capped": 0.2, "Broker": 0.01}},
        "firms": {
            "Capped": {"payout": {"per_payout_cap": 3000, "max_payouts_per_account": 5,
                                  "payout_interval_days": 14}},
            "Broker": {"payout": {"per_payout_cap": None, "max_payouts_per_account": None,
                                  "payout_interval_days": 0}},
        },
        "owner": {"other_wealth_usd": w0},
        "accounts": accounts,
    }


def _firm(reg):
    """The firm register alone: what a tracked seed may hold (no owner money, no accounts)."""
    return {k: v for k, v in reg.items() if k not in ("owner", "accounts")}


def _accounts(reg):
    """The operator file: owner wealth and account money live here, never in the seed."""
    return {"owner": reg["owner"], "accounts": reg["accounts"]}


def _build(reg, **kw):
    kw.setdefault("horizon_days", 30.0)
    kw.setdefault("p_override", {})
    kw.setdefault("time_budget_s", 10.0)
    return cr.build(_firm(reg), None, _accounts(reg), **kw)


def test_daily_hazard_round_trips_annual_probability():
    h = cr.daily_hazard(0.2)
    assert math.isclose(1 - math.exp(-h * 365), 0.2)
    with pytest.raises(ValueError):
        cr.daily_hazard(1.0)


def test_schedule_respects_cap_and_count():
    s = cr.payout_schedule(10_000, 3000, 2, 14)
    assert s == [(0.0, 3000), (14.0, 3000)]
    assert cr.payout_schedule(10_000, None, None, 0) == [(0.0, 10_000)]
    assert cr.payout_schedule(0, 3000, 5, 14) == []
    assert cr.payout_schedule(500, None, 0, 0) == []


def test_capped_account_haircut_and_forfeit():
    reg = _register([{"label": "e8a", "firm": "Capped", "withdrawable_usd": 10_000,
                      "payouts_taken": 3}])
    row = _build(reg)["accounts"][0]
    h = cr.daily_hazard(0.2)
    assert row["status"] == "MEASURED" and row["payouts_remaining"] == 2
    assert row["nominal_withdrawable_usd"] == 6000 and row["forfeit_beyond_caps_usd"] == 4000
    assert math.isclose(row["haircut_withdrawable_usd"],
                        round(3000 + 3000 * math.exp(-h * 14), 2))
    assert row["withdraw_now_usd"] == 3000 and row["spends_capped_slot"] is False


def test_delta_elogw_matches_hand_formula_and_sign():
    reg = _register([{"label": "e8a", "firm": "Capped", "withdrawable_usd": 2000,
                      "payouts_taken": 0}], w0=10_000)
    row = _build(reg)["accounts"][0]
    q = math.exp(-cr.daily_hazard(0.2) * 30)
    want = (q * math.log(12_000) + (1 - q) * math.log(12_000)) - (
        q * math.log(12_000) + (1 - q) * math.log(10_000))
    assert math.isclose(row["delta_elogw_withdraw_now_vs_hold"], want)
    assert row["log_growth_favours"] == "WITHDRAW_NOW"
    assert row["spends_capped_slot"] is True  # 2000 < 3000 cap with a count cap


def test_hold_gain_can_flip_the_sign():
    reg = _register([{"label": "fz", "firm": "Broker", "withdrawable_usd": 1000,
                      "hold_gain_usd": 5000}], w0=10_000)
    row = _build(reg)["accounts"][0]
    assert row["delta_elogw_withdraw_now_vs_hold"] < 0
    assert row["log_growth_favours"] == "HOLD"


def test_zero_default_prior_and_no_gain_is_indifferent():
    reg = _register([{"label": "fz", "firm": "Broker", "withdrawable_usd": 1000}],
                    priors={"Broker": 0.0, "Capped": 0.2})
    row = _build(reg)["accounts"][0]
    assert row["haircut_withdrawable_usd"] == 1000
    assert row["delta_elogw_withdraw_now_vs_hold"] == 0.0
    assert row["log_growth_favours"] == "INDIFFERENT"


def test_missing_inputs_are_unmeasured_with_reasons_never_zero():
    reg = _register([
        {"label": "a", "firm": "Capped", "withdrawable_usd": None, "payouts_taken": 0},
        {"label": "b", "firm": "Capped", "withdrawable_usd": 500, "payouts_taken": None},
        {"label": "c", "firm": "Nope", "withdrawable_usd": 500},
    ])
    doc = _build(reg)
    rows = doc["accounts"]
    assert all(r["status"] == "UNMEASURED" for r in rows)
    assert all(r["haircut_withdrawable_usd"] == "UNMEASURED" for r in rows)
    assert rows[0]["reasons"] == ["withdrawable_usd not supplied"]
    assert rows[1]["reasons"] == ["payouts_taken unknown under a payout-count cap"]
    assert "not in the register" in rows[2]["reasons"][0]
    assert doc["total_haircut_withdrawable_usd"] == "UNMEASURED"
    assert doc["status"] == "UNMEASURED"


def test_owner_wealth_missing_leaves_haircut_but_unmeasures_elogw():
    reg = _register([{"label": "fz", "firm": "Broker", "withdrawable_usd": 1000}], w0=None)
    row = _build(reg)["accounts"][0]
    assert row["haircut_withdrawable_usd"] == 1000.0
    assert row["delta_elogw_withdraw_now_vs_hold"] == "UNMEASURED"
    assert "other_wealth_usd" in row["reasons"][0]


def test_absent_register_is_unmeasured(tmp_path):
    reg, reason = cr.load_json(tmp_path / "none.json")
    doc = cr.build(reg, reason, None, horizon_days=30, p_override={}, time_budget_s=1)
    assert doc["status"] == "UNMEASURED" and doc["reasons"] == ["none.json absent"]


def test_oversized_input_is_refused(tmp_path, monkeypatch):
    p = tmp_path / "big.json"
    p.write_text(json.dumps({"x": "y" * 100}))
    monkeypatch.setattr(cr, "MAX_INPUT_BYTES", 10)
    doc, reason = cr.load_json(p)
    assert doc is None and "budget" in reason


def test_login_keys_and_account_shaped_labels_are_scrubbed():
    reg = _register([{"label": "5551234", "firm": "Broker", "withdrawable_usd": 100,
                      "account": 5551234, "login": "5551234", "Account Number": 5551234}])
    reg["firms"]["Broker"]["login"] = 7778889
    doc = _build(reg)
    text = json.dumps(doc)
    assert "5551234" not in text and "7778889" not in text
    assert doc["accounts"][0]["label"] == "account_0"


def test_account_budget_and_p_override():
    accts = [{"label": f"x{i}", "firm": "Broker", "withdrawable_usd": 10} for i in range(3)]
    reg = _register(accts)
    doc = _build(reg, p_override={"Broker": 0.5})
    assert doc["p_default_prior"]["values"]["Broker"] == 0.5
    assert doc["p_default_prior"]["overridden"] == ["Broker"]
    old = cr.MAX_ACCOUNTS
    try:
        cr.MAX_ACCOUNTS = 2
        doc = _build(reg)
    finally:
        cr.MAX_ACCOUNTS = old
    assert doc["budget"]["exceeded"] is True and doc["accounts"][-1]["status"] == "UNMEASURED"


def test_seed_register_shape_and_no_identifiers():
    doc = json.loads(SEED.read_text(encoding="utf-8"))
    assert set(doc["firms"]) == {"E8 Markets", "FTMO", "Fusion Markets"}
    for firm in doc["firms"].values():
        for key in ("entity", "regulator", "payout", "last_rule_change", "trust_events"):
            assert key in firm
        assert firm["last_rule_change"]["date"] and firm["last_rule_change"]["url"]
        for ev in firm["trust_events"]:
            assert ev["url"].startswith("https://") and len(ev["date"]) == 10
    assert doc["p_default_prior"]["assumption"] is True
    e8 = doc["firms"]["E8 Markets"]
    assert {e["date"] for e in e8["trust_events"]} == {"2026-08-22", "2026-08-23"}
    assert doc["firms"]["Fusion Markets"]["regulator"].startswith("ASIC")

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)

    assert not [k for k in keys(doc) if cr.is_login_key(k)]


def test_main_writes_report_and_reads_operator_accounts(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps(_firm(_register([]))))
    acc = tmp_path / "acc.json"
    acc.write_text(json.dumps({"owner": {"other_wealth_usd": 5000},
                               "accounts": [{"label": "fz", "firm": "Broker",
                                             "withdrawable_usd": 250}]}))
    out = tmp_path / "out" / "counterparty_register.json"
    assert cr.main(["--register", str(reg), "--accounts", str(acc), "--out", str(out),
                    "--p-default", "Broker=0.02"]) == 0
    doc = json.loads(out.read_text())
    assert doc["status"] == "MEASURED" and doc["feeds_allocator"] is False
    assert doc["accounts"][0]["p_default_annual"] == 0.02


def test_the_written_report_carries_no_amount_of_money(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps(_firm(_register([]))))
    acc = tmp_path / "acc.json"
    acc.write_text(json.dumps({"owner": {"other_wealth_usd": 54_321},
                               "accounts": [{"label": "e8a", "firm": "Capped",
                                             "withdrawable_usd": 10_000, "payouts_taken": 3,
                                             "hold_gain_usd": 777}]}))
    out = tmp_path / "counterparty_register.json"
    assert cr.main(["--register", str(reg), "--accounts", str(acc), "--out", str(out)]) == 0
    doc = json.loads(out.read_text())
    numbers = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k != "budget":
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            numbers.append(o)

    walk(doc)
    for amount in (54_321, 10_000, 6000, 4000, 3000, 777):
        assert amount not in numbers, amount
    row = doc["accounts"][0]
    assert not [k for k in row if k.endswith("_usd")]
    h = cr.daily_hazard(0.2)
    assert row["nominal_frac"] == 0.6 and row["forfeit_beyond_caps_frac"] == 0.4
    assert math.isclose(row["haircut_frac"], round((3000 + 3000 * math.exp(-h * 14)) / 10_000, 6),
                        abs_tol=2e-6)
    assert row["withdraw_now_frac"] == 0.3 and row["per_payout_cap_frac"] == 0.3
    assert doc["owner_other_wealth"] == "supplied"
    assert doc["firms"]["Capped"]["payout"]["per_payout_cap"] == "recorded"
    assert math.isclose(doc["total_haircut_frac_of_withdrawable"], row["haircut_frac"], abs_tol=2e-6)


def _ignored(path: str) -> bool:
    root = Path(cr.__file__).resolve().parents[3]
    r = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", path],
                       capture_output=True, timeout=30, check=False)
    assert r.returncode in (0, 1), r.stderr
    return r.returncode == 0


def test_a_seed_carrying_any_usd_value_is_refused_unmeasured():
    reg = _register([{"label": "fz", "firm": "Broker", "withdrawable_usd": 1000}], w0=5000)
    doc = cr.build(reg, None, None, horizon_days=30, p_override={}, time_budget_s=1)
    assert doc["status"] == "UNMEASURED" and doc["accounts"] == []
    why = doc["reasons"][0]
    assert why.startswith("refused") and "owner.other_wealth_usd" in why
    assert "accounts[0].withdrawable_usd" in why
    firm_money = _firm(_register([]))
    firm_money["firms"]["Capped"]["payout"]["per_payout_cap_usd"] = 3000
    doc = cr.build(firm_money, None, None, horizon_days=30, p_override={}, time_budget_s=1)
    assert doc["status"] == "UNMEASURED" and "per_payout_cap_usd" in doc["reasons"][0]


def test_the_tracked_seed_has_every_usd_field_null_and_no_edit_here():
    raw = SEED.read_text(encoding="utf-8")
    assert cr.seed_money(json.loads(raw)) == []
    assert "edit here" not in raw
    doc = cr.build(json.loads(raw), None, None, horizon_days=30, p_override={}, time_budget_s=1)
    assert not str((doc.get("reasons") or [""])[0]).startswith("refused")


def test_main_reads_the_gitignored_local_accounts_file_by_default(tmp_path, monkeypatch):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps(_firm(_register([]))))
    local = tmp_path / "counterparty_accounts.local.json"
    local.write_text(json.dumps({"owner": {"other_wealth_usd": 5000},
                                 "accounts": [{"label": "fz", "firm": "Broker",
                                               "withdrawable_usd": 250}]}))
    monkeypatch.setattr(cr, "ACCOUNTS_LOCAL", local)
    out = tmp_path / "out.json"
    assert cr.main(["--register", str(reg), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["status"] == "MEASURED"


@pytest.mark.skipif(shutil.which("git") is None, reason="git unavailable")
def test_the_operator_accounts_file_is_gitignored():
    assert cr.ACCOUNTS_LOCAL.name == "counterparty_accounts.local.json"
    for p in ("desks/mt5/data/counterparty_accounts.local.json",
              "desks/mt5/data/counterparty_accounts.local.json.tmp"):
        assert _ignored(p), p
    assert not _ignored("desks/mt5/data/counterparty_register.json")   # the seed stays tracked
