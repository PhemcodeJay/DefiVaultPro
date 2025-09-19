import json
import time
import streamlit as st
import asyncio
from typing import Dict, Any
import db
import requests
from views.layer2_focus import get_post_message
from wallet_utils import (
    get_connected_wallet,
    close_position,
    get_token_price,
    connect_to_chain,
    build_aave_withdraw_tx_data,
    build_compound_withdraw_tx_data,
    confirm_tx,
)
from config import NETWORK_LOGOS, NETWORK_NAMES, PROTOCOL_LOGOS, BALANCE_SYMBOLS, CHAIN_IDS, CONTRACT_MAP, ERC20_TOKENS, explorer_urls
from streamlit_javascript import st_javascript

# --- Async Helpers ---
async def async_get_current_token_price(token_symbol: str, chain: str) -> float:
    """Fetch token price safely in a thread."""
    try:
        return await asyncio.to_thread(get_token_price, token_symbol)
    except Exception as e:
        st.warning(f"Failed to fetch price for {token_symbol} on {chain}: {e}")
        return 0.0

async def async_get_chain_gas_fee(chain: str) -> float:
    """Estimate chain gas fee in USD."""
    try:
        w3 = connect_to_chain(chain)
        if not w3:
            return 0.0
        gas_price = w3.eth.gas_price
        gas_estimate = 200_000  # Standard for DeFi tx
        native_token_map = {
            "ethereum": "ethereum",
            "bsc": "binancecoin",
            "arbitrum": "ethereum",
            "optimism": "ethereum",
            "base": "ethereum",
            "avalanche": "avalanche-2",
            "neon": "neon-token",
        }
        native_token = native_token_map.get(chain.lower(), "ethereum")
        data = await asyncio.to_thread(
            lambda: requests.get(
                f"https://api.coingecko.com/api/v3/simple/price?ids={native_token}&vs_currencies=usd",
                timeout=10,
            ).json()
        )
        token_price = data.get(native_token, {}).get("usd", 2000.0)
        gas_fee_native = w3.from_wei(gas_price * gas_estimate, "ether")
        return float(gas_fee_native) * token_price
    except Exception as e:
        st.warning(f"Failed to fetch gas fee for {chain}: {e}")
        return 0.0

async def fetch_positions_data(positions):
    """Fetch all prices and gas fees concurrently."""
    price_tasks = [
        async_get_current_token_price(pos["token_symbol"], pos["chain"])
        for pos in positions
    ]
    gas_tasks = [async_get_chain_gas_fee(pos["chain"]) for pos in positions]
    prices = await asyncio.gather(*price_tasks, return_exceptions=True)
    gas_fees = await asyncio.gather(*gas_tasks, return_exceptions=True)
    return {
        pos["id"]: {
            "price": prices if isinstance(prices, float) else 0.0,
            "gas_fee": gas_fees if isinstance(gas_fees, float) else 0.0,
        }
        for pos in positions
    }

