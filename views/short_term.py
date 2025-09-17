import streamlit as st
import asyncio
import time
import json
import logging
from defi_scanner import YieldEntry, get_short_term_opportunities
from wallet_utils import (
    init_wallets, get_connected_wallet, add_position_to_session,
    create_position, NETWORK_LOGOS, BALANCE_SYMBOLS, ERC20_TOKENS,
    ERC20_ABI, CHAIN_IDS, CONTRACT_MAP, PROTOCOL_LOGOS, explorer_urls,
    connect_to_chain, build_approve_tx_data, build_aave_supply_tx_data,
    build_compound_supply_tx_data, confirm_tx
)
from streamlit_javascript import st_javascript

logger = logging.getLogger(__name__)

# ---------------------- UTILITY FUNCTIONS ---------------------- #
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

# ---------------------- GRID CARDS ---------------------- #
def render_grid_cards(opps_list, category_name: str):
    if "expanded_cards" not in st.session_state:
        st.session_state.expanded_cards = {}

    if not opps_list:
        st.warning(f"No {category_name} opportunities found.")
        return

    st.markdown("<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem;'>", unsafe_allow_html=True)

    for i, opp in enumerate(opps_list):
        pool_id = safe_get(opp, "pool_id", f"unknown_{i}")
        card_key = f"{category_name}_{pool_id}"
        expanded = st.session_state.expanded_cards.get(card_key, False)

        chain = safe_get(opp, "chain", "Unknown").capitalize()
        project = safe_get(opp, "project", "Unknown")
        symbol = safe_get(opp, "symbol", "Unknown")
        apy_str = safe_get(opp, "apy_str", "0%")
        tvl_str = format_number(safe_get(opp, "tvl", 0))
        risk = safe_get(opp, "risk", "Unknown")
        type_ = safe_get(opp, "type", "Unknown")
        contract_address = safe_get(opp, "contract_address", "0x0")
        link = safe_get(opp, "link", "#")

        logo_url = NETWORK_LOGOS.get(chain.lower(), "https://via.placeholder.com/12")
        protocol_logo = PROTOCOL_LOGOS.get(project.lower(), "https://via.placeholder.com/12")
        explorer_url = explorer_urls.get(chain.lower(), "#") + contract_address

        st.markdown(f"""
            <div style='padding:1rem;background:#1e1e2f;border-radius:12px;cursor:pointer;' onclick="document.getElementById('{card_key}').click()">
                <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;'>
                    <div style='display:flex;align-items:center;'>
                        <img src="{protocol_logo}" width="16" height="16" style="margin-right:0.5rem;">
                        <b style='color:#dbeafe'>{symbol}</b>
                    </div>
                    <span style='color:#fff'>{risk}</span>
                </div>
                <div style='display:flex;align-items:center;margin-bottom:0.5rem;'>
                    <img src="{logo_url}" width="12" height="12" style="margin-right:0.25rem;">
                    <span style='color:#aaa;font-size:12px'>{chain}</span>
                </div>
                <div style='display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;font-size:12px;'>
                    <div>APY: <b>{apy_str}</b></div>
                    <div>TVL: <b>{tvl_str}</b></div>
                    <div>Type: <b>{type_}</b></div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Expand details
        expanded = st.checkbox("Expand", value=expanded, key=f"{card_key}_checkbox", label_visibility="collapsed")
        st.session_state.expanded_cards[card_key] = expanded

        if expanded:
            with st.expander("", expanded=True):
                st.markdown(f"""
                    <div style='padding:0.5rem;background:#111; border-radius:8px;color:#ccc;font-size:12px;'>
                        Protocol: {project}<br>
                        Contract: <a href="{explorer_url}" target="_blank">{contract_address[:6]}...{contract_address[-4:]}</a><br>
                        Details: <a href="{link}" target="_blank">View on Protocol</a>
                    </div>
                """, unsafe_allow_html=True)

                # --- MetaMask Investment ---
                connected_wallet = get_connected_wallet(st.session_state, chain.lower())
                if connected_wallet and connected_wallet.verified and connected_wallet.address:
                    token_options = list(ERC20_TOKENS.get(chain.lower(), {}).keys()) + [BALANCE_SYMBOLS.get(chain.lower(), "Native")]
                    selected_token = st.selectbox("Select Token", token_options, key=f"token_{i}")
                    token_address = ERC20_TOKENS.get(chain.lower(), {}).get(selected_token, "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
                    amount = st.number_input("Amount to Invest", min_value=0.0, value=1.0, step=0.01, key=f"amount_{i}")
                    pool_address = CONTRACT_MAP.get(project.lower(), {}).get(chain.lower(), "")
                    chain_id = CHAIN_IDS.get(chain.lower(), 0)

                    if amount > 0 and st.button("💸 Invest with MetaMask", key=f"invest_{i}"):
                        try:
                            protocol = project.lower()
                            # Approve
                            approve_tx = build_approve_tx_data(chain.lower(), token_address, pool_address, amount, connected_wallet.address)
                            approve_tx['chainId'] = chain_id
                            st.markdown(f"<script>performDeFiAction('approve',{json.dumps(approve_tx)});</script>", unsafe_allow_html=True)
                            time.sleep(1)
                            response = get_post_message()
                            if response.get("type") == "streamlit:txSuccess" and confirm_tx(chain.lower(), response['txHash']):
                                st.success("Approve transaction confirmed!")
                            else:
                                st.error("Approve transaction failed")
                                continue

                            # Supply
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
                            if response.get("type") == "streamlit:txSuccess" and confirm_tx(chain.lower(), response['txHash']):
                                position = create_position(chain.lower(), project, selected_token, amount, response['txHash'])
                                add_position_to_session(st.session_state, position)
                                st.success(f"Invested {amount} {selected_token} in {project}!")
                            else:
                                st.error("Supply transaction failed")
                        except Exception as e:
                            st.error(f"Investment failed: {str(e)}")
                        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------- MAIN PAGE ---------------------- #
def render():
    st.title("⚡ Short-Term Opportunities")
    st.write("High-yield DeFi opportunities for short-term gains.")

    # Initialize wallets if not already in session state
    if "wallets" not in st.session_state:
        init_wallets(st.session_state)

    if not short_term_opps:
        st.warning("No short-term opportunities found.")
    else:
        render_grid_cards(short_term_opps, "short_term")


# Fetch + cache
@st.cache_data(ttl=300)
def cached_short_term():
    return asyncio.run(get_short_term_opportunities())

short_term_opps = cached_short_term()

with st.spinner("🔍 Scanning for short-term DeFi opportunities..."):
    if not short_term_opps:
        st.error("No opportunities found. Please check the database or run `python defi_scanner.py`.")
    else:
        render_grid_cards(short_term_opps, "short_term")

# Risk warning
st.markdown("""
<div class="card bg-gradient-to-br from-red-900/30 to-orange-900/30 p-4 mt-4 rounded-lg shadow-md">
    <h3 class="text-lg font-semibold text-red-400 mb-2">⚠️ Risk Warning</h3>
    <p class="text-indigo-200 text-sm">
        Short-term opportunities often come with higher risk due to their high APY. 
        Ensure you understand the risks and conduct thorough research before investing.
    </p>
</div>
""", unsafe_allow_html=True)

if __name__ == "__main__":
    render()