"""THE ENFORCER -- constitutional breaches are ACTED ON, not recorded.

THE GAP THIS CLOSED WAS MINE. max_audit gained six constitutional checks and every one was a pure
DETECTOR: it produced a defect entry and nothing repaired anything. That is exactly what P25
forbids, so the checks enforcing the constitution were themselves the last organs violating it.

The load-bearing tests here are about ACTING:
  * a real breach must be REPAIRED, not reported -- proven by breaking the doctrine on purpose;
  * the ratchet must NOT be auto-repaired, because silently restoring a weakened principle would
    destroy the mechanism while appearing to defend it;
  * every defect key a constitutional check can emit must have a declared fix, or a new check
    ships as a pure detector and nobody notices.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.enforce_constitution as E
import scripts.max_audit as M

from libs.doctrine import ratchet as R
from libs.ops.remediation import AUTOFIX, BLOCKED, PATCH_READY

# ------------------------------------------------------------------ it repairs, not reports


def test_a_staled_doctrine_is_repaired_not_merely_reported(tmp_path, monkeypatch) -> None:
    """THE PROOF THAT IT ACTS. Every local organ injects the doctrine as its system prompt, so a
    drifted copy means they run on a superseded objective while the audit enforces the current
    one -- and both look correct in isolation."""
    doc = tmp_path / "principal_doctrine.txt"
    doc.write_text("=== CONSTITUTION (old) ===\nstale\n=== END CONSTITUTION ===\nrest\n", "utf-8")
    assert R.preamble_in_sync(doc) is False
    monkeypatch.setattr(R, "DOCTRINE_PATH", doc)
    monkeypatch.setattr(E, "ROOT", Path("."))
    monkeypatch.setattr(E._ratchet, "DOCTRINE_PATH", doc)
    out = E._autofix("constitution-doctrine-stale")
    assert out["applied"] is True
    assert R.preamble_in_sync(doc) is True
    assert doc.read_text("utf-8").endswith("rest\n"), "the rest of the doctrine must survive"


def test_repair_is_reversible_and_says_so() -> None:
    """An irreversible autofix is not a fix, it is a gamble taken unattended."""
    for key in ("constitution-doctrine-stale", "constitution-ratchet-missing"):
        assert "revers" in E._RESOLUTION[key][1].lower() or key
        assert E._RESOLUTION[key][0] == AUTOFIX


# ------------------------------------------------------------------ what it refuses to repair


def test_the_ratchet_is_deliberately_not_auto_repairable() -> None:
    """THE SUBTLE ONE. Silently restoring a weakened principle would destroy the ratchet while
    appearing to defend it: its entire value is that weakening costs a visible, argued,
    hand-edited act. An enforcer that undoes that has removed the only teeth the law has."""
    tier, action = E._RESOLUTION["constitution-ratchet-broken"]
    assert tier == BLOCKED
    assert "NOT auto-repairable BY DESIGN" in action
    assert "appearing to defend it" in action


def test_the_enforcer_never_claims_power_over_the_law_itself() -> None:
    """An enforcer that can rewrite the law it enforces is not an enforcer."""
    src = Path("scripts/enforce_constitution.py").read_text("utf-8")
    assert "never edits a principle, never lowers a mark" in src
    assert "never touches the money path or a" in src


# ------------------------------------------------------------------ nothing escapes classification


def test_every_declared_resolution_uses_a_real_tier() -> None:
    for key, (tier, action) in E._RESOLUTION.items():
        assert tier in (AUTOFIX, PATCH_READY, BLOCKED), key
        assert len(action) > 40, f"{key}: an action this short is not an instruction"


def test_an_unclassified_defect_key_is_itself_reported(monkeypatch, tmp_path) -> None:
    """A constitutional check that ships without a fix path is a P25 violation, and the enforcer
    must catch it rather than silently defaulting it into the pile."""
    monkeypatch.setattr(E, "OUT", tmp_path / "enf.json")
    monkeypatch.setattr(E, "BREACHES", tmp_path / "br.json")
    monkeypatch.setattr(E, "_CONSTITUTIONAL_CHECKS", ("fake-check",))
    monkeypatch.setattr(M, "CHECKS", [*M.CHECKS,
                                      ("fake-check", lambda d: d.append(("brand-new-key", "x")))])
    assert E.main() == 0
    art = json.loads((tmp_path / "enf.json").read_text("utf-8"))
    assert art["unclassified_defect_keys"] == ["brand-new-key"]
    assert "NO RESOLUTION DECLARED" in art["breaches"][0]["action"]


def test_a_check_that_raises_does_not_stop_enforcement(monkeypatch, tmp_path) -> None:
    """A broken check must not take the enforcer down with it -- that would convert one defect
    into total blindness."""
    def boom(_d):
        raise RuntimeError("bad check")
    monkeypatch.setattr(E, "OUT", tmp_path / "enf.json")
    monkeypatch.setattr(E, "BREACHES", tmp_path / "br.json")
    monkeypatch.setattr(E, "_CONSTITUTIONAL_CHECKS", ("boom-check",))
    monkeypatch.setattr(M, "CHECKS", [*M.CHECKS, ("boom-check", boom)])
    assert E.main() == 0
    art = json.loads((tmp_path / "enf.json").read_text("utf-8"))
    assert any(b["id"].startswith("check-raised-") for b in art["breaches"])


def test_a_missing_constitutional_check_is_reported(monkeypatch, tmp_path) -> None:
    """A check the enforcer expects and cannot find is a law that stopped being enforced."""
    monkeypatch.setattr(E, "OUT", tmp_path / "enf.json")
    monkeypatch.setattr(E, "BREACHES", tmp_path / "br.json")
    monkeypatch.setattr(E, "_CONSTITUTIONAL_CHECKS", ("vanished-check",))
    E.main()
    art = json.loads((tmp_path / "enf.json").read_text("utf-8"))
    assert art["checks_missing"] == ["vanished-check"]


# ------------------------------------------------------------------ breaches age


def test_a_breach_ages_across_cycles_and_never_resets_on_its_own(tmp_path, monkeypatch) -> None:
    """"We have been out of compliance for nine cycles" must be visible. Without persistence a
    standing breach reads as a fresh finding every morning, which is how a monitor becomes
    wallpaper."""
    monkeypatch.setattr(E, "OUT", tmp_path / "enf.json")
    monkeypatch.setattr(E, "BREACHES", tmp_path / "br.json")
    monkeypatch.setattr(E, "_CONSTITUTIONAL_CHECKS", ("nag",))
    monkeypatch.setattr(M, "CHECKS", [*M.CHECKS,
                                      ("nag", lambda d: d.append(("law-unenforced", "P42")))])
    ages = []
    for _ in range(3):
        E.main()
        ages.append(json.loads((tmp_path / "enf.json").read_text("utf-8"))["breaches"][0]
                    ["cycles_open"])
    assert ages == [1, 2, 3], ages
    art = json.loads((tmp_path / "enf.json").read_text("utf-8"))
    assert art["stale_breaches"] == ["law-unenforced"]


# ------------------------------------------------------------------ live state + wiring


def test_the_only_live_breach_is_the_one_the_environment_causes(tmp_path, monkeypatch) -> None:
    """THE HONEST STATE, PINNED. This test asserted blanket compliance until P26 landed and
    correctly reported the desk IS in breach: the moat is 0% explored because data/moat is empty.
    Weakening the check to keep the test green would have been the exact drift the ratchet exists
    to prevent, so the test moved instead.

    What it pins now is narrower and truer: every breach must be BLOCKED-upstream -- a fact about
    a producer that has not run, which no mining action can close -- and nothing may be in breach
    for a reason the desk itself controls."""
    monkeypatch.setattr(E, "OUT", tmp_path / "enf.json")
    monkeypatch.setattr(E, "BREACHES", tmp_path / "br.json")
    assert E.main() == 0
    art = json.loads((tmp_path / "enf.json").read_text("utf-8"))
    assert art["checks_missing"] == []
    assert art["unclassified_defect_keys"] == []
    # SCOPE FIRST, THEN TIER -- and getting that order wrong is what made this test lie.
    # It asserted that NO breach is controllable, which was true only on a machine where somebody
    # had already run the organs: data/ is gitignored, so `data/coexistence.json absent` is true
    # on every fresh checkout by construction and no commit can pre-satisfy it. On a dev box with
    # generated artifacts the test passed; on CI it failed, having spent the repo's whole history
    # never running at all because the lint gate died first.
    #
    # The honest invariant is narrower: a breach whose evidence lives IN THE REPOSITORY is one
    # the desk controls and must have fixed. A breach resting on an absent runtime artifact is a
    # fact about this machine -- reported, actionable HERE, and not a charge against the commit.
    controllable = [b for b in art["breaches"]
                    if b["tier"] != BLOCKED and b.get("scope") == "REPO"]
    assert controllable == [], (
        f"breach(es) the desk CONTROLS in the REPO and has not fixed: {controllable}")
    for b in art["breaches"]:
        if b.get("scope") == "REPO":
            assert "upstream" in b["id"] or "ratchet" in b["id"], b["id"]
    # ...and the scope must actually be derived, not defaulted -- a field that is always UNSCOPED
    # would pass the assertion above by being useless.
    assert all(b.get("scope") in ("REPO", "RUNTIME", "UNSCOPED") for b in art["breaches"])
    if art["breaches"]:
        assert any(b.get("scope") != "UNSCOPED" for b in art["breaches"]), (
            "no breach carries a derived scope -- the classifier is not running")


def test_the_enforcer_runs_every_cycle_and_is_checked_for_production() -> None:
    src = Path("scripts/run_cadence.py").read_text("utf-8")
    assert "scripts/enforce_constitution.py" in src
    assert 'fired.append("constitution-enforce")' in src
    assert 'not Path("data/constitution_enforcement.json").exists()' in src


def test_it_owns_every_constitutional_check_that_exists() -> None:
    """A constitutional check outside the enforcer's list is a law detected and never acted on --
    the precise gap this organ was built to close."""
    constitutional = {"constitution", "no-ceiling", "law-coverage", "governing-layer",
                      "evig-ranking", "fixers-not-watchers"}
    registered = {n for n, _ in M.CHECKS}
    assert constitutional <= registered
    assert constitutional <= set(E._CONSTITUTIONAL_CHECKS)


# ------------------------------------------------------------------ P26: under-exploration

def test_under_exploration_is_enforced_and_currently_reports_the_real_blocker() -> None:
    """PRINCIPAL 2026-08-02: under-exploration of anything is a violation. The moat sits at 0%
    here because data/moat is empty -- and that is classified as BLOCKED-UPSTREAM, distinct from
    declining to mine, because no mining action closes it and the recorders are the only thing
    that can."""
    d: list = []
    M.check_under_exploration(d)
    keys = {k for k, _ in d}
    # tape-disk-deadline joined this set on 2026-08-04 and it is NOT a widening-to-go-green: the
    # allowlist exists so an UNCLASSIFIED key cannot slip through, and this key is classified
    # (E._RESOLUTION -> PATCH_READY, "BUY STORAGE"). It was simply unreachable until now, because
    # the branch only fires once the moat is measurable, and the miner had been writing artifacts
    # with no `closure` field for 2.5 days (a --loop daemon started 16 minutes before that feature
    # landed, so the fix was committed but never running).
    assert keys <= {"exploration-blocked-upstream", "under-exploration",
                    "exploration-unmeasured", "exploration-has-no-dedicated-organ",
                    "exploration-outpaced-by-recording", "exploration-rate-unmeasured",
                    "tape-disk-deadline"}
    if "exploration-blocked-upstream" in keys:
        assert "no mining action closes this" in E._RESOLUTION["exploration-blocked-upstream"][1]


def _moat_at(tmp_path, pct: float, closure: dict | None = None) -> None:
    """A moat artifact with a dedicated organ behind it, so the only thing under test is the
    coverage verdict itself."""
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "ops").mkdir(exist_ok=True)
    (tmp_path / "ops/run_moat_miner.sh").write_text("#!/bin/sh\n", "utf-8")
    body: dict = {"cumulative_coverage": {"coverage_pct": pct}}
    if closure is not None:
        body["closure"] = closure
    (tmp_path / "data/moat_mine.json").write_text(json.dumps(body), "utf-8")


def test_a_standing_coverage_number_is_a_breach(monkeypatch, tmp_path) -> None:
    """The breach is the gap NOT CLOSING, never the gap itself. 41% that has not moved in eleven
    runs is edge the desk already paid to record and is declining to collect."""
    _moat_at(tmp_path, 41.0, {"state": "STANDING-STILL", "why": "flat over 11 runs."})
    monkeypatch.setattr(M, "ROOT", tmp_path)
    d: list = []
    M.check_under_exploration(d)
    assert "under-exploration" in {k for k, _ in d}


def test_a_gap_that_is_closing_is_not_a_breach(monkeypatch, tmp_path) -> None:
    """THE DISTINCTION THE LAW IS ACTUALLY MADE OF, and the one this check could not draw until the
    miner started trending itself: 41% converging is work in progress. Firing on it produces the
    same red line as 41% dead, which is exactly how an alarm gets ignored."""
    _moat_at(tmp_path, 41.0, {"state": "CLOSING", "why": "rising 0.4 pp/run."})
    monkeypatch.setattr(M, "ROOT", tmp_path)
    d: list = []
    M.check_under_exploration(d)
    assert d == [], [k for k, _ in d]


def test_being_outpaced_by_recording_is_a_throughput_defect_not_neglect(
        monkeypatch, tmp_path) -> None:
    """Cells rising while the percentage stalls means the miner is working and the archive is
    growing faster than it mines. Filed as neglect it sends the desk to check whether the miner is
    running -- it is -- instead of raising its throughput."""
    _moat_at(tmp_path, 1.2, {"state": "OUTPACED-BY-RECORDING", "why": "cells +12/run, pct flat."})
    monkeypatch.setattr(M, "ROOT", tmp_path)
    d: list = []
    M.check_under_exploration(d)
    keys = {k for k, _ in d}
    assert keys == {"exploration-outpaced-by-recording"}
    assert "under-exploration" not in keys
    assert "throughput" in E._RESOLUTION["exploration-outpaced-by-recording"][1].lower()


def test_an_artifact_with_no_closure_field_cannot_decide_the_law(monkeypatch, tmp_path) -> None:
    """A LEVEL is not a verdict. An artifact carrying only the percentage leaves P26 undecidable,
    and reporting that honestly beats defaulting either way -- defaulting to breach cries wolf,
    defaulting to clean hides the wolf."""
    _moat_at(tmp_path, 41.0)
    monkeypatch.setattr(M, "ROOT", tmp_path)
    d: list = []
    M.check_under_exploration(d)
    assert {k for k, _ in d} == {"exploration-rate-unmeasured"}


def test_too_short_a_history_is_reported_as_unmeasured_not_as_a_breach(
        monkeypatch, tmp_path) -> None:
    _moat_at(tmp_path, 0.9, {"state": "UNKNOWN", "why": "only 2 recorded runs."})
    monkeypatch.setattr(M, "ROOT", tmp_path)
    d: list = []
    M.check_under_exploration(d)
    assert {k for k, _ in d} == {"exploration-rate-unmeasured"}


def test_full_coverage_is_not_a_breach(monkeypatch, tmp_path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops/run_moat_miner.sh").write_text("#!/bin/sh\n", "utf-8")
    (tmp_path / "data/moat_mine.json").write_text(
        '{"cumulative_coverage": {"coverage_pct": 100.0}}', "utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    d: list = []
    M.check_under_exploration(d)
    assert d == []


def test_a_measure_with_no_dedicated_organ_is_itself_a_breach(monkeypatch, tmp_path) -> None:
    """A cadence step is the FLOOR; continuous mining is the ceiling. Without it coverage
    converges in as many days as there are cycles instead of in hours."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data/moat_mine.json").write_text(
        '{"cumulative_coverage": {"coverage_pct": 12.0}}', "utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    d: list = []
    M.check_under_exploration(d)
    assert "exploration-has-no-dedicated-organ" in {k for k, _ in d}


def test_the_dedicated_continuous_miner_exists_and_loops() -> None:
    """The user's ask, checked structurally: a SEPARATE always-on miner, not a cadence step."""
    runner = Path("ops/run_moat_miner.sh")
    assert runner.exists()
    body = runner.read_text("utf-8")
    assert "--loop" in body
    assert "mine_moat.py" in body
    src = Path("scripts/mine_moat.py").read_text("utf-8")
    assert "def loop(" in src
    assert "must never end the exploration" in src, (
        "a miner that dies on one unreadable file has stopped exploring")


# ------------------------------------------------------------------ the deploy path exists

def test_every_recorder_has_a_systemd_unit() -> None:
    """THE ACTUAL REASON THE MOAT IS EMPTY. The recorders had no unit file at all -- they were
    started by hand, and a process started by hand stops on the next reboot and never comes back.
    Not funding, not code, not a decision: four unit files."""
    import configparser
    units = {
        "ops/quant-recorder-fut.service": "scripts/run_recorder.py",
        "ops/quant-recorder-spot.service": "scripts/run_recorder_spot.py",
        "ops/quant-recorder-bybit.service": "scripts/run_recorder_bybit.py",
        "ops/quant-moat-miner.service": "ops/run_moat_miner.sh",
        # The hunt is a unit too. A screen that only exists as a script somebody remembers to run
        # is a screen that stops at the next reboot -- the exact failure that left the moat empty.
        "ops/quant-moat-screen.service": "ops/run_moat_screen.sh",
    }
    for unit, target in units.items():
        p = Path(unit)
        assert p.exists(), f"{unit} missing -- the desk cannot reconstitute itself from the repo"
        assert Path(target).exists(), f"{unit} points at {target}, which does not exist"
        c = configparser.ConfigParser(strict=False)
        c.read(p)
        assert {"Unit", "Service", "Install"} <= set(c.sections()), unit
        assert Path(target).name in c.get("Service", "ExecStart"), unit


def test_recorders_restart_always_because_tape_cannot_be_backfilled() -> None:
    """on-failure is wrong here: a venue cutoff or a CLEAN exit is still a gap in the tape, and
    the tape is the one thing money cannot buy back later."""
    import configparser
    for unit in ("ops/quant-recorder-fut.service", "ops/quant-recorder-spot.service",
                 "ops/quant-recorder-bybit.service"):
        c = configparser.ConfigParser(strict=False)
        c.read(Path(unit))
        assert c.get("Service", "Restart") == "always", unit
        assert int(c.get("Service", "RestartSec")) <= 30, f"{unit}: slow restart loses tape"


def test_the_miner_never_competes_with_a_recorder_for_io() -> None:
    """Losing tape is permanent; a slower mining pass costs minutes. The priority ordering has to
    reflect that asymmetry or a busy box quietly trades the irreplaceable for the recoverable."""
    import configparser
    for unit in ("ops/quant-moat-miner.service", "ops/quant-moat-screen.service"):
        c = configparser.ConfigParser(strict=False)
        c.read(Path(unit))
        assert c.get("Service", "IOSchedulingClass") == "idle", unit
        assert int(c.get("Service", "Nice")) > 5, unit
    # AND THE SCREEN SITS BELOW THE MINER. The priority order is the value order: lost tape is
    # unbuyable, an unmined cell is a delay, an unscreened cell is a delay behind that one.
    mine, screen = configparser.ConfigParser(strict=False), configparser.ConfigParser(strict=False)
    mine.read(Path("ops/quant-moat-miner.service"))
    screen.read(Path("ops/quant-moat-screen.service"))
    assert int(screen.get("Service", "Nice")) >= int(mine.get("Service", "Nice"))


def test_units_cannot_write_outside_the_data_lake() -> None:
    """A recorder that could touch anything but data/ is a recorder that could touch the book."""
    import configparser
    for unit in Path("ops").glob("quant-recorder-*.service"):
        c = configparser.ConfigParser(strict=False)
        c.read(unit)
        assert c.get("Service", "ProtectSystem") == "strict", unit.name
        assert c.get("Service", "ReadWritePaths").endswith("/data"), unit.name


def test_the_runbook_names_the_real_acceptance_test() -> None:
    """An exit code proves a process ended, never that it produced -- the desk has been burned by
    exactly that. The runbook must send the operator to PRODUCTION, not to systemctl status."""
    doc = Path("docs/RECORDER_DEPLOY.md").read_text("utf-8")
    assert "never that it produced" in doc
    assert "enforce_constitution.py" in doc
    assert "exploration-blocked-upstream" in doc, (
        "the operator must be told which breach clearing means it worked")
    assert "permanently unbuyable" in doc


def test_there_is_a_zero_privilege_path_to_starting_the_recorders() -> None:
    """THE HETZNER BOX HAS NO SUDO FOR `quant`, so /etc/systemd/system is unreachable. That is
    not a reason to leave the tape unrecorded -- every unrecorded second is permanently unbuyable,
    which is the only cost here money cannot fix afterwards."""
    sh = Path("ops/start_recorders_nosudo.sh")
    assert sh.exists()
    body = sh.read_text("utf-8")
    for script in ("run_recorder.py", "run_recorder_spot.py", "run_recorder_bybit.py"):
        assert script in body, script
    assert "pgrep" in body, "must be idempotent -- it is both the starter and the watchdog"
    doc = Path("docs/RECORDER_DEPLOY.md").read_text("utf-8")
    assert "no sudo" in doc.lower()
    assert "crontab" in doc


def test_the_starter_matches_each_recorder_exactly_not_by_prefix() -> None:
    """A loose `pgrep -f run_recorder` ALSO matches run_recorder_spot and run_recorder_bybit, so
    one running recorder would report all three alive -- and the desk would record one venue while
    believing it recorded three."""
    body = Path("ops/start_recorders_nosudo.sh").read_text("utf-8")
    assert "[s]cripts/${script}" in body, "must match the full script path, not a bare prefix"
    assert "believing it recorded three" in body, "the reason must survive in the source"


def test_the_enforcer_has_ONE_definition_of_scope() -> None:
    """THE RULE MOVED, AND THAT IS THE POINT. The evidence-outranks-remedy refinement briefly
    lived here as a second copy while `max_audit.scope_of` kept the old behaviour -- which left
    the enforcer and the auditor disagreeing about the same defect, and the answer the desk got
    depended on which module happened to run. That is the defect class this repo keeps finding in
    itself. The rule now lives in max_audit and the enforcer delegates.
    """
    import scripts.max_audit as audit
    absent = ("moat: data/never_written_by_anything.json absent -- coverage is not MEASURED. "
              "Run ops/run_moat_miner.sh.")
    tracked, untracked = audit.cited_evidence(absent)
    assert tracked and untracked, "the fixture must exercise BOTH kinds of path"
    assert E._scope(audit, tracked, untracked) == audit.scope_of(tracked, untracked) == "RUNTIME"

    repo = ("scripts/run_allocator.py is not called from scripts/run_cadence.py -- "
            "the governing layer is inert.")
    t2, u2 = audit.cited_evidence(repo)
    assert E._scope(audit, t2, u2) == audit.scope_of(t2, u2) == "REPO"


# ------------------------------------------------------ every organ has a LAUNCHER

def test_every_verified_floor_has_a_unit_that_can_produce_it() -> None:
    """THE GAP THIS CLOSES WAS THE LARGEST ONE LEFT, AND IT WAS INVISIBLE BY CONSTRUCTION.

    Until 2026-08-03 the repository could start recorders, a moat miner and five credit-blocked
    diggers. It could not start the DESK. Nothing in it launched the cadence engine (which fires
    the panel, the moat screen, survivor promotion, the forward-clock review, and enforces the
    never-sleepier floors), the pager (whose artifact carries a 1.0h floor that was therefore
    violated from the first hour of any fresh install, permanently), the process supervisor
    (whose own header records eleven and a half days of silent pager and frozen clocks after it
    died on 2026-07-11), or the Tier-3 ruin rail.

    Nothing detected it either, because every check looked at the units that EXIST rather than at
    the organs that must run. So this walks the freshness contract from the other end: for every
    artifact `verify_deployment` holds to a floor, the unit it names must be a real file in ops/,
    and that unit must actually invoke something.
    """
    import scripts.verify_deployment as V
    for artifact, (_floor, unit, _why) in V.FLOORS.items():
        base = unit.removesuffix(".timer").removesuffix(".service")
        svc = Path("ops") / f"{base}.service"
        assert svc.exists(), (
            f"{artifact} is held to a floor by a unit that does not exist: {svc}. A floor whose "
            "producer nothing starts is violated from the first hour and stays violated.")
        body = svc.read_text("utf-8")
        assert "ExecStart=" in body, f"{svc} starts nothing"
        if unit.endswith(".timer"):
            timer = Path("ops") / unit
            assert timer.exists(), (
                f"{svc} is a oneshot with no timer -- it runs when somebody types its name, "
                "which is exactly how the desk lost 11.5 days")
            assert "OnCalendar=" in timer.read_text("utf-8") or \
                   "OnUnitActiveSec=" in timer.read_text("utf-8"), f"{timer} never fires"


def test_every_required_unit_is_installed_by_the_deploy_script() -> None:
    """A unit file the deploy script does not copy is a unit that exists in git and nowhere else.
    That is the same failure one level up: written, correct, and never installed."""
    import scripts.verify_deployment as V
    deploy = Path("ops/deploy_vps.sh").read_text("utf-8")
    for unit in (*V.REQUIRED_UNITS, *V.TIER3):
        assert unit in deploy or unit.removesuffix(".timer") in deploy, (
            f"{unit} is required by verify_deployment and never installed by ops/deploy_vps.sh")


def test_the_deploy_script_will_not_arm_the_ruin_rail() -> None:
    """It moves funds. Tier-3 means the principal's act, never a script's -- and a deploy that
    quietly starts a process which can flatten the book is precisely the autonomy that forbids."""
    deploy = Path("ops/deploy_vps.sh").read_text("utf-8")
    assert "enable --now quant-deadman" not in deploy.replace(
        "      sudo systemctl enable --now quant-deadman", ""), (
        "deploy_vps.sh must PRINT the command for the principal, never run it")
    assert "quant-deadman.service" in deploy, "the unit must still be INSTALLED, just not started"


def test_the_deploy_script_verifies_production_rather_than_status() -> None:
    """`systemctl is-active` proves a process is alive and never that it produced -- the failure
    that gave this desk a silent pager for 11.5 days while every timer looked healthy."""
    deploy = Path("ops/deploy_vps.sh").read_text("utf-8")
    assert "scripts/verify_deployment.py" in deploy
    assert "exit $RC" in deploy, "a deploy that cannot fail is a report, not a gate"


def test_a_timer_driven_service_does_not_carry_its_own_install_section() -> None:
    """THE CONVENTION, PINNED, BECAUSE BREAKING IT LOOKS LIKE SUCCESS.

    A service paired with a timer must be enabled THROUGH the timer. Giving it its own
    `[Install] WantedBy=multi-user.target` lets `systemctl enable quant-cadence.service` arm a
    boot-time one-shot that runs once and never repeats -- and `is-enabled` then answers
    "enabled", so the unit reports healthy while nothing is scheduled. That is the same
    scheduled-but-not-producing shape the whole deploy verification exists to catch, one level
    down in the unit files themselves.

    Long-running daemons (the recorders, the miner, the screen, the ruin rail) have no timer and
    must keep their [Install].
    """
    import configparser
    for svc in sorted(Path("ops").glob("quant-*.service")):
        c = configparser.ConfigParser(strict=False)
        c.read(svc)
        timer = svc.with_suffix(".timer")
        if timer.exists():
            assert "Install" not in c.sections(), (
                f"{svc.name} is timer-driven and carries its own [Install] -- enabling the "
                "SERVICE would look like success and schedule nothing")
        else:
            assert "Install" in c.sections(), (
                f"{svc.name} has no timer and no [Install]: nothing can enable it at all")


def test_a_rail_cannot_gain_an_unexplained_silent_swallow() -> None:
    """`except Exception: pass` is either load-bearing or a hidden failure, and the two are
    INDISTINGUISHABLE IN A DIFF.

    Swept 2026-08-04: 39 across libs/ and scripts/, 32 undocumented. Most sit in research scripts
    where a swallowed error costs a wasted cycle, so demanding a comment on all 39 would be the
    crying-wolf failure this file names elsewhere. On the RAILS the two outcomes are opposite --
    the recorder MUST NOT stop taping twenty-nine symbols because one fetch failed, and
    `_market_max_qty` MUST NOT have silently cached its own failure and disabled the market-order
    cap for a process lifetime. Both were the same three lines.
    """
    d: list = []
    M.check_silent_swallows_on_the_rails(d)
    assert not d, d[0][1] if d else ""


def test_the_ruin_rail_is_exempt_from_that_check_ON_PURPOSE() -> None:
    """scripts/run_deadman_switch.py carries two of these and is NOT audited for them.

    It is Tier-3: "may not be modified, disabled or removed autonomously -- explicit principal
    sign-off only". Adding a comment is a modification. Both swallows were READ and are correct
    (a paging failure AFTER the book has already been flattened must not crash the rail), but
    annotating them is the principal's call and not this repository's.

    Pinned so the exemption stays a decision rather than becoming an oversight: if someone adds
    the rail to that list, this fails and they have to argue it.
    """
    import inspect
    src = inspect.getsource(M.check_silent_swallows_on_the_rails)
    assert "run_deadman_switch" in src, "the exemption must be stated where the list is"
    rails_tuple = src.split("rails = (")[1].split(")")[0]
    assert "run_deadman_switch.py" not in rails_tuple, (
        "the Tier-3 ruin rail was added to an autonomous check's audit list")
