import streamlit as st
import asyncio
from datetime import datetime
from typing import Dict, Any
import json
import db
import requests
from wallet_utils import (
    get_connected_wallet,
    close_position,
    NETWORK_LOGOS,
    PROTOCOL_LOGOS,
    CONTRACT_MAP,
    CHAIN_IDS,
    explorer_urls,
    get_token_price,
    connect_to_chain,
    build_aave_withdraw_tx_data,
    build_compound_withdraw_tx_data,
    confirm_tx
)
from streamlit_javascript import st_javascript

# --- Async helpers ---
async def async_get_current_token_price(token_symbol: str, chain: str) -> float:
    try:
        # Run synchronous get_token_price in a separate thread
        return await asyncio.to_thread(get_token_price, token_symbol)
    except Exception:
        return 0.0

async def async_get_chain_gas_fee(chain: str) -> float:
    try:
        w3 = connect_to_chain(chain)
        if not w3:
            return 0.0
        gas_price = w3.eth.gas_price
        gas_estimate = 100_000
        native_token_map = {
            "ethereum": "ethereum",
            "bsc": "binancecoin",
            "arbitrum": "ethereum",
            "optimism": "ethereum",
            "base": "ethereum",
            "avalanche": "avalanche-2",
            "neon": "neon-token"
        }
        native_token = native_token_map.get(chain, "ethereum")
        data = await asyncio.to_thread(lambda: json.loads(
            requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={native_token}&vs_currencies=usd", timeout=10).text
        ))
        token_price = data.get(native_token, {}).get("usd", 2000.0)
        gas_fee_native = w3.from_wei(gas_price * gas_estimate, "ether")
        return float(gas_fee_native) * token_price
    except Exception:
        return 0.0

async def fetch_positions_data(positions):
    """Fetch prices and gas fees concurrently for all positions"""
    tasks = []
    for pos in positions:
        tasks.append(async_get_current_token_price(pos["token_symbol"], pos["chain"]))
    prices = await asyncio.gather(*tasks, return_exceptions=True)
    return {pos["position_id"]: price for pos, price in zip(positions, prices)}

# --- Render position cards (same as before, but current_value uses async prices) ---
def render():
    st.title("📊 My Positions")
    st.write("Manage your DeFi positions.")

def render_position_cards(positions, prices_map, status: str, columns: int = 3):
    if "expanded_cards" not in st.session_state:
        st.session_state.expanded_cards = {}

    if not positions:
        st.markdown(f"""
            <div class="compact-card bg-gradient-to-br from-gray-900/30 to-gray-700/30 p-4 rounded-lg">
                <p class="text-indigo-200 text-sm">No {status} positions</p>
            </div>
        """, unsafe_allow_html=True)
        return

    st.markdown("<div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem; padding: 0.5rem;'>", unsafe_allow_html=True)
    for i, pos in enumerate(positions):
        card_key = f"position_{status}_{pos['position_id']}"
        widget_suffix = f"{pos['position_id']}_{i}"
        
        current_price = prices_map.get(pos["position_id"], 0.0)
        current_value = pos["amount"] * current_price
        invested_value = pos["amount"] * pos["entry_price"]
        pnl = current_value - invested_value
        pnl_pct = (pnl / invested_value * 100) if invested_value > 0 else 0
        
        logo_url = NETWORK_LOGOS.get(pos["chain"].lower(), "https://via.placeholder.com/16")
        protocol_logo = PROTOCOL_LOGOS.get(pos["opportunity_name"].lower(), "https://via.placeholder.com/16")
        
        st.markdown(f"""
            <div class="compact-card bg-gradient-to-br from-gray-900/30 to-gray-700/30 {'card-expanded' if st.session_state.expanded_cards.get(card_key, False) else ''}" 
                 onclick="document.getElementById('{card_key}').click()"
                 style="cursor: pointer;">
                <div class="flex justify-between items-start mb-2">
                    <div>
                        <h4 class="font-semibold text-indigo-200 text-xs mb-1">{pos['token_symbol']}</h4>
                        <span class="text-[0.65rem] text-gray-400">{pos['opportunity_name']}</span>
                    </div>
                    <img src="{protocol_logo}" alt="{pos['opportunity_name']}" class="w-4 h-4 rounded-full">
                </div>
                
                <div class="grid grid-cols-2 gap-1 mb-2 text-[0.65rem]">
                    <div class="flex flex-col"><span class="text-gray-400">Amount</span><span class="font-bold">{pos['amount']:.2f}</span></div>
                    <div class="flex flex-col"><span class="text-gray-400">Value</span><span class="font-bold">${current_value:.2f}</span></div>
                    <div class="flex flex-col"><span class="text-gray-400">PnL</span><span class="font-bold {'text-green-400' if pnl >= 0 else 'text-red-400'}">${pnl:.2f}</span></div>
                    <div class="flex flex-col"><span class="text-gray-400">PnL %</span><span class="font-bold {'text-green-400' if pnl >= 0 else 'text-red-400'}">{pnl_pct:.2f}%</span></div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        # Expanders, buttons, wallet actions remain the same
    st.markdown("</div>", unsafe_allow_html=True)

# --- Main Async Entry ---
async def main():
    if 'positions' not in st.session_state:
        st.session_state.positions = db.get_positions()
    
    active_positions = [p for p in st.session_state.positions if p["status"]=="active"]
    closed_positions = [p for p in st.session_state.positions if p["status"]=="closed"]
    
    # Fetch current prices concurrently
    all_positions = active_positions + closed_positions
    prices_map = await fetch_positions_data(all_positions)
    
    # Stats
    total_invested = sum(pos["amount"] * pos["entry_price"] for pos in active_positions)
    total_current_value = sum(pos["amount"] * prices_map.get(pos["position_id"], 0.0) for pos in active_positions)
    total_pnl = total_current_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    
    st.markdown(f"""
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div class="compact-card bg-gradient-to-br from-blue-900/30 to-blue-700/30 p-3 rounded-lg">
            <h4 class="text-xs text-blue-300 mb-1">Total Invested</h4>
            <p class="text-lg font-bold text-white">${total_invested:.2f}</p>
        </div>
        <div class="compact-card bg-gradient-to-br from-green-900/30 to-green-700/30 p-3 rounded-lg">
            <h4 class="text-xs text-green-300 mb-1">Current Value</h4>
            <p class="text-lg font-bold text-white">${total_current_value:.2f}</p>
        </div>
        <div class="compact-card bg-gradient-to-br from-purple-900/30 to-purple-700/30 p-3 rounded-lg">
            <h4 class="text-xs text-purple-300 mb-1">Total PnL</h4>
            <p class="text-lg font-bold {'text-green-400' if total_pnl>=0 else 'text-red-400'}">${total_pnl:.2f}</p>
            <p class="text-xs {'text-green-400' if total_pnl>=0 else 'text-red-400'}">{total_pnl_pct:.2f}%</p>
        </div>
        <div class="compact-card bg-gradient-to-br from-gray-900/30 to-gray-700/30 p-3 rounded-lg">
            <h4 class="text-xs text-gray-300 mb-1">Active Positions</h4>
            <p class="text-lg font-bold text-white">{len(active_positions)}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🟢 Active Positions", "🔴 Closed Positions"])
    with tab1:
        render_position_cards(active_positions, prices_map, "active")
    with tab2:
        render_position_cards(closed_positions, prices_map, "closed")

# --- Run async in Streamlit ---
asyncio.run(main())
