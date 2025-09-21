import os
import streamlit as st
from dotenv import load_dotenv
from streamlit_javascript import st_javascript
import db
from wallet_utils import (
    get_all_wallets,
    init_wallets,
    NETWORK_NAMES
)
from config import NETWORK_LOGOS, BALANCE_SYMBOLS
from web3 import Web3
from typing import Optional
import logging

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    filename="logs/wallets.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

# --- Load Environment Variables ---
load_dotenv()
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
WALLET_CONNECT_PROJECT_ID = os.getenv("WALLET_CONNECT_PROJECT_ID", "bbfc8335f232745db239ec392b6a9d4a")  # Fallback for testing

if not WALLET_ADDRESS:
    st.error("⚠️ No WALLET_ADDRESS found in .env file. Please add it.")
    st.stop()
else:
    try:
        WALLET_ADDRESS = Web3.to_checksum_address(WALLET_ADDRESS)
    except ValueError:
        logger.error(f"Invalid WALLET_ADDRESS in .env: {WALLET_ADDRESS}")
        st.error("⚠️ Invalid WALLET_ADDRESS in .env file. Please provide a valid Ethereum address.")
        st.stop()

if not WALLET_CONNECT_PROJECT_ID:
    st.warning("⚠️ No WALLET_CONNECT_PROJECT_ID found in .env file. Using default project ID.")

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

