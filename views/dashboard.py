import streamlit as st
import pandas as pd
import time
import json
import logging
import subprocess
from utils import connect_to_chain
from wallet_utils import (
    init_wallets, get_connected_wallet, add_position_to_session,
    create_position, build_erc20_approve_tx_data, build_aave_supply_tx_data,
    build_compound_supply_tx_data, confirm_tx, close_position, get_token_price
)
from config import NETWORK_LOGOS, PROTOCOL_LOGOS, CHAIN_IDS, CONTRACT_MAP, ERC20_TOKENS, explorer_urls
from streamlit_javascript import st_javascript
import db
from web3 import Web3

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    filename="logs/dashboard.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

# --- Placeholder Withdraw Functions (To be replaced if actual implementations exist) ---
def build_aave_withdraw_tx_data(chain: str, pool_address: str, token_address: str, amount: float, wallet_address: str) -> dict:
    """Placeholder for Aave withdraw transaction data."""
    try:
        w3 = connect_to_chain(chain)
        if not w3:
            raise ValueError(f"Failed to connect to chain {chain}")
        amount_wei = w3.to_wei(amount, 'ether')
        data = {
            "from": Web3.to_checksum_address(wallet_address),
            "to": Web3.to_checksum_address(pool_address),
            "data": "0x",  # Replace with actual Aave withdraw function call
            "value": 0
        }
        return data
    except Exception as e:
        logger.error(f"Failed to build Aave withdraw tx data: {e}")
        raise

def build_compound_withdraw_tx_data(chain: str, pool_address: str, token_address: str, amount: float, wallet_address: str) -> dict:
    """Placeholder for Compound withdraw transaction data."""
    try:
        w3 = connect_to_chain(chain)
        if not w3:
            raise ValueError(f"Failed to connect to chain {chain}")
        amount_wei = w3.to_wei(amount, 'ether')
        data = {
            "from": Web3.to_checksum_address(wallet_address),
            "to": Web3.to_checksum_address(pool_address),
            "data": "0x",  # Replace with actual Compound withdraw function call
            "value": 0
        }
        return data
    except Exception as e:
        logger.error(f"Failed to build Compound withdraw tx data: {e}")
        raise

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

