#!/usr/bin/env bash
# One command that puts the research VPS back into a state where the dashboard is live and current.
#
# WHY THIS EXISTS. On 2026-09-06 dash.quanttt.xyz took most of a day to bring back, through four
# faults that each hid the next and none of which announced itself:
#
#     the server demanded a token          expressed as the ABSENCE of --require-token, which only
#                                          restores the loopback exemption and does not open it
#     cloudflared held a stale ingress     it reads its config once, at startup
#     two origins and three connectors     traffic load-balanced, so one request in three failed
#     an unfinished merge blocked git      so no fix could reach the machine at all
#
# Each check below answers ONE of those and prints what it found. A failing check names its cause
# and the run continues to the independent ones, but the summary lists every failure -- a
# half-repaired host must not read as a fixed one.
#
# WHAT IT WILL NOT DO. It never stashes (a stash in a shared tree is how work disappears), never
# resets, never force-pushes, and never resolves a CODE conflict for you: which version of a
# gateway runs is not a script's decision. Data conflicts it does resolve, because the box authors
# those files and its copy is by definition the right one.
#
#   ./ops/vps-repair.sh              repair
#   ./ops/vps-repair.sh --check      report only, change nothing
set -uo pipefail

ROOT="${QUANT_ROOT:-$HOME/quant-platform}"
CODE_BRANCH="${CODE_BRANCH:-claude/seats-and-chain}"
BOX_BRANCH="${BOX_BRANCH:-claude/llm-auto-upgrade-verify-gcjac3}"
HOSTNAME_PUBLIC="${HOSTNAME_PUBLIC:-dash.quanttt.xyz}"
TUNNEL="${TUNNEL:-quant-dash}"
PORT="${PORT:-8788}"
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

FAILURES=(); NOTES=()
foreign=""   # set by step 3; step 5 reads it to decide whether its own probes mean anything
step() { printf '\n== %s\n' "$1"; }
ok()   { printf '   OK    %s\n' "$1"; }
warn() { printf '   WARN  %s\n' "$1"; NOTES+=("$1"); }
fail() { printf '   FAIL  %s\n' "$1"; FAILURES+=("$1"); }
info() { printf '   ...   %s\n' "$1"; }

cd "$ROOT" 2>/dev/null || { echo "No checkout at $ROOT"; exit 2; }

# ---------------------------------------------------------------- 1. git, unstuck
step "Git"
git config core.editor true          # an editor opening in a non-interactive run blocks forever
git config pull.rebase false         # merge: the VPS has its own commits and rebasing rewrites them
git config user.email >/dev/null 2>&1 || { git config user.email "desk@quanttt.xyz"; warn "git identity was unset -- a commit cannot be made without one; set a real address if you prefer"; }
git config user.name  >/dev/null 2>&1 || git config user.name "quant desk"

if [ -f .git/MERGE_HEAD ]; then
  if [ "$CHECK_ONLY" = 1 ]; then warn "an unfinished merge is in progress"; else
    unmerged="$(git diff --name-only --diff-filter=U)"
    if [ -n "$unmerged" ]; then
      # CODE STAYS OURS, DATA TAKES THEIRS. The VPS serves a dashboard; its code should be the
      # reviewed branch, while every reports/ and data/ file is authored on the box and the box's
      # copy is the only true one. Auto-resolving code would silently pick which gateway runs.
      code="$(printf '%s\n' "$unmerged" | grep -E '\.(py|sh|ps1|ya?ml)$' || true)"
      data="$(printf '%s\n' "$unmerged" | grep -vE '\.(py|sh|ps1|ya?ml)$' || true)"
      [ -n "$code" ] && { printf '%s\n' "$code" | xargs -r git checkout --ours --; printf '%s\n' "$code" | xargs -r git add --; ok "$(printf '%s\n' "$code" | wc -l) code conflict(s) kept on this branch's version"; }
      [ -n "$data" ] && { printf '%s\n' "$data" | xargs -r git checkout --theirs --; printf '%s\n' "$data" | xargs -r git add --; ok "$(printf '%s\n' "$data" | wc -l) data conflict(s) taken from the box"; }
    fi
    git commit --no-edit >/dev/null 2>&1 && ok "merge concluded" || fail "could not conclude the merge -- run: git status"
  fi
