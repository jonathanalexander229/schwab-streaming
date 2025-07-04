#!/usr/bin/env python3
"""
Options Data Collection CLI Script

Standalone script to collect live options data from Schwab API during market hours
and store it for flow analysis.

Usage:
    python -m options_collection.scripts.collect_options
    python -m options_collection.scripts.collect_options --symbol SPY --strikes 30
    python -m options_collection.scripts.collect_options --status
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from options_collection.core.options_collector import OptionsCollector
from auth import get_schwab_client

def setup_logging(verbose: bool = False):
    """Set up logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('options_collection.log')
        ]
    )

def load_watchlist_symbols(watchlist_path: str = 'watchlist.json') -> list:
    """Load symbols from watchlist file"""
    import json
    try:
        with open(watchlist_path, 'r') as f:
            watchlist_data = json.load(f)
            return watchlist_data.get('symbols', [])
    except FileNotFoundError:
        logging.error(f"Watchlist file not found: {watchlist_path}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in watchlist file: {e}")
        return []

def calculate_time_until_market_open(collector):
    """Calculate seconds until market opens (with 1 minute buffer)"""
    import pytz
    
    now_et = datetime.now(collector.ET)
    
    # If it's weekend, wait until Monday
    if now_et.weekday() >= 5:  # Saturday = 5, Sunday = 6
        days_until_monday = 7 - now_et.weekday()
        next_market_day = now_et + timedelta(days=days_until_monday)
    else:
        next_market_day = now_et
    
    # Set to 9:29 AM ET (1 minute before market open)
    market_open_time = next_market_day.replace(
        hour=9, minute=29, second=0, microsecond=0
    )
    
    # If we're past market open time today, move to next business day
    if now_et >= market_open_time and now_et.weekday() < 5:
        if now_et.weekday() == 4:  # Friday
            market_open_time += timedelta(days=3)  # Move to Monday
        else:
            market_open_time += timedelta(days=1)  # Move to next day
    
    time_diff = market_open_time - now_et
    return int(time_diff.total_seconds())

