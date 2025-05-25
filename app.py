# app.py - Main Flask Application
import os
import json
import logging
import threading
import time
import sqlite3
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from auth import SchwabAuth

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    HOST = '0.0.0.0'
    PORT = 8000
    
    # Directories
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
    STATIC_DIR = os.path.join(BASE_DIR, 'static')

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
app.permanent_session_lifetime = timedelta(hours=24)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
market_data = {}
watchlist = set()
auth_handler = None
streaming_active = False

# Create required directories
os.makedirs(Config.DATA_DIR, exist_ok=True)
os.makedirs(Config.TEMPLATES_DIR, exist_ok=True)
os.makedirs(os.path.join(Config.STATIC_DIR, 'css'), exist_ok=True)
os.makedirs(os.path.join(Config.STATIC_DIR, 'js'), exist_ok=True)

# Database setup
def get_db_connection():
    today_date = datetime.now().strftime('%y%m%d')
    db_filename = os.path.join(Config.DATA_DIR, f'market_data_{today_date}.db')
    
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS equity_quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        timestamp INTEGER,
        last_price REAL,
        bid_price REAL,
        ask_price REAL,
        volume INTEGER,
        net_change REAL,
        net_change_percent REAL,
        high_price REAL,
        low_price REAL
    )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_equity_symbol_ts ON equity_quotes (symbol, timestamp)')
    conn.commit()
    return conn

# Mock Data Generator
class MockDataGenerator:
    def __init__(self):
        self.symbols = {}
        self.running = False
        
    def add_symbol(self, symbol):
        if symbol not in self.symbols:
            self.symbols[symbol] = {
                'symbol': symbol,
                'last_price': round(random.uniform(50, 300), 2),
                'bid_price': 0,
                'ask_price': 0,
                'volume': random.randint(100000, 10000000),
                'net_change': 0,
                'net_change_percent': 0,
                'high_price': 0,
                'low_price': 0,
                'timestamp': int(time.time() * 1000)
            }
    
    def remove_symbol(self, symbol):
        if symbol in self.symbols:
            del self.symbols[symbol]
    
    def start_streaming(self):
        if not self.running:
            self.running = True
            thread = threading.Thread(target=self._generate_data, daemon=True)
            thread.start()
            logger.info("Mock data generator started")
    
    def stop_streaming(self):
        self.running = False
    
    def _generate_data(self):
        while self.running:
            for symbol in list(self.symbols.keys()):
                if symbol in self.symbols:
                    data = self.symbols[symbol]
                    
                    # Generate random price movement
                    change = random.uniform(-2, 2)
                    old_price = data['last_price']
                    new_price = max(1.0, old_price * (1 + change / 100))
                    
                    # Update data
                    data['last_price'] = round(new_price, 2)
                    data['net_change'] = round(new_price - old_price, 2)
                    data['net_change_percent'] = round((new_price - old_price) / old_price * 100, 2)
                    data['bid_price'] = round(new_price - 0.01, 2)
                    data['ask_price'] = round(new_price + 0.01, 2)
                    data['volume'] += random.randint(1000, 50000)
                    data['timestamp'] = int(time.time() * 1000)
                    
                    # Update high/low
                    if data['high_price'] == 0 or new_price > data['high_price']:
                        data['high_price'] = new_price
                    if data['low_price'] == 0 or new_price < data['low_price']:
                        data['low_price'] = new_price
                    
                    # Store globally
                    market_data[symbol] = data
                    
                    # Save to database
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO equity_quotes 
                            (symbol, timestamp, last_price, bid_price, ask_price, volume, 
                             net_change, net_change_percent, high_price, low_price)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (symbol, data['timestamp'], data['last_price'], data['bid_price'],
                              data['ask_price'], data['volume'], data['net_change'],
                              data['net_change_percent'], data['high_price'], data['low_price']))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        logger.error(f"Database error: {e}")
                    
                    # Emit to clients
                    socketio.emit('market_data', {'symbol': symbol, 'data': data})
            
            time.sleep(1)

# Initialize mock generator
mock_generator = MockDataGenerator()

# Schwab Integration (placeholder for real API)
def initialize_schwab_streaming():
    global streaming_active
    try:
        import schwabdev
        
        if not auth_handler or not auth_handler.get_valid_token():
            logger.warning("No valid Schwab token available")
            return False
        
        streaming_active = True
        logger.info("Schwab streaming would be initialized here")
        return True
        
    except ImportError:
        logger.info("schwabdev not available, using mock data")
        return False
    except Exception as e:
        logger.error(f"Schwab streaming error: {e}")
        return False

