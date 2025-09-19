class MetaMaskConnector {
    constructor() {
        this.isConnected = false;
        this.account = null;
        this.chainId = null;
        this.networkMap = {
            '0x1': 'ethereum',
            '0x38': 'bsc',
            '0xa4b1': 'arbitrum',
            '0xa': 'optimism',
            '0x2105': 'base',
            '0xa86a': 'avalanche',
            '0xe9ac0ce': 'neon',
            '0x89': 'polygon',
            '0xfa': 'fantom',
            '0x63564c40': 'solana',
            '0x4e454152': 'aurora',
            '0x19': 'cronos'
        };
        this.ethersProvider = null;
        this.targetOrigin = window.location.origin;
    }

    async checkMetaMaskAvailable() {
        if (typeof window.ethereum !== 'undefined' && typeof window.ethers !== 'undefined') {
            this.ethersProvider = new ethers.providers.Web3Provider(window.ethereum);
            return true;
        }
        throw new Error('MetaMask or ethers.js not installed. Please install MetaMask extension.');
    }

    async connectWallet() {
        try {
            await this.checkMetaMaskAvailable();
            const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
            this.account = accounts[0];
            this.chainId = await window.ethereum.request({ method: 'eth_chainId' });
            this.isConnected = true;

            const result = {
                type: 'streamlit:walletConnected',
                account: this.account,
                chainId: this.chainId,
                network: this.networkMap[this.chainId] || 'unknown'
            };
            window.lastMessage = result;
            window.parent.postMessage(result, this.targetOrigin);

            // Register listeners
            window.ethereum.on('accountsChanged', this.handleAccountsChanged.bind(this));
            window.ethereum.on('chainChanged', this.handleChainChanged.bind(this));

            return result;
        } catch (error) {
            const errorMsg = {
                type: 'streamlit:walletError',
                error: error.message,
                code: error.code || 'UNKNOWN_ERROR'
            };
            window.lastMessage = errorMsg;
            window.parent.postMessage(errorMsg, this.targetOrigin);
            throw error;
        }
    }

    async connectWalletConnect(projectId) {
        try {
            const { WalletConnectModal } = window.WalletConnectModal;
            const modal = new WalletConnectModal({
                projectId: projectId,
                chains: [
                    1,      // Ethereum
                    56,     // BSC
                    42161,  // Arbitrum
                    10,     // Optimism
                    8453,   // Base
                    43114,  // Avalanche
                    245022934, // Neon
                    137,    // Polygon
                    250,    // Fantom
                    7562605, // Solana
                    1313161554, // Aurora
                    25      // Cronos
                ],
                themeMode: 'dark',
                explorerExcludedWalletIds: 'ALL',
                explorerRecommendedWalletIds: [
                    'c5f6866f-3d9b-477e-9b5c-0b1b1b5c4e8c' // MetaMask ID
                ]
            });

            const session = await modal.connect();
            const account = session?.namespaces?.eip155?.accounts?.[0]?.split(':')[2] || null;
            const chainId = session?.namespaces?.eip155?.chains?.[0] || '0x1';
            this.account = account;
            this.chainId = chainId;
            this.isConnected = !!account;

            const result = {
                type: 'streamlit:walletConnected',
                account: account,
                chainId: chainId,
                network: this.networkMap[chainId] || 'unknown'
            };
            window.lastMessage = result;
            window.parent.postMessage(result, this.targetOrigin);

            return result;
        } catch (error) {
            const errorMsg = {
                type: 'streamlit:walletError',
                error: error.message,
                code: error.code || 'UNKNOWN_ERROR'
            };
            window.lastMessage = errorMsg;
            window.parent.postMessage(errorMsg, this.targetOrigin);
            throw error;
        }
    }

    handleAccountsChanged(accounts) {
        this.isConnected = accounts.length > 0;
        this.account = accounts.length > 0 ? accounts[0] : null;

        const msg = {
            type: 'streamlit:accountsChanged',
            account: this.account,
            chainId: this.chainId,
            network: this.networkMap[this.chainId] || 'unknown'
        };
        window.lastMessage = msg;
        window.parent.postMessage(msg, this.targetOrigin);
    }

    handleChainChanged(chainId) {
        this.chainId = chainId;

        const msg = {
            type: 'streamlit:chainChanged',
            chainId: chainId,
            network: this.networkMap[chainId] || 'unknown'
        };
        window.lastMessage = msg;
        window.parent.postMessage(msg, this.targetOrigin);
    }

    disconnect() {
        this.isConnected = false;
        this.account = null;
        this.chainId = null;

        if (window.ethereum) {
            window.ethereum.removeListener('accountsChanged', this.handleAccountsChanged.bind(this));
            window.ethereum.removeListener('chainChanged', this.handleChainChanged.bind(this));
        }
        this.ethersProvider = null;

        const msg = { type: 'streamlit:disconnected' };
        window.lastMessage = msg;
        window.parent.postMessage(msg, this.targetOrigin);
    }
}

// Global instance
window.metamaskConnector = new MetaMaskConnector();

// Helper function to connect MetaMask
window.connectMetaMask = async () => {
    try {
        return await window.metamaskConnector.connectWallet();
    } catch (error) {
        throw error;
    }
};

// Helper function to connect WalletConnect
window.connectWalletConnect = async (projectId) => {
    try {
        return await window.metamaskConnector.connectWalletConnect(projectId);
    } catch (error) {
        throw error;
    }
};

// Helper function to disconnect
window.disconnectWallet = async () => {
    try {
        window.metamaskConnector.disconnect();
    } catch (error) {
        throw error;
    }
};

// Optional: get last known state
window.getMetaMaskState = () => {
    return window.lastMessage || null;
};