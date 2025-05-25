class MarketDataApp {
    constructor() {
        this.socket = io();
        this.marketData = {};
        this.watchlist = new Set();
        this.initializeEventListeners();
        this.setupSocketHandlers();
        this.loadInitialData();
    }

    initializeEventListeners() {
        document.getElementById('symbolInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.addSymbol();
        });
    }

    setupSocketHandlers() {
        this.socket.on('connect', () => {
            console.log('Connected');
            this.updateConnectionStatus(true);
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected');
            this.updateConnectionStatus(false);
        });

        this.socket.on('market_data', (data) => {
            this.updateMarketData(data.symbol, data.data);
        });

        this.socket.on('watchlist_updated', (data) => {
            this.watchlist = new Set(data.watchlist);
        });

        this.socket.on('symbol_removed', (data) => {
            this.removeSymbolFromDisplay(data.symbol);
        });
    }

    updateConnectionStatus(connected) {
        const statusDot = document.getElementById('connectionStatus');
        const statusText = document.getElementById('connectionText');
        
        if (statusDot && statusText) {
            if (connected) {
                statusDot.classList.add('connected');
                statusText.textContent = 'Connected';
            } else {
                statusDot.classList.remove('connected');
                statusText.textContent = 'Disconnected';
            }
        }
    }

    addSymbol() {
        const input = document.getElementById('symbolInput');
        const symbol = input.value.trim().toUpperCase();
        
        if (!symbol || this.watchlist.has(symbol)) return;
        
        this.socket.emit('add_symbol', {symbol: symbol});
        this.watchlist.add(symbol);
        input.value = '';
        this.addPlaceholderCard(symbol);
    }

    removeSymbol(symbol) {
        this.socket.emit('remove_symbol', {symbol: symbol});
        this.watchlist.delete(symbol);
        this.removeSymbolFromDisplay(symbol);
    }

    updateMarketData(symbol, data) {
        this.marketData[symbol] = data;
        
        const container = document.getElementById('marketDataContainer');
        let card = document.getElementById('card-' + symbol);
        
        if (!card) {
            card = this.createStockCard(symbol);
            container.appendChild(card);
        }
        
        this.updateStockCard(card, symbol, data);
        
        const noData = container.querySelector('.no-data');
        if (noData && Object.keys(this.marketData).length > 0) {
            noData.remove();
        }
    }

    createStockCard(symbol) {
        const card = document.createElement('div');
        card.className = 'stock-card';
        card.id = 'card-' + symbol;
        
        card.innerHTML = `
            <div class="stock-header">
                <div class="stock-symbol">${symbol}</div>
                <button class="remove-btn" onclick="app.removeSymbol('${symbol}')" title="Remove">×</button>
            </div>
            <div class="price-main">
                <div class="current-price" id="price-${symbol}">--</div>
                <div class="price-change">
                    <span class="change-amount neutral" id="change-${symbol}">--</span>
                    <span class="change-percent neutral" id="percent-${symbol}">--</span>
                </div>
            </div>
            <div class="price-details">
                <div class="price-item">
                    <span class="price-label">Bid:</span>
                    <span class="price-value" id="bid-${symbol}">--</span>
                </div>
                <div class="price-item">
                    <span class="price-label">Ask:</span>
                    <span class="price-value" id="ask-${symbol}">--</span>
                </div>
                <div class="price-item">
                    <span class="price-label">High:</span>
                    <span class="price-value" id="high-${symbol}">--</span>
                </div>
                <div class="price-item">
                    <span class="price-label">Low:</span>
                    <span class="price-value" id="low-${symbol}">--</span>
                </div>
                <div class="price-item">
                    <span class="price-label">Volume:</span>
                    <span class="price-value" id="volume-${symbol}">--</span>
                </div>
            </div>
            <div class="timestamp" id="timestamp-${symbol}">Waiting for data...</div>
        `;
        
        return card;
    }

    addPlaceholderCard(symbol) {
        const container = document.getElementById('marketDataContainer');
        const noData = container.querySelector('.no-data');
        if (noData) noData.remove();
        
        if (!document.getElementById('card-' + symbol)) {
            const card = this.createStockCard(symbol);
            container.appendChild(card);
        }
    }

    updateStockCard(card, symbol, data) {
        card.classList.add('flash');
        setTimeout(() => card.classList.remove('flash'), 500);
        
        if (data.last_price != null) {
            document.getElementById('price-' + symbol).textContent = ' + data.last_price.toFixed(2);
        }
        
        if (data.net_change != null) {
            const changeEl = document.getElementById('change-' + symbol);
            const change = data.net_change;
            const changeClass = change > 0 ? 'positive' : (change < 0 ? 'negative' : 'neutral');
            const changeSign = change > 0 ? '+' : '';
            
            changeEl.textContent = changeSign + ' + change.toFixed(2);
            changeEl.className = 'change-amount ' + changeClass;
        }
        
        if (data.net_change_percent != null) {
            const percentEl = document.getElementById('percent-' + symbol);
            const percent = data.net_change_percent;
            const percentClass = percent > 0 ? 'positive' : (percent < 0 ? 'negative' : 'neutral');
            const percentSign = percent > 0 ? '+' : '';
            
            percentEl.textContent = percentSign + percent.toFixed(2) + '%';
            percentEl.className = 'change-percent ' + percentClass;
        }
        
        if (data.bid_price != null) document.getElementById('bid-' + symbol).textContent = ' + data.bid_price.toFixed(2);
        if (data.ask_price != null) document.getElementById('ask-' + symbol).textContent = ' + data.ask_price.toFixed(2);
        if (data.high_price != null) document.getElementById('high-' + symbol).textContent = ' + data.high_price.toFixed(2);
        if (data.low_price != null) document.getElementById('low-' + symbol).textContent = ' + data.low_price.toFixed(2);
        if (data.volume != null) document.getElementById('volume-' + symbol).textContent = this.formatVolume(data.volume);
        
        if (data.timestamp) {
            const date = new Date(data.timestamp);
            document.getElementById('timestamp-' + symbol).textContent = 'Last updated: ' + date.toLocaleTimeString();
        }
    }

    removeSymbolFromDisplay(symbol) {
        const card = document.getElementById('card-' + symbol);
        if (card) card.remove();
        
        delete this.marketData[symbol];
        
        const container = document.getElementById('marketDataContainer');
        if (Object.keys(this.marketData).length === 0 && !container.querySelector('.no-data')) {
            container.innerHTML = '<div class="no-data">Add some stock symbols to start streaming market data!</div>';
        }
    }

    formatVolume(volume) {
        if (volume >= 1000000) return (volume / 1000000).toFixed(1) + 'M';
        if (volume >= 1000) return (volume / 1000).toFixed(1) + 'K';
        return volume.toString();
    }

    loadInitialData() {
        fetch('/api/watchlist')
            .then(response => response.json())
            .then(data => {
                if (data.watchlist) {
                    this.watchlist = new Set(data.watchlist);
                    data.watchlist.forEach(symbol => this.addPlaceholderCard(symbol));
                }
            });

        fetch('/api/market-data')
            .then(response => response.json())
            .then(data => {
                Object.entries(data).forEach(([symbol, symbolData]) => {
                    this.updateMarketData(symbol, symbolData);
                });
            });
    }
}

let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new MarketDataApp();
});