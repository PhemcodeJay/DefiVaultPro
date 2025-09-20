import streamlit as st
import streamlit.components.v1 as components
import os
import logging
import importlib
import subprocess
import sys
import atexit
import signal

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
    st.error(f"Failed to start DeFi scanner: {str(e)}")

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
    Powered by **MetaMask & Web3** for secure, fast interactions.
    """,
    unsafe_allow_html=True
)

# --- Custom CSS Theme ---
st.markdown(
    """
    <style>
        /* Global font */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* Backgrounds */
        .main {
            background-color: #383c44ff;
        }

        /* Card styling */
        .card {
            background: linear-gradient(145deg, #383c44ff, #2f3239);
            border-radius: 16px;
            padding: 1.2rem;
            margin-bottom: 1rem;
            box-shadow: 0 6px 12px rgba(0,0,0,0.3);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .card:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.5);
        }

        /* Buttons */
        .stButton>button {
            background: #595bf5ff;
            color: #ffffff;
            border-radius: 12px;
            border: none;
            padding: 0.6rem 1.2rem;
            font-weight: 600;
            transition: background 0.3s ease, transform 0.2s ease;
        }
        .stButton>button:hover {
            background: #4346d6;
            transform: translateY(-2px);
        }

        /* Inputs */
        .stNumberInput input, .stTextInput input, .stSelectbox select {
            background-color: #2d3037;
            color: #e2e8f0;
            border-radius: 8px;
            border: 1px solid #595bf5ff;
        }

        /* Headings */
        h1, h2, h3, h4 {
            color: #e2e8f0;
            font-weight: 700;
        }

        /* Links */
        a {
            color: #9da6ff;
            text-decoration: none;
        }
        a:hover {
            color: #ffffff;
        }

        /* Success / Error messages */
        .stAlert>div {
            border-radius: 12px;
        }
    </style>
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
    st.session_state.selected_page = "Dashboard"

# --- Sidebar Navigation ---
PAGE_MODULES = {
    "🌟 Dashboard": "views.dashboard"
}

st.sidebar.markdown("<h3 style='color:#6366f1;'>Navigation</h3>", unsafe_allow_html=True)
for page_name in PAGE_MODULES.keys():
    if st.sidebar.button(page_name, key=page_name):
        st.session_state.selected_page = page_name
        st.rerun()

# --- Load the selected page ---
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

        render_func()

    except ImportError as e:
        logger.error(f"Failed to load page: {selected_page}. Error: {str(e)}")
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