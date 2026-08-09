#!/usr/bin/env python3
"""Claim, heartbeat, checkpoint or transfer the shared Claude/Codex control plane."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.controller_continuity import (  # noqa: E402
    ControllerLeaseError,
    checkpoint,
    claim,
    heartbeat,
    read_state,
    release,
    transfer,
)


def _git_summary() -> dict[str, object]:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=ROOT, text=True, capture_output=True, timeout=10, check=False
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    return {
        "branch": run("branch", "--show-current"),
        "head": run("rev-parse", "HEAD"),
        "dirty_paths": run("status", "--short").splitlines(),
        "frontier_handoff": "data/overnight_frontier_handoff.json",
        "completion_state": "data/completion_ledger_status.json",
        "research_memory": "data/decision_ledger.json",
        "candidate_queue": "data/hypothesis_queue.jsonl",
    }


def _credentials(args: argparse.Namespace) -> tuple[str, int, str]:
    controller = args.controller or os.environ.get("QUANT_CONTROLLER", "")
    token = args.token or os.environ.get("QUANT_CONTROLLER_TOKEN", "")
    epoch_text = str(args.epoch or os.environ.get("QUANT_CONTROLLER_EPOCH", ""))
    if not controller or not token or not epoch_text:
        raise ValueError(
            "controller, epoch and token are required (arguments or QUANT_CONTROLLER_*)"
        )
    return controller, int(epoch_text), token


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("status", "claim", "heartbeat", "checkpoint", "transfer", "release")
    )
    parser.add_argument("--controller")
    parser.add_argument("--epoch", type=int)
    parser.add_argument("--token")
    parser.add_argument("--successor")
    parser.add_argument("--ttl-seconds", type=int, default=900)
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    try:
        if args.action == "status":
            result = read_state()
        elif args.action == "claim":
            if not args.controller:
                raise ValueError("--controller is required to claim")
            result = claim(args.controller, ttl_seconds=args.ttl_seconds)
        else:
            controller, epoch, token = _credentials(args)
            if args.action == "heartbeat":
                result = heartbeat(controller, epoch, token, ttl_seconds=args.ttl_seconds)
            elif args.action == "checkpoint":
                result = checkpoint(controller, epoch, token, {**_git_summary(), "note": args.note})
            elif args.action == "transfer":
                if not args.successor:
                    raise ValueError("--successor is required to transfer")
                result = transfer(
                    controller,
                    epoch,
                    token,
                    args.successor,
                    {**_git_summary(), "note": args.note},
                    ttl_seconds=args.ttl_seconds,
                )
            else:
                result = release(controller, epoch, token)
    except (ControllerLeaseError, ValueError) as exc:
        print(json.dumps({"status": "REFUSED", "reason": str(exc)}))
        return 2
    print(json.dumps(result, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
