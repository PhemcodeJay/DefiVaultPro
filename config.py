import os

# Centralized configuration for DeFi Dashboard

# defi_scanner.py configurations
MIN_APY = 5  # Minimum APY threshold for yield opportunities (%)
MIN_TVL = 100_000  # Minimum TVL threshold for yield opportunities (USD)
FOCUS_PROTOCOLS = ["aave", "compound", "uniswap", "curve"]  # DeFi protocols to prioritize
MEME_CHAINS = ["ethereum", "bsc", "solana"]  # Blockchain networks for meme coin scanning
RESCAN_INTERVAL = 3600  # Rescan interval for data fetching (seconds, 1 hour)
YIELDS_API_URL = "https://yields.llama.fi/pools"  # DeFiLlama API endpoint for yield data
MEME_API_URL = "https://api.dexscreener.com/latest/dex/search"  # DexScreener API endpoint for meme coins

# utils.py configurations
RPC_URLS = {
    "ethereum": os.getenv("ETH_RPC_URL", "https://mainnet.infura.io/v3/" + os.getenv("INFURA_PROJECT_ID", "")),
    "bsc": os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/"),
    "arbitrum": os.getenv("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc"),
    "optimism": os.getenv("OPTIMISM_RPC_URL", "https://mainnet.optimism.io"),
    "base": os.getenv("BASE_RPC_URL", "https://mainnet.base.org"),
    "avalanche": os.getenv("AVALANCHE_RPC_URL", "https://api.avax.network/ext/bc/C/rpc"),
    "neon": os.getenv("NEON_RPC_URL", "https://neon-proxy-mainnet.solana.p2p.org"),
}

# wallet_utils.py configurations
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
        "DAI": "0x6b175474e89094c44da98b954eedeac495271d0f",
        "WETH": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    },
    "arbitrum": {
        "USDC": "0xaf88d065e77c8cc2239327c5edb3a432268e5831",
        "USDT": "0xfd086bc7cd5c481dcc9c85ebe478a1c0b99fc7a1",
        "DAI": "0xda10009cbd5d07dd0cecc66161fc93d7bf3513e0"
    }
}

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

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "success", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "success", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_from", "type": "address"},
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transferFrom",
        "outputs": [{"name": "success", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": True, "name": "spender", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Approval",
        "type": "event"
    }
]

AAVE_POOL_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "asset", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {"internalType": "address", "name": "onBehalfOf", "type": "address"},
            {"internalType": "uint16", "name": "referralCode", "type": "uint16"}
        ],
        "name": "supply",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "asset", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {"internalType": "address", "name": "onBehalfOf", "type": "address"}
        ],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "user", "type": "address"}
        ],
        "name": "getUserAccountData",
        "outputs": [
            {"internalType": "uint256", "name": "totalCollateralBase", "type": "uint256"},
            {"internalType": "uint256", "name": "totalDebtBase", "type": "uint256"},
            {"internalType": "uint256", "name": "availableBorrowsBase", "type": "uint256"},
            {"internalType": "uint256", "name": "currentLiquidationThreshold", "type": "uint256"},
            {"internalType": "uint256", "name": "ltv", "type": "uint256"},
            {"internalType": "uint256", "name": "healthFactor", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

COMPOUND_COMET_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "asset", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "supply",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "asset", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "user", "type": "address"}
        ],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

explorer_urls = {
        "ethereum": "https://etherscan.io/tx/",
        "bsc": "https://bscscan.com/tx/",
        "arbitrum": "https://arbiscan.io/tx/",
        "optimism": "https://optimistic.etherscan.io/tx/",
        "base": "https://basescan.org/tx/",
        "avalanche": "https://snowtrace.io/tx/",
        "neon": "https://neonscan.org/tx/",
        "polygon": "https://polygonscan.com/tx/",
        "fantom": "https://ftmscan.com/tx/",
        "solana": "https://solscan.io/tx/",
        "aurora": "https://aurorascan.dev/tx/",
        "cronos": "https://cronoscan.com/tx/"
    }