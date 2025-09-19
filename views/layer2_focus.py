import streamlit as st
import time
import json
import logging
from wallet_utils import (
    init_wallets, get_connected_wallet, add_position_to_session,
    create_position, build_erc20_approve_tx_data, build_aave_supply_tx_data,
    build_compound_supply_tx_data, confirm_tx,
)
from config import NETWORK_LOGOS, NETWORK_NAMES, PROTOCOL_LOGOS, BALANCE_SYMBOLS, CHAIN_IDS, CONTRACT_MAP, ERC20_TOKENS, explorer_urls
from utils import get_layer2_opportunities
from streamlit_javascript import st_javascript

# --- Logging ---
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
    except:
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
    current_page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key="page_layer2")
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
        pool_id = safe_get(opp, "pool_id", f"unknown_{i}")
        card_key = f"{category_name}_{pool_id}"
        expanded = st.session_state.expanded_cards.get(card_key, False)

        chain = safe_get(opp, "chain", "unknown").capitalize()
        project = safe_get(opp, "project", safe_get(opp, "symbol", "Unknown"))
        symbol = safe_get(opp, "symbol", "Unknown")
        apy_str = safe_get(opp, "apy_str", "0%")
        tvl_str = format_number(safe_get(opp, "tvl", 0))
        risk = safe_get(opp, "risk", "Unknown")
        type_ = safe_get(opp, "type", "Unknown")
        contract_address = safe_get(opp, "contract_address", "0x0")
        gas_fee_str = safe_get(opp, "gas_fee_str", "$0.00")
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
                        <h3 style='margin:0;font-size:1rem;font-weight:600;color:#c7d2fe;'>{project}</h3>
                    </div>
                    <img src="{protocol_logo}" alt="{project}" style="width:24px;height:24px;border-radius:50%;">
                </div>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    Chain: {chain} | Symbol: {symbol}
                </p>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    Type: {type_}
                </p>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    APY: <span class="text-green-400">{apy_str}</span> | TVL: {tvl_str}
                </p>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    Risk: <span class="{'text-green-400' if risk=='Low' else 'text-yellow-400' if risk=='Medium' else 'text-red-400'}">{risk}</span>
                </p>
                <p style='color:#e0e7ff;font-size:0.9rem;margin-bottom:0.25rem;'>
                    Gas Fee: {gas_fee_str}
                </p>
                <a href="{link}" target="_blank" style='color:#6366f1;text-decoration:none;font-size:0.9rem;'>
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
                    st.info(f"Connect wallet for {chain} to invest.")
                else:
                    available_tokens = list(ERC20_TOKENS.get(chain.lower(), {}).keys())
                    selected_token = st.selectbox("Select Token to Invest", available_tokens, key=f"token_{card_key}")
                    amount = st.number_input("Amount to Invest", min_value=0.0, step=0.1, key=f"amount_{card_key}")
                    if st.button("Invest", key=f"invest_{card_key}"):
                        try:
                            protocol = project.lower()
                            token_address = ERC20_TOKENS[chain.lower()].get(selected_token)
                            pool_address = CONTRACT_MAP.get(protocol, {}).get(chain.lower())
                            chain_id = CHAIN_IDS.get(chain.lower(), 0)
                            if not pool_address or not token_address:
                                st.error("Invalid pool or token address")
                                continue

                            approve_tx = build_erc20_approve_tx_data(chain.lower(), token_address, pool_address, amount, connected_wallet.address) # type: ignore
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
                                supply_tx = build_aave_supply_tx_data(chain.lower(), pool_address, token_address, amount, connected_wallet.address) # type: ignore
                            elif 'compound' in protocol:
                                supply_tx = build_compound_supply_tx_data(chain.lower(), pool_address, token_address, amount, connected_wallet.address) # type: ignore
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

    st.markdown("</div>", unsafe_allow_html=True)

# --- Main Render Function ---
def render():
    st.title("🚀 Layer 2 Focus")
    st.write("Explore efficient DeFi opportunities on Layer 2 networks.")

    # Initialize wallets
    if 'wallets' not in st.session_state:
        init_wallets(st.session_state)

    # Chain Selection
    SUPPORTED_CHAINS = ["ethereum", "bsc", "solana", "arbitrum", "optimism", "base", "avalanche", "neon"]
    LAYER2_CHAINS = ["arbitrum", "optimism", "base"]
    selected_chains = st.multiselect(
        "Select Chains",
        SUPPORTED_CHAINS,
        default=LAYER2_CHAINS,
        format_func=lambda x: f"⚡ {x.capitalize()}" if x in LAYER2_CHAINS else x.capitalize()
    )

    # Fetch Layer2 Opportunities
    @st.cache_data(ttl=300)
    def cached_layer2_opps():
        return get_layer2_opportunities()

    st.subheader("🚀 Layer 2 Opportunities")
    with st.spinner("🔍 Scanning for Layer 2 opportunities..."):
        layer2_opps = cached_layer2_opps()
        layer2_opps = [o for o in layer2_opps if safe_get(o, "chain", "unknown").lower() in selected_chains]
        if not layer2_opps:
            st.error("No opportunities found. Please check the database or run `python defi_scanner.py`.")
        else:
            render_grid_cards(layer2_opps, "layer2_focus")

if __name__ == "__main__":
    render()