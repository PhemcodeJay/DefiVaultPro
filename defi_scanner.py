import asyncio
import json
import time
from dataclasses import dataclass, asdict
from typing import List
import aiohttp
import db
import logging
import config  # New import for centralized config

# ---------------------------------
# Logging setup
# ---------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="defi_scanner.log",
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
    price_usd: str
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
# Config (from config.py)
# ---------------------------------
MIN_APY = config.MIN_APY
MIN_TVL = config.MIN_TVL
FOCUS_PROTOCOLS = config.FOCUS_PROTOCOLS
MEME_CHAINS = config.MEME_CHAINS
RESCAN_INTERVAL = config.RESCAN_INTERVAL
CHAIN_RISK_SCORES = {"ethereum": 0.5, "bsc": 1.0, "solana": 1.5}  # Example enhancement

# ---------------------------------
# Utils
# ---------------------------------
async def async_request(url: str) -> dict:
    retries = 3
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    resp.raise_for_status()  # Raise on HTTP error
                    return await resp.json()
        except aiohttp.ClientError as e:
            logging.error(f"Request to {url} failed (attempt {attempt+1}): {e}")
            if attempt == retries - 1:
                return {"error": str(e)}
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return {"error": "All retries failed"}

def risk_score(apy: float, tvl: float, project: str, chain: str) -> float:
    score = 1.0
    if apy > 20: score += 1
    if tvl < 1_000_000: score += 1
    if project.lower() not in FOCUS_PROTOCOLS: score += 0.5
    score += CHAIN_RISK_SCORES.get(chain.lower(), 1.0)  # Enhanced with chain risk
    return score

async def estimate_gas_fee(chain: str) -> dict:
    return {"fee": 2.5, "price": 1.0, "url": f"https://gasstation/{chain}"}

# ---------------------------------
# Fetch Yields
# ---------------------------------
async def fetch_yields() -> List[YieldEntry]:
    url = config.YIELDS_API_URL  # From config
    data = await async_request(url)
    if "error" in data:
        return []

    entries = []
    for pool in data.get("data", []):
        if (
            pool.get("apy", 0) >= MIN_APY
            and pool.get("tvlUsd", 0) >= MIN_TVL
            and pool.get("project", "").lower() in FOCUS_PROTOCOLS
        ):
            gas_info = await estimate_gas_fee(pool.get("chain", "").lower())
            ror = pool.get("apy", 0) / risk_score(pool.get("apy", 0), pool.get("tvlUsd", 0), pool.get("project", ""), pool.get("chain", ""))

            link = pool.get("url") or f"https://defillama.com/yields/pool/{pool.get('pool', '')}"

            entries.append(
                YieldEntry(
                    chain=pool.get("chain", "unknown").lower(),
                    protocol=pool.get("project", "Unknown"),
                    project=pool.get("project", "Unknown"),
                    symbol=pool.get("symbol", "?"),
                    type=pool.get("poolMeta", "Unknown"),
                    apy=pool.get("apy", 0.0),
                    apy_str=f"{pool.get('apy', 0.0):.2f}%",
                    ror=ror,
                    tvl=pool.get("tvlUsd", 0.0),
                    tvl_str=f"${pool.get('tvlUsd', 0.0):,.0f}",
                    risk="Low" if ror > 2 else "Medium" if ror > 1 else "High",
                    gas_fee=gas_info["fee"],
                    gas_fee_str=f"${gas_info['fee']:.2f}",
                    link=link,
                    contract_address=pool.get("pool", "unknown"),
                    pool_id=pool.get("poolId", pool.get("pool", "unknown")),
                    token_price=gas_info["price"],
                    token_link=gas_info["url"],
                )
            )
    return entries

