// Mock Mode UI Management
class MockModeManager {
    constructor() {
        this.isMockMode = false;
        this.mockBannerDismissed = false;
        this.checkInterval = null;
        
        this.init();
    }
    
    init() {
        // Check auth status on page load
        this.checkAuthStatus();
        
        // Set up periodic checks
        this.checkInterval = setInterval(() => {
            this.checkAuthStatus();
        }, 10000); // Check every 10 seconds
        
        // Handle page visibility changes
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.checkAuthStatus();
            }
        });
    }
    
    async checkAuthStatus() {
        try {
            const response = await fetch('/api/auth-status');
            const data = await response.json();
            
            const wasMockMode = this.isMockMode;
            this.isMockMode = data.mock_mode || false;
            
            // Update UI if mode changed
            if (wasMockMode !== this.isMockMode) {
                this.updateUI();
            }
            
            // Update connection status
            this.updateConnectionStatus(data);
            
        } catch (error) {
            console.error('Failed to check auth status:', error);
        }
    }
    
    updateUI() {
        // Update body class
        document.body.classList.toggle('mock-mode-active', this.isMockMode);
        document.body.classList.toggle('real-mode-active', !this.isMockMode);
        
        // Update mock banner
        this.updateMockBanner();
        
        // Update data source indicators
        this.updateDataSourceIndicators();
        
        // Update page title
        this.updatePageTitle();
        
        // Update mock test controls
        this.updateMockTestControls();
        
        console.log(`UI updated for ${this.isMockMode ? 'MOCK' : 'REAL'} mode`);
    }
    
    updateMockBanner() {
        const banner = document.getElementById('mockModeBanner');
        if (!banner) return;
        
        if (this.isMockMode && !this.mockBannerDismissed) {
            banner.classList.remove('hidden');
            document.body.classList.add('mock-banner-visible');
        } else {
            banner.classList.add('hidden');
            document.body.classList.remove('mock-banner-visible');
        }
    }
    
    updateDataSourceIndicators() {
        // Header indicator
        const headerIndicator = document.getElementById('dataSourceIndicator');
        if (headerIndicator) {
            const icon = document.getElementById('dataSourceIcon');
            const text = document.getElementById('dataSourceText');
            
            if (this.isMockMode) {
                headerIndicator.classList.remove('hidden', 'real-mode');
                headerIndicator.classList.add('mock-mode');
                if (icon) icon.textContent = '🎭';
                if (text) text.textContent = 'MOCK DATA';
            } else {
                headerIndicator.classList.remove('hidden', 'mock-mode');
                headerIndicator.classList.add('real-mode');
                if (icon) icon.textContent = '✅';
                if (text) text.textContent = 'LIVE DATA';
            }
        }
        
        // Watchlist badge
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
    }
    
    updatePageTitle() {
        const currentTitle = document.title;
        const baseTitle = currentTitle.replace(/^\[MOCK\] /, '').replace(/^\[LIVE\] /, '');
        
        if (this.isMockMode) {
            document.title = `[MOCK] ${baseTitle}`;
        } else {
            document.title = `[LIVE] ${baseTitle}`;
        }
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
        
        // Add mock test panel if it doesn't exist
        if (this.isMockMode && !document.getElementById('mockTestPanel')) {
            this.createMockTestPanel();
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
                <button class="mock-event-btn" onclick="mockManager.triggerEvent('bullish_surge')">📈 Bull Run</button>
                <button class="mock-event-btn" onclick="mockManager.triggerEvent('bearish_crash')">📉 Bear Crash</button>
                <button class="mock-event-btn" onclick="mockManager.triggerEvent('high_volatility')">🌪️ High Volatility</button>
                <button class="mock-event-btn" onclick="mockManager.triggerEvent('low_volatility')">😴 Low Volatility</button>
                <button class="mock-event-btn" onclick="mockManager.triggerEvent('market_open')">🔔 Market Open</button>
                <button class="mock-event-btn" onclick="mockManager.triggerEvent('market_close')">🔕 Market Close</button>
            </div>
        `;
        
        container.parentNode.insertBefore(testPanel, container.nextSibling);
    }
    
    updateConnectionStatus(authData) {
        const statusDot = document.getElementById('connectionStatus');
        const statusText = document.getElementById('connectionText');
        
        if (statusDot && statusText) {
            if (authData.authenticated) {
                statusDot.classList.add('connected');
                if (authData.mock_mode) {
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
    }
    
    async triggerEvent(eventType) {
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
            }
        } catch (error) {
            console.error('Error triggering mock event:', error);
        }
    }
    
    showEventNotification(eventType) {
        const eventNames = {
            'bullish_surge': '📈 Bullish Surge Triggered',
            'bearish_crash': '📉 Bearish Crash Triggered',
            'high_volatility': '🌪️ High Volatility Triggered',
            'low_volatility': '😴 Low Volatility Triggered',
            'market_open': '🔔 Market Open Simulated',
            'market_close': '🔕 Market Close Simulated'
        };
        
        const notification = document.createElement('div');
        notification.className = 'mock-event-notification';
        notification.textContent = eventNames[eventType] || `Event ${eventType} triggered`;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOutRight 0.3s ease-in';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }
    
    hideBanner() {
        this.mockBannerDismissed = true;
        this.updateMockBanner();
        
        // Store preference
        localStorage.setItem('mockBannerDismissed', 'true');
    }
    
    destroy() {
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
        }
    }
}

// Global functions for template usage
function hideMockBanner() {
    if (window.mockManager) {
        window.mockManager.hideBanner();
    }
}

function triggerMockEvent() {
    if (window.mockManager) {
        // Trigger a random event for the button click
        const events = ['bullish_surge', 'bearish_crash', 'high_volatility'];
        const randomEvent = events[Math.floor(Math.random() * events.length)];
        window.mockManager.triggerEvent(randomEvent);
    }
}

// Enhanced MarketDataApp integration
if (typeof MarketDataApp !== 'undefined') {
    const originalUpdateMarketData = MarketDataApp.prototype.updateMarketData;
    MarketDataApp.prototype.updateMarketData = function(symbol, data) {
        // Call original method
        originalUpdateMarketData.call(this, symbol, data);
        
        // Add mock/real styling to cards
        const card = document.getElementById('card-' + symbol);
        if (card && window.mockManager) {
            if (window.mockManager.isMockMode) {
                card.classList.add('mock-data');
                card.classList.remove('real-data');
            } else {
                card.classList.add('real-data');
                card.classList.remove('mock-data');
            }
        }
        
        // Update last update time
        const lastUpdate = document.getElementById('lastUpdateTime');
        if (lastUpdate) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString();
            const sourceStr = window.mockManager && window.mockManager.isMockMode ? 'MOCK' : 'LIVE';
            lastUpdate.textContent = `Last update: ${timeStr} (${sourceStr})`;
        }
    };
}

// Initialize mock manager when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.mockManager = new MockModeManager();
    
    // Check if banner was previously dismissed
    if (localStorage.getItem('mockBannerDismissed') === 'true') {
        window.mockManager.mockBannerDismissed = true;
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.mockManager) {
        window.mockManager.destroy();
    }
});