def main():
    parser = argparse.ArgumentParser(
        description='Collect live options data from Schwab API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect all watchlist symbols once (only during market hours)
  python -m options_collection.scripts.collect_options
  
  # Collect specific symbol with more strikes
  python -m options_collection.scripts.collect_options --symbol SPY --strikes 30
  
  # Continuous collection every 30 seconds
  python -m options_collection.scripts.collect_options --continuous --interval 30
  
  # Force collection outside market hours (for testing)
  python -m options_collection.scripts.collect_options --force-collect
  
  # Check collection status
  python -m options_collection.scripts.collect_options --status
        """
    )
    
    parser.add_argument(
        '--symbol', '-s',
        type=str,
        help='Collect data for specific symbol instead of entire watchlist'
    )
    
    parser.add_argument(
        '--strikes', '-k',
        type=int,
        default=20,
        help='Number of strikes to collect per side (default: 20)'
    )
    
    parser.add_argument(
        '--continuous', '-c',
        action='store_true',
        help='Run continuously (Ctrl+C to stop)'
    )
    
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=30,
        help='Collection interval in seconds for continuous mode (default: 30)'
    )
    
    parser.add_argument(
        '--force-collect',
        action='store_true',
        help='Bypass market hours check and collect anyway (for testing)'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show collection status and exit'
    )
    
    parser.add_argument(
        '--db-path',
        type=str,
        default='data/options_data.db',
        help='Path to options database (default: data/options_data.db)'
    )
    
    parser.add_argument(
        '--watchlist-path',
        type=str,
        default='watchlist.json',
        help='Path to watchlist file (default: watchlist.json)'
    )
    
    parser.add_argument(
        '--rate-limit',
        type=float,
        default=0.6,
        help='Delay between API calls in seconds (default: 0.6)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Get Schwab client
        logger.info("🔐 Connecting to Schwab API...")
        schwab_client = get_schwab_client()
        if not schwab_client:
            logger.error("❌ Failed to connect to Schwab API")
            return 1
        logger.info("✅ Connected to Schwab API")
        
        # Initialize collector
        collector = OptionsCollector(schwab_client, args.db_path, args.rate_limit)
        
        # Handle status check
        if args.status:
            logger.info("📊 Checking options collection status...")
            symbols = collector.database.get_all_symbols()
            
            print(f"\n📊 Options Collection Status:")
            print(f"Database: {args.db_path}")
            print(f"Total symbols with data: {len(symbols)}")
            print(f"Is trading time: {collector.is_trading_time()}")
            
            if symbols:
                print(f"\n📋 Symbol Statistics:")
                for symbol in symbols:
                    stats = collector.database.get_symbol_stats(symbol)
                    print(f"  {symbol}: {stats['total_records']:,} records "
                          f"({stats.get('earliest_date', 'N/A')} to {stats.get('latest_date', 'N/A')})")
            
            return 0
        
        # Determine symbols to collect first
        if args.symbol:
            symbols = [args.symbol.upper()]
        else:
            symbols = load_watchlist_symbols(args.watchlist_path)
            if not symbols:
                logger.error("❌ No symbols found in watchlist")
                return 1
        
        # Check market hours for any symbol (unless forced)
        if not args.force_collect:
            any_trading = any(collector.is_trading_time(s) for s in symbols)
            if not any_trading:
                if args.continuous:
                    # Calculate wait time until market opens
                    wait_seconds = calculate_time_until_market_open(collector)
                    wait_hours = wait_seconds // 3600
                    wait_minutes = (wait_seconds % 3600) // 60
                    
                    logger.info(f"📅 Market is closed. Waiting {wait_hours}h {wait_minutes}m until market opens...")
                    logger.info("⚠️  Use --force-collect to bypass market hours check")
                    
                    try:
                        time.sleep(wait_seconds)
                        logger.info("⏰ Market opening soon! Starting collection...")
                    except KeyboardInterrupt:
                        logger.info("⏹️ Wait interrupted by user")
                        return 0
                else:
                    logger.info("📅 Market is closed. No collection will be performed.")
                    logger.info("⚠️  Use --force-collect to collect anyway (data may be stale)")
                    return 0
        
        if args.force_collect:
            any_trading = any(collector.is_trading_time(s) for s in symbols)
            if not any_trading:
                logger.warning("⚠️ Collecting outside market hours - data may be stale!")
        
        logger.info(f"🎯 Target symbols: {symbols}")
        logger.info(f"📈 Strike count: {args.strikes}")
        
        # Single collection
        if not args.continuous:
            logger.info("🚀 Starting single collection...")
            
            if len(symbols) == 1:
                result = collector.collect_options_chain(symbols[0], args.strikes)
                print(f"\n✅ Collection Result for {symbols[0]}:")
                print(f"Status: {result['status']}")
                print(f"Records inserted: {result.get('records_inserted', 0)}")
                if result.get('duplicates', 0) > 0:
                    print(f"Duplicates skipped: {result['duplicates']}")
            else:
                result = collector.collect_multiple_symbols(symbols, args.strikes)
                print(f"\n✅ Collection Summary:")
                print(f"Symbols processed: {result['total_symbols']}")
                print(f"Total records inserted: {result['total_records_inserted']}")
            
            return 0
        
        # Continuous collection
        else:
            logger.info(f"🔄 Starting continuous collection (every {args.interval}s)")
            logger.info("Press Ctrl+C to stop...")
            
            collection_count = 0
            
            try:
                while True:
                    # Check market hours on each iteration (unless forced)
                    if not args.force_collect:
                        any_trading = any(collector.is_trading_time(s) for s in symbols)
                        if not any_trading:
                            logger.info("📅 Market closed during continuous collection")
                            
                            # Wait until market opens
                            wait_seconds = calculate_time_until_market_open(collector)
                            wait_hours = wait_seconds // 3600
                            wait_minutes = (wait_seconds % 3600) // 60
                            
                            logger.info(f"⏳ Waiting {wait_hours}h {wait_minutes}m until market opens...")
                            
                            try:
                                time.sleep(wait_seconds)
                                logger.info("⏰ Market opening! Resuming collection...")
                                continue
                            except KeyboardInterrupt:
                                logger.info("⏹️ Wait interrupted by user")
                                return 0
                    
                    collection_count += 1
                    logger.info(f"📊 Collection #{collection_count}")
                    
                    if len(symbols) == 1:
                        result = collector.collect_options_chain(symbols[0], args.strikes)
                        logger.info(f"✅ {symbols[0]}: {result.get('records_inserted', 0)} records")
                    else:
                        result = collector.collect_multiple_symbols(symbols, args.strikes)
                        logger.info(f"✅ Total: {result['total_records_inserted']} records")
                    
                    logger.info(f"⏳ Waiting {args.interval}s until next collection...")
                    time.sleep(args.interval)
                    
            except KeyboardInterrupt:
                logger.info(f"\n⏹️ Stopped by user after {collection_count} collections")
                return 0
        
    except KeyboardInterrupt:
        logger.info("⏹️ Collection interrupted by user")
        return 1
    
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        if args.verbose:
            raise
        return 1

if __name__ == '__main__':
    exit(main())