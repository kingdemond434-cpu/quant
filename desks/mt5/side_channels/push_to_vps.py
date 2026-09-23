#!/usr/bin/env python3
"""
VPS Push Script — pushes all side-channel code and data to VPS.

Replaces the old sync_to_vps.ps1 with a proper Python script that:
1. Copies all new side_channel miners to VPS
2. Updates git with code changes (not runtime state)
3. Pushes to both code branch and mt5-state branch appropriately
"""

import subprocess
import sys
import os
import time
from pathlib import Path
from datetime import datetime, timezone

# Local paths
LOCAL_BASE = Path(r"C:\Users\dell\mt5-research")
VPS_HOST = "quant@95.216.191.70"
VPS_BASE = "/home/quant/quant-platform"

# Directories to sync (CODE ONLY - no runtime state)
CODE_DIRS = [
    "desks/mt5/side_channels",
    "desks/mt5/pipeline",
    "desks/mt5/policy",
    "desks/mt5/hypotheses",
    "desks/mt5/strategies",
    "desks/mt5/experiments",
    "desks/mt5/archive",
    "desks/mt5/research",  # Updated research files
    "desks/mt5/mt5desk",   # Updated gateway, engine
    "libs",                # Updated libs
    "scripts",             # Updated scripts
    "ops",                 # Updated ops
    "tests",               # Updated tests
]

# Files to sync (config, documentation)
CONFIG_FILES = [
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "pyproject.toml",
    ".gitignore",
    "requirements.txt",
    "requirements-dev.txt",
]

# Runtime state files (go to mt5-state branch only)
STATE_FILES = [
    "desks/mt5/data/universe",
    "desks/mt5/reports",
    "desks/mt5/logs",
    "desks/mt5/data/gateway_state.json",
    "desks/mt5/data/sleeves.json",
    "desks/mt5/data/regime_state.json",
    "desks/mt5/data/shadow_health.json",
    "desks/mt5/data/sync_marker.json",
    "desks/mt5/data/daily_cycle_state.json",
]

def run_cmd(cmd, cwd=None, check=True):
    """Run command and return result."""
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result

def rsync_to_vps(local_path, remote_path, exclude=None):
    """Rsync a path to VPS."""
    cmd = ["rsync", "-avz", "--progress"]
    if exclude:
        for pattern in exclude:
            cmd.extend(["--exclude", pattern])
    cmd.extend([str(local_path) + "/", f"{VPS_HOST}:{remote_path}/"])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode == 0

def push_git_changes():
    """Push git changes to VPS."""
    print("\n=== Pushing git changes ===")

    # Local git status
    run_cmd("git status --short", cwd=LOCAL_BASE)

    # Add code changes
    run_cmd("git add desks/mt5/side_channels desks/mt5/pipeline desks/mt5/policy desks/mt5/hypotheses desks/mt5/strategies desks/mt5/experiments desks/mt5/archive", cwd=LOCAL_BASE)
    run_cmd("git add desks/mt5/research/*.py desks/mt5/mt5desk/*.py", cwd=LOCAL_BASE)
    run_cmd("git add libs scripts ops tests", cwd=LOCAL_BASE)
    run_cmd("git add README.md CLAUDE.md AGENTS.md .gitignore", cwd=LOCAL_BASE)

    # Commit
    msg = f"feat: side-channel alpha factory — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
    run_cmd(f'git commit -m "{msg}"', cwd=LOCAL_BASE)

    # Push to origin
    run_cmd("git push origin desk-sync-clean", cwd=LOCAL_BASE)

    # Push to VPS repo
    vps_cmd = f"cd {VPS_BASE} && git fetch origin && git merge origin/desk-sync-clean --no-edit"
    run_cmd(f'ssh {VPS_HOST} "{vps_cmd}"')

def push_mt5_state():
    """Push runtime state to mt5-state branch on VPS."""
    print("\n=== Pushing runtime state to mt5-state branch ===")

    # Create temp bundle
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle = Path(tmpdir) / "mt5_state_bundle"
        bundle.mkdir()

        # Copy state files
        for f in STATE_FILES:
            src = LOCAL_BASE / f
            if src.exists():
                dst = bundle / f
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    run_cmd(f'robocopy "{src}" "{dst}" /E /COPY:DAT /R:1 /W:1')
                else:
                    run_cmd(f'copy "{src}" "{dst}"')

        # Rsync to VPS mt5-state location
        rsync_to_vps(bundle, VPS_BASE)

        # On VPS: commit to mt5-state branch
        vps_cmd = f"""
        cd {VPS_BASE} &&
        git checkout mt5-state &&
        git add desks/mt5/data desks/mt5/reports desks/mt5/logs &&
        git commit -m "mt5 runtime state sync {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}" &&
        git push origin mt5-state --force &&
        git checkout desk-sync-clean
        """
        run_cmd(f'ssh {VPS_HOST} "{vps_cmd}"')

def main():
    print("=" * 60)
    print("VPS PUSH — Side-Channel Alpha Factory Deployment")
    print("=" * 60)
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Local: {LOCAL_BASE}")
    print(f"VPS: {VPS_HOST}:{VPS_BASE}")

    # 1. Sync code directories
    print("\n=== Syncing code directories ===")
    for dir_name in CODE_DIRS:
        local_dir = LOCAL_BASE / dir_name
        remote_dir = f"{VPS_BASE}/{dir_name}"
        if local_dir.exists():
            print(f"  Syncing {dir_name}...")
            rsync_to_vps(local_dir, remote_dir, exclude=["__pycache__", "*.pyc", ".pytest_cache", "*.log"])
        else:
            print(f"  Skipping {dir_name} (not found locally)")

    # 2. Sync config files
    print("\n=== Syncing config files ===")
    for f in CONFIG_FILES:
        src = LOCAL_BASE / f
        if src.exists():
            run_cmd(f'scp "{src}" {VPS_HOST}:{VPS_BASE}/')

    # 3. Push git changes (code branch)
    push_git_changes()

    # 4. Push runtime state (mt5-state branch)
    push_mt5_state()

    print("\n=== VPS PUSH COMPLETE ===")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

if __name__ == "__main__":
    main()