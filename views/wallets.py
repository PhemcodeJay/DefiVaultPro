import os
import uuid
import streamlit as st
from dotenv import load_dotenv
from streamlit_javascript import st_javascript
import db
from wallet_utils import (
    get_all_wallets,
    init_wallets,
    NETWORK_NAMES,
    NETWORK_LOGOS,
    BALANCE_SYMBOLS,
    Wallet,
)
from web3 import Web3
from typing import Optional


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
        if isinstance(WALLET_ADDRESS, str) and len(WALLET_ADDRESS) >= 10
        else "Not set"
    )

    # Inject MetaMask and WalletConnect logic
    st.markdown(
        f"""
        <!-- WalletConnect Modal -->
        <script src="https://unpkg.com/@walletconnect/modal@2.6.2/dist/index.umd.js"></script>

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
        const walletAddress = document.getElementById('walletAddress');
        const connectButton = document.getElementById('connectButton');

        async function connectMetaMaskDirect() {{
            try {{
                const accounts = await window.ethereum.request({{ method: 'eth_requestAccounts' }});
                const account = accounts[0];
                const chainId = await window.ethereum.request({{ method: 'eth_chainId' }});
                walletAddress.innerText = "Connected via MetaMask: " + account;
                window.lastMessage = {{ type: "streamlit:walletConnected", account, chainId }};
                window.parent.postMessage(window.lastMessage, window.location.origin);
            }} catch (err) {{
                console.error(err);
                walletAddress.innerText = "❌ MetaMask connection failed: " + err.message;
            }}
        }}

        async function connectWithWalletConnect() {{
            try {{
                const modal = new window.WalletConnectModal.WalletConnectModal({{
                    projectId: "{WALLET_CONNECT_PROJECT_ID}",
                    chains: [1, 56, 42161, 10, 8453, 43114, 245022934],
                    themeMode: "dark",
                    explorerExcludedWalletIds: "ALL",
                    explorerRecommendedWalletIds: [
                        "c5f6866f-3d9b-477e-9b5c-0b1b1b5c4e8c" // MetaMask ID
                    ]
                }});

                const session = await modal.connect();
                const account = session?.namespaces?.eip155?.accounts?.[0]?.split(':')[2] || null;
                const chainId = session?.namespaces?.eip155?.chains?.[0] || '0x1';

                if (account) {{
                    walletAddress.innerText = "Connected via WalletConnect: " + account;
                    window.lastMessage = {{ type: "streamlit:walletConnected", account, chainId }};
                    window.parent.postMessage(window.lastMessage, window.location.origin);
                }} else {{
                    walletAddress.innerText = "❌ WalletConnect failed: No account found";
                }}
            }} catch (err) {{
                console.error(err);
                walletAddress.innerText = "❌ WalletConnect connection failed: " + err.message;
            }}
        }}

        connectButton.onclick = async () => {{
            if (typeof window.ethereum !== 'undefined') {{
                await connectMetaMaskDirect();
            }} else {{
                await connectWithWalletConnect();
            }}
        }};
        </script>
        """,
        unsafe_allow_html=True,
    )  # type: ignore

    # Initialize session state
    if 'wallets' not in st.session_state:
        try:
            init_wallets(st.session_state)
        except Exception as e:
            st.warning(f"Failed to initialize wallets: {e}")

    # Fetch last wallet connection
    msg = get_post_message()
    connected_address = msg.get("account")
    chain_id = msg.get("chainId")
    chain_map = {
        '0x1': 'ethereum',
        '0x38': 'bsc',
        '0xa4b1': 'arbitrum',
        '0xa': 'optimism',
        '0x2105': 'base',
        '0xa86a': 'avalanche',
        '0xe9ac0ce': 'neon'
    }
    connected_chain = chain_map.get(chain_id, 'ethereum') if chain_id else None

    # Save connected wallet to DB
    if msg.get("type") == "streamlit:walletConnected" and connected_address and connected_chain:
        try:
            connected_address = Web3.to_checksum_address(connected_address)
            wallet_id = f"{connected_chain}_{connected_address}"
            db.save_wallet(
                wallet_id=wallet_id,
                chain=connected_chain,
                address=connected_address,
                connected=True,
                verified=False,
                balance=0.0,
                nonce=None,
            )
            wallet = st.session_state.wallets.get(connected_chain)
            if wallet:
                wallet.connect(connected_address)
        except Exception as e:
            st.error(f"Failed to save wallet connection: {e}")

    # Render wallet cards with default values if None
    render_wallet_cards(
        connected_address if isinstance(connected_address, str) else "",
        connected_chain if isinstance(connected_chain, str) else ""
    )

