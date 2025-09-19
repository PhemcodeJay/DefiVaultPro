import os
from typing import Optional, Dict, Any, List
import asyncio
from web3 import Web3
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def connect_to_chain(chain: str) -> Optional[Web3]:
    rpc_urls = {
        "ethereum": os.getenv("ETH_RPC_URL", "https://mainnet.infura.io/v3/" + os.getenv("INFURA_PROJECT_ID", "")),
        "bsc": os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/"),
        "arbitrum": os.getenv("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc"),
        "optimism": os.getenv("OPTIMISM_RPC_URL", "https://mainnet.optimism.io"),
        "base": os.getenv("BASE_RPC_URL", "https://mainnet.base.org"),
        "avalanche": os.getenv("AVALANCHE_RPC_URL", "https://api.avax.network/ext/bc/C/rpc"),
        "neon": os.getenv("NEON_RPC_URL", "https://neon-proxy-mainnet.solana.p2p.org"),
    }
    rpc_url = rpc_urls.get(chain.lower())
    if rpc_url:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if w3.is_connected():
                return w3
        except Exception as e:
            print(f"Failed to connect to {chain}: {e}")
    return None

def generate_pdf(scan_results: Dict[str, Any], filename: str = "defi_report.pdf") -> None:
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    y_pos = height - inch
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y_pos, "DeFi & Meme Scan Report")
    y_pos -= 0.5 * inch
    c.setFont("Helvetica", 10)

    for category, items in scan_results.items():
        c.setFont("Helvetica-Bold", 12)
        c.drawString(inch, y_pos, f"=== {category.upper()} ({len(items)}) ===")
        y_pos -= 0.25 * inch
        c.setFont("Helvetica", 9)
        for i, item in enumerate(items[:10]):
            if category == "memes":
                line = f"{i+1}. {item['chain']} | {item['symbol']} | Price: {item['price_usd']} | Liq: {item['liquidity_usd']} | Vol24h: {item['volume_24h_usd']} | Change24h: {item['change_24h_pct']} | Risk: {item['risk']} | {item['url']}"
            else:
                line = f"{i+1}. {item['chain']} | {item['project']} | {item['symbol']} | APY: {item['apy_str']} | ROR: {item['ror']:.2f} | TVL: {item['tvl_str']} | Risk: {item['risk']} | Gas: {item['gas_fee_str']} | {item['link']}"
            c.drawString(inch + 0.25*inch, y_pos, line[:200])
            y_pos -= 0.2 * inch
            if y_pos < inch:
                c.showPage()
                y_pos = height - inch
        y_pos -= 0.2 * inch
    c.save()