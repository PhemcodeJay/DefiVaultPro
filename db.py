import os
import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine, Column, String, Float, DateTime, Boolean, Integer, Text, MetaData, select
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
import logging
from urllib.parse import urlparse
from web3 import Web3
from hexbytes import HexBytes
from eth_typing.encoding import HexStr
from utils import connect_to_chain

# Configure logging
logging.basicConfig(level=logging.INFO, filename="app.log", filemode="a", format="%(asctime)s - %(levelname)s - %(message)s", encoding="utf-8")
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    DATABASE_URL = 'sqlite:///defi_dashboard.db'
    logger.warning("DATABASE_URL not set, using SQLite fallback")

# Parse URL to handle different database types
parsed_url = urlparse(DATABASE_URL)
is_sqlite = parsed_url.scheme == 'sqlite'

# SQLAlchemy setup
if is_sqlite:
    # Ensure the SQLite database file exists
    db_path = parsed_url.path.lstrip('/')
    if not os.path.exists(db_path):
        logger.info(f"SQLite database file {db_path} not found, creating it...")
        open(db_path, 'a').close()  # Create an empty file
    engine = create_engine(DATABASE_URL, echo=False, connect_args={'check_same_thread': False})
else:
    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Database Models
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
)
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


# ---------------------------------
# Wallet Table
# ---------------------------------
class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(String, primary_key=True)  # chain_address combination
    chain = Column(String, nullable=False)
    address = Column(String, nullable=False)
    connected = Column(Boolean, default=False)
    verified = Column(Boolean, default=False)
    balance = Column(Float, default=0.0)
    nonce = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------
# Position Table
# ---------------------------------
class Position(Base):
    __tablename__ = "positions"

    id = Column(String, primary_key=True)
    chain = Column(String, nullable=False)
    wallet_address = Column(String, nullable=False)
    opportunity_name = Column(String, nullable=False)
    token_symbol = Column(String, nullable=False)
    amount_invested = Column(Float, nullable=False)
    current_value = Column(Float, nullable=False)
    entry_date = Column(DateTime, default=datetime.utcnow)
    exit_date = Column(DateTime, nullable=True)
    status = Column(String, default="active")  # active, closed
    tx_hash = Column(String, nullable=True)   # Optional transaction hash
    protocol = Column(String, nullable=True)
    apy = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------