# --- Render Opportunity Table ---
def render_opportunity_table(opps_list, category_name: str, allow_invest=True):
    if not opps_list:
        st.warning(f"No {category_name.replace('_', ' ').title()} opportunities found.")
        return

    # Convert to DataFrame for tabular display
    df = pd.DataFrame(opps_list)
    df['apy'] = df['apy'].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "0%")
    df['tvl'] = df['tvl'].apply(format_number)
    df['chain'] = df['chain'].str.capitalize()
    df['risk'] = df['risk'].fillna('Unknown')

    # Filtering
    with st.expander("Filter Opportunities", expanded=False):
        chains = st.multiselect("Filter by Chain", options=df['chain'].unique(), default=df['chain'].unique(), key=f"filter_chain_{category_name}")
        min_apy = st.slider("Minimum APY (%)", 0.0, 100.0, 0.0, key=f"min_apy_{category_name}")
        risks = st.multiselect("Filter by Risk", options=df['risk'].unique(), default=df['risk'].unique(), key=f"filter_risk_{category_name}")
        
        filtered_df = df[
            (df['chain'].isin(chains)) &
            (df['apy'].str.rstrip('%').astype(float) >= min_apy) &
            (df['risk'].isin(risks))
        ]

    # Display table
    st.dataframe(
        filtered_df[['chain', 'project', 'symbol', 'apy', 'tvl', 'risk', 'type']],
        use_container_width=True,
        column_config={
            "chain": "Chain",
            "project": "Protocol",
            "symbol": "Token",
            "apy": "APY",
            "tvl": "TVL",
            "risk": "Risk",
            "type": "Type"
        }
    )

    # Expandable cards for investment
    if allow_invest:
        for i, opp in enumerate(filtered_df.to_dict('records')):
            pool_id = safe_get(opp, "pool_id", f"unknown_{i}")
            card_key = f"{category_name}_{pool_id}"
            with st.expander(f"{opp['project']} ({opp['chain']})", expanded=st.session_state.get('expanded_cards', {}).get(card_key, False)):
                st.session_state.expanded_cards[card_key] = True
                st.markdown(f"**Symbol:** {opp['symbol']} | **APY:** {opp['apy']} | **TVL:** {opp['tvl']} | **Risk:** {opp['risk']}")
                st.markdown(f"[View on DeFiLlama]({safe_get(opp, 'link', '#')}) | [Explorer]({explorer_urls.get(opp['chain'].lower(), '#') + safe_get(opp, 'contract_address', '0x0')})")
                
                if allow_invest:
                    connected_wallet = get_connected_wallet(st.session_state, chain=opp['chain'].lower())
                    if connected_wallet:
                        selected_token = st.selectbox("Select Token", list(ERC20_TOKENS.keys()), key=f"token_{card_key}")
                        amount = st.number_input("Amount", min_value=0.0, step=0.1, key=f"amount_{card_key}")
                        if st.button("Invest Now", key=f"invest_{card_key}"):
                            try:
                                protocol = opp['project'].lower()
                                chain_id = CHAIN_IDS.get(opp['chain'].lower(), 1)
                                pool_address = CONTRACT_MAP.get(protocol, {}).get(opp['chain'].lower(), "0x0")
                                token_address = ERC20_TOKENS.get(selected_token, {}).get(opp['chain'].lower(), "0x0")
                                if not pool_address or not token_address:
                                    st.error("Invalid pool or token address")
                                    continue

                                # Approve transaction
                                if not connected_wallet or not connected_wallet.address:
                                    st.error("No connected wallet. Please connect your wallet first.")
                                    continue

                                approve_tx = build_erc20_approve_tx_data(
                                    opp['chain'].lower(),
                                    token_address,
                                    pool_address,
                                    amount,
                                    str(connected_wallet.address)  # ensure it's always a string
                                )
                                approve_tx['chainId'] = chain_id

                                st.markdown(
                                    f"<script>performDeFiAction('approve',{json.dumps(approve_tx)});</script>",
                                    unsafe_allow_html=True
                                )
                                time.sleep(1)
                                approve_resp = get_post_message()
                                if approve_resp.get("type") == "streamlit:txSuccess" and isinstance(approve_resp.get("txHash"), str) and approve_resp.get("txHash"):
                                    st.success("Approve confirmed!")
                                else:
                                    st.error("Approve failed")
                                    continue

                                # Supply transaction
                                if 'aave' in protocol:
                                    supply_tx = build_aave_supply_tx_data(
                                        opp['chain'].lower(),
                                        pool_address,
                                        token_address,
                                        amount,
                                        str(connected_wallet.address)
                                    )
                                elif 'compound' in protocol:
                                    supply_tx = build_compound_supply_tx_data(
                                        opp['chain'].lower(),
                                        pool_address,
                                        token_address,
                                        amount,
                                        str(connected_wallet.address)
                                    )
                                else:
                                    st.error(f"Unsupported protocol: {protocol}")
                                    continue


                                supply_tx['chainId'] = chain_id
                                st.markdown(f"<script>performDeFiAction('supply',{json.dumps(supply_tx)});</script>", unsafe_allow_html=True)
                                time.sleep(1)
                                response = get_post_message()
                                if response.get("type") == "streamlit:txSuccess" and isinstance(response.get("txHash"), str) and response.get("txHash"):
                                    if confirm_tx(opp['chain'].lower(), response['txHash']):
                                        position = create_position(opp['chain'].lower(), opp['project'], selected_token, amount, response['txHash'])
                                        add_position_to_session(st.session_state, position)
                                        st.success(f"Invested {amount} {selected_token} in {opp['project']}!")
                                    else:
                                        st.error("Supply transaction failed")
                                else:
                                    st.error("Supply transaction failed")
                            except Exception as e:
                                logger.error(f"Investment failed for {opp['project']}: {e}")
                                st.error(f"Investment failed: {str(e)}")
                            st.rerun()
                    else:
                        st.warning("Connect wallet to invest.")

