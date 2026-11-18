"""The Paperclip company package (agentcompanies/v1), DERIVED from `roles.py`.

    python -c "from libs.research.paperclip_lab.company import write_package; write_package()"

Edit roles.py, never the markdown; `tests/research/test_paperclip_lab.py` fails when the committed
package under ops/paperclip/company drifts from what this writes. Every agent runs on Paperclip's
`process` adapter as `scripts/paperclip_lab_run.py --role <name>`, a worker with no shell tool and
no file writes beyond its bundle. CLI-agent adapters (claude_local, codex_local, cursor, ...) are
not used: several default to approval bypass, and the company needs none of their powers.
"""
from __future__ import annotations

from pathlib import Path

from libs.research.paperclip_lab.roles import RED_TEAM_MISSION, ROLES

ROOT = Path(__file__).resolve().parents[3]


def write_package(root: Path = ROOT) -> int:
    """Regenerate the package; returns the number of agents written."""
    out_dir = root / "ops" / "paperclip" / "company"
    (out_dir / "agents").mkdir(parents=True, exist_ok=True)
    (out_dir / "COMPANY.md").write_text(
        "---\nname: Quant Alpha Research Company\nslug: quant-alpha-research\n"
        "schema: agentcompanies/v1\ndescription: Isolated, free-model research company that "
        "donates exact MT5 cells to the desk's canonical gauntlet. Owns no verdict and no "
        "capital.\n---\n\nThe company proposes; the desk's sealed gauntlet judges; the desk's "
        "allocator owns capital. Output leaves only through the narrow donation gateway "
        "(libs/research/paperclip_lab/contract.py), re-screened on the box.\n", "utf-8")
    yaml = ["schema: paperclip/v1", "agents:"]
    for r in ROLES:
        d = out_dir / "agents" / r.name
        d.mkdir(parents=True, exist_ok=True)
        (d / "AGENTS.md").write_text(
            f"---\nname: {r.name}\ntitle: {r.lane} lab\nreportsTo: null\n---\n\n{r.mission}\n",
            "utf-8")
        yaml += [f"  {r.name}:", "    adapter:", "      type: process", "      config:",
                 f"        command: python scripts/paperclip_lab_run.py --role {r.name} "
                 f"--calls 1 --out out/{r.name}.json",
                 "        timeoutSec: 600", "        dangerouslySkipPermissions: false",
                 "    runtime:", "      heartbeat:", "        enabled: true",
                 "        intervalSec: 3600"]
    d = out_dir / "agents" / "red_team"
    d.mkdir(parents=True, exist_ok=True)
    (d / "AGENTS.md").write_text(
        f"---\nname: red_team\ntitle: pre-gauntlet red team\nreportsTo: null\n---\n\n"
        f"{RED_TEAM_MISSION}\n", "utf-8")
    (out_dir / ".paperclip.yaml").write_text("\n".join(yaml) + "\n", "utf-8")
    return len(ROLES) + 1

