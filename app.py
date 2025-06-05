# app.py - Modular Flask Application for Market Data Streaming
import os
import logging
from datetime import timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_socketio import SocketIO
from dotenv import load_dotenv
from auth import get_schwab_client, get_schwab_streamer

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

# Global variables for Schwab client
schwab_client = None
schwab_streamer = None
global_mock_mode = False

# Create required directories
os.makedirs(Config.DATA_DIR, exist_ok=True)
os.makedirs(Config.TEMPLATES_DIR, exist_ok=True)
os.makedirs(os.path.join(Config.STATIC_DIR, 'css'), exist_ok=True)
os.makedirs(os.path.join(Config.STATIC_DIR, 'js'), exist_ok=True)

# Authentication routes
@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/authenticate')
def authenticate():
    """Enhanced authentication with mock mode tracking"""
    global schwab_client, schwab_streamer, global_mock_mode
    
    try:
        # Determine if using mock mode
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
            logger.info(f"Client class: {schwab_client.__class__.__name__}")
            
            # Initialize enabled features
            initialize_features(is_mock_mode)
            
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
    """Enhanced logout with feature cleanup"""
    global global_mock_mode
    
    # Clean up features
    cleanup_features()
    
    session.clear()
    global_mock_mode = False
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

# Default routes
@app.route('/')
def index():
    """Default route - redirect to appropriate feature or login"""
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    
    # Check if we need to initialize features with Schwab clients
    global schwab_client, schwab_streamer
    if schwab_client is None:
        # User is authenticated but no Schwab client - need to reinitialize
        logger.info("User authenticated but no Schwab client found - reinitializing...")
        
        # Determine mock mode - environment variable takes precedence over session
        env_mock = os.getenv('USE_MOCK_DATA', 'false').lower() == 'true'
        use_mock = env_mock
        
        # Get Schwab client
        from auth import get_schwab_client
        schwab_client = get_schwab_client(use_mock)
        if schwab_client:
            schwab_streamer = schwab_client.stream
            
            # Determine actual mock mode and update session
            is_mock_mode = hasattr(schwab_client, '__class__') and 'Mock' in schwab_client.__class__.__name__
            session['mock_mode'] = is_mock_mode
            global_mock_mode = is_mock_mode
            
            logger.info(f"Reinitialized with mock mode: {is_mock_mode}")
            
            # Reinitialize features with proper clients
            initialize_features(is_mock_mode)
    
    # If market data is enabled, show market data page directly
    if Config.ENABLE_MARKET_DATA:
        return render_template('index.html')
    else:
        # No features enabled, show basic page
        return render_template('index.html')

# Feature initialization functions
def initialize_features(is_mock_mode: bool):
    """Initialize enabled features"""
    logger.info("Initializing enabled features...")
    
    if Config.ENABLE_MARKET_DATA:
        initialize_market_data_feature(is_mock_mode)

def initialize_market_data_feature(is_mock_mode: bool):
    """Initialize market data feature"""
    try:
        from market_data import get_market_data_manager
        from market_data_routes import start_market_data_streaming
        
        logger.info("Initializing market data feature...")
        
        # Get existing manager or create new one
        manager = get_market_data_manager()
        if manager:
            # Update existing manager with Schwab clients
            logger.info("Updating existing market data manager with Schwab clients")
            manager.set_dependencies(schwab_client, schwab_streamer, socketio, is_mock_mode)
        else:
            # Create new manager
            from market_data_routes import initialize_market_data
            manager = initialize_market_data(
                Config.DATA_DIR, 
                schwab_client, 
                schwab_streamer, 
                socketio, 
                is_mock_mode
            )
        
        if manager:
            # Start streaming
            success = start_market_data_streaming()
            if success:
                logger.info("Market data streaming started successfully")
            else:
                logger.warning("Failed to start market data streaming")
        else:
            logger.error("Failed to initialize market data manager")
            
    except Exception as e:
        logger.error(f"Error initializing market data feature: {e}")


def cleanup_features():
    """Clean up all enabled features"""
    if Config.ENABLE_MARKET_DATA:
        try:
            from market_data_routes import stop_market_data_streaming
            stop_market_data_streaming()
            logger.info("Market data streaming stopped")
        except Exception as e:
            logger.error(f"Error stopping market data: {e}")

# Register feature blueprints
def register_blueprints():
    """Register blueprints for enabled features"""
    if Config.ENABLE_MARKET_DATA:
        try:
            from market_data_routes import market_data_bp
            app.register_blueprint(market_data_bp)
            logger.info("Market data blueprint registered")
        except Exception as e:
            logger.error(f"Error registering market data blueprint: {e}")

# Application initialization
def initialize_app():
    """Initialize the application"""
    print("\n" + "="*80)
    print("🚀 SCHWAB MARKET DATA STREAMING APP")
    print("="*80)
    
    # Load environment variables
    load_dotenv()
    
    # Feature status
    features = []
    if Config.ENABLE_MARKET_DATA:
        features.append("📊 Market Data")
    
    if features:
        print(f"🔧 Enabled features: {', '.join(features)}")
    else:
        print("⚠️  No features enabled - check environment variables")
    
    # Register blueprints
    register_blueprints()
    
    # Check environment variable for mock mode first
    env_mock = os.getenv('USE_MOCK_DATA', 'false').lower() == 'true'
    
    # Initialize features even without authentication for basic functionality
    if Config.ENABLE_MARKET_DATA:
        try:
            from market_data_routes import initialize_market_data
            # Initialize with None clients - will be set during authentication
            # Use environment variable to determine mock mode
            initialize_market_data(Config.DATA_DIR, None, None, socketio, env_mock)
            print("📊 Market data manager pre-initialized")
        except Exception as e:
            logger.error(f"Failed to pre-initialize market data: {e}")
    
    if env_mock:
        print("🎭 Environment variable USE_MOCK_DATA=true - using MOCK mode")
    else:
        print("✅ Environment variable USE_MOCK_DATA=false - using REAL Schwab API mode")
    
    print(f"🌐 Starting web server at http://localhost:{Config.PORT}")
    
    if features:
        print("🔗 Available endpoints:")
        if Config.ENABLE_MARKET_DATA:
            print("   📊 Market Data: /")
    
    print("="*80)
    
    logger.info(f"Application initialized with features: {', '.join(features) if features else 'None'}")

# Main execution
if __name__ == '__main__':
    try:
        # Only initialize once (not on restart)
        if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
            initialize_app()
        
        # Run with debug=False to prevent automatic restarts
        socketio.run(app, debug=False, host=Config.HOST, port=Config.PORT)
        
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
        
        # Clean shutdown
        cleanup_features()
        
        if schwab_streamer:
            schwab_streamer.stop()
            
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"❌ Error: {e}")