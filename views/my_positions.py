import json
import time
import streamlit as st
import asyncio
from typing import Dict, Any, List
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
import logging
from utils import safe_get, format_number

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    filename="logs/my_positions.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

# --- Async Helpers ---
async def async_get_current_token_price(token_symbol: str, chain: str) -> float:
    """Fetch token price safely in a thread."""
    try:
        if not isinstance(token_symbol, str) or not isinstance(chain, str):
            logger.warning(f"Invalid token_symbol or chain: {token_symbol}, {chain}")
            return 0.0
        price = await asyncio.to_thread(get_token_price, token_symbol)
        return float(price) if isinstance(price, (int, float, str)) and float(price) >= 0 else 0.0
    except Exception as e:
        logger.warning(f"Failed to fetch price for {token_symbol} on {chain}: {e}")
        return 0.0

async def async_get_chain_gas_fee(chain: str) -> float:
    """Estimate chain gas fee in USD."""
    try:
        if not isinstance(chain, str):
            logger.warning(f"Invalid chain: {chain}")
            return 0.0
        w3 = connect_to_chain(chain.lower())
        if not w3:
            logger.warning(f"No Web3 connection for chain: {chain}")
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
        token_price = float(safe_get(data, native_token, {}).get("usd", 2000.0))
        gas_fee_native = w3.from_wei(gas_price * gas_estimate, "ether")
        return float(gas_fee_native) * token_price if isinstance(gas_fee_native, (int, float)) else 0.0
    except Exception as e:
        logger.warning(f"Failed to fetch gas fee for {chain}: {e}")
        return 0.0

