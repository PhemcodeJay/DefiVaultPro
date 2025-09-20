import streamlit as st
import time
import json
import logging
from wallet_utils import (
    init_wallets, get_connected_wallet, add_position_to_session,
    create_position, build_erc20_approve_tx_data, build_aave_supply_tx_data,
    build_compound_supply_tx_data, confirm_tx
)
from config import NETWORK_LOGOS, PROTOCOL_LOGOS, CHAIN_IDS, CONTRACT_MAP, ERC20_TOKENS, explorer_urls
from streamlit_javascript import st_javascript
import db

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    filename="logs/long_term.log",
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
def render_grid_cards(opps_list, category_name: str):
    if "expanded_cards" not in st.session_state:
        st.session_state.expanded_cards = {}

    if not opps_list:
        st.warning(f"No {category_name} opportunities found.")
        return

    # Pagination
    items_per_page = 10
    total_pages = (len(opps_list) + items_per_page - 1) // items_per_page
    current_page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key="page_long_term")
    start_idx = (current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_opps = opps_list[start_idx:end_idx]

    st.markdown(
        """
        <style>
            .card { background: #1e1e2f; border-radius: 12px; padding: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            .text-green-400 { color: #10B981; }
            .text-yellow-400 { color: #F59E0B; }
            .text-red-400 { color: #EF4444; }
        </style>
        <div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem;'>
        """,
        unsafe_allow_html=True,
    )

    for i, opp in enumerate(paginated_opps):
        pool_id = safe_get(opp, "id", f"unknown_{i}")
        card_key = f"{category_name}_{pool_id}"
        expanded = st.session_state.expanded_cards.get(card_key, False)

        chain = safe_get(opp, "chain", "unknown").capitalize()
        project = safe_get(opp, "project", "Unknown")
        symbol = safe_get(opp, "symbol", "Unknown")
        apy = safe_get(opp, "apy", 0.0)
        apy_str = f"{apy:.2f}%" if apy else "0%"
        tvl_str = format_number(safe_get(opp, "tvl", 0))
        risk = safe_get(opp, "risk", "Unknown")
        type_ = safe_get(opp, "type", "Unknown")
        contract_address = safe_get(opp, "contract_address", "0x0")
        link = safe_get(opp, "link", "#")

        logo_url = NETWORK_LOGOS.get(chain.lower(), "https://via.placeholder.com/32?text=Logo")
        protocol_logo = PROTOCOL_LOGOS.get(project.lower(), "https://via.placeholder.com/32?text=Protocol")
        explorer_url = explorer_urls.get(chain.lower(), "#") + contract_address

        st.markdown(
            f"""
            <div class="card" onclick="document.getElementById('{card_key}').click()">
                <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;'>
                    <div style='display:flex;align-items:center;'>
                        <img src="{logo_url}" alt="{chain}" style="width:24px;height:24px;border-radius:50%;margin-right:0.5rem;">
                        <h3 style='margin:0;font-size:1.1rem;'>{project}</h3>
                    </div>
                    <img src="{protocol_logo}" alt="{project}" style="width:24px;height:24px;border-radius:50%;">
                </div>
                <p style='margin:0.2rem 0;'><strong>Chain:</strong> {chain} | <strong>Symbol:</strong> {symbol}</p>
                <p style='margin:0.2rem 0;'><strong>APY:</strong> <span class="text-green-400">{apy_str}</span></p>
                <p style='margin:0.2rem 0;'><strong>TVL:</strong> {tvl_str}</p>
                <p style='margin:0.2rem 0;'><strong>Risk:</strong> {risk}</p>
                <a href="{link}" target="_blank" style='color:#6366f1;text-decoration:none;'>View on DeFiLlama ↗</a>
                <a href="{explorer_url}" target="_blank" style='color:#6366f1;text-decoration:none;margin-left:1rem;'>Explorer ↗</a>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.checkbox("Expand", key=card_key, value=expanded):
            st.session_state.expanded_cards[card_key] = True
            connected_wallet = get_connected_wallet(st.session_state)
            if connected_wallet:
                selected_token = st.selectbox("Select Token", list(ERC20_TOKENS.keys()), key=f"token_{card_key}")
                amount = st.number_input("Amount", min_value=0.0, step=0.1, key=f"amount_{card_key}")
                if st.button("Invest Now", key=f"invest_{card_key}"):
                    try:
                        protocol = project.lower()
                        chain_id = CHAIN_IDS.get(chain.lower(), 1)
                        pool_address = CONTRACT_MAP.get(protocol, {}).get(chain.lower(), "0x0")
                        token_address = ERC20_TOKENS.get(selected_token, {}).get(chain.lower(), "0x0")
                        if not pool_address or not token_address:
                            st.error("Invalid pool or token address")
                            continue

                        approve_tx = build_erc20_approve_tx_data(chain.lower(), token_address, pool_address, amount, connected_wallet.address)
                        approve_tx['chainId'] = chain_id
                        st.markdown(f"<script>performDeFiAction('approve',{json.dumps(approve_tx)});</script>", unsafe_allow_html=True)
                        time.sleep(1)
                        approve_resp = get_post_message()
                        if approve_resp.get("type") == "streamlit:txSuccess" and isinstance(approve_resp.get("txHash"), str) and approve_resp.get("txHash"):
                            st.success("Approve confirmed!")
                        else:
                            st.error("Approve failed")
                            continue

                        if 'aave' in protocol:
                            supply_tx = build_aave_supply_tx_data(chain.lower(), pool_address, token_address, amount, connected_wallet.address)
                        elif 'compound' in protocol:
                            supply_tx = build_compound_supply_tx_data(chain.lower(), pool_address, token_address, amount, connected_wallet.address)
                        else:
                            st.error(f"Unsupported protocol: {protocol}")
                            continue

                        supply_tx['chainId'] = chain_id
                        st.markdown(f"<script>performDeFiAction('supply',{json.dumps(supply_tx)});</script>", unsafe_allow_html=True)
                        time.sleep(1)
                        response = get_post_message()
                        if response.get("type") == "streamlit:txSuccess" and isinstance(response.get("txHash"), str) and response.get("txHash"):
                            if confirm_tx(chain.lower(), response['txHash']):
                                position = create_position(chain.lower(), project, selected_token, amount, response['txHash'])
                                add_position_to_session(st.session_state, position)
                                st.success(f"Invested {amount} {selected_token} in {project}!")
                            else:
                                st.error("Supply transaction failed")
                        else:
                            st.error("Supply transaction failed")
                    except Exception as e:
                        st.error(f"Investment failed: {str(e)}")
                    st.rerun()
            else:
                st.warning("Connect wallet to invest.")
        else:
            st.session_state.expanded_cards[card_key] = False

    st.markdown("</div>", unsafe_allow_html=True)

# --- Main Render Function ---
def render():
    st.title("🏛 Long-Term Opportunities")
    st.write("Stable DeFi opportunities for long-term investment.")

    # Initialize wallets
    if 'wallets' not in st.session_state:
        init_wallets(st.session_state)

    # Fetch long-term opportunities from DB (e.g., low risk, high TVL filter)
    @st.cache_data(ttl=300)
    def cached_long_term():
        # Assuming db.get_opportunities returns all; filter for low risk or high TVL for long-term
        all_opps = db.get_opportunities(limit=100)
        return [opp for opp in all_opps if opp.get('risk', 'Unknown') == 'Low' or opp.get('tvl', 0) > 1_000_000]  # Example filter for long-term

    with st.spinner("🔍 Scanning for long-term DeFi opportunities..."):
        long_term_opps = cached_long_term()
        if not long_term_opps:
            st.error("No long-term opportunities found. Please check the database or run `python defi_scanner.py`.")
        else:
            render_grid_cards(long_term_opps, "long_term")

    # Additional Info
    st.markdown(
        """
        <div class="card bg-gradient-to-br from-green-900/30 to-teal-900/30 p-4 mt-4 rounded-lg shadow-md">
            <h3 class="text-lg font-semibold text-green-400 mb-2">💡 Selection Criteria</h3>
            <p class="text-indigo-200 text-sm">
                Long-term opportunities are selected for their stability, low risk, and high liquidity (TVL). 
                Ideal for consistent returns over extended periods.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    render()