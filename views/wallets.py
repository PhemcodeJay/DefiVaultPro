import os
import time
import uuid
import streamlit as st
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct
from dotenv import load_dotenv
from streamlit_javascript import st_javascript
import db
from wallet_utils import (
    get_all_wallets,
    init_wallets,
    get_connected_wallet,
    NETWORK_NAMES,
    NETWORK_LOGOS,
    CHAIN_IDS,
    BALANCE_SYMBOLS,
)

# --- Load Environment Variables ---
load_dotenv()

# --- Page Title / Header ---
def render_wallets():
    st.title("👛 Wallets")

    st.markdown(
        """
        <div class="text-center py-6">
            <h1 class="text-3xl font-bold mb-2 bg-clip-text text-transparent 
                bg-gradient-to-r from-indigo-400 to-blue-400">
                Connect Your Wallet
            </h1>
            <p class="text-sm text-gray-400">
                Manage your MetaMask wallets across supported chains
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Inject a MetaMask connect button
    st.markdown(
        """
        <button id="connectButton"
            style="background: linear-gradient(to right, #6366f1, #3b82f6);
                   border:none; padding:12px 24px; border-radius:10px;
                   color:white; font-size:16px; cursor:pointer;">
            🔗 Connect MetaMask
        </button>

        <p id="walletAddress" style="margin-top:10px; font-size:14px; color:#9ca3af;"></p>

        <script>
        const connectButton = document.getElementById('connectButton');
        const walletAddress = document.getElementById('walletAddress');

        if (typeof window.ethereum === 'undefined') {
            connectButton.innerText = 'Install MetaMask';
            connectButton.onclick = () => {
                window.open('https://metamask.io/download.html', '_blank');
            };
        } else {
            connectButton.onclick = async () => {
                try {
                    const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                    walletAddress.innerText = "Connected: " + accounts[0];
                } catch (err) {
                    console.error(err);
                    walletAddress.innerText = "❌ Connection failed";
                }
            };
        }
        </script>
        """,
        unsafe_allow_html=True,
    )
render_wallets()
# --- Initialize Session State ---
try:
    init_wallets(st.session_state)
except Exception as e:
    st.warning(f"Failed to initialize wallets: {e}")

# --- Helper: Modern Gradient Button ---
def action_button(label, color_from="#6366f1", color_to="#3b82f6", key=None):
    """
    Renders a modern gradient button that works with Streamlit.
    Returns True if clicked.
    """
    if key is None:
        key = str(uuid.uuid4())

    button_id = f"btn-{key}"
    clicked = st.button(label, key=button_id, use_container_width=True)

    # Custom CSS
    st.markdown(
        f"""
        <style>
        div[data-testid="stButton"] button#{button_id} {{
            background: linear-gradient(135deg, {color_from}, {color_to});
            color: white !important;
            border: none;
            border-radius: 9999px;
            padding: 0.5rem 1rem;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease-in-out;
            box-shadow: 0 4px 10px rgba(0,0,0,0.25);
        }}
        div[data-testid="stButton"] button#{button_id}:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 14px rgba(0,0,0,0.35);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    return clicked


# --- Utility: get postMessage safely ---
def get_post_message() -> dict:
    """Retrieve postMessage data from JavaScript."""
    try:
        res = st_javascript("return window.lastMessage || {}")
        return res if isinstance(res, dict) else {}
    except Exception:
        return {}