# --- Render Meme Coin Table ---
def render_meme_table(memes_list, category_name: str):
    if not memes_list:
        st.warning(f"No {category_name} opportunities found.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(memes_list)
    df['price'] = df['price'].apply(lambda x: f"${x:.4f}" if pd.notnull(x) else "$0.00")
    df['liquidity_usd'] = df['liquidity_usd'].apply(format_number)
    df['volume_24h_usd'] = df['volume_24h_usd'].apply(format_number)
    df['market_cap'] = df['market_cap'].apply(format_number)
    df['change_24h_pct'] = df['change_24h_pct'].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "0%")
    df['chain'] = df['chain'].str.capitalize()
    df['risk'] = df['risk'].fillna('Unknown')

    # Filtering
    with st.expander("Filter Meme Coins", expanded=False):
        chains = st.multiselect("Filter by Chain", options=df['chain'].unique(), default=df['chain'].unique(), key=f"filter_chain_{category_name}")
        min_volume = st.slider("Minimum 24h Volume ($)", 0, 1000000, 0, key=f"min_volume_{category_name}")
        risks = st.multiselect("Filter by Risk", options=df['risk'].unique(), default=df['risk'].unique(), key=f"filter_risk_{category_name}")
        
        filtered_df = df[
            (df['chain'].isin(chains)) &
            (df['volume_24h_usd'].str.replace('$', '').str.replace('K', 'e3').str.replace('M', 'e6').str.replace('B', 'e9').astype(float) >= min_volume) &
            (df['risk'].isin(risks))
        ]

    # Display table
    st.dataframe(
        filtered_df[['chain', 'name', 'symbol', 'price', 'liquidity_usd', 'volume_24h_usd', 'change_24h_pct', 'market_cap', 'risk']],
        use_container_width=True,
        column_config={
            "chain": "Chain",
            "name": "Name",
            "symbol": "Symbol",
            "price": "Price",
            "liquidity_usd": "Liquidity",
            "volume_24h_usd": "24h Volume",
            "change_24h_pct": "24h Change",
            "market_cap": "Market Cap",
            "risk": "Risk"
        }
    )

    # Expandable cards for swapping
    for i, meme in enumerate(filtered_df.to_dict('records')):
        pool_id = safe_get(meme, "pool_id", f"unknown_{i}")
        card_key = f"{category_name}_{pool_id}"
        with st.expander(f"{meme['name']} ({meme['chain']})", expanded=st.session_state.get('expanded_cards', {}).get(card_key, False)):
            st.session_state.expanded_cards[card_key] = True
            st.markdown(f"**Symbol:** {meme['symbol']} | **Price:** {meme['price']} | **Liquidity:** {meme['liquidity_usd']} | **24h Change:** {meme['change_24h_pct']}")
            st.markdown(f"[View on DexScreener]({safe_get(meme, 'url', '#')}) | [Explorer]({explorer_urls.get(meme['chain'].lower(), '#') + safe_get(meme, 'contract_address', '0x0')})")
            
            connected_wallet = get_connected_wallet(st.session_state, chain=meme['chain'].lower())
            if connected_wallet:
                selected_token = st.selectbox("Select Token to Swap", list(ERC20_TOKENS.keys()), key=f"token_{card_key}")
                amount = st.number_input("Amount", min_value=0.0, step=0.1, key=f"amount_{card_key}")
                if st.button("Swap Now", key=f"swap_{card_key}"):
                    try:
                        chain_id = CHAIN_IDS.get(meme['chain'].lower(), 1)
                        token_address = ERC20_TOKENS.get(selected_token, {}).get(meme['chain'].lower(), "0x0")
                        router_address = CONTRACT_MAP.get('uniswap', {}).get(meme['chain'].lower(), "0x0")
                        if not router_address or not token_address:
                            st.error("Invalid router or token address")
                            continue

                        approve_tx = build_erc20_approve_tx_data(
                            meme['chain'].lower(),
                            token_address,
                            router_address,
                            amount,
                            str(connected_wallet.address) if connected_wallet and connected_wallet.address else ""
                        )

                        approve_tx['chainId'] = chain_id
                        st.markdown(f"<script>performDeFiAction('approve',{json.dumps(approve_tx)});</script>", unsafe_allow_html=True)
                        time.sleep(1)
                        approve_resp = get_post_message()
                        if approve_resp.get("type") == "streamlit:txSuccess" and isinstance(approve_resp.get("txHash"), str) and approve_resp.get("txHash"):
                            st.success("Approve confirmed!")
                        else:
                            st.error("Approve failed")
                            continue

                        swap_tx = {
                            "from": connected_wallet.address,
                            "to": router_address,
                            "data": "0x",
                            "value": 0,
                            "chainId": chain_id
                        }
                        st.markdown(f"<script>performDeFiAction('swap',{json.dumps(swap_tx)});</script>", unsafe_allow_html=True)
                        time.sleep(1)
                        swap_resp = get_post_message()
                        if swap_resp.get("type") == "streamlit:txSuccess" and isinstance(swap_resp.get("txHash"), str) and swap_resp.get("txHash"):
                            if confirm_tx(meme['chain'].lower(), swap_resp['txHash']):
                                position = create_position(meme['chain'].lower(), meme['symbol'], selected_token, amount, swap_resp['txHash'])
                                add_position_to_session(st.session_state, position)
                                st.success(f"Swapped {amount} {selected_token} for {meme['symbol']}!")
                            else:
                                st.error("Swap failed")
                        else:
                            st.error("Swap failed")
                    except Exception as e:
                        logger.error(f"Swap failed for {meme['symbol']}: {e}")
                        st.error(f"Swap error: {str(e)}")
                    st.rerun()
            else:
                st.warning("Connect wallet to swap.")

