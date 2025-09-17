import asyncio
import json
import time
import uuid
from dataclasses import dataclass, asdict
from typing import List, Dict

import aiohttp
from sqlalchemy import create_engine, Column, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------------------------------
# Database Setup
# ---------------------------------
Base = declarative_base()
engine = create_engine("sqlite:///defi_dashboard.db")
SessionLocal = sessionmaker(bind=engine)


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chain = Column(String)
    protocol = Column(String)
    symbol = Column(String)
    type = Column(String)
    apy = Column(Float)
    tvl = Column(Float)
    risk = Column(String)
    link = Column(String)


Base.metadata.create_all(engine)

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
# Config
# ---------------------------------
MIN_APY = 5
MIN_TVL = 100000
FOCUS_PROTOCOLS = ["aave", "compound", "uniswap", "curve"]
MEME_CHAINS = ["ethereum", "bsc", "solana"]
RESCAN_INTERVAL = 3600

# ---------------------------------
# Utils
# ---------------------------------
async def async_request(url: str) -> dict:
    """Safe async HTTP request with timeout + retries"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                return await resp.json()
    except Exception as e:
        return {"error": str(e)}


def risk_score(apy: float, tvl: float, project: str) -> float:
    base = 1.0
    if apy > 20:
        base += 1
    if tvl < 1000000:
        base += 1
    if project.lower() not in FOCUS_PROTOCOLS:
        base += 0.5
    return base


async def estimate_gas_fee(chain: str) -> dict:
    # Fake gas estimator
    return {"fee": 2.5, "price": 1.0, "url": f"https://gasstation/{chain}"}


# ---------------------------------
# Fetch Yields (DefiLlama)
# ---------------------------------
async def fetch_yields() -> List[YieldEntry]:
    url = "https://yields.llama.fi/pools"
    data = await async_request(url)
    if "error" in data:
        return []

    entries = []
    for pool in data.get("data", []):
        if (
            pool["apy"] >= MIN_APY
            and pool["tvlUsd"] >= MIN_TVL
            and pool["project"].lower() in FOCUS_PROTOCOLS
        ):
            gas_info = await estimate_gas_fee(pool["chain"])
            ror = pool["apy"] / risk_score(pool["apy"], pool["tvlUsd"], pool["project"])

            link = pool.get("url")
            if not link:
                if "pool" in pool:
                    link = f"https://defillama.com/yields/pool/{pool['pool']}"
                else:
                    link = "https://defillama.com/yields/pools"

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
# Fetch Meme Coins (Dexscreener)
# ---------------------------------
async def fetch_meme_coins() -> List[MemeEntry]:
    queries = ["pepe", "doge", "shiba", "floki", "bonk", "wif", "popcat"]
    results = await asyncio.gather(
        *(async_request(f"https://api.dexscreener.com/latest/dex/search?q={q}") for q in queries)
    )

    entries = []
    for result in results:
        if "error" in result:
            continue

        for pair in result.get("pairs", []):
            chain = pair.get("chainId", "unknown").lower()
            if chain not in MEME_CHAINS:
                continue

            liquidity = float(pair.get("liquidity", {}).get("usd", 0))
            volume_24h = float(pair.get("volume", {}).get("h24", 0))

            # ✅ Safe extraction of price change (default to 0 if missing)
            change_24h = float(pair.get("priceChange", {}).get("h24", 0))

            if liquidity > 10_000 and volume_24h > 10_000:
                pair_address = pair.get("pairAddress")
                if pair_address:
                    url = pair.get("url") or f"https://dexscreener.com/{chain}/{pair_address}"
                else:
                    url = "https://dexscreener.com"

                entries.append(
                    MemeEntry(
                        chain=chain,
                        symbol=pair["baseToken"]["symbol"],
                        price_usd=(f"${float(pair['priceUsd']):,.4f}"
                                   if float(pair["priceUsd"]) < 1
                                   else f"${float(pair['priceUsd']):,.2f}"),
                        liquidity_usd=f"${liquidity:,.0f}",
                        volume_24h_usd=f"${volume_24h:,.0f}",
                        change_24h_pct=f"{change_24h:.2f}%",
                        risk="High" if abs(change_24h) > 20 else "Medium",
                        url=url,
                        contract_address=pair["baseToken"]["address"],
                        project=pair.get("dexId", "Unknown"),
                        name=pair["baseToken"]["name"],
                        market_cap=float(pair.get("fdv", 0)),
                        growth_potential=f"{change_24h:.2f}%",
                        pool_id=pair.get("pairAddress", f"unknown_{len(entries)}"),
                    )
                )
    return entries


# ---------------------------------
# Save to DB
# ---------------------------------
def save_results_to_db(entries: List[YieldEntry]):
    session = SessionLocal()
    for e in entries:
        opp = Opportunity(
            chain=e.chain,
            protocol=e.protocol,
            symbol=e.symbol,
            type=e.type,
            apy=e.apy,
            tvl=e.tvl,
            risk=e.risk,
            link=e.link,
        )
        session.merge(opp)
    session.commit()
    session.close()


# ---------------------------------
# Main Scan Function
# ---------------------------------
async def full_defi_scan():
    yields, memes = await asyncio.gather(fetch_yields(), fetch_meme_coins())
    return {"yields": [asdict(y) for y in yields], "memes": [asdict(m) for m in memes]}


async def countdown(seconds: int):
    for remaining in range(seconds, 0, -1):
        mins, secs = divmod(remaining, 60)
        print(f"\r⏳ Rescanning in {mins:02d}:{secs:02d}", end="", flush=True)
        await asyncio.sleep(1)
    print("\r✅ Rescanning now...          ")


async def main_loop():
    while True:
        start = time.time()
        results = await full_defi_scan()
        print(f"\nScan complete in {time.time() - start:.2f}s")

        with open("defi_scan_results.json", "w") as f:
            json.dump(results, f, indent=2)

        if results["yields"]:
            save_results_to_db([YieldEntry(**y) for y in results["yields"]])

        await countdown(RESCAN_INTERVAL)


# ---------------------------------
# Exported Functions for Streamlit Pages
# ---------------------------------
from db import get_opportunities


def get_top_picks(limit: int = 10):
    opps = get_opportunities(limit=limit)
    return sorted(opps, key=lambda o: (o["apy"], o["tvl"]), reverse=True)


def get_short_term_opportunities(limit: int = 5):
    opps = get_opportunities(limit=50)
    return sorted(opps, key=lambda o: o["apy"], reverse=True)[:limit]


def get_layer2_opportunities(limit: int = 10):
    L2_CHAINS = {"optimism", "arbitrum", "base", "zksync", "polygon"}
    opps = get_opportunities(limit=100)
    return [o for o in opps if o["chain"].lower() in L2_CHAINS][:limit]


def get_long_term_opportunities(limit: int = 10):
    opps = get_opportunities(limit=100)
    safe = [o for o in opps if o["tvl"] > 5_000_000 and o["apy"] < 20]
    return sorted(safe, key=lambda o: o["tvl"], reverse=True)[:limit]


if __name__ == "__main__":
    asyncio.run(main_loop())
