import os
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

from sqlalchemy import (
    BigInteger,
    Column,
    String,
    Float,
    Boolean,
    DateTime,
    Integer,
    create_engine,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, mapped_column
from sqlalchemy.exc import SQLAlchemyError
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

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
def create_postgres_database(db_url: str) -> None:
    """Create PostgreSQL DB if it doesn't exist."""
    try:
        db_name = db_url.split("/")[-1]
        base_url = "/".join(db_url.split("/")[:-1])

        conn = psycopg2.connect(base_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cursor.fetchone()

        if not exists:
            cursor.execute(f"CREATE DATABASE {db_name}")
            logger.info(f"Created PostgreSQL database: {db_name}")
        else:
            logger.info(f"PostgreSQL database {db_name} already exists")

        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to create PostgreSQL database: {e}")

def get_engine():
    try:
        create_postgres_database(POSTGRES_URL)
        engine = create_engine(POSTGRES_URL)
        conn = engine.connect()
        conn.close()
        logger.info("Connected to PostgreSQL successfully.")
        return engine
    except Exception as e:
        logger.warning(f"PostgreSQL not available: {e}. Falling back to SQLite.")
        return create_engine(SQLITE_URL, connect_args={"check_same_thread": False})

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ----------------------------- Models -----------------------------
class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    chain: Mapped[str] = mapped_column(String(50))
    address: Mapped[str] = mapped_column(String(255))
    connected: Mapped[bool] = mapped_column(Boolean, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    nonce: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Position(Base):
    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    chain: Mapped[str] = mapped_column(String(50))
    wallet_address: Mapped[str] = mapped_column(String(255))
    opportunity_name: Mapped[str] = mapped_column(String(255))
    token_symbol: Mapped[str] = mapped_column(String(50))
    amount_invested: Mapped[float] = mapped_column(Float)
    current_value: Mapped[float] = mapped_column(Float)
    entry_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    exit_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    tx_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    protocol: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    apy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        UniqueConstraint('contract_address', 'chain', name='uix_opportunities_contract_chain'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project: Mapped[str] = mapped_column(String(100))
    symbol: Mapped[str] = mapped_column(String(50))
    chain: Mapped[str] = mapped_column(String(50))
    apy: Mapped[float] = mapped_column(Float)
    tvl: Mapped[float] = mapped_column(Float)
    risk: Mapped[str] = mapped_column(String(20))
    type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contract_address: Mapped[str] = mapped_column(String(255))
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class MemeOpportunity(Base):
    __tablename__ = "meme_opportunities"
    __table_args__ = (
        UniqueConstraint('contract_address', 'chain', name='uix_meme_opportunities_contract_chain'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    symbol: Mapped[str] = mapped_column(String(50))
    chain: Mapped[str] = mapped_column(String(50))
    price: Mapped[float] = mapped_column(Float)
    market_cap: Mapped[float] = mapped_column(Float)
    risk: Mapped[str] = mapped_column(String(20))
    growth_potential: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contract_address: Mapped[str] = mapped_column(String(255))
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

# ----------------------------- DB Session -----------------------------
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
        if 'postgresql' in POSTGRES_URL:
            create_postgres_database(POSTGRES_URL)

        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'opportunities')"
            ))
            if not result.scalar():
                logger.error("Failed to create 'opportunities' table")
                return False
        return True
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

# ----------------------------- Helpers -----------------------------
def parse_float(value: Any) -> float:
    try:
        if isinstance(value, str):
            value = value.replace("$", "").replace(",", "").strip()
        return float(value)
    except (ValueError, TypeError):
        logger.warning(f"Failed to parse float: {value}")
        return 0.0

def validate_opportunity_data(data: Dict[str, Any]) -> bool:
    required = ['project', 'symbol', 'chain', 'contract_address', 'apy', 'tvl', 'risk']
    missing = [f for f in required if data.get(f) in (None, "", " ")]
    if missing:
        logger.info(f"Skipping opportunity {data.get('project', 'unknown')}: missing/invalid fields {missing}")
        return False
    return True

def validate_meme_opportunity_data(data: Dict[str, Any]) -> bool:
    required = ['project', 'name', 'symbol', 'chain', 'contract_address', 'price', 'market_cap', 'risk']
    missing = [f for f in required if data.get(f) in (None, "", " ")]
    if missing:
        logger.info(f"Skipping meme opportunity {data.get('project', 'unknown')}: missing/invalid fields {missing}")
        return False
    return True

# ----------------------------- Save Functions -----------------------------
def save_opportunities(opp_data: List[Dict[str, Any]]) -> bool:
    try:
        with get_db_session() as session:
            for data in opp_data:
                if not validate_opportunity_data(data):
                    continue

                apy = parse_float(data.get('apy', 0.0))
                tvl = parse_float(data.get('tvl', 0.0))

                existing = session.query(Opportunity).filter_by(
                    contract_address=data['contract_address'], chain=data['chain']
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
                    for k, v in opp_dict.items():
                        setattr(existing, k, v)
                else:
                    session.add(Opportunity(**opp_dict))
                session.flush()  # Flush to make changes visible within the session
        return True
    except Exception as e:
        logger.error(f"Failed to save opportunities: {e}")
        return False

def save_meme_opportunities(meme_data: List[Dict[str, Any]]) -> bool:
    try:
        with get_db_session() as session:
            for data in meme_data:
                if not validate_meme_opportunity_data(data):
                    continue

                price = parse_float(data.get('price', 0.0))
                market_cap = parse_float(data.get('market_cap', 0.0))

                existing = session.query(MemeOpportunity).filter_by(
                    contract_address=data['contract_address'], chain=data['chain']
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
                    for k, v in meme_dict.items():
                        setattr(existing, k, v)
                else:
                    session.add(MemeOpportunity(**meme_dict))
                session.flush()  # Flush to make changes visible within the session
        return True
    except Exception as e:
        logger.error(f"Failed to save meme opportunities: {e}")
        return False

# ----------------------------- Retrieval -----------------------------
def get_opportunities(chain: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        with get_db_session() as session:
            query = session.query(Opportunity).filter_by(is_active=True)
            if chain:
                query = query.filter_by(chain=chain)
            opps = query.order_by(Opportunity.tvl.desc()).limit(limit).all()
            return [o.__dict__ for o in opps]
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
            return [m.__dict__ for m in memes]
    except Exception as e:
        logger.error(f"Failed to get meme opportunities: {e}")
        return []

# ----------------------------- Wallet Helpers -----------------------------
def save_wallet(wallet_id: str, chain: str, address: str,
                connected: bool, verified: bool, balance: float, nonce: Optional[int]) -> bool:
    try:
        with get_db_session() as session:
            wallet = session.query(Wallet).filter_by(id=wallet_id).first()
            if wallet:
                wallet.chain = chain
                wallet.address = address
                wallet.connected = connected
                wallet.verified = verified
                wallet.balance = balance
                wallet.nonce = nonce
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
            session.flush()
        return True
    except Exception as e:
        logger.error(f"Failed to save wallet {wallet_id}: {e}")
        return False

def disconnect_wallet(wallet_id: str) -> bool:
    try:
        with get_db_session() as session:
            wallet = session.query(Wallet).filter_by(id=wallet_id).first()
            if wallet:
                wallet.connected = False
                wallet.verified = False
                session.flush()
                return True
        return False
    except Exception as e:
        logger.error(f"Failed to disconnect wallet {wallet_id}: {e}")
        return False

def get_wallets() -> List[Dict[str, Any]]:
    try:
        with get_db_session() as session:
            wallets = session.query(Wallet).all()
            return [w.__dict__ for w in wallets]
    except Exception as e:
        logger.error(f"Failed to get wallets: {e}")
        return []

# ----------------------------- Position Helpers -----------------------------
def save_position(position_id: str, chain: str, wallet_address: str,
                  opportunity_name: str, token_symbol: str,
                  amount_invested: float, tx_hash: str,
                  protocol: Optional[str] = None, apy: Optional[float] = None) -> bool:
    try:
        with get_db_session() as session:
            position = session.query(Position).filter_by(id=position_id).first()
            if position:
                # update if exists
                position.chain = chain
                position.wallet_address = wallet_address
                position.opportunity_name = opportunity_name
                position.token_symbol = token_symbol
                position.amount_invested = amount_invested
                position.tx_hash = tx_hash
                position.protocol = protocol
                position.apy = apy
            else:
                # create new
                position = Position(
                    id=position_id,
                    chain=chain,
                    wallet_address=wallet_address,
                    opportunity_name=opportunity_name,
                    token_symbol=token_symbol,
                    amount_invested=amount_invested,
                    current_value=amount_invested,
                    tx_hash=tx_hash,
                    protocol=protocol,
                    apy=apy,
                    status="pending"
                )
                session.add(position)
            session.flush()
        return True
    except Exception as e:
        logger.error(f"Failed to save position {position_id}: {e}")
        return False

def close_position(position_id: str, tx_hash: Optional[str] = None) -> bool:
    try:
        with get_db_session() as session:
            position = session.query(Position).filter_by(id=position_id).first()
            if position and position.status == "active": # type: ignore
                position.status = "closed"
                position.exit_date = datetime.utcnow()
                if tx_hash:
                    position.tx_hash = tx_hash
                session.flush()
                return True
        return False
    except Exception as e:
        logger.error(f"Failed to close position {position_id}: {e}")
        return False

def get_positions(limit: int = 50) -> List[Dict[str, Any]]:
    try:
        with get_db_session() as session:
            positions = session.query(Position).order_by(Position.entry_date.desc()).limit(limit).all()
            return [p.__dict__ for p in positions]
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return []

# ----------------------------- Init -----------------------------
init_database()

if __name__ == "__main__":
    init_database()