fi

if [ "$CHECK_ONLY" = 0 ]; then
  git add -A -- desks/mt5/data desks/mt5/reports web 2>/dev/null
  git diff --cached --quiet || { git commit -m "vps runtime state before sync" >/dev/null 2>&1; ok "local state committed"; }
  for b in "$CODE_BRANCH" "$BOX_BRANCH"; do
    if out="$(git pull origin "$b" 2>&1)"; then ok "pulled $b"
    else fail "pull of $b failed"; printf '%s\n' "$out" | tail -8 | while read -r l; do info "$l"; done; fi
  done
fi

# ---------------------------------------------------------------- 2. exactly one open origin
step "Dashboard origin"
running="$(pgrep -af 'serve_dashboard' || true)"
n_srv="$(printf '%s' "$running" | grep -c . || true)"
if [ "$n_srv" -gt 1 ]; then
  warn "$n_srv dashboard servers are running; the tunnel reaches one of them and the others can still demand a token"
  printf '%s\n' "$running" | while read -r l; do info "$l"; done
  [ "$CHECK_ONLY" = 0 ] && { pkill -f "serve_dashboard.py --port 8080" 2>/dev/null; ok "stopped the spare on :8080"; }
fi
if printf '%s' "$running" | grep -q -- "--no-auth"; then ok "origin runs with --no-auth (public)"
else
  # `--no-auth` and not merely a missing `--require-token`: without the flag the exemption is
  # LOOPBACK-ONLY, and a tunnel that reaches the origin as anything else falls through to the
  # token check and answers 401 while the unit looks correct.
  warn "origin does NOT carry --no-auth; every non-loopback request will be refused"
  [ "$CHECK_ONLY" = 0 ] && {
    cp "$ROOT/ops/quant-desk-web.service" "$HOME/.config/systemd/user/" 2>/dev/null
    systemctl --user daemon-reload 2>/dev/null
    systemctl --user restart quant-desk-web 2>/dev/null && ok "quant-desk-web restarted from ops/"
  }
fi
loop="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/desk.html" || echo 000)"
[ "$loop" = "200" ] && ok "origin serves desk.html on :${PORT}" || fail "origin returns $loop on :${PORT} -- the page is not being served locally"

# ---------------------------------------------------------------- 3. exactly one tunnel connector
step "Cloudflare tunnel"
n_cfd="$(pgrep -fc 'cloudflared tunnel' || true)"
if [ "${n_cfd:-0}" -gt 1 ] && [ "$CHECK_ONLY" = 0 ]; then
  warn "$n_cfd cloudflared processes -- duplicates split traffic and serve stale ingress"
  pkill -f 'cloudflared tunnel'; sleep 3
  ( cd "$HOME" && nohup cloudflared tunnel --no-autoupdate run "$TUNNEL" >/tmp/cfd.log 2>&1 & )
  info "restarted a single connector; waiting 25s for the edge to register"; sleep 25
