# Schwab Market Data Streaming App

A Python web application that streams real-time market data using the Charles Schwab API with **manual OAuth 2.0 authentication** and comprehensive **mock data testing framework**.

## 🏗️ Architecture Overview

The application uses a sophisticated real-time streaming architecture that combines Schwab's native WebSocket API with Flask-SocketIO for client distribution, plus a complete mock data system for testing and development.

### Key Components:
- **Schwab WebSocket API**: Direct real-time Level 1 equity quotes
- **schwabdev.Client**: Python wrapper handling OAuth 2.0 and streaming
- **Flask Application**: Main controller managing connections and data flow  
- **Message Handler**: Processes incoming WebSocket messages and filters data
- **Flask-SocketIO**: Distributes real-time updates to web clients
- **SQLite Database**: Persists historical market data with daily rotation
- **Mock Data Framework**: Complete simulation system for testing

## 📁 Project Structure

```
schwab-market-app/
├── auth.py                    # OAuth authentication with mock support
├── app.py                     # Main Flask application (update required)
├── mock_data.py               # Mock data framework (NEW)
├── requirements.txt           # Python dependencies
├── .env.example              # Environment configuration template
├── schwab_tokens.json        # Token storage (auto-generated)
├── templates/                # HTML templates
│   ├── login.html            # Login page
│   ├── index.html            # Main application (updated)
│   └── options_flow.html     # Options flow monitor (updated)
├── static/                   # Static assets
│   ├── css/
│   │   ├── login.css         # Login page styles
│   │   ├── main.css          # Main application styles
│   │   ├── options_flow.css  # Options flow styles
│   │   └── mock_indicators.css # Mock mode UI indicators (NEW)
│   └── js/
│       ├── market_data.js    # Equity streaming functionality
│       ├── options_flow.js   # Options flow functionality
│       └── mock_indicators.js # Mock mode UI management (NEW)
└── data/                     # Database storage
    ├── market_data_YYMMDD.db     # Real data
    └── MOCK_market_data_YYMMDD.db # Mock data (separate)
```

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Add Mock Framework Files
Create these new files:
- `mock_data.py` (complete mock framework)
- `static/css/mock_indicators.css` (UI indicators)
- `static/js/mock_indicators.js` (mock mode management)

### 3. Update Existing Files
Update these files with mock support:
- `auth.py` (add mock client support)
- `app.py` (add database separation and mock routes)
- `templates/index.html` (add mock indicators)
- `templates/options_flow.html` (add mock indicators)

### 4. Configure Environment (Optional)
```bash
cp .env.example .env
# Edit .env with your Schwab API credentials (optional - works without them)

# Add mock configuration
echo "USE_MOCK_DATA=false" >> .env
```

### 5. Run the Application
```bash
python app.py
```

The app will prompt you to choose between:
- **Schwab API** (real data - requires authentication)
- **Mock data** (simulated data - no authentication needed)

## 🧪 Testing Framework

### **Mock Data Features**
- ✅ **Realistic Market Simulation**: Base prices, volatility, volume patterns
- ✅ **Market Hours Awareness**: Pre-market, regular hours, after-hours behavior
- ✅ **Separate Database Storage**: `MOCK_market_data_YYMMDD.db` vs `market_data_YYMMDD.db`
- ✅ **UI Indicators**: Orange banners, badges, and card styling for mock mode
- ✅ **Market Event Simulation**: Bull runs, bear crashes, volatility spikes
- ✅ **Performance Testing**: Data generation speed and streaming rate validation

### **Running Tests**

#### **Unit Tests (Mock Framework Only)**
```bash
# Test mock data generation and streaming
python mock_data.py
```

#### **Quick Mock Validation**
```bash
# Fast validation of mock data quality
python test_integration.py --quick
```

#### **Full Integration Tests**
```bash
# Complete test suite including Flask app
python test_integration.py --full
```

#### **Create Simple Test Script**
```bash
# Generate standalone test script
python test_integration.py --simple
python simple_test.py
```

### **Development with Mock Data**

#### **Using Environment Variable**
```bash
# Automatic mock mode
export USE_MOCK_DATA=true
python app.py
```

