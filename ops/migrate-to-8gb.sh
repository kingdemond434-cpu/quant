#!/usr/bin/env bash
# Move the research VPS to the 8GB Hetzner box. RUN THIS ON THE NEW (8GB) MACHINE.
#
# WHY THE MOVE. The 4GB host idles at ~50% used and two research units carried MemoryMax=4G --
# the whole machine -- so a heavy sweep could take every page and the global OOM killer would
# then pick the largest process it could see, routinely the dashboard server or cloudflared
# rather than the organ that overran.
#
# THE ONE HAZARD THIS MACHINE ALREADY CAUSED, and the reason step 1 is what it is. This box was
# left powered on after the last migration, still holding the `quant-dash` tunnel credentials and
# still running cloudflared against an 11-day-old checkout. A named tunnel accepts connectors from
# ANY host holding its credentials and Cloudflare load-balances across them, so it served a share
# of every public request with a login screen: measured 2026-09-06, it held four of the seven
# edges and 4 of 6 external probes returned 401 while the other box was already correct. The old
# connector is stopped and DISABLED before anything else here, and the cutover is explicit rather
# than a race between two boxes that both think they serve the dashboard.
#
# WHAT TRAVELS AND HOW. The bar lake is TRACKED, so git carries it -- 107 charts today, all of
# them once the box has synced. Only two things are outside git and must be hand-carried:
# data/secrets/ and ~/.cloudflared/. This script fetches them over ssh when it can and REFUSES to
# continue when it cannot, naming both -- a desk that starts without its secrets comes up looking
# healthy and quietly does nothing.
#
#   ./ops/migrate-to-8gb.sh --from quant@95.216.191.70     migrate, pulling secrets from the old box
#   ./ops/migrate-to-8gb.sh --check                        report only, change nothing
set -uo pipefail

OLD_HOST=""
ROOT="${QUANT_ROOT:-$HOME/quant-platform}"
REPO="${QUANT_REPO:-git@github.com:kingdemond434-cpu/quant.git}"
BRANCH="${CODE_BRANCH:-desk-sync-clean}"
TUNNEL="${TUNNEL:-quant-dash}"
CHECK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --from) OLD_HOST="${2:-}"; shift 2 ;;
    --check) CHECK=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

FAILURES=()
step() { printf '\n== %s\n' "$1"; }
ok()   { printf '   OK    %s\n' "$1"; }
warn() { printf '   WARN  %s\n' "$1"; }
fail() { printf '   FAIL  %s\n' "$1"; FAILURES+=("$1"); }
info() { printf '   ...   %s\n' "$1"; }

# ---------------------------------------------------------------- 0. am I the right machine
step "Host"
mem_mb=$(( $(awk '/^MemTotal:/ {print $2}' /proc/meminfo) / 1024 ))
info "$(hostname) -- ${mem_mb}MB RAM"
if [ "$mem_mb" -lt 6000 ]; then
  fail "this host has only ${mem_mb}MB: it is not the 8GB box, and running the migration here would move the desk backwards"
  echo; echo "Run this ON THE 8GB MACHINE."; exit 2
fi
ok "8GB-class host confirmed"

# ---------------------------------------------- 1. the old connector dies FIRST, and stays dead
step "Stale tunnel connector"
# BEFORE THE CHECKOUT, BEFORE THE UNITS, BEFORE ANYTHING. While this box's old cloudflared is
# running it is actively breaking the live dashboard on the other host -- so it is stopped first,
# and DISABLED, because a killed connector that returns on reboot puts us straight back here.
if [ "$CHECK" = 1 ]; then
  pgrep -fa 'cloudflared' >/dev/null 2>&1 && warn "cloudflared is running (--check: not stopped)" || ok "no cloudflared running"
else
  sudo systemctl disable --now cloudflared 2>/dev/null
  systemctl --user disable --now cloudflared 2>/dev/null
  pkill -f 'cloudflared tunnel' 2>/dev/null
  sleep 2
  if pgrep -f 'cloudflared' >/dev/null 2>&1; then
    fail "cloudflared is STILL running here -- it will keep poisoning the live dashboard; find it with: pgrep -fa cloudflared"
  else
    ok "old connector stopped and disabled"
  fi
fi

# ---------------------------------------------------------------- 2. the checkout
step "Checkout"
if [ "$CHECK" = 1 ]; then
  [ -d "$ROOT/.git" ] && info "$ROOT exists ($(cd "$ROOT" && git log -1 --format='%cd' --date=short 2>/dev/null))" || info "$ROOT absent -- would clone"
