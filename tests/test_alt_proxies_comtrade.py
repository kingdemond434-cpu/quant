"""alt_proxies, source `un_comtrade_hk_gold`: the UN Comtrade partner-side mirror of Hong Kong's
HS 7108 (gold) trade -- mainland China (156) and Switzerland (757) imports from and exports to
Hong Kong (344), monthly, read from the keyless public preview route -- and its sibling
`un_comtrade_sa_gold`, Saudi Arabia's (682) own HS 7108 trade with the World (0).

The fixtures `tests/fixtures/alt_proxies/un_comtrade_{hk,sa}_gold.json` are SYNTHETIC (each says
so in its own `_fixture` key): every value is invented. UN Comtrade data is internal-use-only, so
no real row is ever committed to this public repository.
"""
from __future__ import annotations

import fnmatch
import json
import shutil
import subprocess
import sys
import urllib.parse
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_proxies as A  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
BODY = (FIX / "un_comtrade_hk_gold.json").read_bytes()
SID = "un_comtrade_hk_gold"
SA = "un_comtrade_sa_gold"
SA_BODY = (FIX / "un_comtrade_sa_gold.json").read_bytes()
NOW = datetime(2026, 11, 11, 6, tzinfo=UTC)


def _by(obs: list[A.Obs]) -> dict[tuple[str, date], float]:
    return {(o.series, o.period): o.value for o in obs}


# ============================================================================ parser
def test_fixture_is_labelled_synthetic() -> None:
    assert json.loads(BODY)["_fixture"].startswith("SYNTHETIC")


def test_parser_reads_value_and_weight_per_reporter_and_flow() -> None:
    got = _by(A.parse_comtrade_hk_gold(BODY, A.Ctx()))
    sep = date(2024, 9, 30)
    assert got[("comtrade_cn_imp_from_hk_gold_usd", sep)] == 700000000.0
    assert got[("comtrade_cn_imp_from_hk_gold_kg", sep)] == pytest.approx(8600.0)
    assert got[("comtrade_cn_exp_to_hk_gold_usd", sep)] == 41250000.0
    assert got[("comtrade_ch_exp_to_hk_gold_kg", sep)] == 23800.0
    assert got[("comtrade_ch_imp_from_hk_gold_usd", sep)] == 310000000.0
    aug = date(2024, 8, 31)
    assert ("comtrade_cn_exp_to_hk_gold_kg", aug) not in got        # netWgt null: no kg point
    assert got[("comtrade_cn_exp_to_hk_gold_usd", aug)] == 38000000.0
    # the transport breakdown row and the silver row are skipped, not summed in
    assert len(got) == 11
    assert {s for s, _ in got} <= set(A.BY_ID[SID].signal_series)


@pytest.mark.parametrize("body", [
    b"not json", b"<html>maintenance</html>", b"[]", b"{}", b'{"data": null}', b'{"data": "x"}',
    b'{"data": {"period": "202409"}}', b'{"data": [1, "a", null]}',
    b'{"statusCode": 404, "message": "Resource not found"}',
    b'{"error": "rate limited", "data": [null]}'])
def test_parser_emits_nothing_on_any_other_shape(body: bytes) -> None:
    assert A.parse_comtrade_hk_gold(body, A.Ctx()) == []
    assert not A.comtrade_shape_ok(body)


def test_parser_skips_rows_that_are_not_the_hk_gold_aggregate() -> None:
    good = json.loads(BODY)["data"][0]
    bad = [{**good, "cmdCode": "7106"}, {**good, "partnerCode": 0},
           {**good, "reporterCode": 842}, {**good, "flowCode": "RX"},
           {**good, "period": "2024-09"}, {**good, "period": "202413"},
           {**good, "freqCode": "A"}, {**good, "partner2Code": 156},
           {**good, "customsCode": "C01"}, {**good, "primaryValue": None, "netWgt": None},
           {**good, "primaryValue": "garbage", "netWgt": -1}]
    assert A.comtrade_shape_ok(json.dumps({"data": bad}).encode())
    assert A.parse_comtrade_hk_gold(json.dumps({"data": bad}).encode(), A.Ctx()) == []
    assert A.parse_comtrade_hk_gold(b'{"data": []}', A.Ctx()) == []     # not yet released


