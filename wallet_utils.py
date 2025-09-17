import streamlit as st
from dataclasses import dataclass
from typing import List, Optional
from web3 import Web3
from web3.types import TxParams
from datetime import datetime
import requests
from dotenv import load_dotenv
import os
import db
import logging
from hexbytes import HexBytes
from utils import connect_to_chain

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    filename="app.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

load_dotenv()

# Network configurations
NETWORK_NAMES = {
    "ethereum": "Ethereum",
    "bsc": "BSC",
    "arbitrum": "Arbitrum",
    "optimism": "Optimism",
    "base": "Base",
    "avalanche": "Avalanche",
    "neon": "Neon EVM"
}

NETWORK_LOGOS = {
    "ethereum": "https://cryptologos.cc/logos/ethereum-eth-logo.svg",
    "bsc": "https://cryptologos.cc/logos/bnb-bnb-logo.svg",
    "arbitrum": "https://cryptologos.cc/logos/arbitrum-arb-logo.svg",
    "optimism": "https://cryptologos.cc/logos/optimism-ethereum-op-logo.svg",
    "base": "https://avatars.githubusercontent.com/u/108554348?s=280&v=4",
    "avalanche": "https://cryptologos.cc/logos/avalanche-avax-logo.svg",
    "neon": "https://pbs.twimg.com/profile_images/1578773001968402434/Yr8tVNbl_400x400.jpg",
    "polygon": "https://cryptologos.cc/logos/polygon-matic-logo.svg",
    "fantom": "https://cryptologos.cc/logos/fantom-ftm-logo.svg",
    "solana": "https://cryptologos.cc/logos/solana-sol-logo.svg",
    "aurora": "https://s2.coinmarketcap.com/static/img/coins/64x64/14803.png",
    "cronos": "https://cryptologos.cc/logos/crypto-com-coin-cro-logo.svg"
}

PROTOCOL_LOGOS = {
    "uniswap": "https://cryptologos.cc/logos/uniswap-uni-logo.svg",
    "sushiswap": "https://cryptologos.cc/logos/sushiswap-sushi-logo.svg",
    "pancakeswap": "https://cryptologos.cc/logos/pancakeswap-cake-logo.svg",
    "balancer": "https://cryptologos.cc/logos/balancer-bal-logo.svg",
    "curve": "https://cryptologos.cc/logos/curve-dao-token-crv-logo.svg",
    "aave": "https://cryptologos.cc/logos/aave-aave-logo.svg",
    "compound": "https://cryptologos.cc/logos/compound-comp-logo.svg",
    "yearn": "https://cryptologos.cc/logos/yearn-finance-yfi-logo.svg",
    "convex": "https://s2.coinmarketcap.com/static/img/coins/64x64/9903.png",
    "beefy": "https://s2.coinmarketcap.com/static/img/coins/64x64/7311.png",
    "lido": "https://cryptologos.cc/logos/lido-dao-ldo-logo.svg",
    "rocket pool": "https://s2.coinmarketcap.com/static/img/coins/64x64/8966.png",
    "stargate": "https://s2.coinmarketcap.com/static/img/coins/64x64/18934.png",
    "trader joe": "https://s2.coinmarketcap.com/static/img/coins/64x64/11396.png",
    "gmx": "https://s2.coinmarketcap.com/static/img/coins/64x64/11857.png",
    "radiant": "https://s2.coinmarketcap.com/static/img/coins/64x64/21574.png"
}

CHAIN_IDS = {
    "ethereum": 1,
    "bsc": 56,
    "arbitrum": 42161,
    "optimism": 10,
    "base": 8453,
    "avalanche": 43114,
    "neon": 245022934
}

BALANCE_SYMBOLS = {
    "ethereum": "ETH",
    "bsc": "BNB",
    "arbitrum": "ETH",
    "optimism": "ETH",
    "base": "ETH",
    "avalanche": "AVAX",
    "neon": "NEON"
}

