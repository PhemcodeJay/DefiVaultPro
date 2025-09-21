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
    filename="logs/short_term.log",
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

def format_number(value) -> str:
    try:
        value = float(value)
        if value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value / 1_000:.2f}K"
        return f"${value:,.2f}"
    except (ValueError, TypeError):
        return "$0.00"

def get_post_message():
    return st_javascript("return window.lastMessage || {}")

# --- Render Grid Cards ---
def render_grid_cards(opps_list, category_name: str):
    if "expanded_cards" not in st.session_state:
        st.session_state.expanded_cards = {}

    if not opps_list:
        st.warning(f"No {category_name} opportunities found.")
        return

    # Validate and clean opportunities
    cleaned_opps = []
    for opp in opps_list:
        try:
            chain = safe_get(opp, "chain", "unknown")
            project = safe_get(opp, "project", "Unknown")
            symbol = safe_get(opp, "symbol", "Unknown")
            risk = safe_get(opp, "risk", "Unknown")
            # Ensure string fields are strings
            if not all(isinstance(x, str) for x in [chain, project, symbol, risk]):
                logger.warning(f"Skipping opportunity with invalid string fields: {opp}")
                continue
            # Ensure numeric fields are valid
            apy = float(safe_get(opp, "apy", 0.0))
            tvl = float(safe_get(opp, "tvl", 0.0))
            if apy < 0 or tvl < 0:
                logger.warning(f"Skipping opportunity with negative apy/tvl: {opp}")
                continue

            cleaned_opps.append({
                "chain": chain.capitalize(),
                "project": project,
                "symbol": symbol,
                "apy": apy,
                "tvl": tvl,
                "risk": risk,
                "type": safe_get(opp, "type", "Unknown"),
                "contract_address": safe_get(opp, "contract_address", "0x0"),
                "link": safe_get(opp, "link", "#"),
                "pool_id": safe_get(opp, "pool_id", f"unknown_{len(cleaned_opps)}")
            })
        except Exception as e:
            logger.warning(f"Error processing opportunity {safe_get(opp, 'project', 'unknown')}: {e}")
            continue

    if not cleaned_opps:
        st.warning(f"No valid {category_name} opportunities found after validation.")
        return

    # Pagination
    items_per_page = 10
    total_pages = (len(cleaned_opps) + items_per_page - 1) // items_per_page
    current_page = st.number_input("Page", min_value=1, max_value=max(1, total_pages), value=1, key="page_short_term")
    start_idx = (current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_opps = cleaned_opps[start_idx:end_idx]

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
        pool_id = opp["pool_id"]
        card_key = f"{category_name}_{pool_id}"
        expanded = st.session_state.expanded_cards.get(card_key, False)

        chain = opp["chain"]
        project = opp["project"]
        symbol = opp["symbol"]
        apy = opp["apy"]
        apy_str = f"{apy:.2f}%"
        tvl_str = format_number(opp["tvl"])
        risk = opp["risk"]
        type_ = opp["type"]
        contract_address = opp["contract_address"]
        link = opp["link"]

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
            connected_wallet = get_connected_wallet(st.session_state, chain=chain.lower())
            if connected_wallet and connected_wallet.address:
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

                        approve_tx = build_erc20_approve_tx_data(
                            chain.lower(), token_address, pool_address, amount, str(connected_wallet.address)
                        )
                        approve_tx['chainId'] = chain_id
                        st.markdown(
                            f"<script>performDeFiAction('approve',{json.dumps(approve_tx)});</script>",
                            unsafe_allow_html=True
                        )
                        time.sleep(1)
                        approve_resp = get_post_message()
                        if approve_resp.get("type") == "streamlit:txSuccess" and isinstance(approve_resp.get("txHash"), str) and approve_resp.get("txHash"):
                            st.success("Approve confirmed!")
                        else:
                            st.error("Approve failed")
                            continue

                        if 'aave' in protocol:
                            supply_tx = build_aave_supply_tx_data(chain.lower(), pool_address, token_address, amount, str(connected_wallet.address))
                        elif 'compound' in protocol:
                            supply_tx = build_compound_supply_tx_data(chain.lower(), pool_address, token_address, amount, str(connected_wallet.address))
                        else:
                            st.error(f"Unsupported protocol: {protocol}")
                            continue

                        supply_tx['chainId'] = chain_id
                        st.markdown(
                            f"<script>performDeFiAction('supply',{json.dumps(supply_tx)});</script>",
                            unsafe_allow_html=True
                        )
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
                        logger.error(f"Investment failed for {project}: {e}")
                        st.error(f"Investment failed: {str(e)}")
                    st.rerun()
            else:
                st.warning("Connect wallet to invest.")
        else:
            st.session_state.expanded_cards[card_key] = False

    st.markdown("</div>", unsafe_allow_html=True)

# --- Main Render Function ---
def render():
    st.title("⚡ Short-Term Opportunities")
    st.write("High-yield DeFi opportunities for short-term gains.")

    # Initialize wallets
    if 'wallets' not in st.session_state:
        init_wallets(st.session_state)

    # Fetch short-term opportunities from DB (high APY filter)
    @st.cache_data(ttl=300)
    def cached_short_term():
        all_opps = db.get_opportunities(limit=100)
        return [
            opp for opp in all_opps
            if float(safe_get(opp, 'apy', 0.0)) > 20
        ]

    with st.spinner("🔍 Scanning for short-term DeFi opportunities..."):
        short_term_opps = cached_short_term()
        if not short_term_opps:
            st.error("No short-term opportunities found. Please check the database or run `python defi_scanner.py`.")
        else:
            render_grid_cards(short_term_opps, "short_term")

    # Risk warning
    st.markdown(
        """
        <div class="card bg-gradient-to-br from-red-900/30 to-orange-900/30 p-4 mt-4 rounded-lg shadow-md">
            <h3 class="text-lg font-semibold text-red-400 mb-2">⚠️ Risk Warning</h3>
            <p class="text-indigo-200 text-sm">
                Short-term opportunities often come with higher risk due to their high APY. 
                Ensure you understand the risks and conduct thorough research before investing.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    render()