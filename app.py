# app.py - Modular Flask Application for Market Data Streaming
import os
import logging
from datetime import timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_socketio import SocketIO
from dotenv import load_dotenv
from auth import get_schwab_client, get_schwab_streamer, require_auth
from features.feature_manager import FeatureManager

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
    
    # Feature toggles
    ENABLE_MARKET_DATA = os.getenv('ENABLE_MARKET_DATA', 'true').lower() == 'true'
    
    # Directories
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
    STATIC_DIR = os.path.join(BASE_DIR, 'static')

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
app.permanent_session_lifetime = timedelta(hours=24)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize feature manager
feature_manager = FeatureManager(Config.DATA_DIR, socketio)
app.feature_manager = feature_manager  # Make accessible via current_app

# Create required directories
os.makedirs(Config.DATA_DIR, exist_ok=True)
os.makedirs(Config.TEMPLATES_DIR, exist_ok=True)
os.makedirs(os.path.join(Config.STATIC_DIR, 'css'), exist_ok=True)
os.makedirs(os.path.join(Config.STATIC_DIR, 'js'), exist_ok=True)

def _initialize_features(use_mock: bool = False):
    """Initialize features based on configuration"""
    if Config.ENABLE_MARKET_DATA:
        try:
            if use_mock:
                # Use mock components directly for mock mode
                from mock_data import MockSchwabClient, MockSchwabStreamer
                schwab_client = MockSchwabClient()
                schwab_streamer = MockSchwabStreamer()
            else:
                # Use real Schwab components for real mode
                schwab_client = get_schwab_client()
                schwab_streamer = get_schwab_streamer()
            
            market_data_manager = feature_manager.initialize_market_data(
                schwab_client, schwab_streamer, use_mock
            )
            
            if market_data_manager:
                logger.info(f"✅ Market data initialized ({'mock' if use_mock else 'real'} mode)")
                logger.info(f"📋 Manager watchlist: {market_data_manager.get_watchlist()}")
                logger.info(f"🎭 Manager mock mode: {market_data_manager.is_mock_mode}")
            else:
                logger.error("❌ Failed to initialize market data")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize market data: {e}")

def _cleanup_features():
    """Clean up features during logout"""
    if feature_manager.is_feature_enabled('market_data'):
        try:
            market_data_manager = feature_manager.get_feature('market_data')
            if market_data_manager:
                market_data_manager.stop_streaming()
                logger.info("Stopped market data streaming")
        except Exception as e:
            logger.error(f"Error stopping streaming during cleanup: {e}")

# Authentication routes
@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/authenticate')
def authenticate():
    """Enhanced authentication with mock mode tracking"""
    try:
        # Determine if using mock mode - check this FIRST before any auth
        use_mock = (
            request.args.get('mock', 'false').lower() == 'true' or
            os.getenv('USE_MOCK_DATA', 'false').lower() == 'true'
        )
        
        if use_mock:
            # Skip all Schwab auth and go straight to mock mode
            session['authenticated'] = True
            session['mock_mode'] = True
            session.permanent = True
            
            logger.info("Using mock mode - skipping Schwab authentication")
            flash('🎭 Using MOCK data mode - Data is simulated for testing', 'warning')
            
            # Initialize features with mock mode
            _initialize_features(use_mock=True)
        else:
            # Try real Schwab authentication
            schwab_client = get_schwab_client()
            
            if schwab_client:
                session['authenticated'] = True
                session['mock_mode'] = False
                session.permanent = True
                
                logger.info("Authentication completed - Real mode")
                flash('✅ Connected to Schwab API - Using REAL market data', 'success')
                
                # Initialize features with real mode
                _initialize_features(use_mock=False)
            else:
                # Fallback to mock mode
                session['authenticated'] = True
                session['mock_mode'] = True
                session.permanent = True
                logger.info("Fallback to mock mode - no client available")
                flash('⚠️ Could not connect to Schwab API. Using MOCK data mode.', 'error')
                _initialize_features(use_mock=True)
        
        return redirect(url_for('index'))
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        session['authenticated'] = True
        session['mock_mode'] = True
        logger.info("Error fallback to mock mode")
        flash(f'Authentication error: {e}. Using MOCK data mode.', 'error')
        _initialize_features(use_mock=True)
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """Enhanced logout with feature cleanup"""
    _cleanup_features()
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