ERC20_TOKENS = {
    "ethereum": {
        "USDC": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "USDT": "0xdac17f958d2ee523a2206206994597c13d831ec7",
        "DAI": "0x6b175474e89094c44da98b954eedeac495271d0f"
    },
    "arbitrum": {
        "USDC": "0xaf88d065e77c8cc2239327c5edb3a432268e5831",
        "USDT": "0xfd086bc7cd5c481dcc9c85ebe478a1c0b99fc7a1",
        "DAI": "0xda10009cbd5d07dd0cecc66161fc93d7bf3513e0"
    }
}

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
     "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True,
     "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}
]

AAVE_POOL_ABI = [
    {"inputs": [{"internalType": "address", "name": "asset", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"},
                {"internalType": "address", "name": "onBehalfOf", "type": "address"},
                {"internalType": "uint16", "name": "referralCode", "type": "uint16"}],
     "name": "supply", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "asset", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"},
                {"internalType": "address", "name": "to", "type": "address"}],
     "name": "withdraw", "outputs": [], "stateMutability": "nonpayable", "type": "function"}
]

COMPOUND_COMET_ABI = [
    {"inputs": [{"internalType": "address", "name": "asset", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"}],
     "name": "supply", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "asset", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"}],
     "name": "withdraw", "outputs": [], "stateMutability": "nonpayable", "type": "function"}
]

CONTRACT_MAP = {
    "aave": {
        "ethereum": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4e2",  # Aave V3 Pool
        "arbitrum": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        "optimism": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        "base": "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
    },
    "compound": {
        "ethereum": "0xc3d688B66703497DAA19211EEdff47f25384cdc3",  # USDC Comet
        "arbitrum": "0xA5EDBDD9646f8dFF606d7448e414884C7d905cCA",
        "base": "0x9c4ec768c28520B50860F7e1e1c5793dC7E70C57"
    }
}

explorer_urls = {
    "ethereum": "https://etherscan.io/tx/",
    "bsc": "https://bscscan.com/tx/",
    "arbitrum": "https://arbiscan.io/tx/",
    "optimism": "https://optimistic.etherscan.io/tx/",
    "base": "https://basescan.org/tx/",
    "avalanche": "https://snowtrace.io/tx/",
    "neon": "https://neonscan.org/tx/"
}


@dataclass
class Wallet:
    chain: str
    address: Optional[str] = None
    connected: bool = False
    verified: bool = False
    balance: float = 0.0
    nonce: Optional[int] = None

    def connect(self, address: str):
        self.address = Web3.to_checksum_address(address)
        self.connected = True
        self.update_balance()
        self.update_nonce()

    def disconnect(self):
        self.address = None
        self.connected = False
        self.verified = False
        self.balance = 0.0
        self.nonce = None

    def update_balance(self):
        w3 = self._get_web3_connection()
        if w3 and self.address:
            try:
                checksum_address = Web3.to_checksum_address(self.address)
                if self.chain in ERC20_TOKENS:
                    token_address = ERC20_TOKENS[self.chain].get("USDC", None)
                    if token_address:
                        token_contract = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
                        self.balance = float(w3.from_wei(
                            token_contract.functions.balanceOf(checksum_address).call(),
                            'ether'
                        ))
                    else:
                        self.balance = float(w3.from_wei(w3.eth.get_balance(checksum_address), 'ether'))
                else:
                    self.balance = float(w3.from_wei(w3.eth.get_balance(checksum_address), 'ether'))
            except Exception as e:
                logger.error(f"Failed to update balance for {self.address}: {e}")
                self.balance = 0.0

    def update_nonce(self):
        w3 = self._get_web3_connection()
        if w3 and self.address:
            try:
                self.nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(self.address))
            except Exception as e:
                logger.error(f"Failed to update nonce for {self.address}: {e}")
                self.nonce = None

    def _get_web3_connection(self) -> Optional[Web3]:
        rpc_urls = {
            "ethereum": os.getenv("ETH_RPC_URL", "https://mainnet.infura.io/v3/YOUR_INFURA_KEY"),
            "bsc": os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/"),
            "arbitrum": os.getenv("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc"),
            "optimism": os.getenv("OPTIMISM_RPC_URL", "https://mainnet.optimism.io"),
            "base": os.getenv("BASE_RPC_URL", "https://mainnet.base.org"),
            "avalanche": os.getenv("AVALANCHE_RPC_URL", "https://api.avax.network/ext/bc/C/rpc"),
            "neon": os.getenv("NEON_RPC_URL", "https://mainnet.neonlabs.org"),
        }
        rpc_url = rpc_urls.get(self.chain)
        if rpc_url:
            return Web3(Web3.HTTPProvider(rpc_url))
        return None


@dataclass
class Position:
    id: str
    chain: str
    opportunity_name: str
    token_symbol: str
    amount_invested: float
    current_value: float
    entry_date: datetime
    tx_hash: str
    status: str = "active"


def build_approve_tx_data(chain: str, token_address: str, spender: str, amount: float, user_address: str) -> TxParams:
    w3 = connect_to_chain(chain)
    if not w3:
        raise ValueError(f"No Web3 connection for chain {chain}")
    token_contract = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
    amount_wei = w3.to_wei(amount, 'ether')
    tx_data: TxParams = token_contract.functions.approve(
        Web3.to_checksum_address(spender),
        amount_wei
    ).build_transaction({
        'from': Web3.to_checksum_address(user_address),
        'gas': 100000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
    })
    return tx_data


def build_aave_supply_tx_data(chain: str, pool_address: str, token_address: str, amount: float, user_address: str) -> TxParams:
    w3 = connect_to_chain(chain)
    if not w3:
        raise ValueError(f"No Web3 connection for chain {chain}")
    pool_contract = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=AAVE_POOL_ABI)
    amount_wei = w3.to_wei(amount, 'ether')
    tx_data: TxParams = pool_contract.functions.supply(
        Web3.to_checksum_address(token_address),
        amount_wei,
        Web3.to_checksum_address(user_address),
        0  # referralCode
    ).build_transaction({
        'from': Web3.to_checksum_address(user_address),
        'gas': 200000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
    })
    return tx_data


