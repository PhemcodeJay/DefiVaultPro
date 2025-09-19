import os
import logging
from typing import Optional, Dict, Any, List
import asyncio
from web3 import Web3
from web3.types import TxReceipt
import db
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from defi_scanner import fetch_yields, YieldEntry
from functools import lru_cache
import config
from datetime import datetime
from hexbytes import HexBytes

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    filename="logs/utils.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

@lru_cache(maxsize=32)
def connect_to_chain(chain: str) -> Optional[Web3]:
    rpc_urls = config.RPC_URLS
    rpc_url = rpc_urls.get(chain.lower())
    if not rpc_url:
        logging.error(f"No RPC URL for chain: {chain}")
        return None
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if w3.is_connected():
            return w3
        logging.error(f"Connection failed for {chain}: Not connected")
    except Exception as e:
        logging.error(f"Failed to connect to {chain}: {e}")
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
        for i, item in enumerate(items):
            if category == "memes":
                line = f"{i+1}. {item['chain']} | {item['symbol']} | Price: {item['price_usd']} | Liq: {item['liquidity_usd']} | Vol24h: {item['volume_24h_usd']} | Change24h: {item['change_24h_pct']} | Risk: {item['risk']} | {item['url']}"
            else:
                line = f"{i+1}. {item['chain']} | {item['project']} | {item['symbol']} | APY: {item['apy_str']} | ROR: {item['ror']:.2f} | TVL: {item['tvl_str']} | Risk: {item['risk']} | Gas: {item['gas_fee_str']} | {item['link']}"
            # Wrap long lines
            if len(line) > 100:
                c.drawString(inch + 0.25*inch, y_pos, line[:100] + "...")
                y_pos -= 0.15 * inch
                c.drawString(inch + 0.5*inch, y_pos, line[100:])
            else:
                c.drawString(inch + 0.25*inch, y_pos, line)
            y_pos -= 0.2 * inch
            if y_pos < inch:
                c.showPage()
                y_pos = height - inch
        y_pos -= 0.2 * inch
    c.save()

def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result()
        return loop.run_until_complete(coro)
    except Exception as e:
        logging.error(f"Async operation failed: {e}")
        return []

def get_top_picks(limit: int = 10) -> List[YieldEntry]:
    try:
        entries = run_async(fetch_yields())
        if entries:
            sorted_entries = sorted(entries, key=lambda e: (e.apy, e.tvl), reverse=True)
            return sorted_entries[:limit]
    except Exception as e:
        logging.error(f"Failed to fetch top picks from async source: {e}")

    opps = db.get_opportunities(limit=limit)
    sorted_opps = sorted(opps, key=lambda o: (o["apy"], o["tvl"]), reverse=True)
    return [YieldEntry(**o) for o in sorted_opps[:limit]]

def get_short_term_opportunities(limit: int = 5) -> List[YieldEntry]:
    try:
        entries = run_async(fetch_yields())
        if entries:
            sorted_entries = sorted(entries, key=lambda e: e.apy, reverse=True)
            return sorted_entries[:limit]
    except Exception as e:
        logging.error(f"Failed to fetch short-term opportunities: {e}")

    opps = db.get_opportunities(limit=50)
    sorted_opps = sorted(opps, key=lambda o: o["apy"], reverse=True)
    return [YieldEntry(**o) for o in sorted_opps[:limit]]

def get_layer2_opportunities(limit: int = 10) -> List[YieldEntry]:
    L2_CHAINS = {"optimism", "arbitrum", "base", "zksync", "polygon"}
    try:
        entries = run_async(fetch_yields())
        l2_entries = [e for e in entries if e.chain.lower() in L2_CHAINS]
        if l2_entries:
            return l2_entries[:limit]
    except Exception as e:
        logging.error(f"Failed to fetch L2 opportunities: {e}")

    opps = db.get_opportunities(limit=100)
    l2_opps = [o for o in opps if o["chain"].lower() in L2_CHAINS]
    return [YieldEntry(**o) for o in l2_opps[:limit]]

def get_long_term_opportunities(limit: int = 10) -> List[YieldEntry]:
    try:
        entries = run_async(fetch_yields())
        safe_entries = [e for e in entries if e.tvl > 5_000_000 and e.apy < 20]
        if safe_entries:
            sorted_entries = sorted(safe_entries, key=lambda e: e.tvl, reverse=True)
            return sorted_entries[:limit]
    except Exception as e:
        logging.error(f"Failed to fetch long-term opportunities: {e}")

    opps = db.get_opportunities(limit=100)
    safe_opps = [o for o in opps if o["tvl"] > 5_000_000 and o["apy"] < 20]
    sorted_opps = sorted(safe_opps, key=lambda o: o["tvl"], reverse=True)
    return [YieldEntry(**o) for o in sorted_opps[:limit]]

def confirm_position(chain: str, position_id: str, tx_hash: str) -> bool:
    """Wait for transaction receipt and mark position active if successful."""
    try:
        w3 = connect_to_chain(chain)
        if not w3:
            logging.error(f"Failed to connect to chain: {chain}")
            return False

        receipt: TxReceipt = w3.eth.wait_for_transaction_receipt(HexBytes(tx_hash), timeout=300)
        if receipt["status"] == 1:
            with db.get_db_session() as session:
                position = session.get(db.Position, position_id)
                if position:
                    position.status = "active"
                    position.updated_at = datetime.utcnow()
                    return True
        return False
    except Exception as e:
        logging.error(f"Failed to confirm position tx {tx_hash}: {e}")
        return False