# --- Utility: get postMessage safely ---
def get_post_message() -> dict:
    try:
        res = st_javascript("return window.lastMessage || {}")
        return res if isinstance(res, dict) else {}
    except Exception:
        return {}

# --- Render Wallet Cards ---
def render_wallet_cards(connected_address: Optional[str], connected_chain: Optional[str]):
    st.markdown(
        """
        <div style='
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); 
            gap: 1.2rem; 
            padding: 1rem;
        '>
        """,
        unsafe_allow_html=True,
    )

    wallets = get_all_wallets(st.session_state) or []
    if not wallets and WALLET_ADDRESS:
        try:
            checksum_address = Web3.to_checksum_address(WALLET_ADDRESS)
            for chain in NETWORK_NAMES.keys():
                db.save_wallet(
                    wallet_id=f"{chain}_{checksum_address}",
                    chain=chain,
                    address=checksum_address,
                    connected=(chain == connected_chain and connected_address == checksum_address),
                    verified=False,
                    balance=0.0,
                    nonce=None,
                )
            wallets = get_all_wallets(st.session_state)
        except Exception as e:
            st.error(f"Failed to initialize default wallets: {e}")

    if not wallets:
        st.info("No wallets available.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for wallet in wallets:
        chain = getattr(wallet, "chain", "unknown")
        logo_url = NETWORK_LOGOS.get(chain, "https://via.placeholder.com/32?text=Logo")
        chain_name = NETWORK_NAMES.get(chain, chain.capitalize())
        address = getattr(wallet, "address", None)
        balance_val = getattr(wallet, "balance", 0.0) or 0.0
        balance_display = f"{balance_val:.4f} {BALANCE_SYMBOLS.get(chain, 'Native')}"
        address_display = (address[:6] + "..." + address[-4:]) if address else "Not connected"
        connection_status = (
            "MetaMask/WalletConnect"
            if chain == connected_chain and address == connected_address
            else ".env" if address else "Disconnected"
        )

        st.markdown(
            f"""
            <div style='
                background: linear-gradient(135deg, rgba(49,46,129,0.3), rgba(30,64,175,0.3));
                border-radius: 16px;
                padding: 1rem;
                box-shadow: 0 4px 12px rgba(0,0,0,0.25);
            '>
                <div style="display:flex; align-items:center; margin-bottom:0.75rem;">
                    <img src="{logo_url}" alt="{chain_name}" style="width:32px; height:32px; border-radius:50%; margin-right:0.6rem;">
                    <h3 style="margin:0; font-size:1rem; font-weight:600; color:#c7d2fe;">
                        {chain_name}
                    </h3>
                </div>
                <div style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.75rem;">
                    <p>Status: {'✅ Connected via ' + connection_status if wallet.connected else '❌ Disconnected'}</p>
                    <p>Address: {address_display}</p>
                    <p>Balance: {balance_display}</p>
                </div>
                <button onclick="document.getElementById('disconnect_{chain}').click()" style="background: #ef4444; border:none; padding:8px 16px; border-radius:8px; color:white; font-size:0.8rem; cursor:pointer;">
                    Disconnect
                </button>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Disconnect", key=f"disconnect_{chain}"):
            wallet.disconnect()
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    render()
