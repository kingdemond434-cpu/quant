#!/usr/bin/env python3
"""THE SAFE TEST ENVIRONMENT: the whole protected-PR pipeline, end to end, against a fake GitHub.

Nothing here touches GitHub, the box or any real key. A throwaway Ed25519 key is made in a temp
folder, the REAL root digest of this checkout is pinned there, the REAL authority decides and
signs, and the REAL box gate (audit_gate.run(box=True)) verifies, sends its veto notice through
a fake channel, waits 24 h on a simulated clock and merges -- into the fake GitHub, which records
the merge call (pinned to the head sha) instead of making it. tests/ops/test_release_authority.py
runs every adversarial case through this; `python ops/release/authority/sandbox.py` prints the
happy path and the fail-closed cases as a transcript.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import sys
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
H1, H2 = "1" * 40, "2" * 40
BASE_SHA = "b" * 40
T0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Clock:
    def __init__(self, t: datetime) -> None:
        self.t = t

    def advance(self, **kw: float) -> None:
        self.t += timedelta(**kw)


def fake_datetime(clock: Clock) -> type:
    class _DT(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            return clock.t if tz else clock.t.replace(tzinfo=None)

    return _DT


class FakeGitHub:
    """A `gh api` stand-in for one PR (#41) into LIVE."""

    def __init__(self, ag: Any, files: tuple[str, ...], head: str = H1) -> None:
        self.ag = ag
        self.pr = {
            "number": 41, "state": "open", "draft": False,
            "head": {"sha": head, "ref": "claude/x", "repo": {"full_name": "o/r"}},
            "base": {"ref": ag.LIVE, "sha": BASE_SHA},
            "labels": [], "changed_files": len(files),
            "updated_at": "2026-11-04T00:00:00Z",
        }  # fmt: skip
        self.files = [{"filename": f, "status": "modified", "additions": 1, "deletions": 0}
                      for f in files]  # fmt: skip
        self.comments: list[dict[str, Any]] = []
        self.board = [{
            "body": ag.ACTIVATE, "created_at": "2026-10-29T00:00:00Z",
            "updated_at": "2026-10-29T00:00:00Z", "author_association": "OWNER",
            "performed_via_github_app": None,
        }]  # fmt: skip
        self.conclusion = dict.fromkeys((*ag.GATING_JOBS, *ag.AUTO_JOBS), "success")
        self.trusted_eval: str | None = "success"
        self.writes: list[tuple[str, str, dict[str, Any]]] = []

    @property
    def head(self) -> str:
        return str(self.pr["head"]["sha"])

    def runs(self) -> list[dict[str, Any]]:
        out = []
        for i, (name, concl) in enumerate(sorted(self.conclusion.items()), start=100):
            wf = self.ag.WORKFLOW_OF[name]
            sid = 1 if wf.endswith("ci.yml") else 2
            out.append({"id": i, "name": name, "status": "completed", "conclusion": concl,
                        "app": {"slug": "github-actions"}, "check_suite": {"id": sid},
                        "started_at": "2026-11-04T00:00:00Z"})  # fmt: skip
        return out

    def __call__(self, *args: str, data: Any = None) -> Any:
        path = args[0]
        if "-X" in args:
            self.writes.append((args[args.index("-X") + 1], path, dict(data or {})))
            return None
        if f"/issues/{self.ag.APPROVALS_ISSUE}/comments" in path:
            return [self.board]
        if path.endswith("/comments?per_page=100"):
            return [self.comments]
        if "/annotations" in path:
            return []
        if "/check-runs" in path:
            return (
                [{"check_runs": self.runs()}] if "--slurp" in args else {"check_runs": self.runs()}
            )
        if "trusted-eval.yml/runs" in path:
            if self.trusted_eval is None:
                return {"workflow_runs": []}
            return {
                "workflow_runs": [
                    {
                        "id": 9,
                        "display_title": f"trusted-eval 41 {self.head}",
                        "path": ".github/workflows/trusted-eval.yml",
                        "head_branch": self.ag.LIVE,
                        "event": "pull_request_target",
                        "status": "completed",
                        "conclusion": self.trusted_eval,
                        "created_at": "2026-11-04T00:00:00Z",
                    }
                ]
            }
        if "/actions/runs?check_suite_id=" in path:
            sid = int(path.split("check_suite_id=")[1].split("&")[0])
            wf = {1: ".github/workflows/ci.yml", 2: ".github/workflows/release-gates.yml"}[sid]
            return {"workflow_runs": [{"id": sid, "path": wf, "head_sha": self.head,
                                       "event": "pull_request",
                                       "pull_requests": [{"number": 41}]}]}  # fmt: skip
        if "/actions/runs/" in path and "/jobs" in path:
            return [{"jobs": [{"id": r["id"]} for r in self.runs()]}]
        if "/files?" in path:
            return [self.files]
        if "/pulls?" in path:
            return [[{"number": 41, "head": {"sha": self.head}}]]
        if "/actions/runs?head_sha=" in path or "/commits?sha=" in path:
            return {"workflow_runs": []} if "runs" in path else []
        return self.pr

    def merges(self) -> list[dict[str, Any]]:
        return [d for (_m, p, d) in self.writes if p.endswith("/merge")]


class Sandbox:
    """Wires the real gate and the real authority to the fake GitHub, a temp key and a clock."""

    def __init__(self, tmp: Path, files: tuple[str, ...] = (".github/workflows/ci.yml",)) -> None:
        self.tmp = tmp
        self.ag = _load("audit_gate", ROOT / ".github" / "scripts" / "audit_gate.py")
        self.auth = _load("authority_service", HERE / "authority.py")
        self.att = self.auth.att
        self.gh = FakeGitHub(self.ag, files)
        self.clock = Clock(T0)
        self.notices: list[str] = []
        self.deliver = True
        self.folder = tmp / "attestations"
        self.folder.mkdir()
        self.registry = tmp / "registry.jsonl"
        self.registry.write_text("", encoding="utf-8")
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        key = ed25519.Ed25519PrivateKey.generate()
        self.key_pem = tmp / "authority.pem"
        self.key_pem.write_bytes(key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))  # fmt: skip
        self.pub = tmp / "authority.pub"
        raw = key.public_key().public_bytes(serialization.Encoding.Raw,
                                            serialization.PublicFormat.Raw)  # fmt: skip
        import base64

        self.pub.write_text(base64.b64encode(raw).decode(), encoding="utf-8")
        self.policy = self.auth.pol.load_policy()
        self.digest = self.auth.tree_digest("HEAD", self.policy)
        self.pin = tmp / "ROOT_PIN.json"
        self.pin.write_text(json.dumps({"digest": self.digest}), encoding="utf-8")
        self.base_text: dict[str, str] = {}
        self.head_text: dict[str, str] = {}

    @contextlib.contextmanager
    def wired(self) -> Iterator[None]:
        ag = self.ag
        names = ("_gh", "_git", "patch_id", "up_to_date", "referenced_by_code", "datetime",
                 "run_notify")  # fmt: skip
        saved = {k: getattr(ag, k) for k in names}
        env = {
            ag.REGISTRY_ENV: str(self.registry),
            ag.AUTHORITY_PUBKEY_ENV: str(self.pub),
            ag.AUTHORITY_DIR_ENV: str(self.folder),
            ag.AUTHORITY_PIN_ENV: str(self.pin),
        }
        old_env = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        saved_bytes = self.auth._git_bytes

        def git_bytes(*args: str) -> bytes | None:
            if args and args[0] == "show":
                rev, _, name = args[1].partition(":")
                src = self.head_text if rev == self.gh.head else self.base_text
                t = src.get(name)
                return t.encode() if t is not None else None
            return saved_bytes(*args)

        def notify(title: str, body: str) -> bool:
            self.notices.append(title)
            return self.deliver

        ag._gh = self.gh
        ag._git = lambda *a: ""
        ag.patch_id = lambda base, sha: f"patch-of-{sha[:4]}"
        ag.up_to_date = lambda base, head: (True, "up to date")
        ag.referenced_by_code = lambda base, n: False
        ag.datetime = fake_datetime(self.clock)
        ag.run_notify = notify
        self.auth._git_bytes = git_bytes
        try:
            yield
        finally:
            for k, v in saved.items():
                setattr(ag, k, v)
            self.auth._git_bytes = saved_bytes
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def authority(self) -> tuple[str, list[str]]:
        """One authority pass over #41: decide, and sign CLEAR/HOLD into the folder."""
        with self.wired():
            f = self.auth.facts(self.ag, "o/r", 41, self.ag.LIVE, self.policy)
            verdict, reasons = self.auth.pol.decide(f)
            if verdict in ("CLEAR", "HOLD"):
                key, kid = self.att.load_private(self.key_pem)
                env = self.auth.issue(f, verdict, reasons, repo="o/r", digest=self.digest,
                                      key=key, kid=kid, ttl_h=48, now=self.clock.t)  # fmt: skip
                self.auth.write(self.folder, env, 41, f["head"], verdict, self.digest)
        return verdict, reasons

    def gate(self) -> int:
        with self.wired():
            return int(self.ag.run("o/r", 41, self.ag.LIVE, 0.0, box=True))


def demo() -> int:
    lines: list[str] = []
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(Path(d))
        v, why = sb.authority()
        lines.append(f"authority: {v} -- {'; '.join(why)}")
        sb.gate()
        lines.append(f"gate t+0h: notices={len(sb.notices)} merges={len(sb.gh.merges())}")
        sb.clock.advance(hours=23)
        sb.gate()
        lines.append(f"gate t+23h: merges={len(sb.gh.merges())} (veto window still open)")
        sb.clock.advance(hours=1, minutes=1)
        sb.gate()
        m = sb.gh.merges()
        lines.append(f"gate t+24h: merges={len(m)} pinned_sha={m[0]['sha'][:9] if m else None} "
                     f"title={m[0]['commit_title'] if m else None!r}")  # fmt: skip
        ok = len(m) == 1 and m[0]["sha"] == H1
    print("\n".join(lines))
    print("DEMO", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(demo())
