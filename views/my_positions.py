import streamlit as st
import asyncio
from datetime import datetime
from typing import Dict, Any
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
    confirm_tx,
)
from streamlit_javascript import st_javascript


# --- Async helpers ---
async def async_get_current_token_price(token_symbol: str, chain: str) -> float:
    try:
        return await asyncio.to_thread(get_token_price, token_symbol)
    except Exception as e:
        st.warning(f"Failed to fetch price for {token_symbol} on {chain}: {e}")
        return 0.0


async def async_get_chain_gas_fee(chain: str) -> float:
    try:
        w3 = connect_to_chain(chain)
        if not w3:
            return 0.0
        gas_price = w3.eth.gas_price
        gas_estimate = 200_000  # Adjusted for DeFi transactions
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
    """Fetch prices and gas fees concurrently for all positions"""
    price_tasks = [
        async_get_current_token_price(pos["token_symbol"], pos["chain"])
        for pos in positions
    ]
    gas_tasks = [async_get_chain_gas_fee(pos["chain"]) for pos in positions]
    prices = await asyncio.gather(*price_tasks, return_exceptions=True)
    gas_fees = await asyncio.gather(*gas_tasks, return_exceptions=True)
    return {
        pos["id"]: {
            "price": price if isinstance(price, float) else 0.0,
            "gas_fee": gas_fee if isinstance(gas_fee, float) else 0.0,
        }
        for pos, price, gas_fee in zip(positions, prices, gas_fees)
    }


