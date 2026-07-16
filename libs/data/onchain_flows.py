"""On-chain stablecoin EXCHANGE-RESERVE reader -- keyless, free, no API key.

Reads the USDT + USDC balances held by known exchange hot wallets via public Ethereum JSON-RPC
(`eth_call` -> ERC-20 `balanceOf`), summed into a total exchange stablecoin reserve. Daily netflow =
day-over-day change in that reserve (the standard CryptoQuant-style "exchange netflow" metric):
reserve UP = net inflow (stables parked on exchanges = dry powder / potential buy pressure); reserve
DOWN = net outflow (stables leaving exchanges). The sign of the edge is an empirical question.
Orthogonal to funding + price -> validated forward, never assumed.

No key, no paid tier: uses public RPC endpoints (fallback across several) and publicly-labelled
exchange addresses. Cheap -- a handful of eth_call per run, not a log scan. Pure/stdlib (urllib).
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

# public, keyless Ethereum JSON-RPC endpoints (tried in order with fallback)
_RPCS = (
    "https://ethereum-rpc.publicnode.com",
    "https://eth.llamarpc.com",
    "https://cloudflare-eth.com",
    "https://rpc.ankr.com/eth",
)

# ERC-20 stablecoins (6 decimals both)
_TOKENS = {
    "USDT": ("0xdAC17F958D2ee523a2206206994597C13D831ec7", 6),
    "USDC": ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
}

# publicly-labelled exchange hot wallets (Etherscan-tagged; public data)
_EXCHANGE_WALLETS = {
    "binance": [
        "0x28C6c06298d514Db089934071355E5743bf21d60",
        "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549",
        "0xDFd5293D8e347dFe59E90eFd55b2956a1343963d",
        "0x9696f59E4d72E237BE84fFD425DCaD154Bf96976",
        "0x4976A4A02f38326660D17bf34b431dC6e2eb2327",
    ],
    "coinbase": [
        "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3",
        "0x503828976D22510aad0201ac7EC88293211D23Da",
        "0xdDBd2B932c763bA5b1b7AE3B362eac3e8d40121A",
        # Coinbase Prime 1 -- custodian wallet holding ~$16M USDC+USDT (verified 2026-07-04)
        "0xcd531ae9efcce479654c4926dec5f6209531ca7b",
    ],
    # OKX and Kraken hold negligible L1 USDT/USDC; they route stablecoins via L2s / internal nets.
    # Checked 2026-07-04: best OKX L1 address holds <$2K, Kraken <$3K. Not added.
    "okx": [
        "0x5041ed759Dd4aFc3a72b8192C143F72f4724081A",
        "0x236F9F97e0E62388479bf9E5BA4889e46B0273C3",
    ],
}

_BALANCE_OF = "0x70a08231"                              # ERC-20 balanceOf(address) selector
_TOTAL_SUPPLY = "0x18160ddd"                            # ERC-20 totalSupply() selector


def _rpc(method: str, params: list[Any]) -> Any:
    """One JSON-RPC call with fallback across public endpoints. Returns the `result` or raises."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last: Exception | None = None
    for url in _RPCS:
        try:
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json",
                                                  "User-Agent": "quant-onchain/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                out = json.loads(r.read())
            if "result" in out:
                return out["result"]
            last = RuntimeError(str(out.get("error"))[:120])
        except Exception as e:  # try the next endpoint
            last = e
    raise RuntimeError(f"all RPC endpoints failed: {last!r}")


def erc20_balance(token_addr: str, holder: str, decimals: int) -> float:
    """ERC-20 balanceOf(holder) in whole tokens (keyless eth_call)."""
    data = _BALANCE_OF + holder.lower().removeprefix("0x").rjust(64, "0")
    res = _rpc("eth_call", [{"to": token_addr, "data": data}, "latest"])
    return int(res, 16) / (10 ** decimals) if res and res != "0x" else 0.0


def stablecoin_supply() -> dict[str, Any]:
    """Total USDT + USDC supply on Ethereum L1 (keyless eth_call -> totalSupply).

    Daily change in total supply = net minting/burning = global new-capital signal.
    Orthogonal to exchange reserves: reserves measure WHERE stables are; supply measures HOW MANY.
    """
    totals: dict[str, float] = {}
    for name, (addr, dec) in _TOKENS.items():
        res = _rpc("eth_call", [{"to": addr, "data": _TOTAL_SUPPLY}, "latest"])
        totals[name] = int(res, 16) / (10 ** dec) if res and res != "0x" else 0.0
    total = round(sum(totals.values()), 2)
    return {"total_supply_usd": total,
            "per_token": {k: round(v, 2) for k, v in totals.items()}}


def exchange_reserves() -> dict[str, Any]:
    """Total USDT+USDC held by the tracked exchange hot wallets, plus a per-exchange breakdown."""
    per_exchange: dict[str, float] = {}
    per_token: dict[str, float] = dict.fromkeys(_TOKENS, 0.0)
    for exch, wallets in _EXCHANGE_WALLETS.items():
        subtotal = 0.0
        for token, (addr, dec) in _TOKENS.items():
            for w in wallets:
                bal = erc20_balance(addr, w, dec)
                subtotal += bal
                per_token[token] += bal
        per_exchange[exch] = round(subtotal, 2)
    total = round(sum(per_token.values()), 2)
    return {"total_reserve_usd": total,
            "per_token": {k: round(v, 2) for k, v in per_token.items()},
            "per_exchange": per_exchange,
            "n_wallets": sum(len(w) for w in _EXCHANGE_WALLETS.values())}
