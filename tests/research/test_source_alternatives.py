"""Tests for the replacement registry and the alternatives hunter.

The load-bearing assertion in this file is the INFORMATION-CLASS one. A registry that let any
reachable site stand in for a dead one would quietly change what corpus the miner reads while
every dashboard stayed green -- a topic change dressed up as a fix. So every candidate is checked
to carry the class of the source it substitutes for, and the class must be one of the named ones.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from libs.research import source_alternatives as alt
from libs.research import source_health as sh
from scripts import hunt_source_alternatives as hunt

_T0 = datetime(2026, 8, 1, 13, 0, tzinfo=UTC)


class TestRegistryShape:
    def test_every_candidate_is_in_the_same_information_class(self) -> None:
        # The whole design point: the desk does not need another website, it needs another source
        # of the SAME INFORMATION.
        for entry in alt.registry():
            for cand in entry.candidates:
                assert cand.information_class == entry.information_class, (
                    f"{entry.source} -> {cand.name} crosses information classes "
                    f"({cand.information_class} vs {entry.information_class})")

    def test_every_class_is_a_named_constant(self) -> None:
        for entry in alt.registry():
            assert entry.information_class in alt.INFORMATION_CLASSES

    def test_every_source_has_at_least_one_candidate(self) -> None:
        for entry in alt.registry():
            assert entry.candidates, f"{entry.source} registered with no substitutes"

    def test_every_candidate_names_concrete_parser_work(self) -> None:
        # "alternative reachable" and nothing else moves the work nowhere.
        for entry in alt.registry():
            for cand in entry.candidates:
                assert len(cand.next_action) > 30, f"{cand.name} has no real next action"

    def test_every_source_records_why_it_is_a_problem(self) -> None:
        for entry in alt.registry():
            assert len(entry.recorded_reason) > 20, f"{entry.source} has no recorded reason"

    def test_every_candidate_url_is_https(self) -> None:
        for entry in alt.registry():
            for cand in entry.candidates:
                assert cand.url.startswith("https://"), f"{cand.name}: {cand.url}"

    def test_source_names_are_unique(self) -> None:
        names = [e.source for e in alt.registry()]
        assert len(names) == len(set(names))

    def test_the_measured_dead_sources_are_all_registered(self) -> None:
        # Everything the tree currently records as blocked/needs_browser must have somewhere to
        # go, or the hunter would find a DEAD source it cannot even name a substitute for.
        registered = {e.source for e in alt.registry()}
        for measured_blocked in ("xueqiu", "zhihu", "csdn", "baidu", "joinquant", "bigquant",
                                 "ricequant", "github"):
            assert measured_blocked in registered

    def test_every_source_the_miner_can_record_as_failing_has_a_registry_entry(self) -> None:
        # Closes the loop the hunter exits 2 on: replay the desk's own last miner report through
        # the observation deriver and require that anything it can mark failing has somewhere to
        # go. Without this the registry gap is only discovered N runs later, in a cron log.
        import json

        report = Path(__file__).resolve().parent.parent.parent / "reports/research_queue.json"
        if not report.is_file():
            pytest.skip("no miner report in the tree to replay")
        doc = json.loads(report.read_text("utf-8"))
        failing = {o.source for o in sh.observations_from_miner_report(doc) if not o.ok}
        registered = {e.source for e in alt.registry()}
        assert failing <= registered, (
            f"no registered alternatives for {sorted(failing - registered)}")

    def test_known_good_in_tree_parsers_are_listed_first(self) -> None:
        # An alternative that is already built and already passing beats four aspirational URLs.
        for entry in alt.registry():
            built = [i for i, c in enumerate(entry.candidates) if c.in_tree is not None]
            assert built == list(range(len(built))), f"{entry.source}: in-tree not listed first"

    def test_in_tree_candidates_point_at_real_modules(self) -> None:
        root = Path(__file__).resolve().parent.parent.parent
        for entry in alt.registry():
            for cand in entry.candidates:
                if cand.in_tree is None:
                    continue
                # "libs/data/cn_sources.sogou_weixin" -> module libs/data/cn_sources.py, symbol
                # sogou_weixin. Both are checked: a stale in_tree pointer is a candidate the
                # report would present as already-built when it is not.
                mod, _, symbol = cand.in_tree.rpartition(".")
                path = root / f"{mod}.py"
                assert path.is_file(), f"{cand.name}: in_tree {cand.in_tree} -> {path} missing"
                assert f"def {symbol}(" in path.read_text("utf-8"), (
                    f"{cand.name}: {symbol} not defined in {path}")

    def test_by_information_class_exposes_single_points_of_failure(self) -> None:
        classes = alt.by_information_class()
        assert set(classes) <= set(alt.INFORMATION_CLASSES)
        assert alt.class_of("zhihu") == alt.CN_LONGFORM_QA
        assert alt.class_of("not_a_source") is None

    def test_alternatives_for_unknown_source_is_none_not_a_guess(self) -> None:
        assert alt.alternatives_for("some_site_nobody_registered") is None


class TestUnverifiedUntilProbed:
    def test_registry_candidates_all_start_unverified(self) -> None:
        for entry in alt.registry():
            for cand in entry.candidates:
                assert cand.status == alt.STATUS_UNVERIFIED
                assert cand.probe_detail is None

    def test_unverified_helper_reports_the_whole_registry_as_unprobed(self) -> None:
        for entry in alt.registry():
            assert len(alt.unverified(entry)) == len(entry.candidates)

    def test_probed_returns_a_new_object_and_never_mutates_the_registry(self) -> None:
        entry = alt.alternatives_for("baidu")
        assert entry is not None
        cand = entry.candidates[0]
        marked = alt.probed(cand, status=alt.STATUS_REACHABLE, detail="HTML, 120000 bytes")
        assert marked.status == alt.STATUS_REACHABLE
        assert cand.status == alt.STATUS_UNVERIFIED          # original untouched
        again = alt.alternatives_for("baidu")
        assert again is not None
        assert again.candidates[0].status == alt.STATUS_UNVERIFIED

    def test_reading_the_registry_twice_cannot_have_learned_anything(self) -> None:
        first = alt.registry()
        for entry in first:
            for cand in entry.candidates:
                alt.probed(cand, status=alt.STATUS_FAILED, detail="x")
        assert all(c.status == alt.STATUS_UNVERIFIED
                   for e in alt.registry() for c in e.candidates)


class TestProbeClassification:
    def test_small_html_is_a_shell_not_a_working_source(self) -> None:
        status, detail = hunt._classify_body(b"<html>tiny</html>", "text/html")
        assert status == alt.STATUS_SHELL
        assert "content bar" in detail

    def test_a_challenge_page_is_a_shell_even_when_large(self) -> None:
        body = ("<html>请输入验证码" + "x" * 60_000 + "</html>").encode()
        status, detail = hunt._classify_body(body, "text/html")
        assert status == alt.STATUS_SHELL
        assert "challenge marker" in detail

    def test_a_small_json_api_response_is_reachable(self) -> None:
        # A byte threshold is right for a results PAGE and completely wrong for an API: five
        # parsed results can be 3KB of perfectly good JSON.
        status, detail = hunt._classify_body(b'{"items": [1, 2, 3]}', "application/json")
        assert status == alt.STATUS_REACHABLE
        assert "JSON" in detail

    def test_an_empty_json_result_set_is_a_shell_not_a_replacement(self) -> None:
        # Measured live on Gitee's v5 search: 200 OK, 2 bytes, `[]`. Filing that as REACHABLE
        # emits a NEXT ACTION telling someone to parse a source that returned nothing.
        status, detail = hunt._classify_body(b"[]", "application/json")
        assert status == alt.STATUS_SHELL
        assert "EMPTY result set" in detail

    def test_unparseable_json_is_a_shell(self) -> None:
        status, _ = hunt._classify_body(b'{"items": ', "application/json")
        assert status == alt.STATUS_SHELL

    def test_large_html_is_reachable(self) -> None:
        status, _ = hunt._classify_body(b"<html>" + b"y" * 60_000, "text/html")
        assert status == alt.STATUS_REACHABLE


class TestHuntReport:
    def _write_dead(self, path: Path, source: str = "zhihu") -> None:
        for i in range(sh.DEAD_AFTER_CONSECUTIVE_FAILURES):
            sh.record_run([sh.Observation(source=source, ok=False, error="HTTP 403",
                                          vantage=sh.VANTAGE_PROXIED)],
                          path=path, now=_T0.replace(day=1 + i))

    def test_no_dead_sources_is_reported_as_a_result_not_an_empty_file(
            self, tmp_path: Path) -> None:
        ledger, out = tmp_path / "h.jsonl", tmp_path / "report.json"
        rc = hunt.main(["--ledger", str(ledger), "--out", str(out)])
        assert rc == 0
        doc = json.loads(out.read_text("utf-8"))
        assert doc["dead_sources"] == []
        assert doc["hunted"] == []
        assert "NO DEAD SOURCES" in doc["note"]

    def test_a_dead_source_is_hunted_and_its_claim_scoped(
            self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(hunt, "probe",
                            lambda url, timeout=25.0: (alt.STATUS_FAILED, "HTTP 403 Forbidden"))
        monkeypatch.setattr(hunt.time, "sleep", lambda _s: None)
        ledger, out = tmp_path / "h.jsonl", tmp_path / "report.json"
        self._write_dead(ledger)
        rc = hunt.main(["--ledger", str(ledger), "--out", str(out)])
        assert rc == 0
        doc = json.loads(out.read_text("utf-8"))
        assert doc["dead_sources"] == ["zhihu"]
        block = doc["hunted"][0]
        assert block["source"] == "zhihu"
        assert block["information_class"] == alt.CN_LONGFORM_QA
        assert block["health"]["scope"] == sh.SCOPE_THIS_VANTAGE
        assert "THIS BOX only" in block["health"]["claim"]

    def test_a_clean_probe_emits_a_concrete_next_action(
            self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(hunt, "probe",
                            lambda url, timeout=25.0: (alt.STATUS_REACHABLE, "HTML, 90000 bytes"))
        monkeypatch.setattr(hunt.time, "sleep", lambda _s: None)
        ledger, out = tmp_path / "h.jsonl", tmp_path / "report.json"
        self._write_dead(ledger)
        hunt.main(["--ledger", str(ledger), "--out", str(out)])
        doc = json.loads(out.read_text("utf-8"))
        assert doc["next_actions"]
        assert all(a.startswith("[zhihu -> ") for a in doc["next_actions"])

    def test_a_healthy_source_produces_standing_options_not_urgent_actions(
            self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # --all probes healthy sources too, which is the point -- but shouting "build a Crossref
        # parser" every day while arXiv is fine is how a daily organ becomes noise and gets muted.
        monkeypatch.setattr(hunt, "probe",
                            lambda url, timeout=25.0: (alt.STATUS_REACHABLE, "JSON, 9000 bytes"))
        monkeypatch.setattr(hunt.time, "sleep", lambda _s: None)
        ledger, out = tmp_path / "h.jsonl", tmp_path / "report.json"
        # RECORDED AT THE CURRENT INSTANT, not at the fixed _T0 (2026-08-05). hunt.main() is a
        # CLI and reads the ledger with the wall clock, so an observation stamped _T0 aged past
        # source_health.STALE_AFTER_HOURS and correctly decayed HEALTHY -> UNKNOWN. That was a
        # true reading of the fixture, not a bug in the hunter: this test means "a source that is
        # CURRENTLY healthy", and under the staleness rule healthy requires recent evidence. The
        # old form was also a time-bomb independent of that rule -- the write-read gap grew by one
        # real day per real day, waiting on the calendar rather than on anyone's edit.
        sh.record_run([sh.Observation(source="arxiv", ok=True)], path=ledger,
                      now=datetime.now(tz=UTC))
        hunt.main(["--source", "arxiv", "--ledger", str(ledger), "--out", str(out)])
        doc = json.loads(out.read_text("utf-8"))
        assert doc["hunted"][0]["health"]["verdict"] == sh.VERDICT_HEALTHY
        assert doc["next_actions"] == []
        assert doc["standing_redundancy_options"]

    def test_a_failed_probe_never_becomes_a_working_source(
            self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            hunt, "probe",
            lambda url, timeout=25.0: (alt.STATUS_FAILED, "TimeoutError: timed out"))
        monkeypatch.setattr(hunt.time, "sleep", lambda _s: None)
        ledger, out = tmp_path / "h.jsonl", tmp_path / "report.json"
        self._write_dead(ledger)
        hunt.main(["--ledger", str(ledger), "--out", str(out)])
        doc = json.loads(out.read_text("utf-8"))
        block = doc["hunted"][0]
        assert block["n_reachable"] == 0
        assert doc["next_actions"] == []
        probed_rows = [r for r in block["candidates"] if r["in_tree"] is None]
        assert all(r["probe_detail"] is not None for r in probed_rows)

    def test_a_vps_only_candidate_is_not_written_off_from_this_container(
            self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # "The same endpoint, from the unproxied box" is a real answer to a datacenter-IP block
        # and is exactly the one this container cannot test. Probing it here would answer a
        # different question, so it stays UNVERIFIED with that reason.
        monkeypatch.setattr(hunt, "probe",
                            lambda url, timeout=25.0: (alt.STATUS_REACHABLE, "should not run"))
        monkeypatch.setattr(hunt.time, "sleep", lambda _s: None)
        monkeypatch.setattr(hunt.health, "current_vantage", lambda: sh.VANTAGE_PROXIED)
        ledger, out = tmp_path / "h.jsonl", tmp_path / "report.json"
        rc = hunt.main(["--source", "youtube_captions", "--ledger", str(ledger),
                        "--out", str(out)])
        assert rc == 0
        rows = {r["name"]: r for r in json.loads(out.read_text("utf-8"))["hunted"][0]["candidates"]}
        vps_only = rows["youtube_timedtext_from_vps"]
        assert vps_only["status"] == alt.STATUS_UNVERIFIED
        assert vps_only["probe_detail"] is not None
        assert "vantage" in vps_only["probe_detail"]

    def test_a_dead_source_with_no_registered_alternative_exits_two(
            self, tmp_path: Path) -> None:
        ledger, out = tmp_path / "h.jsonl", tmp_path / "report.json"
        self._write_dead(ledger, source="some_unregistered_source")
        rc = hunt.main(["--ledger", str(ledger), "--out", str(out)])
        assert rc == 2
        doc = json.loads(out.read_text("utf-8"))
        assert doc["dead_without_registered_alternatives"] == ["some_unregistered_source"]

    def test_report_states_the_vantage_it_measured_from(self, tmp_path: Path) -> None:
        out = tmp_path / "report.json"
        hunt.main(["--ledger", str(tmp_path / "h.jsonl"), "--out", str(out)])
        doc = json.loads(out.read_text("utf-8"))
        assert doc["vantage"] in (sh.VANTAGE_PROXIED, sh.VANTAGE_DIRECT)
        assert "egress proxy" in doc["vantage_note"]
        assert doc["dead_after_consecutive_failures"] == sh.DEAD_AFTER_CONSECUTIVE_FAILURES
