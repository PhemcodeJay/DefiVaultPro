import asyncio
import json
import time
from dataclasses import dataclass, asdict
from typing import List
import aiohttp
import db
import logging
import config

# ---------------------------------
# Logging setup
# ---------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="logs/defi_scanner.log",
    filemode="a",
)

# ---------------------------------
# Dataclasses
# ---------------------------------
@dataclass
class YieldEntry:
    chain: str
    protocol: str
    project: str
    symbol: str
    type: str
    apy: float
    apy_str: str
    ror: float
    tvl: float
    tvl_str: str
    risk: str
    gas_fee: float
    gas_fee_str: str
    link: str
    contract_address: str
    pool_id: str
    token_price: float
    token_link: str

@dataclass
class MemeEntry:
    chain: str
    symbol: str
    price: str
    liquidity_usd: str
    volume_24h_usd: str
    change_24h_pct: str
    risk: str
    url: str
    contract_address: str
    project: str
    name: str
    market_cap: float
    growth_potential: str
    pool_id: str

# ---------------------------------
# Config
# ---------------------------------
MIN_APY = config.MIN_APY
MIN_TVL = config.MIN_TVL
FOCUS_PROTOCOLS = [p.lower() for p in config.FOCUS_PROTOCOLS]
MEME_CHAINS = [c.lower() for c in config.MEME_CHAINS]
RESCAN_INTERVAL = config.RESCAN_INTERVAL
CHAIN_RISK_SCORES = {"ethereum": 0.5, "bsc": 1.0, "solana": 1.5}

# ---------------------------------
# Utils
# ---------------------------------
async def async_request(url: str) -> dict:
    retries = 3
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    resp.raise_for_status()
                    return await resp.json()
        except Exception as e:
            logging.error(f"Request to {url} failed (attempt {attempt+1}): {e}")
            if attempt == retries - 1:
                return {"error": str(e)}
            await asyncio.sleep(2 ** attempt)
    return {"error": "All retries failed"}

def risk_score(apy: float, tvl: float, project: str, chain: str) -> float:
    score = 1.0
    if apy > 20: score += 1
    if tvl < 1_000_000: score += 1
    score += CHAIN_RISK_SCORES.get(chain.lower(), 1.0)
    return score

async def estimate_gas_fee(chain: str) -> dict:
    # This can be extended with real gas API calls
    return {"fee": 2.5, "price": 1.0, "url": f"https://gasstation/{chain}"}

# ---------------------------------
# Fetch Yields
# ---------------------------------
async def fetch_yields() -> List[YieldEntry]:
    url = config.YIELDS_API_URL
    data = await async_request(url)
    entries = []

    if "error" in data:
        logging.error(f"Failed to fetch yields: {data['error']}")
        return entries

    for pool in data.get("data", []):
        chain = (pool.get("chain") or "unknown").lower()
        project = (pool.get("project") or "unknown").lower()
        symbol = pool.get("symbol") or "?"
        type_ = pool.get("poolMeta") or "Unknown"
        apy = float(pool.get("apy") or 0.0)
        tvl = float(pool.get("tvlUsd") or 0.0)

        # Skip low-quality opportunities based on config
        if apy < MIN_APY or tvl < MIN_TVL or (FOCUS_PROTOCOLS and project not in FOCUS_PROTOCOLS):
            continue

        contract_address = pool.get("pool") or f"unknown_{project}_{symbol}_{chain}"
        # Skip if no valid 'pool' ID (invalid/incomplete entry)
        if contract_address.startswith("unknown_"):
            continue

        try:
            gas_info = await estimate_gas_fee(chain)
        except Exception:
            gas_info = {"fee": 0.0, "price": 0.0, "url": ""}

        try:
            ror = apy / risk_score(apy, tvl, project, chain)
        except Exception:
            ror = apy

        link = pool.get("url") or f"https://defillama.com/yields/pool/{pool.get('pool', '')}"

        entries.append(
            YieldEntry(
                chain=chain,
                protocol=pool.get("project", "Unknown"),
                project=project,
                symbol=symbol,
                type=type_,
                apy=apy,
                apy_str=f"{apy:.2f}%",
                ror=ror,
                tvl=tvl,
                tvl_str=f"${tvl:,.0f}",
                risk="Low" if ror > 2 else "Medium" if ror > 1 else "High",
                gas_fee=gas_info.get("fee", 0.0),
                gas_fee_str=f"${gas_info.get('fee', 0.0):.2f}",
                link=link,
                contract_address=contract_address,
                pool_id=pool.get("poolId") or contract_address,
                token_price=gas_info.get("price", 0.0),
                token_link=gas_info.get("url", ""),
            )
        )

    logging.info(f"Fetched {len(entries)} yield opportunities")
    return entries

