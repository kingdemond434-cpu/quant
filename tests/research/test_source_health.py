"""Tests for the per-source health ledger.

The rules under test are the ones that decide whether the desk ACTS on a dead source, so each
gets its own test with the reason it exists written down: a threshold that fires early sends the
hunter chasing sources that heal themselves, and a threshold that condemns a never-probed source
lets the desk retire something it never even tried.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.research import source_health as sh

_T0 = datetime(2026, 8, 1, 13, 0, tzinfo=UTC)
#: Every read below is anchored HERE, not to the wall clock. These tests write ledger rows stamped
#: _T0 and then read them back; reading with datetime.now() meant the gap between write and read
#: grew by one real day per real day, so any assertion sensitive to that gap was a time-bomb
#: waiting on the calendar rather than on anything the code does. Anchoring makes the gap a
#: constant the test states.
#:
#: One hour after _T0, the fixture epoch -- NOT after each test's last write. Multi-day fixtures
#: (`_run_days`) write out to _T0+4d, so those rows are read at a NEGATIVE age. That is harmless
#: and deliberate: the staleness decay only touches HEALTHY, and every multi-day fixture here is
#: building a DEGRADED or DEAD verdict. A single anchor cannot be both "just after a one-run
#: fixture" and "just after a five-day one" without falling outside STALE_AFTER_HOURS for the
#: first, and the one-run fixtures are precisely the staleness-sensitive ones.
_READ = _T0 + timedelta(hours=1)


def _fail(source: str = "zhihu", *, vantage: str = sh.VANTAGE_PROXIED) -> sh.Observation:
    return sh.Observation(source=source, ok=False, error="HTTP 403", vantage=vantage)


def _ok(source: str = "zhihu", *, vantage: str = sh.VANTAGE_PROXIED) -> sh.Observation:
    return sh.Observation(source=source, ok=True, vantage=vantage)


def _run_days(path: Path, obs: list[sh.Observation], *, start: datetime = _T0) -> None:
    """One observation per UTC day, so the counter advances a run at a time."""
    for i, o in enumerate(obs):
        sh.record_run([o], path=path, now=start + timedelta(days=i))


class TestDeadThreshold:
    def test_flips_to_dead_at_exactly_n_consecutive_failures(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        n = sh.DEAD_AFTER_CONSECUTIVE_FAILURES
        _run_days(p, [_fail() for _ in range(n)])
        st = sh.state_of("zhihu", p, now=_READ)
        assert st.consecutive_failed_runs == n
        assert st.verdict == sh.VERDICT_DEAD

    def test_not_dead_one_run_before_the_threshold(self, tmp_path: Path) -> None:
        # The whole point of the constant: DEGRADED is loud from failure one, but the automatic
        # hunt does not fire until the streak is long enough to outlast every transient this desk
        # has measured (Sogou's anti-bot page, Bilibili's rotating WBI keys, the L0052 UA filter).
        p = tmp_path / "health.jsonl"
        n = sh.DEAD_AFTER_CONSECUTIVE_FAILURES
        _run_days(p, [_fail() for _ in range(n - 1)])
        st = sh.state_of("zhihu", p, now=_READ)
        assert st.consecutive_failed_runs == n - 1
        assert st.verdict == sh.VERDICT_DEGRADED
        assert not st.dead_here

    def test_first_failure_is_degraded_not_dead(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        sh.record_run([_fail()], path=p, now=_T0)
        assert sh.state_of("zhihu", p, now=_READ).verdict == sh.VERDICT_DEGRADED

    def test_single_failure_after_a_success_does_not_flip(self, tmp_path: Path) -> None:
        # A long healthy history followed by one bad day is a blip, and treating it as death
        # would be the churn the threshold exists to prevent.
        p = tmp_path / "health.jsonl"
        _run_days(p, [_ok() for _ in range(10)] + [_fail()])
        st = sh.state_of("zhihu", p, now=_READ)
        assert st.consecutive_failed_runs == 1
        assert st.verdict == sh.VERDICT_DEGRADED

    def test_a_success_resets_the_streak(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        n = sh.DEAD_AFTER_CONSECUTIVE_FAILURES
        _run_days(p, [_fail() for _ in range(n - 1)] + [_ok()] + [_fail()])
        st = sh.state_of("zhihu", p, now=_READ)
        assert st.consecutive_failed_runs == 1
        assert st.verdict == sh.VERDICT_DEGRADED
        assert st.last_ok_utc is not None

    def test_dead_sources_lists_only_the_dead(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        n = sh.DEAD_AFTER_CONSECUTIVE_FAILURES
        _run_days(p, [_fail("zhihu") for _ in range(n)])
        sh.record_run([_fail("csdn"), _ok("juejin")], path=p, now=_T0 + timedelta(days=99))
        assert [s.source for s in sh.dead_sources(p, now=_READ)] == ["zhihu"]


class TestUnknownIsNotDead:
    def test_source_never_probed_is_unknown(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        st = sh.state_of("never_touched", p, now=_READ)
        assert st.verdict == sh.VERDICT_UNKNOWN
        assert st.scope == sh.SCOPE_UNKNOWN
        assert not st.dead_here
        assert not st.dead_globally
        assert "never probed" in st.claim()

    def test_unknown_on_an_empty_ledger_with_other_sources_present(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        _run_days(p, [_fail("zhihu") for _ in range(sh.DEAD_AFTER_CONSECUTIVE_FAILURES)])
        assert sh.state_of("bigquant", p, now=_READ).verdict == sh.VERDICT_UNKNOWN

    def test_verdict_for_refuses_to_score_an_unchecked_source(self) -> None:
        verdict, scope = sh.verdict_for(consecutive_failed_runs=99, last_checked_utc=None,
                                        failing_vantages=[], ok_vantages=[])
        assert (verdict, scope) == (sh.VERDICT_UNKNOWN, sh.SCOPE_UNKNOWN)

    def test_declared_but_unmeasured_probe_row_produces_no_observation(self) -> None:
        # papers.probe_all() hardcodes reddit as ok=false WITHOUT making a request. Counting that
        # as a failed run would march a never-probed source to DEAD on the strength of a comment.
        doc = {"academic_probe": [
            {"source": "reddit", "ok": False, "error": "HTTP 403 -- blocked"},
            {"source": "arxiv", "ok": True, "n": 5, "error": None},
        ]}
        names = {o.source for o in sh.observations_from_miner_report(doc)}
        assert names == {"arxiv"}
        assert "reddit" not in names


class TestBlockedHereIsNotDeadGlobally:
    def test_failures_from_one_vantage_scope_to_that_vantage(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        n = sh.DEAD_AFTER_CONSECUTIVE_FAILURES
        _run_days(p, [_fail(vantage=sh.VANTAGE_PROXIED) for _ in range(n)])
        st = sh.state_of("zhihu", p, now=_READ)
        assert st.verdict == sh.VERDICT_DEAD
        assert st.scope == sh.SCOPE_THIS_VANTAGE
        assert st.dead_here
        assert not st.dead_globally          # the claim the desk is NOT entitled to make
        assert "THIS BOX only" in st.claim()

    def test_failures_from_two_vantages_scope_global(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        n = sh.DEAD_AFTER_CONSECUTIVE_FAILURES
        obs = [_fail(vantage=sh.VANTAGE_PROXIED) for _ in range(n - 1)]
        obs.append(_fail(vantage=sh.VANTAGE_DIRECT))
        _run_days(p, obs)
        st = sh.state_of("zhihu", p, now=_READ)
        assert st.verdict == sh.VERDICT_DEAD
        assert st.scope == sh.SCOPE_GLOBAL
        assert st.dead_globally
        assert "claim about the SOURCE" in st.claim()

    def test_health_from_one_vantage_is_also_only_a_local_claim(self, tmp_path: Path) -> None:
        # The proxy cuts both ways: reachable HERE does not prove reachable on the VPS, because
        # the proxy's egress may be exactly what a geo/IP rule is letting through.
        p = tmp_path / "health.jsonl"
        sh.record_run([_ok("juejin", vantage=sh.VANTAGE_PROXIED)], path=p, now=_T0)
        st = sh.state_of("juejin", p, now=_READ)
        assert st.verdict == sh.VERDICT_HEALTHY
        assert st.scope == sh.SCOPE_THIS_VANTAGE

    def test_current_vantage_reads_the_proxy_environment(self) -> None:
        assert sh.current_vantage({"HTTPS_PROXY": "http://127.0.0.1:45903"}) == sh.VANTAGE_PROXIED
        assert sh.current_vantage({}) == sh.VANTAGE_DIRECT
        assert sh.current_vantage({"HTTPS_PROXY": ""}) == sh.VANTAGE_DIRECT


class TestLedgerDurability:
    def test_append_only_across_days(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        _run_days(p, [_fail() for _ in range(3)])
        lines = [ln for ln in p.read_text("utf-8").splitlines() if ln.strip()]
        assert len(lines) == 3
        assert [json.loads(ln)["consecutive_failed_runs"] for ln in lines] == [1, 2, 3]

    def test_idempotent_per_utc_day(self, tmp_path: Path) -> None:
        # The miner is scheduled daily but is also run by hand; three runs in one day must not
        # advance the counter three times, or a source reaches DEAD on a single afternoon.
        p = tmp_path / "health.jsonl"
        for hour in (1, 5, 23):
            sh.record_run([_fail()], path=p, now=_T0.replace(hour=hour))
        lines = [ln for ln in p.read_text("utf-8").splitlines() if ln.strip()]
        assert len(lines) == 1
        assert sh.state_of("zhihu", p, now=_READ).consecutive_failed_runs == 1

    def test_same_day_rerun_supersedes_only_that_source(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        sh.record_run([_fail("zhihu"), _fail("csdn")], path=p, now=_T0)
        sh.record_run([_fail("zhihu")], path=p, now=_T0.replace(hour=20))
        lines = [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]
        assert len(lines) == 2
        assert {r["source"] for r in lines} == {"zhihu", "csdn"}
        assert sh.state_of("csdn", p, now=_READ).consecutive_failed_runs == 1

    def test_one_source_observed_twice_in_one_run_writes_one_row(self, tmp_path: Path) -> None:
        # The invariant is one row per source per UTC day no matter who calls this; a caller that
        # passes the same source twice must not advance the streak twice either.
        p = tmp_path / "health.jsonl"
        sh.record_run([_fail("zhihu"), _fail("zhihu")], path=p, now=_T0)
        lines = [ln for ln in p.read_text("utf-8").splitlines() if ln.strip()]
        assert len(lines) == 1
        assert sh.state_of("zhihu", p, now=_READ).consecutive_failed_runs == 1

    def test_folding_uses_any_lane_up(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        sh.record_run([_fail("juejin"), _ok("juejin")], path=p, now=_T0)
        assert sh.state_of("juejin", p, now=_READ).verdict == sh.VERDICT_HEALTHY

    def test_unparseable_lines_are_preserved(self, tmp_path: Path) -> None:
        # History is evidence. A line this parser cannot read may still be readable by a human,
        # and silently dropping it would destroy the only record of whatever wrote it.
        p = tmp_path / "health.jsonl"
        p.write_text("not json at all\n{\"source\": \"zhihu\", \"day\": \"2026-07-01\"}\n", "utf-8")
        sh.record_run([_fail()], path=p, now=_T0)
        text = p.read_text("utf-8")
        assert "not json at all" in text

    def test_write_is_atomic_and_leaves_no_tmp(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        sh.record_run([_fail()], path=p, now=_T0)
        assert not (tmp_path / "health.jsonl.tmp").exists()

    def test_timestamps_are_timezone_aware_utc(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        sh.record_run([_ok()], path=p, now=_T0)
        stamp = sh.state_of("zhihu", p, now=_READ).last_ok_utc
        assert stamp is not None
        assert datetime.fromisoformat(stamp).tzinfo is not None

    def test_naive_now_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="naive"):
            sh.record_run([_ok()], path=tmp_path / "h.jsonl",
                          now=datetime(2026, 8, 1, 13, 0))


class TestReplaced:
    def test_mark_replaced_sets_the_verdict_and_names_the_substitute(self,
                                                                     tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        _run_days(p, [_fail() for _ in range(sh.DEAD_AFTER_CONSECUTIVE_FAILURES)])
        st = sh.mark_replaced("zhihu", "wechat", path=p, now=_T0 + timedelta(days=30))
        assert st.verdict == sh.VERDICT_REPLACED
        assert st.replaced_by == "wechat"
        assert sh.state_of("zhihu", p, now=_READ).verdict == sh.VERDICT_REPLACED
        assert sh.dead_sources(p, now=_READ) == []   # replaced sources are no longer hunted

    def test_replacement_survives_a_later_probe(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        sh.mark_replaced("zhihu", "wechat", path=p, now=_T0)
        sh.record_run([_fail()], path=p, now=_T0 + timedelta(days=1))
        assert sh.state_of("zhihu", p, now=_READ).replaced_by == "wechat"


class TestObservationsFromMinerReport:
    def test_a_lane_that_fetched_counts_as_usable(self) -> None:
        doc = {"bilibili_discovered": {"量化交易 策略": 60}, "channels_blocked": {}}
        obs = {o.source: o for o in sh.observations_from_miner_report(doc)}
        assert obs["bilibili"].ok

    def test_mining_success_outranks_a_diagnostic_probe_failure(self) -> None:
        # The live case: the miner reads Bilibili through WBI-signed search while CN_SOURCES
        # probes the RAW endpoint, which answers 412 because it is unsigned. Letting the probe
        # outvote 15 mined rows would mark a working source dead.
        doc = {
            "bilibili_discovered": {"量化交易 策略": 60},
            "cn_sources": [{"name": "bilibili", "reachable": True, "bytes": 38,
                            "looks_like_content": False}],
        }
        obs = {o.source: o for o in sh.observations_from_miner_report(doc)}
        assert obs["bilibili"].ok

    def test_any_lane_up_means_the_platform_is_up(self) -> None:
        doc = {"cn_article_discovered": {"juejin:量化 回测 陷阱": 20},
               "channels_blocked": {"juejin:因子 挖掘 回测": "HTTPError: 500"}}
        obs = {o.source: o for o in sh.observations_from_miner_report(doc)}
        assert obs["juejin"].ok

    def test_every_lane_down_is_a_failure_with_the_reason_kept(self) -> None:
        doc = {"channels_blocked": {"juejin:量化": "HTTPError: HTTP Error 503"}}
        obs = {o.source: o for o in sh.observations_from_miner_report(doc)}
        assert not obs["juejin"].ok
        assert obs["juejin"].error is not None
        assert "503" in obs["juejin"].error

    def test_a_source_not_attempted_gets_no_observation(self) -> None:
        # `--only bilibili` leaves every other group absent. Absence is absence (L1.41): those
        # counters must neither advance nor reset.
        doc = {"bilibili_discovered": {"量化": 60}}
        assert {o.source for o in sh.observations_from_miner_report(doc)} == {"bilibili"}

    def test_reachable_shell_is_a_failure_not_a_success(self) -> None:
        doc = {"cn_sources": [{"name": "baidu", "reachable": True, "bytes": 1438,
                               "looks_like_content": False}]}
        obs = {o.source: o for o in sh.observations_from_miner_report(doc)}
        assert not obs["baidu"].ok
        assert obs["baidu"].error is not None
        assert "1438" in obs["baidu"].error

    def test_a_byte_count_cannot_refute_a_recorded_needs_browser_finding(self) -> None:
        # BigQuant's JS shell measures 27,705 bytes and clears the 20,000-byte content bar while
        # carrying zero listings. A probe measures bytes, not rendering, so it is not evidence
        # against the recorded finding -- marking it HEALTHY would be a dead lane wearing a green
        # badge, which is worse than the silence it replaces.
        doc = {"cn_sources": [{"name": "bigquant", "declared": "needs_browser",
                               "reason": "reachable but JS-rendered; listings require Chromium",
                               "reachable": True, "bytes": 27705, "looks_like_content": True}]}
        obs = {o.source: o for o in sh.observations_from_miner_report(doc)}
        assert not obs["bigquant"].ok
        assert obs["bigquant"].error is not None
        assert "needs_browser" in obs["bigquant"].error

    def test_a_probe_still_refutes_a_declared_block(self) -> None:
        # The other half of L0052: a recorded HTTP failure that turns out to be a header problem
        # must be allowed to come back. A declared "blocked" IS a prior the probe can overturn.
        doc = {"cn_sources": [{"name": "xueqiu", "declared": "blocked",
                               "reason": "was 403 once", "reachable": True, "bytes": 110310,
                               "looks_like_content": True}]}
        obs = {o.source: o for o in sh.observations_from_miner_report(doc)}
        assert obs["xueqiu"].ok

    def test_youtube_lanes_collapse_to_one_platform(self) -> None:
        doc = {"channels_scanned": {"@neurotrader888": 24},
               "search_discovered": {"quant backtest": 20},
               "channels_blocked": {"@Algovibes": "LAYOUT CHANGE"}}
        obs = {o.source: o for o in sh.observations_from_miner_report(doc)}
        assert set(obs) == {"youtube"}
        assert obs["youtube"].ok

    def test_wechat_probe_name_is_canonicalised_onto_the_mining_name(self) -> None:
        doc = {"cn_article_discovered": {"wechat:量化": 10},
               "cn_source_probe": [{"source": "wechat_sogou", "ok": False, "n": 0,
                                    "error": "rate limited"}]}
        names = [o.source for o in sh.observations_from_miner_report(doc)]
        assert names.count("wechat") == 1
        assert "wechat_sogou" not in names

    def test_record_from_report_folds_a_whole_report_in(self, tmp_path: Path) -> None:
        p = tmp_path / "health.jsonl"
        doc = {"cn_sources": [{"name": "zhihu", "reachable": False, "http_status": 403}],
               "cn_article_discovered": {"juejin:量化": 20}}
        touched = sh.record_from_report(doc, path=p, now=_T0)
        assert set(touched) == {"zhihu", "juejin"}
        assert sh.state_of("zhihu", p, now=_READ).verdict == sh.VERDICT_DEGRADED
        assert sh.state_of("juejin", p, now=_READ).verdict == sh.VERDICT_HEALTHY


class TestAHealthyVerdictIsAClaimAboutThePresent:
    """A source probed once, successfully, and then never probed again reported HEALTHY forever
    (found 2026-08-05). The write side was honest -- it recorded what it saw -- and the read side
    quoted that record as though it described today, with no one ever asking how old it was.

    ``verdict_for`` already refused to score a source with ``last_checked_utc=None``, which closes
    the NEVER-probed hole and leaves the STOPPED-BEING-probed one open. They are the same hole at
    different ages, and only the first one had a test.

    Why this is the expensive version of the bug: scripts/hunt_source_alternatives.py hunts
    replacements for whatever ``dead_sources()`` returns, and a stale HEALTHY never enters that
    list. So a lane that quietly stopped being probed is never hunted, never replaced, and never
    reported -- miner breadth collapses with every artifact still showing green.
    """

    def _aged(self, path: Path, hours: float) -> sh.SourceState:
        """One successful probe, then the clock moves on and nothing probes again."""
        sh.record_run([_ok("zhihu")], path=path, now=_T0)
        return sh.state_of("zhihu", path, now=_T0 + timedelta(hours=hours))

    def test_a_fresh_success_is_healthy(self, tmp_path: Path) -> None:
        st = self._aged(tmp_path / "h.jsonl", 1.0)
        assert st.verdict == sh.VERDICT_HEALTHY, (
            "a check that fires on the healthy case is a check that gets deleted")

    def test_a_success_just_inside_the_window_is_still_healthy(self, tmp_path: Path) -> None:
        st = self._aged(tmp_path / "h.jsonl", sh.STALE_AFTER_HOURS - 0.1)
        assert st.verdict == sh.VERDICT_HEALTHY

    def test_a_success_past_the_window_decays_to_unknown(self, tmp_path: Path) -> None:
        st = self._aged(tmp_path / "h.jsonl", sh.STALE_AFTER_HOURS + 0.1)
        assert st.verdict == sh.VERDICT_UNKNOWN
        assert st.scope == sh.SCOPE_UNKNOWN, (
            "an aged-out claim cannot keep the scope of the observation that is no longer current")

    def test_the_decay_says_why_rather_than_just_changing_the_answer(self, tmp_path: Path) -> None:
        st = self._aged(tmp_path / "h.jsonl", 500.0)
        assert "STALE" in (st.last_error or "")
        assert "not a failure" in (st.last_error or ""), (
            "the reason must distinguish 'we stopped looking' from 'it broke' -- they have "
            "different first moves and the operator must not have to guess which happened")

    def test_a_stale_success_is_never_reported_as_dead(self, tmp_path: Path) -> None:
        """The decay target is the load-bearing choice. An old success is the ABSENCE of recent
        evidence, not evidence of failure; calling it DEAD would manufacture a failure nobody
        observed and send the hunter chasing a source that may be perfectly fine."""
        p = tmp_path / "h.jsonl"
        st = self._aged(p, 10_000.0)
        assert st.verdict != sh.VERDICT_DEAD
        assert not st.dead_here
        assert not sh.dead_sources(p, now=_T0 + timedelta(hours=10_000.0))

    def test_a_dead_verdict_does_not_age_out(self, tmp_path: Path) -> None:
        """The inverse error, and the more expensive one: ageing DEAD to UNKNOWN would drop the
        source out of dead_sources() and silently CANCEL the alternatives hunt its failure
        started -- while looking like the situation had improved."""
        p = tmp_path / "h.jsonl"
        _run_days(p, [_fail("zhihu") for _ in range(sh.DEAD_AFTER_CONSECUTIVE_FAILURES)])
        late = _T0 + timedelta(days=400)
        assert sh.state_of("zhihu", p, now=late).verdict == sh.VERDICT_DEAD
        assert [s.source for s in sh.dead_sources(p, now=late)] == ["zhihu"]

    def test_a_replaced_verdict_does_not_age_out(self, tmp_path: Path) -> None:
        """A replacement is a desk DECISION, not an observation, so it does not decay with the
        clock -- there is no probe whose absence makes it less true."""
        p = tmp_path / "h.jsonl"
        sh.record_run([_ok("zhihu")], path=p, now=_T0)
        sh.mark_replaced("zhihu", "bigquant", path=p, now=_T0)
        assert sh.state_of("zhihu", p, now=_T0 + timedelta(days=400)).verdict == sh.VERDICT_REPLACED

    def test_a_healthy_row_with_an_unreadable_date_decays(self, tmp_path: Path) -> None:
        """The sharpest form of the bug, not an edge case: a claim of health carrying no readable
        date can NEVER be shown to be old, so exempting it would leave the original defect intact
        for exactly the rows least able to justify themselves."""
        p = tmp_path / "h.jsonl"
        sh.record_run([_ok("zhihu")], path=p, now=_T0)
        rows = [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]
        rows[-1]["last_checked_utc"] = "not a date"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")
        st = sh.state_of("zhihu", p, now=_T0 + timedelta(hours=1))
        assert st.verdict == sh.VERDICT_UNKNOWN
        assert "no readable check timestamp" in (st.last_error or "")

    def test_age_hours_reports_none_rather_than_zero_when_undatable(self) -> None:
        """None must never collapse to 0.0. A row that cannot prove its age reading as 'fresh' is
        the precise shape of the whole defect."""
        assert sh.SourceState(source="x").age_hours(now=_T0) is None
        assert sh.SourceState(source="x", last_checked_utc="garbage").age_hours(now=_T0) is None

    def test_age_hours_measures_real_elapsed_time(self, tmp_path: Path) -> None:
        p = tmp_path / "h.jsonl"
        sh.record_run([_ok("zhihu")], path=p, now=_T0)
        raw = sh.load_states(p, stale_after_h=float("inf"))["zhihu"]
        assert raw.age_hours(now=_T0 + timedelta(hours=30)) == pytest.approx(30.0, abs=0.02)

    def test_raw_rows_remain_reachable_but_only_on_purpose(self, tmp_path: Path) -> None:
        """An escape hatch must exist -- forensics needs the stored row -- but it must be TYPED,
        never the default, or the defect returns through the convenient path."""
        p = tmp_path / "h.jsonl"
        sh.record_run([_ok("zhihu")], path=p, now=_T0)
        late = _T0 + timedelta(days=400)
        assert sh.load_states(p, now=late)["zhihu"].verdict == sh.VERDICT_UNKNOWN
        assert sh.load_states(p, now=late,
                              stale_after_h=float("inf"))["zhihu"].verdict == sh.VERDICT_HEALTHY

    def test_unproven_lists_the_lanes_nothing_else_was_responsible_for(self,
                                                                      tmp_path: Path) -> None:
        """dead_sources() answers 'what failed'. A lane that stopped being probed never fails, so
        before this it appeared in no list at all and no organ owned it."""
        p = tmp_path / "h.jsonl"
        sh.record_run([_ok("zhihu"), _ok("bigquant")], path=p, now=_T0)
        sh.record_run([_ok("bigquant")], path=p, now=_T0 + timedelta(days=30))
        # 31 days after T0: zhihu's evidence is 31d old, bigquant's is 1d old.
        names = [s.source for s in sh.unproven_sources(p, now=_T0 + timedelta(days=31))]
        assert names == ["zhihu"], f"expected only the un-reprobed lane, got {names}"

    def test_unproven_is_ordered_weakest_evidence_first(self, tmp_path: Path) -> None:
        p = tmp_path / "h.jsonl"
        sh.record_run([_ok("older")], path=p, now=_T0)
        sh.record_run([_ok("newer")], path=p, now=_T0 + timedelta(days=5))
        names = [s.source for s in sh.unproven_sources(p, now=_T0 + timedelta(days=40))]
        assert names == ["older", "newer"], "oldest evidence must sort first"
