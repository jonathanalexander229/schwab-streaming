# auth.py - Simple authentication using schwabdev library
import os
import dotenv
import schwabdev
from functools import wraps
from flask import session, redirect, url_for, jsonify, request

def get_schwab_client():
    """
    Initialize and return a real Schwab client for API access.
    Returns:    
        schwabdev.Client: The Schwab client instance or None if failed.
    """
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
    Get the real Schwab streamer object for real-time data.
    Returns:
        schwabdev.Streamer: The Schwab streamer instance if available, otherwise None.
    """
    client = get_schwab_client()
    if client:
        return client.stream
    return None

def require_auth(f):
    """
    Decorator to require authentication for routes.
    Redirects unauthenticated users to login page for HTML requests.
    Returns 401 JSON error for API requests.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        authenticated = session.get('authenticated')
        print(f"🔍 require_auth check: path={request.path}, authenticated={authenticated}, session_keys={list(session.keys())}")
        
        if not authenticated:
            # Check if this is an API request (JSON content type or /api/ path)
            if (request.is_json or 
                request.path.startswith('/api/') or 
                request.headers.get('Content-Type') == 'application/json'):
                return jsonify({'error': 'Not authenticated'}), 401
            else:
                # HTML request - redirect to login
                print(f"🔄 Redirecting to login from {request.path}")
                return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function