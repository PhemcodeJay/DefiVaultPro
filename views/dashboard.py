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

# --- Placeholder Withdraw Functions ---
def build_aave_withdraw_tx_data(chain: str, pool_address: str, token_address: str, amount: float, wallet_address: str) -> dict:
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

def get_post_message():
    return st_javascript("return window.lastMessage || {}")

# --- Render Opportunity Table ---
def render_opportunity_table(opps_list, category_name: str, allow_invest=True):
    if not opps_list:
        st.warning(f"No {category_name.replace('_', ' ').title()} opportunities found.")
        return

    # Validate and clean data
    cleaned_opps = []
    for opp in opps_list:
        try:
            chain = safe_get(opp, 'chain', 'unknown')
            project = safe_get(opp, 'project', 'Unknown')
            symbol = safe_get(opp, 'symbol', 'Unknown')
            risk = safe_get(opp, 'risk', 'Unknown')
            # Ensure string fields are strings
            if not all(isinstance(x, str) for x in [chain, project, symbol, risk]):
                logger.warning(f"Skipping opportunity with invalid string fields: {opp}")
                continue
            # Ensure numeric fields are valid
            apy = float(safe_get(opp, 'apy', 0.0))
            tvl = float(safe_get(opp, 'tvl', 0.0))
            if apy < 0 or tvl < 0:
                logger.warning(f"Skipping opportunity with negative apy/tvl: {opp}")
                continue

            cleaned_opps.append({
                'chain': chain.capitalize(),
                'project': project,
                'symbol': symbol,
                'apy': apy,
                'tvl': tvl,
                'risk': risk,
                'type': safe_get(opp, 'type', 'Unknown'),
                'contract_address': safe_get(opp, 'contract_address', '0x0'),
                'link': safe_get(opp, 'link', '#'),
                'pool_id': safe_get(opp, 'pool_id', f"unknown_{len(cleaned_opps)}")
            })
        except Exception as e:
            logger.warning(f"Skipping invalid opportunity {safe_get(opp, 'project', 'unknown')}: {e}")
            continue

    if not cleaned_opps:
        st.warning(f"No valid {category_name.replace('_', ' ').title()} opportunities found after validation.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(cleaned_opps)
    df['apy_str'] = df['apy'].apply(lambda x: f"{x:.2f}%" if x is not None else "0%")
    df['tvl_str'] = df['tvl'].apply(format_number)

    # Filtering
    with st.expander("Filter Opportunities", expanded=False):
        chains = st.multiselect("Filter by Chain", options=df['chain'].unique(), default=df['chain'].unique(), key=f"filter_chain_{category_name}")
        min_apy = st.slider("Minimum APY (%)", 0.0, 100.0, 0.0, key=f"min_apy_{category_name}")
        risks = st.multiselect("Filter by Risk", options=df['risk'].unique(), default=df['risk'].unique(), key=f"filter_risk_{category_name}")
        
        filtered_df = df[
            (df['chain'].isin(chains)) &
            (df['apy'] >= min_apy) &
            (df['risk'].isin(risks))
        ]

    # Display table
    st.dataframe(
        filtered_df[['chain', 'project', 'symbol', 'apy_str', 'tvl_str', 'risk', 'type']],
        use_container_width=True,
        column_config={
            "chain": "Chain",
            "project": "Protocol",
            "symbol": "Token",
            "apy_str": "APY",
            "tvl_str": "TVL",
            "risk": "Risk",
            "type": "Type"
        }
    )

    # Expandable cards for investment
    if allow_invest:
        for i, opp in enumerate(filtered_df.to_dict('records')):
            pool_id = opp['pool_id']
            card_key = f"{category_name}_{pool_id}"
            with st.expander(f"{opp['project']} ({opp['chain']})", expanded=st.session_state.get('expanded_cards', {}).get(card_key, False)):
                st.session_state.setdefault('expanded_cards', {})[card_key] = True
                st.markdown(f"**Symbol:** {opp['symbol']} | **APY:** {opp['apy_str']} | **TVL:** {opp['tvl_str']} | **Risk:** {opp['risk']}")
                st.markdown(f"[View on DeFiLlama]({opp['link']}) | [Explorer]({explorer_urls.get(opp['chain'].lower(), '#') + opp['contract_address']})")
                
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
                                    str(connected_wallet.address)
                                )
                                approve_tx['chainId'] = chain_id

                                st.markdown(
                                    f"<script>performDeFiAction('approve',{json.dumps(approve_tx)});</script>",
                                    unsafe_allow_html=True
                                )
                            except Exception as e:
                                logger.error(f"Failed to initiate investment for {opp['project']}: {e}")
                                st.error(f"Failed to initiate investment: {str(e)}")
                    else:
                        st.warning("Please connect a wallet to invest.")