#### **Interactive Mode Selection**
```bash
python app.py
# Choose option 2 when prompted for mock data
```

#### **Testing Market Events**
```bash
# Trigger market events via API (mock mode only)
curl -X POST http://localhost:8000/api/test/market-event \
  -H "Content-Type: application/json" \
  -d '{"event_type": "bullish_surge"}'

# Available events:
# - bullish_surge
# - bearish_crash  
# - high_volatility
# - low_volatility
# - market_open
# - market_close
```

## 🎭 Mock vs Real Data

### **Data Storage Separation**
- **Real Data**: `data/market_data_241201.db`
- **Mock Data**: `data/MOCK_market_data_241201.db`
- **No Data Mixing**: Completely separate databases and processing

### **UI Indicators**
- **Mock Mode**: Orange banner, 🎭 icons, "[MOCK]" in page title
- **Real Mode**: Green indicators, ✅ icons, "[LIVE]" in page title
- **Connection Status**: Orange dot for mock, green dot for real
- **Stock Cards**: Orange left border for mock data

### **Database Management**
```bash
# View database info
curl http://localhost:8000/api/admin/data-info

# Clean up mock databases
curl -X POST http://localhost:8000/api/admin/cleanup-mock
```

## 🔧 Getting Schwab API Credentials

1. Visit [https://developer.schwab.com/](https://developer.schwab.com/)
2. Create a developer account and wait for approval
3. Create a new **Individual Developer** application
4. **Important**: Set callback URL to: `https://127.0.0.1`
5. Add your **App Key** and **App Secret** to `.env` file

## 🔐 Authentication Flow

### **Real Data Mode**
1. **Check for existing tokens** - If authenticated before, uses those
2. **Try to refresh expired tokens** - Automatically refreshes if possible
3. **Manual authentication** - Opens browser for Schwab login
4. **Copy/paste redirect URL** - Secure manual verification
5. **Tokens saved** - Automatic token management

### **Mock Data Mode**
1. **No authentication required** - Instant access
2. **Realistic data simulation** - Market hours, volatility, trends
3. **Performance testing** - High-frequency updates available
4. **Event simulation** - Test market scenarios

## 💡 Features

### 📈 **Real-Time Equity Streaming**
- **WebSocket Architecture**: Millisecond-latency real-time streaming
- **Field-Based Subscriptions**: Last, Bid, Ask, Volume, High, Low, Net Change
- **Automatic Token Refresh**: Background token management
- **Connection Monitoring**: Real-time status indicators

### 📊 **Options Flow Analysis**  
- **Delta × Volume Analysis**: Real-time options flow sentiment
- **Interactive Charts**: Call/Put delta volume, net delta trends
- **Technical Indicators**: Momentum, volatility, trend strength
- **Market Status**: Pre-market, regular hours, after-hours detection

### 🧪 **Testing & Development**
- **Mock Data Mode**: Works without API credentials
- **Separate Data Storage**: No mixing of real and mock data
- **Market Event Simulation**: Test various market conditions
- **Performance Validation**: Verify app handles high-frequency updates
- **UI Test Framework**: Comprehensive integration testing

## 📊 Testing Examples

### **Basic Mock Test**
```python
from mock_data import MockSchwabClient
import time

# Create mock client
client = MockSchwabClient()
streamer = client.stream

# Start streaming
def handle_message(msg):
    print(f"Received: {msg}")

streamer.start(handle_message)
streamer.add_symbol('AAPL')
time.sleep(10)
streamer.stop()
```

### **Market Event Testing**
```python
# Simulate bullish market
streamer.simulate_market_event('bullish_surge')

# Simulate high volatility
streamer.simulate_market_event('high_volatility')

# Simulate market open
streamer.simulate_market_event('market_open')
```

### **Performance Testing**
```bash
# Test data generation speed
python -c "
from mock_data import MockMarketDataGenerator
import time
gen = MockMarketDataGenerator()
start = time.time()
for i in range(1000):
    gen.generate_quote('AAPL')
print(f'Generated 1000 quotes in {time.time()-start:.2f}s')
