// Options Flow JavaScript
class OptionsFlowApp {
    constructor() {
        this.socket = io();
        this.charts = {};
        this.currentSymbol = 'SPY';
        this.maxDataPoints = 50;
        this.lastUpdate = null;
        
        // Data storage
        this.historicalData = {
            timestamps: [],
            callDeltas: [],
            putDeltas: [],
            netDeltas: [],
            callVolume: [],
            putVolume: [],
            underlyingPrices: []
        };
        
        this.initializeEventListeners();
        this.setupSocketHandlers();
        this.initializeCharts();
        this.updateConnectionStatus(false);
        this.loadInitialData();
    }

    initializeEventListeners() {
        // Symbol input enter key
        document.getElementById('symbolInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.changeSymbol();
        });
    }

    setupSocketHandlers() {
        this.socket.on('connect', () => {
            console.log('Connected to options flow server');
            this.updateConnectionStatus(true);
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from options flow server');
            this.updateConnectionStatus(false);
        });

        this.socket.on('options_flow_data', (data) => {
            this.updateOptionsData(data);
        });

        this.socket.on('error', (error) => {
            console.error('Socket error:', error);
            this.showError('Connection error: ' + error.message);
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

    changeSymbol() {
        const input = document.getElementById('symbolInput');
        const newSymbol = input.value.trim().toUpperCase();
        
        if (!newSymbol) {
            this.showError('Please enter a valid symbol');
            return;
        }
        
        if (newSymbol === this.currentSymbol) {
            return;
        }
        
        this.currentSymbol = newSymbol;
        this.clearHistoricalData();
        
        // Emit symbol change to server
        this.socket.emit('change_options_symbol', {symbol: newSymbol});
        
        console.log(`Changed options monitoring to ${newSymbol}`);
    }

    clearHistoricalData() {
        // Clear all historical data
        Object.keys(this.historicalData).forEach(key => {
            this.historicalData[key] = [];
        });
        
        // Clear charts
        Object.values(this.charts).forEach(chart => {
            if (chart && chart.data && chart.data.datasets) {
                chart.data.datasets.forEach(dataset => {
                    dataset.data = [];
                });
                chart.update('none');
            }
        });
    }

    initializeCharts() {
        // Delta Volume Chart
        const deltaCtx = document.getElementById('deltaVolumeChart').getContext('2d');
        this.charts.deltaVolume = new Chart(deltaCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Call Δ×Volume',
                        data: [],
                        borderColor: '#4caf50',
                        backgroundColor: 'rgba(76, 175, 80, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: 'Put Δ×Volume',
                        data: [],
                        borderColor: '#f44336',
                        backgroundColor: 'rgba(244, 67, 54, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            displayFormats: {
                                minute: 'HH:mm'
                            }
                        },
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Delta × Volume'
                        },
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        position: 'top'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.dataset.label + ': ' + context.parsed.y.toLocaleString();
                            }
                        }
                    }
                }
            }
        });

        // Net Delta Chart
        const netCtx = document.getElementById('netDeltaChart').getContext('2d');
        this.charts.netDelta = new Chart(netCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Net Delta',
                    data: [],
                    borderColor: '#9c27b0',
                    backgroundColor: function(context) {
                        const value = context.parsed?.y || 0;
                        return value >= 0 ? 'rgba(76, 175, 80, 0.1)' : 'rgba(244, 67, 54, 0.1)';
                    },
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            displayFormats: {
                                minute: 'HH:mm'
                            }
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Net Delta'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });

        // Volume Chart
        const volCtx = document.getElementById('volumeChart').getContext('2d');
        this.charts.volume = new Chart(volCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Call Volume',
                        data: [],
                        backgroundColor: 'rgba(76, 175, 80, 0.8)',
                        borderColor: '#4caf50',
                        borderWidth: 1
                    },
                    {
                        label: 'Put Volume',
                        data: [],
                        backgroundColor: 'rgba(244, 67, 54, 0.8)',
                        borderColor: '#f44336',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            displayFormats: {
                                minute: 'HH:mm'
                            }
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Volume'
                        },
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        position: 'top'
                    }
                }
            }
        });
    }

    updateOptionsData(data) {
        try {
            // Update current symbol if it changed
            if (data.symbol !== this.currentSymbol) {
                this.currentSymbol = data.symbol;
                document.getElementById('symbolInput').value = data.symbol;
            }

            // Update status cards
            this.updateStatusCards(data);
            
            // Update indicators
            this.updateIndicators(data);
            
            // Update raw data display
            this.updateRawData(data);
            
            // Update historical data and charts if available
            if (data.historical_data) {
                this.updateHistoricalData(data.historical_data);
                this.updateCharts();
            }
            
            this.lastUpdate = new Date(data.timestamp);
            
            // Add flash effect to indicate update
            document.body.classList.add('flash-update');
            setTimeout(() => document.body.classList.remove('flash-update'), 500);
            
        } catch (error) {
            console.error('Error updating options data:', error);
            this.showError('Error updating display: ' + error.message);
        }
    }

    updateStatusCards(data) {
        // Sentiment
        const sentimentCard = document.getElementById('sentimentCard');
        const sentimentValue = document.getElementById('sentimentValue');
        const sentimentDetail = document.getElementById('sentimentDetail');
        
        sentimentValue.textContent = data.sentiment || '-';
        sentimentDetail.textContent = `${data.market_status || 'Unknown Status'}`;
        
        // Update sentiment styling
        sentimentCard.classList.remove('bullish', 'bearish');
        if (data.sentiment === 'Bullish') {
            sentimentCard.classList.add('bullish');
        } else if (data.sentiment === 'Bearish') {
            sentimentCard.classList.add('bearish');
        }

        // Net Delta
        document.getElementById('netDeltaValue').textContent = 
            this.formatNumber(data.net_delta) || '-';
        
        // Delta Ratio
        const ratio = data.delta_ratio;
        document.getElementById('deltaRatioValue').textContent = 
            (ratio && ratio !== Infinity) ? ratio.toFixed(2) : '-';
        
        // Underlying Price
        document.getElementById('underlyingValue').textContent = 
            data.underlying_price ? `$${data.underlying_price.toFixed(2)}` : '-';
        document.getElementById('marketStatus').textContent = data.market_status || 'Unknown';
    }

    updateIndicators(data) {
        const indicators = data.indicators || {};
        
        // Momentum
        const momentum = indicators.momentum;
        document.getElementById('momentumValue').textContent = 
            momentum !== undefined ? momentum.toFixed(3) : '-';
        
        // Volatility
        const volatility = indicators.volatility;
        document.getElementById('volatilityValue').textContent = 
            volatility !== undefined ? this.formatNumber(volatility) : '-';
        
        // Trend
        const trend = indicators.trend;
        document.getElementById('trendValue').textContent = 
            trend !== undefined ? trend.toFixed(3) : '-';
        
        // Data Quality
        const performance = data.performance || {};
        const successRate = performance.success_rate;
        document.getElementById('qualityValue').textContent = 
            successRate !== undefined ? `${successRate.toFixed(1)}%` : '-';
    }

    updateRawData(data) {
        document.getElementById('callDeltaVolValue').textContent = 
            this.formatNumber(data.call_delta_vol) || '-';
        document.getElementById('putDeltaVolValue').textContent = 
            this.formatNumber(data.put_delta_vol) || '-';
        document.getElementById('callVolumeValue').textContent = 
            this.formatNumber(data.call_volume) || '-';
        document.getElementById('putVolumeValue').textContent = 
            this.formatNumber(data.put_volume) || '-';
        document.getElementById('lastUpdateValue').textContent = 
            this.lastUpdate ? this.lastUpdate.toLocaleTimeString() : '-';
        
        const performance = data.performance || {};
        document.getElementById('fetchCountValue').textContent = 
            `${performance.fetch_count || 0} (${performance.error_count || 0} errors)`;
    }

    updateHistoricalData(historicalData) {
        // Limit data points
        const maxPoints = this.maxDataPoints;
        
        this.historicalData.timestamps = historicalData.timestamps.slice(-maxPoints);
        this.historicalData.callDeltas = historicalData.call_deltas.slice(-maxPoints);
        this.historicalData.putDeltas = historicalData.put_deltas.slice(-maxPoints);
        this.historicalData.netDeltas = historicalData.net_deltas.slice(-maxPoints);
        this.historicalData.callVolume = historicalData.call_volume.slice(-maxPoints);
        this.historicalData.putVolume = historicalData.put_volume.slice(-maxPoints);
        this.historicalData.underlyingPrices = historicalData.underlying_prices.slice(-maxPoints);
    }

    updateCharts() {
        const timestamps = this.historicalData.timestamps.map(ts => new Date(ts));
        
        // Update Delta Volume Chart
        if (this.charts.deltaVolume) {
            this.charts.deltaVolume.data.labels = timestamps;
            this.charts.deltaVolume.data.datasets[0].data = this.historicalData.callDeltas;
            this.charts.deltaVolume.data.datasets[1].data = this.historicalData.putDeltas;
            this.charts.deltaVolume.update('none');
        }
        
        // Update Net Delta Chart
        if (this.charts.netDelta) {
            this.charts.netDelta.data.labels = timestamps;
            this.charts.netDelta.data.datasets[0].data = this.historicalData.netDeltas;
            this.charts.netDelta.update('none');
        }
        
        // Update Volume Chart
        if (this.charts.volume) {
            this.charts.volume.data.labels = timestamps;
            this.charts.volume.data.datasets[0].data = this.historicalData.callVolume;
            this.charts.volume.data.datasets[1].data = this.historicalData.putVolume;
            this.charts.volume.update('none');
        }
    }

    formatNumber(num) {
        if (num === null || num === undefined) return '-';
        if (Math.abs(num) >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (Math.abs(num) >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toFixed(0);
    }

    showError(message) {
        console.error(message);
        // Could add a toast notification here
    }

    loadInitialData() {
        // Load current symbol from server
        fetch('/api/options-flow/current')
            .then(response => response.json())
            .then(data => {
                if (data.symbol) {
                    this.currentSymbol = data.symbol;
                    document.getElementById('symbolInput').value = data.symbol;
                }
                if (data.timestamp) {
                    this.updateOptionsData(data);
                }
            })
            .catch(error => {
                console.error('Error loading initial options data:', error);
            });

        // Load historical data
        fetch('/api/options-flow/historical?limit=50')
            .then(response => response.json())
            .then(data => {
                if (data.historical_data) {
                    this.updateHistoricalData(data.historical_data);
                    this.updateCharts();
                }
            })
            .catch(error => {
                console.error('Error loading historical options data:', error);
            });
    }
}

// Global function for button onclick
function changeSymbol() {
    if (window.optionsApp) {
        window.optionsApp.changeSymbol();
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.optionsApp = new OptionsFlowApp();
});