# --- Render ML Table ---
def render_ml_table(opps_list, category_name: str):
    if not opps_list:
        st.warning(f"No {category_name} opportunities found.")
        return

    df = pd.DataFrame(opps_list)
    df['apy'] = df['apy'].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "0%")
    df['tvl'] = df['tvl'].apply(format_number)
    df['chain'] = df['chain'].str.capitalize()
    df['risk'] = df['risk'].fillna('Unknown')
    df['final_score'] = df['final_score'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "0.00")
    df['predicted_ror'] = df['predicted_ror'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "0.00")

    # Filtering
    with st.expander("Filter ML Results", expanded=False):
        chains = st.multiselect("Filter by Chain", options=df['chain'].unique(), default=df['chain'].unique(), key=f"filter_chain_ml_{category_name}")
        min_score = st.slider("Minimum Score", 0.0, 1.0, 0.0, key=f"min_score_{category_name}")
        filtered_df = df[
            (df['chain'].isin(chains)) &
            (df['final_score'].astype(float) >= min_score)
        ]

    st.dataframe(
        filtered_df[['chain', 'project', 'symbol', 'apy', 'tvl', 'risk', 'final_score', 'predicted_ror']],
        use_container_width=True,
        column_config={
            "chain": "Chain",
            "project": "Protocol",
            "symbol": "Token",
            "apy": "APY",
            "tvl": "TVL",
            "risk": "Risk",
            "final_score": "Score",
            "predicted_ror": "Predicted RoR"
        }
    )

