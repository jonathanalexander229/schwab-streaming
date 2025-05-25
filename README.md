# Schwab Market Data Streaming App

A simple Python web application that streams real-time market data using the Charles Schwab API with OAuth 2.0 authentication.

## 📁 Project Structure

```
schwab-market-app/
├── auth.py                    # OAuth authentication handler
├── app.py                     # Main Flask application
├── requirements.txt           # Python dependencies
├── .env.example              # Environment configuration template
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
# Edit .env with your Schwab API credentials
```

### 3. Run the Application
```bash
python app.py
```

### 4. Open Browser
Navigate to `http://localhost:5000`

## 🔧 Getting Schwab API Credentials (Optional)

1. Visit [https://developer.schwab.com/](https://developer.schwab.com/)
2. Create a developer account
3. Create a new **Individual Developer** application
4. Set callback URL to: `https://127.0.0.1:8443/callback`
5. Wait for approval (can take several days)
6. Add your **App Key** and **App Secret** to `.env`

## 💡 Features

- **OAuth 2.0 Authentication**: Secure login with Schwab
- **Real-time Streaming**: Live market data via WebSockets  
- **Mock Data Mode**: Works without API credentials
- **Automatic Token Refresh**: Background token management
- **Responsive Design**: Works on desktop and mobile
- **Database Storage**: Historical data persistence
- **Separated Assets**: Clean CSS/JS organization

## 🎯 How It Works

1. **Authentication**: Click "Authenticate with Schwab" 
2. **Login**: Browser opens to Schwab login page
3. **Authorization**: Grant permissions to your app
4. **Streaming**: Add stock symbols to watch live data
5. **Updates**: Real-time price changes via WebSocket

## 🧪 Mock Data Mode

If Schwab API credentials aren't configured, the app automatically uses mock data that simulates realistic market movements. Perfect for:

- Testing the application
- Development without API access  
- Learning the OAuth flow
- Demonstrating features

## 📊 Technical Details

- **Flask** web framework with **SocketIO** for real-time updates
- **SQLite** database for market data storage
- **schwabdev** library for Schwab API integration
- **Responsive HTML/CSS/JavaScript** frontend
- **Background threading** for token refresh and data generation
- **Modular asset structure** for maintainability

## 🏃‍♂️ Quick Start Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application  
python app.py

# Open browser to http://localhost:5000
# Click "Authenticate with Schwab" or use mock data
# Add symbols like AAPL, MSFT, GOOGL
# Watch real-time price updates!
```

## 📋 File Descriptions

### Core Files
- **`auth.py`**: Complete OAuth 2.0 implementation with token management
- **`app.py`**: Main Flask application with routes, WebSocket handlers, and mock data
- **`requirements.txt`**: Python dependencies
- **`.env.example`**: Environment variables template

### Templates
- **`templates/login.html`**: Clean login page with OAuth flow
- **`templates/index.html`**: Main application interface

### Static Assets
- **`static/css/login.css`**: Login page styling
- **`static/css/main.css`**: Main application styling with responsive design
- **`static/js/market-data.js`**: JavaScript functionality for real-time updates

## 🔒 Security Features

- **Secure token storage** in local JSON file
- **Automatic token refresh** before expiry
- **Session management** with Flask sessions
- **OAuth state validation** prevents attacks
- **Environment-based configuration**

## ⚠️ Important Notes

- App works with or without Schwab API credentials
- Market data is simulated if API not available
- Tokens are stored locally and auto-refreshed
- Use `Ctrl+C` to stop the server
- All styling is in separate CSS files for easy customization

## 🤝 Usage

This is a complete, working example of:
- OAuth 2.0 implementation with Schwab
- Real-time data streaming with WebSockets
- Professional web application structure
- Separated concerns (HTML, CSS, JS, Python)
- Error handling and fallback modes

Perfect for learning or as a foundation for larger trading applications!

---

## 🔧 Development Notes

### Adding New Styles
Edit `static/css/main.css` or `static/css/login.css` directly - no need to restart the Python server.

### Modifying JavaScript
Edit `static/js/market-data.js` for client-side functionality changes.

### Template Updates
Modify `templates/login.html` or `templates/index.html` for structural changes.

### Python Logic
Edit `app.py` for server-side functionality or `auth.py` for authentication logic.

This modular structure makes it easy to work on different aspects of the application independently!
