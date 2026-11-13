"""THE DONE ROWS' PROOFS ARE PUBLISHED, AND NOTHING THAT IDENTIFIES THE BOX GOES WITH THEM.

The underbuilt audit of 2026-11-13 could not verify L141/L144/L230/L115/L310/L318 because their
artifacts stayed on the trading box. `research/public_proofs.py` (core hourly leg
`public_proofs`) writes redacted projections into desks/mt5/reports/public/ and the box sync
publishes them. The repository is public, so the central test here plants a hostname, an IP, a
token, an absolute path and exception text in EVERY source and asserts that none of them reaches
ANY file the leg writes.
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for p in (str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.ops import public_redact as R  # noqa: E402
from research import public_proofs as PP  # noqa: E402
from research import recovery_drills as rd  # noqa: E402

NOW = datetime(2026, 11, 13, 18, tzinfo=UTC)

HOST = "vmi3571445"
IP = "95.216.191.70"
IP6 = "fe80::1ff:fe23:4567:890a"
TOKENS = ("ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4", "sk-" + "planted0token0value0abcdef123",
          "github_pat_" + "11ABCDEFG0123456789_abcdefghijk")
WIN_PATH = r"C:\Users\Administrator\memecoin-codex-stage-20261020\repo\data\state"
POSIX_PATH = "/home/quant/quant-platform/data/secrets/key.hmac"
EXC_TEXT = "ValueError: planted-xyzzy-message"
EMAIL = "someone.planted@example.org"
PLANTED_WORDS = ("planted-xyzzy-message", HOST, IP, IP6, *TOKENS, "Administrator",
                 "quant-platform", "key.hmac", EMAIL)


def _poison(extra: dict[str, object] | None = None) -> dict[str, object]:
    """A source document carrying every plant, in values, keys' values and nested rows."""
    real_host = socket.gethostname()
    return {
        "generated_utc": NOW.isoformat(),
        "host": HOST, "hostname": real_host, "ip": IP, "pid": 4242,
        "cmdline": f"python {WIN_PATH}\\run.py --token {TOKENS[0]}",
        "error": f"{EXC_TEXT} at {WIN_PATH}",
        "why": (f"{EXC_TEXT}; reached {IP} and {IP6} on {HOST} via {WIN_PATH} and {POSIX_PATH} "
                f"with token={TOKENS[1]} Bearer {TOKENS[2]} mail {EMAIL}"),
        "path": WIN_PATH, "log_dir": POSIX_PATH,
        "rows": [{"verdict": "FAIL", "why": f"OSError: [Errno 13] {POSIX_PATH}",
                  "note": f"Traceback (most recent call last):\n  File \"{POSIX_PATH}\"\n"
                          f"{EXC_TEXT}"} for _ in range(3)],
        "nested": {"deeper": {"evidence": f"{WIN_PATH} {HOST}.contabo.net {IP}"}},
        **(extra or {}),
    }


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake box: every source poisoned, the memecoin limits, evidence and disk roots too."""
    root = tmp_path / "box"
    for _name, rel, *_ in PP.SOURCES:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(_poison()), "utf-8")
    drills = root / "desks/mt5/reports/RECOVERY_DRILLS.json"
    drills.write_text(json.dumps(_poison({
        "drills": [{"drill": "partial_fill", "failure_mode": "partial fill", "verdict": "FAIL",
                    "evidence": "code", "why": f"{EXC_TEXT} {WIN_PATH} {IP}"}],
        "counts": {"PASS": 0, "FAIL": 1}, "per_mode": {
            "partial_fill": {"verdict": "FAIL", "FAIL": 3, "PASS": 0, "recent": ["FAIL"] * 3}}})))
    limits = tmp_path / "limits"
    (limits / "status").mkdir(parents=True)
    work = tmp_path / "disk" / "memecoin-codex-stage-20261020"
    (work / "data" / "state").mkdir(parents=True)
    (limits / "roles.json").write_text(json.dumps({"terminal": {
        "task": "MemecoinPaperTerminal", "cpu_rate": 50, "working_directory": str(work),
        "execute": f"{WIN_PATH}\\python.exe", "arguments": f"--token {TOKENS[0]}"}}))
    (limits / "status" / "terminal.json").write_text(json.dumps({
        "observed_at": int(NOW.timestamp()) - 600, "role": "terminal", "state": "BOUNDED",
        "launcher_pid": 31428, "child_pid": 14996, "cpu_rate": 50, "cpu_percent": 0.5,
        "total_configured_percent": 10, "exit_code": 0, "process_ids": [1, 2],
        "live_authority_changed": False, "host": HOST}))
    fill_at = (NOW - timedelta(hours=2)).isoformat()
    (work / "data" / "state" / "trade_evidence.jsonl").write_text(
        json.dumps({"ts": fill_at, "event": "paper_fill", "mode": "paper", "host": HOST,
                    "wallet": TOKENS[1], "note": f"{EXC_TEXT} {WIN_PATH}"}) + "\n" +
        json.dumps({"ts": fill_at, "event": "quote", "ip": IP}) + "\n")
    backup = tmp_path / "disk" / f"memecoin-backup-{HOST}"
    backup.mkdir(parents=True)
    (backup / "blob.bin").write_bytes(b"x" * 4096)
    monkeypatch.setenv(PP.MEMECOIN_LIMITS_ENV, str(limits))
    monkeypatch.delenv(PP.MEMECOIN_EVIDENCE_ENV, raising=False)
    monkeypatch.setenv(PP.MEMECOIN_DISK_ROOTS_ENV, str(tmp_path / "disk"))
    out = tmp_path / "public"
    monkeypatch.setattr(PP, "OUT_DIR", out)
    monkeypatch.setattr(PP, "MANIFEST", out / "PUBLIC_PROOFS.json")
    monkeypatch.setattr(PP, "REPORTS", root / "desks/mt5/reports")
    return root


def _published(out: Path) -> dict[str, str]:
    return {p.name: p.read_text("utf-8") for p in sorted(out.glob("*.json"))}


def test_no_plant_reaches_any_published_file(box: Path, tmp_path: Path) -> None:
    """THE FENCE: hostname, IP, token, absolute path and exception text reach no file."""
    PP.run(NOW, disk_budget_s=5, cpu_sample_s=0.2, root=box)
    files = _published(tmp_path / "public")
    expected = {Path(p).name for p in PP.published_paths()}
    assert set(files) == expected, f"wrote {sorted(files)}; declared {sorted(expected)}"
    real_host = socket.gethostname()
    for name, text in files.items():
        for plant in PLANTED_WORDS:
            assert plant not in text, f"{name} carries a planted value ({plant[:6]}...)"
        if len(real_host) >= 4:
            assert real_host not in text, f"{name} carries this machine's hostname"
        assert str(box) not in text and str(tmp_path) not in text, f"{name}: absolute path"
        assert not re.search(r"[A-Za-z]:\\\\", text), f"{name}: a Windows path"
        assert not re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text), f"{name}: an IPv4"
        assert R.violations(text) == [], f"{name}: {R.violations(text)}"
        assert len(text.encode()) <= PP.MAX_BYTES + 4096, f"{name} is not small"


def test_sources_are_published_with_their_verdicts_not_absent(box: Path, tmp_path: Path) -> None:
    m = PP.run(NOW, disk_budget_s=5, cpu_sample_s=0.2, root=box)
    by = {r["name"]: r for r in m["proofs"]}
    for name, *_ in PP.SOURCES:
        assert by[name]["status"] in (PP.PUBLISHED, PP.REDUCED), by[name]
        assert by[name]["found_in_source"], f"{name}: the raw source scan saw nothing planted"
    doc = json.loads((tmp_path / "public" / "RECOVERY_DRILLS.json").read_text())
    assert doc["body"]["failing_modes"] == ["partial_fill"]
    assert doc["body"]["per_mode"]["partial_fill"]["FAIL"] == 3
    assert "recent" not in doc["body"]["per_mode"]["partial_fill"]
    assert doc["body"]["drills"][0]["why"].startswith("ValueError")


def test_memecoin_proof_reads_the_cap_and_a_paper_fill(box: Path, tmp_path: Path) -> None:
    PP.run(NOW, disk_budget_s=5, cpu_sample_s=0.2, root=box)
    body = json.loads((tmp_path / "public" / "MEMECOIN_PROOF.json").read_text())["body"]
    assert body["paper_fill"]["verdict"] == "PAPER_FILL_PROVEN", body["paper_fill"]
    assert body["paper_fill"]["fill_rows"] == 1 and body["paper_fill"]["live_rows"] == 0
    assert body["limits"]["verdict"] == "CAP_CONFIGURED_AND_BOUND", body["limits"]
    assert body["limits"]["total_configured_percent"] == 10.0
    assert "owned_by" in body
    disk = json.loads((tmp_path / "public" / "DISK_USAGE.json").read_text())["body"]
    dirs = disk["memecoin_dirs"]
    assert dirs["n_dirs"] == 2 and dirs["complete"] is True
    classes = {d["class"] for d in dirs["dirs"]}
    assert classes == {"in_use", "backup_like"}, dirs["dirs"]


def test_absent_sources_are_said_absent_never_skipped(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "public"
    monkeypatch.setattr(PP, "OUT_DIR", out)
    monkeypatch.setattr(PP, "MANIFEST", out / "PUBLIC_PROOFS.json")
    monkeypatch.setenv(PP.MEMECOIN_LIMITS_ENV, str(tmp_path / "none"))
    monkeypatch.setenv(PP.MEMECOIN_DISK_ROOTS_ENV, str(tmp_path / "none"))
    m = PP.run(NOW, disk_budget_s=1, cpu_sample_s=0.2, root=tmp_path / "empty")
    by = {r["name"]: r for r in m["proofs"]}
    assert all(by[n]["status"] == PP.ABSENT for n, *_ in PP.SOURCES)
    meme = json.loads((out / "MEMECOIN_PROOF.json").read_text())["body"]
    assert meme["verdict"] == PP.UNMEASURED and "Memecoin thread" in meme["owned_by"]


def test_redactor_reduces_errors_to_their_type_and_keeps_repo_paths() -> None:
    proj, removed = R.public_fields({
        "error": "KeyError: 'secret-ish'", "errors": ["OSError: [Errno 2] /tmp/x"],
        "path": str(ROOT / "desks" / "mt5" / "reports" / "X.json"), "login": 5551234,
        "sha": "bb527d650cfa11b0f152f7915951d8d6c188b12e"})
    assert proj == {"error": "KeyError", "errors": ["OSError"],
                    "path": "desks/mt5/reports/X.json",
                    "sha": "bb527d650cfa11b0f152f7915951d8d6c188b12e"}
    assert removed["dropped_keys"] == 1
    assert R.public_text("[WinError 5] Access is denied: 'C:\\\\x'") == "[WinError 5]"
    assert R.violations("desks/mt5/reports/public/ALPHA_CAPTURE_ALLOCATION_INTEL.json") == []


def test_every_published_path_is_listed_by_the_sync_and_not_ignored() -> None:
    src = (DESK / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")
    start = src.index("$reportPaths = @(")
    block = src[start:src.index("\n)", start)]
    listed = set(re.findall(r'"(desks/mt5/reports/public/[^"]+)"', block))
    assert listed == set(PP.published_paths())
    for rel in PP.published_paths():
        r = subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=ROOT, check=False)
        assert r.returncode != 0, f"{rel} is ignored: the sync would stage nothing"


def test_it_is_a_core_always_run_leg_ahead_of_publication() -> None:
    import hourly_cycle as hc  # type: ignore[import-not-found,unused-ignore]

    from libs.ops import leg_rotation as LR
    from libs.research import layers
    assert "public_proofs" in hc.CORE_LEGS and "public_proofs" in LR.ALWAYS_RUN
    assert layers.LEG_LAYER["public_proofs"] == "meta"
    text = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert text.index('_costed("public_proofs"') < text.index('_costed("publish_state"')


def test_recovery_drills_carry_a_per_mode_tally(monkeypatch: pytest.MonkeyPatch,
                                                tmp_path: Path) -> None:
    for attr in ("CHAOS", "OPS", "OFFSITE", "REBOOT", "DESK_STALE", "PIT", "FORECAST",
                 "REPLAY", "RELEASE", "LIMITS", "ACCOUNT", "POSITIONS"):
        monkeypatch.setattr(rd, attr, tmp_path / f"{attr}.json")
    monkeypatch.setattr(rd, "STALL", (tmp_path / "stall.json",))
    first = rd.build(NOW)
    second = rd.build(NOW + timedelta(hours=1), prior=first)
    assert {"partial_fill", "out_of_order"} <= set(second["failing_modes"])
    pf = second["per_mode"]["partial_fill"]
    assert pf["FAIL"] == 2 and pf["PASS"] == 0 and pf["streak"] == 2 and pf["passes"] == 2
    assert pf["last_fail_utc"] == (NOW + timedelta(hours=1)).isoformat(timespec="seconds")
    assert len(second["per_mode"]) == second["n"]
    long = first
    for i in range(rd.TALLY_WINDOW + 5):
        long = rd.build(NOW + timedelta(hours=i), prior=long)
    assert long["per_mode"]["partial_fill"]["passes"] == rd.TALLY_WINDOW