# Opportunity Table
# ---------------------------------
class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    apy = Column(Float, nullable=False)
    tvl = Column(Float, nullable=False)
    risk = Column(String, nullable=False)
    type = Column(String, nullable=False)
    contract_address = Column(String, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


# ---------------------------------
# Meme Opportunities Table
# ---------------------------------
class MemeOpportunity(Base):
    __tablename__ = "meme_opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project = Column(String, nullable=False)
    name = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    market_cap = Column(Float, nullable=False)
    risk = Column(String, nullable=False)
    growth_potential = Column(String, nullable=False)
    source_url = Column(String, nullable=True)
    contract_address = Column(String, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

@contextmanager
def get_db_session():
    """Context manager for database sessions."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()

def test_connection() -> bool:
    """Test database connection."""
    try:
        with get_db_session() as session:
            session.execute(select(1))
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

def init_database() -> bool:
    """Initialize database tables."""
    try:
        if is_sqlite:
            db_path = parsed_url.path.lstrip('/')
            if not os.path.exists(db_path):
                logger.error(f"SQLite database file {db_path} still not found after creation attempt")
                return False
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

def save_wallet(wallet_id: str, chain: str, address: str, connected: bool = False, verified: bool = False, balance: float = 0.0, nonce: Optional[int] = None) -> bool:
    """Save or update a wallet."""
    try:
        with get_db_session() as session:
            wallet = session.query(Wallet).filter_by(id=wallet_id).first()
            if wallet:
                # Update existing wallet using setattr to avoid direct Column assignment
                setattr(wallet, 'address', address)
                setattr(wallet, 'connected', connected)
                setattr(wallet, 'verified', verified)
                setattr(wallet, 'balance', balance)
                setattr(wallet, 'nonce', nonce)
                setattr(wallet, 'updated_at', datetime.utcnow())
                session.merge(wallet)
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
    """Get all wallets."""
    try:
        with get_db_session() as session:
            wallets = session.query(Wallet).all()
            return [{
                'id': w.id,
                'chain': w.chain,
                'address': w.address,
                'connected': w.connected,
                'verified': w.verified,
                'balance': w.balance,
                'nonce': w.nonce,
                'created_at': w.created_at,
                'updated_at': w.updated_at
            } for w in wallets]
    except Exception as e:
        logger.error(f"Failed to get wallets: {e}")
        return []

def disconnect_wallet(wallet_id: str) -> bool:
    """Disconnect a wallet."""
    try:
        with get_db_session() as session:
            wallet = session.query(Wallet).filter_by(id=wallet_id).first()
            if wallet:
                setattr(wallet, 'connected', False)
                setattr(wallet, 'updated_at', datetime.utcnow())
                session.merge(wallet)
                return True
        return False
    except Exception as e:
        logger.error(f"Failed to disconnect wallet: {e}")
        return False

def save_position(position_id: str, chain: str, wallet_address: str, opportunity_name: str, token_symbol: str, amount_invested: float, tx_hash: str, protocol: Optional[str] = None, apy: Optional[float] = None) -> bool:
    """Save a new position with real transaction data."""
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
    """Close a position with optional closing transaction hash."""
    try:
        with get_db_session() as session:
            position = session.query(Position).filter_by(id=position_id).first()
            if position is None:
                return False

            if position is not None and str(position.status) == "active":
                setattr(position, 'status', 'closed')  # Use setattr to avoid type issues
                setattr(position, 'exit_date', datetime.utcnow())
                setattr(position, 'updated_at', datetime.utcnow())
                if tx_hash:
                    setattr(position, 'tx_hash', tx_hash)  # Update with closing tx if provided
                session.merge(position)
                return True

            return False
    except Exception as e:
        logger.error(f"Failed to close position: {e}")
        return False


def confirm_position(chain: str, position_id: str, tx_hash: str) -> bool:
    """Confirm a position's transaction is successful."""
    try:
        w3 = connect_to_chain(chain)
        if w3 is None:
            logger.error(f"Failed to connect to chain: {chain}")
            return False
        receipt = w3.eth.wait_for_transaction_receipt(HexBytes(tx_hash), timeout=300)  # Convert to HexBytes
        if receipt["status"] == 1:
            with get_db_session() as session:
                position = session.query(Position).filter_by(id=position_id).first()
                if position:
                    setattr(position, 'updated_at', datetime.utcnow())  # Use setattr to avoid type issues
                    session.merge(position)
                    return True
        return False
    except Exception as e:
        logger.error(f"Failed to confirm position tx {tx_hash}: {e}")
        return False

def update_position_value(position_id: str, new_value: float) -> bool:
    """Update the current value of a position."""
    try:
        with get_db_session() as session:
            position = session.query(Position).filter_by(id=position_id).first()
            if position:
                setattr(position, 'current_value', new_value)
                setattr(position, 'updated_at', datetime.utcnow())
                session.merge(position)
                return True
        return False
    except Exception as e:
        logger.error(f"Failed to update position value: {e}")
        return False

def get_positions(wallet_address: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get positions, optionally filtered by wallet."""
    try:
        with get_db_session() as session:
            query = session.query(Position)
            if wallet_address:
                query = query.filter_by(wallet_address=Web3.to_checksum_address(wallet_address))
            positions = query.all()
            return [{
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
            } for p in positions]
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return []

def get_active_positions(wallet_address: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get active positions."""
    try:
        with get_db_session() as session:
            query = session.query(Position).filter_by(status='active')
            if wallet_address:
                query = query.filter_by(wallet_address=Web3.to_checksum_address(wallet_address))
            positions = query.all()
            return [{
                'id': p.id,
                'chain': p.chain,
                'wallet_address': p.wallet_address,
                'opportunity_name': p.opportunity_name,
                'token_symbol': p.token_symbol,
                'amount_invested': p.amount_invested,
                'current_value': p.current_value,  # Fixed typo (was current_value12)
                'entry_date': p.entry_date,
                'tx_hash': p.tx_hash,
                'protocol': p.protocol,
                'apy': p.apy
            } for p in positions]
    except Exception as e:
        logger.error(f"Failed to get active positions: {e}")
        return []

def save_opportunities(opp_data: List[Dict[str, Any]]) -> bool:
    """Save or update yield opportunities."""
    try:
        with get_db_session() as session:
            for data in opp_data:
                opp = Opportunity(
                    id=data['id'],
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
    """Get yield opportunities, optionally filtered by chain."""
    try:
        with get_db_session() as session:
            query = session.query(Opportunity).filter_by(is_active=True)
            if chain:
                query = query.filter_by(chain=chain)
            opps = query.order_by(Opportunity.tvl.desc()).limit(limit).all()
            return [{
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
            } for o in opps]
    except Exception as e:
        logger.error(f"Failed to get opportunities: {e}")
        return []

def save_meme_opportunities(meme_data: List[Dict[str, Any]]) -> bool:
    """Save or update meme opportunities."""
    try:
        with get_db_session() as session:
            for data in meme_data:
                meme_opp = MemeOpportunity(
                    id=data['id'],
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
                session.merge(meme_opp)
        return True
    except Exception as e:
        logger.error(f"Failed to save meme opportunities: {e}")
        return False

def get_meme_opportunities(limit: int = 20) -> List[Dict[str, Any]]:
    """Get meme coin opportunities."""
    try:
        with get_db_session() as session:
            meme_opps = session.query(MemeOpportunity).filter(
                MemeOpportunity.is_active == True
            ).order_by(MemeOpportunity.market_cap.desc()).limit(limit).all()
            
            return [{
                'id': meme.id,
                'project': meme.project,
                'name': meme.name,
                'symbol': meme.symbol,
                'chain': meme.chain,
                'price': meme.price,
                'market_cap': meme.market_cap,
                'risk': meme.risk,
                'growth_potential': meme.growth_potential,
                'source_url': meme.source_url,
                'contract_address': meme.contract_address,
                'last_updated': meme.last_updated
            } for meme in meme_opps]
    except Exception as e:
        logger.error(f"Failed to get meme opportunities: {e}")
        return []

def get_database_stats() -> Dict[str, int]:
    """Get database statistics."""
    try:
        with get_db_session() as session:
            stats = {
                'wallets': session.query(Wallet).count(),
                'active_positions': session.query(Position).filter(Position.status == 'active').count(),
                'closed_positions': session.query(Position).filter(Position.status == 'closed').count(),
                'opportunities': session.query(Opportunity).filter(Opportunity.is_active == True).count(),
                'meme_opportunities': session.query(MemeOpportunity).filter(MemeOpportunity.is_active == True).count()
            }
            return stats
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return {}

def cleanup_old_data(days: int = 30) -> bool:
    """Clean up old inactive data."""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        with get_db_session() as session:
            session.query(Opportunity).filter(
                Opportunity.is_active == False,
                Opportunity.last_updated < cutoff_date
            ).delete()
            
            session.query(MemeOpportunity).filter(
                MemeOpportunity.is_active == False,
                MemeOpportunity.last_updated < cutoff_date
            ).delete()
        
        logger.info(f"Cleaned up data older than {days} days")
        return True
    except Exception as e:
        logger.error(f"Failed to cleanup old data: {e}")
        return False
    
# --- Auto initialize DB on import ---
try:
    if test_connection():
        init_database()
        logger.info("Database initialized automatically on import")
    else:
        logger.error("Database connection failed on import")
except Exception as e:
    logger.error(f"Failed to auto initialize database: {e}")



if __name__ == "__main__":
    if test_connection():
        if init_database():
            print("Database initialized successfully!")
            stats = get_database_stats()
            print(f"Database stats: {stats}")
        else:
            print("Failed to initialize database")
    else:
        print("Database connection failed")