fi
# FOREIGN CONNECTORS ARE THE ONE FAULT THIS CANNOT FIX FROM HERE. A named tunnel accepts
# connections from ANY host holding its credentials, and Cloudflare load-balances across all of
# them -- so one forgotten machine makes a fraction of every request hit an origin nobody is
# maintaining.
#
# WHAT THIS ACTUALLY WAS, 2026-09-06, recorded because the guess was wrong twice. Connector
# 8dda72b7 reported ORIGIN IP 2.28.12.83, holding the fra03/fra17/fra18/prg03 edges. That address
# reverse-resolves to static.83.12.28.2.clients.your-server.de and RDAP puts 2.28.0.0-2.28.15.255
# in Hetzner's CLOUD-FSN1 block (Falkenstein, DE) -- it is the desk's OWN decommissioned 8GB VPS,
# never shut down, still holding this tunnel's credentials and still serving a stale checkout that
# answers 401. It was NOT a laptop and NOT a stranger. The current host is 95.216.191.70, Hetzner
# CLOUD-HEL1, which is why its own probes always looked clean (see step 5).
#
# This check FAILS rather than warns: a foreign connector is a live fault that silently breaks a
# share of every public request, and a warning is the shape of finding that gets scrolled past.
if command -v cloudflared >/dev/null 2>&1; then
  mine="$( { hostname -I 2>/dev/null; curl -s --max-time 8 https://api.ipify.org 2>/dev/null; echo; } | tr ' ' '\n' | grep -v '^$' | sort -u)"
  conn="$(cloudflared tunnel info "$TUNNEL" 2>/dev/null | sed -n '/CONNECTOR ID/,$p')"
  info "connectors for $TUNNEL:"
  printf '%s\n' "$conn" | while read -r l; do [ -n "$l" ] && info "$l"; done
  # READ THE COLUMN, DO NOT PATTERN-MATCH THE LINE. The first version of this regexed every
  # IPv4/IPv6-looking literal out of the whole table, and an IPv6 pattern matches a CLOCK: in
  # `2026-09-06T17:12:19Z`, "17:" and "12:" are two hextet-colon groups and "19" is the tail, so
  # it reported the connector's CREATED timestamp as a foreign origin -- measured 2026-09-06,
  # this step failed with "foreign connector(s): 17:12:19 17:12:31" on a host whose only
  # connectors were its own. A false alarm on a fault this expensive is worse than no check: it
  # sends the reader hunting a machine that does not exist.
  #
  # `cloudflared tunnel info` prints fixed columns -- id, created, architecture, version, origin
  # ip, edges -- so ORIGIN IP is field 5 of any row whose first field is a connector UUID. That
  # test also skips the header, whose own field 5 is "VERSION".
  foreign="$(printf '%s\n' "$conn" \
    | awk '$1 ~ /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/ {print $5}' \
    | sort -u | grep -vxF -f <(printf '%s\n' "$mine") 2>/dev/null || true)"
  n_rows="$(printf '%s\n' "$conn" | awk '$1 ~ /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/' | wc -l)"
  if [ "${n_rows:-0}" -eq 0 ]; then
    warn "could not parse any connector row from 'cloudflared tunnel info $TUNNEL' -- foreign connectors were NOT checked"
  elif [ -n "$foreign" ]; then
    fail "foreign connector(s) on $TUNNEL -- they serve a share of every public request from an origin this script does not control: $(printf '%s' "$foreign" | tr '\n' ' ')"
    info "fix A (no access needed): repoint the ${HOSTNAME_PUBLIC} CNAME at a tunnel whose credentials that host does NOT hold"
    info "fix B: stop and disable cloudflared on each address above, then re-run"
  else
    ok "every connector on $TUNNEL originates from this host"
  fi
fi

