import streamlit as st
import time
import json
import logging
from wallet_utils import (
    init_wallets, get_connected_wallet, add_position_to_session,
    create_position, build_erc20_approve_tx_data, confirm_tx,
    build_uniswap_swap_tx_data
)
from config import NETWORK_LOGOS, PROTOCOL_LOGOS, CHAIN_IDS, CONTRACT_MAP, ERC20_TOKENS, explorer_urls
from streamlit_javascript import st_javascript
import db

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
            return f"${value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value / 1_000:.2f}K"
        return f"${value:,.2f}"
    except Exception:
        return str(value)

def get_post_message():
    return st_javascript("return window.lastMessage || {}")

# --- Render Grid Cards ---
def render_meme_grid_cards(memes_list, category_name: str):
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
        project = safe_get(meme, "project", "Unknown")
        name = safe_get(meme, "name", "Unknown")
        symbol = safe_get(meme, "symbol", "Unknown")
        price = safe_get(meme, "price", "0.00")
        liquidity_usd = safe_get(meme, "liquidity_usd", "0")
        volume_24h_usd = safe_get(meme, "volume_24h_usd", "0")
        change_24h_pct = safe_get(meme, "change_24h_pct", "0%")
        risk = safe_get(meme, "risk", "Unknown")
        url = safe_get(meme, "url", "#")
        contract_address = safe_get(meme, "contract_address", "0x0")
        market_cap = format_number(safe_get(meme, "market_cap", 0))
        growth_potential = safe_get(meme, "growth_potential", "0%")

        logo_url = NETWORK_LOGOS.get(chain.lower(), "https://via.placeholder.com/32?text=Logo")
        protocol_logo = PROTOCOL_LOGOS.get(project.lower(), "https://via.placeholder.com/32?text=Protocol")
        explorer_url = explorer_urls.get(chain.lower(), "#") + contract_address

        st.markdown(
            f"""
            <div class="card" onclick="document.getElementById('{card_key}').click()">
                <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;'>
                    <div style='display:flex;align-items:center;'>
                        <img src="{logo_url}" alt="{chain}" style="width:24px;height:24px;border-radius:50%;margin-right:0.5rem;">
                        <h3 style='margin:0;font-size:1.1rem;'>{name}</h3>
                    </div>
                    <img src="{protocol_logo}" alt="{project}" style="width:24px;height:24px;border-radius:50%;">
                </div>
                <p style='margin:0.2rem 0;'><strong>Chain:</strong> {chain} | <strong>Symbol:</strong> {symbol}</p>
                <p style='margin:0.2rem 0;'><strong>Price:</strong> {price}</p>
                <p style='margin:0.2rem 0;'><strong>Liquidity:</strong> {liquidity_usd} | <strong>Volume 24h:</strong> {volume_24h_usd}</p>
                <p style='margin:0.2rem 0;'><strong>24h Change:</strong> {change_24h_pct}</p>
                <p style='margin:0.2rem 0;'><strong>Risk:</strong> {risk} | <strong>Market Cap:</strong> {market_cap}</p>
                <p style='margin:0.2rem 0;'><strong>Growth Potential:</strong> {growth_potential}</p>
                <a href="{url}" target="_blank" style='color:#6366f1;text-decoration:none;'>View on DexScreener ↗</a>
                <a href="{explorer_url}" target="_blank" style='color:#6366f1;text-decoration:none;margin-left:1rem;'>Explorer ↗</a>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.checkbox("Expand", key=card_key, value=expanded):
            st.session_state.expanded_cards[card_key] = True
            connected_wallet = get_connected_wallet(st.session_state, chain.lower())

            if connected_wallet and connected_wallet.address:
                selected_token = st.selectbox("Select Token to Swap", list(ERC20_TOKENS.keys()), key=f"token_{card_key}")
                amount = st.number_input("Amount", min_value=0.0, step=0.1, key=f"amount_{card_key}")
                if st.button("Swap Now", key=f"swap_{card_key}"):
                    try:
                        chain_id = CHAIN_IDS.get(chain.lower(), 1)
                        token_address = ERC20_TOKENS.get(selected_token, {}).get(chain.lower(), "0x0")
                        router_address = CONTRACT_MAP.get('uniswap', {}).get(chain.lower(), "0x0")
                        if not router_address or not token_address:
                            st.error("Invalid router or token address")
                            continue

                        # Approve first
                        approve_tx = build_erc20_approve_tx_data(
                            chain.lower(),
                            token_address,
                            router_address,
                            amount,
                            str(connected_wallet.address)  # enforce str
                        )
                        approve_tx['chainId'] = chain_id
                        st.markdown(f"<script>performDeFiAction('approve',{json.dumps(approve_tx)});</script>", unsafe_allow_html=True)
                        time.sleep(1)
                        approve_resp = get_post_message()
                        if approve_resp.get("type") == "streamlit:txSuccess" and isinstance(approve_resp.get("txHash"), str) and approve_resp.get("txHash"):
                            st.success("Approve confirmed!")
                        else:
                            st.error("Approve failed")
                            continue

                        # Build swap tx data
                        swap_data = build_uniswap_swap_tx_data(
                            chain=chain.lower(),
                            token_in=token_address,
                            token_out=contract_address,
                            amount_in=amount,
                            amount_out_min=0,  # TODO: add slippage later
                            wallet_address=str(connected_wallet.address)
                        )

                        swap_tx = {
                            "from": str(connected_wallet.address),
                            "to": router_address,
                            "data": swap_data,
                            "value": 0,
                            "chainId": chain_id
                        }

                        st.markdown(f"<script>performDeFiAction('swap',{json.dumps(swap_tx)});</script>", unsafe_allow_html=True)
                        time.sleep(1)
                        swap_resp = get_post_message()
                        if swap_resp.get("type") == "streamlit:txSuccess" and isinstance(swap_resp.get("txHash"), str) and swap_resp.get("txHash"):
                            if confirm_tx(chain.lower(), swap_resp['txHash']):
                                position = create_position(chain.lower(), symbol, selected_token, amount, swap_resp['txHash'])
                                add_position_to_session(st.session_state, position)
                                st.success(f"Swapped {amount} {selected_token} for {symbol}!")
                            else:
                                st.error("Swap failed")
                        else:
                            st.error("Swap failed")
                    except Exception as e:
                        st.error(f"Swap error: {e}")
                    st.rerun()
            else:
                st.warning("Connect wallet to swap.")
        else:
            st.session_state.expanded_cards[card_key] = False

    st.markdown("</div>", unsafe_allow_html=True)

# --- Main Render Function ---
def render():
    st.title("🐸 Meme Coins")
    st.write("Trending meme coins and speculative plays.")

    # Initialize wallets
    if 'wallets' not in st.session_state:
        init_wallets(st.session_state)

    # Fetch meme coins from DB
    @st.cache_data(ttl=300)
    def cached_get_meme_coins():
        return db.get_meme_opportunities(limit=100)

    with st.spinner("🔍 Scanning for trending meme coins..."):
        meme_coins = cached_get_meme_coins()
        if not meme_coins:
            st.error("No meme coins found. Please check the database or run `python defi_scanner.py`.")
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
