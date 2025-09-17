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
)

# --- Load Environment Variables ---
load_dotenv()
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")

if not WALLET_ADDRESS:
    st.error("⚠️ No WALLET_ADDRESS found in .env file. Please add it.")
    st.stop()


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
                Your wallet address is loaded from <code>.env</code>. 
                MetaMask or WalletConnect can override this if connected.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Inject WalletConnect modal + MetaMask logic
    st.markdown(
        f"""
        <!-- WalletConnect Modal -->
        <script src="https://unpkg.com/@walletconnect/modal@2.6.2/dist/index.umd.js"></script>

        <button id="connectButton"
            style="background: linear-gradient(to right, #6366f1, #3b82f6);
                   border:none; padding:12px 24px; border-radius:10px;
                   color:white; font-size:16px; cursor:pointer;">
            🔗 Connect MetaMask
        </button>

        <p id="walletAddress" style="margin-top:10px; font-size:14px; color:#9ca3af;">
            Loaded from .env: {WALLET_ADDRESS}
        </p>

        <script>
        const walletAddress = document.getElementById('walletAddress');
        const connectButton = document.getElementById('connectButton');

        async function connectMetaMaskDirect() {{
            try {{
                const accounts = await window.ethereum.request({{ method: 'eth_requestAccounts' }});
                const account = accounts[0];
                walletAddress.innerText = "Connected via MetaMask: " + account;
                window.lastMessage = {{ type: "streamlit:walletConnected", account }};
                window.parent.postMessage(window.lastMessage, window.location.origin);
            }} catch (err) {{
                console.error(err);
                walletAddress.innerText = "❌ Connection failed";
            }}
        }}

        async function connectWithWalletConnect() {{
            try {{
                const modal = new window.WalletConnectModal.WalletConnectModal({{
                    projectId: "demo", // 🔑 replace with your WalletConnect projectId
                    chains: [1],
                    themeMode: "dark",
                    explorerExcludedWalletIds: "ALL", 
                    explorerRecommendedWalletIds: [
                        "c5f6866f-3d9b-477e-9b5c-0b1b1b5c4e8c" // MetaMask ID
                    ]
                }});

                const session = await modal.connect();
                const account = session?.addresses?.[0] || null;

                if (account) {{
                    walletAddress.innerText = "Connected via MetaMask (WalletConnect): " + account;
                    window.lastMessage = {{ type: "streamlit:walletConnected", account }};
                    window.parent.postMessage(window.lastMessage, window.location.origin);
                }}
            }} catch (err) {{
                console.error(err);
                walletAddress.innerText = "❌ Connection failed (WalletConnect)";
            }}
        }}

        connectButton.onclick = async () => {{
            if (typeof window.ethereum !== 'undefined') {{
                // MetaMask extension available
                await connectMetaMaskDirect();
            }} else {{
                // No extension → use WalletConnect modal
                await connectWithWalletConnect();
            }}
        }};
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


# --- Utility: get postMessage safely ---
def get_post_message() -> dict:
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

    # Fetch last wallet connection (MetaMask or WalletConnect)
    msg = get_post_message()
    connected_address = msg.get("account", WALLET_ADDRESS)

    # ✅ Save connected wallet to DB (override .env address)
    if msg.get("type") == "streamlit:walletConnected" and connected_address:
        for chain in NETWORK_NAMES.keys():
            db.save_wallet(
                wallet_id=f"{chain}_{connected_address}",
                chain=chain,
                address=connected_address,
                connected=True,
                verified=False,
                balance=0.0,
                nonce=None,
            )

    wallets = get_all_wallets(st.session_state) or []
    if not wallets and WALLET_ADDRESS:
        for chain in NETWORK_NAMES.keys():
            db.save_wallet(
                wallet_id=f"{chain}_{WALLET_ADDRESS}",
                chain=chain,
                address=WALLET_ADDRESS,
                connected=True,
                verified=False,
                balance=0.0,
                nonce=None,
            )
        wallets = get_all_wallets(st.session_state)

    if not wallets:
        st.info("No wallets available.")

    for wallet in wallets:
        chain = getattr(wallet, "chain", "unknown")
        logo_url = NETWORK_LOGOS.get(chain, "https://via.placeholder.com/32?text=Logo")
        chain_name = NETWORK_NAMES.get(chain, chain.capitalize())
        address = getattr(wallet, "address", connected_address)
        balance_val = getattr(wallet, "balance", 0.0) or 0.0
        balance_display = f"{balance_val:.4f} {BALANCE_SYMBOLS.get(chain, 'Native')}"
        address_display = (address[:6] + "..." + address[-4:]) if address else "Not connected"

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
                    <p>Status: ✅ Using {('MetaMask/WalletConnect' if msg.get('type') == 'streamlit:walletConnected' else '.env')}</p>
                    <p>Address: {address_display}</p>
                    <p>Balance: {balance_display}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


render_wallet_cards()