# --- Render Position Table ---
def render_position_table(positions, data_map, category_name: str):
    if not positions:
        st.info(f"No {category_name} positions found.")
        return

    df = pd.DataFrame(positions)
    df['current_value'] = df.apply(lambda row: row['amount_invested'] * data_map.get(row['id'], {}).get('price', 0.0), axis=1)
    df['pnl'] = df['current_value'] - df['amount_invested']
    df['pnl_pct'] = df.apply(lambda row: (row['pnl'] / row['amount_invested'] * 100) if row['amount_invested'] > 0 else 0, axis=1)
    df['chain'] = df['chain'].str.capitalize()
    df['gas_fee'] = df['id'].apply(lambda x: data_map.get(x, {}).get('gas_fee', 0.0))

    # Filtering
    with st.expander("Filter Positions", expanded=False):
        chains = st.multiselect("Filter by Chain", options=df['chain'].unique(), default=df['chain'].unique(), key=f"filter_chain_pos_{category_name}")
        filtered_df = df[df['chain'].isin(chains)]

    # Display table
    st.dataframe(
        filtered_df[['chain', 'project', 'token_symbol', 'amount_invested', 'current_value', 'pnl', 'pnl_pct', 'gas_fee']],
        use_container_width=True,
        column_config={
            "chain": "Chain",
            "project": "Protocol",
            "token_symbol": "Token",
            "amount_invested": "Invested",
            "current_value": "Current Value",
            "pnl": "PnL ($)",
            "pnl_pct": "PnL (%)",
            "gas_fee": "Gas Fee ($)"
        }
    )

    # Expandable cards for closing positions
    if category_name == "active":
        for i, pos in enumerate(filtered_df.to_dict('records')):
            position_id = pos['id']
            with st.expander(f"{pos['project']} ({pos['chain']})", expanded=st.session_state.get('expanded_cards', {}).get(f"pos_{position_id}", False)):
                st.session_state.expanded_cards[f"pos_{position_id}"] = True
                st.markdown(f"**Token:** {pos['token_symbol']} | **Invested:** {pos['amount_invested']:.2f} | **PnL:** {pos['pnl']:.2f} ({pos['pnl_pct']:.2f}%)")
                st.markdown(f"[View Transaction]({explorer_urls.get(pos['chain'].lower(), '#') + pos['tx_hash']})")
                
                connected_wallet = get_connected_wallet(st.session_state, chain=pos['chain'].lower())
                if connected_wallet and st.button("Close Position", key=f"close_{position_id}"):
                    try:
                        protocol = pos['project'].lower()
                        chain_id = CHAIN_IDS.get(pos['chain'].lower(), 1)
                        pool_address = CONTRACT_MAP.get(protocol, {}).get(pos['chain'].lower(), "0x0")
                        token_address = ERC20_TOKENS.get(pos['token_symbol'], {}).get(pos['chain'].lower(), "0x0")
                        amount = pos['amount_invested']
                        if not pool_address or not token_address:
                            st.error("Invalid pool or token address")
                            continue

                        if not connected_wallet or not connected_wallet.address:
                            st.error("No connected wallet. Please connect your wallet first.")
                            continue

                        if 'aave' in protocol:
                            withdraw_tx = build_aave_withdraw_tx_data(
                                pos['chain'].lower(),
                                pool_address,
                                token_address,
                                amount,
                                str(connected_wallet.address)
                            )
                        elif 'compound' in protocol:
                            withdraw_tx = build_compound_withdraw_tx_data(
                                pos['chain'].lower(),
                                pool_address,
                                token_address,
                                amount,
                                str(connected_wallet.address)
                            )
                        else:
                            st.error(f"Unsupported protocol: {protocol}")
                            continue


                        withdraw_tx['chainId'] = chain_id
                        st.markdown(f"<script>performDeFiAction('withdraw',{json.dumps(withdraw_tx)});</script>", unsafe_allow_html=True)
                        time.sleep(1)
                        response = get_post_message()
                        if response.get("type") == "streamlit:txSuccess" and isinstance(response.get("txHash"), str) and response.get("txHash"):
                            if confirm_tx(pos['chain'].lower(), response['txHash']):
                                close_position(st.session_state, position_id, response['txHash'])
                                st.success(f"Closed position for {amount} {pos['token_symbol']} in {pos['project']}!")
                            else:
                                st.error("Withdraw transaction failed")
                        else:
                            st.error("Withdraw transaction failed")
                    except Exception as e:
                        logger.error(f"Failed to close position {position_id}: {e}")
                        st.error(f"Failed to close position: {str(e)}")
                    st.rerun()

