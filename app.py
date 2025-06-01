# app.py - Complete Fixed Flask Application with Mock Data Support
import os
import json
import logging
import threading
import time
import sqlite3
import sys
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

# Global flag to track if we're in mock mode (avoids session context issues)
global_mock_mode = False

# Create required directories
os.makedirs(Config.DATA_DIR, exist_ok=True)
os.makedirs(Config.TEMPLATES_DIR, exist_ok=True)
os.makedirs(os.path.join(Config.STATIC_DIR, 'css'), exist_ok=True)
os.makedirs(os.path.join(Config.STATIC_DIR, 'js'), exist_ok=True)

# Enhanced Database setup with options flow support and mock data separation
def get_db_connection(is_mock_mode=None):
    """Get database connection with mock/real separation"""
    global global_mock_mode
    
    if is_mock_mode is None:
        # Try to get from session first, fallback to global flag
        try:
            is_mock_mode = session.get('mock_mode', global_mock_mode)
        except RuntimeError:
            # Outside request context, use global flag
            is_mock_mode = global_mock_mode
    
    today_date = datetime.now().strftime('%y%m%d')
    
    if is_mock_mode:
        # Mock data goes to separate database files
        db_filename = os.path.join(Config.DATA_DIR, f'MOCK_market_data_{today_date}.db')
        logger.info(f"Using MOCK database: {db_filename}")
    else:
        # Real data goes to regular database files
        db_filename = os.path.join(Config.DATA_DIR, f'market_data_{today_date}.db')
        logger.info(f"Using REAL database: {db_filename}")
    
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()
    
    # Existing equity quotes table with data source tracking
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
        low_price REAL,
        data_source TEXT DEFAULT 'UNKNOWN'
    )
    ''')
    
    # New options flow table with data source tracking
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
        market_status TEXT,
        data_source TEXT DEFAULT 'UNKNOWN'
    )
    ''')
    
    # Metadata table to track data source
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS data_metadata (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at INTEGER,
        data_source TEXT,
        app_version TEXT,
        notes TEXT
    )
    ''')
    
    # Insert metadata record on first connection
    cursor.execute('SELECT COUNT(*) FROM data_metadata')
    if cursor.fetchone()[0] == 0:
        data_source = 'MOCK' if is_mock_mode else 'SCHWAB_API'
        cursor.execute('''
            INSERT INTO data_metadata (created_at, data_source, app_version, notes)
            VALUES (?, ?, ?, ?)
        ''', (
            int(time.time() * 1000),
            data_source,
            "1.0.0",  # Your app version
            f"Database created in {'mock' if is_mock_mode else 'real'} mode"
        ))
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_equity_symbol_ts ON equity_quotes (symbol, timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_options_symbol_ts ON options_flow (symbol, timestamp)')
    conn.commit()
    return conn

# Enhanced Schwab streaming handler with proper context handling
def schwab_message_handler(message):
    """Enhanced message handler with data source tracking"""
    global global_mock_mode
    
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
        
        # Use global flag instead of session to avoid context issues
        is_mock_mode = global_mock_mode or (hasattr(schwab_client, '__class__') and 'Mock' in schwab_client.__class__.__name__)
        
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
                        'timestamp': timestamp,
                        'data_source': 'MOCK' if is_mock_mode else 'SCHWAB_API'
                    }
                    
                    # Store globally
                    market_data[symbol] = market_data_item
                    
                    # Save to appropriate database
                    try:
                        conn = get_db_connection(is_mock_mode)
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO equity_quotes 
                            (symbol, timestamp, last_price, bid_price, ask_price, volume, 
                             net_change, net_change_percent, high_price, low_price, data_source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (symbol, timestamp, market_data_item['last_price'], market_data_item['bid_price'],
                              market_data_item['ask_price'], market_data_item['volume'], market_data_item['net_change'],
                              market_data_item['net_change_percent'], market_data_item['high_price'], 
                              market_data_item['low_price'], market_data_item['data_source']))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        logger.error(f"Database error: {e}")
                    
                    # Emit to clients with source information (use app context)
                    with app.app_context():
                        socketio.emit('market_data', {
                            'symbol': symbol, 
                            'data': market_data_item,
                            'is_mock': is_mock_mode
                        })
                    
                    # Enhanced logging
                    source_label = "MOCK" if is_mock_mode else "REAL"
                    logger.info(f"{source_label} data for {symbol}: Last ${market_data_item.get('last_price', 'N/A')}")
        
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
    """Enhanced authentication with mock mode tracking"""
    global schwab_client, schwab_streamer, global_mock_mode
    
    try:
        # Determine if using mock mode - check multiple sources
        use_mock = (
            request.args.get('mock', 'false').lower() == 'true' or
            os.getenv('USE_MOCK_DATA', 'false').lower() == 'true' or
            global_mock_mode
        )
        
        schwab_client = get_schwab_client(use_mock)
        
        if schwab_client:
            schwab_streamer = schwab_client.stream
            session['authenticated'] = True
            
            # Determine if we're actually in mock mode by checking the client class
            is_mock_mode = hasattr(schwab_client, '__class__') and 'Mock' in schwab_client.__class__.__name__
            
            # Set both session and global flags
            session['mock_mode'] = is_mock_mode
            global_mock_mode = is_mock_mode
            session.permanent = True
            
            # Debug logging
            logger.info(f"Authentication completed - Mock mode: {is_mock_mode}")
            logger.info(f"Session mock_mode: {session.get('mock_mode')}")
            logger.info(f"Global mock_mode: {global_mock_mode}")
            logger.info(f"Client class: {schwab_client.__class__.__name__}")
            
            # Initialize options flow monitor
            options_monitor = get_options_monitor()
            if options_monitor:
                options_monitor.set_dependencies(schwab_client, socketio, 
                    lambda: get_db_connection(is_mock_mode))
                if not options_monitor.is_running:
                    options_monitor.start_monitoring(30)
            
            if is_mock_mode:
                flash('🎭 Using MOCK data mode - Data is simulated for testing', 'warning')
            else:
                flash('✅ Connected to Schwab API - Using REAL market data', 'success')
        else:
            # Fallback to mock mode
            session['authenticated'] = True
            session['mock_mode'] = True
            global_mock_mode = True
            logger.info("Fallback to mock mode - no client available")
            flash('⚠️ Could not connect to Schwab API. Using MOCK data mode.', 'error')
        
        return redirect(url_for('index'))
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        session['authenticated'] = True
        session['mock_mode'] = True
        global_mock_mode = True
        logger.info("Error fallback to mock mode")
        flash(f'Authentication error: {e}. Using MOCK data mode.', 'error')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    global global_mock_mode
    
    # Stop options monitor if running
    options_monitor = get_options_monitor()
    if options_monitor and options_monitor.is_running:
        options_monitor.stop_monitoring()
    
    session.clear()
    global_mock_mode = False  # Reset global flag
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

# API Routes for Market Data (enhanced with mock support)
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
                # Check if using mock or real streamer
                if hasattr(schwab_streamer, 'add_symbol'):
                    # Mock streamer method
                    schwab_streamer.add_symbol(symbol)
                    logger.info(f"Added {symbol} to mock stream")
                else:
                    # Real Schwab streamer method
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
    
    # Add mock status to response
    response_data = {
        'market_data': market_data,
        'is_mock_mode': session.get('mock_mode', False),
        'data_source': 'MOCK' if session.get('mock_mode', False) else 'SCHWAB_API',
        'timestamp': int(time.time() * 1000)
    }
    
    return jsonify(response_data)

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

# Enhanced API Routes for Mock Testing and Admin
@app.route('/api/auth-status')
def auth_status():
    is_authenticated = session.get('authenticated', False)
    is_mock_mode = session.get('mock_mode', False)
    
    return jsonify({
        'authenticated': is_authenticated,
        'mock_mode': is_mock_mode,
        'using_real_api': schwab_client is not None and not is_mock_mode,
        'has_streamer': schwab_streamer is not None,
        'data_source': 'MOCK' if is_mock_mode else 'SCHWAB_API',
        'database_prefix': 'MOCK_' if is_mock_mode else '',
        'options_monitor_running': get_options_monitor().is_running if get_options_monitor() else False
    })

@app.route('/api/debug/session')
def debug_session():
    """Debug route to check session status"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify({
        'global_mock_mode': global_mock_mode,
        'authenticated': session.get('authenticated', False),
        'session_keys': list(session.keys()),
        'client_class': schwab_client.__class__.__name__ if schwab_client else 'None',
        'is_mock_client': hasattr(schwab_client, '__class__') and 'Mock' in schwab_client.__class__.__name__ if schwab_client else False
    })

@app.route('/api/test/market-event', methods=['POST'])
def trigger_market_event():
    """Trigger mock market events for testing"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Check mock mode with better debugging
    is_mock_client = hasattr(schwab_client, '__class__') and 'Mock' in schwab_client.__class__.__name__ if schwab_client else False
    
    logger.info(f"Market event trigger attempt:")
    logger.info(f"  Global mock_mode: {global_mock_mode}")
    logger.info(f"  Client is mock: {is_mock_client}")
    logger.info(f"  Session keys: {list(session.keys())}")
    
    
    try:
        data = request.get_json()
        event_type = data.get('event_type', 'bullish_surge')
        symbols = data.get('symbols', list(watchlist))
        
        if hasattr(schwab_streamer, 'simulate_market_event'):
            schwab_streamer.simulate_market_event(event_type, symbols)
            logger.info(f"Successfully triggered {event_type} for {len(symbols)} symbols")
        else:
            logger.warning("Streamer does not have simulate_market_event method")
            return jsonify({'error': 'Mock events not available on this streamer'}), 400
        
        return jsonify({
            'success': True, 
            'event_type': event_type,
            'symbols': symbols,
            'message': f'Triggered {event_type} for {len(symbols)} symbols'
        })
        
    except Exception as e:
        logger.error(f"Error triggering market event: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/data-info')
def data_info():
    """Get information about stored data"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        files = []
        data_dir = Config.DATA_DIR
        
        for filename in os.listdir(data_dir):
            if filename.endswith('.db'):
                is_mock = filename.startswith('MOCK_')
                size = os.path.getsize(os.path.join(data_dir, filename))
                files.append({
                    'filename': filename,
                    'type': 'MOCK' if is_mock else 'REAL',
                    'size_mb': round(size / (1024*1024), 2),
                    'path': os.path.join(data_dir, filename)
                })
        
        stats = {
            'total_files': len(files),
            'mock_files': len([f for f in files if f['type'] == 'MOCK']),
            'real_files': len([f for f in files if f['type'] == 'REAL']),
            'total_size_mb': sum(f['size_mb'] for f in files),
            'mock_size_mb': sum(f['size_mb'] for f in files if f['type'] == 'MOCK'),
            'real_size_mb': sum(f['size_mb'] for f in files if f['type'] == 'REAL')
        }
        
        return jsonify({
            'current_mode': 'MOCK' if session.get('mock_mode', False) else 'REAL',
            'database_files': files,
            'statistics': stats,
            'current_database': f"{'MOCK_' if session.get('mock_mode', False) else ''}market_data_{datetime.now().strftime('%y%m%d')}.db"
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/cleanup-mock', methods=['POST'])
def cleanup_mock():
    """Clean up mock database files"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data_dir = Config.DATA_DIR
        removed_files = []
        
        for filename in os.listdir(data_dir):
            if filename.startswith('MOCK_') and filename.endswith('.db'):
                file_path = os.path.join(data_dir, filename)
                os.remove(file_path)
                removed_files.append(filename)
        
        return jsonify({
            'success': True,
            'removed_files': removed_files,
            'count': len(removed_files)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# WebSocket Events for Market Data (enhanced with mock compatibility)
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
                # Check if using mock or real streamer
                if hasattr(schwab_streamer, 'add_symbol'):
                    # Mock streamer method
                    schwab_streamer.add_symbol(symbol)
                    logger.info(f"Added {symbol} to mock stream")
                else:
                    # Real Schwab streamer method
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

# Template creation functions (your existing functions)
def create_static_files():
    """Create CSS and JavaScript files"""
    # Your existing CSS and JS creation code
    pass

def create_templates():
    """Create HTML templates"""
    # Your existing template creation code
    pass

# Enhanced initialization with mock/real separation
def initialize_app():
    """Enhanced initialization with proper mock/real separation"""
    global schwab_client, schwab_streamer, global_mock_mode
    
    create_static_files()
    create_templates()
    
    print("\n" + "="*80)
    print("🚀 SCHWAB MARKET DATA STREAMING APP WITH OPTIONS FLOW")
    print("="*80)
    
    # Check for environment override
    env_mock = os.getenv('USE_MOCK_DATA', 'false').lower() == 'true'
    
    if env_mock:
        use_mock = True
        print("🎭 Environment variable USE_MOCK_DATA=true detected")
    else:
        # Interactive mode selection
        print("Choose your data source:")
        print("1. Schwab API (real market data - requires authentication)")
        print("2. Mock data (simulated data - separate database)")
        print("="*80)
        
        while True:
            try:
                choice = input("Enter your choice (1 or 2): ").strip()
                if choice == '1':
                    use_mock = False
                    break
                elif choice == '2':
                    use_mock = True
                    break
                else:
                    print("Please enter 1 or 2")
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                sys.exit(0)
    
    print("Initializing connection...")
    
    # Initialize options flow monitor
    options_monitor = initialize_options_monitor("SPY", 20, 100)
    logger.info("Options flow monitor initialized")
    
    # Get client
    schwab_client = get_schwab_client(use_mock)
    is_mock_mode = hasattr(schwab_client, '__class__') and 'Mock' in schwab_client.__class__.__name__
    global_mock_mode = is_mock_mode  # Set global flag
    
    if schwab_client and hasattr(schwab_client, 'stream'):
        schwab_streamer = schwab_client.stream
        
        if is_mock_mode:
            print("🎭 MOCK DATA MODE ACTIVE")
            print("   • Realistic market data simulation")
            print("   • Data saved to: data/MOCK_market_data_YYMMDD.db")
            print("   • No API credentials required")
            print("   • Perfect for testing and development")
        else:
            print("✅ REAL DATA MODE ACTIVE")
            print("   • Live Schwab API connection")
            print("   • Data saved to: data/market_data_YYMMDD.db")
            print("   • Real-time market streaming enabled")
        
        # Set dependencies with proper database connection
        options_monitor.set_dependencies(
            schwab_client, 
            socketio, 
            lambda: get_db_connection(is_mock_mode)
        )
        
        # Start the streamer
        try:
            schwab_streamer.start(schwab_message_handler)
            print("✅ Market data streamer started")
            
            # Subscribe to default symbol
            default_symbol = "SPY"
            if is_mock_mode:
                schwab_streamer.add_symbol(default_symbol)
            else:
                schwab_streamer.send(schwab_streamer.level_one_equities(default_symbol, "0,1,2,3,4,5,8,12,13,29,30"))
            
            watchlist.add(default_symbol)
            print(f"✅ Subscribed to {default_symbol}")
            
        except Exception as e:
            print(f"⚠️  Could not start streamer: {e}")
    else:
        print("❌ Could not initialize market data source")
        print("   Using minimal mock mode")
    
    print(f"🌐 Starting web server at http://localhost:{Config.PORT}")
    print("📊 Main app: Add stock symbols to start streaming market data")
    print("📈 Options flow: Monitor delta×volume analysis at /options-flow")
    
    if is_mock_mode:
        print("="*80)
        print("⚠️  REMINDER: You are using MOCK DATA for testing purposes")
        print("   • Database files are prefixed with MOCK_")
        print("   • UI will show orange indicators")
        print("   • Test market events available via API")
    
    print("="*80)
    
    logger.info(f"Application initialized in {'MOCK' if is_mock_mode else 'REAL'} mode")

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