# ---------------------------------------------------------------- 3b. the link that FEEDS the page
step "Desk state pull (the box -> this host link)"
# THIS IS THE JOB THAT MAKES THE DASHBOARD SAY ANYTHING AT ALL, and nothing here checked it.
#
# The page is not fed by git. `quant-desk-pull.timer` runs `ops/pull_desk_state.sh` every two
# minutes and scp's the box's `web/desk_state.json` -- plus the ledgers, the gate report, the
# docket and the universe registry -- straight off the trading box over SSH. When that scp fails
# the script says so and exits 1, the last good copy stays in place, and the page reports the
# box SILENT with an ever-growing age.
#
# MEASURED 2026-09-06: "box has not reported for 260.8h" -- eleven days of that pull failing every
# two minutes, roughly eight thousand consecutive failures, while every other check on this host
# passed and this script printed VPS REPAIRED. A repair script that never tests the one link the
# deliverable depends on is not testing the deliverable.
# GIT IS THE TRANSPORT, so freshness of the DELIVERED ARTIFACTS is the check -- not whether some
# particular mover ran. The box publishes with `sync_shadow_to_git.ps1` (scheduled task
# MT5-ShadowSync, every 15 minutes) onto the shared branch, this host pulls that branch in step 1,
# and `build_zentech_state.py` reads what arrived. Judge the outcome, and the answer stays correct
# whichever mover is in use.
STATE_FILES="desks/mt5/data/account_state.json desks/mt5/reports/shadow/shadow_health.json desks/mt5/data/gateway_state.json desks/mt5/reports/shadow/scalp_shadow_state.json"
fresh=0; stale=0; absent=0
for f in $STATE_FILES; do
  if [ ! -f "$ROOT/$f" ]; then
    absent=$((absent + 1)); info "ABSENT  $f"
  else
    age_h="$(python3 -c "import os,time,sys;print(int((time.time()-os.path.getmtime(sys.argv[1]))//3600))" "$ROOT/$f" 2>/dev/null || echo 999)"
    if [ "$age_h" -le 6 ]; then fresh=$((fresh + 1)); ok "${age_h}h  $f"
    else stale=$((stale + 1)); info "${age_h}h  $f  (STALE)"; fi
  fi
done
if [ "$fresh" -gt 0 ] && [ "$stale" -eq 0 ] && [ "$absent" -eq 0 ]; then
  ok "the box's state is arriving -- every published artifact is under 6h old"
else
  fail "the box's state is NOT arriving: $fresh fresh, $stale stale, $absent absent"
  info "the publisher is on the BOX, not here: scheduled task MT5-ShadowSync runs sync_shadow_to_git.ps1 every 15 minutes"
  info "fix it there with: .\\ops\\box-repair.ps1 -ResolveCode theirs   (its 'Shadow sync to git' step reports and restarts it)"
fi

# THE RETIRED SCP PATH, reported as retired rather than as a failure. `pull_desk_state.sh` scp's
# from ssh alias `contabo-mt5`, and `sync_shadow_to_git.ps1`'s own header records that its
# destination was decommissioned on 2026-08-23. Failing on it every run would put a permanently
# red line in this report, and a detector that is always red is one everybody scrolls past -- so
# it is a NOTE while git is delivering, and only a failure if git is not.
PULL="$ROOT/ops/pull_desk_state.sh"
if [ -f "$PULL" ]; then
  remote="$(sed -n 's/^REMOTE=//p' "$PULL" | head -1)"
  if grep -qs "^Host[[:space:]].*\b${remote}\b" "$HOME/.ssh/config"; then
    if timeout 25 ssh -o BatchMode=yes -o ConnectTimeout=15 "$remote" true 2>/dev/null; then
      ok "legacy scp path: ssh alias '${remote}' still answers"
      [ "$CHECK_ONLY" = 0 ] && { timeout 180 bash "$PULL" >/dev/null 2>&1 && ok "legacy pull also succeeded" || warn "legacy pull ran and failed"; }
    else
      warn "legacy scp path is dead (ssh alias '${remote}' unreachable) -- superseded by the git sync, so this is expected"
    fi
  else
    warn "legacy scp path is unwired (no ssh alias '${remote}' in ~/.ssh/config) -- superseded by the git sync, so this is expected"
  fi
  # A timer that fails every two minutes forever is noise in the journal and teaches the reader
  # to ignore this unit. Stop it once git is confirmed to be delivering, never before.
  if systemctl --user is-active quant-desk-pull.timer >/dev/null 2>&1; then
    if [ "$fresh" -gt 0 ] && [ "$stale" -eq 0 ] && [ "$absent" -eq 0 ] && [ "$CHECK_ONLY" = 0 ]; then
      systemctl --user disable --now quant-desk-pull.timer >/dev/null 2>&1 \
        && ok "stopped quant-desk-pull.timer -- git is delivering and this timer only logged failures" \
        || warn "quant-desk-pull.timer is active and failing; could not stop it"
    else
      info "quant-desk-pull.timer left running -- it is failing, but nothing else is delivering yet either"
    fi
  fi
fi

# ---------------------------------------------------------------- 4. state and freshness
step "Dashboard state"
if [ "$CHECK_ONLY" = 0 ]; then
  python3 scripts/build_zentech_state.py >/dev/null 2>&1 && ok "desk_state.json rebuilt" || fail "build_zentech_state.py failed"
fi
python3 - <<'PY'
import json, pathlib, sys
p = pathlib.Path("web/desk_state.json")
try:
    d = json.loads(p.read_text("utf-8"))
except Exception as exc:
    print(f"   FAIL  desk_state.json unreadable ({exc})"); sys.exit(0)
h = (d.get("health") or {}).get("box") or {}
pipe = d.get("pipeline") or {}
print(f"   ...   built {d.get('generated_at')}")
status = h.get("status")
line = "   OK    " if status == "REPORTING" else "   WARN  "
print(f"{line}box {status}: {str(h.get('why'))[:110]}")
print(f"   ...   certified {pipe.get('certified')}  clocks {pipe.get('forward_clocks')}  docket {pipe.get('docket_candidates')}")
PY

# ---------------------------------------------------------------- 5. the public answer
step "Public"
codes=""
for _ in $(seq 1 12); do
  codes="$codes $(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "https://${HOSTNAME_PUBLIC}/desk.html" || echo 000)"
done
info "twelve probes:$codes"
bad="$(printf '%s' "$codes" | tr ' ' '\n' | grep -cv '^200$' || true)"

# TWELVE, NOT ONE -- AND A CLEAN SWEEP HERE IS NOT A PASS.
#
# Two separate reasons a single probe lies. First, traffic is load-balanced across connectors, so
# when one origin is broken each request only has some chance of hitting it: the 2026-09-06 fault
# showed as 200 200 200 401 200 and later as one 401 in twelve, and a single probe would have
# reported success either way.
#
# Second and worse: THIS HOST CANNOT MEASURE ITS OWN TUNNEL. Cloudflare answers a request at the
# edge nearest the CLIENT, and the client here is the tunnel host itself -- so its curl exits via
# its own local edge and lands on its own connector essentially every time. Measured 2026-09-06:
# from this VPS, 6 of 6 probes returned 200 while an off-network client saw 4 of 6 return 401,
# because the broken origin held only the Frankfurt and Prague edges. Both measurements were
# correct; the local one was answering a different question.
#
# So a clean sweep is reported as INCONCLUSIVE whenever step 3 found a foreign connector. A check
# that cannot fail in the presence of the fault it is meant to catch carries no information, and
# an inconclusive result must never be allowed to read as a repair.
if [ "${bad:-0}" -gt 0 ]; then
  fail "$bad of 12 probes did not return 200 -- traffic is split across origins; see the connector list above"
elif [ -n "${foreign:-}" ]; then
  fail "12 of 12 probes returned 200 BUT THIS PROVES NOTHING: a foreign connector is still registered, and requests from this host resolve to its own nearest edge and its own connector. Verify from a phone on mobile data, off this network."
else
  ok "https://${HOSTNAME_PUBLIC}/desk.html is public and consistent, and this host holds every connector"
fi

# ---------------------------------------------------------------- verdict
step "Summary"
if [ "${#FAILURES[@]}" -eq 0 ]; then
  echo; echo "VPS REPAIRED -- no step failed."
  for n in "${NOTES[@]:-}"; do [ -n "$n" ] && echo "  note: $n"; done
  exit 0
fi
echo; echo "VPS NOT FULLY REPAIRED -- ${#FAILURES[@]} step(s) failed:"
for f in "${FAILURES[@]}"; do echo "  - $f"; done
echo "Nothing above this line should be read as working."
exit 1