# --- Render Position Cards ---
def render_position_cards(positions, data_map, status_type: str):
    if not positions:
        st.info(f"No {status_type} positions found.")
        return

    # Pagination
    items_per_page = 5
    total_pages = (len(positions) + items_per_page - 1) // items_per_page
    current_page = st.number_input(f"{status_type.capitalize()} Page", min_value=1, max_value=total_pages, value=1, key=f"page_{status_type}")
    start_idx = (current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_positions = positions[start_idx:end_idx]

    st.markdown(
        """
        <style>
            .card { background: #1e1e2f; border-radius: 12px; padding: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            .text-green-400 { color: #10B981; }
            .text-red-400 { color: #EF4444; }
        </style>
        <div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem;'>
        """,
        unsafe_allow_html=True,
    )

    for pos in paginated_positions:
        chain = pos.get("chain", "unknown").capitalize()
        protocol = pos.get("protocol", "unknown").lower()
        opportunity = pos.get("opportunity_name", "Unknown")
        symbol = pos.get("token_symbol", "Unknown")
        invested = pos.get("amount_invested", 0.0)
        tx_hash = pos.get("tx_hash", "No Tx")
        entry_date = pos.get("entry_date", "Unknown")
        exit_date = pos.get("exit_date", "Active") if status_type == "closed" else "Active"
        apy = pos.get("apy", 0.0)

        data = data_map.get(pos["id"], {})
        price = data.get("price", 0.0)
        gas_fee = data.get("gas_fee", 0.0)
        current_value = invested * price
        pnl = current_value - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0

        logo_url = NETWORK_LOGOS.get(chain.lower(), "https://via.placeholder.com/32?text=Logo")
        protocol_logo = PROTOCOL_LOGOS.get(protocol, "https://via.placeholder.com/32?text=Protocol")
        explorer_url = explorer_urls.get(chain.lower(), "#") + tx_hash if tx_hash != "No Tx" else "#"

        st.markdown(
            f"""
            <div class="card">
                <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;'>
                    <div style='display:flex;align-items:center;'>
                        <img src="{logo_url}" alt="{chain}" style="width:24px;height:24px;border-radius:50%;margin-right:0.5rem;">
                        <h3 style='margin:0;font-size:1rem;font-weight:600;color:#c7d2fe;'>{opportunity}</h3>
                    </div>
                    <img src="{protocol_logo}" alt="{protocol.capitalize()}" style="width:24px;height:24px;border-radius:50%;">
                </div>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    Chain: {chain} | Protocol: {protocol.capitalize()}
                </p>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    Invested: {invested:.2f} {symbol} (${invested * price:.2f})
                </p>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    Current Value: ${current_value:.2f}
                </p>
                <p class="{'text-green-400' if pnl >= 0 else 'text-red-400'}" style='font-size:0.9rem;margin-bottom:0.25rem;'>
                    PnL: ${pnl:.2f} ({pnl_pct:.2f}%)
                </p>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    APY: {apy:.2f}% | Gas to Close: ${gas_fee:.2f}
                </p>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    Entry: {entry_date} | Exit: {exit_date}
                </p>
                <a href="{explorer_url}" target="_blank" style='color:#6366f1;text-decoration:none;font-size:0.9rem;'>
                    View Tx on Explorer ↗
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if status_type == "active":
            with st.container():
                if st.button("Close Position", key=f"close_{pos['id']}"):
                    connected_wallet = get_connected_wallet(st.session_state, chain.lower())
                    if not connected_wallet:
                        st.error(f"No connected wallet for {chain}.")
                    else:
                        try:
                            protocol = protocol.lower()
                            token_address = pos.get("token_address")
                            pool_address = CONTRACT_MAP.get(protocol, {}).get(chain.lower())
                            if not pool_address or not token_address:
                                st.error("Invalid pool or token address")
                            else:
                                if 'aave' in protocol:
                                    withdraw_tx = build_aave_withdraw_tx_data(chain.lower(), token_address, invested, connected_wallet.address) # type: ignore
                                elif 'compound' in protocol:
                                    withdraw_tx = build_compound_withdraw_tx_data(chain.lower(), token_address, invested, connected_wallet.address) # type: ignore
                                else:
                                    st.error(f"Unsupported protocol: {protocol}")
                                    continue

                                withdraw_tx['chainId'] = CHAIN_IDS.get(chain.lower(), 0)
                                st.markdown(f"<script>performDeFiAction('withdraw',{json.dumps(withdraw_tx)});</script>", unsafe_allow_html=True)
                                time.sleep(1)
                                response = get_post_message()
                                if response.get("type") == "streamlit:txSuccess" and isinstance(response.get("txHash"), str) and response.get("txHash"):
                                    if confirm_tx(chain.lower(), response['txHash']):
                                        if close_position(st.session_state, pos["id"], response['txHash']):
                                            st.success("Position closed successfully.")
                                            st.rerun()
                                        else:
                                            st.error("Failed to close position.")
                                    else:
                                        st.error("Transaction confirmation failed.")
                                else:
                                    st.error("Withdraw transaction failed.")
                        except Exception as e:
                            st.error(f"Failed to close position: {str(e)}")

    st.markdown("</div>", unsafe_allow_html=True)

# --- Main Render Function ---
def render():
    st.title("📊 My Positions")
    st.write("Manage your DeFi positions.")

    if "positions" not in st.session_state:
        st.session_state.positions = db.get_positions()

    active_positions = [p for p in st.session_state.positions if p["status"] == "active"]
    closed_positions = [p for p in st.session_state.positions if p["status"] == "closed"]

    try:
        data_map = asyncio.run(fetch_positions_data(active_positions + closed_positions))
    except Exception as e:
        st.warning(f"Failed to fetch price/gas data: {e}")
        data_map = {}

    # Summary cards
    total_invested = sum(pos["amount_invested"] for pos in active_positions)
    total_current_value = sum(
        pos["amount_invested"] * data_map.get(pos["id"], {}).get("price", 0.0)
        for pos in active_positions
    )
    total_pnl = total_current_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    st.markdown(
        f"""
        <style>
            .compact-card {{ background: linear-gradient(135deg, rgba(49,46,129,0.3), rgba(30,64,175,0.3));
                            border-radius: 12px; padding: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        </style>
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div class="compact-card">
                <h4 class="text-xs text-blue-300 mb-1">Total Invested</h4>
                <p class="text-lg font-bold text-white">${total_invested:.2f}</p>
            </div>
            <div class="compact-card">
                <h4 class="text-xs text-green-300 mb-1">Current Value</h4>
                <p class="text-lg font-bold text-white">${total_current_value:.2f}</p>
            </div>
            <div class="compact-card">
                <h4 class="text-xs text-purple-300 mb-1">Total PnL</h4>
                <p class="text-lg font-bold {'text-green-400' if total_pnl>=0 else 'text-red-400'}">${total_pnl:.2f}</p>
                <p class="text-xs {'text-green-400' if total_pnl>=0 else 'text-red-400'}">{total_pnl_pct:.2f}%</p>
            </div>
            <div class="compact-card">
                <h4 class="text-xs text-gray-300 mb-1">Active Positions</h4>
                <p class="text-lg font-bold text-white">{len(active_positions)}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["🟢 Active Positions", "🔴 Closed Positions"])
    with tab1:
        render_position_cards(active_positions, data_map, "active")
    with tab2:
        render_position_cards(closed_positions, data_map, "closed")

if __name__ == "__main__":
    render()