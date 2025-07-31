# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

For comprehensive project information, architecture details, and usage instructions, see **README.md**. This file focuses on development-specific guidance and recent improvements.

## Common Development Commands

### Running the Application
```bash
python app.py
```

### Running Tests
```bash
python run_tests.py
```

### Historical Data Collection
```bash
# Collect all watchlist symbols (5 years, all frequencies)
python -m historical_collection.scripts.collect_historical --all-frequencies

# Collect specific symbol with extended hours
python -m historical_collection.scripts.collect_historical --symbol AAPL --years 3 --include-extended-hours

# Check collection status
python -m historical_collection.scripts.collect_historical --status
```

### Options Data Collection
```bash
# Collect options data for all watchlist symbols
python -m options_collection.scripts.collect_options

# Force collection outside market hours
python -m options_collection.scripts.collect_options --force

# Check collection status
python -m options_collection.scripts.collect_options --status
```

## Architecture Overview

### Core Design Principles
- **Modular Architecture**: Clean separation of concerns with Blueprint-based feature modules
- **Inheritance-Based Streaming**: Generic `StreamManager` base class with asset-specific extensions
- **Dependency Injection**: Features receive dependencies through `FeatureManager` 
- **Environment-Driven Configuration**: All features controlled via environment variables
- **Mock/Real Mode Isolation**: Separate data sources and databases for testing vs production

### Key Components

#### Application Orchestration
- **`app.py`**: Main Flask application with centralized feature initialization
- **`features/feature_manager.py`**: Centralized feature lifecycle management
- **`auth.py`**: Authentication with `@require_auth` decorator

#### Streaming Infrastructure
- **`streaming/stream_manager.py`**: Generic streaming base class (handles start/stop, subscriptions)
- **`streaming/equity_stream_manager.py`**: Equity-specific streaming (inherits from StreamManager)
- **`streaming/equity_stream.py`**: Equity field mapping and validation
- **`streaming/subscription_manager.py`**: Generic symbol subscription handling

#### Business Features
- **`features/market_data.py`**: Market data business logic and database operations
- **`features/market_data_routes.py`**: Market data API routes and WebSocket handlers
- **`historical_collection/`**: Historical OHLC data collection system
- **`options_collection/`**: Real-time options flow analysis system

#### Data Storage
- **SQLite databases** in `data/` directory with `MOCK_` prefix for simulated data
- **Automatic data separation** between real and mock modes
- **Time-series optimized** schemas for streaming and historical data

### Adding New Streaming Features

When adding new asset types (e.g., futures, forex), follow this inheritance pattern:

1. **Create Asset-Specific Processor**: Handle field mapping and validation
2. **Extend StreamManager**: Create `[Asset]StreamManager` that inherits from `StreamManager`
3. **Add to FeatureManager**: Initialize the new feature following the market data pattern
4. **Register Routes**: Add Blueprint for API endpoints

Example structure:
```python
# Create futures processor
class FuturesStreamProcessor:
    def validate_symbol(self, symbol: str) -> bool:
        # Futures-specific validation
        pass
    
    def process_message(self, message_data):
        # Futures-specific field mapping
        pass

# Extend StreamManager
class FuturesStreamManager(StreamManager):
    def __init__(self):
        super().__init__()
        self.futures_processor = FuturesStreamProcessor()
        super().set_message_handler(self._process_futures_message)
```

### Database Schema

#### Live Market Data (`equity_quotes` table)
- `symbol`, `timestamp`, `last_price`, `bid_price`, `ask_price`, `volume`
- `net_change`, `net_change_percent`, `high_price`, `low_price`
- `data_source`: 'MOCK' or 'SCHWAB_API'

#### Historical Data (`ohlc_data` table)  
- `symbol`, `timestamp`, `open_price`, `high_price`, `low_price`, `close_price`
- `volume`, `frequency`: ('1m', '5m', '1d', etc.)

#### Options Flow (`options_data` table)
- `symbol`, `timestamp`, `option_type`, `strike_price`, `expiration_date`
- `bid_price`, `ask_price`, `mark_price`, `total_volume`, `open_interest`
- `delta`, `gamma`, `theta`, `vega`, `rho`, `underlying_price`

### Environment Variables