# Main routes
@app.route('/')
@require_auth
def index():
    """Main landing page - shows available features"""
    features = {
        'market_data': Config.ENABLE_MARKET_DATA,
        'market_data_initialized': feature_manager.is_feature_enabled('market_data')
    }
    
    return render_template('index.html', features=features)

@app.route('/historical-charts')
@require_auth
def historical_charts():
    """Historical charts viewer page"""
    try:
        # Get available symbols from watchlist
        import json
        watchlist_path = os.path.join(Config.BASE_DIR, 'watchlist.json')
        
        symbols = []
        if os.path.exists(watchlist_path):
            with open(watchlist_path, 'r') as f:
                watchlist_data = json.load(f)
                symbols = watchlist_data.get('symbols', [])
        
        return render_template('historical_charts.html', symbols=symbols)
    except Exception as e:
        logger.error(f"Error loading historical charts page: {e}")
        flash('Error loading historical charts page', 'error')
        return redirect(url_for('index'))

@app.route('/live-charts')
@require_auth
def live_charts():
    """Live charts viewer page"""
    return render_template('live_charts.html')

@app.route('/api/session-info')
@require_auth
def session_info():
    """API endpoint to get session information"""
    return jsonify({
        'authenticated': session.get('authenticated', False),
        'mock_mode': session.get('mock_mode', False)
    })

@app.route('/api/mock-speed', methods=['POST'])
@require_auth
def set_mock_speed():
    """API endpoint to set mock data update speed"""
    try:
        data = request.get_json()
        interval = float(data.get('interval', 1.0))
        
        # Validate interval bounds (allow very fast speeds for testing)
        interval = max(0.001, min(60.0, interval))
        
        # Update mock speed if in mock mode and market data is enabled
        if session.get('mock_mode') and feature_manager.is_feature_enabled('market_data'):
            market_data_manager = feature_manager.get_feature('market_data')
            if market_data_manager and hasattr(market_data_manager, 'equity_stream_manager'):
                stream_manager = market_data_manager.equity_stream_manager
                if hasattr(stream_manager, 'streamer') and stream_manager.streamer:
                    if hasattr(stream_manager.streamer, 'set_update_interval'):
                        stream_manager.streamer.set_update_interval(interval)
                        logger.info(f"Updated mock data speed to {interval}s interval")
                        return jsonify({'success': True, 'interval': interval})
                    else:
                        return jsonify({'success': False, 'error': 'Mock streamer does not support speed control'})
                else:
                    return jsonify({'success': False, 'error': 'Stream manager or streamer not available'})
            else:
                return jsonify({'success': False, 'error': 'Market data manager not available'})
        else:
            return jsonify({'success': False, 'error': 'Not in mock mode or market data disabled'})
            
    except Exception as e:
        logger.error(f"Error setting mock speed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/historical-data/<symbol>')
@require_auth
def get_historical_data(symbol):
    """API endpoint to serve historical OHLC data"""
    try:
        from historical_collection.core.ohlc_database import OHLCDatabase
        from datetime import datetime, timedelta
        
        # Get query parameters
        timeframe = request.args.get('timeframe', '1m')
        range_param = request.args.get('range', '1m')
        
        # Calculate date range
        end_date = datetime.now()
        
        if range_param == '1d':
            start_date = end_date - timedelta(days=1)
        elif range_param == '1w':
            start_date = end_date - timedelta(weeks=1)
        elif range_param == '1m':
            start_date = end_date - timedelta(days=30)
        elif range_param == '3m':
            start_date = end_date - timedelta(days=90)
        elif range_param == '6m':
            start_date = end_date - timedelta(days=180)
        elif range_param == '1y':
            start_date = end_date - timedelta(days=365)
        else:  # 'all'
            start_date = end_date - timedelta(days=365 * 10)  # 10 years max
        
        # Initialize database
        db_path = os.path.join(Config.DATA_DIR, 'historical_data.db')
        database = OHLCDatabase(db_path)
        
        # Get data from database
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())
        
        data = database.get_ohlc_data(symbol, start_timestamp, end_timestamp, timeframe)
        
        # Apply data limit for performance (max 10,000 points)
        max_points = 10000
        if len(data) > max_points:
            # Sample data to reduce points
            step = len(data) // max_points
            data = data[::step]
        
        return jsonify({
            'symbol': symbol,
            'timeframe': timeframe,
            'range': range_param,
            'count': len(data),
            'data': data
        })
        
    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {e}")
        return jsonify({
            'error': f'Error fetching data: {str(e)}'
        }), 500

