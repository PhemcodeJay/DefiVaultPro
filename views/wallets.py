from argparse import Action
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
    filename="logs/app.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

# --- Load Environment Variables ---
load_dotenv()
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
WALLET_CONNECT_PROJECT_ID = os.getenv("WALLET_CONNECT_PROJECT_ID", "bbfc8335f232745db239ec392b6a9d4a")  # Fallback for testing

if not WALLET_ADDRESS:
    st.error("⚠️ No WALLET_ADDRESS found in .env file. Please add it.")
    st.stop()

if not WALLET_CONNECT_PROJECT_ID:
    st.warning("⚠️ No WALLET_CONNECT_PROJECT_ID found in .env file. Using default project ID.")

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
        if isinstance(WALLET_ADDRESS, str) and len(WALLET_ADDRESS) > 10
        else "Not set"
    )

    # Inject MetaMask and WalletConnect logic (embedded JS, no separate file)
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
                    '0xe9ac0ce': 'neon',
                    '0x89': 'polygon',
                    '0xfa': 'fantom',
                    '0x63564c40': 'solana',
                    '0x4e454152': 'aurora',
                    '0x19': 'cronos'
                }};
                this.ethersProvider = null;
                this.targetOrigin = window.location.origin;
            }}

            async checkMetaMaskAvailable() {{
                if (typeof window.ethereum !== 'undefined' && typeof window.ethers !== 'undefined') {{
                    this.ethersProvider = new ethers.providers.Web3Provider(window.ethereum);
                    return true;
                }}
                throw new Error('MetaMask or ethers.js not installed. Please install MetaMask extension.');
            }}

            async connectWallet() {{
                try {{
                    await this.checkMetaMaskAvailable();
                    const accounts = await window.ethereum.request({{ method: 'eth_requestAccounts' }});
                    this.account = accounts[0];
                    this.chainId = await window.ethereum.request({{ method: 'eth_chainId' }});
                    this.isConnected = true;

                    const result = {{
                        type: 'streamlit:walletConnected',
                        account: this.account,
                        chainId: this.chainId,
                        network: this.networkMap[this.chainId] || 'unknown'
                    }};
                    window.lastMessage = result;
                    window.parent.postMessage(result, this.targetOrigin);

                    window.ethereum.on('accountsChanged', this.handleAccountsChanged.bind(this));
                    window.ethereum.on('chainChanged', this.handleChainChanged.bind(this));

                    return result;
                }} catch (error) {{
                    const errorMsg = {{
                        type: 'streamlit:walletError',
                        error: error.message,
                        code: error.code || 'UNKNOWN_ERROR'
                    }};
                    window.lastMessage = errorMsg;
                    window.parent.postMessage(errorMsg, this.targetOrigin);
                    throw error;
                }}
            }}

            async connectWalletConnect(projectId) {{
                try {{
                    const {{ WalletConnectModal }} = window.WalletConnectModal;
                    const modal = new WalletConnectModal({{
                        projectId: projectId,
                        chains: [
                            1,      // Ethereum
                            56,     // BSC
                            42161,  // Arbitrum
                            10,     // Optimism
                            8453,   // Base
                            43114,  // Avalanche
                            245022934, // Neon
                            137,    // Polygon
                            250,    // Fantom
                            756260, // Solana (if supported)
                            1313161554, // Aurora
                            25      // Cronos
                        ]
                    }});

                    const {{ uri }} = await modal.openModal();
                    console.log('WalletConnect URI:', uri);

                    modal.subscribeModal((data) => {{
                        if (data && data.account && data.chainId) {{
                            this.account = data.account;
                            this.chainId = data.chainId;
                            this.isConnected = true;

                            const result = {{
                                type: 'streamlit:walletConnected',
                                account: data.account,
                                chainId: data.chainId,
                                network: this.networkMap[data.chainId] || 'unknown'
                            }};
                            window.lastMessage = result;
                            window.parent.postMessage(result, this.targetOrigin);
                        }}
                    }});

                    return {{ message: 'WalletConnect modal opened' }};
                }} catch (error) {{
                    const errorMsg = {{
                        type: 'streamlit:walletError',
                        error: error.message,
                        code: error.code || 'UNKNOWN_ERROR'
                    }};
                    window.lastMessage = errorMsg;
                    window.parent.postMessage(errorMsg, this.targetOrigin);
                    throw error;
                }}
            }}

            async performDeFiAction(action, txData) {{
                try {{
                    if (!this.isConnected || !this.ethersProvider) {{
                        throw new Error('Wallet not connected');
                    }}
                    const signer = this.ethersProvider.getSigner();
                    const tx = await signer.sendTransaction(txData);
                    const receipt = await tx.wait();
                    const result = {{
                        type: 'streamlit:txSuccess',
                        txHash: receipt.transactionHash
                    }};
                    window.lastMessage = result;
                    window.parent.postMessage(result, this.targetOrigin);
                    return result;
                }} catch (error) {{
                    const errorMsg = {{
                        type: 'streamlit:txError',
                        error: error.message,
                        code: error.code || 'UNKNOWN_ERROR'
                    }};
                    window.lastMessage = errorMsg;
                    window.parent.postMessage(errorMsg, this.targetOrigin);
                    throw error;
                }}
            }}

            handleAccountsChanged(accounts) {{
                this.isConnected = accounts.length > 0;
                this.account = accounts.length > 0 ? accounts[0] : null;

                const msg = {{
                    type: 'streamlit:accountsChanged',
                    account: this.account,
                    chainId: this.chainId,
                    network: this.networkMap[this.chainId] || 'unknown'
                }};
                window.lastMessage = msg;
                window.parent.postMessage(msg, this.targetOrigin);
            }}

            handleChainChanged(chainId) {{
                this.chainId = chainId;

                const msg = {{
                    type: 'streamlit:chainChanged',
                    chainId: chainId,
                    network: this.networkMap[chainId] || 'unknown'
                }};
                window.lastMessage = msg;
                window.parent.postMessage(msg, this.targetOrigin);
            }}

            disconnect() {{
                this.isConnected = false;
                this.account = null;
                this.chainId = null;

                if (window.ethereum) {{
                    window.ethereum.removeListener('accountsChanged', this.handleAccountsChanged.bind(this));
                    window.ethereum.removeListener('chainChanged', this.handleChainChanged.bind(this));
                }}
                this.ethersProvider = null;

                const msg = {{ type: 'streamlit:disconnected' }};
                window.lastMessage = msg;
                window.parent.postMessage(msg, this.targetOrigin);
            }}
        }}

        window.metamaskConnector = new MetaMaskConnector();

        document.getElementById('connectButton').addEventListener('click', async () => {{
            try {{
                await window.metamaskConnector.connectWallet();
            }} catch (error) {{
                console.error('Connection failed:', error);
            }}
        }});

        window.performDeFiAction = async (action, txData) => {{
            try {{
                return await window.metamaskConnector.performDeFiAction(action, txData);
            }} catch (error) {{
                console.error(`${Action} failed:`, error);
                throw error;
            }}
        }};
        </script>
        """,
        unsafe_allow_html=True,
    )

    # Fetch connected chain and address from JS
    connected_address = None
    connected_chain = None
    response = st_javascript("return window.lastMessage || {}")
    if isinstance(response, dict) and response.get("type") == "streamlit:walletConnected":
        connected_address = response.get("account")
        connected_chain = response.get("network")

    # Initialize default wallets if not present
    try:
        if 'wallets' not in st.session_state:
            init_wallets(st.session_state)
            for chain in NETWORK_NAMES.keys():
                checksum_address = Web3.to_checksum_address(WALLET_ADDRESS) # type: ignore
                st.session_state.wallets[chain] = db.Wallet(
                    chain=chain,
                    address=checksum_address,
                    connected=(connected_chain == chain and connected_address == checksum_address),
                    verified=False,
                    balance=0.0,
                    nonce=None,
                )
            wallets = get_all_wallets(st.session_state)
    except Exception as e:
        st.error(f"Failed to initialize default wallets: {e}")

    if not st.session_state.get('wallets'):
        st.info("No wallets available.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Tabs for Wallets
    tab_active, tab_disconnected = st.tabs(["Active Wallets", "Disconnected Wallets"])

    with tab_active:
        active_wallets = [w for w in st.session_state.wallets.values() if w.connected]
        if not active_wallets:
            st.info("No active wallets.")
        else:
            st.markdown(
                """
                <style>
                    .card { background: #1e1e2f; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
                </style>
                """,
                unsafe_allow_html=True,
            )
            for wallet in active_wallets:
                chain = wallet.chain
                logo_url = NETWORK_LOGOS.get(chain, "https://via.placeholder.com/32?text=Logo")
                chain_name = NETWORK_NAMES.get(chain, chain.capitalize())
                address = wallet.address
                balance_val = wallet.balance or 0.0
                balance_display = f"{balance_val:.4f} {BALANCE_SYMBOLS.get(chain, 'Native')}"
                address_display = (address[:6] + "..." + address[-4:]) if address else "Not connected"
                connection_status = "MetaMask/WalletConnect" if chain == connected_chain and address == connected_address else ".env"

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
                    unsafe_allow_html=True,
                )
                if st.button("Disconnect", key=f"disconnect_active_{chain}"):
                    wallet.disconnect()
                    st.rerun()

    with tab_disconnected:
        disconnected_wallets = [w for w in st.session_state.wallets.values() if not w.connected]
        if not disconnected_wallets:
            st.info("No disconnected wallets.")
        else:
            st.markdown(
                """
                <style>
                    .card { background: #1e1e2f; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
                </style>
                """,
                unsafe_allow_html=True,
            )
            for wallet in disconnected_wallets:
                chain = wallet.chain
                logo_url = NETWORK_LOGOS.get(chain, "https://via.placeholder.com/32?text=Logo")
                chain_name = NETWORK_NAMES.get(chain, chain.capitalize())
                address = wallet.address
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
                    unsafe_allow_html=True,
                )
                address_input = st.text_input("Enter Wallet Address to Connect", key=f"addr_{chain}")
                if st.button("Connect", key=f"connect_{chain}"):
                    try:
                        wallet.connect(address_input)
                        st.success("Wallet connected.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    render()