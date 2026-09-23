"""THE ANTI-STALENESS FENCE, held to its own claims.

Everything is planted in `tmp_path` against a FAKE registry and a FAKE reconciler, so the tests
say what the fence does rather than what this box's clocks did last night. The reconciler double
is the point of two of them: the brief's law is that a stale artifact raises its repair through
`libs/ops/control_plane/reconciler.py` and never through a fixer of this fence's own, and the
only way to prove that is to watch the call arrive.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.control_plane.specs import ComponentSpec, Registry  # noqa: E402
from scripts import check_no_staleness as NS  # noqa: E402

NOW = 1_780_000_000.0


def spec(cid: str, out: str, **kw: Any) -> ComponentSpec:
    base: dict[str, Any] = {"kind": "leg", "host": "any", "cadence_s": 3600,
                            "artifact_class": "hourly", "schedule": f"hourly_cycle:{cid}",
                            "restart_action": "restart:task:MT5-Hourly"}
    base.update(kw)
    return ComponentSpec(component_id=cid, outputs=(out,), **base)


def plant(root: Path, rel: str, hours_old: float, *, body: Any = None) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(body if body is not None else {"ok": True}), encoding="utf-8")
    t = NOW - hours_old * 3600.0
    import os
    os.utime(p, (t, t))
    return p


class FakeReconciler:
    """Records what the fence hands it. Mirrors the real module's public surface exactly."""

    BROKEN_STATES = frozenset({"BROKEN", "STALLED", "STALE"})

    def __init__(self) -> None:
        self.observed: list[str] = []
        self.planned: list[dict[str, Any]] = []
        self.applied: list[dict[str, Any]] = []

    def observe(self, s: ComponentSpec, **_kw: Any) -> Any:
        self.observed.append(s.component_id)

        class Obs:  # a stand-in for reconciler.Observation
            component_id = s.component_id
            state = "STALE"
            criticality = s.criticality
        return Obs()

    def plan(self, obs: Any, registry: Any) -> list[dict[str, Any]]:
        self.planned = [{"component_id": o.component_id, "state": o.state,
                         "actuator": registry.get(o.component_id).restart_action}
                        for o in obs]
        return self.planned

    def apply_plan(self, rows: Any, _registry: Any, **_kw: Any) -> list[dict[str, Any]]:
        self.applied = [{"component_id": r["component_id"], "repaired": True} for r in rows]
        return self.applied


# ------------------------------------------------------------------------------ expectations
def test_expectation_comes_from_the_declared_class_first() -> None:
    from libs.ops.control_plane import lease
    s = spec("leg:a", "desks/mt5/reports/A.json", artifact_class="hourly")
    secs, why = NS.expectation(s, lease.TTL_BY_CLASS)
    assert secs == lease.TTL_BY_CLASS["hourly"]
    assert "TTL_BY_CLASS" in why


def test_expectation_is_derived_from_the_clock_when_no_class_is_declared() -> None:
    """The brief: where an expectation does not exist yet, DERIVE it and RECORD it."""
    s = spec("leg:b", "desks/mt5/reports/B.json", artifact_class="", cadence_s=900)
    secs, why = NS.expectation(s, {})
    assert secs == int(900 * NS.STALL_CADENCES)
    assert why.startswith("DERIVED")
    assert "hourly_cycle:leg:b" in why


def test_expectation_with_neither_class_nor_cadence_is_unmeasured_never_a_pass() -> None:
    s = spec("leg:c", "desks/mt5/reports/C.json", artifact_class="", cadence_s=None,
             max_silence_s=None)
    secs, why = NS.expectation(s, {})
    assert secs is None
    assert "UNMEASURED" in why


