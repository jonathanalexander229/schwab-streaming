// Enhanced market_data.js - Fixed to handle mock mode properly
class MarketDataApp {
    constructor() {
        this.socket = io();
        this.marketData = {};
        this.watchlist = new Set();
        this.isMockMode = false;
        this.connectionStatusInitialized = false;
        
        // Set initial connection status
        this.updateConnectionStatus(false);
        
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
            console.log('Connected to server');
            // Check mock mode first, then update connection status
            this.checkMockMode().then(() => {
                this.updateConnectionStatus(true);
            });
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.updateConnectionStatus(false);
        });

        this.socket.on('market_data', (data) => {
            // Filter out non-equity data that might be sent accidentally
            if (this.isValidSymbol(data.symbol)) {
                this.updateMarketData(data.symbol, data.data);
                
                // Update mock mode status if provided
                if (data.is_mock !== undefined) {
                    this.isMockMode = data.is_mock;
                    this.updateMockModeUI();
                    // Update connection status with current mock mode
                    this.updateConnectionStatus(this.socket.connected);
                }
            } else {
                console.log('Filtered out invalid symbol:', data.symbol);
            }
        });

        this.socket.on('watchlist_updated', (data) => {
            // Filter the watchlist to only include valid symbols
            const validSymbols = data.watchlist.filter(symbol => this.isValidSymbol(symbol));
            this.watchlist = new Set(validSymbols);
        });

        this.socket.on('symbol_removed', (data) => {
            if (this.isValidSymbol(data.symbol)) {
                this.removeSymbolFromDisplay(data.symbol);
            }
        });

        this.socket.on('error', (error) => {
            console.error('Socket error:', error);
        });
    }

    isValidSymbol(symbol) {
        // Check if this looks like a valid stock symbol
        if (!symbol || typeof symbol !== 'string') return false;
        
        // Filter out debug/metadata symbols
        const invalidSymbols = [
            'data_source', 'is_mock_mode', 'market_data', 'timestamp', 
            'using_real_api', 'has_streamer', 'database_prefix'
        ];
        
        if (invalidSymbols.includes(symbol.toLowerCase())) return false;
        
        // Valid symbols are typically 1-5 characters, all uppercase letters
        const symbolRegex = /^[A-Z]{1,5}$/;
        return symbolRegex.test(symbol);
    }

    async checkMockMode() {
        try {
            const response = await fetch('/api/auth-status');
            const data = await response.json();
            
            console.log('Auth status response:', data);
            
            this.isMockMode = data.mock_mode || false;
            console.log('Mock mode set to:', this.isMockMode);
            
            this.updateMockModeUI();
            
            return data;
        } catch (error) {
            console.error('Failed to check mock mode:', error);
            return null;
        }
    }

    updateMockModeUI() {
        console.log('Updating mock mode UI, isMockMode:', this.isMockMode);
        
        // Update mock mode banner
        const mockBanner = document.getElementById('mockModeBanner');
        if (mockBanner) {
            if (this.isMockMode) {
                mockBanner.classList.remove('hidden');
                document.body.classList.add('mock-banner-visible');
            } else {
                mockBanner.classList.add('hidden');
                document.body.classList.remove('mock-banner-visible');
            }
        }

        // Update data source indicator
        const dataSourceIndicator = document.getElementById('dataSourceIndicator');
        if (dataSourceIndicator) {
            const icon = document.getElementById('dataSourceIcon');
            const text = document.getElementById('dataSourceText');
            
            if (this.isMockMode) {
                dataSourceIndicator.classList.remove('hidden', 'real-mode');
                dataSourceIndicator.classList.add('mock-mode');
                if (icon) icon.textContent = '🎭';
                if (text) text.textContent = 'MOCK DATA';
            } else {
                dataSourceIndicator.classList.remove('hidden', 'mock-mode');
                dataSourceIndicator.classList.add('real-mode');
                if (icon) icon.textContent = '✅';
                if (text) text.textContent = 'LIVE DATA';
            }
        }

        // Update page title
        const currentTitle = document.title;
        const baseTitle = currentTitle.replace(/^\[MOCK\] /, '').replace(/^\[LIVE\] /, '');
        
        if (this.isMockMode) {
            document.title = `[MOCK] ${baseTitle}`;
        } else {
            document.title = `[LIVE] ${baseTitle}`;
        }

        // Update last update info
        const lastUpdate = document.getElementById('lastUpdateTime');
        if (lastUpdate) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString();
            const sourceStr = this.isMockMode ? 'MOCK' : 'LIVE';
            lastUpdate.textContent = `Last update: ${timeStr} (${sourceStr})`;
        }

        // Update data source badge
        const badge = document.getElementById('dataSourceBadge');
        if (badge) {
            const badgeIcon = badge.querySelector('.badge-icon');
            const badgeText = badge.querySelector('.badge-text');
            
            if (this.isMockMode) {
                badge.classList.remove('hidden', 'real');
                badge.classList.add('mock');
                if (badgeIcon) badgeIcon.textContent = '🎭';
                if (badgeText) badgeText.textContent = 'MOCK';
            } else {
                badge.classList.remove('hidden', 'mock');
                badge.classList.add('real');
                if (badgeIcon) badgeIcon.textContent = '✅';
                if (badgeText) badgeText.textContent = 'LIVE';
            }
        }

        // Add mock test controls if in mock mode
        this.updateMockTestControls();
    }

    updateMockTestControls() {
        const testBtn = document.getElementById('mockTestBtn');
        if (testBtn) {
            if (this.isMockMode) {
                testBtn.classList.remove('hidden');
            } else {
                testBtn.classList.add('hidden');
            }
        }

        // Add mock test panel if it doesn't exist and we're in mock mode
        if (this.isMockMode && !document.getElementById('mockTestPanel')) {
            this.createMockTestPanel();
        } else if (!this.isMockMode && document.getElementById('mockTestPanel')) {
            // Remove mock test panel if not in mock mode
            const panel = document.getElementById('mockTestPanel');
            if (panel) panel.remove();
        }
    }

    createMockTestPanel() {
        const container = document.querySelector('.add-symbol-section');
        if (!container) return;
        
        const testPanel = document.createElement('div');
        testPanel.id = 'mockTestPanel';
        testPanel.className = 'mock-test-controls';
        testPanel.innerHTML = `
            <h3>🎯 Mock Market Events</h3>
            <div class="mock-event-buttons">
                <button class="mock-event-btn" onclick="app.triggerMockEvent('bullish_surge')">📈 Bull Run</button>
                <button class="mock-event-btn" onclick="app.triggerMockEvent('bearish_crash')">📉 Bear Crash</button>
                <button class="mock-event-btn" onclick="app.triggerMockEvent('high_volatility')">🌪️ High Volatility</button>
                <button class="mock-event-btn" onclick="app.triggerMockEvent('low_volatility')">😴 Low Volatility</button>
                <button class="mock-event-btn" onclick="app.triggerMockEvent('market_open')">🔔 Market Open</button>
                <button class="mock-event-btn" onclick="app.triggerMockEvent('market_close')">🔕 Market Close</button>
            </div>
        `;
        
        container.parentNode.insertBefore(testPanel, container.nextSibling);
    }

    async triggerMockEvent(eventType) {
        try {
            const response = await fetch('/api/test/market-event', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    event_type: eventType
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showEventNotification(eventType);
            } else {
                console.error('Failed to trigger event:', result.error);
                this.showEventNotification(`Error: ${result.error}`, true);
            }
        } catch (error) {
            console.error('Error triggering mock event:', error);
            this.showEventNotification('Connection error', true);
        }
    }

    showEventNotification(eventType, isError = false) {
        const eventNames = {
            'bullish_surge': '📈 Bullish Surge Triggered!',
            'bearish_crash': '📉 Bearish Crash Triggered!',
            'high_volatility': '🌪️ High Volatility Triggered!',
            'low_volatility': '😴 Low Volatility Triggered!',
            'market_open': '🔔 Market Open Simulated!',
            'market_close': '🔕 Market Close Simulated!'
        };
        
        const notification = document.createElement('div');
        notification.className = 'mock-event-notification';
        notification.textContent = eventNames[eventType] || eventType;
        notification.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            background: ${isError ? '#f44336' : '#ff9800'};
            color: white;
            padding: 12px 20px;
            border-radius: 5px;
            z-index: 1001;
            font-weight: bold;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            animation: slideInRight 0.3s ease-out;
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOutRight 0.3s ease-in';
            setTimeout(() => {
                if (document.body.contains(notification)) {
                    document.body.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }

    updateConnectionStatus(connected) {
        console.log('Updating connection status:', { connected, isMockMode: this.isMockMode });
        
        const statusDot = document.getElementById('connectionStatus');
        const statusText = document.getElementById('connectionText');
        
        if (statusDot && statusText) {
            if (connected) {
                statusDot.classList.add('connected');
                if (this.isMockMode) {
                    statusText.textContent = 'Mock Connected';
                    statusDot.classList.add('mock-connected');
                    statusDot.classList.remove('real-connected');
                } else {
                    statusText.textContent = 'Live Connected';
                    statusDot.classList.add('real-connected');
                    statusDot.classList.remove('mock-connected');
                }
            } else {
                statusDot.classList.remove('connected', 'mock-connected', 'real-connected');
                statusText.textContent = 'Disconnected';
            }
        }
        
        this.connectionStatusInitialized = true;
    }

    addSymbol() {
        const input = document.getElementById('symbolInput');
        const symbol = input.value.trim().toUpperCase();
        
        if (!symbol) return;
        
        // Validate symbol format
        if (!this.isValidSymbol(symbol)) {
            alert('Please enter a valid stock symbol (1-5 letters, e.g., AAPL, MSFT)');
            return;
        }
        
        if (this.watchlist.has(symbol)) {
            alert(`${symbol} is already in your watchlist`);
            return;
        }
        
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
        // Only process valid symbols
        if (!this.isValidSymbol(symbol)) {
            return;
        }

        this.marketData[symbol] = data;
        
        const container = document.getElementById('marketDataContainer');
        let card = document.getElementById('card-' + symbol);
        
        if (!card) {
            card = this.createStockCard(symbol);
            container.appendChild(card);
        }
        
        this.updateStockCard(card, symbol, data);
        
        // Add mock/real styling to cards
        if (this.isMockMode) {
            card.classList.add('mock-data');
            card.classList.remove('real-data');
        } else {
            card.classList.add('real-data');
            card.classList.remove('mock-data');
        }
        
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
        
        if (data.last_price != null && typeof data.last_price === 'number') {
            document.getElementById('price-' + symbol).textContent = '$' + data.last_price.toFixed(2);
        }
        
        if (data.net_change != null && typeof data.net_change === 'number') {
            const changeEl = document.getElementById('change-' + symbol);
            const change = data.net_change;
            const changeClass = change > 0 ? 'positive' : (change < 0 ? 'negative' : 'neutral');
            const changeSign = change > 0 ? '+' : '';
            
            changeEl.textContent = changeSign + '$' + change.toFixed(2);
            changeEl.className = 'change-amount ' + changeClass;
        }
        
        if (data.net_change_percent != null && typeof data.net_change_percent === 'number') {
            const percentEl = document.getElementById('percent-' + symbol);
            const percent = data.net_change_percent;
            const percentClass = percent > 0 ? 'positive' : (percent < 0 ? 'negative' : 'neutral');
            const percentSign = percent > 0 ? '+' : '';
            
            percentEl.textContent = percentSign + percent.toFixed(2) + '%';
            percentEl.className = 'change-percent ' + percentClass;
        }
        
        if (data.bid_price != null && typeof data.bid_price === 'number') document.getElementById('bid-' + symbol).textContent = '$' + data.bid_price.toFixed(2);
        if (data.ask_price != null && typeof data.ask_price === 'number') document.getElementById('ask-' + symbol).textContent = '$' + data.ask_price.toFixed(2);
        if (data.high_price != null && typeof data.high_price === 'number') document.getElementById('high-' + symbol).textContent = '$' + data.high_price.toFixed(2);
        if (data.low_price != null && typeof data.low_price === 'number') document.getElementById('low-' + symbol).textContent = '$' + data.low_price.toFixed(2);
        if (data.volume != null && typeof data.volume === 'number') document.getElementById('volume-' + symbol).textContent = this.formatVolume(data.volume);
        
        if (data.timestamp) {
            const date = new Date(data.timestamp);
            const source = this.isMockMode ? 'MOCK' : 'LIVE';
            document.getElementById('timestamp-' + symbol).textContent = `Last updated: ${date.toLocaleTimeString()} (${source})`;
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

    async loadInitialData() {
        // First check mock mode
        const authData = await this.checkMockMode();
        
        // Then update connection status after a brief delay to ensure socket is ready
        setTimeout(() => {
            if (this.socket.connected) {
                this.updateConnectionStatus(true);
            }
        }, 500);

        // Load watchlist
        fetch('/api/watchlist')
            .then(response => response.json())
            .then(data => {
                if (data.watchlist) {
                    // Filter watchlist to only valid symbols
                    const validSymbols = data.watchlist.filter(symbol => this.isValidSymbol(symbol));
                    this.watchlist = new Set(validSymbols);
                    validSymbols.forEach(symbol => this.addPlaceholderCard(symbol));
                }
            })
            .catch(error => {
                console.error('Error loading watchlist:', error);
            });

        // Load market data
        fetch('/api/market-data')
            .then(response => response.json())
            .then(data => {
                console.log('Market data response:', data);
                
                // Handle the market data response properly
                if (data.market_data) {
                    Object.entries(data.market_data).forEach(([symbol, symbolData]) => {
                        if (this.isValidSymbol(symbol)) {
                            this.updateMarketData(symbol, symbolData);
                        }
                    });
                }
                
                // Update mock mode status if provided
                if (data.is_mock_mode !== undefined) {
                    this.isMockMode = data.is_mock_mode;
                    this.updateMockModeUI();
                    // Update connection status with current mock mode
                    this.updateConnectionStatus(this.socket.connected);
                }
            })
            .catch(error => {
                console.error('Error loading market data:', error);
            });
    }
}

// Global function for triggering mock events
function triggerMockEvent() {
    if (window.app && window.app.isMockMode) {
        // Trigger a random event for the button click
        const events = ['bullish_surge', 'bearish_crash', 'high_volatility'];
        const randomEvent = events[Math.floor(Math.random() * events.length)];
        window.app.triggerMockEvent(randomEvent);
    }
}

// Global function for hiding mock banner
function hideMockBanner() {
    const banner = document.getElementById('mockModeBanner');
    if (banner) {
        banner.classList.add('hidden');
        document.body.classList.remove('mock-banner-visible');
        
        // Store preference
        localStorage.setItem('mockBannerDismissed', 'true');
    }
}

let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new MarketDataApp();
    
    // Check if banner was previously dismissed
    if (localStorage.getItem('mockBannerDismissed') === 'true') {
        setTimeout(() => {
            hideMockBanner();
        }, 1000);
    }
});

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);