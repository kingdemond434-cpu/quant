# Desk dashboard — how it is served, and why this way

**Page:** `web/desk.html` · **State:** `web/desk_state.json` · **URL:** `https://dash.quanttt.xyz`

## The shape

```
TRADING BOX (Contabo, Windows)          PUBLIC BOX (Hetzner)              YOUR DEVICES
  MT5 terminal                            quant-desk-pull.timer  ──┐        Dell
    └ MT5-DeskState (5 min)               (every 2 min, SSH pull)  │        phone
        builds desk_state.json  ────────► web/desk_state.json      │          ▲
                                          quant-desk-web.service   │          │
  serves NOTHING, no open port            (127.0.0.1:8788,         └──► cloudflared tunnel
                                           --require-token)              dash.quanttt.xyz
```

**Why the trading box serves nothing.** It runs the live account. Every open port on it is a
route to the money, and a dashboard is not worth that. It only *builds* state; this box pulls it
over the SSH identity that already existed for deploys — no new credential, no inbound port
there, nothing for a scanner to find.

**Why a pull, not a push.** The pull runs here, so a failure is *this* box's problem: the last
good copy keeps serving and the page's `source … ago` field states its true age. A push would
have made the trading box responsible for a dashboard's uptime.

## Auth — and the trap that nearly shipped

Requests from a Cloudflare tunnel reach the origin over **127.0.0.1**. The first cut of the auth
trusted loopback, so the tunnel would have published live equity, P&L and open positions to
anyone who knew the hostname, with the token bypassed for precisely the traffic it was added to
protect. Hence `--require-token`, which **drops the loopback exemption entirely**. Verified:
`/desk.html` and `/desk_state.json` both return 401 from loopback without a key.

The key lives at `data/secrets/dashboard_token.txt` on this box, mode 0600, and is never printed
by any tool (CLAUDE.md: `data/secrets/**` never leaves the box). Read it there when enrolling a
device:

```bash
cat /home/quant/quant-platform/data/secrets/dashboard_token.txt
```

**Enrolling a device (once per device):** open `https://dash.quanttt.xyz/desk.html?k=<key>`. The
server sets a one-year `HttpOnly` cookie, so afterwards the bare URL works — bookmark it, or add
it to the phone's home screen. Three carriers are accepted (`Authorization: Bearer`, `?k=`,
cookie) because three situations need them: scripts, first-time enrolment by pasted link, and
every visit after.

## Operating it

| Unit | Cadence | Purpose |
|---|---|---|
| `quant-desk-pull.timer` | 2 min | pull state from the trading box |
| `quant-desk-web.service` | always | serve `web/` on 127.0.0.1:8788, token required |
| `quant-tunnel.service` (system) | always | cloudflared → `dash.quanttt.xyz` |
| `MT5-DeskState` (trading box) | 5 min | build `desk_state.json` from the live terminal |

```bash
systemctl --user status quant-desk-web.service quant-desk-pull.timer
journalctl --user -u quant-desk-pull.service -n 20      # pull health
./ops/pull_desk_state.sh                                 # pull by hand
```

**Rotating the key:** delete `data/secrets/dashboard_token.txt` and restart
`quant-desk-web.service`; a new one is minted on first request and every enrolled device must be
re-enrolled. Do this if a link with `?k=` is ever pasted anywhere it could be read.

## What the page shows

Funnel — discovered+backtested → certified (ten gates) → forward clocks → promotion-ready →
live. Then account KPIs, equity curve, book statistics (Sharpe, win rate, max/current DD), daily
gains, **every forward clock with its day-N/14 progress and forward t-stat**, the live decay
monitor (L1.59), certified survivors with DSR/PBO/SPA, and broker-reported positions.

Missing values render as `—` / `UNMEASURED` rather than `0`. A dashboard that prints a confident
zero for something it did not measure is how a desk talks itself into a decision (L1.28a).
