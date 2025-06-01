# app.py - Enhanced Flask Application with Options Flow Integration
import os
import json
import logging
import threading
import time
import sqlite3
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from auth import get_schwab_client, get_schwab_streamer
from options_flow_web import OptionsFlowWebMonitor, initialize_options_monitor, get_options_monitor

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
schwab_client = None
schwab_streamer = None

# Create required directories
os.makedirs(Config.DATA_DIR, exist_ok=True)
os.makedirs(Config.TEMPLATES_DIR, exist_ok=True)
os.makedirs(os.path.join(Config.STATIC_DIR, 'css'), exist_ok=True)
os.makedirs(os.path.join(Config.STATIC_DIR, 'js'), exist_ok=True)

# Enhanced Database setup with options flow support
def get_db_connection():
    today_date = datetime.now().strftime('%y%m%d')
    db_filename = os.path.join(Config.DATA_DIR, f'market_data_{today_date}.db')
    
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()
    
    # Existing equity quotes table
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
    
    # New options flow table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS options_flow (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        timestamp INTEGER,
        call_delta_vol REAL,
        put_delta_vol REAL,
        net_delta REAL,
        delta_ratio REAL,
        call_volume INTEGER,
        put_volume INTEGER,
        underlying_price REAL,
        market_status TEXT
    )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_equity_symbol_ts ON equity_quotes (symbol, timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_options_symbol_ts ON options_flow (symbol, timestamp)')
    conn.commit()
    return conn

# Schwab streaming handler (existing functionality)
def schwab_message_handler(message):
    """Handle incoming messages from Schwab stream"""
    try:
        data = json.loads(message)
        
        # Skip heartbeat messages
        if 'notify' in data and any('heartbeat' in item for item in data['notify']):
            return
        
        # Handle service messages
        if 'notify' in data:
            for item in data['notify']:
                if item.get('service') == 'ADMIN':
                    logger.warning(f"Admin message: {item.get('content', {}).get('msg', 'Unknown')}")
                    return
        
        # Process actual market data
        if "data" not in data:
            return

        for item in data["data"]:
            service = item.get("service")
            if not service or "content" not in item:
                continue
            
            timestamp = int(time.time() * 1000)
            
            # Process each content item
            for content in item["content"]:
                symbol = content.get("key")
                if not symbol:
                    continue

                if service == "LEVELONE_EQUITIES":
                    # Process level one equity data
                    market_data_item = {
                        'symbol': symbol,
                        'last_price': content.get("1"),      # Last price
                        'bid_price': content.get("2"),       # Bid price  
                        'ask_price': content.get("3"),       # Ask price
                        'volume': content.get("8"),          # Volume
                        'high_price': content.get("12"),     # High price
                        'low_price': content.get("13"),      # Low price
                        'net_change': content.get("29"),     # Net change
                        'net_change_percent': content.get("30"), # Net change percent
                        'timestamp': timestamp
                    }
                    
                    # Store globally
                    market_data[symbol] = market_data_item
                    
                    # Save to database
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO equity_quotes 
                            (symbol, timestamp, last_price, bid_price, ask_price, volume, 
                             net_change, net_change_percent, high_price, low_price)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (symbol, timestamp, market_data_item['last_price'], market_data_item['bid_price'],
                              market_data_item['ask_price'], market_data_item['volume'], market_data_item['net_change'],
                              market_data_item['net_change_percent'], market_data_item['high_price'], market_data_item['low_price']))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        logger.error(f"Database error: {e}")
                    
                    # Emit to clients
                    socketio.emit('market_data', {'symbol': symbol, 'data': market_data_item})
                    logger.info(f"Updated market data for {symbol}: Last ${market_data_item.get('last_price', 'N/A')}")
        
    except Exception as e:
        logger.error(f"Error processing Schwab message: {e}")
        logger.error(f"Problematic message: {message}")

# Flask Routes
@app.route('/')
def index():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/options-flow')
def options_flow():
    """Options flow monitoring page"""
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    
    options_monitor = get_options_monitor()
    current_symbol = options_monitor.symbol if options_monitor else 'SPY'
    
    return render_template('options_flow.html', current_symbol=current_symbol)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/authenticate')