Required for real API access:
- `SCHWAB_APP_KEY`: Schwab API key
- `SCHWAB_APP_SECRET`: Schwab API secret
- `FLASK_SECRET_KEY`: Flask session secret

Feature toggles:
- `ENABLE_MARKET_DATA`: Enable market data feature (default: true)
- `USE_MOCK_DATA`: Force mock mode (default: false)

### Mock Mode vs Real Mode

The application automatically falls back to mock mode if Schwab API credentials are missing or invalid. Mock mode provides:
- Realistic price movements with volatility simulation
- Market hours simulation  
- Bullish/bearish trend simulation
- Event-based price changes
- Adjustable update speed via `/api/mock-speed`

### Authentication Flow

1. User visits `/login` 
2. Clicks authenticate button (with optional `?mock=true`)
3. App checks for mock mode flag or valid Schwab credentials
4. Features are initialized based on authentication result
5. All subsequent routes protected by `@require_auth` decorator

### WebSocket Events

Real-time updates are pushed via Socket.IO:
- Market data updates automatically streamed to connected clients
- Options flow calculations broadcast every 30 seconds
- Connection management with automatic streaming start/stop

### API Endpoints

#### Market Data
- `GET /api/watchlist`, `POST /api/watchlist`, `DELETE /api/watchlist`
- `GET /api/market-data`, `GET /api/auth-status`, `GET /api/session-info`

#### Streaming Control (NEW)
- `POST /api/streaming/start` - Start market data streaming
- `POST /api/streaming/stop` - Stop market data streaming
- `GET /api/streaming/status` - Get current streaming status

#### Historical Data  
- `GET /api/historical-data/<symbol>?timeframe=1m&range=1d`
- `GET /api/test-data` (database stats)

#### Options Flow
- `GET /api/options/symbols` - Fast symbol list (no stats) - **PERFORMANCE OPTIMIZED**
- `GET /api/options/status` - Full status with stats (admin/debug only)
- `GET /api/options/chart-agg/<symbol>` - Chart data with fallback logic
- `GET /api/options/flow` (all symbols)
- `GET /api/options/flow/<symbol>` (specific symbol)  
- `GET /api/options/flow/<symbol>/history?hours=24`

## Recent Improvements & Best Practices

### Performance Optimizations (Latest)
- **Options Flow Loading**: Created `/api/options/symbols` for fast dropdown loading (no expensive stats)
- **Chart Data Fallback**: Smart date fallback logic (24h → 48h → longer ranges)
- **SPY Default**: Auto-loads SPY data immediately while symbols load
- **Page Visibility**: Auto-pause updates when page is hidden

### Streaming Control Features (Latest)
- **Manual Control**: Start/Stop streaming buttons with REST API endpoints
- **Resource Management**: Stop streaming to save bandwidth and API calls  
- **Status Tracking**: Real-time streaming status with UI indicators
- **Default Enabled**: Streaming starts automatically but can be controlled

### Performance Guidelines
- **Use `/api/options/symbols` for UI dropdowns** (fast, no stats)
- **Use `/api/options/status` only for debugging** (slow, full stats)
- **Always implement date fallback logic** for chart data
- **Consider page visibility for auto-updates**

### Database Concurrency (SQLite)

**Issue Resolved**: SQLite concurrency problems between options collection script and Flask app have been addressed with robust connection management in `OptionsDatabase` class.

**Current Implementation**:
- WAL mode with optimized PRAGMA settings for better concurrency
- Retry logic with exponential backoff for lock conflicts  
- Separate read-only and write connections with proper transaction scoping
- Centralized `_execute_read()` and `_execute_write()` methods for all database operations

### Important Implementation Notes

- **Always use dependency injection** when adding new features to `FeatureManager`
- **Follow the StreamManager inheritance pattern** for new asset types
- **Separate mock and real data** using prefixes and environment controls
- **Use Blueprint registration** for modular route management
- **Implement proper error handling** with fallback to mock mode
- **Add comprehensive logging** for debugging and monitoring
- **Test both mock and real modes** when making changes

### Testing Strategy

The application includes comprehensive testing via `run_tests.py`:
- Mock data generation validation
- Database operations testing  
- Field mapping verification
- Authentication flow testing
- Modular component integration testing