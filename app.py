# app.py - Modular Flask Application for Market Data Streaming
import os
import logging
from datetime import timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_socketio import SocketIO
from dotenv import load_dotenv
from auth import get_schwab_client, get_schwab_streamer, require_auth
from core import FeatureManager

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
socketio = SocketIO(app, cors_allowed_origins="*")

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
            schwab_client = get_schwab_client(use_mock=use_mock)
            schwab_streamer = get_schwab_streamer()
            
            market_data_manager = feature_manager.initialize_market_data(
                schwab_client, schwab_streamer, use_mock
            )
            
            if market_data_manager:
                logger.info(f"✅ Market data initialized ({'mock' if use_mock else 'real'} mode)")
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
        # Determine if using mock mode
        use_mock = (
            request.args.get('mock', 'false').lower() == 'true' or
            os.getenv('USE_MOCK_DATA', 'false').lower() == 'true'
        )
        
        schwab_client = get_schwab_client(use_mock)
        
        if schwab_client:
            session['authenticated'] = True
            session.permanent = True
            
            # Determine if we're actually in mock mode by checking the client class
            is_mock_mode = hasattr(schwab_client, '__class__') and 'Mock' in schwab_client.__class__.__name__
            session['mock_mode'] = is_mock_mode
            
            # Debug logging
            logger.info(f"Authentication completed - Mock mode: {is_mock_mode}")
            logger.info(f"Client class: {schwab_client.__class__.__name__}")
            
            # Initialize enabled features
            _initialize_features(is_mock_mode)
            
            if is_mock_mode:
                flash('🎭 Using MOCK data mode - Data is simulated for testing', 'warning')
            else:
                flash('✅ Connected to Schwab API - Using REAL market data', 'success')
        else:
            # Fallback to mock mode
            session['authenticated'] = True
            session['mock_mode'] = True
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

# Register blueprints conditionally
if Config.ENABLE_MARKET_DATA:
    logger.info("Registering market data routes...")
    from market_data_routes import market_data_bp
    app.register_blueprint(market_data_bp)
    logger.info("✅ Market data routes registered")
else:
    logger.info("Market data feature disabled")

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

# Initialize features at startup with mock mode by default
with app.app_context():
    logger.info("🚀 Initializing features at startup...")
    _initialize_features(use_mock=True)  # Start with mock mode
    logger.info(f"🎯 Features initialized: {list(feature_manager.features.keys())}")

if __name__ == '__main__':
    logger.info(f"Starting Flask-SocketIO server on {Config.HOST}:{Config.PORT}")
    logger.info(f"Debug mode: {Config.DEBUG}")
    logger.info(f"Features enabled: Market Data={Config.ENABLE_MARKET_DATA}")
    
    socketio.run(app, 
                host=Config.HOST, 
                port=Config.PORT, 
                debug=Config.DEBUG,
                allow_unsafe_werkzeug=True)