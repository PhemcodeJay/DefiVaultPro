import streamlit as st
import asyncio
import time
import json
import logging
from typing import List
from defi_scanner import fetch_meme_coins, MemeEntry
from wallet_utils import (
    init_wallets,
    get_connected_wallet,
    create_position,
    add_position_to_session,
    NETWORK_LOGOS,
    BALANCE_SYMBOLS,
    ERC20_TOKENS,
    ERC20_ABI,
    CHAIN_IDS,
    CONTRACT_MAP,
    explorer_urls,
    connect_to_chain,
    confirm_tx
)
from streamlit_javascript import st_javascript

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

    st.markdown("<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem;'>", unsafe_allow_html=True)

    for i, meme in enumerate(memes_list):
        pool_id = safe_get(meme, "pool_id", f"unknown_{i}")
        card_key = f"{category_name}_{pool_id}"
        expanded = st.session_state.expanded_cards.get(card_key, False)

        chain = safe_get(meme, "chain", "Unknown").capitalize()
        symbol = safe_get(meme, "symbol", "Unknown")
        price = safe_get(meme, "price_usd", "$0.00")
        change = safe_get(meme, "change_24h_pct", "0%")
        volume = safe_get(meme, "volume_24h_usd", 0)
        liquidity = safe_get(meme, "liquidity_usd", 0)
        contract = safe_get(meme, "contract_address", "0x0")
        project = safe_get(meme, "project", "Unknown")
        url = safe_get(meme, "url", "#")

        price_str = f"${float(str(price).lstrip('$')):,.4f}" if float(str(price).lstrip('$')) < 1 else f"${float(str(price).lstrip('$')):,.2f}"
        change_str = f"{float(str(change).rstrip('%')):.2f}%"
        volume_str = format_number(volume)
        liquidity_str = format_number(liquidity)

        logo_url = NETWORK_LOGOS.get(chain.lower(), "https://via.placeholder.com/12")
        explorer_url = explorer_urls.get(chain.lower(), "#") + contract

        st.markdown(f"""
            <div style='padding:1rem;background:#1e1e2f;border-radius:12px;cursor:pointer;'>
                <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;'>
                    <div style='display:flex;align-items:center;'>
                        <img src="{logo_url}" width="16" height="16" style="margin-right:0.5rem;">
                        <b style='color:#dbeafe'>{symbol}</b>
                    </div>
                    <span style='color:{'#10B981' if float(change_str.rstrip('%'))>=0 else '#EF4444'}'>{change_str}</span>
                </div>
                <div style='display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;font-size:12px;'>
                    <div>Price: <b>{price_str}</b></div>
                    <div>24h Volume: <b>{volume_str}</b></div>
                    <div>Liquidity: <b>{liquidity_str}</b></div>
                    <div>Project: <b>{project}</b></div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        expanded = st.checkbox("Expand", value=expanded, key=f"{card_key}_checkbox", label_visibility="collapsed")
        st.session_state.expanded_cards[card_key] = expanded

        if expanded:
            with st.expander("", expanded=True):
                st.markdown(f"""
                    <div style='padding:0.5rem;background:#111; border-radius:8px;color:#ccc;font-size:12px;'>
                        Contract: <a href="{explorer_url}" target="_blank">{contract[:6]}...{contract[-4:]}</a><br>
                        Details: <a href="{url}" target="_blank">View on Dex</a>
                    </div>
                """, unsafe_allow_html=True)

                connected_wallet = get_connected_wallet(st.session_state, chain.lower())
                if connected_wallet and connected_wallet.verified and connected_wallet.address:
                    token_options = list(ERC20_TOKENS.get(chain.lower(), {}).keys()) + [BALANCE_SYMBOLS.get(chain.lower(), "Native")]
                    selected_token = st.selectbox("Select Token", token_options, key=f"token_{i}")
                    token_address = ERC20_TOKENS.get(chain.lower(), {}).get(selected_token, "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
                    amount = st.number_input("Amount", min_value=0.0, value=1.0, step=0.01, key=f"amount_{i}")

                    if amount > 0 and st.button("💸 Swap with MetaMask", key=f"swap_{i}"):
                        try:
                            router_address = CONTRACT_MAP.get("uniswap", {}).get(chain.lower(), "")
                            if not router_address:
                                st.error(f"No router for {chain}")
                                continue
                            approve_tx = {
                                "from": connected_wallet.address,
                                "to": token_address,
                                "data": "0x",  # simplified
                                "value": 0,
                                "chainId": CHAIN_IDS.get(chain.lower(), 0)
                            }
                            st.markdown(f"<script>performDeFiAction('approve',{json.dumps(approve_tx)});</script>", unsafe_allow_html=True)  # type: ignore
                            time.sleep(1)
                            response = get_post_message()
                            if response.get("type") == "streamlit:txSuccess" and isinstance(response.get("txHash"), str) and response.get("txHash"):
                                st.success("Approve confirmed!")
                            else:
                                st.error("Approve failed")
                                continue

                            swap_tx = {
                                "from": connected_wallet.address,
                                "to": router_address,
                                "data": "0x",
                                "value": 0,
                                "chainId": CHAIN_IDS.get(chain.lower(), 0)
                            }
                            st.markdown(f"<script>performDeFiAction('swap',{json.dumps(swap_tx)});</script>", unsafe_allow_html=True)  # type: ignore
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
    if "wallets" not in st.session_state:
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
    st.markdown("""
    <div class="card bg-gradient-to-br from-yellow-900/30 to-orange-900/30 p-4 mt-4 rounded-lg shadow-md">
        <h3 class="text-lg font-semibold text-yellow-400 mb-2">⚠️ Risk Warning</h3>
        <p class="text-indigo-200 text-sm">
            Meme coins are highly speculative and volatile. Only invest what you can afford to lose, 
            and conduct thorough research before participating in these markets.
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    render()