# ---------------------------------
# Fetch Meme Coins
# ---------------------------------
async def fetch_meme_coins() -> List[MemeEntry]:
    queries = ["pepe", "doge", "shiba", "floki", "bonk", "wif", "popcat"]
    results = await asyncio.gather(*(async_request(f"{config.MEME_API_URL}?q={q}") for q in queries))
    entries = []
    seen = set()  # Deduplicate by (chain, contract_address)

    for result in results:
        if "error" in result:
            logging.error(f"Meme fetch error: {result['error']}")
            continue

        for pair in result.get("pairs", []):
            chain = (pair.get("chain") or pair.get("chainId") or "unknown").lower()
            if chain not in MEME_CHAINS:
                continue

            contract_address = pair.get("baseToken", {}).get("address") or f"unknown_{chain}_{len(entries)}"
            key = (chain, contract_address)
            if key in seen:
                continue
            seen.add(key)

            liquidity = float(pair.get("liquidity", {}).get("usd") or 0)
            volume_24h = float(pair.get("volume", {}).get("h24") or 0)
            change_24h = float(pair.get("priceChange", {}).get("h24") or 0)
            price = float(pair.get("priceUsd") or 0)
            market_cap = float(pair.get("fdv") or 0)

            pair_address = pair.get("pairAddress", "")
            url = pair.get("url") or (f"https://dexscreener.com/{chain}/{pair_address}" if pair_address else "https://dexscreener.com")
            price_str = f"${price:.4f}" if price < 1 else f"${price:.2f}"

            entries.append(
                MemeEntry(
                    chain=chain,
                    symbol=pair.get("baseToken", {}).get("symbol") or "Unknown",
                    price=price_str,
                    liquidity_usd=f"${liquidity:,.0f}",
                    volume_24h_usd=f"${volume_24h:,.0f}",
                    change_24h_pct=f"{change_24h:.2f}%",
                    risk="High" if abs(change_24h) > 20 else "Medium",
                    url=url,
                    contract_address=contract_address,
                    project=pair.get("dexId", "Unknown"),
                    name=pair.get("baseToken", {}).get("name") or "Unknown",
                    market_cap=market_cap,
                    growth_potential=f"{change_24h:.2f}%",
                    pool_id=pair.get("pairAddress") or f"unknown_{len(entries)}",
                )
            )

    logging.info(f"Fetched {len(entries)} meme coins")
    return entries

# ---------------------------------
# Save Results
# ---------------------------------
def save_results_to_db(entries: List[YieldEntry]):
    for entry in entries:
        try:
            existing = db.get_opportunities(chain=entry.chain)
            existing_entry = next((o for o in existing if o["contract_address"] == entry.contract_address), None)
            opp_dict = {
                "project": entry.project,
                "symbol": entry.symbol,
                "chain": entry.chain,
                "apy": entry.apy,
                "tvl": entry.tvl,
                "risk": entry.risk,
                "type": entry.type,
                "contract_address": entry.contract_address,
            }
            if existing_entry:
                opp_dict["id"] = existing_entry["id"]

            db.save_opportunities([opp_dict])
        except Exception as e:
            logging.error(f"Failed to save opportunity {entry.project}: {e}")

# ---------------------------------
# Main Scan Loop
# ---------------------------------
async def full_defi_scan():
    yields, memes = await asyncio.gather(fetch_yields(), fetch_meme_coins())
    return {"yields": [asdict(y) for y in yields], "memes": [asdict(m) for m in memes]}

async def main_loop():
    while True:
        start = time.time()
        results = await full_defi_scan()
        logging.info(f"Scan completed in {time.time() - start:.2f}s")

        if results["yields"]:
            save_results_to_db([YieldEntry(**y) for y in results["yields"]])

        if results["memes"]:
            db.save_meme_opportunities(results["memes"])

        with open("defi_scan_results.json", "w") as f:
            json.dump(results, f, indent=2)

        logging.info(f"Next scan in {RESCAN_INTERVAL / 3600} hours")
        await asyncio.sleep(RESCAN_INTERVAL)

# ---------------------------------
# Entry Point
# ---------------------------------
if __name__ == "__main__":
    asyncio.run(main_loop())