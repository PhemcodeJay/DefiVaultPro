import os
import time
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

from web3 import Web3
from hexbytes import HexBytes
from sqlalchemy import BigInteger, Column, create_engine, select
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, mapped_column
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from utils import connect_to_chain

# ----------------------------- Logging -----------------------------
logging.basicConfig(
    level=logging.INFO,
    filename="logs/db.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

# ----------------------------- Database URLs -----------------------------
POSTGRES_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:1234@localhost:5432/Defiscanner"
)
SQLITE_URL = "sqlite:///defi_dashboard.db"

# ----------------------------- Engine -----------------------------
def get_engine():
    try:
        engine = create_engine(POSTGRES_URL)
        conn = engine.connect()
        conn.close()
        logger.info("Connected to PostgreSQL successfully.")
        return engine
    except Exception as e:
        logger.warning(f"PostgreSQL not available: {e}. Falling back to SQLite.")
        engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
        return engine

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ----------------------------- Models -----------------------------
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
    status: Mapped[str] = mapped_column(default="active")
    tx_hash: Mapped[Optional[str]] = mapped_column(default=None)
    protocol: Mapped[Optional[str]] = mapped_column(default=None)
    apy: Mapped[Optional[float]] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project: Mapped[str]
    symbol: Mapped[str]
    chain: Mapped[str]
    apy: Mapped[float]
    tvl: Mapped[float]
    risk: Mapped[str]
    type: Mapped[Optional[str]]
    contract_address: Mapped[str]
    last_updated: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(default=True)

class MemeOpportunity(Base):
    __tablename__ = "meme_opportunities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
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

# ----------------------------- Database Utilities -----------------------------
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

def init_database() -> bool:
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

# ----------------------------- Helper -----------------------------
def parse_float(value: Any) -> float:
    try:
        if isinstance(value, str):
            value = value.replace("$", "").replace(",", "").strip()
        return float(value)
    except (ValueError, TypeError):
        logger.warning(f"Failed to parse float from value: {value}. Returning 0.0")
        return 0.0

def validate_opportunity_data(data: Dict[str, Any]) -> bool:
    required_fields = ['project', 'symbol', 'chain', 'contract_address', 'apy', 'tvl', 'risk']
    for field in required_fields:
        if field not in data or data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
            logger.error(f"Missing or invalid required field: {field}")
            return False
    return True

def validate_meme_opportunity_data(data: Dict[str, Any]) -> bool:
    required_fields = ['project', 'name', 'symbol', 'chain', 'contract_address', 'price', 'market_cap', 'risk']
    for field in required_fields:
        if field not in data or data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
            logger.error(f"Missing or invalid required field for meme: {field}")
            return False
    return True

# ----------------------------- Wallet Functions -----------------------------
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

# ----------------------------- Position Functions -----------------------------
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

# ----------------------------- Opportunities Functions -----------------------------
def save_opportunities(opp_data: List[Dict[str, Any]]) -> bool:
    try:
        with get_db_session() as session:
            for data in opp_data:
                if not validate_opportunity_data(data):
                    logger.warning(f"Skipping invalid opportunity data: {data}")
                    continue

                apy = parse_float(data.get('apy', 0.0))
                tvl = parse_float(data.get('tvl', 0.0))

                # Check for existing opportunity by contract_address and chain
                existing = session.query(Opportunity).filter_by(
                    contract_address=data['contract_address'],
                    chain=data['chain']
                ).first()

                opp_dict = {
                    "project": data['project'],
                    "symbol": data['symbol'],
                    "chain": data['chain'],
                    "apy": apy,
                    "tvl": tvl,
                    "risk": data['risk'],
                    "type": data.get('type'),
                    "contract_address": data['contract_address'],
                    "last_updated": datetime.utcnow(),
                    "is_active": True
                }

                if existing:
                    # Update existing record
                    for key, value in opp_dict.items():
                        setattr(existing, key, value)
                    session.merge(existing)
                else:
                    # Insert new record
                    opp = Opportunity(**opp_dict)
                    session.add(opp)

            return True
    except IntegrityError as e:
        logger.error(f"Integrity error while saving opportunities: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to save opportunities: {e}")
        return False

def save_meme_opportunities(meme_data: List[Dict[str, Any]]) -> bool:
    try:
        with get_db_session() as session:
            for data in meme_data:
                if not validate_meme_opportunity_data(data):
                    logger.warning(f"Skipping invalid meme opportunity data: {data}")
                    continue

                price = parse_float(data.get('price', 0.0))
                market_cap = parse_float(data.get('market_cap', 0.0))

                # Check for existing meme opportunity by contract_address and chain
                existing = session.query(MemeOpportunity).filter_by(
                    contract_address=data['contract_address'],
                    chain=data['chain']
                ).first()

                meme_dict = {
                    "project": data['project'],
                    "name": data['name'],
                    "symbol": data['symbol'],
                    "chain": data['chain'],
                    "price": price,
                    "market_cap": market_cap,
                    "risk": data['risk'],
                    "growth_potential": data.get('growth_potential', '0%'),
                    "source_url": data.get('source_url'),
                    "contract_address": data['contract_address'],
                    "last_updated": datetime.utcnow(),
                    "is_active": True
                }

                if existing:
                    # Update existing record
                    for key, value in meme_dict.items():
                        setattr(existing, key, value)
                    session.merge(existing)
                else:
                    # Insert new record
                    meme = MemeOpportunity(**meme_dict)
                    session.add(meme)

            return True
    except IntegrityError as e:
        logger.error(f"Integrity error while saving meme opportunities: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to save meme opportunities: {e}")
        return False

# ----------------------------- Retrieval Functions -----------------------------
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
                    'price': float(m.price),
                    'market_cap': float(m.market_cap),
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

# ----------------------------- Initialize DB -----------------------------
if __name__ == "__main__":
    init_database()