# Historical Data Collection Module

A standalone, modular system for collecting and managing historical OHLC (Open, High, Low, Close) data from the Schwab API. This module provides comprehensive 1-minute candle data collection with built-in data validation, gap detection, and quality assurance.

## Features

- **📊 Comprehensive Data Collection**: Collect up to 5 years of 1-minute OHLC data
- **⚡ Rate-Limited API Access**: Respects Schwab's 120 requests/minute limit
- **🔍 Data Quality Validation**: Comprehensive OHLC relationship validation
- **📈 Market Hours Filtering**: Optional filtering to trading hours only
- **🔧 Gap Detection & Backfill**: Automatic detection and filling of data gaps
- **💾 Progress Tracking**: Resume capability for interrupted collections
- **🎯 Watchlist Integration**: Automatically uses existing watchlist.json
- **📋 CLI Interface**: Easy-to-use command-line tools

## Architecture

```
historical_collection/
├── core/
│   ├── historical_data_manager.py    # Main orchestration
│   ├── ohlc_database.py             # SQLite database operations
│   └── rate_limited_collector.py    # Schwab API client
├── utils/
│   └── data_validator.py            # Data quality validation
├── scripts/
│   ├── collect_historical.py        # Main collection CLI
│   └── backfill_gaps.py             # Gap detection/filling
└── README.md                        # This file
```

## Quick Start

### 1. Test API Connection

```bash
python -m historical_collection.scripts.collect_historical --test-connection
```

### 2. Check Collection Status

```bash
python -m historical_collection.scripts.collect_historical --status
```

### 3. Collect All Watchlist Data

```bash
# Collect 5 years of data for all watchlist symbols
python -m historical_collection.scripts.collect_historical

# Collect 2 years of data
python -m historical_collection.scripts.collect_historical --years 2
```

### 4. Collect Specific Symbol

```bash
# Collect data for AAPL only
python -m historical_collection.scripts.collect_historical --symbol AAPL --years 3
```

## CLI Reference

### Main Collection Script

```bash
python -m historical_collection.scripts.collect_historical [OPTIONS]
```

**Options:**
- `--symbol SYMBOL` - Collect specific symbol instead of entire watchlist
- `--years N` - Number of years to collect (default: 5)
- `--test-connection` - Test API connection and exit
- `--status` - Show collection status and exit
- `--include-extended-hours` - Include extended hours data
- `--no-validation` - Skip data quality validation (faster)
- `--db-path PATH` - Custom database path
- `--watchlist-path PATH` - Custom watchlist file path
- `--rate-limit SECONDS` - API call delay (default: 0.6)
- `--verbose` - Enable detailed logging

### Gap Detection & Backfill

```bash
python -m historical_collection.scripts.backfill_gaps [OPTIONS]
```

**Options:**
- `--symbol SYMBOL` - Process specific symbol
- `--detect-only` - Only detect gaps, don't backfill
- `--max-gaps N` - Maximum gaps to backfill per symbol
- `--min-gap-minutes N` - Minimum gap size to consider (default: 5)

## Usage Examples

### Basic Collection

```bash
# Collect all watchlist symbols (default 5 years)
python -m historical_collection.scripts.collect_historical

# Include extended hours trading data
python -m historical_collection.scripts.collect_historical --include-extended-hours

# Fast collection without validation
python -m historical_collection.scripts.collect_historical --no-validation
```

### Targeted Collection

```bash
# Collect specific symbol for 2 years
python -m historical_collection.scripts.collect_historical --symbol TSLA --years 2

# Multiple symbols (run separately)
python -m historical_collection.scripts.collect_historical --symbol AAPL
python -m historical_collection.scripts.collect_historical --symbol GOOGL
```

### Monitoring & Maintenance

```bash
# Check collection status
python -m historical_collection.scripts.collect_historical --status

# Detect data gaps
python -m historical_collection.scripts.backfill_gaps --detect-only

# Backfill gaps for specific symbol
python -m historical_collection.scripts.backfill_gaps --symbol AAPL

# Backfill all gaps (limited to 10 per symbol)
python -m historical_collection.scripts.backfill_gaps --max-gaps 10
```

## Database Schema

