# Desk facts to remember across sessions

- **VPS IP: 95.216.191.70** — the production box this repo deploys to. No SSH access from this
  container (confirmed repeatedly — only HTTPS reads via `dash.quanttt.xyz`'s static `web/*.json`
  work). If SSH ever becomes reachable, this is the host.
- **MT5 UNIVERSE MANDATE (2026-08-18, principal's standing order)** — the desk's primary market
  universe is the full MT5/Fusion Markets universe: FX majors/crosses/exotics, gold (XAUUSD),
  silver, metals, equity indices, energy, soft commodities, US share CFDs. **No crypto-exchange
  universe (Binance/Bybit/OKX/Hyperliquid etc.) may EVER be hunted again** — no miner, hunter,
  query, channel list, scoring vocabulary, or research mandate may target crypto-exchange-native
  opportunities. Fusion-executable crypto CFDs are part of the MT5 universe; crypto reference data
  may be used only WHEN it informs an MT5 instrument, never as a hunted universe of its own.
  The live MT5 desk works on branch `claude/llm-auto-upgrade-verify-gcjac3` (VPS pushes hourly
  "mt5 desk hourly sync" commits there) — reconcile with it, never blindly overwrite it.
