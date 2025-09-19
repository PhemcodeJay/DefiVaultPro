import streamlit as st
from dataclasses import dataclass
from typing import List, Optional, TypedDict
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
import time
import config

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    filename="logs/wallet_utils.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

load_dotenv()

# ---------- Network & Token Config ----------
NETWORK_NAMES = config.NETWORK_NAMES
ERC20_TOKENS = config.ERC20_TOKENS
ERC20_TOKENS['ethereum']['WETH'] = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
CONTRACT_MAP = config.CONTRACT_MAP

# ---------- TypedDict for transaction receipt ----------
class TxReceipt(TypedDict):
    status: int
    transactionHash: HexBytes
    blockNumber: int  # use int instead of BlockNumber for type compatibility

# ---------- Wallet & Position ----------
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
        db.save_wallet(f"{self.chain}_{self.address}", self.chain, self.address,
                       self.connected, self.verified, self.balance, self.nonce)

    def disconnect(self):
        if self.address:
            db.disconnect_wallet(f"{self.chain}_{self.address}")
        self.address = None
        self.connected = False
        self.verified = False
        self.balance = 0.0
        self.nonce = None

    def update_balance(self):
        w3 = connect_to_chain(self.chain)
        if w3 and self.address:
            try:
                checksum_address = Web3.to_checksum_address(self.address)
                if self.chain in ERC20_TOKENS:
                    token_address = ERC20_TOKENS[self.chain].get("USDC")
                    if token_address:
                        contract = w3.eth.contract(address=Web3.to_checksum_address(token_address),
                                                   abi=config.ERC20_ABI)
                        balance_wei = contract.functions.balanceOf(checksum_address).call()
                        self.balance = float(w3.from_wei(balance_wei, 'ether'))
                    else:
                        self.balance = float(w3.from_wei(w3.eth.get_balance(checksum_address), 'ether'))
                else:
                    self.balance = float(w3.from_wei(w3.eth.get_balance(checksum_address), 'ether'))
                db.save_wallet(f"{self.chain}_{self.address}", self.chain, self.address,
                               self.connected, self.verified, self.balance, self.nonce)
            except Exception as e:
                logger.error(f"Failed to update balance for {self.address}: {e}")
                self.balance = 0.0

    def update_nonce(self):
        w3 = connect_to_chain(self.chain)
        if w3 and self.address:
            try:
                self.nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(self.address))
                db.save_wallet(f"{self.chain}_{self.address}", self.chain, self.address,
                               self.connected, self.verified, self.balance, self.nonce)
            except Exception as e:
                logger.error(f"Failed to update nonce for {self.address}: {e}")
                self.nonce = None

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
    status: str
    protocol: Optional[str] = None
    apy: Optional[float] = None
    exit_date: Optional[datetime] = None

# ---------- Transaction Builders ----------
def build_erc20_approve_tx_data(chain: str, token_address: str, spender: str,
                                amount: float, user_address: str) -> TxParams:
    w3 = connect_to_chain(chain)
    if not w3:
        raise ValueError(f"No Web3 connection for chain {chain}")
    token_contract = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=config.ERC20_ABI)
    amount_wei = w3.to_wei(amount, 'ether')
    func = token_contract.functions.approve(Web3.to_checksum_address(spender), amount_wei)
    tx_params: TxParams = {
        'from': Web3.to_checksum_address(user_address),
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
    }
    tx_params['gas'] = int(func.estimate_gas(tx_params) * 1.2)
    return func.build_transaction(tx_params)

def build_aave_supply_tx_data(chain: str, pool_address: str, token_address: str,
                              amount: float, user_address: str) -> TxParams:
    w3 = connect_to_chain(chain)
    if not w3:
        raise ValueError(f"No Web3 connection for chain {chain}")
    pool_contract = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=config.AAVE_POOL_ABI)
    amount_wei = w3.to_wei(amount, 'ether')
    func = pool_contract.functions.supply(
        Web3.to_checksum_address(token_address),
        amount_wei,
        Web3.to_checksum_address(user_address),
        0  # referralCode
    )
    tx_params: TxParams = {
        'from': Web3.to_checksum_address(user_address),
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
    }
    tx_params['gas'] = int(func.estimate_gas(tx_params) * 1.2)
    return func.build_transaction(tx_params)

def build_aave_withdraw_tx_data(chain: str, pool_address: str, token_address: str,
                              amount: float, user_address: str) -> TxParams:
    w3 = connect_to_chain(chain)
    if not w3:
        raise ValueError(f"No Web3 connection for chain {chain}")
    pool_contract = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=config.AAVE_POOL_ABI)
    amount_wei = w3.to_wei(amount, 'ether')
    func = pool_contract.functions.withdraw(
        Web3.to_checksum_address(token_address),
        amount_wei,
        Web3.to_checksum_address(user_address),
        0  # referralCode
    )
    tx_params: TxParams = {
        'from': Web3.to_checksum_address(user_address),
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
    }
    tx_params['gas'] = int(func.estimate_gas(tx_params) * 1.2)
    return func.build_transaction(tx_params)

