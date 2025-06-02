# debug_schwab_mode.py - Systematic debugging for Schwab API mode

import os
import sys
import logging
from dotenv import load_dotenv

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug.log')
    ]
)
logger = logging.getLogger(__name__)

def test_environment():
    """Test environment setup"""
    print("="*60)
    print("1. TESTING ENVIRONMENT")
    print("="*60)
    
    load_dotenv()
    
    # Check environment variables
    use_mock = os.getenv('USE_MOCK_DATA', 'false').lower()
    app_key = os.getenv('SCHWAB_APP_KEY')
    app_secret = os.getenv('SCHWAB_APP_SECRET')
    
    print(f"USE_MOCK_DATA: {use_mock}")
    print(f"SCHWAB_APP_KEY: {'Set' if app_key else 'Not set'}")
    print(f"SCHWAB_APP_SECRET: {'Set' if app_secret else 'Not set'}")
    print(f"Expected mock mode: {use_mock == 'true'}")
    
    return use_mock == 'true'

def test_imports():
    """Test all imports"""
    print("\n" + "="*60)
    print("2. TESTING IMPORTS")
    print("="*60)
    
    try:
        import schwabdev
        print("✅ schwabdev imported successfully")
        print(f"   Version: {getattr(schwabdev, '__version__', 'unknown')}")
    except Exception as e:
        print(f"❌ schwabdev import failed: {e}")
        return False
    
    try:
        from mock_data import MockSchwabClient
        print("✅ MockSchwabClient imported successfully")
    except Exception as e:
        print(f"❌ MockSchwabClient import failed: {e}")
        return False
    
    try:
        from flask import Flask
        from flask_socketio import SocketIO
        print("✅ Flask imports successful")
    except Exception as e:
        print(f"❌ Flask imports failed: {e}")
        return False
    
    return True

def test_schwab_client(use_mock=False):
    """Test Schwab client creation"""
    print("\n" + "="*60)
    print(f"3. TESTING SCHWAB CLIENT (mock={use_mock})")
    print("="*60)
    
    try:
        if use_mock:
            from mock_data import MockSchwabClient
            client = MockSchwabClient()
            print("✅ Mock client created successfully")
        else:
            import schwabdev
            load_dotenv()
            app_key = os.getenv("SCHWAB_APP_KEY")
            app_secret = os.getenv("SCHWAB_APP_SECRET")
            
            print("Creating real Schwab client...")
            print("This may open a browser for authentication...")
            
            client = schwabdev.Client(app_key, app_secret, callback_url="https://127.0.0.1")
            print("✅ Real Schwab client created successfully")
        
        # Test client attributes
        print(f"Client class: {client.__class__.__name__}")
        print(f"Has stream attribute: {hasattr(client, 'stream')}")
        
        if hasattr(client, 'stream'):
            streamer = client.stream
            print(f"Streamer class: {streamer.__class__.__name__}")
            print(f"Streamer has start method: {hasattr(streamer, 'start')}")
            print(f"Streamer has send method: {hasattr(streamer, 'send')}")
            
            if use_mock:
                print(f"Mock streamer has add_symbol: {hasattr(streamer, 'add_symbol')}")
            else:
                print(f"Real streamer has level_one_equities: {hasattr(streamer, 'level_one_equities')}")
        
        return client
        
    except Exception as e:
        print(f"❌ Client creation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_flask_app_basic():
    """Test basic Flask app creation"""
    print("\n" + "="*60)
    print("4. TESTING BASIC FLASK APP")
    print("="*60)
    
    try:
        from flask import Flask
        from flask_socketio import SocketIO
        
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test-key'
        socketio = SocketIO(app, cors_allowed_origins="*")
        
        @app.route('/')
        def index():
            return "Hello World"
        
        print("✅ Basic Flask app created")
        print("✅ SocketIO initialized")
        print("✅ Basic route defined")
        
        return app, socketio
        
    except Exception as e:
        print(f"❌ Flask app creation failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def test_streaming(client, use_mock=False):
    """Test streaming functionality"""
    print("\n" + "="*60)
    print("5. TESTING STREAMING")
    print("="*60)
    
    if not client:
        print("❌ No client to test streaming")
        return False
    
    try:
        streamer = client.stream
        received_messages = []
        
        def message_handler(message):
            received_messages.append(message)
            print(f"📥 Received message: {message[:100]}...")
        
        print("Starting streamer...")
        streamer.start(message_handler)
        
        print("Adding test symbol...")
        if use_mock:
            streamer.add_symbol('AAPL')
        else:
            subscription = streamer.level_one_equities('AAPL', '0,1,2,3,8')
            streamer.send(subscription)
        
        print("Waiting 5 seconds for messages...")
        import time
        time.sleep(5)
        
        print("Stopping streamer...")
        streamer.stop()
        
        print(f"✅ Received {len(received_messages)} messages")
        return len(received_messages) > 0
        
    except Exception as e:
        print(f"❌ Streaming test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("SCHWAB API MODE DEBUG SCRIPT")
    print("This will test each component systematically")
    
    # Test 1: Environment
    expected_mock = test_environment()
    
    # Test 2: Imports
    if not test_imports():
        print("\n❌ CRITICAL: Import failures detected")
        return
    
    # Test 3: Client creation
    print(f"\nTesting with mock mode: {expected_mock}")
    client = test_schwab_client(use_mock=expected_mock)
    
    # Test 4: Basic Flask
    app, socketio = test_flask_app_basic()
    
    # Test 5: Streaming
    if client:
        test_streaming(client, use_mock=expected_mock)
    
    print("\n" + "="*60)
    print("DEBUG SUMMARY")
    print("="*60)
    print("Check the output above for any ❌ failures")
    print("The debug.log file contains detailed logs")
    print("Run with: python debug_schwab_mode.py")

if __name__ == "__main__":
    main()