def test_a_duplicated_aggregate_key_is_dropped_never_guessed() -> None:
    good = json.loads(BODY)["data"][0]
    body = json.dumps({"data": [good, {**good, "primaryValue": 1.0}]}).encode()
    got = _by(A.parse_comtrade_hk_gold(body, A.Ctx()))
    assert ("comtrade_cn_imp_from_hk_gold_usd", date(2024, 9, 30)) not in got


def test_net_flow_is_imports_minus_exports_only_where_both_legs_are_held() -> None:
    src = A.BY_ID[SID]
    store: dict[str, Any] = {}
    A.merge_vintages(store, src, A.parse_comtrade_hk_gold(BODY, A.Ctx()), NOW)
    net = _by(A.comtrade_net_obs(store))
    sep, aug = date(2024, 9, 30), date(2024, 8, 31)
    assert net[("comtrade_cn_net_imp_from_hk_gold_usd", sep)] == 700000000.0 - 41250000.0
    assert net[("comtrade_cn_net_imp_from_hk_gold_kg", sep)] == pytest.approx(8600.0 - 510.5)
    assert net[("comtrade_cn_net_imp_from_hk_gold_usd", aug)] == 512000000.0 - 38000000.0
    assert ("comtrade_cn_net_imp_from_hk_gold_kg", aug) not in net     # export kg missing
    assert not any(s.startswith("comtrade_ch_") for s, _ in net)


# ============================================================================ requests
def test_urls_carry_the_preview_params_and_comma_joined_periods() -> None:
    src = A.BY_ID[SID]
    st: dict[str, Any] = {}
    reqs = A.requests_for(src, NOW, st)
    assert len(reqs) == 8                                  # 2 reporters x 2 flows x 2 blocks
    seen = set()
    for r in reqs:
        base, q = r.url.split("?")
        assert base == "https://comtradeapi.un.org/public/v1/preview/C/M/HS"
        qs = urllib.parse.parse_qs(q)
        assert qs["partnerCode"] == ["344"] and qs["cmdCode"] == ["7108"]
        assert qs["reporterCode"][0] in ("156", "757") and qs["flowCode"][0] in ("M", "X")
        periods = qs["period"][0].split(",")
        assert 1 <= len(periods) <= A.COMTRADE_PERIODS_PER_CALL <= 12
        assert all(len(p) == 6 and p.isdigit() for p in periods)
        assert "subscription" not in r.url.lower() and "key" not in qs
        seen.add((qs["reporterCode"][0], qs["flowCode"][0], qs["period"][0]))
    assert len(seen) == 8
    recent = urllib.parse.parse_qs(reqs[0].url.split("?")[1])["period"][0].split(",")
    assert recent[0] == "202610" and len(recent) == A.COMTRADE_RECENT_MONTHS
    back = urllib.parse.parse_qs(reqs[4].url.split("?")[1])["period"][0].split(",")
    assert back == ["202604", "202603", "202602", "202601", "202512", "202511"]
    assert st["backfill_to_next"] == "2025-10-01"
    assert A.comtrade_url(156, "M", ["202409"]).endswith(
        "?reporterCode=156&partnerCode=344&cmdCode=7108&flowCode=M&period=202409")
    with pytest.raises(ValueError):
        A.comtrade_url(156, "M", [f"2024{m:02d}" for m in range(1, 13)] + ["202501"])


