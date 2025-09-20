import streamlit as st
import asyncio
import time
import json
import logging
from typing import List
from defi_scanner import fetch_meme_coins, MemeEntry
from wallet_utils import (
    build_erc20_approve_tx_data,
    init_wallets,
    get_connected_wallet,
    create_position,
    add_position_to_session,
    connect_to_chain,
    confirm_tx
)
from config import NETWORK_LOGOS, NETWORK_NAMES, PROTOCOL_LOGOS, BALANCE_SYMBOLS, CHAIN_IDS, CONTRACT_MAP, ERC20_TOKENS, explorer_urls
from streamlit_javascript import st_javascript

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    filename="logs/meme_coins.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

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
            return f"${value/1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"${value/1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value/1_000:.2f}K"
        return f"${value:,.2f}"
    except:
        return str(value)

def get_post_message():
    return st_javascript("return window.lastMessage || {}")

# --- Render Grid Cards ---
def render_meme_grid_cards(memes_list: List[MemeEntry], category_name: str):
    if "expanded_cards" not in st.session_state:
        st.session_state.expanded_cards = {}

    if not memes_list:
        st.warning(f"No {category_name} opportunities found.")
        return

    # Pagination
    items_per_page = 10
    total_pages = (len(memes_list) + items_per_page - 1) // items_per_page
    current_page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key="page_meme_coins")
    start_idx = (current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_memes = memes_list[start_idx:end_idx]

    st.markdown(
        """
        <style>
            .card { background: #1e1e2f; border-radius: 12px; padding: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            .text-green-400 { color: #10B981; }
            .text-red-400 { color: #EF4444; }
        </style>
        <div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem;'>
        """,
        unsafe_allow_html=True,
    )

    for i, meme in enumerate(paginated_memes):
        pool_id = safe_get(meme, "pool_id", f"unknown_{i}")
        card_key = f"{category_name}_{pool_id}"
        expanded = st.session_state.expanded_cards.get(card_key, False)

        chain = safe_get(meme, "chain", "unknown").capitalize()
        symbol = safe_get(meme, "symbol", "Unknown")
        price = safe_get(meme, "price_usd", "0.00")
        change = safe_get(meme, "change_24h_pct", "0")
        volume = safe_get(meme, "volume_24h_usd", 0)
        liquidity = safe_get(meme, "liquidity_usd", 0)
        contract = safe_get(meme, "contract_address", "0x0")
        project = safe_get(meme, "project", "Unknown")
        url = safe_get(meme, "url", "#")

        price_str = f"${float(str(price).lstrip('$')):,.4f}" if float(str(price).lstrip('$')) < 1 else f"${float(str(price).lstrip('$')):,.2f}"
        change_str = f"{float(str(change).rstrip('%')):.2f}%"
        volume_str = format_number(volume)
        liquidity_str = format_number(liquidity)

        logo_url = NETWORK_LOGOS.get(chain.lower(), "https://via.placeholder.com/32?text=Logo")
        explorer_url = explorer_urls.get(chain.lower(), "#") + contract

        st.markdown(
            f"""
            <div class="card" onclick="document.getElementById('{card_key}').click()">
                <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;'>
                    <div style='display:flex;align-items:center;'>
                        <img src="{logo_url}" alt="{chain}" style="width:24px;height:24px;border-radius:50%;margin-right:0.5rem;">
                        <h3 style='margin:0;font-size:1rem;font-weight:600;color:#c7d2fe;'>{symbol}</h3>
                    </div>
                </div>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    Chain: {chain} | Project: {project}
                </p>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    Price: {price_str} | 24h: <span class="{'text-green-400' if float(change_str.rstrip('%')) >= 0 else 'text-red-400'}">{change_str}</span>
                </p>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    Volume 24h: {volume_str}
                </p>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    Liquidity: {liquidity_str}
                </p>
                <a href="{url}" target="_blank" style='color:#6366f1;text-decoration:none;font-size:0.9rem;'>
                    View Opportunity ↗
                </a>
                <a href="{explorer_url}" target="_blank" style='color:#6366f1;text-decoration:none;font-size:0.9rem;margin-left:1rem;'>
                    Explore Contract ↗
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container():
            st.checkbox("Expand", value=expanded, key=card_key)
            if expanded:
                connected_wallet = get_connected_wallet(st.session_state, chain.lower())
                if not connected_wallet:
                    st.info(f"Connect wallet for {chain} to swap.")
                else:
                    available_tokens = list(ERC20_TOKENS.get(chain.lower(), {}).keys())
                    selected_token = st.selectbox("Select Token to Swap From", available_tokens, key=f"token_{card_key}")
                    amount = st.number_input("Amount to Swap", min_value=0.0, step=0.1, key=f"amount_{card_key}")
                    if st.button("Swap", key=f"swap_{card_key}"):
                        try:
                            router_address = CONTRACT_MAP.get("uniswap", {}).get(chain.lower())
                            token_address = ERC20_TOKENS[chain.lower()].get(selected_token)
                            chain_id = CHAIN_IDS.get(chain.lower(), 0)
                            if not router_address or not token_address:
                                st.error("Invalid router or token address")
                                continue

                            approve_tx = build_erc20_approve_tx_data(chain.lower(), token_address, router_address, amount, connected_wallet.address) # type: ignore
                            approve_tx['chainId'] = chain_id
                            st.markdown(f"<script>performDeFiAction('approve',{json.dumps(approve_tx)});</script>", unsafe_allow_html=True)
                            time.sleep(1)
                            approve_resp = get_post_message()
                            if approve_resp.get("type") == "streamlit:txSuccess" and isinstance(approve_resp.get("txHash"), str) and approve_resp.get("txHash"):
                                st.success("Approve confirmed!")
                            else:
                                st.error("Approve failed")
                                continue

                            swap_tx = {
                                "from": connected_wallet.address,
                                "to": router_address,
                                "data": "0x",
                                "value": 0,
                                "chainId": chain_id
                            }
                            st.markdown(f"<script>performDeFiAction('swap',{json.dumps(swap_tx)});</script>", unsafe_allow_html=True)
                            time.sleep(1)
                            swap_resp = get_post_message()
                            if swap_resp.get("type") == "streamlit:txSuccess" and isinstance(swap_resp.get("txHash"), str) and swap_resp.get("txHash"):
                                position = create_position(chain.lower(), symbol, selected_token, amount, swap_resp['txHash'])
                                add_position_to_session(st.session_state, position)
                                st.success(f"Swapped {amount} {selected_token} for {symbol}!")
                            else:
                                st.error("Swap failed")
                        except Exception as e:
                            st.error(f"Swap error: {e}")
                        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# --- Main Render Function ---
def render():
    st.title("🐸 Meme Coins")
    st.write("Trending meme coins and speculative plays.")

    # Initialize wallets
    if 'wallets' not in st.session_state:
        init_wallets(st.session_state)

    # Fetch meme coins
    @st.cache_data(ttl=300)
    def cached_get_meme_coins() -> List[MemeEntry]:
        return asyncio.run(fetch_meme_coins())

    with st.spinner("🔍 Scanning for trending meme coins..."):
        meme_coins = cached_get_meme_coins()
        if not meme_coins:
            st.error("No meme coins found.")
        else:
            render_meme_grid_cards(meme_coins, "meme_coins")

    # Risk warning
    st.markdown(
        """
        <div class="card bg-gradient-to-br from-yellow-900/30 to-orange-900/30 p-4 mt-4 rounded-lg shadow-md">
            <h3 class="text-lg font-semibold text-yellow-400 mb-2">⚠️ Risk Warning</h3>
            <p class="text-indigo-200 text-sm">
                Meme coins are highly speculative and volatile. Only invest what you can afford to lose, 
                and conduct thorough research before participating in these markets.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    render()