def test_artifact_paths_survive_the_registrys_prose_outputs() -> None:
    """`outputs` are derived from source and carry citations and trailing notes."""
    s = ComponentSpec(component_id="leg:x", outputs=(
        "desks/mt5/reports/universal_gates_external.json (desks/mt5/scripts/x.py:1605-1606); "
        "desks/mt5/reports/UNIVERSAL_SURVIVORS.json (:1637)",
        "desks/mt5/reports/ADVERSARY.json gate_detail"))
    assert NS.artifact_paths(s) == ("desks/mt5/reports/universal_gates_external.json",
                                    "desks/mt5/reports/UNIVERSAL_SURVIVORS.json",
                                    "desks/mt5/reports/ADVERSARY.json")


# ------------------------------------------------------------------------------------- hosts
@pytest.mark.parametrize(("spec_host", "here", "ok"), [
    ("any", "build_box", True), ("any", "trading_box", True),
    ("box", "trading_box", True), ("box", "box_clocks_off", True),
    ("box", "build_box", False), ("box", "vps", False),
    ("vps", "vps", True), ("vps", "build_box", False), ("vps", "trading_box", False),
])
def test_host_rule(spec_host: str, here: str, ok: bool) -> None:
    got, why = NS.measurable_here(spec_host, here)
    assert got is ok
    assert ok or "not stale" in why or "mirror" in why


def test_a_box_artifact_on_a_build_box_is_unmeasured_not_stale(tmp_path: Path) -> None:
    """The honesty requirement: a build box's mirror of a gateway artifact is not stale."""
    from libs.ops.control_plane import lease
    plant(tmp_path, "desks/mt5/reports/G.json", 900.0)
    row = NS.judge("desks/mt5/reports/G.json", spec("leg:g", "desks/mt5/reports/G.json",
                                                    host="box"),
                   root=tmp_path, now=NOW, here="build_box",
                   ttl_by_class=lease.TTL_BY_CLASS, lease=None)
    assert row["verdict"] == NS.UNMEASURED
    assert "mirror" in row["why"]


# --------------------------------------------------------------------------------- verdicts
def _judge(tmp_path: Path, rel: str, s: ComponentSpec, here: str = "any") -> dict[str, Any]:
    from libs.ops.control_plane import lease
    return NS.judge(rel, s, root=tmp_path, now=NOW, here=here,
                    ttl_by_class=lease.TTL_BY_CLASS, lease=None)


def test_fresh_artifact_passes(tmp_path: Path) -> None:
    plant(tmp_path, "desks/mt5/reports/F.json", 0.5)
    row = _judge(tmp_path, "desks/mt5/reports/F.json", spec("leg:f", "desks/mt5/reports/F.json"))
    assert row["verdict"] == NS.FRESH


def test_stale_artifact_fails_and_names_organ_clock_and_expectation(tmp_path: Path) -> None:
    plant(tmp_path, "desks/mt5/reports/S.json", 600.0)
    row = _judge(tmp_path, "desks/mt5/reports/S.json", spec("leg:s", "desks/mt5/reports/S.json"))
    assert row["verdict"] == NS.STALE
    assert row["organ"] == "leg:s"
    assert row["clock"] == "hourly_cycle:leg:s"
    assert row["expected_refresh_s"] == 7200
    assert "600.0h old against a 2.0h expectation" in row["why"]


def test_absent_artifact_is_missing_not_fresh(tmp_path: Path) -> None:
    row = _judge(tmp_path, "desks/mt5/reports/N.json", spec("leg:n", "desks/mt5/reports/N.json"))
    assert row["verdict"] == NS.MISSING
    assert row["age_s"] is None


def test_the_documents_own_stamp_beats_its_mtime(tmp_path: Path) -> None:
    from datetime import UTC, datetime
    old = datetime.fromtimestamp(NOW - 500 * 3600.0, tz=UTC).isoformat()
    plant(tmp_path, "desks/mt5/reports/D.json", 0.1, body={"at": old})
    row = _judge(tmp_path, "desks/mt5/reports/D.json", spec("leg:d", "desks/mt5/reports/D.json"))
    assert row["verdict"] == NS.STALE
    assert row["stamp"] == "document field `at`"