# --- Render Meme Table ---
def render_meme_table(meme_list, category_name: str):
    if not meme_list:
        st.warning(f"No {category_name.replace('_', ' ').title()} found.")
        return

    # Validate and clean meme data
    cleaned_memes = []
    for meme in meme_list:
        try:
            chain = safe_get(meme, 'chain', 'unknown')
            project = safe_get(meme, 'project', 'Unknown')
            name = safe_get(meme, 'name', 'Unknown')
            symbol = safe_get(meme, 'symbol', 'Unknown')
            risk = safe_get(meme, 'risk', 'Unknown')
            if not all(isinstance(x, str) for x in [chain, project, name, symbol, risk]):
                logger.warning(f"Skipping meme with invalid string fields: {meme}")
                continue
            market_cap = float(safe_get(meme, 'market_cap', 0.0))
            if market_cap < 0:
                logger.warning(f"Skipping meme with negative market_cap: {meme}")
                continue

            cleaned_memes.append({
                'chain': chain.capitalize(),
                'project': project,
                'name': name,
                'symbol': symbol,
                'price': safe_get(meme, 'price', 0.0),
                'market_cap': market_cap,
                'risk': risk,
                'growth_potential': safe_get(meme, 'growth_potential', 0.0)
            })
        except Exception as e:
            logger.warning(f"Skipping invalid meme {safe_get(meme, 'project', 'unknown')}: {e}")
            continue

    if not cleaned_memes:
        st.warning(f"No valid {category_name.replace('_', ' ').title()} found after validation.")
        return

    df = pd.DataFrame(cleaned_memes)
    df['market_cap'] = df['market_cap'].apply(format_number)

    st.dataframe(
        df[['chain', 'project', 'name', 'symbol', 'price', 'market_cap', 'risk', 'growth_potential']],
        use_container_width=True,
        column_config={
            "chain": "Chain",
            "project": "DEX",
            "name": "Name",
            "symbol": "Symbol",
            "price": "Price",
            "market_cap": "Market Cap",
            "risk": "Risk",
            "growth_potential": "24h Change"
        }
    )

# --- Render Position Table ---
def render_position_table(positions, data_map, category_name: str):
    if not positions:
        st.info(f"No {category_name} positions found.")
        return

    cleaned_positions = []
    for pos in positions:
        try:
            chain = safe_get(pos, 'chain', 'unknown')
            opportunity_name = safe_get(pos, 'opportunity_name', 'Unknown')
            token_symbol = safe_get(pos, 'token_symbol', 'Unknown')
            protocol = safe_get(pos, 'protocol', 'Unknown')
            if not all(isinstance(x, str) for x in [chain, opportunity_name, token_symbol, protocol]):
                logger.warning(f"Skipping position with invalid string fields: {pos}")
                continue
            amount_invested = float(safe_get(pos, 'amount_invested', 0.0))
            apy = float(safe_get(pos, 'apy', 0.0)) if safe_get(pos, 'apy', None) is not None else None
            if amount_invested < 0:
                logger.warning(f"Skipping position with negative amount_invested: {pos}")
                continue

            cleaned_positions.append({
                'chain': chain.capitalize(),
                'opportunity_name': opportunity_name,
                'token_symbol': token_symbol,
                'amount_invested': amount_invested,
                'apy': apy,
                'protocol': protocol,
                'id': safe_get(pos, 'id', f"unknown_{len(cleaned_positions)}"),
                'status': safe_get(pos, 'status', 'unknown')
            })
        except Exception as e:
            logger.warning(f"Skipping invalid position {safe_get(pos, 'id', 'unknown')}: {e}")
            continue

    if not cleaned_positions:
        st.info(f"No valid {category_name} positions found after validation.")
        return

    df = pd.DataFrame(cleaned_positions)
    df['current_value'] = df.apply(
        lambda row: format_number(
            row['amount_invested'] * data_map.get(row['id'], {}).get('price', 0.0)
        ), axis=1
    )
    df['apy'] = df['apy'].apply(lambda x: f"{x:.2f}%" if x is not None else "N/A")
    df['amount_invested'] = df['amount_invested'].apply(format_number)

    st.dataframe(
        df[['chain', 'opportunity_name', 'token_symbol', 'amount_invested', 'current_value', 'apy', 'protocol']],
        use_container_width=True,
        column_config={
            "chain": "Chain",
            "opportunity_name": "Opportunity",
            "token_symbol": "Token",
            "amount_invested": "Invested",
            "current_value": "Current Value",
            "apy": "APY",
            "protocol": "Protocol"
        }
    )

    for pos in cleaned_positions:
        position_id = pos['id']
        with st.expander(f"{pos['opportunity_name']} ({pos['chain']})"):
            st.markdown(f"**Token:** {pos['token_symbol']} | **Invested:** {format_number(pos['amount_invested'])} | **APY:** {pos['apy']}")
            if pos['status'] == 'active':
                amount = st.number_input("Amount to Withdraw", min_value=0.0, step=0.1, key=f"withdraw_amount_{position_id}")
                if st.button("Withdraw", key=f"withdraw_{position_id}"):
                    try:
                        chain = pos['chain'].lower()
                        protocol = pos['protocol'].lower()
                        pool_address = CONTRACT_MAP.get(protocol, {}).get(chain, "0x0")
                        token_address = ERC20_TOKENS.get(pos['token_symbol'], {}).get(chain, "0x0")
                        wallet_address = safe_get(pos, 'wallet_address', '')

                        if not pool_address or not token_address:
                            st.error("Invalid pool or token address")
                            continue

                        if protocol == 'aave':
                            withdraw_tx = build_aave_withdraw_tx_data(chain, pool_address, token_address, amount, wallet_address)
                        elif protocol == 'compound':
                            withdraw_tx = build_compound_withdraw_tx_data(chain, pool_address, token_address, amount, wallet_address)
                        else:
                            st.error(f"Unsupported protocol: {protocol}")
                            continue

                        withdraw_tx['chainId'] = CHAIN_IDS.get(chain, 1)
                        st.markdown(
                            f"<script>performDeFiAction('withdraw',{json.dumps(withdraw_tx)});</script>",
                            unsafe_allow_html=True
                        )
                    except Exception as e:
                        logger.error(f"Failed to initiate withdrawal for {position_id}: {e}")
                        st.error(f"Failed to initiate withdrawal: {str(e)}")

