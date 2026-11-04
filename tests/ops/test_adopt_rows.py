"""Merge-time ADOPT_CLEARS rows (ops/release/adopt_rows.py, R2f): written only from a verdict the
box can verify again, self-authenticating, and re-verified by the adopt guard."""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.ops import adopt_guard as ag

ROOT = Path(__file__).resolve().parents[2]
QUIET = datetime(2026, 10, 28, 18, 0, tzinfo=UTC)
LIVE = "claude/llm-auto-upgrade-verify-gcjac3"


def _load(name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ar = _load("_t_adopt_rows", "ops/release/adopt_rows.py")
att = _load("_t_attestation", "ops/release/authority/attestation.py")


def _g(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _write(repo: Path, rel: str, text: str) -> None:
    f = repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def _commit(repo: Path, msg: str) -> str:
    _g(repo, "add", "-A")
    _g(repo, "commit", "-q", "-m", msg)
    return _g(repo, "rev-parse", "HEAD")


class Box:
    """A bare 'origin', a work clone that makes PR merges on LIVE, and a box clone."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.origin = tmp / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", LIVE, str(self.origin)], check=True)
        self.work = tmp / "work"
        subprocess.run(
            ["git", "clone", "-q", str(self.origin), str(self.work)],
            check=True,
            capture_output=True,
        )
        for k, v in (("user.email", "t@t"), ("user.name", "t")):
            _g(self.work, "config", k, v)
        _g(self.work, "checkout", "-q", "-b", LIVE)
        _write(self.work, "libs/x.py", "X = 1\n")
        _write(self.work, "libs/y.py", "Y = 1\n")
        _write(self.work, "desks/mt5/data/sleeves.json", "{}\n")
        base = _commit(self.work, "base")
        _write(self.work, "desks/mt5/data/RELEASE.json", json.dumps({"code_sha": base}) + "\n")
        _commit(self.work, "seal")
        _g(self.work, "push", "-q", "origin", LIVE)
        self.box = tmp / "box"
        subprocess.run(
            ["git", "clone", "-q", "-b", LIVE, str(self.origin), str(self.box)],
            check=True,
            capture_output=True,
        )
        for k, v in (("user.email", "b@b"), ("user.name", "b")):
            _g(self.box, "config", k, v)
        self.registry = tmp / "registry.jsonl"
        self.registry.write_text("")
        self.env: dict[str, str] = {ar.REGISTRY_ENV: str(self.registry)}

    def pr(
        self,
        n: int,
        files: dict[str, str],
        *,
        also_live: dict[str, str] | None = None,
        title: str | None = None,
    ) -> tuple[str, str]:
        """(merge sha, head sha) of PR #n merged into LIVE with a merge commit."""
        _g(self.work, "checkout", "-q", "-b", f"pr{n}", LIVE)
        for rel, text in files.items():
            _write(self.work, rel, text)
        head = _commit(self.work, f"pr {n}")
        _g(self.work, "checkout", "-q", LIVE)
        if also_live:
            for rel, text in also_live.items():
                _write(self.work, rel, text)
            _commit(self.work, "live moved")
        _g(
            self.work,
            "merge",
            "-q",
            "--no-ff",
            "-X",
            "theirs",
            f"pr{n}",
            "-m",
            title or f"Merge pull request #{n} from x/pr{n}",
        )
        merge = _g(self.work, "rev-parse", "HEAD")
        _g(self.work, "push", "-q", "origin", LIVE)
        _g(self.box, "fetch", "-q", "origin")
        return merge, head

    def registry_row(self, pr: int, sha: str, verdict: str = "CLEAR") -> None:
        with self.registry.open("a") as f:
            f.write(
                json.dumps(
                    {"pr": pr, "sha": sha, "verdict": verdict, "at": datetime.now(UTC).isoformat()}
                )
                + "\n"
            )

    def authority(self) -> tuple[Any, str]:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        key = ed25519.Ed25519PrivateKey.generate()
        raw = key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        pub = self.tmp / "authority.pub"
        pub.write_text(base64.b64encode(raw).decode())
        pin = self.tmp / "ROOT_PIN.json"
        pin.write_text(json.dumps({"digest": "d" * 64}))
        folder = self.tmp / "attestations"
        folder.mkdir()
        self.env.update(
            {ar.PUBKEY_ENV: str(pub), ar.PIN_ENV: str(pin), ar.ATTEST_DIR_ENV: str(folder)}
        )
        return key, att.key_id(raw)

    def attest(
        self,
        key: Any,
        kid: str,
        pr: int,
        head: str,
        verdict: str = "CLEAR",
        digest: str = "d" * 64,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        st = att.statement(
            repo=ar.REPO,
            pr=pr,
            head_sha=head,
            base_sha="0" * 40,
            patch_id="p",
            tier="AUTO",
            verdict=verdict,
            policy_digest=digest,
            evidence={},
            reasons=[],
            kid=kid,
            now=now or datetime.now(UTC) - timedelta(minutes=1),
        )
        env = att.sign(st, key, kid)
        n = len(list(Path(self.env[ar.ATTEST_DIR_ENV]).glob(f"pr{pr}-*.json")))
        (Path(self.env[ar.ATTEST_DIR_ENV]) / f"pr{pr}-{n}.json").write_text(json.dumps(env))
        return env

    def rows(self) -> list[dict[str, Any]]:
        git = ar.git_in(self.box)
        return ar.pending(
            git,
            f"refs/remotes/origin/{LIVE}",
            authority=ar.Authority.load(self.box, self.env),
            registry_path=self.env.get(ar.REGISTRY_ENV),
        )


@pytest.fixture
def box(tmp_path: Path) -> Box:
    b = Box(tmp_path)
    # the box tree must carry the verifier modules the guard loads from its own root
    for rel in ("ops/release/adopt_rows.py", "ops/release/authority/attestation.py"):
        f = b.box / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes((ROOT / rel).read_bytes())
    return b


# ------------------------------------------------------------------------------- what is written
def test_no_verified_verdict_means_no_row(box: Box) -> None:
    box.pr(7, {"libs/x.py": "X = 2\n"}, title="Merge #7 (AUTO tier, no comment: AUTO tier)")
    assert box.rows() == []


def test_a_registry_clear_of_the_exact_head_writes_the_heads_blobs(box: Box) -> None:
    merge, head = box.pr(7, {"libs/x.py": "X = 2\n"})
    box.registry_row(7, head)
    (row,) = box.rows()
    assert row["commit"] == merge and row["by"] == ar.BY
    assert row["source"] == {"kind": "registry", "pr": 7, "head": head, "at": row["source"]["at"]}
    assert row["paths"] == {"libs/x.py": _g(box.box, "rev-parse", f"{head}:libs/x.py")}
    ag.parse_clears(json.dumps(row))  # the guard's own parser takes it


@pytest.mark.parametrize("last", ["HOLD", "OTHER_SHA"])
def test_a_registry_hold_or_another_head_writes_nothing(box: Box, last: str) -> None:
    _merge, head = box.pr(7, {"libs/x.py": "X = 2\n"})
    box.registry_row(7, head)
    box.registry_row(
        7, "f" * 40 if last == "OTHER_SHA" else head, "CLEAR" if last == "OTHER_SHA" else "HOLD"
    )
    assert box.rows() == []


def test_a_path_the_merge_changed_beyond_the_cleared_head_is_left_out(box: Box) -> None:
    merge, head = box.pr(7, {"libs/x.py": "X = 2\n", "libs/y.py": "Y = 2\n"})
    # a merge whose result differs from the cleared head in y.py (a hand-resolved conflict)
    w = box.work
    _g(w, "checkout", "-q", "--detach", merge)
    _write(w, "libs/y.py", "Y = 99\n")
    _g(w, "add", "-A")
    tree = _g(w, "write-tree")
    odd = _g(w, "commit-tree", tree, "-p", f"{merge}^1", "-p", head, "-m", "Merge #7")
    _g(w, "checkout", "-q", LIVE)
    paths = ar.row_paths(ar.git_in(w), odd, head)
    assert paths == {"libs/x.py": _g(w, "rev-parse", f"{head}:libs/x.py")}


def test_an_authority_clear_writes_a_row_carrying_its_signed_envelope(box: Box) -> None:
    key, kid = box.authority()
    merge, head = box.pr(9, {"libs/x.py": "X = 9\n"}, title="Merge #9 (AUTO tier, no comment: x)")
    env = box.attest(key, kid, 9, head)
    (row,) = box.rows()
    assert row["source"]["kind"] == "authority" and row["source"]["attestation"] == env
    assert row["commit"] == merge


def test_any_verified_authority_hold_blocks_the_row(box: Box) -> None:
    key, kid = box.authority()
    _merge, head = box.pr(9, {"libs/x.py": "X = 9\n"})
    box.attest(key, kid, 9, head)
    box.attest(key, kid, 9, head, verdict="HOLD")
    assert box.rows() == []


def test_an_attestation_under_another_root_policy_writes_nothing(box: Box) -> None:
    key, kid = box.authority()
    _merge, head = box.pr(9, {"libs/x.py": "X = 9\n"})
    box.attest(key, kid, 9, head, digest="e" * 64)
    assert box.rows() == []


def test_the_kill_file_turns_the_authority_source_off(box: Box) -> None:
    key, kid = box.authority()
    _merge, head = box.pr(9, {"libs/x.py": "X = 9\n"})
    box.attest(key, kid, 9, head)
    (Path(box.env[ar.ATTEST_DIR_ENV]) / ar.KILL).write_text("")
    assert box.rows() == []


# --------------------------------------------------------------------------- verification
def _verify(box: Box, row: dict[str, Any]) -> tuple[bool, str]:
    return ar.verify_row(
        ar.git_in(box.box),
        row,
        authority=ar.Authority.load(box.box, box.env),
        registry_path=box.env.get(ar.REGISTRY_ENV),
    )


def test_a_forged_blob_does_not_verify(box: Box) -> None:
    _merge, head = box.pr(7, {"libs/x.py": "X = 2\n"})
    box.registry_row(7, head)
    (row,) = box.rows()
    row["paths"]["libs/x.py"] = "a" * 40
    assert _verify(box, row)[0] is False
    row2 = json.loads(json.dumps(box.rows()[0]))
    row2["paths"]["libs/y.py"] = _g(box.box, "rev-parse", f"{head}:libs/y.py")  # not the PR's
    assert _verify(box, row2)[0] is False


def test_a_row_pointing_at_another_head_does_not_verify(box: Box) -> None:
    _m1, head1 = box.pr(7, {"libs/x.py": "X = 2\n"})
    m2, _head2 = box.pr(8, {"libs/y.py": "Y = 2\n"})
    box.registry_row(7, head1)
    (row,) = box.rows()
    row["commit"] = m2  # the CLEAR of #7 carried onto #8's merge
    assert _verify(box, row)[0] is False


def test_a_tampered_attestation_does_not_verify(box: Box) -> None:
    key, kid = box.authority()
    _merge, head = box.pr(9, {"libs/x.py": "X = 9\n"})
    box.attest(key, kid, 9, head)
    (row,) = box.rows()
    st = json.loads(row["source"]["attestation"]["statement"])
    st["pr"] = 10
    row["source"]["attestation"]["statement"] = json.dumps(
        st, sort_keys=True, separators=(",", ":")
    )
    assert _verify(box, row)[0] is False


def test_a_registry_hold_after_the_row_revokes_it(box: Box) -> None:
    _merge, head = box.pr(7, {"libs/x.py": "X = 2\n"})
    box.registry_row(7, head)
    (row,) = box.rows()
    assert _verify(box, row)[0] is True
    box.registry_row(7, head, "HOLD")
    assert _verify(box, row)[0] is False


# ----------------------------------------------------------------------------- the sweep
def test_the_sweep_appends_once_as_a_data_only_commit(box: Box) -> None:
    _merge, head = box.pr(7, {"libs/x.py": "X = 2\n"})
    box.registry_row(7, head)
    tip = _g(box.box, "rev-parse", f"origin/{LIVE}")
    assert ar.sweep(box.box, apply=True, env=box.env) == 0
    _g(box.box, "fetch", "-q", "origin")
    new = _g(box.box, "rev-parse", f"origin/{LIVE}")
    assert _g(box.box, "rev-parse", f"{new}^") == tip
    assert _g(box.box, "diff", "--name-only", tip, new) == ar.CLEARS_REL
    rows = ag.parse_clears(_g(box.box, "show", f"{new}:{ar.CLEARS_REL}") + "\n")
    assert [r.by for r in rows] == [ar.BY]
    assert ar.sweep(box.box, apply=True, env=box.env) == 0  # nothing left to write
    _g(box.box, "fetch", "-q", "origin")
    assert _g(box.box, "rev-parse", f"origin/{LIVE}") == new


def test_a_dry_sweep_pushes_nothing(box: Box) -> None:
    _merge, head = box.pr(7, {"libs/x.py": "X = 2\n"})
    box.registry_row(7, head)
    tip = _g(box.box, "rev-parse", f"origin/{LIVE}")
    assert ar.sweep(box.box, apply=False, env=box.env) == 0
    assert _g(box.box, "ls-remote", "origin", LIVE).split()[0] == tip


# ------------------------------------------------------------------------------- the guard
def _box_at(box: Box, ref: str) -> None:
    _g(box.box, "reset", "-q", "--hard", ref)


def test_the_guard_counts_a_verified_merge_row_and_drops_a_revoked_one(
    box: Box, monkeypatch: pytest.MonkeyPatch
) -> None:
    for k, v in box.env.items():
        monkeypatch.setenv(k, v)
    sealed = _g(box.box, "rev-parse", "HEAD")
    merge, head = box.pr(7, {"libs/x.py": "X = 2\n"})
    code, doc = ag.pre(box.box, merge, now=QUIET, offset_h=lambda _t: 3)
    assert code == ag.HOLD and doc["uncovered"] == ["libs/x.py"]

    box.registry_row(7, head)
    assert ar.sweep(box.box, apply=True, env=box.env) == 0
    _g(box.box, "fetch", "-q", "origin")
    # the row sits AFTER the merge; the guard reads origin LIVE's copy for an ancestor target
    code, doc = ag.pre(box.box, merge, now=QUIET, offset_h=lambda _t: 3)
    assert code == ag.GO, doc
    assert _g(box.box, "rev-parse", "HEAD") == sealed

    box.registry_row(7, head, "HOLD")
    code, doc = ag.pre(box.box, merge, now=QUIET, offset_h=lambda _t: 3)
    assert code == ag.HOLD and doc["uncovered"] == ["libs/x.py"]
    assert doc["unverified_rows"] and "registry" in doc["unverified_rows"][0]


def test_without_the_verifier_a_merge_row_is_absent(box: Box) -> None:
    merge, head = box.pr(7, {"libs/x.py": "X = 2\n"})
    box.registry_row(7, head)
    (row,) = box.rows()
    clear = ag.parse_clears(json.dumps(row))
    (box.box / "ops" / "release" / "adopt_rows.py").unlink()
    kept, dropped = ag.authenticated(box.box, clear, env=box.env)
    assert kept == [] and dropped
    assert merge  # silence


def test_an_auditor_row_is_untouched_by_authentication(box: Box) -> None:
    row = ag.Clear("a" * 40, "CLEAR", "reports/audit/x.md", {"p": "b" * 40})
    assert ag.authenticated(box.box, [row], env={}) == ([row], [])


def test_a_target_outside_origin_live_reads_its_own_record(box: Box) -> None:
    side = _g(box.box, "commit-tree", _g(box.box, "rev-parse", "HEAD^{tree}"), "-m", "side")
    assert ag.clears_ref(box.box, side) == side
    tip = _g(box.box, "rev-parse", f"origin/{LIVE}")
    assert ag.clears_ref(box.box, _g(box.box, "rev-parse", "HEAD")) == tip
    assert os.environ is not None