def build_aave_withdraw_tx_data(chain: str, pool_address: str, token_address: str, amount: float, user_address: str) -> TxParams:
    w3 = connect_to_chain(chain)
    if not w3:
        raise ValueError(f"No Web3 connection for chain {chain}")
    pool_contract = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=AAVE_POOL_ABI)
    amount_wei = w3.to_wei(amount, 'ether')
    tx_data: TxParams = pool_contract.functions.withdraw(
        Web3.to_checksum_address(token_address),
        amount_wei,
        Web3.to_checksum_address(user_address)
    ).build_transaction({
        'from': Web3.to_checksum_address(user_address),
        'gas': 200000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
    })
    return tx_data


def build_compound_supply_tx_data(chain: str, comet_address: str, token_address: str, amount: float, user_address: str) -> TxParams:
    w3 = connect_to_chain(chain)
    if not w3:
        raise ValueError(f"No Web3 connection for chain {chain}")
    comet_contract = w3.eth.contract(address=Web3.to_checksum_address(comet_address), abi=COMPOUND_COMET_ABI)
    amount_wei = w3.to_wei(amount, 'ether')
    tx_data: TxParams = comet_contract.functions.supply(
        Web3.to_checksum_address(token_address),
        amount_wei
    ).build_transaction({
        'from': Web3.to_checksum_address(user_address),
        'gas': 200000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
    })
    return tx_data


def build_compound_withdraw_tx_data(chain: str, comet_address: str, token_address: str, amount: float, user_address: str) -> TxParams:
    w3 = connect_to_chain(chain)
    if not w3:
        raise ValueError(f"No Web3 connection for chain {chain}")
    comet_contract = w3.eth.contract(address=Web3.to_checksum_address(comet_address), abi=COMPOUND_COMET_ABI)
    amount_wei = w3.to_wei(amount, 'ether')
    tx_data: TxParams = comet_contract.functions.withdraw(
        Web3.to_checksum_address(token_address),
        amount_wei
    ).build_transaction({
        'from': Web3.to_checksum_address(user_address),
        'gas': 200000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
    })
    return tx_data