async def fetch_positions_data(positions: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Fetch all prices and gas fees concurrently."""
    if not positions:
        return {}
    price_tasks = [
        async_get_current_token_price(pos["token_symbol"], pos["chain"])
        for pos in positions
    ]
    gas_tasks = [async_get_chain_gas_fee(pos["chain"]) for pos in positions]
    prices = await asyncio.gather(*price_tasks, return_exceptions=True)
    gas_fees = await asyncio.gather(*gas_tasks, return_exceptions=True)
    data_map = {}
    for i, pos in enumerate(positions):
        price = prices[i]
        gas_fee = gas_fees[i]
        price_value = 0.0
        gas_fee_value = 0.0
        if not isinstance(price, Exception):
            try:
                price_value = float(price) if isinstance(price, (int, float)) else 0.0
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid price for position {pos['id']}: {e}")
        if not isinstance(gas_fee, Exception):
            try:
                gas_fee_value = float(gas_fee) if isinstance(gas_fee, (int, float)) else 0.0
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid gas fee for position {pos['id']}: {e}")
        data_map[pos["id"]] = {"price": price_value, "gas_fee": gas_fee_value}
    return data_map

# --- Render Position Cards ---
def render_position_cards(positions, data_map, status: str):
    if not positions:
        st.info(f"No {status} positions found.")
        return

    st.markdown(
        """
        <style>
            .card { background: #1e1e2f; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            .text-green-400 { color: #10B981; }
            .text-red-400 { color: #EF4444; }
        </style>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        """,
        unsafe_allow_html=True,
    )

    for pos in positions:
        try:
            chain = safe_get(pos, "chain", "unknown")
            opportunity_name = safe_get(pos, "opportunity_name", "Unknown")
            token_symbol = safe_get(pos, "token_symbol", "Unknown")
            protocol = safe_get(pos, "protocol", "Unknown")
            tx_hash = safe_get(pos, "tx_hash", "#")
            if not all(isinstance(x, str) for x in [chain, opportunity_name, token_symbol, protocol, tx_hash]):
                logger.warning(f"Skipping position with invalid string fields: {pos}")
                continue
            amount_invested = float(safe_get(pos, "amount_invested", 0.0))
            apy = float(safe_get(pos, "apy", 0.0))
            if amount_invested < 0 or apy < 0:
                logger.warning(f"Skipping position with negative amount_invested/apy: {pos}")
                continue

            position_id = pos["id"]
            price = float(safe_get(data_map.get(position_id, {}), "price", 0.0))
            gas_fee = float(safe_get(data_map.get(position_id, {}), "gas_fee", 0.0))
            current_value = amount_invested * price
            pnl = current_value - amount_invested
            pnl_pct = (pnl / amount_invested * 100) if amount_invested > 0 else 0.0
            explorer_url = explorer_urls.get(chain.lower(), "#") + tx_hash

            logo_url = NETWORK_LOGOS.get(chain.lower(), "https://via.placeholder.com/32?text=Logo")
            protocol_logo = PROTOCOL_LOGOS.get(protocol.lower(), "https://via.placeholder.com/32?text=Protocol")

            st.markdown(
                f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
                        <div style="display:flex; align-items:center;">
                            <img src="{logo_url}" alt="{chain}" style="width:24px; height:24px; border-radius:50%; margin-right:0.6rem;">
                            <h3 style="margin:0; font-size:1rem; font-weight:600; color:#c7d2fe;">
                                {opportunity_name}
                            </h3>
                        </div>
                        <img src="{protocol_logo}" alt="{protocol}" style="width:24px; height:24px; border-radius:50%;">
                    </div>
                    <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                        Chain: {chain.capitalize()} | Token: {token_symbol}
                    </p>
                    <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                        Amount: {format_number(amount_invested)}
                    </p>
                    <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                        Current Value: {format_number(current_value)}
                    </p>
                    <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                        PnL: <span class="{'text-green-400' if pnl >= 0 else 'text-red-400'}">{format_number(pnl)} ({pnl_pct:.2f}%)</span>
                    </p>
                    <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                        APY: {apy:.2f}%
                    </p>
                    <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                        Gas to Exit: {format_number(gas_fee)}
                    </p>
                    <a href="{explorer_url}" target="_blank" style="color:#6366f1; text-decoration:none;">View Transaction ↗</a>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if status == "active":
                connected_wallet = get_connected_wallet(st.session_state, chain=chain.lower())
                if connected_wallet and connected_wallet.address:
                    if st.button("Close Position", key=f"close_{position_id}"):
                        try:
                            pool_address = CONTRACT_MAP.get(protocol.lower(), {}).get(chain.lower(), "0x0")
                            token_address = ERC20_TOKENS.get(token_symbol, {}).get(chain.lower(), "0x0")
                            if not pool_address or not token_address:
                                st.error("Invalid pool or token address")
                                continue

                            if 'aave' in protocol.lower():
                                withdraw_tx = build_aave_withdraw_tx_data(
                                    chain.lower(), pool_address, token_address, amount_invested, str(connected_wallet.address)
                                )
                            elif 'compound' in protocol.lower():
                                withdraw_tx = build_compound_withdraw_tx_data(
                                    chain.lower(), pool_address, token_address, amount_invested, str(connected_wallet.address)
                                )
                            else:
                                st.error(f"Unsupported protocol: {protocol}")
                                continue

                            withdraw_tx['chainId'] = CHAIN_IDS.get(chain.lower(), 1)
                            st.markdown(
                                f"<script>performDeFiAction('withdraw',{json.dumps(withdraw_tx)});</script>",
                                unsafe_allow_html=True
                            )
                            time.sleep(1)
                            response = get_post_message()
                            if response.get("type") == "streamlit:txSuccess" and isinstance(response.get("txHash"), str) and response.get("txHash"):
                                if confirm_tx(chain.lower(), response['txHash']):
                                    if close_position(st.session_state, position_id, response['txHash']):
                                        st.success(f"Position {position_id} closed successfully!")
                                    else:
                                        st.error("Failed to close position")
                                else:
                                    st.error("Withdraw transaction failed")
                            else:
                                st.error("Withdraw transaction failed")
                            st.rerun()
                        except Exception as e:
                            logger.error(f"Failed to close position {position_id}: {e}")
                            st.error(f"Failed to close position: {str(e)}")
                else:
                    st.warning(f"Connect wallet to close position on {chain}.")
        except Exception as e:
            logger.warning(f"Error rendering position {safe_get(pos, 'id', 'unknown')}: {e}")
            continue

    st.markdown("</div>", unsafe_allow_html=True)

# --- Main Render Function ---
def render():
    st.title("📊 My Positions")
    st.write("Manage your DeFi positions.")

    if "positions" not in st.session_state:
        st.session_state.positions = db.get_positions()

    # Validate and clean positions
    cleaned_positions = []
    for pos in st.session_state.positions:
        try:
            chain = safe_get(pos, "chain", "unknown")
            opportunity_name = safe_get(pos, "opportunity_name", "Unknown")
            token_symbol = safe_get(pos, "token_symbol", "Unknown")
            protocol = safe_get(pos, "protocol", "Unknown")
            status = safe_get(pos, "status", "unknown")
            tx_hash = safe_get(pos, "tx_hash", "#")
            if not all(isinstance(x, str) for x in [chain, opportunity_name, token_symbol, protocol, status, tx_hash]):
                logger.warning(f"Skipping position with invalid string fields: {pos}")
                continue
            amount_invested = float(safe_get(pos, "amount_invested", 0.0))
            apy = float(safe_get(pos, "apy", 0.0))
            if amount_invested < 0 or apy < 0:
                logger.warning(f"Skipping position with negative amount_invested/apy: {pos}")
                continue
            cleaned_positions.append({
                "id": pos["id"],
                "chain": chain,
                "opportunity_name": opportunity_name,
                "token_symbol": token_symbol,
                "protocol": protocol,
                "amount_invested": amount_invested,
                "apy": apy,
                "status": status,
                "tx_hash": tx_hash
            })
        except Exception as e:
            logger.warning(f"Error processing position {safe_get(pos, 'id', 'unknown')}: {e}")
            continue

    if not cleaned_positions:
        st.warning("No valid positions found.")
        return

    active_positions = [p for p in cleaned_positions if p["status"] == "active"]
    closed_positions = [p for p in cleaned_positions if p["status"] == "closed"]

    try:
        data_map = asyncio.run(fetch_positions_data(cleaned_positions))
    except Exception as e:
        logger.warning(f"Failed to fetch price/gas data: {e}")
        st.warning(f"Failed to fetch price/gas data: {e}")
        data_map = {}

    # Summary cards
    total_invested = sum(pos["amount_invested"] for pos in active_positions)
    total_current_value = sum(
        pos["amount_invested"] * float(safe_get(data_map.get(pos["id"], {}), "price", 0.0))
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
                <p class="text-lg font-bold text-white">{format_number(total_invested)}</p>
            </div>
            <div class="compact-card">
                <h4 class="text-xs text-green-300 mb-1">Current Value</h4>
                <p class="text-lg font-bold text-white">{format_number(total_current_value)}</p>
            </div>
            <div class="compact-card">
                <h4 class="text-xs text-purple-300 mb-1">Total PnL</h4>
                <p class="text-lg font-bold {'text-green-400' if total_pnl>=0 else 'text-red-400'}">{format_number(total_pnl)}</p>
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