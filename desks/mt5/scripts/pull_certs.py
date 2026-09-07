r"""Pull gate certificates from VPS to C:\opt\quant\desks\mt5\reports\.

Run after every gauntlet sweep. With the merge fix in place these persist
through sweeps — the sweep logic excludes C:\opt\quant.
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

VPS = "quant@95.216.191.70"
VPS_BASE = "/home/quant/quant-platform/desks/mt5"
WIN_BASE = Path(r"C:\opt\quant\desks\mt5")


def pull(vps_rel: str, win_rel: str) -> bool:
    win_path = WIN_BASE / win_rel
    win_path.parent.mkdir(parents=True, exist_ok=True)
    # Never copy over live evidence: scp may truncate its destination before failing.
    # An existing destination is not proof this transfer succeeded.
    fd, name = tempfile.mkstemp(prefix="." + win_path.name + ".", suffix=".incoming",
                                dir=win_path.parent)
    os.close(fd)
    incoming = Path(name)
    try:
        cmd = ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
               "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3",
               VPS + ":" + VPS_BASE + "/" + vps_rel, str(incoming)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            print(f"  FAILED {win_rel}: transfer exit {result.returncode}; kept existing evidence")
            return False
        value = json.loads(incoming.read_text("utf-8-sig"))
        if not isinstance(value, (dict, list)):
            raise ValueError("expected a JSON object or array")
        os.replace(incoming, win_path)
        print(f"  OK  {win_rel} ({win_path.stat().st_size} bytes)")
        return True
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"  FAILED {win_rel}: {type(exc).__name__}; kept existing evidence")
        return False
    finally:
        incoming.unlink(missing_ok=True)


def main():
    print("Pulling gate certificates from VPS...")
    pulled = 0

    # Authority files
    for f in [
        ("reports/UNIVERSAL_SURVIVORS.json", "reports/UNIVERSAL_SURVIVORS.json"),
        ("data/UNIVERSAL_SURVIVORS.canon.json", "data/UNIVERSAL_SURVIVORS.canon.json"),
    ]:
        if pull(f[0], f[1]):
            pulled += 1

    # All gate report files
    cmd = ["ssh", "-o", "ConnectTimeout=15", VPS,
           "ls " + VPS_BASE + "/reports/universal_gates_*.json 2>/dev/null"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    for line in r.stdout.strip().split("\n"):
        if not line.strip():
            continue
        fname = os.path.basename(line.strip())
        if pull("reports/" + fname, "reports/" + fname):
            pulled += 1

    # Gauntlet certification
    pull("reports/gauntlet_certification.json", "reports/gauntlet_certification.json")

    print(f"\n{pulled} certificates ported to {WIN_BASE}")


if __name__ == "__main__":
    main()