# --- Render Wallets ---
def render_wallets():
    if 'wallets' not in st.session_state:
        init_wallets(st.session_state)

    st.markdown(
        """
        <style>
            .card { background: #1e1e2f; border-radius: 12px; padding: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            .connect-button { background: linear-gradient(to right, #6366f1, #3b82f6); border: none; padding: 12px 24px; border-radius: 10px; color: white; font-size: 16px; cursor: pointer; }
            .text-green-400 { color: #10B981; }
            .text-red-400 { color: #EF4444; }
        </style>
        <script src="https://unpkg.com/@walletconnect/modal@2.6.2/dist/index.umd.js"></script>
        <script src="https://cdn.ethers.io/lib/ethers-5.7.umd.min.js"></script>
        <button id="connectButton" class="connect-button">🔗 Connect Wallet</button>
        <script>
            const modal = new window.WalletConnectModal.default({
                projectId: 'bbfc8335f232745db239ec392b6a9d4a',
                chains: ['eip155:1', 'eip155:56', 'eip155:42161', 'eip155:10', 'eip155:8453', 'eip155:43114', 'eip155:245022926'],
            });
            async function connectWallet() {
                if (window.ethereum) {
                    try {
                        const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                        window.lastMessage = { type: 'streamlit:connect', account: accounts[0], chainId: await window.ethereum.request({ method: 'eth_chainId' }) };
                    } catch (e) {
                        window.lastMessage = { type: 'streamlit:error', message: e.message };
                    }
                } else {
                    try {
                        const uri = await modal.openModal();
                        modal.on('connect', (result) => {
                            window.lastMessage = { type: 'streamlit:connect', account: result.accounts[0], chainId: result.chainId };
                        });
                    } catch (e) {
                        window.lastMessage = { type: 'streamlit:error', message: e.message };
                    }
                }
            }
            document.getElementById('connectButton').addEventListener('click', connectWallet);
        </script>
        """,
        unsafe_allow_html=True,
    )

    tab_connected, tab_disconnected = st.tabs(["🟢 Connected Wallets", "🔴 Disconnected Wallets"])

    with tab_connected:
        connected_wallets = [w for w in st.session_state.wallets.values() if w.connected]
        if not connected_wallets:
            st.info("No connected wallets.")
        else:
            for wallet in connected_wallets:
                chain = wallet.chain
                logo_url = NETWORK_LOGOS.get(chain, "https://via.placeholder.com/32?text=Logo")
                chain_name = chain.capitalize()
                address = wallet.address
                address_display = (address[:6] + "..." + address[-4:]) if address else "Not connected"
                balance = wallet.get_balance() if hasattr(wallet, 'get_balance') else 0.0
                balance_display = f"{balance:.2f} {chain.upper()}"

                st.markdown(
                    f"""
                    <div class="card">
                        <div style="display:flex; align-items:center; margin-bottom:0.75rem;">
                            <img src="{logo_url}" alt="{chain_name}" style="width:32px; height:32px; border-radius:50%; margin-right:0.6rem;">
                            <h3 style="margin:0; font-size:1rem; font-weight:600; color:#c7d2fe;">{chain_name}</h3>
                        </div>
                        <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">Status: <span class="text-green-400">✅ Connected</span></p>
                        <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">Address: {address_display}</p>
                        <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">Balance: {balance_display}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Disconnect", key=f"disconnect_{chain}"):
                    wallet.disconnect()
                    st.rerun()

    with tab_disconnected:
        disconnected_wallets = [w for w in st.session_state.wallets.values() if not w.connected]
        if not disconnected_wallets:
            st.info("No disconnected wallets.")
        else:
            for wallet in disconnected_wallets:
                chain = wallet.chain
                logo_url = NETWORK_LOGOS.get(chain, "https://via.placeholder.com/32?text=Logo")
                chain_name = chain.capitalize()
                address = wallet.address
                address_display = (address[:6] + "..." + address[-4:]) if address else "Not connected"

                st.markdown(
                    f"""
                    <div class="card">
                        <div style="display:flex; align-items:center; margin-bottom:0.75rem;">
                            <img src="{logo_url}" alt="{chain_name}" style="width:32px; height:32px; border-radius:50%; margin-right:0.6rem;">
                            <h3 style="margin:0; font-size:1rem; font-weight:600; color:#c7d2fe;">{chain_name}</h3>
                        </div>
                        <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">Status: <span class="text-red-400">❌ Disconnected</span></p>
                        <p style="color:#e0e7ff; font-size:0.9rem; margin-bottom:0.25rem;">Address: {address_display}</p>
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

# --- Main Render Function ---
def render():
    st.markdown(
        """
        <style>
            .header { background: linear-gradient(135deg, #1e1e2f, #312e81); padding: 2rem; border-radius: 12px; text-align: center; }
            .header h1 { color: #c7d2fe; font-size: 2.5rem; font-weight: bold; }
            .header p { color: #e0e7ff; font-size: 1rem; }
        </style>
        <div class="header">
            <h1>🌟 DeFiVaultPro Dashboard</h1>
            <p>Explore top DeFi opportunities, track your positions, and manage wallets with ease.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    if 'wallets' not in st.session_state:
        init_wallets(st.session_state)
    if 'positions' not in st.session_state:
        st.session_state.positions = db.get_positions()
    if 'expanded_cards' not in st.session_state:
        st.session_state.expanded_cards = {}

    tab_opportunities, tab_positions, tab_wallets = st.tabs(["🌐 Opportunities", "📊 My Positions", "👛 Wallets"])

    with tab_opportunities:
        sub_tab1, sub_tab2, sub_tab3, sub_tab4, sub_tab5 = st.tabs(
            ["🏆 Top Picks", "⚡ Short-Term", "🏛 Long-Term", "🚀 Layer 2", "🐸 Meme Coins"]
        )

        with sub_tab1:
            st.markdown("### Curated DeFi Opportunities")
            st.write("Balanced risk-reward opportunities enhanced by ML insights.")
            if st.button("Run ML Analysis", key="ml_analysis"):
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
                data = {"yields": [], "memes": []}

            st.subheader("🏆 ML-Enhanced Yields")
            render_ml_table(data.get("yields", []), "ml_yields")
            st.subheader("🐸 ML-Enhanced Meme Coins")
            render_ml_table(data.get("memes", []), "ml_memes")

            @st.cache_data(ttl=300)
            def cached_top_picks():
                return db.get_opportunities(limit=100)
            with st.spinner("🔍 Scanning for top DeFi opportunities..."):
                top_picks = cached_top_picks()
                render_opportunity_table(top_picks, "top_picks")

            st.markdown(
                """
                <div class="card" style="background: linear-gradient(to right, #1e40af, #312e81); padding: 1rem; margin-top: 1rem;">
                    <h3 style="color: #c7d2fe;">💡 Selection Criteria</h3>
                    <p style="color: #e0e7ff;">Top picks are curated for high APY, moderate risk, and strong liquidity (TVL).</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with sub_tab2:
            @st.cache_data(ttl=300)
            def cached_short_term():
                all_opps = db.get_opportunities(limit=100)
                return [opp for opp in all_opps if safe_get(opp, 'apy', 0) > 20]
            with st.spinner("🔍 Scanning for short-term DeFi opportunities..."):
                short_term_opps = cached_short_term()
                render_opportunity_table(short_term_opps, "short_term")
            st.markdown(
                """
                <div class="card" style="background: linear-gradient(to right, #7f1d1d, #991b1b); padding: 1rem; margin-top: 1rem;">
                    <h3 style="color: #fecaca;">⚠️ Risk Warning</h3>
                    <p style="color: #e0e7ff;">Short-term opportunities have higher risk due to high APY. Research thoroughly.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with sub_tab3:
            @st.cache_data(ttl=300)
            def cached_long_term():
                all_opps = db.get_opportunities(limit=100)
                return [opp for opp in all_opps if safe_get(opp, 'risk', 'Unknown') == 'Low' or safe_get(opp, 'tvl', 0) > 1_000_000]
            with st.spinner("🔍 Scanning for long-term DeFi opportunities..."):
                long_term_opps = cached_long_term()
                render_opportunity_table(long_term_opps, "long_term")
            st.markdown(
                """
                <div class="card" style="background: linear-gradient(to right, #065f46, #047857); padding: 1rem; margin-top: 1rem;">
                    <h3 style="color: #6ee7b7;">💡 Selection Criteria</h3>
                    <p style="color: #e0e7ff;">Long-term opportunities prioritize stability, low risk, and high liquidity (TVL).</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with sub_tab4:
            SUPPORTED_CHAINS = ["ethereum", "bsc", "solana", "arbitrum", "optimism", "base", "avalanche", "neon"]
            LAYER2_CHAINS = ["arbitrum", "optimism", "base"]
            selected_chains = st.multiselect(
                "Select Chains",
                SUPPORTED_CHAINS,
                default=LAYER2_CHAINS,
                format_func=lambda x: f"⚡ {x.capitalize()}" if x in LAYER2_CHAINS else x.capitalize(),
                key="layer2_chains"
            )
            @st.cache_data(ttl=300)
            def cached_layer2_opps():
                all_opps = db.get_opportunities(limit=100)
                return [o for o in all_opps if safe_get(o, 'chain', 'unknown').lower() in LAYER2_CHAINS]
            with st.spinner("🔍 Scanning for Layer 2 opportunities..."):
                layer2_opps = cached_layer2_opps()
                layer2_opps = [o for o in layer2_opps if safe_get(o, 'chain', 'unknown').lower() in selected_chains]
                render_opportunity_table(layer2_opps, "layer2_focus")

        with sub_tab5:
            @st.cache_data(ttl=300)
            def cached_meme_coins():
                return db.get_meme_opportunities(limit=100)
            with st.spinner("🔍 Scanning for trending meme coins..."):
                meme_coins = cached_meme_coins()
                render_meme_table(meme_coins, "meme_coins")
            st.markdown(
                """
                <div class="card" style="background: linear-gradient(to right, #854d0e, #a16207); padding: 1rem; margin-top: 1rem;">
                    <h3 style="color: #fef08a;">⚠️ Risk Warning</h3>
                    <p style="color: #e0e7ff;">Meme coins are highly speculative and volatile. Invest only what you can afford to lose.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with tab_positions:
        active_positions = [p for p in st.session_state.positions if safe_get(p, "status", "") == "active"]
        closed_positions = [p for p in st.session_state.positions if safe_get(p, "status", "") == "closed"]
        data_map = {}
        for pos in active_positions + closed_positions:
            position_id = safe_get(pos, "id", f"unknown_{pos.get('chain', 'unknown')}")
            try:
                price = get_token_price(safe_get(pos, "token_symbol", "Unknown"))
                gas_fee = 0.01  # Placeholder; assume wallet_utils provides accurate gas estimation
                data_map[position_id] = {"price": price, "gas_fee": gas_fee}
            except Exception as e:
                logger.warning(f"Failed to fetch price/gas for {position_id}: {e}")
                data_map[position_id] = {"price": 0.0, "gas_fee": 0.0}

        total_invested = sum(safe_get(pos, "amount_invested", 0) for pos in active_positions)
        total_current_value = sum(
            safe_get(pos, "amount_invested", 0) * data_map.get(safe_get(pos, "id", ""), {}).get("price", 0.0)
            for pos in active_positions
        )
        total_pnl = total_current_value - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

        st.markdown(
            f"""
            <div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:1.5rem;'>
                <div class="card" style="background: linear-gradient(to right, #1e40af, #312e81);">
                    <h4 style="color: #93c5fd; font-size: 0.9rem;">Total Invested</h4>
                    <p style="color: #f8fafc; font-size: 1.2rem; font-weight: bold;">${total_invested:.2f}</p>
                </div>
                <div class="card" style="background: linear-gradient(to right, #065f46, #047857);">
                    <h4 style="color: #6ee7b7; font-size: 0.9rem;">Current Value</h4>
                    <p style="color: #f8fafc; font-size: 1.2rem; font-weight: bold;">${total_current_value:.2f}</p>
                </div>
                <div class="card" style="background: linear-gradient(to right, #5b21b6, #6d28d9);">
                    <h4 style="color: #c4b5fd; font-size: 0.9rem;">Total PnL</h4>
                    <p style="color: {'#10B981' if total_pnl>=0 else '#EF4444'}; font-size: 1.2rem; font-weight: bold;">${total_pnl:.2f} ({total_pnl_pct:.2f}%)</p>
                </div>
                <div class="card" style="background: linear-gradient(to right, #4b5563, #6b7280);">
                    <h4 style="color: #d1d5db; font-size: 0.9rem;">Active Positions</h4>
                    <p style="color: #f8fafc; font-size: 1.2rem; font-weight: bold;">{len(active_positions)}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        pos_tab1, pos_tab2 = st.tabs(["🟢 Active Positions", "🔴 Closed Positions"])
        with pos_tab1:
            render_position_table(active_positions, data_map, "active")
        with pos_tab2:
            render_position_table(closed_positions, data_map, "closed")

    with tab_wallets:
        render_wallets()

if __name__ == "__main__":
    render()