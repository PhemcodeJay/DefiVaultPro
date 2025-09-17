import streamlit as st
import json
import os
from uuid import uuid4
from typing import Dict, Any
from web3 import Web3
from dotenv import load_dotenv
import asyncio
import logging
import aiohttp
from defi_scanner import get_long_term_opportunities, YieldEntry
from wallet_utils import (
    get_connected_wallet,
    create_position,
    add_position_to_session,
    NETWORK_LOGOS,
    BALANCE_SYMBOLS,
    NETWORK_NAMES,
    CHAIN_IDS,
    ERC20_TOKENS,
    ERC20_ABI,
    explorer_urls,
    connect_to_chain,
    build_approve_tx_data,
    build_aave_supply_tx_data,
    build_compound_supply_tx_data,
    confirm_tx,
    PROTOCOL_LOGOS,
    CONTRACT_MAP,
    init_wallets
)
from streamlit_javascript import st_javascript

# --- Load Environment Variables ---
load_dotenv()
logger = logging.getLogger(__name__)

def render():
    st.title("🏛 Long-Term Opportunities")
    st.write("Stable DeFi opportunities for long-term investment.")

# --- Utility Functions ---
def safe_get(obj, key, default):
    if hasattr(obj, key):
        return getattr(obj, key, default)
    elif isinstance(obj, dict):
        return obj.get(key, default)
    return default

def format_number(value: float) -> str:
    try:
        value = float(value)
        if value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value / 1_000:.2f}K"
        return f"${value:,.2f}"
    except (ValueError, TypeError):
        return str(value)

# --- Async ETH price fetch ---
async def async_get_eth_price() -> float:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
            ) as resp:
                data = await resp.json()
                return data.get("ethereum", {}).get("usd", 2000.0)
    except Exception:
        return 2000.0

# --- Async gas fee estimation ---
async def get_chain_gas_fee(chain: str) -> float:
    try:
        w3 = connect_to_chain(chain)
        if not w3:
            return 0.0
        gas_price = w3.eth.gas_price
        gas_estimate = 100000
        eth_price = await async_get_eth_price()
        gas_fee_eth = w3.from_wei(gas_price * gas_estimate, "ether")
        return float(gas_fee_eth) * eth_price
    except Exception:
        return 0.0

# --- JS postMessage ---
def get_post_message() -> Dict[str, Any]:
    return st_javascript("return window.lastMessage || {}")