def start_token_refresh_task():
    def refresh_loop():
        while True:
            try:
                if auth_handler and auth_handler.refresh_token and auth_handler.token_expires_at:
                    time_until_expiry = (auth_handler.token_expires_at - datetime.now()).total_seconds()
                    if time_until_expiry < 600:  # 10 minutes
                        logger.info("Auto-refreshing token...")
                        auth_handler.refresh_access_token()
                        logger.info("Token refreshed successfully")
                
                time.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Token refresh error: {e}")
                time.sleep(300)
    
    thread = threading.Thread(target=refresh_loop, daemon=True)
    thread.start()
    logger.info("Token refresh task started")

# Flask Routes
@app.route('/')
def index():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/authenticate')
def authenticate():
    global auth_handler
    
    try:
        auth_handler = SchwabAuth()
        
        if auth_handler.load_tokens() and auth_handler.is_token_valid():
            session['authenticated'] = True
            session.permanent = True
            flash('Successfully authenticated with existing tokens!', 'success')
            
            if initialize_schwab_streaming():
                flash('Schwab streaming initialized', 'info')
                start_token_refresh_task()
            else:
                flash('Using mock data for demonstration', 'info')
                mock_generator.start_streaming()
            
            return redirect(url_for('index'))
        
        if auth_handler.authenticate():
            session['authenticated'] = True
            session.permanent = True
            flash('Successfully authenticated with Schwab!', 'success')
            
            if initialize_schwab_streaming():
                flash('Schwab streaming initialized', 'info')
                start_token_refresh_task()
            else:
                flash('Using mock data for demonstration', 'info')
                mock_generator.start_streaming()
            
            return redirect(url_for('index'))
        else:
            flash('Authentication failed. Using mock data.', 'warning')
            mock_generator.start_streaming()
            session['authenticated'] = True
            return redirect(url_for('index'))
            
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        flash(f'Authentication error. Using mock data.', 'error')
        mock_generator.start_streaming()
        session['authenticated'] = True
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/api/watchlist', methods=['GET'])
def get_watchlist():
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    return jsonify({'watchlist': list(watchlist)})