elif [ -d "$ROOT/.git" ]; then
  cd "$ROOT" || exit 2
  git config core.editor true
  git config pull.rebase false
  # AN UNFINISHED MERGE FROM BEFORE BLOCKS EVERY LATER GIT CALL, and this box was abandoned
  # mid-merge: `error: Merging is not possible because you have unmerged files` on the first run
  # here. Resolve it the way vps-repair.sh does -- CODE stays on the reviewed branch, DATA takes
  # the incoming copy -- and if code conflicts remain, ABORT rather than guess. Aborting decides
  # nothing: it restores the pre-merge tree, so the box keeps exactly what it had.
  if [ -f .git/MERGE_HEAD ] || [ -n "$(git diff --name-only --diff-filter=U)" ]; then
    unmerged="$(git diff --name-only --diff-filter=U)"
    if [ -n "$unmerged" ]; then
      code="$(printf '%s\n' "$unmerged" | grep -E '\.(py|sh|ps1|ya?ml)$' || true)"
      data="$(printf '%s\n' "$unmerged" | grep -vE '\.(py|sh|ps1|ya?ml)$' || true)"
      [ -n "$data" ] && { printf '%s\n' "$data" | xargs -r git checkout --theirs -- 2>/dev/null; printf '%s\n' "$data" | xargs -r git add -- 2>/dev/null; info "$(printf '%s\n' "$data" | wc -l) data conflict(s) taken from the branch"; }
      [ -n "$code" ] && { printf '%s\n' "$code" | xargs -r git checkout --ours -- 2>/dev/null; printf '%s\n' "$code" | xargs -r git add -- 2>/dev/null; info "$(printf '%s\n' "$code" | wc -l) code conflict(s) kept on this branch's version"; }
    fi
    if git commit --no-edit >/dev/null 2>&1; then ok "the abandoned merge was concluded"
    else
      git merge --abort >/dev/null 2>&1
      [ -f .git/MERGE_HEAD ] && fail "could not clear the abandoned merge -- run: git status" \
                             || warn "abandoned merge declined and the tree restored"
    fi
  fi
  # UPDATED BY MERGE, NEVER BY RESET: this box may still hold state nobody has copied off it, and
  # a reset would take that with it silently.
  if out="$(git fetch origin "$BRANCH" 2>&1 && git merge --no-edit "origin/$BRANCH" 2>&1)"; then
    ok "updated to origin/$BRANCH"
  else
    fail "could not fast-forward the existing checkout -- resolve by hand, do NOT reset"
    printf '%s\n' "$out" | tail -6 | while read -r l; do info "$l"; done
  fi
else
  if git clone --branch "$BRANCH" "$REPO" "$ROOT" 2>&1 | tail -3; then ok "cloned $BRANCH into $ROOT"
  else fail "clone failed -- check the deploy key on this box"; fi
fi

# ------------------------------------------------- 3. the two things git does not carry
step "Secrets and tunnel credentials"
need_secrets=0
[ -d "$ROOT/data/secrets" ] && [ -n "$(ls -A "$ROOT/data/secrets" 2>/dev/null)" ] || need_secrets=1
need_cfd=0
[ -n "$(ls -A "$HOME/.cloudflared" 2>/dev/null)" ] || need_cfd=1

if [ "$need_secrets" = 0 ] && [ "$need_cfd" = 0 ]; then
  ok "data/secrets and ~/.cloudflared are both present"
elif [ "$CHECK" = 1 ]; then
  warn "missing: $([ $need_secrets = 1 ] && echo 'data/secrets ')$([ $need_cfd = 1 ] && echo '~/.cloudflared')"
