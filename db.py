import os
import time
import json
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from web3 import Web3
from hexbytes import HexBytes
from sqlalchemy import create_engine, select
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, mapped_column
from sqlalchemy.exc import SQLAlchemyError
from utils import connect_to_chain

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    filename="logs/db.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///defi_dashboard.db')
parsed_url = urlparse(DATABASE_URL)
is_sqlite = parsed_url.scheme == 'sqlite'

# SQLAlchemy engine
if is_sqlite:
    db_path = parsed_url.path.lstrip('/')
    if not os.path.exists(db_path):
        open(db_path, 'a').close()
        logger.info(f"SQLite DB file created at {db_path}")
    engine = create_engine(DATABASE_URL, echo=False, connect_args={'check_same_thread': False})
else:
    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ----------------------- MODELS -----------------------
class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[str] = mapped_column(primary_key=True)
    chain: Mapped[str]
    address: Mapped[str]
    connected: Mapped[bool] = mapped_column(default=False)
    verified: Mapped[bool] = mapped_column(default=False)
    balance: Mapped[float] = mapped_column(default=0.0)
    nonce: Mapped[Optional[int]] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(primary_key=True)
    chain: Mapped[str]
    wallet_address: Mapped[str]
    opportunity_name: Mapped[str]
    token_symbol: Mapped[str]
    amount_invested: Mapped[float]
    current_value: Mapped[float]
    entry_date: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    exit_date: Mapped[Optional[datetime]] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="active")  # active/closed
    tx_hash: Mapped[Optional[str]] = mapped_column(default=None)
    protocol: Mapped[Optional[str]] = mapped_column(default=None)
    apy: Mapped[Optional[float]] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project: Mapped[str]
    symbol: Mapped[str]
    chain: Mapped[str]
    apy: Mapped[float]
    tvl: Mapped[float]
    risk: Mapped[str]
    type: Mapped[str]
    contract_address: Mapped[str]
    last_updated: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(default=True)


class MemeOpportunity(Base):
    __tablename__ = "meme_opportunities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project: Mapped[str]
    name: Mapped[str]
    symbol: Mapped[str]
    chain: Mapped[str]
    price: Mapped[float]
    market_cap: Mapped[float]
    risk: Mapped[str]
    growth_potential: Mapped[str]
    source_url: Mapped[Optional[str]] = mapped_column(default=None)
    contract_address: Mapped[str]
    last_updated: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(default=True)


# ----------------------- DATABASE UTILS -----------------------
@contextmanager
def get_db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"DB session error: {e}")
        raise
    finally:
        session.close()


def test_connection(retries: int = 3) -> bool:
    for attempt in range(retries):
        try:
            with get_db_session() as session:
                session.execute(select(1))
            return True
        except Exception as e:
            logger.error(f"DB connection test failed (attempt {attempt + 1}): {e}")
            if attempt == retries - 1:
                return False
            time.sleep(2 ** attempt)
    return False


def init_database() -> bool:
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


# ----------------------- WALLET FUNCTIONS -----------------------
def save_wallet(wallet_id: str, chain: str, address: str,
                connected: bool = False, verified: bool = False,
                balance: float = 0.0, nonce: Optional[int] = None) -> bool:
    if not Web3.is_checksum_address(address):
        logger.error(f"Invalid checksum address: {address}")
        return False
    try:
        with get_db_session() as session:
            wallet = session.get(Wallet, wallet_id)
            if wallet:
                wallet.address = address
                wallet.connected = connected
                wallet.verified = verified
                wallet.balance = balance
                wallet.nonce = nonce
                wallet.updated_at = datetime.utcnow()
            else:
                wallet = Wallet(
                    id=wallet_id,
                    chain=chain,
                    address=address,
                    connected=connected,
                    verified=verified,
                    balance=balance,
                    nonce=nonce
                )
                session.add(wallet)
        return True
    except Exception as e:
        logger.error(f"Failed to save wallet: {e}")
        return False


