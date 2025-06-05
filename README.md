# Schwab Market Data Streaming App

A **modular Python web application** that streams real-time market data using the Charles Schwab API with **manual OAuth 2.0 authentication** and comprehensive **mock data testing framework**.

## 🏗️ Modular Architecture Overview

The application uses a **modular microservice-like architecture** with feature toggles, separate Flask blueprints, and environment-driven configuration for scalable development and deployment.

### Core Architecture:
- **🎛️ Feature Toggle System**: Environment-controlled module loading (`ENABLE_MARKET_DATA`, `ENABLE_OPTIONS_FLOW`)
- **📦 Flask Blueprints**: Modular route organization with independent initialization
- **🔄 Dependency Injection**: Loose coupling between modules through manager pattern
- **🎭 Mock/Real Mode Switching**: Seamless environment-controlled data source switching
- **📊 Persistent Data Layer**: SQLite with automatic mock/real data separation

### Key Modules:
- **🔐 Authentication Module** (`auth.py`): OAuth 2.0 + mock client factory
- **📈 Market Data Module** (`market_data.py`, `market_data_routes.py`): Real-time equity streaming
- **📊 Options Flow Module** (`options_flow.py`, `options_flow_routes.py`): Options analysis (ready for future)
- **🎭 Mock Data Framework** (`mock_data.py`): Complete market simulation system
- **⚙️ App Orchestrator** (`app.py`): Feature initialization and blueprint registration

## 📁 Modular Project Structure

```
schwab-streaming/
├── 🎛️ Core Application
│   ├── app.py                     # Feature orchestrator & Flask app
│   ├── auth.py                    # Authentication with mock/real client factory
│   └── requirements.txt           # Python dependencies
├── 📈 Market Data Module
│   ├── market_data.py             # MarketDataManager class
│   ├── market_data_routes.py      # Market data Flask blueprint  
│   └── watchlist.json             # Persistent watchlist storage
├── 📊 Options Flow Module (Future)
│   ├── options_flow.py            # OptionsFlowMonitor class
│   └── options_flow_routes.py     # Options flow Flask blueprint
├── 🎭 Testing & Mock Framework
│   ├── mock_data.py               # Complete mock data simulation
│   └── test_integration.py        # Integration test suite
├── 🌐 Web Interface
│   ├── templates/
│   │   ├── login.html             # Authentication page
│   │   └── index.html             # Market data interface
│   └── static/
│       ├── css/
│       │   ├── main.css           # Core application styles
│       │   └── mock_indicators.css # Mock mode UI indicators
│       └── js/
│           └── market_data.js     # Real-time streaming client
├── 📊 Data Layer
│   └── data/                      # SQLite databases
│       ├── market_data_YYMMDD.db      # Real market data
│       └── MOCK_market_data_YYMMDD.db # Mock data (separate)
└── ⚙️ Configuration
    ├── .env.example               # Environment template
    └── .env                       # Environment configuration
```

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings:

# Feature toggles
ENABLE_MARKET_DATA=true
ENABLE_OPTIONS_FLOW=false

# Data source mode
USE_MOCK_DATA=false  # true for mock data, false for real Schwab API

# Schwab API credentials (optional - only needed for real data)
SCHWAB_APP_KEY=your_app_key_here
SCHWAB_APP_SECRET=your_app_secret_here
```

### 3. Run the Application
```bash
# Using environment variables
USE_MOCK_DATA=true python app.py

# Or with .env configuration
python app.py
```

### 4. Access the Application
- **Mock Mode**: Instant access with simulated data
- **Real Mode**: OAuth authentication with Schwab API

## 🏗️ Modular Architecture Details

### **Feature Toggle System**
```python
# Environment-driven feature loading
ENABLE_MARKET_DATA=true    # Load market data module
ENABLE_OPTIONS_FLOW=false  # Skip options flow module
USE_MOCK_DATA=true         # Use mock data instead of Schwab API
```

### **Module Independence**
- **Market Data Module**: Standalone with `MarketDataManager` class
- **Options Flow Module**: Independent with `OptionsFlowMonitor` class  
- **Mock Framework**: Complete simulation without external dependencies
- **Flask Blueprints**: Modular route registration with `/api` namespacing

### **Dependency Injection Pattern**
```python
# Loose coupling through manager pattern
manager = MarketDataManager(data_dir)
manager.set_dependencies(schwab_client, schwab_streamer, socketio, is_mock_mode)

# Feature initialization with dependency injection
initialize_market_data_feature(is_mock_mode)
initialize_options_flow_feature(is_mock_mode)
```

### **Data Separation**
- **Real Data**: `data/market_data_YYMMDD.db`
- **Mock Data**: `data/MOCK_market_data_YYMMDD.db`
- **Watchlist**: `watchlist.json` (persistent across sessions)
- **Configuration**: `.env` file with environment variables

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
