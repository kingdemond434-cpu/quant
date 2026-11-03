"""The release-lag alarm: GREEN on adopted or fresh releases, RED BEHIND past 3h naming the guard,
RED NO_GREEN_RELEASE past 24h of unreleased LIVE code, UNMEASURED (never GREEN) on no reading,
and the heartbeat pages it once per new failure / changed kind / day -- not every 5 minutes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import box_heartbeat as hb  # noqa: E402
import release_lag as rl  # noqa: E402

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC).timestamp()
LIVE = rl.LIVE_BRANCH


class Repo:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir()
        self.git("init", "-q", "-b", LIVE)
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "tag.gpgsign", "false")

    def git(self, *args: str, at: float | None = None) -> str:
        env = dict(os.environ)
        if at is not None:
            stamp = f"@{int(at)} +0000"
            env.update(GIT_COMMITTER_DATE=stamp, GIT_AUTHOR_DATE=stamp)
        r = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True,
                           env=env, check=True)
        return r.stdout.strip()

    def commit(self, rel: str, at: float) -> str:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{rel} {at}\n")
        self.git("add", rel)
        self.git("commit", "-q", "-m", rel, at=at)
        return self.git("rev-parse", "HEAD")

    def ref(self, name: str, sha: str) -> None:
        self.git("update-ref", name, sha)

    def tag(self, sha: str, at: float) -> str:
        name = f"release/{datetime.fromtimestamp(at, UTC):%Y%m%dT%H%M%SZ}-{sha[:12]}"
        self.git("tag", "-a", "-m", "green", name, sha, at=at)
        return name


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    repo = Repo(tmp_path / "repo")
    rel = tmp_path / "RELEASE.json"
    for name, path in (("ADOPT_GUARD", tmp_path / "ADOPT_GUARD.json"),
                       ("ADOPT_HEARTBEAT", tmp_path / "ADOPTION_HEARTBEAT.json"),
                       ("ADOPT_LOG", tmp_path / "adopt_and_seal.log"),
                       ("RELEASE_JSON", rel)):
        monkeypatch.setattr(rl, name, path)
    return {"repo": repo, "rel": rel, "tmp": tmp_path}


def _seal(box: dict[str, Any], sha: str) -> None:
    box["rel"].write_text(json.dumps({"code_sha": sha, "generated_utc": "2026-10-29T14:28:39Z"}))


def _measure(box: dict[str, Any], prev: dict[str, Any] | None = None,
             now: float = NOW) -> dict[str, Any]:
    return rl.measure(now, root=box["repo"].root, prev=prev, release_json=box["rel"])


def test_green_when_the_box_runs_the_newest_release(box: dict[str, Any]) -> None:
    r = box["repo"]
    a = r.commit("lib.py", NOW - 50 * 3600)
    r.tag(a, NOW - 49 * 3600)
    r.ref("refs/quant/release-gate/production", a)
    # box state on top of the release: not code, so not a CI outage
    tip = r.commit("desks/mt5/reports/x.json", NOW - 600)
    r.ref("refs/quant/release-gate/tip", tip)
    _seal(box, tip)
    d = _measure(box)
    assert d["verdict"] == "GREEN" and d["releases_behind"] == 0, d
    assert d["adopted"]["source"] == "RELEASE.json code_sha"
    assert d["green_at"] == d["measured_at"]


def test_green_while_a_new_release_is_inside_its_window(box: dict[str, Any]) -> None:
    r = box["repo"]
    a = r.commit("lib.py", NOW - 10 * 3600)
    _seal(box, a)
    b = r.commit("lib2.py", NOW - 2 * 3600)
    r.tag(b, NOW - 1 * 3600)
    r.ref("refs/quant/release-gate/production", b)
    r.ref("refs/quant/release-gate/tip", b)
    d = _measure(box)
    assert d["verdict"] == "GREEN", d
    assert d["adopted"]["contains_newest_green"] is False and d["releases_behind"] == 1


def test_behind_past_3h_names_the_guard_and_the_count(box: dict[str, Any]) -> None:
    r = box["repo"]
    a = r.commit("lib.py", NOW - 30 * 3600)
    _seal(box, a)
    b = r.commit("lib2.py", NOW - 20 * 3600)
    r.tag(b, NOW - 19 * 3600)
    c = r.commit("lib3.py", NOW - 6 * 3600)
    r.tag(c, NOW - 5 * 3600)
    r.ref("refs/remotes/origin/production", c)
    r.ref(f"refs/remotes/origin/{LIVE}", c)
    rl.ADOPT_GUARD.write_text(json.dumps({"at": "2026-11-03T11:12:00Z", "step": "pre",
                                          "decision": "HOLD_UNAUDITED",
                                          "reason": "3 governed path(s) carry no CLEAR"}))
    rl.ADOPT_LOG.write_text("2026-11-03 11:12:01Z adopt-and-seal: adopt guard HOLD\n")
    d = _measure(box)
    assert d["verdict"] == "RED" and d["kind"] == "BEHIND", d
    assert d["releases_behind"] == 2
    assert "HOLD_UNAUDITED" in d["reason"] and "3 governed path(s)" in d["reason"]
    assert d["context"]["log_tail"] == ["2026-11-03 11:12:01Z adopt-and-seal: adopt guard HOLD"]
    assert d["green_at"] is None


def test_no_green_release_when_live_code_waits_over_24h(box: dict[str, Any]) -> None:
    r = box["repo"]
    a = r.commit("lib.py", NOW - 100 * 3600)
    r.tag(a, NOW - 99 * 3600)
    r.ref("refs/quant/release-gate/production", a)
    r.commit("new_code.py", NOW - 30 * 3600)           # merged, never released
    tip = r.commit("desks/mt5/reports/x.json", NOW - 300)
    r.ref("refs/quant/release-gate/tip", tip)
    _seal(box, tip)                                    # fully adopted -- CI is what is dark
    d = _measure(box, prev={"green_at": "2026-11-01T00:00:00+00:00"})
    assert d["verdict"] == "RED" and d["kind"] == "NO_GREEN_RELEASE", d
    assert d["unreleased_code_paths"] == 1 and d["unreleased_age_h"] == pytest.approx(30, abs=0.1)
    assert d["green_at"] == "2026-11-01T00:00:00+00:00"   # carried through RED


def test_unreleased_code_inside_24h_stays_green(box: dict[str, Any]) -> None:
    r = box["repo"]
    a = r.commit("lib.py", NOW - 100 * 3600)
    r.tag(a, NOW - 99 * 3600)
    r.ref("refs/quant/release-gate/production", a)
    tip = r.commit("new_code.py", NOW - 5 * 3600)
    r.ref("refs/quant/release-gate/tip", tip)
    _seal(box, a)
    assert _measure(box)["verdict"] == "GREEN"


def test_untagged_release_is_aged_from_first_sight(box: dict[str, Any]) -> None:
    r = box["repo"]
    a = r.commit("lib.py", NOW - 100 * 3600)
    _seal(box, a)
    b = r.commit("lib2.py", NOW - 90 * 3600)   # old commit, promoted with no local tag
    r.ref("refs/quant/release-gate/production", b)
    r.ref("refs/quant/release-gate/tip", b)
    d1 = _measure(box)
    assert d1["verdict"] == "GREEN" and d1["newest_green"]["green_since_basis"] == "first seen"
    d2 = _measure(box, prev=d1, now=NOW + 4 * 3600)
    assert d2["verdict"] == "RED" and d2["kind"] == "BEHIND"


def test_no_release_at_all_is_red_and_unreadable_identity_is_unmeasured(
        box: dict[str, Any]) -> None:
    r = box["repo"]
    a = r.commit("lib.py", NOW - 3600)
    r.ref("refs/quant/release-gate/tip", a)
    _seal(box, a)
    assert _measure(box)["kind"] == "NO_GREEN_RELEASE"
    r.git("update-ref", "-d", "refs/quant/release-gate/tip")
    d = _measure(box)
    assert d["verdict"] == "UNMEASURED" and d["kind"] == "UNMEASURED"


def test_missing_or_stale_report_reads_unmeasured_never_green(tmp_path: Path) -> None:
    c = rl.check(NOW, tmp_path / "RELEASE_LAG.json")
    assert c["verdict"] == "UNMEASURED" and c["fail"] is True
    p = tmp_path / "RELEASE_LAG.json"
    p.write_text(json.dumps({"verdict": "GREEN", "kind": "GREEN",
                             "measured_at": rl._iso(NOW - 3 * 3600)}))
    c = rl.check(NOW, p)
    assert c["verdict"] == "UNMEASURED" and c["fail"] is True
    p.write_text(json.dumps({"verdict": "GREEN", "kind": "GREEN", "measured_at": rl._iso(NOW)}))
    assert rl.check(NOW, p)["fail"] is False
    p.write_text("{not json")
    assert rl.check(NOW, p)["verdict"] == "UNMEASURED"


def test_refresh_never_raises_and_throttles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                            ) -> None:
    out = tmp_path / "RELEASE_LAG.json"

    def boom(*a: Any, **k: Any) -> dict[str, Any]:
        raise RuntimeError("x")
    monkeypatch.setattr(rl, "measure", boom)
    d = rl.refresh(NOW, out=out)
    assert d["verdict"] == "UNMEASURED" and json.loads(out.read_text())["verdict"] == "UNMEASURED"
    calls: list[float] = []
    monkeypatch.setattr(rl, "measure", lambda t, **k: calls.append(t) or rl._finish(
        {"measured_at": rl._iso(t), "problems": []}, "GREEN", t, {}))
    rl.refresh(NOW + 60, out=out)
    assert calls == []                              # inside REMEASURE_MIN: reuse
    rl.refresh(NOW + 20 * 60, out=out)
    assert len(calls) == 1


def _lag(kind: str) -> dict[str, Any]:
    return {"verdict": "GREEN" if kind == "GREEN" else ("UNMEASURED" if kind == "UNMEASURED"
                                                         else "RED"),
            "kind": kind, "reason": kind, "fail": kind != "GREEN"}


def test_heartbeat_pages_new_failure_changed_kind_and_daily_only(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "BOX_HEARTBEAT.json"
    sent: list[str] = []
    import libs.ops.alert_channels as ac
    monkeypatch.setattr(ac, "send_all", lambda t, b, **k: sent.append(b) or {"status": "ok"})
    sec = (tmp_path / "absent.json",)

    def beat(kind: str, t: float) -> dict[str, Any]:
        lag = _lag(kind)
        failing = ["adopt_lag"] if lag["fail"] else []
        reading = {"at": rl._iso(t), "checks": {"adopt_lag": lag}, "failing": failing,
                   "verdict": "FAIL" if failing else "OK"}
        return hb.run(out=out, secrets=sec, reading=reading, now=t)

    beat("GREEN", NOW)
    assert sent == []
    beat("BEHIND", NOW + 300)
    assert len(sent) == 1 and "BEHIND" in sent[0]
    for i in range(2, 30):                           # every 5 min for ~2.5h: silent
        beat("BEHIND", NOW + 300 * i)
    assert len(sent) == 1
    beat("BEHIND+NO_GREEN_RELEASE", NOW + 3 * 3600)  # the reason changed: page
    assert len(sent) == 2
    beat("BEHIND+NO_GREEN_RELEASE", NOW + 20 * 3600)
    assert len(sent) == 2
    beat("BEHIND+NO_GREEN_RELEASE", NOW + 27 * 3600 + 1)  # a day since the last page
    assert len(sent) == 3
    beat("BEHIND+NO_GREEN_RELEASE", NOW + 27 * 3600 + 301)
    assert len(sent) == 3
    beat("GREEN", NOW + 28 * 3600)
    assert json.loads(out.read_text())["adopt_lag_paged"] is None
    beat("BEHIND", NOW + 29 * 3600)                  # a fresh failure after recovery pages
    assert len(sent) == 4


def test_heartbeat_measure_fails_on_an_unmeasured_lag(monkeypatch: pytest.MonkeyPatch,
                                                      tmp_path: Path) -> None:
    monkeypatch.setattr(rl, "OUT", tmp_path / "RELEASE_LAG.json")
    monkeypatch.setattr(rl, "refresh", lambda now: {})
    c = rl.check(time.time(), tmp_path / "RELEASE_LAG.json")
    assert c["fail"] and c["verdict"] == "UNMEASURED"
    r = hb.measure(NOW, research={"age_days": 0.01}, disk_free_gb=50,
                   adopt_lag=c)
    assert "adopt_lag" in r["failing"]


def test_contract_reads_green_at_not_mtime(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "ops"))
    import organ_contract as oc
    rel = "desks/mt5/reports/RELEASE_LAG.json"
    assert oc.CONTRACTS["MT5-AdoptRelease"][0] == rel
    assert oc.INTERNAL_STAMPS[rel] == "green_at"
    p = tmp_path / rel
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"verdict": "RED", "green_at": None}))
    assert oc.artifact_age_min(rel, root=tmp_path) is None          # ABSENT, never OK
    now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    p.write_text(json.dumps({"verdict": "RED", "green_at": "2026-11-03T09:00:00+00:00"}))
    assert oc.artifact_age_min(rel, now=now, root=tmp_path) == pytest.approx(180)