def confirm_tx(chain: str, tx_hash: str) -> bool:
    try:
        w3 = connect_to_chain(chain)
        if not w3:
            raise ValueError(f"No Web3 connection for chain {chain}")
        receipt = w3.eth.wait_for_transaction_receipt(HexBytes(tx_hash), timeout=300)
        return receipt["status"] == 1
    except Exception as e:
        logger.error(f"Failed to confirm tx {tx_hash}: {e}")
        return False


def init_wallets(session_state):
    session_state.wallets = {chain: Wallet(chain=chain) for chain in NETWORK_NAMES.keys()}
    db_wallets = db.get_wallets()
    for db_wallet in db_wallets:
        chain = db_wallet['chain']
        if chain in session_state.wallets:
            wallet = session_state.wallets[chain]
            wallet.address = db_wallet['address']
            wallet.connected = db_wallet['connected']
            wallet.verified = db_wallet['verified']
            wallet.balance = db_wallet['balance']
            wallet.nonce = db_wallet['nonce']

def get_connected_wallet(session_state, chain: str) -> Optional[Wallet]:
    if 'wallets' not in session_state:
        init_wallets(session_state)
    return session_state.wallets.get(chain)

def get_all_wallets(session_state) -> List[Wallet]:
    if 'wallets' not in session_state:
        init_wallets(session_state)
    return list(session_state.wallets.values())

def create_position(chain: str, opportunity_name: str, token_symbol: str, amount: float, tx_hash: str, protocol: Optional[str] = None) -> Position:
    position = Position(
        id=f"pos_{tx_hash[:8]}",
        chain=chain,
        opportunity_name=opportunity_name,
        token_symbol=token_symbol,
        amount_invested=amount,
        current_value=amount,
        entry_date=datetime.now(),
        tx_hash=tx_hash,
        status="pending"  # Start as pending until confirmed
    )
    if db.confirm_position(chain, position.id, tx_hash):
        position.status = "active"
    else:
        position.status = "failed"
    return position

def add_position_to_session(session_state, position: Position):
    if 'positions' not in session_state:
        session_state.positions = []
    session_state.positions.append(position)
    chain = position.chain
    wallet_address = session_state.wallets[chain].address if chain in session_state.wallets and session_state.wallets[chain].address else None
    if not wallet_address:
        raise ValueError("No connected wallet for chain")
    db.save_position(
        position_id=position.id,
        chain=position.chain,
        wallet_address=wallet_address,
        opportunity_name=position.opportunity_name,
        token_symbol=position.token_symbol,
        amount_invested=position.amount_invested,
        tx_hash=position.tx_hash,
        protocol=position.opportunity_name.lower(),
        apy=None  # Fetch from opportunity if needed
    )

def close_position(session_state, position_id: str, tx_hash: Optional[str] = None):
    if db.close_position(position_id, tx_hash):
        if tx_hash and not db.confirm_position(session_state.positions[0].chain, position_id, tx_hash):
            return False
        if 'positions' in session_state:
            for pos in session_state.positions:
                if pos.id == position_id and pos.status == "active":
                    pos.status = "closed"
                    pos.tx_hash = tx_hash or pos.tx_hash
                    return True
    return False

def get_token_price(symbol: str) -> float:
    try:
        coingecko_ids = {
            "ETH": "ethereum",
            "BNB": "binancecoin", 
            "AVAX": "avalanche-2",
            "USDC": "usd-coin",
            "USDT": "tether",
            "DAI": "dai"
        }
        coingecko_id = coingecko_ids.get(symbol, symbol.lower())
        response = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd",
            timeout=10
        )
        data = response.json()
        return data.get(coingecko_id, {}).get("usd", 0.0)
    except Exception:
        return 0.0