@app.route('/api/test-data')
@require_auth
def test_data():
    """Test endpoint to verify API is working"""
    try:
        from historical_collection.core.ohlc_database import OHLCDatabase
        
        db_path = os.path.join(Config.DATA_DIR, 'historical_data.db')
        database = OHLCDatabase(db_path)
        
        # Get stats for all symbols
        import json
        watchlist_path = os.path.join(Config.BASE_DIR, 'watchlist.json')
        symbols = []
        if os.path.exists(watchlist_path):
            with open(watchlist_path, 'r') as f:
                watchlist_data = json.load(f)
                symbols = watchlist_data.get('symbols', [])
        
        stats = {}
        for symbol in symbols:
            stats[symbol] = database.get_symbol_stats(symbol)
        
        return jsonify({
            'database_path': db_path,
            'database_exists': os.path.exists(db_path),
            'symbols': symbols,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Test error: {str(e)}'
        }), 500

@app.route('/options-flow')
@require_auth
def options_flow():
    """Options flow dashboard page"""
    return render_template('options_flow.html')

@app.route('/chart-test')
@require_auth
def chart_test():
    """Simple chart test page"""
    return render_template('chart_test.html')

# Register blueprints conditionally
if Config.ENABLE_MARKET_DATA:
    logger.info("Registering market data routes...")
    from features.market_data_routes import market_data_bp
    app.register_blueprint(market_data_bp)
    logger.info("✅ Market data routes registered")
else:
    logger.info("Market data feature disabled")

# Register options routes
try:
    logger.info("Registering options flow routes...")
    from options_collection.api_routes import options_bp
    app.register_blueprint(options_bp)
    logger.info("✅ Options flow routes registered")
except Exception as e:
    logger.error(f"❌ Failed to register options routes: {e}")

# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    
    # Start streaming if market data is enabled and user is authenticated
    if session.get('authenticated') and feature_manager.is_feature_enabled('market_data'):
        try:
            market_data_manager = feature_manager.get_feature('market_data')
            if market_data_manager and not hasattr(market_data_manager, '_streaming_started'):
                success = market_data_manager.start_streaming()
                if success:
                    market_data_manager._streaming_started = True
                    logger.info("Started market data streaming for new client")
                else:
                    logger.error("Failed to start market data streaming")
        except Exception as e:
            logger.error(f"Error starting streaming on connect: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

# Features will be initialized when user authenticates
logger.info("🚀 Application started - features will be initialized on authentication")

if __name__ == '__main__':
    logger.info(f"Starting Flask-SocketIO server on {Config.HOST}:{Config.PORT}")
    logger.info(f"Debug mode: {Config.DEBUG}")
    logger.info(f"Features enabled: Market Data={Config.ENABLE_MARKET_DATA}")
    
    socketio.run(app, 
                host=Config.HOST, 
                port=Config.PORT, 
                debug=Config.DEBUG,
                allow_unsafe_werkzeug=True)