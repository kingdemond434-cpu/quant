"""A DECLARED MEMORY CEILING ABOVE PHYSICAL RAM IS WORSE THAN NO CEILING.

WHAT HAPPENED (gap-fixer 2026-08-29). `memecoin-shadow.service` -- a Solana project living in
`~/.local/opt`, outside this repo and outside the mandated MT5 universe -- carried
`MemoryMax=4G`, with a comment stating the intent exactly: "a ceiling so a leak takes the desk
down rather than the machine". This box has 3815 MB of RAM and ZERO swap. A 4G cgroup ceiling is
above physical memory, so it can NEVER bind: the cgroup limit never fires, and the kernel's
GLOBAL oom-killer runs instead and picks whichever process is largest at that instant.

MEASURED over 7 days in `data/cro_ai_logs/unit_deaths.jsonl`: that service recorded 62 oom-kills,
and 73% of the 73 desk-organ oom-kills landed within 3 minutes of one of its deaths --
quant-cadence 40 times, the auto-push guard 19, quant-gap-wirer 4, quant-external-pipeline 3,
quant-seat-dataaxis 3, and one each for the brain chain, the blindspot autofix, the mt5 suite
and the prospector seat. The desk read those as eight unrelated unit bugs for a week, because
each unit's journal shows only its own death.

The reason it stayed invisible is the reason this test exists: in `systemctl show` an unbindable
ceiling and a real one are the same field with a bigger number. The check is one comparison
nobody had written.

NO SWAP is what makes this sharp here -- with swap the kernel has somewhere to go first, and the
same misconfiguration degrades instead of killing.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _module():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("uh", ROOT / "scripts" / "check_unit_health.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_check_exists_and_is_called_by_main() -> None:
    """A fence nobody calls always returns True -- a lesson already on this desk's tab."""
    mod = _module()
    assert hasattr(mod, "check_memory_ceilings")
    src = (ROOT / "scripts" / "check_unit_health.py").read_text("utf-8")
    body = src[src.index("def main(") :]
    assert "check_memory_ceilings()" in body, (
        "check_memory_ceilings is defined but main() never calls it -- walk the call graph, a "
        "one-hop grep proves a name exists, never that the code path runs"
    )


def test_an_unbindable_ceiling_is_reported(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The defect: MemoryMax above RAM+swap. Must be NAMED, with the box's real budget."""
    mod = _module()

    def fake_run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
        if "list-unit-files" in cmd:
            return 0, "leaky.service enabled enabled\nfine.service enabled enabled\n"
        if "show" in cmd and "leaky.service" in cmd:
            return 0, "MemoryMax=99999999999"
        return 0, "MemoryMax=infinity"

    monkeypatch.setattr(mod, "_run", fake_run)
    found = mod.check_memory_ceilings()
    assert len(found) == 1, found
    assert "leaky.service" in found[0]
    assert "never bind" in found[0], "the finding must say WHY, not merely that a number is big"
    # The honest alternative must not be flagged: `infinity` claims no ceiling and implies none.
    assert "fine.service" not in " ".join(found)


def test_a_ceiling_that_actually_binds_is_not_a_finding(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The other direction: a fence that fires on correct config gets switched off (L1.43)."""
    mod = _module()

    def fake_run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
        if "list-unit-files" in cmd:
            return 0, "bounded.service enabled enabled\n"
        return 0, "MemoryMax=104857600"  # 100 MB, below any real box

    monkeypatch.setattr(mod, "_run", fake_run)
    assert mod.check_memory_ceilings() == []


def test_an_unreadable_meminfo_is_unmeasured_never_clean(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """L1.28a. 'we cannot count it' and 'it is fine' must never render identically."""
    mod = _module()
    monkeypatch.setattr(mod, "_run", lambda cmd, timeout=60: (1, ""))
    found = mod.check_memory_ceilings()
    assert found and "UNMEASURED" in found[0], found


def test_this_box_has_no_unbindable_ceiling_left() -> None:
    """The live assertion. Reads the real host, so it fails if one is reintroduced anywhere."""
    mod = _module()
    meminfo = Path("/proc/meminfo").read_text("utf-8")
    total = int(re.search(r"MemTotal:\s+(\d+)", meminfo).group(1))  # type: ignore[union-attr]
    assert total > 0
    assert mod.check_memory_ceilings() == [], (
        "a user service declares a memory ceiling this box cannot supply; it reads as protection "
        "and provides none"
    )
