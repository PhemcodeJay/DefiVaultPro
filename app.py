import streamlit as st
import streamlit.components.v1 as components
import os
from dotenv import load_dotenv
import db
import wallet_utils
import logging
import importlib
import asyncio
import inspect
import subprocess
import sys
import atexit
import signal  # Fixed: signal was missing

# --- Load Environment Variables ---
load_dotenv()

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    filename="logs/app.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

# --- Start defi_scanner.py at startup ---
try:
    p = subprocess.Popen([sys.executable, "defi_scanner.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    atexit.register(lambda: os.kill(p.pid, signal.SIGTERM) if p.poll() is None else None)
    logger.info("Started defi_scanner.py successfully.")
except Exception as e:
    logger.error(f"Failed to start defi_scanner.py: {e}")

# --- Initialize Database ---
if db.test_connection():
    logger.info("Database connection successful.")
    if db.init_database():
        st.success("Database initialized successfully.")
    else:
        st.warning("Database initialization failed or tables already exist.")
else:
    st.error("Database connection failed. Some features may not work.")

# --- Page Config ---
st.set_page_config(
    page_title="💰 DeFiVaultPro Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- App Header and Description ---
st.markdown(
    """
    # 💰 DeFiVaultPro Dashboard
    **Real-time multi-chain DeFi scanner**  
    Track top yield opportunities, meme coins, and your wallet positions.  
    Powered by MetaMask & Web3 for secure, fast interactions.
    """,
    unsafe_allow_html=True
)

# --- Hide default Streamlit menu/footer ---
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- Load ethers.js for real transactions ---
components.html("""<script src="https://cdn.ethers.io/lib/ethers-5.7.umd.min.js"></script>""", height=0)

# --- Custom CSS for Sidebar Buttons ---
st.markdown("""
<style>
.stButton > button {
    width: 100%;
    margin-bottom: 0.3rem;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    border: none;
    border-radius: 6px;
    padding: 0.5rem 1rem;
    font-size: 0.85rem;
    text-align: left;
    transition: all 0.3s ease;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}
</style>
""", unsafe_allow_html=True)

# --- Initialize Session State ---
if 'selected_page' not in st.session_state:
    st.session_state.selected_page = "🏆 Top Picks"
if 'wallets' not in st.session_state:
    wallet_utils.init_wallets(st.session_state)
if 'positions' not in st.session_state:
    st.session_state.positions = db.get_positions()

# --- Sidebar Navigation & Page Loader ---
PAGE_MODULES = {
    "🏆 Top Picks": "views.top_picks",
    "⚡ Short Term": "views.short_term",
    "🚀 Layer 2 Focus": "views.layer2_focus",
    "🏦 Long Term": "views.long_term",
    "🤖 ML Analysis": "views.ml_analysis", 
    "🐸 Meme Coins": "views.meme_coins",
    "📊 My Positions": "views.my_positions",
    "👛 Wallets": "views.wallets"
}

st.sidebar.markdown("<h3 style='color:#6366f1;'>Navigation</h3>", unsafe_allow_html=True)
for page_name in PAGE_MODULES.keys():
    if st.sidebar.button(page_name, key=page_name):
        st.session_state.selected_page = page_name
        st.rerun()  # Proper rerun for Streamlit

# --- Load the selected page with proper async handling ---
def load_page(selected_page: str):
    module_name = PAGE_MODULES.get(selected_page)
    if not module_name:
        st.warning(f"Unknown page: {selected_page}")
        return

    try:
        page_module = importlib.import_module(module_name)
        render_func = getattr(page_module, "render", None)

        if not callable(render_func):
            st.warning(f"Module {selected_page} loaded but no render() found.")
            return

        if inspect.iscoroutinefunction(render_func):
            # Run coroutine safely without blocking Streamlit
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(render_func())
                else:
                    asyncio.run(render_func())
            except RuntimeError as e:
                logger.error(f"Async execution error: {e}")
                st.error(f"Failed to load async page: {selected_page}")
        else:
            render_func()

    except ImportError as e:
        st.error(f"Failed to load page: {selected_page}. Error: {str(e)}")
    except Exception as e:
        logger.exception(f"Error rendering page {selected_page}: {e}")
        st.error(f"Error rendering page {selected_page}: {str(e)}")

# --- Load the currently selected page ---
load_page(st.session_state.selected_page)

# --- Sidebar Footer ---
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="text-align: center; color: #64748b; font-size: 0.8rem;">
    <p>🔒 Secure • 🌐 Multi-Chain • ⚡ Fast</p>
    <p>Powered by MetaMask & Web3 | Streamlit</p>
    <p>Developed by CyberTrendHub</p>
</div>
""", unsafe_allow_html=True)
