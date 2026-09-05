"""Pull gate certificates from VPS to C:\opt\quant\desks\mt5\reports\.

Run after every gauntlet sweep. With the merge fix in place these persist
through sweeps — the sweep logic excludes C:\opt\quant.
"""
import subprocess
import os
from pathlib import Path

VPS = "quant@95.216.191.70"
VPS_BASE = "/home/quant/quant-platform/desks/mt5"
WIN_BASE = Path(r"C:\opt\quant\desks\mt5")


def pull(vps_rel: str, win_rel: str) -> bool:
    win_path = WIN_BASE / win_rel
    win_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["scp", "-o", "ConnectTimeout=15",
           VPS + ":" + VPS_BASE + "/" + vps_rel, str(win_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    ok = win_path.exists()
    if ok:
        print("  OK  " + win_rel + " (" + str(win_path.stat().st_size) + " bytes)")
    else:
        print("  SKIP " + win_rel)
    return ok


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