# --- Render DeFi grid cards ---
def render_grid_cards(
    opps_list,
    category_name: str,
    columns: int = 3,
    bg_color: str = "bg-gradient-to-br from-green-900/30 to-teal-900/30",
):
    if "expanded_cards" not in st.session_state:
        st.session_state.expanded_cards = {}

    logger.info(f"Rendering {len(opps_list)} {category_name} opportunities")
    if not opps_list:
        st.markdown(
            f"""
            <div class="card {bg_color} p-4 rounded-lg shadow-md">
                <p class="text-indigo-200 text-sm flex items-center">
                    <i class="fas fa-info-circle mr-2"></i>No {category_name.replace('_', ' ').title()} opportunities available.
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        """
        <style>
            .card { aspect-ratio: 1/1; transition: all 0.3s; border-radius: 12px; padding: 1rem;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            .card:hover { transform: translateY(-4px); box-shadow: 0 8px 16px rgba(0,0,0,0.2); }
            .risk-low { color: #10B981; }
            .risk-medium { color: #F59E0B; }
            .risk-high { color: #EF4444; }
        </style>
        <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem; padding: 1rem;'>
    """,
        unsafe_allow_html=True,
    )

    for i, opp in enumerate(opps_list):
        pool_id = safe_get(opp, "id", safe_get(opp, "pool_id", f"unknown_{i}"))
        card_key = f"{category_name}_{pool_id}"
        expanded = st.session_state.expanded_cards.get(card_key, False)

        chain = safe_get(opp, "chain", "unknown").capitalize()
        project = safe_get(opp, "project", safe_get(opp, "symbol", "Unknown"))
        symbol = safe_get(opp, "symbol", "Unknown")
        apy_str = safe_get(opp, "apy", safe_get(opp, "apy_str", "0%"))
        tvl_str = safe_get(opp, "tvl", safe_get(opp, "tvl_str", "$0"))
        risk = safe_get(opp, "risk", "Unknown")
        type_ = safe_get(opp, "type", "Unknown")
        contract_address = safe_get(opp, "contract_address", "0x0")
        gas_fee_str = safe_get(opp, "gas_fee_str", "$0.00")
        last_updated = safe_get(opp, "last_updated", "Unknown")
        link = safe_get(opp, "link", "#")

        # Define these variables from opp safely
        token_address = safe_get(opp, "token_address", "0x0")
        pool_address = safe_get(opp, "pool_address", contract_address)
        amount = safe_get(opp, "amount", 0)
        chain_id = safe_get(opp, "chain_id", 1)  # fallback default
        selected_token = symbol

        # Format APY and TVL nicely
        try:
            apy_float = float(str(apy_str).rstrip("%"))
            apy_str = f"{apy_float:.2f}%"
        except:
            pass

        try:
            tvl_float = float(str(tvl_str).rstrip("$").replace(",", ""))
            tvl_str = format_number(tvl_float)
        except:
            pass

        logo_url = NETWORK_LOGOS.get(chain.lower(), "https://via.placeholder.com/12")
        protocol_logo = PROTOCOL_LOGOS.get(project.lower(), "https://via.placeholder.com/12")
        explorer_url = explorer_urls.get(chain.lower(), "#") + contract_address

        st.markdown(
            f"""
            <div class="card {bg_color} hover:shadow-lg" 
                 onclick="document.getElementById('{card_key}').click()"
                 style="cursor:pointer;" role="button" aria-label="Expand {project} card">
                <div class="flex justify-between items-center mb-3">
                    <div class="flex items-center">
                        <img src="{protocol_logo}" alt="{project}" class="w-3 h-3 rounded-full mr-2">
                        <h4 class="font-bold text-indigo-100 text-lg">{symbol}</h4>
                    </div>
                    <span class="text-sm font-semibold risk-{risk.lower()}">{risk}</span>
                </div>
                <div class="flex items-center mb-2">
                    <img src="{logo_url}" alt="{chain}" class="w-3 h-3 rounded-full mr-2">
                    <span class="text-xs text-gray-400">{chain}</span>
                </div>
                <div class="grid grid-cols-2 gap-2 text-sm">
                    <div class="flex flex-col"><span class="text-xs text-gray-400">APY</span>
                        <span class="font-bold text-indigo-100">{apy_str}</span></div>
                    <div class="flex flex-col"><span class="text-xs text-gray-400">TVL</span>
                        <span class="font-bold text-indigo-100">{tvl_str}</span></div>
                    <div class="flex flex-col"><span class="text-xs text-gray-400">Type</span>
                        <span class="font-bold text-indigo-100">{type_}</span></div>
                    <div class="flex flex-col"><span class="text-xs text-gray-400">Gas Fee</span>
                        <span class="font-bold text-indigo-100">{gas_fee_str}</span></div>
                </div>
            </div>
        """,
            unsafe_allow_html=True,
        )

        expanded = st.checkbox("Expand", value=expanded, key=f"{card_key}_checkbox", label_visibility="collapsed")
        st.session_state.expanded_cards[card_key] = expanded

        if expanded:
            with st.expander("", expanded=True):
                st.markdown(
                    f"""
                    <div class="p-3 bg-gray-800/50 rounded-lg">
                        <p class="text-xs text-gray-400 mb-1">Protocol: {project}</p>
                        <p class="text-xs text-gray-400 mb-1">Contract: 
                            <a href="{explorer_url}" target="_blank" class="text-blue-400 hover:underline">
                                {contract_address[:6]}...{contract_address[-4:]}
                            </a>
                        </p>
                        <p class="text-xs text-gray-400 mb-1">Details: 
                            <a href="{link}" target="_blank" class="text-blue-400 hover:underline">View on Protocol</a>
                        </p>
                        <p class="text-xs text-gray-400 mb-1">Last Updated: {last_updated}</p>
                    </div>
                """,
                    unsafe_allow_html=True,
                )


# --- Page content ---
st.markdown("""
<div class="text-center py-8">
    <h1 class="text-4xl font-bold mb-3 bg-clip-text text-transparent bg-gradient-to-r from-green-400 to-teal-400">🏛 Long-Term Opportunities</h1>
    <p class="text-sm text-indigo-200">Stable DeFi opportunities for long-term investment</p>
</div>
""", unsafe_allow_html=True)

if 'wallets' not in st.session_state:
    init_wallets(st.session_state)

# --- Async fetch long-term opportunities ---
@st.cache_data(ttl=300)
def cached_get_long_term_opportunities():
    results = asyncio.run(get_long_term_opportunities())
    # Ensure results are serializable (convert custom objects to dicts)
    serializable = [
    vars(r) if hasattr(r, "__dict__") else dict(r) if isinstance(r, (list, tuple)) else r
    for r in results
]
    return serializable

def main():
    st.subheader("🏛 Stable Opportunities")
    long_term_opps = cached_get_long_term_opportunities()
    logger.info(f"Fetched {len(long_term_opps)} long-term opportunities for rendering")
    if not long_term_opps:
        st.error("No opportunities found. Please check the database or run `python defi_scanner.py`.")
    else:
        render_grid_cards(long_term_opps, "long_term")

main()

# --- Additional Info ---
st.markdown("""
<div class="card bg-gradient-to-br from-green-900/30 to-teal-900/30 p-4 mt-4 rounded-lg shadow-md">
    <h3 class="text-lg font-semibold text-green-400 mb-2">💡 Selection Criteria</h3>
    <p class="text-indigo-200 text-sm">
        Long-term opportunities are selected for their stability, low risk, and high liquidity (TVL). 
        Ideal for consistent returns over extended periods.
    </p>
</div>
""", unsafe_allow_html=True)
