# Schwab Streaming Application

A modular Flask-based web application for streaming market data from Charles Schwab API with real-time visualization.

## Features

- 🔐 **Authentication**: Secure login with Schwab API or mock mode for testing
- 📊 **Real-time Market Data**: Live streaming of equity quotes and prices
- 📋 **Watchlist Management**: Add/remove symbols to track
- 💾 **Data Storage**: SQLite database with automatic data separation (mock vs real)
- 🎭 **Mock Mode**: Simulated market data for testing without hitting real API
- 🌐 **WebSocket Support**: Real-time updates via Socket.IO
- 📱 **Responsive UI**: Clean, modern interface that works on all devices
- 🏗️ **Modular Architecture**: Clean separation of concerns for easy feature expansion
- 🔄 **Inheritance-Based Streaming**: Generic StreamManager with asset-specific extensions
- ✅ **Comprehensive Testing**: GitHub Actions workflows for CI/CD validation

## Quick Start

### Prerequisites

- Python 3.8+
- Charles Schwab Developer Account (for real data)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd schwab_streaming
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables** (Optional - for real API)
   ```bash
   # Create .env file
   SCHWAB_APP_KEY=your_app_key_here
   SCHWAB_APP_SECRET=your_app_secret_here
   FLASK_SECRET_KEY=your-secret-key-here
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open your browser** to `http://localhost:8000`

## Usage

### Authentication Options

- **Mock Mode**: No API keys required - generates realistic simulated data
- **Real API**: Requires Schwab developer credentials for live market data

### Adding Symbols

1. Enter a stock symbol (e.g., "AAPL", "MSFT") in the search box
2. Click "Add to Watchlist" 
3. Real-time quotes will appear automatically

### Data Sources

- **Real Mode**: Live data from Charles Schwab API
- **Mock Mode**: Simulated realistic market movements for testing

## Architecture

### Modular Design

The application follows a clean, modular architecture designed for maintainability and easy feature expansion:

### Streaming Architecture

The streaming system uses an **inheritance-based pattern** that separates generic streaming concerns from asset-specific logic:

- **StreamManager (Base Class)**: Handles common streaming operations (start/stop, subscriptions, raw message processing)
- **EquityStreamManager (Inherits StreamManager)**: Adds equity-specific validation, field mapping, and business logic
- **Future Asset Managers**: Can easily inherit from StreamManager (e.g., OptionsStreamManager, ForexStreamManager)

This design ensures code reusability while maintaining clean separation between generic infrastructure and business-specific logic.

#### Core Components

- **FeatureManager**: Centralized feature initialization and lifecycle management
- **StreamManager**: Generic streaming base class for any asset type (equities, options, etc.)
- **EquityStreamManager**: Equity-specific streaming that inherits from StreamManager
- **EquityStreamProcessor**: Handles equity field mapping and validation
- **SubscriptionManager**: Generic symbol subscription handling
- **MarketDataManager**: Market data business logic and database operations

#### Package Structure

```
schwab_streaming/
├── app.py                    # Main Flask application with feature orchestration
├── auth.py                   # Authentication with @require_auth decorator
├── features/                 # Business feature modules
│   ├── __init__.py
│   ├── feature_manager.py    # Centralized feature initialization and management
│   ├── market_data.py        # Market data business logic and database operations
│   └── market_data_routes.py # Market data API routes and WebSocket handlers
├── streaming/                # Generic streaming infrastructure
│   ├── __init__.py
│   ├── stream_manager.py     # Generic streaming manager (base class)
│   ├── equity_stream.py      # Equity-specific processing and field mapping
│   ├── equity_stream_manager.py # Equity streaming manager (inherits StreamManager)
│   └── subscription_manager.py # Generic symbol subscription handling
├── mock_data.py              # Mock data generation and testing framework
├── templates/                # HTML templates
├── static/                   # CSS/JS assets
├── data/                     # SQLite databases
└── requirements.txt          # Python dependencies
```

### Benefits of Modular Architecture

1. **Clear Separation of Concerns**: Each component has a single responsibility
2. **No Code Duplication**: `@require_auth` decorator eliminates repetitive auth checks
3. **Easy Feature Expansion**: Adding new streaming features requires minimal core changes
4. **Better Testing**: Can unit test streaming logic separately
5. **Maintainable**: Clean package structure with well-defined interfaces

### Adding New Streaming Features

With the modular architecture, adding new streaming features follows a clear inheritance pattern:

