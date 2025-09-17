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
            window.ethereum.on('accountsChanged', this.handleAccountsChanged.bind(this));
            window.ethereum.on('chainChanged', this.handleChainChanged.bind(this));
            return {
                account: this.account,
                chainId: this.chainId,
                network: this.networkMap[this.chainId] || 'unknown'
            };
        } catch (error) {
            window.parent.postMessage({
                type: 'streamlit:walletError',
                error: error.message,
                code: error.code || 'UNKNOWN_ERROR'
            }, this.targetOrigin);
            throw error;
        }
    }

    async switchNetwork(targetChainId) {
        try {
            await window.ethereum.request({
                method: 'wallet_switchEthereumChain',
                params: [{ chainId: targetChainId }],
            });
            this.chainId = targetChainId;
            window.parent.postMessage({
                type: 'streamlit:networkSwitched',
                chainId: targetChainId,
                network: this.networkMap[targetChainId] || 'unknown'
            }, this.targetOrigin);
        } catch (switchError) {
            if (switchError.code === 4902) {
                await this.addNetwork(targetChainId);
            } else {
                window.parent.postMessage({
                    type: 'streamlit:walletError',
                    error: switchError.message,
                    code: switchError.code || 'SWITCH_FAILED'
                }, this.targetOrigin);
                throw switchError;
            }
        }
    }

    async addNetwork(chainId) {
        const networkConfigs = {
            '0x1': {
                chainId: '0x1',
                chainName: 'Ethereum Mainnet',
                nativeCurrency: { name: 'ETH', symbol: 'ETH', decimals: 18 },
                rpcUrls: ['https://eth.llamarpc.com', 'https://rpc.ankr.com/eth', 'https://ethereum.publicnode.com'],
                blockExplorerUrls: ['https://etherscan.io/']
            },
            '0x38': {
                chainId: '0x38',
                chainName: 'Binance Smart Chain',
                nativeCurrency: { name: 'BNB', symbol: 'BNB', decimals: 18 },
                rpcUrls: ['https://bsc-dataseed.binance.org/'],
                blockExplorerUrls: ['https://bscscan.com/']
            },
            '0xa4b1': {
                chainId: '0xa4b1',
                chainName: 'Arbitrum One',
                nativeCurrency: { name: 'ETH', symbol: 'ETH', decimals: 18 },
                rpcUrls: ['https://arb1.arbitrum.io/rpc'],
                blockExplorerUrls: ['https://arbiscan.io/']
            },
            '0xa': {
                chainId: '0xa',
                chainName: 'Optimism',
                nativeCurrency: { name: 'ETH', symbol: 'ETH', decimals: 18 },
                rpcUrls: ['https://mainnet.optimism.io'],
                blockExplorerUrls: ['https://optimistic.etherscan.io/']
            },
            '0x2105': {
                chainId: '0x2105',
                chainName: 'Base',
                nativeCurrency: { name: 'ETH', symbol: 'ETH', decimals: 18 },
                rpcUrls: ['https://mainnet.base.org'],
                blockExplorerUrls: ['https://basescan.org/']
            },
            '0xa86a': {
                chainId: '0xa86a',
                chainName: 'Avalanche C-Chain',
                nativeCurrency: { name: 'AVAX', symbol: 'AVAX', decimals: 18 },
                rpcUrls: ['https://api.avax.network/ext/bc/C/rpc'],
                blockExplorerUrls: ['https://snowtrace.io/']
            },
            '0xe9ac0ce': {
                chainId: '0xe9ac0ce',
                chainName: 'Neon EVM Mainnet',
                nativeCurrency: { name: 'NEON', symbol: 'NEON', decimals: 18 },
                rpcUrls: ['https://neon-proxy-mainnet.solana.p2p.org', 'https://mainnet.neonlabs.org'],
                blockExplorerUrls: ['https://neonscan.org/']
            }
        };

        const config = networkConfigs[chainId];
        if (!config) {
            const error = new Error(`Network configuration not found for chain ID: ${chainId}`);
            window.parent.postMessage({
                type: 'streamlit:walletError',
                error: error.message,
                code: 'INVALID_CHAIN_ID'
            }, this.targetOrigin);
            throw error;
        }

        await window.ethereum.request({
            method: 'wallet_addEthereumChain',
            params: [config]
        });
    }

    async signMessage(message) {
        if (!this.isConnected) {
            throw new Error('Wallet not connected');
        }
        try {
            return await window.ethereum.request({
                method: 'personal_sign',
                params: [message, this.account]
            });
        } catch (error) {
            window.parent.postMessage({
                type: 'streamlit:walletError',
                error: error.message,
                code: error.code || 'SIGN_FAILED'
            }, this.targetOrigin);
            throw error;
        }
    }

    async getBalance() {
        if (!this.isConnected || !this.ethersProvider) {
            return null;
        }
        try {
            const balanceWei = await this.ethersProvider.getBalance(this.account);
            return ethers.utils.formatEther(balanceWei);
        } catch (error) {
            window.parent.postMessage({
                type: 'streamlit:walletError',
                error: error.message,
                code: error.code || 'BALANCE_FAILED'
            }, this.targetOrigin);
            return null;
        }
    }

    async performDeFiAction(action, txData) {
        try {
            if (!this.isConnected || !this.ethersProvider) {
                throw new Error('Wallet not connected');
            }
            await this.switchNetwork(txData.chainId);
            const txHash = await window.ethereum.request({
                method: 'eth_sendTransaction',
                params: [{
                    from: this.account,
                    to: txData.to,
                    data: txData.data,
                    value: txData.value || '0x0',
                    gas: txData.gas || undefined
                }]
            });
            window.parent.postMessage({
                type: 'streamlit:txSuccess',
                action,
                txHash
            }, this.targetOrigin);
            return txHash;
        } catch (error) {
            window.parent.postMessage({
                type: 'streamlit:walletError',
                action,
                error: error.message,
                code: error.code || 'TX_FAILED'
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
        window.parent.postMessage({
            type: 'streamlit:accountsChanged',
            account: this.account
        }, this.targetOrigin);
    }

    handleChainChanged(chainId) {
        this.chainId = chainId;
        window.parent.postMessage({
            type: 'streamlit:chainChanged',
            chainId: chainId,
            network: this.networkMap[chainId] || 'unknown'
        }, this.targetOrigin);
    }

    disconnect() {
        this.isConnected = false;
        this.account = null;
        this.chainId = null;
        window.ethereum.removeListener('accountsChanged', this.handleAccountsChanged.bind(this));
        window.ethereum.removeListener('chainChanged', this.handleChainChanged.bind(this));
        this.ethersProvider = null;
        window.parent.postMessage({
            type: 'streamlit:disconnected'
        }, this.targetOrigin);
    }
}

// Global instance
window.metamaskConnector = new MetaMaskConnector();

// Helper functions for Streamlit
window.connectMetaMask = async () => {
    try {
        const result = await window.metamaskConnector.connectWallet();
        window.parent.postMessage({
            type: 'streamlit:walletConnected',
            ...result
        }, window.metamaskConnector.targetOrigin);
        return result;
    } catch (error) {
        window.parent.postMessage({
            type: 'streamlit:walletError',
            error: error.message,
            code: error.code || 'CONNECT_FAILED'
        }, window.metamaskConnector.targetOrigin);
        throw error;
    }
};

window.switchMetaMaskNetwork = async (chainId) => {
    try {
        await window.metamaskConnector.switchNetwork(chainId);
        return true;
    } catch (error) {
        window.parent.postMessage({
            type: 'streamlit:walletError',
            error: error.message,
            code: error.code || 'SWITCH_FAILED'
        }, window.metamaskConnector.targetOrigin);
        return false;
    }
};

window.signMetaMaskMessage = async (message) => {
    try {
        const signature = await window.metamaskConnector.signMessage(message);
        window.parent.postMessage({
            type: 'streamlit:signature',
            signature
        }, window.metamaskConnector.targetOrigin);
        return signature;
    } catch (error) {
        window.parent.postMessage({
            type: 'streamlit:walletError',
            error: error.message,
            code: error.code || 'SIGN_FAILED'
        }, window.metamaskConnector.targetOrigin);
        throw error;
    }
};

window.getMetaMaskBalance = async () => {
    try {
        const balance = await window.metamaskConnector.getBalance();
        window.parent.postMessage({
            type: 'streamlit:balance',
            balance
        }, window.metamaskConnector.targetOrigin);
        return balance;
    } catch (error) {
        window.parent.postMessage({
            type: 'streamlit:walletError',
            error: error.message,
            code: error.code || 'BALANCE_FAILED'
        }, window.metamaskConnector.targetOrigin);
        throw error;
    }
};

window.performDeFiAction = async (action, txData) => {
    try {
        const txHash = await window.metamaskConnector.performDeFiAction(action, txData);
        return txHash;
    } catch (error) {
        throw error;
    }
};