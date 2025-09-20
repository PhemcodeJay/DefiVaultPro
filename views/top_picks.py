import streamlit as st
import time
import json
import logging
import subprocess
import db
from wallet_utils import (
    init_wallets, get_connected_wallet, add_position_to_session,
    create_position, build_erc20_approve_tx_data, build_aave_supply_tx_data,
    build_compound_supply_tx_data, confirm_tx
)
from config import NETWORK_LOGOS, PROTOCOL_LOGOS, CHAIN_IDS, CONTRACT_MAP, ERC20_TOKENS, explorer_urls
from streamlit_javascript import st_javascript

import wallet_utils

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    filename="logs/top_picks.log",
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

# --- Render Grid Cards (Top Picks) ---
def render_grid_cards(opps_list, category_name: str):
    if "expanded_cards" not in st.session_state:
        st.session_state.expanded_cards = {}

    if not opps_list:
        st.warning(f"No {category_name} opportunities found.")
        return

    items_per_page = 10
    total_pages = (len(opps_list) + items_per_page - 1) // items_per_page
    current_page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key=f"page_{category_name}")
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

                        # Fixed: Ensure correct parameters for build_erc20_approve_tx_data
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
                        logger.error(f"Investment failed for {project}: {e}")
                        st.error(f"Investment failed: {str(e)}")
                    st.rerun()
            else:
                st.warning("Connect wallet to invest.")
        else:
            st.session_state.expanded_cards[card_key] = False

    st.markdown("</div>", unsafe_allow_html=True)

# --- Render ML Grid Cards ---
def render_ml_grid_cards(opps_list, category_name: str):
    if not opps_list:
        st.warning(f"No {category_name} opportunities found.")
        return

    items_per_page = 10
    total_pages = (len(opps_list) + items_per_page - 1) // items_per_page
    current_page = st.number_input(f"{category_name} Page", min_value=1, max_value=total_pages, value=1, key=f"ml_page_{category_name}")
    start_idx = (current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_opps = opps_list[start_idx:end_idx]

    st.markdown("<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem;'>", unsafe_allow_html=True)
    for i, opp in enumerate(paginated_opps):
        pool_id = safe_get(opp, "pool_id", f"unknown_{i}")
        card_key = f"{category_name}_{pool_id}"

        project = safe_get(opp, "project", safe_get(opp, "symbol", "Unknown"))
        chain = safe_get(opp, "chain", "Unknown").capitalize()
        symbol = safe_get(opp, "symbol", "Unknown")
        apy = safe_get(opp, "apy", 0.0)
        apy_str = f"{apy:.2f}%" if apy else "0%"
        tvl_str = format_number(safe_get(opp, "tvl", 0))
        risk = safe_get(opp, "risk", "Unknown")
        final_score = safe_get(opp, "final_score", 0)
        predicted = safe_get(opp, "predicted_ror", safe_get(opp, "predicted_growth", 0))
        type_ = safe_get(opp, "type", "Unknown")
        link = safe_get(opp, "link", "#")

        st.markdown(
            f"""
            <div style='background:#1e1e2f;padding:1rem;border-radius:12px;box-shadow:0 4px 6px rgba(0,0,0,0.1);'>
                <h3 style='color:#c7d2fe;'>{project}</h3>
                <p style='color:#e0e7ff;'>Chain: {chain} | Symbol: {symbol}</p>
                <p style='color:#e0e7ff;'>Type: {type_}</p>
                <p style='color:#e0e7ff;'>APY: {apy_str} | TVL: {tvl_str}</p>
                <p style='color:#e0e7ff;'>Risk: {risk} | Predicted: {predicted:.2f} | Score: {final_score:.2f}</p>
                <a href="{link}" target="_blank" style='color:#6366f1;text-decoration:none;'>View Opportunity ↗</a>
            </div>
            """,
            unsafe_allow_html=True
        )
    st.markdown("</div>", unsafe_allow_html=True)

# --- Main Render Function ---
def render():
    st.title("🏆 Top Picks & ML Analysis")
    st.write("Curated DeFi opportunities with balanced risk and reward, enhanced by ML insights.")

    # Initialize wallets
    if 'wallets' not in st.session_state:
        init_wallets(st.session_state)

    # Tabs for Top Picks and ML Analysis
    tab1, tab2 = st.tabs(["🏆 Top Picks", "🤖 ML Analysis"])

    with tab1:
        # Fetch top picks from DB
        @st.cache_data(ttl=300)
        def cached_top_picks():
            return db.get_opportunities(limit=100)

        with st.spinner("🔍 Scanning for top DeFi opportunities..."):
            top_picks = cached_top_picks()
            if not top_picks:
                st.error("No opportunities found in DB. Ensure `defi_scanner.py` is running.")
            else:
                render_grid_cards(top_picks, "top_picks")

        st.markdown(
            """
            <div class="card bg-gradient-to-br from-blue-900/30 to-indigo-900/30 p-4 mt-4 rounded-lg shadow-md">
                <h3 class="text-lg font-semibold text-blue-400 mb-2">💡 Selection Criteria</h3>
                <p class="text-indigo-200 text-sm">
                    Top picks are curated based on high APY, moderate risk, and strong liquidity (TVL).
                    Ideal for balanced risk-reward opportunities.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tab2:
        if st.button("Run ML Analysis"):
            try:
                result = subprocess.run(["python", "ml.py"], capture_output=True, text=True)
                if result.returncode == 0:
                    st.success("ML Analysis completed! Refreshing...")
                    st.rerun()
                else:
                    st.error(f"ML Analysis failed: {result.stderr}")
            except Exception as e:
                logger.error(f"Failed to run ML analysis: {e}")
                st.error(f"Failed to run ML analysis: {e}")

        try:
            with open("defi_scan_results_enhanced.json", "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            st.warning("Enhanced scan not found. Run ML analysis first.")
            return

        yields = data.get("yields", [])
        memes = data.get("memes", [])

        st.subheader("🏆 Top 10 Yield Opportunities")
        render_ml_grid_cards(yields, "yields")

        st.subheader("🐸 Top 10 Meme Coin Opportunities")
        render_ml_grid_cards(memes, "memes")

        if yields and memes:
            avg_yield_score = sum([safe_get(y, "final_score", 0) for y in yields]) / len(yields)
            avg_meme_score = sum([safe_get(m, "final_score", 0) for m in memes]) / len(memes)
            st.markdown(f"**Average Risk-Adjusted Yield Score:** {avg_yield_score:.2f}")
            st.markdown(f"**Average Risk-Adjusted Meme Growth Score:** {avg_meme_score:.2f}")

if __name__ == "__main__":
    render()