def build_compound_supply_tx_data(chain: str, pool_address: str, token_address: str,
                                  amount: float, user_address: str) -> TxParams:
    w3 = connect_to_chain(chain)
    if not w3:
        raise ValueError(f"No Web3 connection for chain {chain}")
    ctoken_contract = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=config.COMPOUND_COMET_ABI)
    amount_wei = w3.to_wei(amount, 'ether')
    func = ctoken_contract.functions.mint(amount_wei)
    tx_params: TxParams = {
        'from': Web3.to_checksum_address(user_address),
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
    }
    tx_params['gas'] = int(func.estimate_gas(tx_params) * 1.2)
    return func.build_transaction(tx_params)

def build_compound_withdraw_tx_data(chain: str, pool_address: str, token_address: str,
                                  amount: float, user_address: str) -> TxParams:
    w3 = connect_to_chain(chain)
    if not w3:
        raise ValueError(f"No Web3 connection for chain {chain}")
    ctoken_contract = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=config.COMPOUND_COMET_ABI)
    amount_wei = w3.to_wei(amount, 'ether')
    func = ctoken_contract.functions.mint(amount_wei)
    tx_params: TxParams = {
        'from': Web3.to_checksum_address(user_address),
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))
    }
    tx_params['gas'] = int(func.estimate_gas(tx_params) * 1.2)
    return func.build_transaction(tx_params)

# ---------- Confirm Transactions ----------
def confirm_tx(chain: str, tx_hash: str) -> bool:
    try:
        w3 = connect_to_chain(chain)
        if not w3:
            return False
        web3_receipt = w3.eth.wait_for_transaction_receipt(HexBytes(tx_hash), timeout=300)
        receipt: TxReceipt = {
            "status": web3_receipt["status"] if isinstance(web3_receipt, dict) else web3_receipt.status,
            "transactionHash": web3_receipt["transactionHash"] if isinstance(web3_receipt, dict) else web3_receipt.transactionHash,
            "blockNumber": int(web3_receipt["blockNumber"] if isinstance(web3_receipt, dict) else web3_receipt.blockNumber)
        }
        return receipt["status"] == 1
    except Exception as e:
        logger.error(f"Failed to confirm tx {tx_hash}: {e}")
        return False

def confirm_position(chain: str, position_id: str, tx_hash: str) -> bool:
    return confirm_tx(chain, tx_hash)

# ---------- Wallet Session Helpers ----------
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
    return session_state.wallets.get(chain.lower())

def get_all_wallets(session_state) -> List[Wallet]:
    if 'wallets' not in session_state:
        init_wallets(session_state)
    return list(session_state.wallets.values())

# ---------- Position Management ----------
def create_position(chain: str, opportunity_name: str, token_symbol: str,
                    amount: float, tx_hash: str, protocol: Optional[str] = None) -> Position:
    position = Position(
        id=f"pos_{tx_hash[:8]}",
        chain=chain,
        opportunity_name=opportunity_name,
        token_symbol=token_symbol,
        amount_invested=amount,
        current_value=amount,
        entry_date=datetime.now(),
        tx_hash=tx_hash,
        status="pending",
        protocol=protocol
    )
    if confirm_position(chain, position.id, tx_hash):
        position.status = "active"
    else:
        position.status = "failed"
    return position

def add_position_to_session(session_state, position: Position):
    if 'positions' not in session_state:
        session_state.positions = []
    session_state.positions.append(position)
    wallet = get_connected_wallet(session_state, position.chain)
    if not wallet or not wallet.address:
        raise ValueError("No connected wallet for chain")
    db.save_position(
        position_id=position.id,
        chain=position.chain,
        wallet_address=wallet.address,
        opportunity_name=position.opportunity_name,
        token_symbol=position.token_symbol,
        amount_invested=position.amount_invested,
        tx_hash=position.tx_hash,
        protocol=position.protocol,
        apy=position.apy
    )

def close_position(session_state, position_id: str, tx_hash: Optional[str] = None) -> bool:
    if db.close_position(position_id, tx_hash):
        if tx_hash and not confirm_position(session_state.positions[0].chain, position_id, tx_hash):
            return False
        if 'positions' in session_state:
            for pos in session_state.positions:
                if pos.id == position_id and pos.status == "active":
                    pos.status = "closed"
                    pos.exit_date = datetime.now()
                    pos.tx_hash = tx_hash or pos.tx_hash
                    return True
    return False

# ---------- Token Price ----------
def get_token_price(symbol: str) -> float:
    retries = 3
    for attempt in range(retries):
        try:
            coingecko_ids = {
                "ETH": "ethereum",
                "BNB": "binancecoin",
                "AVAX": "avalanche-2",
                "USDC": "usd-coin",
                "USDT": "tether",
                "DAI": "dai",
                "WETH": "weth"
            }
            coingecko_id = coingecko_ids.get(symbol.upper(), symbol.lower())
            response = requests.get(
                f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return float(data.get(coingecko_id, {}).get("usd", 0.0))
        except Exception as e:
            logger.error(f"Failed to fetch token price for {symbol} (attempt {attempt+1}): {e}")
            if attempt == retries - 1:
                return 0.0
            time.sleep(2 ** attempt)
    return 0.0  # fallback to satisfy return type