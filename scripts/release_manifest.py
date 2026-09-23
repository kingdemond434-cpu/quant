#!/usr/bin/env python3
"""Seal, describe or verify the canonical live release. See `libs.ops.release`.

    python scripts/release_manifest.py --seal [--tested] [--by X]   # seal HEAD into RELEASE.json
    python scripts/release_manifest.py --seal --if-needed           # no-op when HEAD is already
                                                                    #   the sealed code (CI-safe)
    python scripts/release_manifest.py --verify                     # exit 1 if the tree drifted
    python scripts/release_manifest.py --identity                   # is HEAD the sealed code?
    python scripts/release_manifest.py                              # legacy: describe the
                                                                    #   working tree (not a seal)

THE SEAL IS ITS OWN COMMIT. After `--seal`, commit desks/mt5/data/RELEASE.json and NOTHING ELSE
("seal release <sha12>"): that commit's diff against its parent is exactly the manifest, which is
the one shape `accepts()` admits besides the sealed commit itself. Bundling the seal with code
recreates the defect this exists to end -- a manifest that names the commit before the one that
ships. `--if-needed` makes the step idempotent, so a CI job that runs on its own seal commit does
not seal again forever.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from libs.ops import release  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seal", action="store_true",
                    help="seal HEAD from its own blobs (then commit RELEASE.json alone)")
    ap.add_argument("--tested", action="store_true",
                    help="attest that the suite ran green on this SHA (CI passes this)")
    ap.add_argument("--by", default=None, help="who/what sealed (default: GITHUB_ACTOR|operator)")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="seal even when tracked files differ from HEAD (recorded, not hidden)")
    ap.add_argument("--if-needed", action="store_true",
                    help="with --seal: do nothing when HEAD is already the sealed code")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--identity", action="store_true",
                    help="is HEAD accepted by the written release (the SHA rule only; --verify "
                         "adds the on-disk hashes, mt5desk/release_identity.py is the box's "
                         "full verdict)? exit 1 if not")
    ap.add_argument("--root", type=Path, default=None, help="repository root (default: this one)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.verify:
        v = release.verify(root=a.root)
        print(json.dumps(v, indent=1) if a.json else
              f"release {v.get('release_id')}: {'OK' if v['ok'] else 'DRIFT'} -- {v['why']}"
              f" ({v.get('identity', '')})")
        for k, (was, now) in (v.get("diffs") or {}).items():
            print(f"  {k}: {was} -> {now}")
        return 0 if v["ok"] else 1

    if a.identity or (a.seal and a.if_needed):
        rec = release.load(a.root)
        head = release.git_head(a.root)
        ok, why, code = (release.accepts(head, rec, root=a.root) if rec is not None
                         else (False, "no RELEASE.json", []))
        if a.identity:
            print(json.dumps({"ok": ok, "running_sha": head, "why": why, "code_paths": code},
                             indent=1) if a.json else f"identity {'OK' if ok else 'REFUSED'}: {why}")
            return 0 if ok else 1
        if ok:
            print(f"seal not needed: {why}")
            return 0

    if a.seal:
        try:
            d = release.seal(root=a.root, tested=a.tested, by=a.by, allow_dirty=a.allow_dirty)
        except RuntimeError as exc:
            print(f"SEAL REFUSED: {exc}")
            return 2
        print(json.dumps(d, indent=1) if a.json else
              f"release {d['release_id']} sealed: code_sha={d['code_sha'][:12]} "
              f"parent={str(d['parent_sha'])[:12]} money_path={d['money_path_hash']} "
              f"immutable={(d.get('immutable_manifest') or {}).get('sha256_16')} "
              f"tested={'yes' if d['tested_sha'] else 'no'} dirty={len(d['worktree_dirty'])}"
              f"\n  now commit {release.RELEASE_REL} ALONE: \"seal release {d['code_sha'][:12]}\"")
        return 0

    d = release.build(write=True, root=a.root)
    print(json.dumps(d, indent=1) if a.json else
          f"release {d['release_id']} described (NOT sealed): sha={d['live_sha'][:12]} "
          f"money_path={d['money_path_hash']} allocator={d['allocator_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