# --- Render Wallets ---
def render_wallets():
    wallets = st.session_state.get('wallets', [])
    if not wallets:
        st.info("No wallets connected.")
        return

    for wallet in wallets:
        chain = safe_get(wallet, 'chain', 'unknown')
        if not isinstance(chain, str):
            chain = 'unknown'
        address = safe_get(wallet, 'address', '0x0')
        balance = float(safe_get(wallet, 'balance', 0.0))
        connected = safe_get(wallet, 'connected', False)
        logo = NETWORK_LOGOS.get(chain.lower(), '')
        status = "Connected" if connected else "Disconnected"

        st.markdown(
            f"""
            <div class="card">
                <img src="{logo}" width="24" style="vertical-align: middle; margin-right: 8px;">
                <span style="font-weight: bold;">{chain.capitalize()}</span> | {address[:6]}...{address[-4:]} | {format_number(balance)} | {status}
                {'<button onclick="connectWallet()">Reconnect</button>' if not connected else ''}
            </div>
            """,
            unsafe_allow_html=True
        )

# --- Main Render Function ---
def render():
    if 'expanded_cards' not in st.session_state:
        st.session_state.expanded_cards = {}

    tab_yields, tab_positions, tab_wallets = st.tabs(["📈 Yield Opportunities", "💼 My Positions", "👛 Wallets"])

    with tab_yields:
        sub_tab1, sub_tab2, sub_tab3, sub_tab4, sub_tab5 = st.tabs([
            "🏆 Top Picks",
            "⚡ Short Term",
            "🏦 Long Term",
            "🚀 Layer 2",
            "🐸 Meme Coins"
        ])

        with sub_tab1:
            with st.spinner("🔍 Scanning for top DeFi opportunities..."):
                top_picks = db.get_opportunities(limit=100)
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
            with st.spinner("🔍 Scanning for short-term DeFi opportunities..."):
                all_opps = db.get_opportunities(limit=100)
                short_term_opps = [opp for opp in all_opps if float(safe_get(opp, 'apy', 0.0)) > 20]
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
            with st.spinner("🔍 Scanning for long-term DeFi opportunities..."):
                all_opps = db.get_opportunities(limit=100)
                long_term_opps = [opp for opp in all_opps if safe_get(opp, 'risk', 'Unknown') == 'Low' or float(safe_get(opp, 'tvl', 0.0)) > 1_000_000]
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
            with st.spinner("🔍 Scanning for Layer 2 opportunities..."):
                all_opps = db.get_opportunities(limit=100)
                layer2_opps = [opp for opp in all_opps if safe_get(opp, 'chain', 'unknown').lower() in selected_chains]
                render_opportunity_table(layer2_opps, "layer2_focus")

        with sub_tab5:
            with st.spinner("🔍 Scanning for trending meme coins..."):
                meme_coins = db.get_meme_opportunities(limit=100)
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
        active_positions = [p for p in st.session_state.get('positions', []) if safe_get(p, "status", "") == "active"]
        closed_positions = [p for p in st.session_state.get('positions', []) if safe_get(p, "status", "") == "closed"]
        data_map = {}
        for pos in active_positions + closed_positions:
            position_id = safe_get(pos, "id", f"unknown_{pos.get('chain', 'unknown')}")
            try:
                token_symbol = safe_get(pos, "token_symbol", "Unknown")
                if not isinstance(token_symbol, str):
                    token_symbol = "Unknown"
                price = get_token_price(token_symbol)
                gas_fee = 0.01  # Placeholder; assume wallet_utils provides accurate gas estimation
                data_map[position_id] = {"price": price, "gas_fee": gas_fee}
            except Exception as e:
                logger.warning(f"Failed to fetch price/gas for {position_id}: {e}")
                data_map[position_id] = {"price": 0.0, "gas_fee": 0.0}

        total_invested = sum(float(safe_get(pos, "amount_invested", 0.0)) for pos in active_positions)
        total_current_value = sum(
            float(safe_get(pos, "amount_invested", 0.0)) * data_map.get(safe_get(pos, "id", ""), {}).get("price", 0.0)
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