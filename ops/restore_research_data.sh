#!/usr/bin/env bash
# The other half of path (b): unpack a research snapshot into data/ on a fresh clone.
#
# VERIFIES BEFORE IT UNPACKS. A truncated transfer produces a snapshot that unpacks cleanly and is
# missing half the tape, and a study run against it reports a smaller sample rather than an error.
# That is the worst failure available here: a number computed on partial data enters the funnel
# wearing the same vocabulary as one computed on all of it. So the checksum is checked if present,
# and the manifest is verified file-by-file after extraction.
#
#   bash ops/restore_research_data.sh data/snapshots/research-snapshot-<stamp>.tar.zst
#   bash ops/restore_research_data.sh <file> --dry-run     # list what it would place, place nothing
set -euo pipefail
cd "$(dirname "$0")/.."

ARCHIVE="${1:?usage: restore_research_data.sh <snapshot.tar.zst|.tar.gz> [--dry-run]}"
DRY="${2:-}"
[ -f "$ARCHIVE" ] || { echo "no such archive: $ARCHIVE"; exit 1; }

if [ -f "${ARCHIVE}.sha256" ]; then
  echo "== checksum =="
  sha256sum -c "${ARCHIVE}.sha256" || { echo "CHECKSUM FAILED -- transfer was truncated or the "\
"archive was modified. Re-fetch; do NOT run a study against this."; exit 1; }
else
  echo "== checksum == (no .sha256 alongside; cannot verify the transfer)"
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "== extracting =="
case "$ARCHIVE" in
  *.tar.zst) zstd -dc "$ARCHIVE" | tar -C "$STAGE" -xf - ;;
  *.tar.gz)  tar -C "$STAGE" -xzf "$ARCHIVE" ;;
  *) echo "unrecognised archive format: $ARCHIVE"; exit 1 ;;
esac

ROOT="$(find "$STAGE" -maxdepth 1 -mindepth 1 -type d | head -1)"
[ -n "$ROOT" ] || { echo "archive has no top-level directory"; exit 1; }

if [ -f "$ROOT/MANIFEST.json" ]; then
  echo "== manifest =="
  python3 - "$ROOT" <<'PY'
import hashlib, json, os, sys
root = sys.argv[1]
m = json.load(open(os.path.join(root, "MANIFEST.json")))
bad, missing = [], []
for row in m["files"]:
    p = os.path.join(root, row["path"])
    if not os.path.exists(p):
        missing.append(row["path"]); continue
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest()[:16] != row["sha256"]:
        bad.append(row["path"])
print(f"  created {m['created']}  files {m['n_files']}  {m['total_bytes'] / 1e6:.1f} MB")
if missing or bad:
    print(f"  INCOMPLETE: {len(missing)} missing, {len(bad)} corrupt")
    for p in (missing + bad)[:10]:
        print(f"    ! {p}")
    raise SystemExit(1)
print("  every file present and intact")
PY
fi

# Refuse to place anything under data/secrets even if a hand-built archive contains it. The
# snapshot side already excludes them; this side does not trust that, because the archive may not
# have come from the snapshot side.
if find "$ROOT" -path '*/secrets/*' -type f | grep -q .; then
  echo "REFUSING: this archive contains data/secrets paths. Credentials are placed by hand, "\
"per host -- see scripts/check_credentials.py."
  exit 1
fi

if [ "$DRY" = "--dry-run" ]; then
  echo "== would place (dry run) =="
  (cd "$ROOT" && find data -type f | head -40)
  echo "  ... $(cd "$ROOT" && find data -type f | wc -l) file(s) total"
  exit 0
fi

echo "== placing into data/ =="
mkdir -p data
cp -pr "$ROOT/data/." data/
# RETIRED 2026-09-05 under the MT5 universe mandate (2026-08-18): these two lines told the
# operator to run scripts/run_failed_breakout_study.py and scripts/screen_moat.py, both deleted
# with the crypto-exchange desk. A restore script that ends by naming two commands which fail
# teaches the operator the restore itself failed, which it did not.
echo "  done. Registered studies live in ops/run_study_on_vps.sh; its registry is currently"
echo "  empty by design -- no pre-registered study runs on this box under the MT5 mandate yet."