def authenticate():
    """Authenticate with Schwab API"""
    global schwab_client, schwab_streamer
    
    try:
        # Try to get Schwab client
        schwab_client = get_schwab_client()
        
        if schwab_client:
            schwab_streamer = schwab_client.stream
            session['authenticated'] = True
            session.permanent = True
            
            # Initialize options flow monitor with dependencies
            options_monitor = get_options_monitor()
            if options_monitor:
                options_monitor.set_dependencies(schwab_client, socketio, get_db_connection)
                if not options_monitor.is_running:
                    options_monitor.start_monitoring(30)  # 30 second updates
            
            flash('Successfully connected to Schwab API!', 'success')
        else:
            session['authenticated'] = True  # Allow access anyway
            flash('Could not connect to Schwab API. Using mock data mode.', 'warning')
        
        return redirect(url_for('index'))
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        session['authenticated'] = True  # Allow access anyway
        flash(f'Authentication error: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    # Stop options monitor if running
    options_monitor = get_options_monitor()
    if options_monitor and options_monitor.is_running:
        options_monitor.stop_monitoring()
    
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

# API Routes for Market Data (existing)
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
        
        # If we have Schwab streamer, subscribe to the symbol
        if schwab_streamer:
            try:
                # Subscribe to level one equity quotes with specific fields
                schwab_streamer.send(schwab_streamer.level_one_equities(symbol, "0,1,2,3,4,5,8,12,13,29,30"))
                logger.info(f"Subscribed to Schwab data for {symbol}")
            except Exception as e:
                logger.error(f"Error subscribing to {symbol}: {e}")
        
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

# API Routes for Options Flow
@app.route('/api/options-flow/current')
def get_current_options_flow():
    """Get current options flow data"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        options_monitor = get_options_monitor()
        if not options_monitor:
            return jsonify({'error': 'Options monitor not initialized'}), 500
        
        current_data = options_monitor.get_current_data()
        return jsonify(current_data)
        
    except Exception as e:
        logger.error(f"Error getting current options flow: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/options-flow/historical')
def get_historical_options_flow():
    """Get historical options flow data"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        limit = request.args.get('limit', type=int)
        
        options_monitor = get_options_monitor()
        if not options_monitor:
            return jsonify({'error': 'Options monitor not initialized'}), 500
        
        historical_data = options_monitor.get_historical_data(limit)
        return jsonify(historical_data)
        
    except Exception as e:
        logger.error(f"Error getting historical options flow: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/options-flow/symbol', methods=['POST'])
def change_options_symbol():
    """Change the options flow monitoring symbol"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        new_symbol = data.get('symbol', '').upper().strip()
        
        if not new_symbol:
            return jsonify({'error': 'Symbol is required'}), 400
        
        options_monitor = get_options_monitor()
        if not options_monitor:
            return jsonify({'error': 'Options monitor not initialized'}), 500
        
        options_monitor.change_symbol(new_symbol)
        return jsonify({'success': True, 'symbol': new_symbol})
        
    except Exception as e:
        logger.error(f"Error changing options symbol: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth-status')
def auth_status():
    is_authenticated = session.get('authenticated', False)
    return jsonify({
        'authenticated': is_authenticated,
        'using_real_api': schwab_client is not None,
        'has_streamer': schwab_streamer is not None,
        'options_monitor_running': get_options_monitor().is_running if get_options_monitor() else False
    })

# WebSocket Events for Market Data (existing)
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
        
        if schwab_streamer:
            try:
                schwab_streamer.send(schwab_streamer.level_one_equities(symbol, "0,1,2,3,4,5,8,12,13,29,30"))
                logger.info(f"Subscribed to {symbol} via Schwab WebSocket")
            except Exception as e:
                logger.error(f"Error subscribing to {symbol}: {e}")
        
        emit('watchlist_updated', {'watchlist': list(watchlist)}, broadcast=True)

@socketio.on('remove_symbol')
def handle_remove_symbol(data):
    if not session.get('authenticated'):
        emit('error', {'message': 'Not authenticated'})
        return
    
    symbol = data.get('symbol', '').upper().strip()
    if symbol in watchlist:
        watchlist.remove(symbol)
        
        if symbol in market_data:
            del market_data[symbol]
        
        emit('watchlist_updated', {'watchlist': list(watchlist)}, broadcast=True)
        emit('symbol_removed', {'symbol': symbol}, broadcast=True)

# WebSocket Events for Options Flow
@socketio.on('change_options_symbol')
def handle_change_options_symbol(data):
    """Handle options symbol change via WebSocket"""
    if not session.get('authenticated'):
        emit('error', {'message': 'Not authenticated'})
        return
    
    try:
        new_symbol = data.get('symbol', '').upper().strip()
        
        if not new_symbol:
            emit('error', {'message': 'Symbol is required'})
            return
        
        options_monitor = get_options_monitor()
        if not options_monitor:
            emit('error', {'message': 'Options monitor not initialized'})
            return
        
        options_monitor.change_symbol(new_symbol)
        emit('options_symbol_changed', {'symbol': new_symbol}, broadcast=True)
        logger.info(f"Options symbol changed to {new_symbol} via WebSocket")
        
    except Exception as e:
        logger.error(f"Error changing options symbol via WebSocket: {e}")
        emit('error', {'message': str(e)})

# Template creation functions (existing functionality)
def create_static_files():
    """Create CSS and JavaScript files"""
    
    # Main CSS (existing - you have this in static/css/main.css)
    # JavaScript (existing - you have this in static/js/market-data.js)
    
    # Note: The options flow CSS and JS are already created separately
    pass

def create_templates():
    """Create HTML templates"""
    
    # Login template (existing - you have this in templates/login.html)
    # Main template (existing - you have this in templates/index.html)
    # Options flow template is created separately
    
    pass

# Initialize application
def initialize_app():
    """Initialize the application"""
    global schwab_client, schwab_streamer
    
    # Create static files and templates
    create_static_files()
    create_templates()
    
    print("\n" + "="*80)
    print("🚀 SCHWAB MARKET DATA STREAMING APP WITH OPTIONS FLOW")
    print("="*80)
    print("Initializing Schwab connection...")
    
    # Initialize options flow monitor
    options_monitor = initialize_options_monitor("SPY", 20, 100)
    logger.info("Options flow monitor initialized")
    
    # Try to connect to Schwab
    schwab_client = get_schwab_client()
    
    if schwab_client:
        schwab_streamer = schwab_client.stream
        print("✅ Connected to Schwab API")
        
        # Set dependencies for options monitor
        options_monitor.set_dependencies(schwab_client, socketio, get_db_connection)
        
        # Start the equity streamer
        try:
            schwab_streamer.start(schwab_message_handler)
            print("✅ Schwab equity streamer started")
            
            # Subscribe to a default symbol to keep the stream alive
            default_symbol = "SPY"
            schwab_streamer.send(schwab_streamer.level_one_equities(default_symbol, "0,1,2,3,4,5,8,12,13,29,30"))
            watchlist.add(default_symbol)
            print(f"✅ Subscribed to {default_symbol} to keep stream alive")
            
        except Exception as e:
            print(f"⚠️  Could not start equity streamer: {e}")
    else:
        print("❌ Could not connect to Schwab API")
        print("   Make sure SCHWAB_APP_KEY and SCHWAB_APP_SECRET are set in .env")
        print("   Options flow will use mock data")
        
        # Set minimal dependencies for mock mode
        options_monitor.set_dependencies(None, socketio, get_db_connection)
    
    print(f"🌐 Starting web server at http://localhost:{Config.PORT}")
    print("📊 Main app: Add stock symbols to start streaming market data")
    print("📈 Options flow: Monitor delta×volume analysis at /options-flow")
    print("="*80)
    
    logger.info("Application initialized with options flow support")

# Main execution
if __name__ == '__main__':
    try:
        initialize_app()
        socketio.run(app, debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)
        
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
        
        # Clean shutdown
        options_monitor = get_options_monitor()
        if options_monitor and options_monitor.is_running:
            options_monitor.stop_monitoring()
        
        if schwab_streamer:
            schwab_streamer.stop()
            
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"❌ Error: {e}")
                