def test_backfill_stops_at_the_floor_and_a_pass_runs_at_most_once_a_day() -> None:
    src = A.BY_ID[SID]
    st: dict[str, Any] = {"backfill_to": "2010-03-01"}
    reqs = A.requests_for(src, NOW, st)
    last = urllib.parse.parse_qs(reqs[-1].url.split("?")[1])["period"][0]
    assert last == "201003,201002,201001"
    st = {"backfill_to": "2009-12-01"}
    assert len(A.requests_for(src, NOW, st)) == 4 and "backfill_to_next" not in st
    gated = {"last_attempt": (NOW - timedelta(hours=3)).isoformat()}
    assert A.requests_for(src, NOW, gated) == []
    due = {"last_attempt": (NOW - timedelta(hours=A.COMTRADE_MIN_GAP_H + 1)).isoformat()}
    assert len(A.requests_for(src, NOW, due)) == 8
    # 8 calls a pass, one pass per gap: far under the free tier's 500 calls/day
    assert 8 * (24 // A.COMTRADE_MIN_GAP_H + 1) < A.COMTRADE_MAX_CALLS_PER_DAY
    assert A.COMTRADE_MIN_INTERVAL_S >= 1.0


def test_collect_paces_calls_holds_the_cursor_on_a_bad_reply_and_never_logs_more(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = A.BY_ID[SID]
    sleeps: list[float] = []
    monkeypatch.setattr(A, "_sleep", sleeps.append)
    paths = A.Paths(tmp_path / "desk")
    calls: list[str] = []

    def getter(url: str) -> tuple[bytes, str]:
        calls.append(url)
        return BODY, "application/json"

    state: dict[str, Any] = {}
    rec = A.collect(paths, src, state, NOW, fetch=True, fixtures=None, deadline=1e18,
                    getter=getter)
    sst = state["sources"][SID]
    assert len(calls) == 8 and sleeps == [A.COMTRADE_MIN_INTERVAL_S] * 7
    assert rec["errors"] == [] and sst["backfill_to"] == "2025-10-01"
    assert sst["last_attempt"] == NOW.isoformat(timespec="seconds")
    store = json.loads((paths.obs_dir / f"{SID}.json").read_text("utf-8"))
    assert "comtrade_cn_net_imp_from_hk_gold_usd|2024-09-30" in store
    # the next hourly pass inside the gap makes no call at all
    calls.clear()
    A.collect(paths, src, state, NOW + timedelta(hours=1), fetch=True, fixtures=None,
              deadline=1e18, getter=getter)
    assert calls == []
    # a reply of another shape is an error: nothing parsed from it, the cursor is held
    state2: dict[str, Any] = {}
    rec = A.collect(paths, src, state2, NOW, fetch=True, fixtures=None, deadline=1e18,
                    getter=lambda url: (b'{"statusCode": 429}', "application/json"))
    assert rec["errors"] and "backfill_to" not in state2["sources"][SID]


def test_release_rule_is_ninety_days_after_the_month_closes_on_a_weekday() -> None:
    src = A.BY_ID[SID]
    assert src.rule is A.rule_comtrade_monthly
    for d in (date(2024, 9, 30), date(2026, 1, 31), date(2026, 2, 28), date(2026, 8, 31)):
        t = src.rule(d)
        assert t >= datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(days=91)
        assert t.weekday() < 5 and t - datetime(d.year, d.month, d.day, tzinfo=UTC) < (
            timedelta(days=94))
    assert src.rule(date(2024, 9, 30)) == datetime(2024, 12, 30, tzinfo=UTC)   # Mon 30 Dec


# ============================================================================ terms
def test_terms_row_is_internal_use_only_with_the_evidence_and_attribution() -> None:
    src = A.BY_ID[SID]
    label, why = A.TERMS[SID]
    assert label == src.terms == "confirmed" and label in A.TERMS_VALUES
    assert why.startswith("INTERNAL-USE-ONLY") and "no re-dissemination" in why
    assert "500 calls/day" in why and "'Source: UN Comtrade'" in why
    ev = A.TERMS_EVIDENCE[SID]
    assert ev["terms_quote"] == ("Internal use: UN Comtrade data may be used internally for "
                                 "research, analysis, processing, modelling and AI.")
    assert "utilize the UN Comtrade APIs directly" in ev["policy_quote"]
    assert "internal use only and may not be re-disseminated" in ev["policy_quote"]
    assert ev["licence_quote"].startswith("5. Except as may otherwise be expressly permitted")
    assert "automated browsing or downloading, redistribution" in ev["licence_quote"]
    assert "500 calls/day" in ev["limits_quote"] and "1 call per second" in ev["limits_quote"]
    assert "TENSION" in ev["judgement"] and "to_confirm" in ev["judgement"]
    assert ev["checked_at"] == "2026-11-11"
    assert A.credit_of(SID) == "Source: UN Comtrade."
    assert "INTERNAL USE ONLY" in src.licence and "Source: UN Comtrade" in src.licence
    row = {r["id"]: r for r in A.roster_rows()}[SID]
    assert row["credit"] == "Source: UN Comtrade." and row["terms"] == "confirmed"
    assert row["auth"] == "none" and src.key_env is None


def test_robots_is_recorded_absent_from_the_box_read() -> None:
    ev = A.TERMS_EVIDENCE[SID]["robots"]
    assert "ROBOTS_ABSENT" in ev and "404" in ev
    assert "/mnt/project-files/reports/box_reads/comtrade_robots_2026-11-11.md" in ev.replace(
        '"', "")


def test_the_row_fails_closed_when_its_terms_are_not_confirmed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The fetch gate is the terms label: flipped back to `to_confirm` (the principal's call on
    licence s.5), the row is BLOCKED_ON_TERMS and nothing is requested, fixtures or live."""
    blocked = replace(A.BY_ID[SID], terms="to_confirm")
    assert A.status_of(blocked, {}) == "BLOCKED_ON_TERMS:to_confirm"

    def boom(url: str) -> tuple[bytes, str]:
        raise AssertionError(f"fetched {url}")

    paths = A.Paths(tmp_path / "desk")
    for fixtures in (None, FIX):
        rec = A.collect(paths, blocked, {}, NOW, fetch=True, fixtures=fixtures, deadline=1e18,
                        getter=boom)
        assert rec["requests"] == 0 and rec["status"] == "BLOCKED_ON_TERMS:to_confirm"


def test_instruments_are_xauusd_with_the_supply_legs_signed_against() -> None:
    src = A.BY_ID[SID]
    assert src.instruments == {"XAUUSD": 1}
    assert src.instruments_for("comtrade_cn_imp_from_hk_gold_kg") == {"XAUUSD": 1}
    assert src.instruments_for("comtrade_cn_net_imp_from_hk_gold_usd") == {"XAUUSD": 1}
    assert src.instruments_for("comtrade_ch_exp_to_hk_gold_usd") == {"XAUUSD": 1}
    assert src.instruments_for("comtrade_cn_exp_to_hk_gold_usd") == {"XAUUSD": -1}
    assert src.instruments_for("comtrade_ch_imp_from_hk_gold_kg") == {"XAUUSD": -1}
    assert src.vintage == "current" and src.cadence == "monthly"


def test_comtrade_values_never_reach_the_public_repository() -> None:
    """UN Comtrade is internal-use-only and this repository is public: the source's store and
    axis file are gitignored (the vault already is, under lake/), so a box state commit cannot
    publish a row."""
    gi = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(encoding="utf-8")
    assert "desks/mt5/data/alt_proxies/obs/un_comtrade_*" in gi
    assert "desks/mt5/data/axes/alt_un_comtrade_*" in gi
    assert "lake/" in gi
    # every Comtrade source's own paths, Saudi Arabia's included, fall under those lines
    assert set(A.COMTRADE_SPECS) == {SID, SA}
    owned = [p for sid in A.COMTRADE_SPECS for p in (
        f"desks/mt5/data/alt_proxies/obs/{sid}.json", f"desks/mt5/data/axes/alt_{sid}.json",
        f"desks/mt5/data/lake/vault/alt_{sid}/x.json",
        f"desks/mt5/data/lake/series/alt_{sid}__x.csv")]
    for p in owned:
        assert p.startswith("desks/mt5/data/lake/") or any(
            fnmatch.fnmatch(p, pat) for pat in ("desks/mt5/data/alt_proxies/obs/un_comtrade_*",
                                                "desks/mt5/data/axes/alt_un_comtrade_*")), p
    git = shutil.which("git")
    if git is not None and (ROOT / ".git").exists():
        res = subprocess.run([git, "check-ignore", "--no-index", *owned], cwd=ROOT,
                             capture_output=True, text=True, check=False)
        assert res.returncode == 0 and set(res.stdout.split()) == set(owned), res.stdout


# ============================================================================ Saudi Arabia
def test_sa_fixture_is_labelled_synthetic() -> None:
    assert json.loads(SA_BODY)["_fixture"].startswith("SYNTHETIC")
    assert "Every row and value is invented" in json.loads(SA_BODY)["_fixture"]


def test_sa_parser_reads_the_world_total_per_flow_and_drops_breakdowns() -> None:
    got = _by(A.parse_comtrade_sa_gold(SA_BODY, A.Ctx()))
    sep, aug = date(2024, 9, 30), date(2024, 8, 31)
    assert got[("comtrade_sa_imp_gold_usd", sep)] == 1250000000.0
    assert got[("comtrade_sa_imp_gold_kg", sep)] == pytest.approx(16400.0)
    assert got[("comtrade_sa_exp_gold_usd", sep)] == 420000000.0
    assert got[("comtrade_sa_exp_gold_kg", sep)] == pytest.approx(5300.0)
    assert got[("comtrade_sa_exp_gold_usd", aug)] == 310000000.0
    assert ("comtrade_sa_exp_gold_kg", aug) not in got              # netWgt null: no kg point
    # the transport, per-country and customs breakdown rows and the silver row are skipped
    assert len(got) == 7
    assert {s for s, _ in got} <= set(A.BY_ID[SA].signal_series)
    # the two specs never read each other's rows
    assert A.parse_comtrade_hk_gold(SA_BODY, A.Ctx()) == []
    assert A.parse_comtrade_sa_gold(BODY, A.Ctx()) == []


@pytest.mark.parametrize("body", [
    b"not json", b"<html>maintenance</html>", b"[]", b"{}", b'{"data": null}',
    b'{"data": [1, "a", null]}', b'{"statusCode": 404, "message": "Resource not found"}'])
def test_sa_parser_emits_nothing_on_garbage(body: bytes) -> None:
    assert A.parse_comtrade_sa_gold(body, A.Ctx()) == []


def test_sa_parser_keeps_only_the_partner_world_aggregate() -> None:
    good = json.loads(SA_BODY)["data"][0]
    assert A.parse_comtrade_sa_gold(json.dumps({"data": [good]}).encode(), A.Ctx())
    bad = [{**good, "partnerCode": 344}, {**good, "partnerCode": 784},
           {**good, "partner2Code": 784}, {**good, "motCode": 2100},
           {**good, "customsCode": "C01"}, {**good, "reporterCode": 156},
           {**good, "cmdCode": "7106"}, {**good, "flowCode": "RM"},
           {**good, "freqCode": "A"}, {**good, "period": "202400"},
           {**good, "primaryValue": "garbage", "netWgt": 0}]
    assert A.parse_comtrade_sa_gold(json.dumps({"data": bad}).encode(), A.Ctx()) == []
    dup = json.dumps({"data": [good, {**good, "primaryValue": 1.0}]}).encode()
    assert ("comtrade_sa_imp_gold_usd", date(2024, 9, 30)) not in _by(
        A.parse_comtrade_sa_gold(dup, A.Ctx()))


def test_sa_net_import_is_imports_minus_exports_only_where_both_flows_are_held() -> None:
    src = A.BY_ID[SA]
    store: dict[str, Any] = {}
    A.merge_vintages(store, src, A.parse_comtrade_sa_gold(SA_BODY, A.Ctx()), NOW)
    net = _by(A.comtrade_net_obs(store, A.COMTRADE_SA))
    sep, aug = date(2024, 9, 30), date(2024, 8, 31)
    assert net[("comtrade_sa_net_imp_gold_usd", sep)] == 1250000000.0 - 420000000.0
    assert net[("comtrade_sa_net_imp_gold_kg", sep)] == pytest.approx(16400.0 - 5300.0)
    assert net[("comtrade_sa_net_imp_gold_usd", aug)] == 980000000.0 - 310000000.0
    assert ("comtrade_sa_net_imp_gold_kg", aug) not in net          # export kg missing
    assert len(net) == 3
    # one flow alone writes no net
    only_imp = {k: v for k, v in store.items() if "_imp_gold_" in k}
    assert A.comtrade_net_obs(only_imp, A.COMTRADE_SA) == []
    # the Hong Kong derivation never reads Saudi rows
    assert A.comtrade_net_obs(store) == []


def test_sa_urls_ask_reporter_682_against_the_world_four_calls_a_pass() -> None:
    src = A.BY_ID[SA]
    st: dict[str, Any] = {}
    reqs = A.requests_for(src, NOW, st)
    assert len(reqs) == 4                                  # 2 flows x (recent + backfill)
    seen = set()
    for r in reqs:
        base, q = r.url.split("?")
        assert base == "https://comtradeapi.un.org/public/v1/preview/C/M/HS"
        qs = urllib.parse.parse_qs(q)
        assert qs["reporterCode"] == ["682"] and qs["partnerCode"] == ["0"]
        assert qs["cmdCode"] == ["7108"] and qs["flowCode"][0] in ("M", "X")
        assert "key" not in qs and "subscription" not in r.url.lower()
        seen.add((qs["flowCode"][0], qs["period"][0]))
    assert len(seen) == 4
    recent = urllib.parse.parse_qs(reqs[0].url.split("?")[1])["period"][0].split(",")
    assert recent[0] == "202610" and len(recent) == A.COMTRADE_RECENT_MONTHS
    assert st["backfill_to_next"] == "2025-10-01"
    assert A.comtrade_url(682, "X", ["202409"], partner=0).endswith(
        "?reporterCode=682&partnerCode=0&cmdCode=7108&flowCode=X&period=202409")
    # its own 20h clock: gated by its own last_attempt, never by Hong Kong's
    assert A.requests_for(src, NOW, {"last_attempt": (NOW - timedelta(hours=3)).isoformat()}) \
        == []
    due = {"last_attempt": (NOW - timedelta(hours=A.COMTRADE_MIN_GAP_H + 1)).isoformat()}
    assert len(A.requests_for(src, NOW, due)) == 4
    assert (8 + 4) * (24 // A.COMTRADE_MIN_GAP_H + 1) < A.COMTRADE_MAX_CALLS_PER_DAY


def test_sa_collect_runs_on_its_own_clock_and_paces_after_hong_kong(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(A, "_sleep", sleeps.append)
    monkeypatch.setattr(A, "_comtrade_last", None)
    paths = A.Paths(tmp_path / "desk")
    calls: list[str] = []

    def getter(url: str) -> tuple[bytes, str]:
        calls.append(url)
        return (SA_BODY if "reporterCode=682" in url else BODY), "application/json"

    state: dict[str, Any] = {}
    A.collect(paths, A.BY_ID[SID], state, NOW, fetch=True, fixtures=None, deadline=1e18,
              getter=getter)
    sleeps.clear()
    rec = A.collect(paths, A.BY_ID[SA], state, NOW, fetch=True, fixtures=None, deadline=1e18,
                    getter=getter)
    # four calls, every one paced -- the first too, straight after Hong Kong's last call
    assert len(calls) == 12 and sleeps == [A.COMTRADE_MIN_INTERVAL_S] * 4
    sst = state["sources"][SA]
    assert rec["errors"] == [] and sst["backfill_to"] == "2025-10-01"
    assert sst["last_attempt"] == NOW.isoformat(timespec="seconds")
    store = json.loads((paths.obs_dir / f"{SA}.json").read_text("utf-8"))
    assert "comtrade_sa_net_imp_gold_usd|2024-09-30" in store
    assert not any(k.startswith("comtrade_cn_") for k in store)


def test_sa_release_rule_terms_and_attribution_are_hong_kongs() -> None:
    src, hk = A.BY_ID[SA], A.BY_ID[SID]
    assert src.rule is A.rule_comtrade_monthly is hk.rule
    assert src.rule(date(2024, 9, 30)) == datetime(2024, 12, 30, tzinfo=UTC)
    assert A.TERMS[SA] == A.TERMS[SID] and A.TERMS[SA][0] == src.terms == "confirmed"
    assert A.TERMS_EVIDENCE[SA] is A.TERMS_EVIDENCE[SID]           # one shared record
    assert A.credit_of(SA) == "Source: UN Comtrade."
    row = {r["id"]: r for r in A.roster_rows()}[SA]
    assert row["credit"] == "Source: UN Comtrade." and row["terms"] == "confirmed"
    assert row["auth"] == "none" and src.key_env is None
    assert "INTERNAL USE ONLY" in src.licence and "Source: UN Comtrade" in src.licence
    # the note says why this is the route: GASTAT's own is robots-disallowed
    assert "robots-disallowed" in src.note and "sa_gastat_gold_terms_2026-11-11.md" in src.note


def test_sa_instruments_sign_imports_for_and_exports_against_gold() -> None:
    src = A.BY_ID[SA]
    assert src.instruments == {"XAUUSD": 1}
    assert src.instruments_for("comtrade_sa_imp_gold_usd") == {"XAUUSD": 1}
    assert src.instruments_for("comtrade_sa_net_imp_gold_kg") == {"XAUUSD": 1}
    assert src.instruments_for("comtrade_sa_exp_gold_usd") == {"XAUUSD": -1}
    assert src.instruments_for("comtrade_sa_exp_gold_kg") == {"XAUUSD": -1}
    assert src.vintage == "current" and src.cadence == "monthly"


def test_sa_fails_closed_when_its_terms_are_not_confirmed(tmp_path: Path) -> None:
    blocked = replace(A.BY_ID[SA], terms="to_confirm")
    assert A.status_of(blocked, {}) == "BLOCKED_ON_TERMS:to_confirm"

    def boom(url: str) -> tuple[bytes, str]:
        raise AssertionError(f"fetched {url}")

    paths = A.Paths(tmp_path / "desk")
    for fixtures in (None, FIX):
        rec = A.collect(paths, blocked, {}, NOW, fetch=True, fixtures=fixtures, deadline=1e18,
                        getter=boom)
        assert rec["requests"] == 0 and rec["status"] == "BLOCKED_ON_TERMS:to_confirm"