elif [ -n "$OLD_HOST" ]; then
  mkdir -p "$ROOT/data/secrets" "$HOME/.cloudflared"
  [ "$need_secrets" = 1 ] && { scp -pq "$OLD_HOST:quant-platform/data/secrets/*" "$ROOT/data/secrets/" 2>/dev/null \
      && { chmod 600 "$ROOT"/data/secrets/* 2>/dev/null; ok "secrets copied from $OLD_HOST"; } \
      || fail "could not copy data/secrets from $OLD_HOST"; }
  [ "$need_cfd" = 1 ] && { scp -pq "$OLD_HOST:.cloudflared/*" "$HOME/.cloudflared/" 2>/dev/null \
      && ok "tunnel credentials copied from $OLD_HOST" \
      || fail "could not copy ~/.cloudflared from $OLD_HOST"; }
else
  fail "data/secrets and/or ~/.cloudflared are missing and no --from host was given"
  info "from your laptop:  scp -r quant@95.216.191.70:quant-platform/data/secrets  <thisbox>:quant-platform/data/"
  info "from your laptop:  scp -r quant@95.216.191.70:.cloudflared                 <thisbox>:~/"
fi
# A DESK WITHOUT ITS SECRETS STARTS CLEANLY AND DOES NOTHING, which is the worst of both worlds:
# every unit green, every organ silently unauthenticated. Stop rather than hand that over.
if [ "$CHECK" = 0 ] && { [ ! -d "$ROOT/data/secrets" ] || [ -z "$(ls -A "$ROOT/data/secrets" 2>/dev/null)" ]; }; then
  echo; echo "STOPPING: no data/secrets on this box. Copy them, then re-run."; exit 1
fi

# ---------------------------------------------------------------- 4. units, linger, budget
step "systemd"
if [ "$CHECK" = 1 ]; then
  info "would install $(ls "$ROOT"/ops/*.service "$ROOT"/ops/*.timer "$ROOT"/ops/*.slice 2>/dev/null | wc -l) unit file(s)"
else
  mkdir -p "$HOME/.config/systemd/user"
  cp "$ROOT"/ops/*.service "$ROOT"/ops/*.timer "$ROOT"/ops/*.slice "$HOME/.config/systemd/user/" 2>/dev/null
  systemctl --user daemon-reload 2>/dev/null && ok "$(ls "$HOME/.config/systemd/user"/*.timer 2>/dev/null | wc -l) timer(s) installed"
  # WITHOUT LINGERING A USER SERVICE DIES WHEN THE SSH SESSION ENDS, so the desk would run only
  # while somebody is logged in -- and would come back from a reboot dead with no error anywhere.
  loginctl enable-linger "$USER" 2>/dev/null && ok "lingering enabled ($USER survives logout and reboot)" \
    || warn "could not enable lingering -- run: loginctl enable-linger $USER"
  bash "$ROOT/ops/size_memory_budget.sh" 2>&1 | sed 's/^/   /'
  for t in "$HOME"/.config/systemd/user/*.timer; do
    systemctl --user enable --now "$(basename "$t")" >/dev/null 2>&1
  done
  ok "timers enabled"
fi

# ---------------------------------------------------------------- 5. serve, then cut over
step "Dashboard and tunnel"
if [ "$CHECK" = 1 ]; then
  info "would start quant-desk-web and the $TUNNEL connector"
else
  # RESTART, NOT `enable --now`. `enable --now` starts a STOPPED unit and does nothing at all to a
  # running one -- so this box, which had a serve_dashboard from before the migration already
  # listening on :8788, kept serving the OLD process with the OLD token-gated arguments and
  # answered 401 locally under a unit file that plainly says --no-auth. Measured here 2026-09-06.
  # The unit file on disk is not the process that is running, and only a restart makes them agree.
  systemctl --user enable quant-desk-web 2>/dev/null
  systemctl --user restart quant-desk-web 2>/dev/null && ok "quant-desk-web restarted from ops/" || fail "quant-desk-web did not start"
  sleep 3
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8788/desk.html || echo 000)"
  if [ "$code" = "200" ]; then
    ok "origin serves desk.html locally"
  else
    fail "origin returns $code locally -- do NOT cut the tunnel over yet"
    if [ "$code" = "401" ]; then
      # Name the two causes, because they need different fixes and look identical from here.
      info "401 means the server wants a token. Either the running process predates this unit"
      info "(check: pgrep -af serve_dashboard -- it must carry --no-auth), or a second server"
      info "is holding :8788: pkill -f serve_dashboard, then systemctl --user start quant-desk-web"
      running="$(pgrep -af serve_dashboard 2>/dev/null || true)"
      [ -n "$running" ] && printf '%s\n' "$running" | while read -r l; do info "$l"; done
    fi
  fi
  if [ "$code" = "200" ]; then
    ( cd "$HOME" && nohup cloudflared tunnel --no-autoupdate run "$TUNNEL" >/tmp/cfd.log 2>&1 & )
    info "connector starting; waiting 25s for the edge to register"; sleep 25
    ok "connector started -- SAME tunnel and SAME hostname, so no Cloudflare DNS change is needed"
  fi
fi

# ---------------------------------------------------------------- 6. verdict
step "Summary"
if [ "${#FAILURES[@]}" -eq 0 ]; then
  echo; echo "MIGRATED. Now, in this order:"
  echo "  1. On the OLD box: systemctl --user disable --now quant-desk-web; pkill -f 'cloudflared tunnel'"
  echo "     Until you do, BOTH boxes serve the tunnel and requests split between them."
  echo "  2. Verify from a phone on mobile data -- NOT from either VPS. A probe run on the tunnel"
  echo "     host exits via its own nearest edge and hits its own connector every time, so it"
  echo "     cannot see a split. That is what hid this exact fault for a day."
  echo "  3. Leave the old box up but idle for a few days, then delete it."
  exit 0
fi
echo; echo "MIGRATION INCOMPLETE -- ${#FAILURES[@]} step(s) failed:"
for f in "${FAILURES[@]}"; do echo "  - $f"; done
echo "Do NOT stop the old box until these are resolved: it is still serving the desk."
exit 1
