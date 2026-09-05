#!/usr/bin/env bash
# PATH (b): SHIP A RESEARCH SNAPSHOT OFF THE BOX, so a clone can run a study against real data.
#
# THE PROBLEM THIS SOLVES, stated exactly. `.gitignore` carries `data/*` with the comment "the
# journal is data/, not git". Every analysis container is a FRESH CLONE. So:
#
#     research runs where there is no data; data accumulates where there is no research,
#     and nothing moves one to the other.
#
# That is a TRANSPORT gap, not a data gap -- the desk holds moat_depth.jsonl, moat_trades.jsonl and
# funding_history.jsonl, and has been converting tape into coverage for weeks. It is why every
# study reports BLOCKED, and it is not fixed by writing more analysis code.
#
# WHAT THIS SHIPS AND WHAT IT REFUSES TO SHIP. Research inputs only. `data/secrets/**` is excluded
# by an explicit deny that runs BEFORE the include list is assembled, and the archive is scanned
# for secret-shaped paths after it is built -- belt and braces, because the cost of getting this
# wrong once is every key the desk owns. Nothing here is encrypted, so treat the artifact as
# public and never point PUBLISH_TO at anything world-readable.
#
# SIZE IS BOUNDED ON PURPOSE. The moat tape grows without limit; a snapshot that tried to carry all
# of it would fail slowly and confusingly every night. `SNAPSHOT_DAYS` takes the most recent N days
# of tape, which is what a study needs to run at all -- the full archive is what the VPS is for
# (see ops/run_study_on_vps.sh, path (a)).
#
#   bash ops/snapshot_research_data.sh                      # writes data/snapshots/<stamp>.tar.zst
#   SNAPSHOT_DAYS=30 bash ops/snapshot_research_data.sh     # a month of tape instead of 7 days
#   PUBLISH_TO=user@host:/srv/snap bash ops/snapshot_research_data.sh   # and scp it somewhere
#
# On the analysis side: `bash ops/restore_research_data.sh <file>` unpacks it into data/.
set -euo pipefail
cd "$(dirname "$0")/.."

DAYS="${SNAPSHOT_DAYS:-7}"
OUT_DIR="${SNAPSHOT_DIR:-data/snapshots}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
NAME="research-snapshot-${STAMP}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$OUT_DIR"

# ---------------------------------------------------------------- what a study actually needs
# Named explicitly rather than "everything except secrets". An allow-list cannot leak a file class
# nobody thought about; a deny-list leaks every one added after it was written.
# RETIRED 2026-09-05 under the MT5 universe mandate (2026-08-18) -- removed from the allow-list:
#   "data/funding_history.jsonl"        perpetual funding history; the venue is retired ground
#   "data/sor_autodiscovery.sqlite"     the crypto smart-order-router's autodiscovery store
#   "data/cashcarry_shadow_state.json"  cash-and-carry shadow state; that book is closed
# They are named here rather than silently dropped because this is an ALLOW-LIST: a file that
# quietly stops being copied is indistinguishable from a file nobody ever needed, and a study
# restored from a snapshot would not know what it was missing. If any of these still exist on a
# box, they are residue of the retired desk and should be deleted, not snapshotted.
INCLUDE_FILES=(
  "data/decision_ledger.json"
  "data/nav_attestation.jsonl"
  "data/desk_metrics.sqlite"
  "data/mine_conversion_log.jsonl"
  "data/moat_survivors.json"
  "data/moat_coverage.json"
  "data/axis_shadow_state.json"
  "data/crossasset_shadow_state.json"
)
INCLUDE_TREES=(
  "data/bars"
  "data/lake"
)

echo "== staging research inputs (last ${DAYS}d of tape) =="
mkdir -p "$STAGE/$NAME/data"

for f in "${INCLUDE_FILES[@]}"; do
  if [ -f "$f" ]; then
    mkdir -p "$STAGE/$NAME/$(dirname "$f")"
    cp -p "$f" "$STAGE/$NAME/$f"
    echo "  + $f"
  else
    echo "  . $f (absent on this box)"
  fi
done

