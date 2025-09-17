# DeFi Dashboard

This DeFi Dashboard is a user-friendly web app built with Streamlit to help you explore and manage Decentralized Finance (DeFi) opportunities. You can browse yield farming options, invest in meme coins, track your positions, and connect your MetaMask wallet to interact with blockchains like Ethereum, BSC, Arbitrum, Optimism, Base, Avalanche, and Neon EVM.

## Features

- **Browse Opportunities**: Discover DeFi yield farming and meme coin investments with real-time data on APY, TVL, and market trends.
- **Wallet Integration**: Connect your MetaMask wallet to invest or withdraw funds securely.
- **Position Tracking**: Monitor your active and closed investments with profit/loss (PnL) calculations.
- **Multi-Chain Support**: Works with Ethereum, BSC, Arbitrum, Optimism, Base, Avalanche, and Neon EVM.
- **Real-Time Data**: Get live token prices, gas fees, and market info from DeFiLlama and CoinGecko.

## System Architecture

### Frontend
- **Framework**: Streamlit for a simple, interactive web interface.
- **Design**: Clean, modern look with gradient cards and clickable elements for easy navigation.
- **Navigation**: Multiple pages for wallets, positions, top picks, layer 2 opportunities, and meme coins.
- **State Management**: Uses Streamlit session state to track wallet connections and positions.

### Backend
- **Blockchain Interaction**: Connects to blockchains using Web3.py for transactions and gas estimation.
- **Wallet Management**: Supports MetaMask for signing transactions (e.g., approve, supply, swap, withdraw) via JavaScript.
- **Data Sources**: Pulls DeFi data from DeFiLlama and token prices from CoinGecko.
- **Database**: Stores position data in PostgreSQL for persistent tracking.

### Multi-Chain Support
- **Networks**: Ethereum, BSC, Arbitrum, Optimism, Base, Avalanche, Neon EVM.
- **RPC Setup**: Uses public RPC endpoints (configurable in `.env`) for blockchain connections.
- **Chain Logic**: Handles network switching and chain-specific transactions (e.g., Uniswap swaps on Ethereum).

### Smart Contract Integration
- **Protocols**: Supports Aave and Compound for yield farming, Uniswap for meme coin swaps.
- **Contract ABIs**: Includes ABIs for ERC20 tokens, Aave, Compound, and Uniswap routers.
- **Transactions**: Enables direct contract interactions for investing and withdrawing via MetaMask.

### Data Management
- **Opportunity Sorting**: Groups DeFi opportunities by risk, time horizon, and protocol type.
- **Pricing**: Fetches live token prices and calculates gas fees for each chain.
- **Position Tracking**: Tracks investments with real-time PnL and stores data in PostgreSQL.

## External Dependencies

### Blockchain Infrastructure
- **Public RPCs**:
  - Ethereum: `https://eth.llamarpc.com`
  - BSC: `https://bsc-dataseed1.binance.org/`
  - Arbitrum: `https://arb1.arbitrum.io/rpc`
  - Optimism: `https://mainnet.optimism.io`
  - Base: `https://mainnet.base.org`
  - Avalanche: `https://api.avax.network/ext/bc/C/rpc`
  - Neon EVM: `https://neon-proxy-mainnet.solana.p2p.org`
- **Infura** (Optional): Ethereum RPC access with `INFURA_PROJECT_ID` for private endpoints.

### Market Data APIs
- **DeFiLlama**: Provides yield opportunities and TVL data.
- **CoinGecko**: Supplies token prices and market cap info.

### Python Libraries
- `streamlit==1.28.0`: Builds the web interface.
- `web3==6.11.0`: Handles blockchain interactions.
- `eth-account==0.9.0`: Manages wallet accounts.
- `eth-utils==2.2.0`: Ethereum utilities (e.g., unit conversion).
- `requests==2.31.0`: Makes API calls to DeFiLlama and CoinGecko.
- `python-dotenv==1.0.0`: Loads environment variables from `.env`.
- `sqlalchemy==2.0.23`: Manages database interactions.
- `psycopg2-binary==2.9.9`: PostgreSQL adapter.
- `alembic==1.12.1`: Handles database migrations.
- `typing-extensions==4.8.0`: Supports type hints.
- `streamlit-javascript==0.1.5`: Enables MetaMask transaction signing.

### Development Tools (Optional)
- `pytest==7.4.3`: For unit testing.
- `black==23.9.1`: For code formatting.
- `flake8==6.1.0`: For linting.

## Environment Variables
- `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://postgres:your_secure_password_here@localhost:5432/Defiscanner`).
- `INFURA_PROJECT_ID` (Optional): For private Ethereum RPC access.
- `ETH_RPC_URL`, `BSC_RPC_URL`, `ARBITRUM_RPC_URL`, `OPTIMISM_RPC_URL`, `BASE_RPC_URL`, `AVALANCHE_RPC_URL`, `NEON_RPC_URL`: Custom RPC endpoints (defaults to public URLs).
- `SECRET_KEY`: Secure key for session management (generate with `python -c "import secrets; print(secrets.token_hex(32))"`).

## Setup Instructions
1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd defi-dashboard