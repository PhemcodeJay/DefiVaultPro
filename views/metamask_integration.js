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
            '0xe9ac0ce': 'neon'
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

            // 🔗 Sync to Streamlit
            const result = {
                account: this.account,
                chainId: this.chainId,
                network: this.networkMap[this.chainId] || 'unknown'
            };
            window.lastMessage = { type: 'streamlit:walletConnected', ...result };
            window.parent.postMessage(window.lastMessage, this.targetOrigin);

            // Register listeners
            window.ethereum.on('accountsChanged', this.handleAccountsChanged.bind(this));
            window.ethereum.on('chainChanged', this.handleChainChanged.bind(this));

            return result;
        } catch (error) {
            window.parent.postMessage({
                type: 'streamlit:walletError',
                error: error.message,
                code: error.code || 'UNKNOWN_ERROR'
            }, this.targetOrigin);
            throw error;
        }
    }

    handleAccountsChanged(accounts) {
        if (accounts.length === 0) {
            this.isConnected = false;
            this.account = null;
        } else {
            this.account = accounts[0];
        }

        const msg = {
            type: 'streamlit:accountsChanged',
            account: this.account
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

        window.ethereum.removeListener('accountsChanged', this.handleAccountsChanged.bind(this));
        window.ethereum.removeListener('chainChanged', this.handleChainChanged.bind(this));
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

// Optional: get last known state
window.getMetaMaskState = () => {
    return window.lastMessage || null;
};