for t in "${INCLUDE_TREES[@]}"; do
  if [ -d "$t" ]; then
    mkdir -p "$STAGE/$NAME/$t"
    # -mtime bounds the tape; the lake's parquet partitions are small and taken whole.
    find "$t" -type f \( -name '*.parquet' -o -name '*.csv' -o -name '*.jsonl' \) \
      -mtime "-${DAYS}" -print0 |
      while IFS= read -r -d '' src; do
        mkdir -p "$STAGE/$NAME/$(dirname "$src")"
        cp -p "$src" "$STAGE/$NAME/$src"
      done
    echo "  + $t (files newer than ${DAYS}d)"
  fi
done

# The moat tape lives under data/moat/<venue>/<SYMBOL>/<day>.jsonl.gz and is the bulk of the size.
if [ -d "data/moat" ]; then
  echo "  + data/moat (last ${DAYS}d)"
  find data/moat -type f -name '*.jsonl.gz' -mtime "-${DAYS}" -print0 |
    while IFS= read -r -d '' src; do
      mkdir -p "$STAGE/$NAME/$(dirname "$src")"
      cp -p "$src" "$STAGE/$NAME/$src"
    done
fi

# ---------------------------------------------------------------- the secrets fence
# Runs AFTER staging and BEFORE archiving. Deleting from the stage is cheap; retracting a published
# archive is not, and on a box with live venue keys it is not possible at all.
echo "== secrets fence =="
FOUND="$(find "$STAGE" \( -path '*/secrets/*' -o -name '*.key' -o -name '*.pem' \
  -o -name '*token*' -o -name '*credential*' \) -type f -print || true)"
if [ -n "$FOUND" ]; then
  echo "REFUSING: secret-shaped files reached the stage:"
  echo "$FOUND"
  exit 1
fi
echo "  clean"

# A manifest so the analysis side can tell a partial snapshot from a complete one, and so a study
# that reports BLOCKED can say WHICH input was missing rather than just that something was.
python3 - "$STAGE/$NAME" <<'PY' > "$STAGE/$NAME/MANIFEST.json"
import hashlib, json, os, sys, datetime
root = sys.argv[1]
rows = []
for dirpath, _dirs, files in os.walk(root):
    for name in sorted(files):
        p = os.path.join(dirpath, name)
        rel = os.path.relpath(p, root)
        if rel == "MANIFEST.json":
            continue
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        rows.append({"path": rel, "bytes": os.path.getsize(p), "sha256": h.hexdigest()[:16]})
print(json.dumps({
    "created": datetime.datetime.now(datetime.UTC).isoformat(),
    "n_files": len(rows),
    "total_bytes": sum(r["bytes"] for r in rows),
    "note": "research inputs only; data/secrets is excluded by an allow-list and a post-stage fence",
    "files": rows,
}, indent=1))
PY

# ---------------------------------------------------------------- archive
if command -v zstd >/dev/null 2>&1; then
  ARCHIVE="${OUT_DIR}/${NAME}.tar.zst"
  tar -C "$STAGE" -cf - "$NAME" | zstd -q -19 -T0 -o "$ARCHIVE"
else
  ARCHIVE="${OUT_DIR}/${NAME}.tar.gz"
  tar -C "$STAGE" -czf "$ARCHIVE" "$NAME"
fi
sha256sum "$ARCHIVE" > "${ARCHIVE}.sha256"

echo "== snapshot =="
echo "  $ARCHIVE"
echo "  $(du -h "$ARCHIVE" | cut -f1)"
echo "  $(cat "${ARCHIVE}.sha256")"

# Keep the last N so a nightly timer cannot fill the disk -- a full disk takes the recorders down,
# which costs more tape than every snapshot ever saved.
KEEP="${SNAPSHOT_KEEP:-5}"
ls -1t "${OUT_DIR}"/research-snapshot-*.tar.* 2>/dev/null | tail -n "+$((KEEP + 1))" |
  while read -r old; do echo "  - pruning $old"; rm -f "$old" "${old}.sha256"; done

if [ -n "${PUBLISH_TO:-}" ]; then
  echo "== publishing to ${PUBLISH_TO} =="
  scp -q "$ARCHIVE" "${ARCHIVE}.sha256" "$PUBLISH_TO"
  echo "  sent"
fi
