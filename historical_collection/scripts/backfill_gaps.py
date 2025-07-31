#!/usr/bin/env python3
"""
Gap Detection and Backfill Utility

Identifies gaps in historical data collection and backfills missing periods
using the modular historical collection system.

Usage:
    python -m historical_collection.scripts.backfill_gaps
    python -m historical_collection.scripts.backfill_gaps --symbol AAPL
    python -m historical_collection.scripts.backfill_gaps --detect-only
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Dict, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from historical_collection.core.historical_data_manager import HistoricalDataManager
from historical_collection.core.ohlc_database import OHLCDatabase
from historical_collection.core.rate_limited_collector import RateLimitedCollector
from historical_collection.utils.data_validator import DataValidator

def setup_logging(verbose: bool = False):
    """Set up logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('backfill_gaps.log')
        ]
    )

class GapBackfiller:
    def __init__(self, db_path: str = "data/historical_data.db", 
                 rate_limit_delay: float = 0.6):
        self.database = OHLCDatabase(db_path)
        self.collector = RateLimitedCollector(rate_limit_delay)
        self.validator = DataValidator()
        self.logger = logging.getLogger(__name__)
    
    def detect_gaps(self, symbol: str, timeframe: str = '1m', 
                   min_gap_minutes: int = 5) -> List[Dict[str, Any]]:
        """
        Detect gaps in data for a specific symbol
        
        Args:
            symbol: Stock symbol to check
            timeframe: Timeframe to analyze (default: '1m')
            min_gap_minutes: Minimum gap size to report (default: 5 minutes)
        
        Returns:
            List of gap information dictionaries
        """
        self.logger.info(f"🔍 Detecting gaps for {symbol}")
        
        # Get raw gaps from database
        raw_gaps = self.database.get_data_gaps(symbol, timeframe)
        
        if not raw_gaps:
            self.logger.info(f"✅ No gaps detected for {symbol}")
            return []
        
        # Filter and format gaps
        significant_gaps = []
        min_gap_seconds = min_gap_minutes * 60
        
        for start_ts, end_ts in raw_gaps:
            gap_duration = end_ts - start_ts
            
            if gap_duration >= min_gap_seconds:
                start_dt = datetime.fromtimestamp(start_ts)
                end_dt = datetime.fromtimestamp(end_ts)
                
                # Check if gap spans market hours
                market_hours_affected = self._gap_affects_market_hours(start_dt, end_dt)
                
                gap_info = {
                    'start_timestamp': start_ts,
                    'end_timestamp': end_ts,
                    'start_datetime': start_dt,
                    'end_datetime': end_dt,
                    'duration_minutes': gap_duration // 60,
                    'market_hours_affected': market_hours_affected
                }
                
                significant_gaps.append(gap_info)
        
        self.logger.info(f"🔧 Found {len(significant_gaps)} significant gaps for {symbol}")
        return significant_gaps
    
    def _gap_affects_market_hours(self, start_dt: datetime, end_dt: datetime) -> bool:
        """Check if a gap affects market trading hours"""
        # Simple check - gap spans weekdays between 9:30 AM and 4:00 PM ET
        current_dt = start_dt
        while current_dt <= end_dt:
            if current_dt.weekday() < 5:  # Monday to Friday
                market_start = current_dt.replace(hour=9, minute=30, second=0)
                market_end = current_dt.replace(hour=16, minute=0, second=0)
                
                if (current_dt <= market_end and 
                    end_dt >= market_start):
                    return True
            
            current_dt += timedelta(days=1)
        
        return False
    
    def backfill_gap(self, symbol: str, start_timestamp: int, end_timestamp: int) -> Dict[str, Any]:
        """
        Backfill a specific gap with historical data
        
        Args:
            symbol: Stock symbol
            start_timestamp: Gap start timestamp
            end_timestamp: Gap end timestamp
        
        Returns:
            Dictionary with backfill results
        """
        start_dt = datetime.fromtimestamp(start_timestamp)
        end_dt = datetime.fromtimestamp(end_timestamp)
        
        self.logger.info(f"🔧 Backfilling gap for {symbol} from {start_dt} to {end_dt}")
        
        try:
            # Fetch data for the gap period
            gap_data = self.collector.get_historical_data(
                symbol=symbol,
                start_date=start_dt,
                end_date=end_dt
            )
            
            if not gap_data:
                return {
                    'symbol': symbol,
                    'status': 'no_data',
                    'message': 'No data available for gap period'
                }
            
            # Validate and clean data
            cleaned_data = self.validator.remove_duplicates(gap_data)
            quality_report = self.validator.get_data_quality_report(cleaned_data, symbol)
            
            # Insert into database
            inserted_count = self.database.insert_ohlc_data(symbol, cleaned_data)
            
            self.logger.info(f"✅ Backfilled {inserted_count} candles for {symbol} gap")
            
            return {
                'symbol': symbol,
                'status': 'success',
                'gap_start': start_dt.isoformat(),
                'gap_end': end_dt.isoformat(),
                'raw_candles': len(gap_data),
                'inserted_candles': inserted_count,
                'quality_score': quality_report['quality_score']
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error backfilling gap for {symbol}: {e}")
            return {
                'symbol': symbol,
                'status': 'error',
                'message': str(e)
            }
    
    def backfill_symbol_gaps(self, symbol: str, max_gaps: int = None) -> Dict[str, Any]:
        """
        Backfill all gaps for a specific symbol
        
        Args:
            symbol: Stock symbol
            max_gaps: Maximum number of gaps to backfill (None for all)
        
        Returns:
            Dictionary with overall backfill results
        """
        gaps = self.detect_gaps(symbol)
        
        if not gaps:
            return {
                'symbol': symbol,
                'status': 'no_gaps',
                'message': 'No gaps detected'
            }
        
        # Limit gaps if requested
        if max_gaps and len(gaps) > max_gaps:
            gaps = gaps[:max_gaps]
            self.logger.info(f"ℹ️  Limiting to first {max_gaps} gaps")
        
        results = []
        successful_backfills = 0
        
        for i, gap in enumerate(gaps, 1):
            self.logger.info(f"🔧 Processing gap {i}/{len(gaps)} for {symbol}")
            
            result = self.backfill_gap(
                symbol, 
                gap['start_timestamp'], 
                gap['end_timestamp']
            )
            
            results.append(result)
            
            if result['status'] == 'success':
                successful_backfills += 1
        
        return {
            'symbol': symbol,
            'status': 'completed',
            'total_gaps': len(gaps),
            'successful_backfills': successful_backfills,
            'failed_backfills': len(gaps) - successful_backfills,
            'gap_results': results
        }

def main():
    parser = argparse.ArgumentParser(
        description='Detect and backfill gaps in historical data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Detect and backfill gaps for all symbols
  python -m historical_collection.scripts.backfill_gaps
  
  # Detect gaps for specific symbol (no backfill)
  python -m historical_collection.scripts.backfill_gaps --symbol AAPL --detect-only
  
  # Backfill gaps for specific symbol
  python -m historical_collection.scripts.backfill_gaps --symbol AAPL
  
  # Limit backfill to first 5 gaps
  python -m historical_collection.scripts.backfill_gaps --symbol AAPL --max-gaps 5
        """
    )
    
    parser.add_argument(
        '--symbol', '-s',
        type=str,
        help='Process specific symbol instead of all symbols'
    )
    
    parser.add_argument(
        '--detect-only',
        action='store_true',
        help='Only detect gaps, do not backfill'
    )
    
    parser.add_argument(
        '--max-gaps',
        type=int,
        help='Maximum number of gaps to backfill per symbol'
    )
    
    parser.add_argument(
        '--min-gap-minutes',
        type=int,
        default=5,
        help='Minimum gap size in minutes to consider (default: 5)'
    )
    
    parser.add_argument(
        '--db-path',
        type=str,
        default='data/historical_data.db',
        help='Path to historical data database'
    )
    
    parser.add_argument(
        '--watchlist-path',
        type=str,
        default='watchlist.json',
        help='Path to watchlist file'
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
        # Initialize backfiller
        backfiller = GapBackfiller(args.db_path)
        
        # Get symbols to process
        if args.symbol:
            symbols = [args.symbol]
        else:
            # Load from manager to get watchlist
            manager = HistoricalDataManager(
                db_path=args.db_path,
                watchlist_path=args.watchlist_path
            )
            symbols = manager.symbols
        
        if not symbols:
            print("❌ No symbols to process")
            return 1
        
        logger.info(f"🎯 Processing {len(symbols)} symbols")
        
        # Process each symbol
        all_results = []
        total_gaps_found = 0
        total_gaps_filled = 0
        
        for symbol in symbols:
            logger.info(f"📊 Processing {symbol}")
            
            # Detect gaps
            gaps = backfiller.detect_gaps(symbol, min_gap_minutes=args.min_gap_minutes)
            total_gaps_found += len(gaps)
            
            if not gaps:
                print(f"✅ {symbol}: No gaps detected")
                continue
            
            print(f"🔍 {symbol}: Found {len(gaps)} gaps")
            
            if args.verbose:
                for i, gap in enumerate(gaps, 1):
                    market_indicator = "📈" if gap['market_hours_affected'] else "🌙"
                    print(f"   {market_indicator} Gap {i}: {gap['start_datetime']} to "
                          f"{gap['end_datetime']} ({gap['duration_minutes']} minutes)")
            
            # Backfill if requested
            if not args.detect_only:
                result = backfiller.backfill_symbol_gaps(symbol, args.max_gaps)
                all_results.append(result)
                
                if result['status'] == 'completed':
                    filled = result['successful_backfills']
                    total_gaps_filled += filled
                    print(f"🔧 {symbol}: Backfilled {filled}/{result['total_gaps']} gaps")
                else:
                    print(f"❌ {symbol}: {result.get('message', 'Backfill failed')}")
        
        # Summary
        if args.detect_only:
            print(f"\n📊 Gap Detection Summary:")
            print(f"Total symbols processed: {len(symbols)}")
            print(f"Total gaps found: {total_gaps_found}")
        else:
            print(f"\n🎉 Backfill Summary:")
            print(f"Total symbols processed: {len(symbols)}")
            print(f"Total gaps found: {total_gaps_found}")
            print(f"Total gaps filled: {total_gaps_filled}")
            
            success_rate = (total_gaps_filled / total_gaps_found * 100) if total_gaps_found > 0 else 0
            print(f"Success rate: {success_rate:.1f}%")
        
        return 0
    
    except KeyboardInterrupt:
        logger.info("⏹️  Process interrupted by user")
        print("\n⏹️  Process interrupted by user")
        return 1
    
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        print(f"💥 Unexpected error: {e}")
        if args.verbose:
            raise
        return 1

if __name__ == '__main__':
    exit(main())