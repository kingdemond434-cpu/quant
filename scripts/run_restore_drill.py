"""RESTORE DRILL -- prove the forward evidence can actually come back, weekly.

A backup verified only by manifest hashes proves the COPY is intact, not that a restore
produces working artifacts. This drill restores the forward-evidence stores from the latest
backup into a temp directory, parses each as its consumer would, checks row counts against the
live copies (restored >= 90% of live -- a backup that lost a third of the clocks is not a
backup), and writes the verdict where the pulse can see it. It never touches live paths.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "desks" / "mt5" / "reports" / "restore_drill.json"
STORES = {
    "forward_registry": ("desks/mt5/data/sleeve_registry.json", "sleeves"),
    "shadow_state": ("desks/mt5/reports/shadow/shadow_state.json", None),
    "universal_canon": ("desks/mt5/reports/UNIVERSAL_SURVIVORS.json", "survivors"),
}


def _rows(doc, key):
    if not isinstance(doc, dict):
        return 0
    inner = doc.get(key) if key else doc
    return len(inner) if isinstance(inner, dict) else 0


def main() -> int:
    backup_root = ROOT / "backups" / "moat"
    candidates = ([backup_root / "manifest.json"]
                  if (backup_root / "manifest.json").exists()
                  else sorted(backup_root.glob("*/manifest.json"), reverse=True))
    verdict = {"drilled_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
               "stores": {}, "status": "PASS"}
    if not candidates:
        verdict["status"] = "NO_BACKUP_FOUND"
        verdict["why"] = f"no manifest under {backup_root} -- the drill cannot rehearse"
    else:
        src_dir = candidates[0].parent
        verdict["backup"] = str(src_dir)
        with tempfile.TemporaryDirectory(prefix="restore_drill_") as tmp:
            for name, (rel, key) in STORES.items():
                # file stores land FLAT, named by store key (backups/moat/forward_registry IS
                # the file); tree stores get directories. Try store-name file first.
                backed = src_dir / name
                if backed.is_dir() or not backed.exists():
                    alt = src_dir / name / Path(rel).name
                    backed = alt if alt.exists() else (src_dir / Path(rel).name)
                row = {"backed_up": backed.exists()}
                if backed.exists():
                    dest = Path(tmp) / Path(rel).name
                    shutil.copy2(backed, dest)
                    try:
                        restored = json.loads(dest.read_text("utf-8"))
                        live = json.loads((ROOT / rel).read_text("utf-8"))
                        r_n, l_n = _rows(restored, key), _rows(live, key)
                        row.update({"parses": True, "restored_rows": r_n, "live_rows": l_n,
                                    "sufficient": l_n == 0 or r_n >= l_n * 0.9})
                        if not row["sufficient"]:
                            verdict["status"] = "FAIL"
                    except (OSError, ValueError) as exc:
                        row.update({"parses": False, "why": str(exc)[:120]})
                        verdict["status"] = "FAIL"
                else:
                    verdict["status"] = "FAIL"
                verdict["stores"][name] = row
    OUT.write_text(json.dumps(verdict, indent=1), "utf-8")
    print(f"restore drill: {verdict['status']} -> {OUT}")
    return 0 if verdict["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