The system creates a separate `data/historical_data.db` SQLite database with the following tables:

### ohlc_data
- `symbol` - Stock symbol
- `timestamp` - Unix timestamp
- `open_price` - Opening price
- `high_price` - High price
- `low_price` - Low price
- `close_price` - Closing price
- `volume` - Trading volume
- `timeframe` - Data timeframe (default: '1m')

### collection_progress
- `symbol` - Stock symbol
- `start_date` - Collection start timestamp
- `end_date` - Collection end timestamp
- `last_collected` - Last successful timestamp
- `status` - Collection status (pending/in_progress/completed/failed)

## Data Quality Features

### Validation Checks
- **OHLC Relationships**: High ≥ max(Open, Close), Low ≤ min(Open, Close)
- **Price Positivity**: All prices must be positive
- **Realistic Changes**: Flags unrealistic price movements (>50% in 1 minute)
- **Volume Validation**: Volume must be non-negative
- **Timestamp Validation**: Proper Unix timestamp format

### Data Cleaning
- **Duplicate Removal**: Automatic removal of duplicate timestamps
- **Market Hours Filtering**: Optional filtering to 9:30 AM - 4:00 PM ET
- **Gap Detection**: Identifies missing time periods
- **Quality Scoring**: 0-100 quality score for each symbol

## Performance Characteristics

- **Storage**: ~1.8MB for complete 5-year, 6-symbol dataset
- **Collection Time**: ~30-50 API calls per symbol (rate limited)
- **Memory Usage**: Minimal - streaming writes to database
- **API Rate Limit**: 120 requests/minute (0.6s delay between calls)

## Integration

The module is designed to integrate seamlessly with the existing Schwab streaming system:

- **Authentication**: Uses existing `auth.py` Schwab client
- **Configuration**: Reads from existing `watchlist.json`
- **Storage**: Separate database in existing `data/` directory
- **Logging**: Follows existing logging patterns

## Programmatic Usage

```python
from historical_collection.core.historical_data_manager import HistoricalDataManager

# Initialize manager
manager = HistoricalDataManager()

# Test connection
if manager.test_connection():
    print("✅ Connection successful")

# Check status
status = manager.get_collection_status()
print(f"Completed: {status['completed']}/{status['total_symbols']}")

# Collect data for specific symbol
result = manager.collect_historical_data("AAPL", years=3)
print(f"Collected {result['inserted_candles']} candles")

# Collect all watchlist data
results = manager.collect_all_watchlist_data(years=5)
print(f"Total candles: {results['total_candles_collected']:,}")
```

## Error Handling

The system includes comprehensive error handling:

- **API Failures**: Exponential backoff and retry logic
- **Rate Limiting**: Automatic enforcement of API limits
- **Data Validation**: Graceful handling of invalid data
- **Resume Capability**: Interrupted collections can be resumed
- **Progress Tracking**: Detailed logging and status tracking

## Troubleshooting

### Common Issues

**Connection Test Fails**
```bash
# Check API credentials
python -m historical_collection.scripts.collect_historical --test-connection
```

**No Data Returned**
- Verify symbol exists and is valid
- Check date ranges (weekends/holidays have no data)
- Ensure API credentials are properly configured

**Rate Limit Errors**
- Increase `--rate-limit` value (default: 0.6 seconds)
- Check for other concurrent API usage

**Database Errors**
- Ensure `data/` directory exists and is writable
- Check available disk space
- Verify database isn't locked by another process

### Logs

Collection logs are saved to:
- `historical_collection.log` - Main collection log
- `backfill_gaps.log` - Gap detection/backfill log

Use `--verbose` flag for detailed debugging information.

## Configuration

The system uses the following default paths:
- Database: `data/historical_data.db`
- Watchlist: `watchlist.json`
- Logs: `historical_collection.log`

All paths can be customized via command-line options.

## Future Enhancements

Potential future features:
- **Higher Timeframes**: Automatic aggregation to 5m, 15m, 1h, 1d
- **Real-time Updates**: Continuous data collection
- **Data Export**: CSV/JSON export capabilities
- **Advanced Analytics**: Built-in technical indicators
- **Web Interface**: Browser-based collection monitoring