# --- Render Wallet Cards ---
def render_wallet_cards():
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
    if not wallets:
        st.info("No wallets available.")

    for idx, wallet in enumerate(wallets):
        chain = getattr(wallet, "chain", "unknown")
        # Get the logo URL safely
        logo_url = NETWORK_LOGOS.get(chain)  # Try to get the URL

        # Fallback if chain is missing, None, or empty
        if not logo_url:
            logo_url = "https://via.placeholder.com/32?text=Logo"

        chain_name = NETWORK_NAMES.get(chain, chain.capitalize())
        is_connected = getattr(wallet, "connected", False)
        address = getattr(wallet, "address", None)
        verified_flag = getattr(wallet, "verified", False)

        address_display = (address[:6] + "..." + address[-4:]) if address else "Not connected"
        balance_val = getattr(wallet, "balance", 0.0) or 0.0
        balance_display = f"{balance_val:.4f} {BALANCE_SYMBOLS.get(chain, 'Native')}"
        nonce_val = getattr(wallet, "nonce", "N/A")

        base_key = f"{chain}_{idx}_{address or 'noaddr'}"

        # --- Card Container ---
        st.markdown(
            f"""
            <div style='
                background: linear-gradient(135deg, rgba(49,46,129,0.3), rgba(30,64,175,0.3));
                border-radius: 16px;
                padding: 1rem;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                box-shadow: 0 4px 12px rgba(0,0,0,0.25);
            '>
                <div style="display:flex; align-items:center; margin-bottom:0.75rem;">
                    <img src="{logo_url}" onerror="this.src='https://via.placeholder.com/32'" 
                         alt="{chain_name}" 
                         style="width:32px; height:32px; border-radius:50%; margin-right:0.6rem;">
                    <h3 style="margin:0; font-size:1rem; font-weight:600; color:#c7d2fe;">
                        {chain_name}
                    </h3>
                </div>
                <div style="color:#e0e7ff; font-size:0.9rem; line-height:1.4; margin-bottom:0.75rem;">
                    <p style="margin:0;">Status: {'✅ Connected' if is_connected else '❌ Disconnected'}</p>
                    <p style="margin:0;">Address: {address_display}</p>
                    <p style="margin:0;">Balance: {balance_display}</p>
                    <p style="margin:0;">Nonce: {nonce_val}</p>
                </div>
                <div style="display:flex; flex-direction:column; gap:0.5rem;">
            """,
            unsafe_allow_html=True,
        )

        # Buttons
        if is_connected:
            if action_button("🔄 Update Balance", key=f"update_{base_key}"):
                with st.spinner("Updating balance..."):
                    try:
                        wallet.update_balance()
                        if address:
                            db.save_wallet(
                                wallet_id=f"{chain}_{address}",
                                chain=chain,
                                address=address,
                                connected=True,
                                verified=verified_flag,
                                balance=wallet.balance,
                                nonce=wallet.nonce,
                            )
                            st.success("Balance updated!")
                    except Exception as e:
                        st.error(f"Failed: {e}")
                st.rerun()

            if not verified_flag and action_button("✅ Verify Ownership", "#10b981", "#059669", key=f"verify_{base_key}"):
                with st.spinner("Verifying..."):
                    try:
                        nonce = wallet.nonce or 0
                        message = f"Verify wallet ownership: {nonce}"
                        st.markdown(
                            f"""
                            <script>
                            (async () => {{
                                try {{
                                    const sig = await window.signMetaMaskMessage("{message}");
                                    window.lastMessage = {{type: 'streamlit:signature', signature: sig}};
                                    window.parent.postMessage(window.lastMessage, window.location.origin);
                                }} catch (err) {{
                                    window.lastMessage = {{type: 'streamlit:walletError', error: err?.message || String(err)}};
                                    window.parent.postMessage(window.lastMessage, window.location.origin);
                                }}
                            }})();
                            </script>
                            """,
                            unsafe_allow_html=True,
                        )
                        time.sleep(1)
                        response = get_post_message()
                        if response.get("type") == "streamlit:signature":
                            signature = response["signature"]
                            signer = Account.recover_message(
                                encode_defunct(text=message), signature=signature
                            )
                            if address and signer.lower() == address.lower():
                                wallet.verified = True
                                db.save_wallet(
                                    wallet_id=f"{chain}_{address}",
                                    chain=chain,
                                    address=address,
                                    connected=True,
                                    verified=True,
                                    balance=wallet.balance,
                                    nonce=wallet.nonce,
                                )
                                st.success("Wallet verified!")
                    except Exception as e:
                        st.error(f"Verification failed: {e}")
                st.rerun()

            if action_button("❌ Disconnect", "#ef4444", "#dc2626", key=f"disconnect_{base_key}"):
                try:
                    wallet.disconnect()
                    if address:
                        db.disconnect_wallet(f"{chain}_{address}")
                    st.success("Wallet disconnected!")
                except Exception as e:
                    st.error(f"Failed: {e}")
                st.rerun()
        else:
            if action_button("🔗 Connect MetaMask", "#6366f1", "#3b82f6", key=f"connect_{base_key}"):
                with st.spinner("Connecting..."):
                    try:
                        chain_id = CHAIN_IDS.get(chain)
                        if not chain_id:
                            st.error(f"No chain ID found for {chain}")
                        else:
                            chain_id_hex = hex(chain_id)
                            st.markdown(
                                f"""
                                <script>
                                (async () => {{
                                    try {{
                                        await window.switchMetaMaskNetwork('{chain_id_hex}');
                                        const result = await window.connectMetaMask();
                                        window.lastMessage = {{type: 'streamlit:walletConnected', ...result}};
                                        window.parent.postMessage(window.lastMessage, window.location.origin);
                                    }} catch (err) {{
                                        window.lastMessage = {{type: 'streamlit:walletError', error: err?.message || String(err)}};
                                        window.parent.postMessage(window.lastMessage, window.location.origin);
                                    }}
                                }})();
                                </script>
                                """,
                                unsafe_allow_html=True,
                            )
                            time.sleep(2)
                            response = get_post_message()
                            if response.get("type") == "streamlit:walletConnected":
                                addr = response["account"]
                                wallet.connect(addr)
                                wallet.update_nonce()
                                db.save_wallet(
                                    wallet_id=f"{chain}_{addr}",
                                    chain=chain,
                                    address=addr,
                                    connected=True,
                                    verified=False,
                                    balance=wallet.balance,
                                    nonce=wallet.nonce,
                                )
                                st.success(f"Connected to {addr} on {chain_name}")
                    except Exception as e:
                        st.error(f"Connection failed: {e}")
                st.rerun()

        st.markdown("</div></div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# --- Render Cards ---
render_wallet_cards()

# --- Manual Wallet Connection ---
st.subheader("📝 Manual Wallet Connection")
manual_chain = st.selectbox("Select Chain", list(NETWORK_NAMES.keys()))
manual_address = st.text_input("Enter Wallet Address")
if action_button("Add Manual Wallet", "#8b5cf6", "#6366f1", key="manual_add"):
    if manual_chain and manual_address:
        if not Web3.is_address(manual_address):
            st.error("Invalid wallet address")
        else:
            wallet = get_connected_wallet(st.session_state, manual_chain)
            if wallet:
                wallet.connect(manual_address)
                db.save_wallet(
                    wallet_id=f"{manual_chain}_{manual_address}",
                    chain=manual_chain,
                    address=manual_address,
                    connected=True,
                    verified=False,
                    balance=0.0,
                    nonce=None,
                )
                st.success("Manual wallet added!")
                st.rerun()
            else:
                st.error(f"No wallet found for {manual_chain}")
    else:
        st.error("Please select a chain and enter a valid address")

# --- Supported Networks ---
st.markdown(
    """
<div class="card bg-gradient-to-br from-gray-900/30 to-gray-700/30 p-4 mt-4">
    <h3 class="text-lg font-semibold text-gray-400 mb-3">🌐 Supported Networks</h3>
    <div style="display:grid; grid-template-columns: repeat(2, 1fr); gap:8px; font-size:0.9rem;">
""",
    unsafe_allow_html=True,
)

networks_info = [
    ("Ethereum", "ethereum", "Layer 1"),
    ("BSC", "bsc", "Layer 1"),
    ("Arbitrum", "arbitrum", "Layer 2"),
    ("Optimism", "optimism", "Layer 2"),
    ("Base", "base", "Layer 2"),
    ("Avalanche", "avalanche", "Layer 1"),
    ("Neon EVM", "neon", "Solana-based"),
]

for name, chain, layer in networks_info:
    logo_url = NETWORK_LOGOS.get(chain, "https://via.placeholder.com/16")
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; padding: 0.5rem; 
                    background: rgba(55, 65, 81, 0.5); border-radius: 6px;">
            <img src="{logo_url}" alt="{name}" 
                 style="width: 16px; height: 16px; margin-right: 0.5rem; border-radius: 50%;" 
                 onerror="this.src='https://via.placeholder.com/16'">
            <span style="color: #c7d2fe; font-size: 0.85rem;">
                <strong>{name}</strong> 
                <span style="color: #9ca3af;">({layer})</span>
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("</div></div>", unsafe_allow_html=True)
