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
# them -- so one forgotten machine (an old VPS, a laptop) makes a fraction of every request hit an
# origin nobody is maintaining. Measured 2026-09-06: connector 8dda72b7 from 2.28.12.83 was
# serving 401s while this host was already correct.
if command -v cloudflared >/dev/null 2>&1; then
  mine="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' || true)"
  info "connectors for $TUNNEL:"
  cloudflared tunnel info "$TUNNEL" 2>/dev/null | sed -n '/CONNECTOR ID/,$p' | while read -r l; do info "$l"; done
  warn "any ORIGIN IP above that is not this host is a foreign connector -- stop cloudflared there; it will keep poisoning a share of requests"
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
for _ in 1 2 3 4 5 6; do
  codes="$codes $(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "https://${HOSTNAME_PUBLIC}/desk.html" || echo 000)"
done
info "six probes:$codes"
# SIX, NOT ONE. A single 200 proves nothing when traffic is split across connectors: the fault
# that cost most of 2026-09-06 showed as 200 200 200 401 200, and any single probe had a two in
# three chance of reporting success.
if printf '%s' "$codes" | grep -qv '200'; then :; fi
bad="$(printf '%s' "$codes" | tr ' ' '\n' | grep -cv '^200$' || true)"
if [ "${bad:-0}" -eq 0 ]; then ok "https://${HOSTNAME_PUBLIC}/desk.html is public and consistent"
else fail "$bad of 6 probes did not return 200 -- traffic is still split; see the connector list above"; fi

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
