import streamlit as st
import time
import json
import logging
from wallet_utils import init_wallets
from utils import safe_get, format_number
from streamlit_javascript import st_javascript

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Post message helper for JS interactions ---
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
    current_page = st.number_input(f"{category_name} Page", min_value=1, max_value=total_pages, value=1, key=f"page_{category_name}")
    start_idx = (current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_opps = opps_list[start_idx:end_idx]

    st.markdown("<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem;'>", unsafe_allow_html=True)
    for i, opp in enumerate(paginated_opps):
        pool_id = safe_get(opp, "pool_id", f"unknown_{i}")
        card_key = f"{category_name}_{pool_id}"
        expanded = st.session_state.expanded_cards.get(card_key, False)

        project = safe_get(opp, "project", safe_get(opp, "symbol", "Unknown"))
        chain = safe_get(opp, "chain", "Unknown").capitalize()
        symbol = safe_get(opp, "symbol", "Unknown")
        apy_str = safe_get(opp, "apy_str", "0%")
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
    st.title("🤖 ML Enhanced Scan")
    st.write("Top DeFi opportunities ranked by ML-predicted rewards and risk-adjusted scoring.")

    # Initialize wallets
    if 'wallets' not in st.session_state:
        init_wallets(st.session_state)

    # Load enhanced scan results
    try:
        with open("defi_scan_results_enhanced.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        st.warning("Enhanced scan not found. Run the scanner first.")
        return

    yields = data.get("yields", [])
    memes = data.get("memes", [])

    st.subheader("🏆 Top 10 Yield Opportunities")
    render_grid_cards(yields, "yields")

    st.subheader("🐸 Top 10 Meme Coin Opportunities")
    render_grid_cards(memes, "memes")

    # Summary statistics
    if yields and memes:
        avg_yield_score = sum([safe_get(y, "final_score", 0) for y in yields]) / len(yields)
        avg_meme_score = sum([safe_get(m, "final_score", 0) for m in memes]) / len(memes)
        st.markdown(f"**Average Risk-Adjusted Yield Score:** {avg_yield_score:.2f}")
        st.markdown(f"**Average Risk-Adjusted Meme Growth Score:** {avg_meme_score:.2f}")

if __name__ == "__main__":
    render()