# ---------------------------------
# Fetch Meme Coins
# ---------------------------------
async def fetch_meme_coins() -> List[MemeEntry]:
    queries = ["pepe", "doge", "shiba", "floki", "bonk", "wif", "popcat"]
    results = await asyncio.gather(*(async_request(f"{config.MEME_API_URL}?q={q}") for q in queries))

    entries = []
    for result in results:
        if "error" in result: continue
        for pair in result.get("pairs", []):
            chain = pair.get("chainId", "unknown").lower()
            if chain not in MEME_CHAINS: continue

            liquidity = float(pair.get("liquidity", {}).get("usd", 0))
            volume_24h = float(pair.get("volume", {}).get("h24", 0))
            change_24h = float(pair.get("priceChange", {}).get("h24", 0))
            if liquidity < 10_000 or volume_24h < 10_000: continue

            pair_address = pair.get("pairAddress", "")
            url = pair.get("url") or f"https://dexscreener.com/{chain}/{pair_address}" if pair_address else "https://dexscreener.com"

            entries.append(
                MemeEntry(
                    chain=chain,
                    symbol=pair.get("baseToken", {}).get("symbol", "Unknown"),
                    price_usd=(f"${float(pair.get('priceUsd', 0)):.4f}" if float(pair.get("priceUsd", 0)) < 1 else f"${float(pair.get('priceUsd', 0)):.2f}"),
                    liquidity_usd=f"${liquidity:,.0f}",
                    volume_24h_usd=f"${volume_24h:,.0f}",
                    change_24h_pct=f"{change_24h:.2f}%",
                    risk="High" if abs(change_24h) > 20 else "Medium",
                    url=url,
                    contract_address=pair.get("baseToken", {}).get("address", "unknown"),
                    project=pair.get("dexId", "Unknown"),
                    name=pair.get("baseToken", {}).get("name", "Unknown"),
                    market_cap=float(pair.get("fdv", 0)),
                    growth_potential=f"{change_24h:.2f}%",
                    pool_id=pair.get("pairAddress", f"unknown_{len(entries)}"),
                )
            )
    return entries

# ---------------------------------
# Save Results with Upsert and Retry
# ---------------------------------
def save_results_to_db(entries: List[YieldEntry]):
    retries = 3
    for entry in entries:
        for attempt in range(retries):
            try:
                # Check if opportunity exists
                existing = [o for o in db.get_opportunities(chain=entry.chain) if o["contract_address"] == entry.contract_address]
                if existing:
                    logging.info(f"Updating opportunity: {entry.project} ({entry.contract_address})")
                    db.save_opportunities([{
                        "id": existing[0]["id"],
                        "project": entry.project,
                        "symbol": entry.symbol,
                        "chain": entry.chain,
                        "apy": entry.apy,
                        "tvl": entry.tvl,
                        "risk": entry.risk,
                        "type": entry.type,
                        "contract_address": entry.contract_address
                    }])
                else:
                    logging.info(f"Inserting new opportunity: {entry.project} ({entry.contract_address})")
                    db.save_opportunities([{
                        "id": None,
                        "project": entry.project,
                        "symbol": entry.symbol,
                        "chain": entry.chain,
                        "apy": entry.apy,
                        "tvl": entry.tvl,
                        "risk": entry.risk,
                        "type": entry.type,
                        "contract_address": entry.contract_address
                    }])
                break  # Success, exit retry loop
            except Exception as e:
                logging.error(f"Database save failed (attempt {attempt+1}): {e}")
                if attempt == retries - 1:
                    logging.error(f"Failed to save after {retries} attempts: {entry.project}")
                time.sleep(2 ** attempt)  # Backoff

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

        # Save results with retry
        if results["yields"]:
            save_results_to_db([YieldEntry(**y) for y in results["yields"]])
        if results["memes"]:
            db.save_meme_opportunities(results["memes"])

        # Write to JSON file
        with open("defi_scan_results.json", "w") as f:
            json.dump(results, f, indent=2)

        logging.info(f"Next scan in {RESCAN_INTERVAL / 3600} hours")
        await asyncio.sleep(RESCAN_INTERVAL)

# ---------------------------------
# Entry Point
# ---------------------------------
if __name__ == "__main__":
    asyncio.run(main_loop())