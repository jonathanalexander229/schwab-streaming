#!/usr/bin/env python3
"""
Historical Data Collection CLI Script

Standalone script to collect 5 years of 1-minute OHLC data from Schwab API
for watchlist symbols using the modular historical collection system.

Usage:
    python -m historical_collection.scripts.collect_historical
    python -m historical_collection.scripts.collect_historical --symbol AAPL --years 2
    python -m historical_collection.scripts.collect_historical --test-connection
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from historical_collection.core.historical_data_manager import HistoricalDataManager

def setup_logging(verbose: bool = False):
    """Set up logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('historical_collection.log')
        ]
    )

def main():
    parser = argparse.ArgumentParser(
        description='Collect historical OHLC data from Schwab API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect all watchlist symbols for 5 years
  python -m historical_collection.scripts.collect_historical
  
  # Collect specific symbol for 2 years
  python -m historical_collection.scripts.collect_historical --symbol AAPL --years 2
  
  # Test API connection
  python -m historical_collection.scripts.collect_historical --test-connection
  
  # Include extended hours data
  python -m historical_collection.scripts.collect_historical --include-extended-hours
  
  # Skip data validation (faster but less reliable)
  python -m historical_collection.scripts.collect_historical --no-validation
        """
    )
    
    parser.add_argument(
        '--symbol', '-s',
        type=str,
        help='Collect data for specific symbol instead of entire watchlist'
    )
    
    parser.add_argument(
        '--years', '-y',
        type=int,
        default=5,
        help='Number of years of historical data to collect (default: 5)'
    )
    
    parser.add_argument(
        '--test-connection', '-t',
        action='store_true',
        help='Test Schwab API connection and exit'
    )
    
    parser.add_argument(
        '--include-extended-hours',
        action='store_true',
        help='Include extended hours trading data (default: market hours only)'
    )
    
    parser.add_argument(
        '--no-validation',
        action='store_true',
        help='Skip data quality validation (faster collection)'
    )
    
    parser.add_argument(
        '--db-path',
        type=str,
        default='data/historical_data.db',
        help='Path to historical data database (default: data/historical_data.db)'
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
        '--status',
        action='store_true',
        help='Show collection status for all symbols and exit'
    )
    
    parser.add_argument(
        '--frequency-type',
        type=str,
        choices=['minute', 'daily'],
        default='minute',
        help='Frequency type (default: minute)'
    )
    
    parser.add_argument(
        '--frequency',
        type=int,
        default=1,
        help='Frequency value - 1,5,15,30 for minute; 1 for daily (default: 1)'
    )
    
    parser.add_argument(
        '--all-frequencies',
        action='store_true',
        help='Collect all supported frequencies: 1m, 5m, daily'
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
        # Initialize the historical data manager
        logger.info("🚀 Initializing Historical Data Manager...")
        manager = HistoricalDataManager(
            db_path=args.db_path,
            watchlist_path=args.watchlist_path,
            rate_limit_delay=args.rate_limit
        )
        
        # Handle test connection
        if args.test_connection:
            logger.info("🔍 Testing Schwab API connection...")
            if manager.test_connection():
                print("✅ Connection test successful!")
                return 0
            else:
                print("❌ Connection test failed!")
                return 1
        
        # Handle status check
        if args.status:
            logger.info("📊 Checking collection status...")
            status = manager.get_collection_status()
            
            print(f"\n📊 Collection Status Summary:")
            print(f"Total symbols: {status['total_symbols']}")
            print(f"Completed: {status['completed']}")
            print(f"In progress: {status['in_progress']}")
            print(f"Failed: {status['failed']}")
            print(f"Pending: {status['pending']}")
            
            print(f"\n📋 Individual Symbol Status:")
            for symbol_info in status['symbols']:
                status_emoji = {
                    'completed': '✅',
                    'in_progress': '⏳',
                    'failed': '❌',
                    'pending': '⏸️'
                }.get(symbol_info['status'], '❓')
                
                print(f"{status_emoji} {symbol_info['symbol']}: {symbol_info['status']} "
                      f"({symbol_info['candles_collected']:,} candles)")
            
            return 0
        
        # Determine collection parameters
        market_hours_only = not args.include_extended_hours
        validate_data = not args.no_validation
        
        # Execute collection
        if args.all_frequencies:
            # Collect all supported frequencies
            frequencies_to_collect = [
                ('minute', 1),   # 1-minute
                ('minute', 5),   # 5-minute  
                ('daily', 1)     # Daily
            ]
            
            if args.symbol:
                # Single symbol, all frequencies
                logger.info(f"🎯 Collecting all frequencies for {args.symbol}")
                for freq_type, freq_val in frequencies_to_collect:
                    logger.info(f"📊 Collecting {freq_val}{freq_type[0]} data...")
                    result = manager.collect_historical_data(
                        symbol=args.symbol,
                        years=args.years,
                        market_hours_only=market_hours_only,
                        validate_data=validate_data,
                        frequency_type=freq_type,
                        frequency=freq_val
                    )
                    print(f"✅ {freq_val}{freq_type[0]}: {result.get('inserted_candles', 0):,} candles")
                return 0
            else:
                # All symbols, all frequencies
                logger.info("🎯 Collecting all frequencies for all watchlist symbols")
                for freq_type, freq_val in frequencies_to_collect:
                    logger.info(f"📊 Collecting {freq_val}{freq_type[0]} data for all symbols...")
                    results = manager.collect_all_watchlist_data(
                        years=args.years,
                        market_hours_only=market_hours_only,
                        validate_data=validate_data,
                        frequency_type=freq_type,
                        frequency=freq_val
                    )
                    print(f"✅ {freq_val}{freq_type[0]}: {results['total_candles_collected']:,} total candles")
                return 0
        
        elif args.symbol:
            # Collect single symbol, single frequency
            logger.info(f"🎯 Collecting {args.frequency}{args.frequency_type[0]} data for {args.symbol}")
            result = manager.collect_historical_data(
                symbol=args.symbol,
                years=args.years,
                market_hours_only=market_hours_only,
                validate_data=validate_data,
                frequency_type=args.frequency_type,
                frequency=args.frequency
            )
            
            # Display results
            if result['status'] == 'success':
                print(f"\n✅ Successfully collected data for {args.symbol}")
                print(f"📊 Raw candles: {result['raw_candles']:,}")
                print(f"📊 Processed candles: {result['processed_candles']:,}")
                print(f"📊 Inserted candles: {result['inserted_candles']:,}")
                
                if result.get('quality_report'):
                    quality = result['quality_report']
                    print(f"📈 Data quality score: {quality['quality_score']:.1f}/100")
                    
                    if quality['issues']:
                        print("⚠️  Quality issues:")
                        for issue in quality['issues']:
                            print(f"   • {issue}")
                
                return 0
            else:
                print(f"❌ Failed to collect data for {args.symbol}: {result.get('message', 'Unknown error')}")
                return 1
        
        else:
            # Collect all watchlist symbols, single frequency
            logger.info(f"🎯 Collecting {args.frequency}{args.frequency_type[0]} data for all watchlist symbols")
            results = manager.collect_all_watchlist_data(
                years=args.years,
                market_hours_only=market_hours_only,
                validate_data=validate_data,
                frequency_type=args.frequency_type,
                frequency=args.frequency
            )
            
            # Display summary
            print(f"\n🎉 Collection Complete!")
            print(f"📊 Total symbols: {results['total_symbols']}")
            print(f"✅ Successful: {results['successful_collections']}")
            print(f"❌ Failed: {results['failed_collections']}")
            print(f"ℹ️  Already existing: {results['already_existing']}")
            print(f"📈 Total candles collected: {results['total_candles_collected']:,}")
            
            # Show individual results
            if args.verbose:
                print(f"\n📋 Individual Results:")
                for result in results['individual_results']:
                    status_emoji = {
                        'success': '✅',
                        'already_exists': 'ℹ️',
                        'failed': '❌',
                        'error': '💥'
                    }.get(result['status'], '❓')
                    
                    candles = result.get('inserted_candles', 0)
                    print(f"{status_emoji} {result['symbol']}: {result['status']} ({candles:,} candles)")
            
            # Return appropriate exit code
            if results['failed_collections'] > 0:
                return 1  # Some failures occurred
            else:
                return 0  # All successful
    
    except KeyboardInterrupt:
        logger.info("⏹️  Collection interrupted by user")
        print("\n⏹️  Collection interrupted by user")
        return 1
    
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        print(f"💥 Unexpected error: {e}")
        if args.verbose:
            raise
        return 1

if __name__ == '__main__':
    exit(main())