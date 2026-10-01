"""A refused tool call in an unattended `claude -p` pass must leave a row that counts as MISSED.

The fixture events below copy the shapes Claude Code 2.1.285 emitted on 2026-09-30 for a real
refused `Bash` call under `--output-format stream-json --verbose`: a system `permission_denied`
event, an `is_error` tool_result, and the result event's `permission_denials` array.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from libs.ops import agent_denials as ad

ROOT = Path(__file__).resolve().parents[2]

_INIT = {"type": "system", "subtype": "init", "cwd": "C:/opt/quant", "model": "claude-opus-5"}
_USE_BASH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "toolu_A", "name": "Bash",
     "input": {"command": "ls desks/mt5/reports/JUDGING_BURNDOWN.json", "description": "x"}}]}}
_DENIED_EVT = {"type": "system", "subtype": "permission_denied", "tool_name": "Bash",
               "tool_use_id": "toolu_A", "message": "denied"}
_DENIED_RESULT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "toolu_A", "is_error": True,
     "content": "Claude requested permissions to use Bash, but you haven't granted it yet."}]}}
_USE_FETCH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "toolu_B", "name": "WebFetch",
     "input": {"url": "https://ecos.bok.or.kr/api/x?serviceKey=SECRETVALUE123&y=1",
               "prompt": "p"}}]}}
_FETCH_REFUSED = {"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "toolu_B", "is_error": True,
     "content": [{"type": "text", "text": "Claude requested permissions to use WebFetch, but "
                                          "you haven't granted it yet."}]}]}}
_TEXT = {"type": "assistant", "message": {"content": [{"type": "text", "text": "partial words"}]}}


def _result(denials: list[dict] | None = None, text: str = "PASS DONE") -> dict:
    return {"type": "result", "subtype": "success", "is_error": False, "result": text,
            "permission_denials": denials or []}


def _lines(*events: object) -> list[str]:
    return [e if isinstance(e, str) else json.dumps(e) for e in events]


DENIAL_STREAM = _lines(_INIT, _USE_BASH, _DENIED_EVT, _DENIED_RESULT, _result(
    [{"tool_name": "Bash", "tool_use_id": "toolu_A",
      "tool_input": {"command": "ls desks/mt5/reports/JUDGING_BURNDOWN.json"}}]))
CLEAN_STREAM = _lines(_INIT, _TEXT, _result())


# ------------------------------------------------------------------ parsing
def test_a_denial_is_found_once_across_all_three_signals() -> None:
    s = ad.parse_stream(DENIAL_STREAM)
    assert s.result_seen and s.result_text == "PASS DONE"
    assert len(s.denials) == 1
    d = s.denials[0]
    assert d["tool"] == "Bash" and d["tool_use_id"] == "toolu_A"
    assert set(d["signals"]) == {"system", "tool_result", "result"}


def test_no_denial_means_no_rows() -> None:
    s = ad.parse_stream(CLEAN_STREAM)
    assert s.denials == [] and s.result_text == "PASS DONE"
    assert ad.denial_rows(s, surface="cro_cycle") == []


def test_malformed_lines_are_counted_and_do_not_hide_the_refusals_around_them() -> None:
    lines = ["{not json", "plain stderr from the CLI", '["a list"]', *DENIAL_STREAM, ""]
    s = ad.parse_stream(lines)
    assert s.malformed == 2
    assert s.non_json == ["plain stderr from the CLI"]
    assert len(s.denials) == 1


def test_a_stream_cut_off_before_its_result_still_yields_the_refusal() -> None:
    s = ad.parse_stream(_lines(_INIT, _USE_FETCH, _FETCH_REFUSED, _TEXT))
    assert not s.result_seen
    assert s.result_text == "partial words"
    assert [d["tool"] for d in s.denials] == ["WebFetch"]
    assert s.denials[0]["tool_input"]["url"].startswith("https://ecos.bok.or.kr")


def test_an_ordinary_failed_command_is_not_relabelled_as_a_refusal() -> None:
    failed = {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "toolu_A", "is_error": True,
         "content": "cat: x: Permission denied"}]}}
    assert ad.parse_stream(_lines(_USE_BASH, failed, _result())).denials == []


def test_a_bom_on_the_first_line_is_tolerated() -> None:
    lines = DENIAL_STREAM.copy()
    lines[0] = "\ufeff" + lines[0]
    assert ad.parse_stream(lines).malformed == 0


# ------------------------------------------------------------------ rows and scrubbing
def test_each_row_is_unmeasured_and_counts_as_missed() -> None:
    rows = ad.denial_rows(ad.parse_stream(DENIAL_STREAM), surface="cro_cycle", lane="noon")
    assert len(rows) == 1
    r = rows[0]
    for k, v in {"verdict": "UNMEASURED", "counts_as": "MISSED", "reason": "permission_denied",
                 "tool": "Bash", "lane": "noon", "surface": "cro_cycle"}.items():
        assert r[k] == v
    assert "JUDGING_BURNDOWN" in r["input_summary"]
    assert r["duties"] == ["D13", "D15"]


def test_webfetch_refusals_serve_the_ingestion_duties_and_never_carry_the_key() -> None:
    s = ad.parse_stream(_lines(_USE_FETCH, _FETCH_REFUSED, _result()))
    (r,) = ad.denial_rows(s, surface="cro_cycle")
    assert "SECRETVALUE123" not in json.dumps(r)
    assert "serviceKey=[redacted]" in r["input_summary"]
    assert {"D7", "D13", "D19"} <= set(r["duties"])


@pytest.mark.parametrize("raw", [
    "cat data/secrets/claude_oauth_token",
    r"type C:\opt\quant\data\secrets\ntfy.json",
    "export ANTHROPIC_API_KEY=sk-ant-api03-abcdefghijklmnop",
    "curl -H 'Authorization: Bearer abcdefghijklmnop.qrstuv'",
    "echo ghp_abcdefghijklmnopqrstuvwxyz0123",
    "x 0123456789abcdef0123456789abcdef0123",
    "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcd",
])
def test_secrets_paths_and_key_shaped_strings_are_scrubbed(raw: str) -> None:
    out = ad.summarize_input("Bash", {"command": raw})
    for bad in ("claude_oauth_token", "ntfy.json", "abcdefghijklmnop", "ghp_abc",
                "0123456789abcdef0123", "AbCdEfGhIj"):
        assert bad not in out, (raw, out)


def test_a_long_repo_path_survives_scrubbing() -> None:
    p = "desks/mt5/data/hypotheses/gate_verdict_ledger_with_a_long_descriptive_name.jsonl"
    assert ad.scrub(p) == p


def test_the_summary_is_capped() -> None:
    out = ad.summarize_input("Bash", {"command": "echo " + "word " * 200})
    assert len(out) <= ad.SUMMARY_CAP and out.endswith("...")


def test_append_jsonl_writes_one_object_per_line(tmp_path: Path) -> None:
    led = tmp_path / "led.jsonl"
    rows = ad.denial_rows(ad.parse_stream(DENIAL_STREAM), surface="cro_cycle")
    assert ad.append_jsonl(led, rows) == 1 and ad.append_jsonl(led, []) == 0
    assert json.loads(led.read_text("utf-8").splitlines()[0])["counts_as"] == "MISSED"


# ------------------------------------------------------------------ duty scoring
def test_a_duty_the_pass_called_met_reads_missed_when_its_step_was_refused() -> None:
    duties = {"D15": {"status": "MET", "metric": "x"}, "D13": {"status": "MISSED"}}
    rows = ad.denial_rows(ad.parse_stream(DENIAL_STREAM), surface="cro_cycle")
    changed = ad.apply_to_duties(duties, rows)
    assert changed == ["D15"]
    assert duties["D15"]["status"] == "MISSED" and duties["D15"]["status_claimed"] == "MET"
    assert duties["D15"]["verdict"] == "UNMEASURED" and duties["D15"]["counts_as"] == "MISSED"
    assert duties["D13"]["status"] == "MISSED" and duties["D13"]["denied_steps"]


def _review(tmp_path: Path, at: str) -> Path:
    p = tmp_path / "TIER1_BREADTH_REVIEW.json"
    p.write_text(json.dumps({"history": [], "latest": {
        "at": at, "duties": {"D15": {"status": "MET"}, "D13": {"status": "MET"}}}}), "utf-8")
    return p


def test_the_review_this_pass_wrote_is_scored(tmp_path: Path) -> None:
    p = _review(tmp_path, "2026-09-30T12:30:00+00:00")
    rows = ad.denial_rows(ad.parse_stream(DENIAL_STREAM), surface="cro_cycle")
    out = ad.score_review(p, rows, "2026-09-30T12:00:01.1234567Z")
    assert out["applied"] and sorted(out["changed"]) == ["D13", "D15"]
    latest = json.loads(p.read_text("utf-8"))["latest"]
    assert latest["duties"]["D15"]["status"] == "MISSED"
    assert latest["permission_denials"]["count"] == 1


def test_an_older_review_is_never_rewritten(tmp_path: Path) -> None:
    p = _review(tmp_path, "2026-09-29T12:30:00+00:00")
    before = p.read_text("utf-8")
    rows = ad.denial_rows(ad.parse_stream(DENIAL_STREAM), surface="cro_cycle")
    out = ad.score_review(p, rows, "2026-09-30T12:00:00Z")
    assert not out["applied"] and p.read_text("utf-8") == before


# ------------------------------------------------------------------ the one domain list
EXPECTED_HOSTS = {
    "www.customs.go.kr", "www.tsa.gov", "api.census.gov", "api.e-stat.go.jp",
    "firms.modaps.eosdis.nasa.gov", "pib.gov.in", "data.gdeltproject.org", "wikimedia.org",
    "ecos.bok.or.kr", "www.meti.go.jp", "www.stats.gov.cn", "www.kobis.or.kr",
    "openapi.seoul.go.kr", "tablebuilder.singstat.gov.sg", "www.immd.gov.hk",
    "olinda.bcb.gov.br", "www.inegi.org.mx", "veriportali.tuik.gov.tr", "apis.data.go.kr",
}


def test_the_domain_file_holds_exactly_the_nineteen_confirmed_hosts() -> None:
    hosts = ad.load_webfetch_domains()
    assert len(hosts) == 19 and set(hosts) == EXPECTED_HOSTS
    assert ad.webfetch_rules()[0].startswith("WebFetch(domain:")


def test_a_malformed_or_unevidenced_host_is_refused(tmp_path: Path) -> None:
    for row in ({"domain": "*.evil.com", "sources": ["x"], "terms": "t"},
                {"domain": "https://a.gov", "sources": ["x"], "terms": "t"},
                {"domain": "ok.gov", "sources": [], "terms": "t"}):
        f = tmp_path / "d.json"
        f.write_text(json.dumps({"domains": [row]}), "utf-8")
        with pytest.raises(ValueError):
            ad.load_webfetch_domains(f)


# ------------------------------------------------------------------ the recorder CLI
def test_the_recorder_writes_ledger_log_and_review(tmp_path: Path) -> None:
    stream = tmp_path / "s.jsonl"
    stream.write_text("\ufeff" + "\n".join(DENIAL_STREAM) + "\n", "utf-8")
    led, log = tmp_path / "led.jsonl", tmp_path / "cycle_noon.log"
    review = _review(tmp_path, "2026-09-30T12:30:00+00:00")
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "record_agent_denials.py"),
                        "--stream", str(stream), "--ledger", str(led), "--log", str(log),
                        "--review", str(review), "--started-at", "2026-09-30T12:00:00Z",
                        "--lane", "noon", "--agent", "claude", "--date", "2026-09-30"],
                       capture_output=True, text=True, check=False, cwd=ROOT)
    assert p.returncode == 0, p.stderr
    summary = json.loads(p.stdout.strip().splitlines()[-1])
    assert summary["denials"] == 1 and summary["review_applied"]
    row = json.loads(led.read_text("utf-8"))
    assert row["counts_as"] == "MISSED" and row["lane"] == "noon"
    text = log.read_text("utf-8")
    assert "PASS DONE" in text and "PERMISSION DENIED" in text


def test_an_unreadable_stream_is_unmeasured_not_clean(tmp_path: Path) -> None:
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "record_agent_denials.py"),
                        "--stream", str(tmp_path / "absent.jsonl"),
                        "--ledger", str(tmp_path / "led.jsonl")],
                       capture_output=True, text=True, check=False, cwd=ROOT)
    assert p.returncode == 2
    assert json.loads(p.stdout)["status"] == "UNMEASURED"


# ------------------------------------------------------------------ the VPS probes
def test_the_vps_probes_hold_no_tools_and_no_bypass() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import brain_model_upgrade as bmu
    import run_model_upgrade as rmu

    for argv in (bmu.probe_argv(), rmu.ping_argv("claude-opus-5")):
        assert not any("dangerously" in a for a in argv)
        assert "bypassPermissions" not in argv
        i = argv.index("--allowedTools")
        assert argv[i + 1] == ""
        assert argv[argv.index("--output-format") + 1] == "stream-json"
        assert "--verbose" in argv and argv[argv.index("--max-turns") + 1] == "1"
    for name in ("brain_model_upgrade.py", "run_model_upgrade.py"):
        assert "--dangerously-skip-permissions\"" not in (ROOT / "scripts" / name).read_text()


def test_a_vps_probe_logs_its_refusals_and_reads_the_result_text(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_model_upgrade as rmu

    stream = "\n".join(_lines(_USE_BASH, _DENIED_EVT, _result(
        [{"tool_name": "Bash", "tool_use_id": "toolu_A", "tool_input": {"command": "ls"}}],
        text="PING-OK")))

    class _P:
        stdout, stderr, returncode = stream, "", 0

    monkeypatch.setattr(rmu, "_LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(rmu.subprocess, "run", lambda *a, **k: _P())
    ok, detail = rmu._ping("claude-opus-9")
    assert ok and detail == "PING-OK"
    row = json.loads((tmp_path / "log.jsonl").read_text("utf-8"))
    assert row["counts_as"] == "MISSED" and row["model"] == "claude-opus-9"


def test_a_probe_whose_prompt_merely_mentions_the_token_does_not_pass(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import brain_model_upgrade as bmu

    summary_only = json.dumps({"type": "system", "subtype": "post_turn_summary",
                               "status_detail": "asked to reply UPGRADE-OK"})

    class _P:
        stdout, stderr, returncode = summary_only + "\n" + json.dumps(
            _result(text="I cannot do that")), "", 0

    monkeypatch.setattr(bmu, "LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(bmu.subprocess, "run", lambda *a, **k: _P())
    ok, _ = bmu.probe("claude-opus-9")
    assert not ok