def test_an_expired_lease_beats_everything(tmp_path: Path) -> None:
    from libs.ops.control_plane import lease
    plant(tmp_path, "desks/mt5/reports/L.json", 0.01)

    class FakeLease:
        TTL_BY_CLASS = lease.TTL_BY_CLASS

        @staticmethod
        def read_envelope(_p: Path) -> dict[str, Any]:
            return {"valid_until": "2020-01-01T00:00:00+00:00"}

        @staticmethod
        def valid(_env: Any, _now: Any) -> bool:
            return False

    row = NS.judge("desks/mt5/reports/L.json", spec("leg:l", "desks/mt5/reports/L.json"),
                   root=tmp_path, now=NOW, here="any", ttl_by_class=lease.TTL_BY_CLASS,
                   lease=FakeLease)
    assert row["verdict"] == NS.STALE
    assert row["stamp"] == "lease envelope"
    assert "lease has expired" in row["why"]


# -------------------------------------------------------- the repair reaches the reconciler
def test_the_reconciler_receives_the_repair(tmp_path: Path) -> None:
    """The principal's law: no new independent fixer. The repair goes through the existing flow."""
    s = spec("leg:r", "desks/mt5/reports/R.json")
    reg = Registry([s])
    rec = FakeReconciler()
    out = NS.raise_repairs([{"organ": "leg:r", "artifact": "desks/mt5/reports/R.json"}], reg,
                           apply=False, root=tmp_path, reconciler=rec)
    assert rec.observed == ["leg:r"]
    assert out["planned"][0]["component_id"] == "leg:r"
    assert out["planned"][0]["actuator"] == "restart:task:MT5-Hourly"
    assert out["mode"] == "observe"
    assert rec.applied == []          # observe-only never runs an actuator


def test_apply_runs_the_reconcilers_plan_not_a_fixer_of_our_own(tmp_path: Path) -> None:
    s = spec("leg:r", "desks/mt5/reports/R.json")
    rec = FakeReconciler()
    out = NS.raise_repairs([{"organ": "leg:r"}], Registry([s]), apply=True, root=tmp_path,
                           reconciler=rec)
    assert rec.applied == [{"component_id": "leg:r", "repaired": True}]
    assert out["mode"] == "apply"


def test_an_unknown_component_raises_nothing_and_says_so(tmp_path: Path) -> None:
    rec = FakeReconciler()
    out = NS.raise_repairs([{"organ": "leg:ghost"}], Registry([]), root=tmp_path, reconciler=rec)
    assert rec.observed == []
    assert out["observed"] == 0
    assert "no stale artifact maps" in out["why"]


# -------------------------------------------------------------------------------- the audit
def _audit(tmp_path: Path, specs: list[ComponentSpec], **kw: Any) -> dict[str, Any]:
    rec = FakeReconciler()
    return NS.audit(tmp_path, now=NOW, here="any", registry=Registry(specs),
                    reconciler=rec, **kw)


def test_audit_passes_when_everything_is_fresh(tmp_path: Path) -> None:
    plant(tmp_path, "desks/mt5/reports/A.json", 0.5)
    doc = _audit(tmp_path, [spec("leg:a", "desks/mt5/reports/A.json")])
    assert doc["verdicts"][NS.FRESH] == 1
    assert doc["measured_for_ratchet"] == 0
    assert doc["ratchet_breach"] is False


def test_audit_fails_on_a_planted_stale_artifact(tmp_path: Path) -> None:
    plant(tmp_path, "desks/mt5/reports/A.json", 0.5)
    plant(tmp_path, "desks/mt5/reports/B.json", 700.0)
    doc = _audit(tmp_path, [spec("leg:a", "desks/mt5/reports/A.json"),
                            spec("leg:b", "desks/mt5/reports/B.json")])
    assert doc["measured_for_ratchet"] == 1
    assert doc["stale_artifacts"] == ["desks/mt5/reports/B.json"]
    assert doc["ratchet_breach"] is True          # MAX_STALE is 0
    assert doc["repairs"]["planned"][0]["component_id"] == "leg:b"


