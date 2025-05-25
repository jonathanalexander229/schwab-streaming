# auth.py - OAuth Authentication Handler
import os
import base64
import json
import webbrowser
import urllib.parse
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv
import threading
import time
from flask import Flask, request
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SchwabAuth:
    def __init__(self, app_key=None, app_secret=None, callback_url=None, token_path=None):
        self.app_key = app_key or os.getenv('SCHWAB_APP_KEY')
        self.app_secret = app_secret or os.getenv('SCHWAB_APP_SECRET')
        self.callback_url = callback_url or os.getenv('SCHWAB_CALLBACK_URL', 'https://127.0.0.1:8443/callback')
        self.token_path = token_path or os.getenv('SCHWAB_TOKEN_PATH', './schwab_tokens.json')
        
        # Schwab OAuth endpoints
        self.auth_url = "https://api.schwabapi.com/v1/oauth/authorize"
        self.token_url = "https://api.schwabapi.com/v1/oauth/token"
        
        # Token storage
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self.oauth_state = None
        self.authorization_code = None
        
        if not self.app_key or not self.app_secret:
            logger.warning("Schwab API credentials not found. Using mock data mode.")
    
    def construct_auth_url(self):
        import secrets
        self.oauth_state = secrets.token_urlsafe(32)
        
        params = {
            'client_id': self.app_key,
            'redirect_uri': self.callback_url,
            'response_type': 'code',
            'state': self.oauth_state,
            'scope': 'readonly'
        }
        
        auth_url = f"{self.auth_url}?" + urllib.parse.urlencode(params)
        return auth_url
    
    def start_callback_server(self):
        callback_app = Flask(__name__)
        
        @callback_app.route('/callback')
        def oauth_callback():
            code = request.args.get('code')
            state = request.args.get('state')
            error = request.args.get('error')
            
            if error:
                return f"<h1>OAuth Error</h1><p>{error}</p>", 400
            
            if not code or state != self.oauth_state:
                return "<h1>Error</h1><p>Invalid authorization response</p>", 400
            
            self.authorization_code = code
            threading.Thread(target=self._shutdown_server, daemon=True).start()
            
            return """
            <h1>Authorization Successful!</h1>
            <p>You can close this window and return to your application.</p>
            <script>setTimeout(function() { window.close(); }, 3000);</script>
            """
        
        # Start server in thread
        import socket
        parsed_url = urllib.parse.urlparse(self.callback_url)
        port = parsed_url.port or 8443
        
        def run_server():
            callback_app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)
        
        self.callback_server = threading.Thread(target=run_server, daemon=True)
        self.callback_server.start()
        logger.info(f"Callback server started on port {port}")
    
    def _shutdown_server(self):
        time.sleep(2)
        import signal
        import os
        os.kill(os.getpid(), signal.SIGTERM)
    
    def exchange_code_for_tokens(self):
        if not self.authorization_code:
            raise ValueError("No authorization code available")
        
        credentials = f"{self.app_key}:{self.app_secret}"
        base64_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        
        headers = {
            "Authorization": f"Basic {base64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        payload = {
            "grant_type": "authorization_code",
            "code": self.authorization_code,
            "redirect_uri": self.callback_url,
        }
        
        response = requests.post(self.token_url, headers=headers, data=payload)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data.get('access_token')
        self.refresh_token = token_data.get('refresh_token')
        
        expires_in = token_data.get('expires_in', 1800)
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        self.save_tokens()
        return token_data
    
    def refresh_access_token(self):
        if not self.refresh_token:
            raise ValueError("No refresh token available")
        
        credentials = f"{self.app_key}:{self.app_secret}"
        base64_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        
        headers = {
            "Authorization": f"Basic {base64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        
        response = requests.post(self.token_url, headers=headers, data=payload)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data.get('access_token')
        if 'refresh_token' in token_data:
            self.refresh_token = token_data['refresh_token']
        
        expires_in = token_data.get('expires_in', 1800)
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        self.save_tokens()
        return token_data
    
    def save_tokens(self):
        token_data = {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'expires_at': self.token_expires_at.isoformat() if self.token_expires_at else None,
            'app_key': self.app_key,
            'created_at': datetime.now().isoformat()
        }
        
        try:
            with open(self.token_path, 'w') as f:
                json.dump(token_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")
    
    def load_tokens(self):
        try:
            if not os.path.exists(self.token_path):
                return False
            
            with open(self.token_path, 'r') as f:
                token_data = json.load(f)
            
            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
            
            expires_at_str = token_data.get('expires_at')
            if expires_at_str:
                self.token_expires_at = datetime.fromisoformat(expires_at_str)
            
            return True
        except Exception as e:
            logger.error(f"Error loading tokens: {e}")
            return False
    
    def is_token_valid(self):
        if not self.access_token or not self.token_expires_at:
            return False
        return datetime.now() < (self.token_expires_at - timedelta(minutes=5))
    
    def get_valid_token(self):
        if not self.access_token:
            self.load_tokens()
        
        if self.is_token_valid():
            return self.access_token
        
        if self.refresh_token:
            try:
                self.refresh_access_token()
                return self.access_token
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
        
        return None
    
    def authenticate(self, auto_open_browser=True):
        try:
            if self.load_tokens() and self.is_token_valid():
                return True
            
            if self.refresh_token:
                try:
                    self.refresh_access_token()
                    return True
                except Exception:
                    pass
            
            # Start OAuth flow
            self.start_callback_server()
            auth_url = self.construct_auth_url()
            
            print("\n" + "="*60)
            print("SCHWAB OAUTH AUTHENTICATION")
            print("="*60)
            print(f"1. Open this URL: {auth_url}")
            print("2. Login and authorize the application")
            print("3. Wait for the callback...")
            print("="*60)
            
            if auto_open_browser:
                webbrowser.open(auth_url)
            
            # Wait for authorization code
            timeout = 300
            start_time = time.time()
            
            while not self.authorization_code and (time.time() - start_time) < timeout:
                time.sleep(1)
            
            if not self.authorization_code:
                return False
            
            self.exchange_code_for_tokens()
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