@app.route('/api/watchlist', methods=['POST'])
def add_to_watchlist():
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').upper().strip()
        
        if not symbol:
            return jsonify({'error': 'Symbol is required'}), 400
        
        watchlist.add(symbol)
        
        if streaming_active:
            logger.info(f"Would subscribe to {symbol} via Schwab API")
        else:
            mock_generator.add_symbol(symbol)
            if not mock_generator.running:
                mock_generator.start_streaming()
        
        return jsonify({'success': True, 'watchlist': list(watchlist)})
        
    except Exception as e:
        logger.error(f"Error adding to watchlist: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/watchlist', methods=['DELETE'])
def remove_from_watchlist():
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').upper().strip()
        
        if symbol in watchlist:
            watchlist.remove(symbol)
            mock_generator.remove_symbol(symbol)
            
            if symbol in market_data:
                del market_data[symbol]
        
        return jsonify({'success': True, 'watchlist': list(watchlist)})
        
    except Exception as e:
        logger.error(f"Error removing from watchlist: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/market-data')
def get_market_data():
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    return jsonify(market_data)

@app.route('/api/auth-status')
def auth_status():
    is_authenticated = session.get('authenticated', False)
    return jsonify({
        'authenticated': is_authenticated,
        'using_real_api': streaming_active,
        'token_valid': auth_handler.is_token_valid() if auth_handler else False
    })

@app.route('/api/refresh-token', methods=['POST'])
def refresh_token():
    if not session.get('authenticated') or not auth_handler:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        auth_handler.refresh_access_token()
        return jsonify({'success': True, 'message': 'Token refreshed'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    if not session.get('authenticated'):
        emit('error', {'message': 'Not authenticated'})
        return False
    
    logger.info('Client connected')
    for symbol, data in market_data.items():
        emit('market_data', {'symbol': symbol, 'data': data})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

@socketio.on('add_symbol')
def handle_add_symbol(data):
    if not session.get('authenticated'):
        emit('error', {'message': 'Not authenticated'})
        return
    
    symbol = data.get('symbol', '').upper().strip()
    if symbol and symbol not in watchlist:
        watchlist.add(symbol)
        
        if streaming_active:
            logger.info(f"Would subscribe to {symbol} via Schwab")
        else:
            mock_generator.add_symbol(symbol)
            if not mock_generator.running:
                mock_generator.start_streaming()
        
        emit('watchlist_updated', {'watchlist': list(watchlist)}, broadcast=True)

@socketio.on('remove_symbol')
def handle_remove_symbol(data):
    if not session.get('authenticated'):
        emit('error', {'message': 'Not authenticated'})
        return
    
    symbol = data.get('symbol', '').upper().strip()
    if symbol in watchlist:
        watchlist.remove(symbol)
        mock_generator.remove_symbol(symbol)
        
        if symbol in market_data:
            del market_data[symbol]
        
        emit('watchlist_updated', {'watchlist': list(watchlist)}, broadcast=True)
        emit('symbol_removed', {'symbol': symbol}, broadcast=True)

# Create static files and templates
def create_static_files():
    """Create CSS and JavaScript files."""
    
    # Login CSS
    login_css = """/* Login page styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
}

.login-container {
    background: white;
    padding: 40px;
    border-radius: 20px;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
    text-align: center;
    max-width: 400px;
    width: 90%;
}

.logo {
    font-size: 3em;
    margin-bottom: 20px;
}

h1 {
    color: #004B8D;
    margin-bottom: 10px;
    font-size: 2em;
}

.subtitle {
    color: #666;
    margin-bottom: 30px;
    font-size: 1.1em;
}

.auth-btn {
    background: linear-gradient(135deg, #004B8D, #0066CC);
    color: white;
    border: none;
    padding: 15px 30px;
    border-radius: 50px;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    margin: 10px 0;
    transition: all 0.3s ease;
}

.auth-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 20px rgba(0, 75, 141, 0.3);
}

.features {
    margin-top: 30px;
    text-align: left;
}

.features h3 {
    color: #004B8D;
    margin-bottom: 15px;
}

.features ul {
    list-style: none;
    padding-left: 0;
}

.features li {
    padding: 5px 0;
    color: #666;
}

.features li:before {
    content: "✓ ";
    color: #4CAF50;
    font-weight: bold;
}

.flash-messages {
    margin-bottom: 20px;
}

.flash-message {
    padding: 10px;
    border-radius: 5px;
    margin-bottom: 10px;
}

.flash-success { background-color: #d4edda; color: #155724; }
.flash-error { background-color: #f8d7da; color: #721c24; }
.flash-warning { background-color: #fff3cd; color: #856404; }
.flash-info { background-color: #d1ecf1; color: #0c5460; }"""

    # Main CSS
    main_css = """/* Main application styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background-color: #f5f7fa;
    color: #333;
    line-height: 1.6;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

.header {
    background: linear-gradient(135deg, #004B8D, #0066CC);
    color: white;
    padding: 20px;
    border-radius: 10px;
    margin-bottom: 30px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
}

.header h1 {
    font-size: 2.5em;
    margin-bottom: 10px;
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
}

.status-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background-color: #f44336;
    transition: background-color 0.3s ease;
}

.status-dot.connected {
    background-color: #4caf50;
}

.logout-btn {
    background: rgba(255, 255, 255, 0.2);
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.3);
    padding: 8px 16px;
    border-radius: 5px;
    text-decoration: none;
}

.add-symbol-section {
    background: white;
    padding: 25px;
    border-radius: 10px;
    margin-bottom: 30px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.add-symbol-section h2 {
    margin-bottom: 15px;
    color: #004B8D;
}

.input-group {
    display: flex;
    gap: 15px;
    align-items: center;
    flex-wrap: wrap;
}

.input-group input {
    flex: 1;
    min-width: 200px;
    padding: 12px 15px;
    border: 2px solid #e0e0e0;
    border-radius: 5px;
    font-size: 16px;
}

.btn {
    padding: 12px 25px;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    font-size: 16px;
    font-weight: bold;
}

.btn-primary {
    background-color: #004B8D;
    color: white;
}

    gap: 20px;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
}

.stock-card {
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 10px;
    padding: 20px;
    transition: all 0.3s ease;
}

.stock-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
}

.stock-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
}

.stock-symbol {
    font-size: 1.5em;
    font-weight: bold;
    color: #004B8D;
}

.remove-btn {
    background: none;
    border: none;
    color: #666;
    cursor: pointer;
    font-size: 18px;
    padding: 5px;
    border-radius: 50%;
}

.remove-btn:hover {
    background-color: #f44336;
    color: white;
}

.price-main {
    text-align: center;
    margin-bottom: 15px;
}

.current-price {
    font-size: 2.5em;
    font-weight: bold;
    color: #333;
}

.price-change {
    display: flex;
    justify-content: center;
    gap: 10px;
    margin-top: 5px;
}

.change-amount, .change-percent {
    font-size: 1.1em;
    font-weight: bold;
    padding: 5px 10px;
    border-radius: 5px;
}

.positive {
    background-color: #e8f5e8;
    color: #2e7d32;
}

.negative {
    background-color: #ffebee;
    color: #c62828;
}

.neutral {
    background-color: #f5f5f5;
    color: #666;
}

.price-details {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
    font-size: 0.9em;
}

.price-item {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #eee;
}

.price-label {
    color: #666;
    font-weight: 500;
}

.price-value {
    font-weight: bold;
    color: #333;
}

.timestamp {
    text-align: center;
    margin-top: 15px;
    font-size: 0.8em;
    color: #999;
}

.no-data {
    text-align: center;
    padding: 40px;
    color: #666;
    font-style: italic;
}

.flash {
    animation: flashGreen 0.5s ease-in-out;
}

@keyframes flashGreen {
    0% { background-color: #e8f5e8; }
    50% { background-color: #c8e6c9; }
    100% { background-color: #f8f9fa; }
}

@media (max-width: 768px) {
    .container { padding: 10px; }
    .header h1 { font-size: 2em; }
    .input-group { flex-direction: column; }
    .input-group input { min-width: auto; width: 100%; }
    .market-data-grid { grid-template-columns: 1fr; }
    .price-details { grid-template-columns: 1fr; }
}"""

    # JavaScript
    market_js = """class MarketDataApp {
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
});"""

    # Save files
    with open(os.path.join(Config.STATIC_DIR, 'css', 'login.css'), 'w') as f:
        f.write(login_css)
    
    with open(os.path.join(Config.STATIC_DIR, 'css', 'main.css'), 'w') as f:
        f.write(main_css)
    
    with open(os.path.join(Config.STATIC_DIR, 'js', 'market-data.js'), 'w') as f:
        f.write(market_js)

def create_templates():
    """Create clean HTML templates that reference external CSS/JS."""
    
    # Login template
    login_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Schwab Market Data - Login</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/login.css') }}">
</head>
<body>
    <div class="login-container">
        <div class="logo">📈</div>
        <h1>Schwab Market Data</h1>
        <p class="subtitle">Real-time streaming market data</p>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="flash-message flash-{{ category }}">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        
        <a href="{{ url_for('authenticate') }}" class="auth-btn">
            🔐 Authenticate with Schwab
        </a>
        
        <div class="features">
            <h3>Features:</h3>
            <ul>
                <li>Real-time market data streaming</li>
                <li>Live price updates with WebSockets</li>
                <li>Custom watchlist management</li>
                <li>OAuth 2.0 secure authentication</li>
                <li>Mock data mode for testing</li>
            </ul>
        </div>
    </div>
</body>
</html>'''

    # Main template
    index_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Schwab Market Data Stream</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/main.css') }}">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>📈 Market Data Stream</h1>
                <p>Real-time equity market data</p>
            </div>
            <div style="display: flex; align-items: center; gap: 20px;">
                <div class="status-indicator">
                    <div class="status-dot" id="connectionStatus"></div>
                    <span id="connectionText">Connecting...</span>
                </div>
                <a href="{{ url_for('logout') }}" class="logout-btn">Logout</a>
            </div>
        </div>

        <div class="add-symbol-section">
            <h2>Add Stock Symbol</h2>
            <div class="input-group">
                <input type="text" id="symbolInput" placeholder="Enter stock symbol (e.g., AAPL, MSFT, GOOGL)" maxlength="10">
                <button class="btn btn-primary" onclick="app.addSymbol()">Add to Watchlist</button>
            </div>
            <div id="messageArea"></div>
        </div>

        <div style="background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h2>📊 Your Watchlist</h2>
            <div id="marketDataContainer" class="market-data-grid">
                <div class="no-data">Add some stock symbols to start streaming market data!</div>
            </div>
        </div>
    </div>

    <script src="{{ url_for('static', filename='js/market-data.js') }}"></script>
</body>
</html>'''

    # Save templates
    with open(os.path.join(Config.TEMPLATES_DIR, 'login.html'), 'w') as f:
        f.write(login_html)
    
    with open(os.path.join(Config.TEMPLATES_DIR, 'index.html'), 'w') as f:
        f.write(index_html)

# Initialize application
def initialize_app():
    create_static_files()
    create_templates()
    logger.info("Application initialized with external CSS/JS files")

# Main execution
if __name__ == '__main__':
    try:
        initialize_app()
        
        print("\n" + "="*60)
        print("🚀 SCHWAB MARKET DATA STREAMING APP")
        print("="*60)
        print(f"🌐 Open http://localhost:{Config.PORT} in your browser")
        print("🔐 You'll be prompted to authenticate with Schwab")
        print("📊 Add stock symbols to start streaming market data")
        print("💡 Uses mock data if Schwab API not available")
        print("🎨 Now with separated CSS and JavaScript files!")
        print("="*60)
        
        socketio.run(app, debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)
        
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"❌ Error: {e}")