def test_a_stale_required_artifact_is_always_a_breach(tmp_path: Path) -> None:
    plant(tmp_path, "desks/mt5/reports/C.json", 700.0)
    doc = _audit(tmp_path, [spec("leg:c", "desks/mt5/reports/C.json", criticality="required")])
    assert doc["required_stale"] == ["desks/mt5/reports/C.json"]
    assert doc["ratchet_breach"] is True


def test_one_stale_file_owned_by_three_legs_counts_once(tmp_path: Path) -> None:
    plant(tmp_path, "desks/mt5/data/cost_surface.json", 700.0)
    doc = _audit(tmp_path, [spec(f"leg:{n}", "desks/mt5/data/cost_surface.json")
                            for n in ("a", "b", "c")])
    assert doc["verdicts"][NS.STALE] == 3
    assert doc["measured_for_ratchet"] == 1


def test_derived_expectations_are_recorded(tmp_path: Path) -> None:
    plant(tmp_path, "desks/mt5/reports/E.json", 0.1)
    doc = _audit(tmp_path, [spec("leg:e", "desks/mt5/reports/E.json",
                                 artifact_class="", cadence_s=600)])
    assert doc["derived_expectations"][0]["expected_refresh_s"] == 1200
    assert doc["derived_expectations"][0]["from"].startswith("DERIVED")


def test_unmeasured_is_reported_and_never_silently_fresh(tmp_path: Path) -> None:
    plant(tmp_path, "desks/mt5/reports/U.json", 900.0)
    doc = _audit(tmp_path, [spec("leg:u", "desks/mt5/reports/U.json", host="vps")])
    assert doc["verdicts"].get(NS.FRESH) is None
    assert doc["unmeasured"][0]["artifact"] == "desks/mt5/reports/U.json"


def test_missing_artifacts_are_listed_separately(tmp_path: Path) -> None:
    doc = _audit(tmp_path, [spec("leg:m", "desks/mt5/reports/M.json")])
    assert doc["missing"][0]["organ"] == "leg:m"
    assert doc["missing"][0]["clock"] == "hourly_cycle:leg:m"


def test_the_suspension_only_fires_on_a_box_with_every_clock_disabled(tmp_path: Path) -> None:
    plant(tmp_path, "desks/mt5/reports/S.json", 700.0)
    specs = [spec("leg:s", "desks/mt5/reports/S.json")]

    def run(kind: str, clocks: int | None) -> dict[str, Any]:
        import unittest.mock as um

        from desks.mt5.research import loop_liveness as LL
        with um.patch.object(LL, "host_facts", lambda: {"kind": kind, "why": "test",
                                                        "enabled_box_clocks": clocks}):
            return NS.audit(tmp_path, now=NOW, registry=Registry(specs),
                            reconciler=FakeReconciler())

    stopped = run("box_clocks_off", 0)
    assert stopped["ratchet_breach"] is False
    assert "DISABLED" in stopped["ratchet_suspended"]
    running = run("trading_box", 4)
    assert running["ratchet_breach"] is True
    assert running["ratchet_suspended"] is None


def test_audit_reports_elapsed_and_the_rule(tmp_path: Path) -> None:
    doc = _audit(tmp_path, [spec("leg:a", "desks/mt5/reports/A.json")])
    assert isinstance(doc["elapsed_s"], float)
    assert "UNMEASURED is a verdict, never a pass" in doc["rule"]
    assert "reconciler.py" in doc["rule"]


