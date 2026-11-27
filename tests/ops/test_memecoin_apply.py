import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ops" / "box"))
import memecoin_apply as ma


def run(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture()
def world(tmp_path):
    """origin repo with main + 2 packet branches; spot clone behind main; a drop folder."""
    origin = tmp_path / "origin"
    origin.mkdir()
    run(origin, "init", "-q", "-b", "main")
    (origin / "src").mkdir()
    (origin / "src" / "__init__.py").write_text("")
    (origin / "src" / "main.py").write_text("X = 1\n")
    run(origin, "add", ".")
    run(origin, "commit", "-q", "-m", "old")
    old = run(origin, "rev-parse", "HEAD")
    spot = tmp_path / "spot"
    subprocess.run(["git", "clone", "-q", str(origin), str(spot)], check=True)
    (origin / "src" / "base.py").write_text("B = 1\n")
    run(origin, "add", ".")
    run(origin, "commit", "-q", "-m", "base")
    base = run(origin, "rev-parse", "HEAD")
    heads = {}
    for name, fname, body in (("a", "a.py", "A = 1\n"), ("b", "b.py", "B2 = 2\n")):
        run(origin, "checkout", "-q", "-b", f"feat/{name}", base)
        (origin / "src" / fname).write_text(body)
        run(origin, "add", ".")
        run(origin, "commit", "-q", "-m", name)
        heads[name] = run(origin, "rev-parse", "HEAD")
    run(origin, "checkout", "-q", "main")
    drop = tmp_path / "drop"
    mc = drop / "memecoin"
    (mc / "verdicts").mkdir(parents=True)
    run(origin, "bundle", "create", str(mc / "main.bundle"), "main")
    for name, head in heads.items():
        run(origin, "bundle", "create", str(mc / f"p{name}.bundle"), f"main..feat/{name}")
        (mc / f"p{name}.json").write_text(json.dumps({"branch": f"feat/{name}", "head": head}))
        (mc / "verdicts" / f"p{name}.json").write_text(json.dumps({"line": f"AUDIT CLEAR {head}"}))
    (mc / "APPLY_ORDER.json").write_text(json.dumps({"base": base, "order": ["pa", "pb"]}))
    fake = tmp_path / "schtasks.py"
    log = tmp_path / "schtasks.log"
    fake.write_text(f"import sys\nopen(r'{log}','a').write(' '.join(sys.argv[1:])+'\\n')\n")
    return {
        "origin": origin,
        "spot": spot,
        "drop": drop,
        "mc": mc,
        "heads": heads,
        "base": base,
        "old": old,
        "schtasks": [sys.executable, str(fake)],
        "log": log,
    }


def _apply(w, **kw):
    kw.setdefault("schtasks", w["schtasks"])
    return ma.apply(w["drop"], w["spot"], **kw)


def test_applies_in_order_and_restarts_only_the_task(world):
    r = _apply(world)
    assert r["refused"] is None and [a["packet"] for a in r["applied"]] == ["pa", "pb"]
    assert r["fast_forward"] == world["base"] and r["smoke"]["ok"]
    for h in world["heads"].values():
        assert ma.is_ancestor(world["spot"], h, "HEAD")
    assert world["log"].read_text().splitlines() == [
        "/End /TN MemecoinShadowCodex",
        "/Run /TN MemecoinShadowCodex",
    ]
    again = _apply(world)
    assert again["applied"] == [] and again["skipped"] == {"pa": "already in", "pb": "already in"}
    assert again["restart"] is None


def test_a_verdict_for_another_sha_refuses_and_stops(world):
    (world["mc"] / "verdicts" / "pb.json").write_text(
        json.dumps({"line": "AUDIT CLEAR " + "0" * 40})
    )
    r = _apply(world)
    assert [a["packet"] for a in r["applied"]] == ["pa"]
    assert "pb: verdict" in r["refused"]


def test_hold_verdict_refuses(world):
    head = world["heads"]["a"]
    (world["mc"] / "verdicts" / "pa.json").write_text(json.dumps({"line": f"AUDIT HOLD {head}"}))
    r = _apply(world)
    assert r["applied"] == [] and "not AUDIT CLEAR" in r["refused"] and r["restart"] is None


def test_fenced_is_skipped(world):
    m = json.loads((world["mc"] / "pa.json").read_text())
    (world["mc"] / "pa.json").write_text(json.dumps({**m, "fenced": True}))
    r = _apply(world)
    assert r["skipped"]["pa"].startswith("fenced") and [a["packet"] for a in r["applied"]] == ["pb"]


def test_dirty_checkout_is_refused_untouched(world):
    (world["spot"] / "src" / "main.py").write_text("X = 2\n")
    before = run(world["spot"], "rev-parse", "HEAD")
    r = _apply(world)
    assert "uncommitted" in r["refused"] and r["applied"] == []
    assert run(world["spot"], "rev-parse", "HEAD") == before
    assert (world["spot"] / "src" / "main.py").read_text() == "X = 2\n"


def test_bundle_tip_must_be_the_cleared_head(world):
    m = json.loads((world["mc"] / "pa.json").read_text())
    other = "1" * 40
    (world["mc"] / "pa.json").write_text(json.dumps({**m, "head": other}))
    (world["mc"] / "verdicts" / "pa.json").write_text(json.dumps({"line": f"AUDIT CLEAR {other}"}))
    r = _apply(world)
    assert "bundle tip" in r["refused"] and r["applied"] == []


def test_diverged_checkout_needs_a_person(world):
    (world["spot"] / "local.txt").write_text("x")
    run(world["spot"], "add", ".")
    run(world["spot"], "commit", "-q", "-m", "local box commit")
    r = _apply(world)
    assert "diverged" in r["refused"] and r["applied"] == []


def test_failed_smoke_reverts_every_merge_of_the_run(world):
    run(world["origin"], "checkout", "-q", "feat/b")
    (world["origin"] / "src" / "main.py").write_text("raise SystemExit(9)\n")
    run(world["origin"], "add", ".")
    run(world["origin"], "commit", "-q", "-m", "breaks import")
    head = run(world["origin"], "rev-parse", "HEAD")
    run(world["origin"], "checkout", "-q", "main")
    run(world["origin"], "bundle", "create", str(world["mc"] / "pb.bundle"), "main..feat/b")
    (world["mc"] / "pb.json").write_text(json.dumps({"branch": "feat/b", "head": head}))
    (world["mc"] / "verdicts" / "pb.json").write_text(json.dumps({"line": f"AUDIT CLEAR {head}"}))
    r = _apply(world)
    assert not r["smoke"]["ok"] and len(r["reverted"]) == 2
    assert all(x["rc"] == 0 for x in r["reverted"])
    assert (world["spot"] / "src" / "main.py").read_text() == "X = 1\n"
    assert not (world["spot"] / "src" / "a.py").exists()


def test_merge_conflict_aborts_cleanly(world):
    for name in ("a", "b"):
        run(world["origin"], "checkout", "-q", f"feat/{name}")
        (world["origin"] / "src" / "same.py").write_text(f"{name}\n")
        run(world["origin"], "add", ".")
        run(world["origin"], "commit", "-q", "-m", f"{name} same")
        head = run(world["origin"], "rev-parse", "HEAD")
        run(
            world["origin"],
            "bundle",
            "create",
            str(world["mc"] / f"p{name}.bundle"),
            f"main..feat/{name}",
        )
        (world["mc"] / f"p{name}.json").write_text(
            json.dumps({"branch": f"feat/{name}", "head": head})
        )
        (world["mc"] / "verdicts" / f"p{name}.json").write_text(
            json.dumps({"line": f"AUDIT CLEAR {head}"})
        )
    run(world["origin"], "checkout", "-q", "main")
    r = _apply(world)
    assert [a["packet"] for a in r["applied"]] == ["pa"] and "merge conflict" in r["refused"]
    assert not (world["spot"] / ".git" / "MERGE_HEAD").exists()
    assert run(world["spot"], "status", "--porcelain", "--untracked-files=no") == ""


def test_dry_run_changes_nothing_and_cli_writes_out(world, tmp_path):
    before = run(world["spot"], "rev-parse", "HEAD")
    r = _apply(world, dry_run=True)
    assert r["plan"] == ["pa", "pb"] and run(world["spot"], "rev-parse", "HEAD") == before
    out = tmp_path / "o" / "memecoin_apply.json"
    rc = ma.main(
        ["--drop", str(world["drop"]), "--repo", str(world["spot"]), "--out", str(out), "--dry-run"]
    )
    assert rc == 0 and json.loads(out.read_text())["dry_run"] is True


def test_a_failed_revert_aborts_and_never_restarts(world, monkeypatch):
    run(world["origin"], "checkout", "-q", "feat/b")
    (world["origin"] / "src" / "main.py").write_text("raise SystemExit(9)\n")
    run(world["origin"], "add", ".")
    run(world["origin"], "commit", "-q", "-m", "breaks import")
    head = run(world["origin"], "rev-parse", "HEAD")
    run(world["origin"], "checkout", "-q", "main")
    run(world["origin"], "bundle", "create", str(world["mc"] / "pb.bundle"), "main..feat/b")
    (world["mc"] / "pb.json").write_text(json.dumps({"branch": "feat/b", "head": head}))
    (world["mc"] / "verdicts" / "pb.json").write_text(json.dumps({"line": f"AUDIT CLEAR {head}"}))
    real = subprocess.run

    def fake(cmd, *a, **k):
        if "revert" in cmd and "--abort" not in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "conflict")
        return real(cmd, *a, **k)

    monkeypatch.setattr(ma.subprocess, "run", fake)
    r = _apply(world)
    assert "needs a person" in r["refused"] and r["restart"] is None
    assert not world["log"].exists()