# --- Render position cards ---
def render_position_cards(positions, data_map, status: str):
    if "expanded_cards" not in st.session_state:
        st.session_state.expanded_cards = {}

    if not positions:
        st.markdown(
            f"""
            <div class="compact-card bg-gradient-to-br from-gray-900/30 to-gray-700/30 p-4 rounded-lg">
                <p class="text-indigo-200 text-sm">No {status} positions</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        """
        <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem; padding: 0.5rem;'>
        """,
        unsafe_allow_html=True,
    )
    for pos in positions:
        card_key = f"position_{status}_{pos['id']}"
        current_price = data_map.get(pos["id"], {}).get("price", 0.0)
        current_value = pos["amount_invested"] * current_price
        pnl = current_value - pos["amount_invested"]
        pnl_pct = (
            (pnl / pos["amount_invested"] * 100) if pos["amount_invested"] > 0 else 0
        )
        gas_fee = data_map.get(pos["id"], {}).get("gas_fee", 0.0)
        logo_url = NETWORK_LOGOS.get(
            pos["chain"].lower(), "https://via.placeholder.com/16"
        )
        protocol_logo = PROTOCOL_LOGOS.get(
            pos["protocol"].lower() if pos.get("protocol") else "",
            "https://via.placeholder.com/16",
        )

        st.markdown(
            f"""
            <div class="compact-card bg-gradient-to-br from-gray-900/30 to-gray-700/30 {'card-expanded' if st.session_state.expanded_cards.get(card_key, False) else ''}" 
                 style="cursor: pointer;">
                <div class="flex justify-between items-start mb-2">
                    <div>
                        <h4 class="font-semibold text-indigo-200 text-xs mb-1">{pos['token_symbol']}</h4>
                        <span class="text-[0.65rem] text-gray-400">{pos['opportunity_name']}</span>
                    </div>
                    <img src="{protocol_logo}" alt="{pos['opportunity_name']}" class="w-4 h-4 rounded-full">
                </div>
                
                <div class="grid grid-cols-2 gap-1 mb-2 text-[0.65rem]">
                    <div class="flex flex-col"><span class="text-gray-400">Amount</span><span class="font-bold">{pos['amount_invested']:.2f}</span></div>
                    <div class="flex flex-col"><span class="text-gray-400">Value</span><span class="font-bold">${current_value:.2f}</span></div>
                    <div class="flex flex-col"><span class="text-gray-400">PnL</span><span class="font-bold {'text-green-400' if pnl >= 0 else 'text-red-400'}">${pnl:.2f}</span></div>
                    <div class="flex flex-col"><span class="text-gray-400">PnL %</span><span class="font-bold {'text-green-400' if pnl >= 0 else 'text-red-400'}">{pnl_pct:.2f}%</span></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("Details", expanded=st.session_state.expanded_cards.get(card_key, False)):
            st.markdown(
                f"""
                <div class="text-xs text-gray-300">
                    <p><strong>Chain:</strong> {pos['chain'].capitalize()}</p>
                    <p><strong>Protocol:</strong> {pos['protocol'] or 'N/A'}</p>
                    <p><strong>Entry Date:</strong> {pos['entry_date'].strftime('%Y-%m-%d %H:%M:%S') if pos['entry_date'] else 'N/A'}</p>
                    <p><strong>Tx Hash:</strong> <a href="{explorer_urls.get(pos['chain'].lower(), '')}{pos['tx_hash']}" target="_blank">{pos['tx_hash'][:6]}...{pos['tx_hash'][-4:]}</a></p>
                    <p><strong>Estimated Gas to Close:</strong> ${gas_fee:.2f}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if status == "active":
                if st.button("Close Position", key=f"close_{pos['id']}"):
                    wallet = get_connected_wallet(st.session_state, pos["chain"])
                    if not wallet or not wallet.address:
                        st.error("No connected wallet for this chain.")
                    else:
                        try:
                            protocol = pos["protocol"].lower() if pos.get("protocol") else ""
                            contract_address = CONTRACT_MAP.get(protocol, {}).get(pos["chain"].lower())
                            if not contract_address:
                                st.error(f"No contract address found for {protocol} on {pos['chain']}.")
                            else:
                                if protocol == "aave":
                                    tx_data = build_aave_withdraw_tx_data(
                                        pos["chain"], contract_address, pos["token_symbol"], pos["amount_invested"], wallet.address
                                    )
                                elif protocol == "compound":
                                    tx_data = build_compound_withdraw_tx_data(
                                        pos["chain"], contract_address, pos["token_symbol"], pos["amount_invested"], wallet.address
                                    )
                                else:
                                    st.error(f"Unsupported protocol: {protocol}")
                                    return

                                # 🔧 Safe type normalization
                                from_addr: str = str(tx_data.get("from", ""))
                                to_addr: str = str(tx_data.get("to", ""))
                                gas: int = int(tx_data.get("gas", 0) or 0)
                                gas_price: int = int(tx_data.get("gasPrice", 0) or 0)
                                data: str = str(tx_data.get("data", ""))
                                nonce: int = int(tx_data.get("nonce", 0) or 0)

                                st.write("Please confirm the transaction in your wallet.")
                                st.markdown(
                                    f"""
                                    <script>
                                    async function sendTransaction() {{
                                        try {{
                                            const txResponse = await window.ethereum.request({{
                                                method: 'eth_sendTransaction',
                                                params: [{{
                                                    from: '{from_addr}',
                                                    to: '{to_addr}',
                                                    gas: '0x{gas:x}',
                                                    gasPrice: '0x{gas_price:x}',
                                                    data: '{data}',
                                                    nonce: '0x{nonce:x}'
                                                }}]
                                            }});
                                            window.lastMessage = {{ type: 'streamlit:txSent', txHash: txResponse }};
                                            window.parent.postMessage(window.lastMessage, window.location.origin);
                                        }} catch (err) {{
                                            window.lastMessage = {{ type: 'streamlit:txError', error: err.message }};
                                            window.parent.postMessage(window.lastMessage, window.location.origin);
                                        }}
                                    }}
                                    sendTransaction();
                                    </script>
                                    """,
                                    unsafe_allow_html=True,
                                )
                                msg = get_post_message()
                                if msg.get("type") == "streamlit:txSent" and isinstance(msg.get("txHash"), str) and msg.get("txHash"):
                                    if confirm_tx(pos["chain"], msg["txHash"]):
                                        close_position(st.session_state, pos["id"], msg["txHash"])
                                        st.success("Position closed successfully!")
                                        st.rerun()
                                    else:
                                        st.error("Transaction failed.")
                                elif msg.get("type") == "streamlit:txError":
                                    st.error(f"Transaction error: {msg['error']}")
                        except Exception as e:
                            st.error(f"Failed to close position: {e}")

    st.markdown("</div>", unsafe_allow_html=True)


# --- Utility: get postMessage safely ---
def get_post_message() -> Dict[str, Any]:
    try:
        res = st_javascript("return window.lastMessage || {}")
        return res if isinstance(res, dict) else {}
    except Exception:
        return {}


# --- Main Render Function ---
def render():
    st.title("📊 My Positions")
    st.write("Manage your DeFi positions.")

    if "positions" not in st.session_state:
        st.session_state.positions = db.get_positions()

    active_positions = [p for p in st.session_state.positions if p["status"] == "active"]
    closed_positions = [p for p in st.session_state.positions if p["status"] == "closed"]

    # Fetch current prices and gas fees
    loop = asyncio.get_event_loop()
    if loop.is_running():
        data_map = loop.run_until_complete(fetch_positions_data(active_positions + closed_positions))
    else:
        data_map = asyncio.run(fetch_positions_data(active_positions + closed_positions))

    # Calculate stats
    total_invested = sum(pos["amount_invested"] for pos in active_positions)
    total_current_value = sum(
        pos["amount_invested"] * data_map.get(pos["id"], {}).get("price", 0.0)
        for pos in active_positions
    )
    total_pnl = total_current_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    st.markdown(
        f"""
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