def get_wallets() -> List[Dict[str, Any]]:
    try:
        with get_db_session() as session:
            wallets = session.query(Wallet).all()
            return [
                {
                    'id': w.id,
                    'chain': w.chain,
                    'address': w.address,
                    'connected': w.connected,
                    'verified': w.verified,
                    'balance': w.balance,
                    'nonce': w.nonce,
                    'created_at': w.created_at,
                    'updated_at': w.updated_at
                } for w in wallets
            ]
    except Exception as e:
        logger.error(f"Failed to get wallets: {e}")
        return []


def disconnect_wallet(wallet_id: str) -> bool:
    try:
        with get_db_session() as session:
            wallet = session.get(Wallet, wallet_id)
            if wallet:
                wallet.connected = False
                wallet.updated_at = datetime.utcnow()
                return True
            return False
    except Exception as e:
        logger.error(f"Failed to disconnect wallet: {e}")
        return False


# ----------------------- POSITION FUNCTIONS -----------------------
def save_position(position_id: str, chain: str, wallet_address: str,
                  opportunity_name: str, token_symbol: str,
                  amount_invested: float, tx_hash: str,
                  protocol: Optional[str] = None, apy: Optional[float] = None) -> bool:
    try:
        with get_db_session() as session:
            position = Position(
                id=position_id,
                chain=chain,
                wallet_address=Web3.to_checksum_address(wallet_address),
                opportunity_name=opportunity_name,
                token_symbol=token_symbol,
                amount_invested=amount_invested,
                current_value=amount_invested,
                tx_hash=tx_hash,
                protocol=protocol,
                apy=apy
            )
            session.add(position)
        return True
    except Exception as e:
        logger.error(f"Failed to save position: {e}")
        return False


def close_position(position_id: str, tx_hash: Optional[str] = None) -> bool:
    try:
        with get_db_session() as session:
            position = session.get(Position, position_id)
            if position:
                position.status = 'closed'
                position.exit_date = datetime.utcnow()
                if tx_hash:
                    position.tx_hash = tx_hash
                position.updated_at = datetime.utcnow()
                return True
            return False
    except Exception as e:
        logger.error(f"Failed to close position: {e}")
        return False

def confirm_position(chain: str, position_id: str, tx_hash: str) -> bool:
    try:
        w3 = connect_to_chain(chain)
        if not w3:
            logger.error(f"Failed to connect to chain: {chain}")
            return False

        receipt = w3.eth.wait_for_transaction_receipt(HexBytes(tx_hash), timeout=300)

        # Access 'status' as dictionary key
        if receipt["status"] == 1:
            with get_db_session() as session:
                position = session.get(Position, position_id)
                if position:
                    position.status = 'active'
                    position.updated_at = datetime.utcnow()
                    return True
        return False
    except Exception as e:
        logger.error(f"Failed to confirm position tx {tx_hash}: {e}")
        return False


def update_position_value(position_id: str, new_value: float) -> bool:
    try:
        with get_db_session() as session:
            position = session.get(Position, position_id)
            if position:
                position.current_value = new_value
                position.updated_at = datetime.utcnow()
                return True
            return False
    except Exception as e:
        logger.error(f"Failed to update position value: {e}")
        return False