# --- Page Title / Header ---
def render():
    st.title("👛 Wallets")

    st.markdown(
        """
        <div class="text-center py-6">
            <h1 class="text-3xl font-bold mb-2 bg-clip-text text-transparent 
                bg-gradient-to-r from-indigo-400 to-blue-400">
                Connect Your Wallet
            </h1>
            <p class="text-sm text-gray-400">
                Your wallet address is loaded from <code>.env</code>. 
                MetaMask or WalletConnect can override this if connected.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Safe display of .env wallet address
    wallet_display = (
        f"{WALLET_ADDRESS[:6]}...{WALLET_ADDRESS[-4:]}"
        if isinstance(WALLET_ADDRESS, str) and len(WALLET_ADDRESS) >= 42
        else "Invalid address"
    )

    # Inject MetaMask and WalletConnect logic
    st.markdown(
        f"""
        <!-- WalletConnect Modal -->
        <script src="https://unpkg.com/@walletconnect/modal@2.6.2/dist/index.umd.js"></script>
        <script src="https://cdn.ethers.io/lib/ethers-5.7.umd.min.js"></script>

        <button id="connectButton"
            style="background: linear-gradient(to right, #6366f1, #3b82f6);
                   border:none; padding:12px 24px; border-radius:10px;
                   color:white; font-size:16px; cursor:pointer;">
            🔗 Connect Wallet
        </button>

        <p id="walletAddress" style="margin-top:10px; font-size:14px; color:#9ca3af;">
            Loaded from .env: {wallet_display}
        </p>

        <script>
        class MetaMaskConnector {{
            constructor() {{
                this.isConnected = false;
                this.account = null;
                this.chainId = null;
                this.networkMap = {{
                    '0x1': 'ethereum',
                    '0x38': 'bsc',
                    '0xa4b1': 'arbitrum',
                    '0xa': 'optimism',
                    '0x2105': 'base',
                    '0xa86a': 'avalanche',
                    '0xe9ac0ce': 'neon'
                }};
            }}

            async connect() {{
                if (typeof window.ethereum !== 'undefined') {{
                    try {{
                        const accounts = await window.ethereum.request({{ method: 'eth_requestAccounts' }});
                        this.account = accounts[0];
                        this.chainId = await window.ethereum.request({{ method: 'eth_chainId' }});
                        this.isConnected = true;
                        window.postMessage({{
                            type: 'streamlit:connectWallet',
                            address: this.account,
                            chain: this.networkMap[this.chainId] || 'unknown',
                            connector: 'MetaMask'
                        }}, '*');
                    }} catch (error) {{
                        console.error('MetaMask connection failed:', error);
                        window.postMessage({{
                            type: 'streamlit:connectError',
                            error: error.message
                        }}, '*');
                    }}
                }} else {{
                    window.postMessage({{
                        type: 'streamlit:connectError',
                        error: 'MetaMask not installed'
                    }}, '*');
                }}
            }}

            disconnect() {{
                this.isConnected = false;
                this.account = null;
                this.chainId = null;
                window.postMessage({{
                    type: 'streamlit:disconnectWallet',
                    connector: 'MetaMask'
                }}, '*');
            }}
        }}

        class WalletConnectConnector {{
            constructor(projectId) {{
                this.projectId = projectId;
                this.modal = null;
                this.provider = null;
                this.isConnected = false;
                this.account = null;
                this.chainId = null;
                this.networkMap = {{
                    '0x1': 'ethereum',
                    '0x38': 'bsc',
                    '0xa4b1': 'arbitrum',
                    '0xa': 'optimism',
                    '0x2105': 'base',
                    '0xa86a': 'avalanche',
                    '0xe9ac0ce': 'neon'
                }};
            }}

            async init() {{
                try {{
                    this.modal = new window.WalletConnectModal.default({{
                        projectId: this.projectId,
                        themeMode: 'dark'
                    }});
                }} catch (error) {{
                    console.error('Failed to initialize WalletConnect:', error);
                }}
            }}

            async connect() {{
                if (!this.modal) await this.init();
                try {{
                    const provider = new ethers.providers.Web3Provider(this.modal.provider || window.ethereum);
                    const accounts = await provider.listAccounts();
                    this.account = accounts[0] || (await provider.getSigner().getAddress());
                    this.chainId = (await provider.getNetwork()).chainId.toString();
                    this.isConnected = true;
                    window.postMessage({{
                        type: 'streamlit:connectWallet',
                        address: this.account,
                        chain: this.networkMap['0x' + parseInt(this.chainId).toString(16)] || 'unknown',
                        connector: 'WalletConnect'
                    }}, '*');
                }} catch (error) {{
                    console.error('WalletConnect connection failed:', error);
                    window.postMessage({{
                        type: 'streamlit:connectError',
                        error: error.message
                    }}, '*');
                }}
            }}

            disconnect() {{
                if (this.modal) this.modal.closeModal();
                this.isConnected = false;
                this.account = null;
                this.chainId = null;
                window.postMessage({{
                    type: 'streamlit:disconnectWallet',
                    connector: 'WalletConnect'
                }}, '*');
            }}
        }}

        const metaMask = new MetaMaskConnector();
        const walletConnect = new WalletConnectConnector('{WALLET_CONNECT_PROJECT_ID}');
        const connectButton = document.getElementById('connectButton');

        connectButton.addEventListener('click', async () => {{
            if (typeof window.ethereum !== 'undefined') {{
                await metaMask.connect();
            }} else {{
                await walletConnect.connect();
            }}
        }});

        window.addEventListener('message', (event) => {{
            window.lastMessage = event.data;
        }});
        </script>
        """,
        unsafe_allow_html=True
    )

    # Initialize wallets
    if 'wallets' not in st.session_state:
        init_wallets(st.session_state)

    # Process connection messages
    message = st_javascript("return window.lastMessage || {}")
    if message.get("type") == "streamlit:connectWallet":
        chain = safe_get(message, "chain", "unknown")
        address = safe_get(message, "address", None)
        connector = safe_get(message, "connector", "Unknown")
        try:
            if address and Web3.is_address(address):
                address = Web3.to_checksum_address(address)
                wallet = st.session_state.wallets.get(chain)
                if wallet:
                    wallet.connect(address)
                    st.success(f"Connected via {connector}: {address[:6]}...{address[-4:]}")
                    st.rerun()
                else:
                    logger.error(f"Invalid chain: {chain}")
                    st.error(f"Unsupported chain: {chain}")
            else:
                st.error("Invalid wallet address received.")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            st.error(f"Connection failed: {str(e)}")
    elif message.get("type") == "streamlit:connectError":
        st.error(f"Connection error: {safe_get(message, 'error', 'Unknown error')}")
    elif message.get("type") == "streamlit:disconnectWallet":
        connector = safe_get(message, "connector", "Unknown")
        st.info(f"Disconnected from {connector}")
        st.rerun()

    # Display wallets
    st.markdown(
        """
        <style>
            .card { background: #1e1e2f; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        </style>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        """,
        unsafe_allow_html=True
    )

    # Validate and clean wallets
    cleaned_wallets = []
    for wallet in st.session_state.wallets.values():
        try:
            chain = safe_get(wallet, "chain", "unknown")
            address = safe_get(wallet, "address", None)
            balance = float(safe_get(wallet, "balance", 0.0))
            connected = bool(safe_get(wallet, "connected", False))
            if not isinstance(chain, str):
                logger.warning(f"Skipping wallet with invalid chain: {wallet}")
                continue
            if balance < 0:
                logger.warning(f"Skipping wallet with negative balance: {wallet}")
                continue
            if address and not Web3.is_address(address):
                logger.warning(f"Skipping wallet with invalid address: {address}")
                continue
            cleaned_wallets.append({
                "chain": chain,
                "address": address,
                "balance": balance,
                "connected": connected,
                "wallet_obj": wallet
            })
        except Exception as e:
            logger.warning(f"Error processing wallet {safe_get(wallet, 'chain', 'unknown')}: {e}")
            continue

    if not cleaned_wallets:
        st.warning("No valid wallets found.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Separate active and disconnected wallets
    active_wallets = [w for w in cleaned_wallets if w["connected"]]
    disconnected_wallets = [w for w in cleaned_wallets if not w["connected"]]

    tab_active, tab_disconnected = st.tabs(["🟢 Active Wallets", "🔴 Disconnected Wallets"])

    with tab_active:
        if not active_wallets:
            st.info("No active wallets.")
        else:
            for wallet in active_wallets:
                chain = wallet["chain"]
                address = wallet["address"]
                balance = wallet["balance"]
                wallet_obj = wallet["wallet_obj"]

                logo_url = NETWORK_LOGOS.get(chain.lower(), "https://via.placeholder.com/32?text=Logo")
                chain_name = NETWORK_NAMES.get(chain.lower(), chain.capitalize())
                address_display = (address[:6] + "..." + address[-4:]) if address else "Not connected"
                balance_display = format_number(balance)
                connection_status = "MetaMask" if address == WALLET_ADDRESS else "WalletConnect"

                st.markdown(
                    f"""
                    <div class="card">
                        <div style="display:flex; align-items:center; margin-bottom:0.75rem;">
                            <img src="{logo_url}" alt="{chain_name}" style="width:32px; height:32px; border-radius:50%; margin-right:0.6rem;">
                            <h3 style="margin:0; font-size:1rem; font-weight:600; color:#c7d2fe;">
                                {chain_name}
                            </h3>
                        </div>
                        <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                            Status: ✅ Connected via {connection_status}
                        </p>
                        <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                            Address: {address_display}
                        </p>
                        <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                            Balance: {balance_display}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                if st.button("Disconnect", key=f"disconnect_active_{chain}"):
                    wallet_obj.disconnect()
                    st.rerun()

    with tab_disconnected:
        if not disconnected_wallets:
            st.info("No disconnected wallets.")
        else:
            for wallet in disconnected_wallets:
                chain = wallet["chain"]
                address = wallet["address"]
                wallet_obj = wallet["wallet_obj"]

                logo_url = NETWORK_LOGOS.get(chain.lower(), "https://via.placeholder.com/32?text=Logo")
                chain_name = NETWORK_NAMES.get(chain.lower(), chain.capitalize())
                address_display = (address[:6] + "..." + address[-4:]) if address else "Not connected"

                st.markdown(
                    f"""
                    <div class="card">
                        <div style="display:flex; align-items:center; margin-bottom:0.75rem;">
                            <img src="{logo_url}" alt="{chain_name}" style="width:32px; height:32px; border-radius:50%; margin-right:0.6rem;">
                            <h3 style="margin:0; font-size:1rem; font-weight:600; color:#c7d2fe;">
                                {chain_name}
                            </h3>
                        </div>
                        <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                            Status: ❌ Disconnected
                        </p>
                        <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                            Address: {address_display}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                address_input = st.text_input("Enter Wallet Address to Connect", key=f"addr_{chain}")
                if st.button("Connect", key=f"connect_{chain}"):
                    try:
                        if Web3.is_address(address_input):
                            wallet_obj.connect(address_input)
                            st.success("Wallet connected.")
                            st.rerun()
                        else:
                            st.error("Invalid wallet address.")
                    except ValueError as e:
                        logger.error(f"Connection failed for {chain}: {e}")
                        st.error(f"Connection failed: {str(e)}")

    st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    render()