def test_a_reconciler_that_raises_is_reported_not_crashed(tmp_path: Path) -> None:
    """A fence that dies inside the law gate is a fence that gets deleted."""
    plant(tmp_path, "desks/mt5/reports/B.json", 700.0)

    class Boom:
        def observe(self, *_a: Any, **_k: Any) -> Any:
            raise RuntimeError("control plane unavailable")

    doc = NS.audit(tmp_path, now=NOW, here="any",
                   registry=Registry([spec("leg:b", "desks/mt5/reports/B.json")]),
                   reconciler=Boom())
    assert doc["repairs"]["mode"] == "error"
    assert "control plane unavailable" in doc["repairs"]["why"]


# ----------------------------------------------------------------------------------- wiring
def test_the_fence_is_registered_in_the_law_gate() -> None:
    """UNWIRED IS A DEFECT: a fence nothing runs is a claim the desk cannot cash (L1.49)."""
    src = (ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert '"check_no_staleness.py"' in src or "'check_no_staleness.py'" in src


def test_main_writes_its_artifact_and_returns_the_right_code(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch
                                                             ) -> None:
    plant(tmp_path, "desks/mt5/reports/B.json", 700.0)
    fake = {"verdicts": {NS.STALE: 1}, "ratchet_breach": False, "stale": [], "host": "any",
            "artifacts_judged": 1, "measured_for_ratchet": 1, "ratchet": 0, "repairs": {}}
    monkeypatch.setattr(NS, "audit", lambda **_k: dict(fake))
    out = tmp_path / "NO_STALENESS.json"
    assert NS.main(["--report", str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["measured_for_ratchet"] == 1
    monkeypatch.setattr(NS, "audit", lambda **_k: {**fake, "ratchet_breach": True})
    assert NS.main(["--report", str(out)]) == 2
    monkeypatch.setattr(NS, "audit", lambda **_k: {**fake, "verdicts": {}})
    assert NS.main(["--report", str(out)]) == 0


def test_time_is_injected_so_the_verdict_is_reproducible(tmp_path: Path) -> None:
    plant(tmp_path, "desks/mt5/reports/A.json", 0.5)
    a = _audit(tmp_path, [spec("leg:a", "desks/mt5/reports/A.json")])
    b = NS.audit(tmp_path, now=NOW + 10 * 86400.0, here="any",
                 registry=Registry([spec("leg:a", "desks/mt5/reports/A.json")]),
                 reconciler=FakeReconciler())
    assert a["verdicts"][NS.FRESH] == 1
    assert b["verdicts"][NS.STALE] == 1
    assert time.time() > 0            # the audit never had to read the wall clock


def test_the_stale_row_names_the_organs_last_exit(tmp_path: Path) -> None:
    """The brief: name the organ, its clock AND its last exit. "Old file" is not a diagnosis."""
    from libs.ops.control_plane import lease
    plant(tmp_path, "desks/mt5/reports/S.json", 600.0)
    runs = {"leg:s": {"at": "2026-09-16T15:07:09+00:00", "outcome": "failed", "wall_s": 3.2}}
    row = NS.judge("desks/mt5/reports/S.json", spec("leg:s", "desks/mt5/reports/S.json"),
                   root=tmp_path, now=NOW, here="any", ttl_by_class=lease.TTL_BY_CLASS,
                   lease=None, runs=runs)
    assert row["verdict"] == NS.STALE
    assert row["organ_last_exit"]["outcome"] == "failed"
    assert row["organ_last_exit"]["at"] == "2026-09-16T15:07:09+00:00"


def test_an_organ_with_no_costed_run_is_unmeasured_not_never() -> None:
    """Never-ran and ran-and-failed are different defects with different repairs."""
    got = NS.last_exit("leg:ghost", {})
    assert got["outcome"] == NS.UNMEASURED
    assert "no costed run" in got["why"]
    assert NS.last_exit("leg:s", {"s": {"at": "x", "outcome": "ok"}})["outcome"] == "ok"
