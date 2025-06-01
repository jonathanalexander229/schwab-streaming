# auth.py - Simple authentication using schwabdev library
import os
import dotenv
import schwabdev

def get_schwab_client(use_mock=False):
    """
    Initialize and return a Schwab client for API access.
    If `use_mock` is True, it will return a mock client instead.
    This is useful for testing without hitting the real API.
    Returns:    
        schwabdev.Client or MockSchwabClient: The Schwab client instance.
    """
    if use_mock or os.getenv('USE_MOCK_DATA', 'false').lower() == 'true':
        from mock_data import MockSchwabClient
        print("🎭 Using mock Schwab client")
        return MockSchwabClient()
    
    try:
        # Load environment variables
        dotenv.load_dotenv()
        app_key = os.getenv("SCHWAB_APP_KEY")
        app_secret = os.getenv("SCHWAB_APP_SECRET")
        
        if not app_key or not app_secret:
            print("❌ SCHWAB_APP_KEY and SCHWAB_APP_SECRET must be set in .env file")
            return None
        
        print("🔐 Connecting to Schwab API...")
        
        # Create client - this will handle authentication automatically
        client = schwabdev.Client(app_key, app_secret)
        
        print("✅ Connected to Schwab API")
        return client
        
    except Exception as e:
        print(f"❌ Failed to connect to Schwab API: {e}")
        return None

def get_schwab_streamer():
    """
    Get the Schwab streamer object for real-time data.
    Returns:
        schwabdev.Streamer: The Schwab streamer instance if connected, otherwise None.
    """
    client = get_schwab_client()
    if client:
        return client.stream
    return None