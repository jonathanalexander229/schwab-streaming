# Schwab Market Data Streaming App

A Python web application that streams real-time market data using the Charles Schwab API with **manual OAuth 2.0 authentication** (matching the market depth app approach).

## 📁 Project Structure

```
schwab-market-app/
├── auth.py                    # OAuth authentication handler (manual flow)
├── authenticate.py            # Standalone CLI authentication script
├── app.py                     # Main Flask application
├── requirements.txt           # Python dependencies
├── .env.example              # Environment configuration template
├── schwab_tokens.json        # Token storage (auto-generated)
├── templates/                # HTML templates
│   ├── login.html            # Login page
│   └── index.html            # Main application
└── static/                   # Static assets
    ├── css/
    │   ├── login.css         # Login page styles
    │   └── main.css          # Main application styles
    └── js/
        └── market-data.js    # JavaScript functionality
```

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
```bash
cp .env.example .env
# Edit .env with your Schwab API credentials (optional - works without them)
```

### 3. Run the Application
```bash
python app.py
```

The app will prompt you to choose between:
- **Schwab API** (real data - requires authentication)
- **Mock data** (simulated data - no authentication needed)

### 4. Open Browser
Navigate to `http://localhost:8000`

## 🔧 Getting Schwab API Credentials

1. Visit [https://developer.schwab.com/](https://developer.schwab.com/)
2. Create a developer account and wait for approval
3. Create a new **Individual Developer** application
4. **Important**: Set callback URL to: `https://127.0.0.1`
5. Add your **App Key** and **App Secret** to `.env` file

## 🔐 Authentication Flow (Built-in)

When you run `python app.py`, the application will:

1. **Check for existing tokens** - If you've authenticated before, it uses those
2. **Try to refresh expired tokens** - Automatically refreshes if possible
3. **Prompt for authentication choice** - If no valid tokens found:

```bash
================================================================================
🚀 SCHWAB MARKET DATA STREAMING APP
================================================================================
Choose your data source:
1. Schwab API (real market data - requires authentication)
2. Mock data (simulated data - no authentication needed)
================================================================================

Enter your choice (1 or 2): 1
```

### If you choose Schwab API :
1. **Browser Opens**: Automatically opens Schwab login page
2. **Login**: Enter your Schwab credentials  
3. **Authorize**: Grant permissions to your app
4. **Copy URL**: After authorization, copy the entire redirect URL
5. **Paste URL**: Paste it into the terminal when prompted
6. **Tokens Saved**: Authentication tokens are saved for future use

## 💡 Features

- **Manual OAuth 2.0**: Simple copy/paste authentication flow
- **Real-time Streaming**: Live market data via WebSockets  
- **Mock Data Mode**: Works without API credentials
- **Automatic Token Refresh**: Background token management
- **Responsive Design**: Works on desktop and mobile
- **Database Storage**: Historical data persistence
- **CLI Authentication**: Standalone authentication script

## 🧪 Mock Data Mode

If you don't authenticate with Schwab, the app automatically uses realistic mock data:

- Simulates live price movements
- Perfect for testing and development
- No API credentials required
- Full functionality demonstration

## 📊 Usage Examples

### Quick Start (Single Command)
```bash
# One command does everything!
python app.py

# Choose option 2 for mock data (no setup required)
# Or choose option 1 for real Schwab data (requires API credentials)
```

### Example Session:
```bash
$ python app.py

================================================================================
🚀 SCHWAB MARKET DATA STREAMING APP
================================================================================
Choose your data source:
1. Schwab API (real market data - requires authentication)
2. Mock data (simulated data - no authentication needed)
================================================================================

Enter your choice (1 or 2): 2

🎭 Using mock data mode
🌐 Starting web server at http://localhost:8000
📊 Add stock symbols to start streaming market data
================================================================================
```

## 🔒 Security Features

- **Secure token storage** in local JSON file
- **Manual URL verification** prevents automated attacks
- **Automatic token refresh** before expiry
- **Session management** with Flask sessions
- **OAuth state validation** prevents CSRF attacks

## 🛠️ Technical Details

- **Flask** web framework with **SocketIO** for real-time updates
- **SQLite** database for market data storage
- **Manual OAuth flow** matching market depth app approach
- **schwabdev** library for Schwab API integration
- **Background threading** for token refresh and data generation

## 📋 File Descriptions

### Core Files
- **`auth.py`**: OAuth 2.0 implementation with manual URL flow
- **`app.py`**: Main Flask application with integrated authentication
- **`.env.example`**: Environment variables template

### Authentication Files
- **`schwab_tokens.json`**: Automatically created token storage
- **`.env`**: Your API credentials (create from .env.example)

## 🔧 Configuration

### Required Environment Variables
```bash
# Schwab API Credentials
SCHWAB_APP_KEY=your_app_key_here
SCHWAB_APP_SECRET=your_app_secret_here

# Callback URL (must match your Schwab app settings)
SCHWAB_CALLBACK_URL=https://127.0.0.1

# Optional Flask settings
FLASK_SECRET_KEY=your_secret_key_here
FLASK_DEBUG=True
```

### Schwab Developer App Settings
- **App Type**: Individual Developer
- **Callback URL**: `https://127.0.0.1` (exactly)
- **Scopes**: readonly (for market data)

## ⚠️ Important Notes

- **Callback URL**: Must be exactly `https://127.0.0.1` in both your Schwab app settings and .env file
- **Manual Process**: You'll need to copy/paste the redirect URL (this is intentional for security)
- **Token Persistence**: Tokens are saved locally and auto-refreshed

## 🚀 Quick Commands

```bash
# Run the application (choose authentication in the prompt)
python app.py

# That's it! Everything is handled in one command.
```

## 🎯 Perfect For

- Learning OAuth 2.0 implementation
- Building trading applications
- Real-time data streaming projects
- Schwab API integration examples
- Secure authentication patterns

The manual authentication flow provides better security and matches the proven approach used in the market depth application!