def get_positions(wallet_address: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        with get_db_session() as session:
            query = session.query(Position)
            if wallet_address:
                query = query.filter_by(wallet_address=Web3.to_checksum_address(wallet_address))
            positions = query.all()
            return [
                {
                    'id': p.id,
                    'chain': p.chain,
                    'wallet_address': p.wallet_address,
                    'opportunity_name': p.opportunity_name,
                    'token_symbol': p.token_symbol,
                    'amount_invested': p.amount_invested,
                    'current_value': p.current_value,
                    'entry_date': p.entry_date,
                    'exit_date': p.exit_date,
                    'status': p.status,
                    'tx_hash': p.tx_hash,
                    'protocol': p.protocol,
                    'apy': p.apy,
                    'created_at': p.created_at,
                    'updated_at': p.updated_at
                } for p in positions
            ]
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return []


def get_active_positions(wallet_address: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        with get_db_session() as session:
            query = session.query(Position).filter_by(status='active')
            if wallet_address:
                query = query.filter_by(wallet_address=Web3.to_checksum_address(wallet_address))
            positions = query.all()
            return [
                {
                    'id': p.id,
                    'chain': p.chain,
                    'wallet_address': p.wallet_address,
                    'opportunity_name': p.opportunity_name,
                    'token_symbol': p.token_symbol,
                    'amount_invested': p.amount_invested,
                    'current_value': p.current_value,
                    'entry_date': p.entry_date,
                    'tx_hash': p.tx_hash,
                    'protocol': p.protocol,
                    'apy': p.apy
                } for p in positions
            ]
    except Exception as e:
        logger.error(f"Failed to get active positions: {e}")
        return []


# ----------------------- OPPORTUNITIES FUNCTIONS -----------------------
def save_opportunities(opp_data: List[Dict[str, Any]]) -> bool:
    try:
        with get_db_session() as session:
            for data in opp_data:
                opp = Opportunity(
                    id=data.get('id'),
                    project=data['project'],
                    symbol=data['symbol'],
                    chain=data['chain'],
                    apy=data['apy'],
                    tvl=data['tvl'],
                    risk=data['risk'],
                    type=data['type'],
                    contract_address=data['contract_address'],
                    last_updated=datetime.utcnow(),
                    is_active=True
                )
                session.merge(opp)
        return True
    except Exception as e:
        logger.error(f"Failed to save opportunities: {e}")
        return False


def get_opportunities(chain: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        with get_db_session() as session:
            query = session.query(Opportunity).filter_by(is_active=True)
            if chain:
                query = query.filter_by(chain=chain)
            opps = query.order_by(Opportunity.tvl.desc()).limit(limit).all()
            return [
                {
                    'id': o.id,
                    'project': o.project,
                    'symbol': o.symbol,
                    'chain': o.chain,
                    'apy': o.apy,
                    'tvl': o.tvl,
                    'risk': o.risk,
                    'type': o.type,
                    'contract_address': o.contract_address,
                    'last_updated': o.last_updated
                } for o in opps
            ]
    except Exception as e:
        logger.error(f"Failed to get opportunities: {e}")
        return []


def save_meme_opportunities(meme_data: List[Dict[str, Any]]) -> bool:
    try:
        with get_db_session() as session:
            for data in meme_data:
                meme = MemeOpportunity(
                    project=data['project'],
                    name=data['name'],
                    symbol=data['symbol'],
                    chain=data['chain'],
                    price=data['price'],
                    market_cap=data['market_cap'],
                    risk=data['risk'],
                    growth_potential=data['growth_potential'],
                    source_url=data.get('source_url'),
                    contract_address=data['contract_address'],
                    last_updated=datetime.utcnow(),
                    is_active=True
                )
                session.merge(meme)
        return True
    except Exception as e:
        logger.error(f"Failed to save meme opportunities: {e}")
        return False


def get_meme_opportunities(chain: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        with get_db_session() as session:
            query = session.query(MemeOpportunity).filter_by(is_active=True)
            if chain:
                query = query.filter_by(chain=chain)
            memes = query.order_by(MemeOpportunity.market_cap.desc()).limit(limit).all()
            return [
                {
                    'id': m.id,
                    'project': m.project,
                    'name': m.name,
                    'symbol': m.symbol,
                    'chain': m.chain,
                    'price': m.price,
                    'market_cap': m.market_cap,
                    'risk': m.risk,
                    'growth_potential': m.growth_potential,
                    'source_url': m.source_url,
                    'contract_address': m.contract_address,
                    'last_updated': m.last_updated
                } for m in memes
            ]
    except Exception as e:
        logger.error(f"Failed to get meme opportunities: {e}")
        return []


# ----------------------- INIT -----------------------
if __name__ == "__main__":
    init_database()