```python
# Example: Adding options streaming
from streaming.stream_manager import StreamManager
from streaming.equity_stream import EquityStreamProcessor  # Use as template

# 1. Create options-specific processor
class OptionsStreamProcessor:
    def __init__(self):
        self.is_mock_mode = False
    
    def validate_symbol(self, symbol: str) -> bool:
        # Options-specific validation (e.g., "AAPL240315C00150000")
        pass
    
    def process_message(self, message_data):
        # Options-specific field mapping
        pass

# 2. Create options stream manager (inherits from StreamManager)
class OptionsStreamManager(StreamManager):
    def __init__(self):
        super().__init__()
        self.options_processor = OptionsStreamProcessor()
        super().set_message_handler(self._process_options_message)
    
    def add_options_subscription(self, symbol: str) -> bool:
        if not self.options_processor.validate_symbol(symbol):
            return False
        return self.add_subscription(symbol)

# 3. Create options data manager
class OptionsDataManager:
    def __init__(self, data_dir):
        self.options_stream_manager = OptionsStreamManager()
        # Options-specific business logic here

# 4. Add to FeatureManager
def initialize_options_data(self, schwab_client, schwab_streamer, is_mock_mode):
    # Initialize options feature following same pattern as market data
    pass
```

### Database Schema

**equity_quotes** table:
- `symbol`: Stock symbol (e.g., AAPL)
- `timestamp`: Unix timestamp in milliseconds
- `last_price`: Current trading price
- `bid_price`: Highest bid price
- `ask_price`: Lowest ask price
- `volume`: Total trading volume
- `net_change`: Price change from previous close
- `net_change_percent`: Percentage change
- `high_price`: Daily high
- `low_price`: Daily low
- `data_source`: 'MOCK' or 'SCHWAB_API'

## Testing

Run the test suite:

```bash
python run_tests.py
```

Tests include:
- Mock data generation
- Database operations
- Field mapping validation
- Authentication flows
- Modular component integration

## Development

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SCHWAB_APP_KEY` | Your Schwab API key | None |
| `SCHWAB_APP_SECRET` | Your Schwab API secret | None |
| `FLASK_SECRET_KEY` | Flask session secret | 'your-secret-key-here' |
| `FLASK_DEBUG` | Enable debug mode | 'True' |
| `USE_MOCK_DATA` | Force mock mode | 'false' |
| `ENABLE_MARKET_DATA` | Enable market data feature | 'true' |

### Development Principles

1. **Feature Toggles**: All features can be enabled/disabled via configuration
2. **Dependency Injection**: External dependencies are injected rather than hardcoded
3. **Generic Interfaces**: Streaming components work with any data type
4. **Clean Authentication**: Single `@require_auth` decorator for all routes
5. **Centralized Management**: FeatureManager handles all feature lifecycle

### Mock Mode Features

- Realistic price movements with volatility
- Market hours simulation
- Bullish/bearish trend simulation
- Volume and spread calculations
- Event-based price changes (e.g., earnings, news)

## API Endpoints

### Market Data

- `GET /api/watchlist` - Get current watchlist
- `POST /api/watchlist` - Add symbol to watchlist
- `DELETE /api/watchlist` - Remove symbol from watchlist
- `GET /api/market-data` - Get current market data
- `GET /api/auth-status` - Get authentication status

### Testing (Mock Mode Only)

- `POST /api/test/market-event` - Trigger simulated market events

### Administration

- `GET /api/admin/data-info` - Database information and statistics
- `POST /api/admin/cleanup-mock` - Clean up mock database files

## Troubleshooting

### Common Issues

1. **"Failed to connect to Schwab API"**
   - Check your API credentials in `.env`
   - Ensure your Schwab developer account is active
   - Try using mock mode instead

2. **"No data appearing"**
   - Check the browser console for errors
   - Verify WebSocket connection is established
   - Ensure symbols are properly added to watchlist

3. **"Authentication required" errors**
   - Clear browser cookies and try logging in again
   - Check that session is properly maintained

### Logs

The application provides detailed logging:
- Authentication events
- Market data streaming status
- Database operations
- WebSocket connections
- Feature initialization

## Security Notes

- API credentials are stored in environment variables only
- Sessions use secure cookies with configurable timeout
- All API endpoints require authentication via `@require_auth` decorator
- Real and mock data are clearly separated

## Future Expansion

The modular architecture makes it easy to add new features:

- **Options Flow**: Real-time options data and analysis
- **Futures Data**: Commodity and index futures streaming
- **News Integration**: Market news and sentiment analysis
- **Technical Analysis**: Chart patterns and indicators
- **Portfolio Tracking**: Position management and P&L

Each new feature can reuse the existing `StreamManager` and `FeatureManager` infrastructure.

## License

This project is for educational and personal use. Please ensure compliance with Charles Schwab's API terms of service when using real market data.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes following the modular architecture principles
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

---

**Note**: This application is designed for educational purposes. Always verify market data accuracy before making trading decisions.