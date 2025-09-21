import streamlit as st
import logging
from typing import List, Dict, Any
from utils import safe_get, format_number, get_layer2_opportunities
from wallet_utils import get_connected_wallet, NETWORK_NAMES
from config import NETWORK_LOGOS, BALANCE_SYMBOLS
from web3 import Web3
from streamlit_javascript import st_javascript
import db

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    filename="logs/layer2_focus.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

# --- Utility Functions ---
def get_post_message():
    """Retrieve the last JavaScript message."""
    return st_javascript("return window.lastMessage || {}")

# --- Page Title / Header ---
def render():
    st.title("🌉 Layer 2 Opportunities")
    st.write("Explore high-yield opportunities on Layer 2 networks.")

    # Wallet connection UI
    wallet = get_connected_wallet(st.session_state, chain=None)  # Default to any chain
    wallet_display = (
        f"{wallet.address[:6]}...{wallet.address[-4:]}"
        if wallet and wallet.address and Web3.is_address(wallet.address)
        else "Not connected"
    )

    st.markdown(
        """
        <div class="text-center py-6">
            <h1 class="text-3xl font-bold mb-2 bg-clip-text text-transparent 
                bg-gradient-to-r from-indigo-400 to-blue-400">
                Connect Your Wallet
            </h1>
            <p class="text-sm text-gray-400">
                Connect via MetaMask or WalletConnect to interact with opportunities.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Inject MetaMask and WalletConnect logic
    st.markdown(
        """
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
            Current: {wallet_display}
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
                    const network = await provider.getNetwork();
                    this.chainId = network.chainId.toString();
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
        const walletConnect = new WalletConnectConnector('bbfc8335f232745db239ec392b6a9d4a');
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
        """.replace("{wallet_display}", wallet_display),
        unsafe_allow_html=True
    )

    # Process connection messages
    message = get_post_message()
    if message.get("type") == "streamlit:connectWallet":
        chain = safe_get(message, "chain", "unknown")
        address = safe_get(message, "address", None)
        connector = safe_get(message, "connector", "Unknown")
        try:
            if address and Web3.is_address(address):
                address = Web3.to_checksum_address(address)
                wallet = get_connected_wallet(st.session_state, chain)
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
        if wallet:
            wallet.disconnect()
            st.info(f"Disconnected from {connector}")
            st.rerun()

    # Fetch and validate L2 opportunities
    l2_opps = get_layer2_opportunities()  # Assumed synchronous; returns List[Dict]
    cleaned_opps = []
    for opp in l2_opps:
        try:
            chain = safe_get(opp, "chain", "unknown")
            project = safe_get(opp, "project", "Unknown")
            token_symbol = safe_get(opp, "symbol", "Unknown")
            protocol = safe_get(opp, "protocol", "Unknown")
            if not all(isinstance(x, str) for x in [chain, project, token_symbol, protocol]):
                logger.warning(f"Skipping invalid opportunity: {opp}")
                continue
            apy = float(safe_get(opp, "apy", 0.0))
            tvl = float(safe_get(opp, "tvl", 0.0))
            if apy < 0 or tvl < 0:
                logger.warning(f"Skipping opportunity with negative APY/TVL: {opp}")
                continue
            cleaned_opps.append({
                "chain": chain,
                "project": project,
                "token_symbol": token_symbol,
                "protocol": protocol,
                "apy": apy,
                "tvl": tvl,
                "url": safe_get(opp, "url", "#")
            })
        except Exception as e:
            logger.warning(f"Error processing opportunity: {e}")
            continue

    if not cleaned_opps:
        st.warning("No valid Layer 2 opportunities found.")
        return

    # Display opportunities
    st.markdown(
        """
        <style>
            .card { background: #1e1e2f; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        </style>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        """,
        unsafe_allow_html=True
    )

    for opp in cleaned_opps:
        chain = opp["chain"]
        project = opp["project"]
        token_symbol = opp["token_symbol"]
        protocol = opp["protocol"]
        apy = opp["apy"]
        tvl = opp["tvl"]
        url = opp["url"]

        logo_url = NETWORK_LOGOS.get(chain.lower(), "https://via.placeholder.com/32?text=Logo")
        chain_name = NETWORK_NAMES.get(chain.lower(), chain.capitalize())

        st.markdown(
            f"""
            <div class="card">
                <div style="display:flex; align-items:center; margin-bottom:0.75rem;">
                    <img src="{logo_url}" alt="{chain_name}" style="width:32px; height:32px; border-radius:50%; margin-right:0.6rem;">
                    <h3 style="margin:0; font-size:1rem; font-weight:600; color:#c7d2fe;">
                        {project}
                    </h3>
                </div>
                <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                    Chain: {chain_name} | Token: {token_symbol}
                </p>
                <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                    Protocol: {protocol}
                </p>
                <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                    APY: {apy:.2f}%
                </p>
                <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">
                    TVL: {format_number(tvl)}
                </p>
                <a href="{url}" target="_blank" style="color:#6366f1; text-decoration:none;">View Details ↗</a>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    render()