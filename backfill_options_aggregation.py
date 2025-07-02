#!/usr/bin/env python3
"""
Enhanced Options Aggregation Backfill Script

This script processes raw options data and creates aggregated flow metrics for multiple symbols
and date ranges. It can auto-discover available symbols and dates or process specific targets.

Usage:
    # Process all symbols for all available dates
    python backfill_options_aggregation.py --all
    
    # Process specific symbol for specific date
    python backfill_options_aggregation.py --symbol SPY --date 2025-07-01
    
    # Process specific symbols for date range
    python backfill_options_aggregation.py --symbols SPY,QQQ,TSLA --start-date 2025-07-01 --end-date 2025-07-02
    
    # Process missing July 1st data for all symbols except SPY
    python backfill_options_aggregation.py --missing-july-1st

The script will:
1. Discover available symbols and dates (or use specified parameters)
2. Process each symbol/timestamp combination using the flow calculator
3. Store aggregated results in the options_flow_agg table
4. Provide detailed progress updates and summary statistics
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple, Set

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from options_collection.core.flow_calculator import OptionsFlowCalculator

def setup_logging(verbose: bool = False):
    """Set up logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('backfill_options_aggregation.log')
        ]
    )

def discover_available_symbols(db_path: str) -> List[str]:
    """
    Discover all symbols that have raw options data
    
    Args:
        db_path: Path to options database
        
    Returns:
        List of symbols sorted alphabetically
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM options_data ORDER BY symbol")
        return [row[0] for row in cursor.fetchall()]

def discover_available_dates(db_path: str, symbol: str = None) -> List[str]:
    """
    Discover all dates that have raw options data
    
    Args:
        db_path: Path to options database
        symbol: Optional symbol to filter by
        
    Returns:
        List of dates in YYYY-MM-DD format
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        if symbol:
            cursor.execute("""
                SELECT DISTINCT date(datetime(timestamp/1000, 'unixepoch')) as date
                FROM options_data 
                WHERE symbol = ?
                ORDER BY date
            """, (symbol,))
        else:
            cursor.execute("""
                SELECT DISTINCT date(datetime(timestamp/1000, 'unixepoch')) as date
                FROM options_data 
                ORDER BY date
            """)
        
        return [row[0] for row in cursor.fetchall()]

def get_timestamps_for_symbol_date(db_path: str, symbol: str, date: str) -> List[int]:
    """
    Get all distinct timestamps for a symbol on a specific date
    
    Args:
        db_path: Path to options database
        symbol: Symbol to process
        date: Date in YYYY-MM-DD format
        
    Returns:
        List of timestamps sorted chronologically
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT timestamp 
            FROM options_data 
            WHERE symbol = ? 
            AND date(datetime(timestamp/1000, 'unixepoch')) = ?
            ORDER BY timestamp
        """, (symbol, date))
        
        return [row[0] for row in cursor.fetchall()]

def check_existing_aggregations(db_path: str, symbol: str, date: str) -> int:
    """
    Check how many aggregated records already exist for a symbol/date
    
    Args:
        db_path: Path to options database
        symbol: Symbol to check
        date: Date in YYYY-MM-DD format
        
    Returns:
        Number of existing aggregated records
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM options_flow_agg 
            WHERE symbol = ? 
            AND date(datetime(timestamp/1000, 'unixepoch')) = ?
        """, (symbol, date))
        
        return cursor.fetchone()[0]

def get_missing_july_1st_symbols(db_path: str) -> List[str]:
    """
    Get symbols that are missing July 1st aggregated data
    
    Args:
        db_path: Path to options database
        
    Returns:
        List of symbols missing July 1st data
    """
    all_symbols = discover_available_symbols(db_path)
    missing_symbols = []
    
    for symbol in all_symbols:
        existing_count = check_existing_aggregations(db_path, symbol, '2025-07-01')
        if existing_count == 0:
            missing_symbols.append(symbol)
    
    return missing_symbols

def process_symbol_date(flow_calc: OptionsFlowCalculator, symbol: str, date: str, 
                       timestamps: List[int], logger: logging.Logger) -> Tuple[int, int]:
    """
    Process all timestamps for a specific symbol/date combination
    
    Args:
        flow_calc: OptionsFlowCalculator instance
        symbol: Symbol to process
        date: Date being processed
        timestamps: List of timestamps to process
        logger: Logger instance
        
    Returns:
        Tuple of (successful_count, failed_count)
    """
    successful = 0
    failed = 0
    
    for i, timestamp in enumerate(timestamps, 1):
        try:
            progress = (i / len(timestamps)) * 100
            timestamp_readable = datetime.fromtimestamp(timestamp / 1000).strftime('%H:%M:%S')
            
            success = flow_calc.calculate_and_store_aggregation(symbol, timestamp)
            
            if success:
                successful += 1
                if i % 100 == 0 or i <= 5:  # Log every 100th or first 5 for progress
                    logger.info(f"  ✅ [{i:4d}/{len(timestamps)}] ({progress:5.1f}%) {timestamp_readable}")
            else:
                failed += 1
                logger.warning(f"  ❌ [{i:4d}/{len(timestamps)}] ({progress:5.1f}%) {timestamp_readable} - Failed")
                
        except Exception as e:
            failed += 1
            logger.error(f"  💥 [{i:4d}/{len(timestamps)}] {timestamp_readable} - Error: {e}")
            continue
    
    return successful, failed

def show_sample_data(db_path: str, symbol: str, date: str, logger: logging.Logger):
    """Show sample of aggregated data that was created"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                datetime(timestamp/1000, 'unixepoch') as time,
                call_delta_volume,
                put_delta_volume,
                net_delta_volume,
                underlying_price,
                sentiment
            FROM options_flow_agg 
            WHERE symbol = ? 
            AND date(datetime(timestamp/1000, 'unixepoch')) = ?
            ORDER BY timestamp 
            LIMIT 3
        """, (symbol, date))
        
        rows = cursor.fetchall()
        if rows:
            logger.info(f"    📋 Sample {symbol} data for {date}:")
            for row in rows:
                logger.info(f"      {row[0]} | Call ΔVol: {row[1]:8.0f} | Put ΔVol: {row[2]:8.0f} | Net: {row[3]:8.0f} | ${row[4]:6.2f} | {row[5]}")

def main():
    """Main backfill process"""
    parser = argparse.ArgumentParser(description='Backfill options aggregation data')
    parser.add_argument('--all', action='store_true', help='Process all symbols and all dates')
    parser.add_argument('--missing-july-1st', action='store_true', help='Process missing July 1st data for all symbols except SPY')
    parser.add_argument('--symbol', type=str, help='Process specific symbol')
    parser.add_argument('--symbols', type=str, help='Process specific symbols (comma-separated)')
    parser.add_argument('--date', type=str, help='Process specific date (YYYY-MM-DD)')
    parser.add_argument('--start-date', type=str, help='Start date for range (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date for range (YYYY-MM-DD)')
    parser.add_argument('--db-path', type=str, default='data/options_data.db', help='Path to database')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without doing it')
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Configuration
    DB_PATH = args.db_path
    
    logger.info("🚀 Starting enhanced options aggregation backfill")
    logger.info(f"📂 Database: {DB_PATH}")
    
    try:
        # Determine symbols to process
        if args.all:
            symbols_to_process = discover_available_symbols(DB_PATH)
            logger.info(f"🎯 Processing ALL symbols: {', '.join(symbols_to_process)}")
        elif args.missing_july_1st:
            symbols_to_process = get_missing_july_1st_symbols(DB_PATH)
            logger.info(f"🎯 Processing symbols missing July 1st data: {', '.join(symbols_to_process)}")
        elif args.symbols:
            symbols_to_process = [s.strip().upper() for s in args.symbols.split(',')]
            logger.info(f"🎯 Processing specified symbols: {', '.join(symbols_to_process)}")
        elif args.symbol:
            symbols_to_process = [args.symbol.upper()]
            logger.info(f"🎯 Processing single symbol: {args.symbol.upper()}")
        else:
            logger.error("❌ Must specify symbols to process (--all, --missing-july-1st, --symbol, or --symbols)")
            return 1
        
        # Determine dates to process
        if args.all:
            # For --all, process all available dates for each symbol
            dates_to_process = None  # Will be determined per symbol
        elif args.missing_july_1st:
            dates_to_process = ['2025-07-01']
        elif args.date:
            dates_to_process = [args.date]
        elif args.start_date and args.end_date:
            # Generate date range
            start = datetime.strptime(args.start_date, '%Y-%m-%d')
            end = datetime.strptime(args.end_date, '%Y-%m-%d')
            dates_to_process = []
            current = start
            while current <= end:
                dates_to_process.append(current.strftime('%Y-%m-%d'))
                current += timedelta(days=1)
        else:
            # Default to discovering all dates
            dates_to_process = discover_available_dates(DB_PATH)
            if args.symbol or args.symbols:
                logger.info(f"📅 Processing all available dates: {', '.join(dates_to_process)}")
        
        if not symbols_to_process:
            logger.warning("❌ No symbols to process")
            return 1
        
        # Initialize flow calculator if not dry run
        if not args.dry_run:
            flow_calc = OptionsFlowCalculator(DB_PATH)
        
        # Process each symbol
        total_successful = 0
        total_failed = 0
        total_timestamps = 0
        
        for symbol in symbols_to_process:
            logger.info(f"\n📊 Processing symbol: {symbol}")
            
            # Get dates for this symbol if not specified
            if dates_to_process is None:
                symbol_dates = discover_available_dates(DB_PATH, symbol)
            else:
                symbol_dates = dates_to_process
            
            logger.info(f"📅 Dates for {symbol}: {', '.join(symbol_dates)}")
            
            symbol_successful = 0
            symbol_failed = 0
            symbol_timestamps = 0
            
            for date in symbol_dates:
                # Check existing aggregations
                existing_count = check_existing_aggregations(DB_PATH, symbol, date)
                
                # Get timestamps to process
                timestamps = get_timestamps_for_symbol_date(DB_PATH, symbol, date)
                
                if not timestamps:
                    logger.info(f"  📅 {date}: No raw data found")
                    continue
                
                symbol_timestamps += len(timestamps)
                total_timestamps += len(timestamps)
                
                start_time = datetime.fromtimestamp(timestamps[0] / 1000)
                end_time = datetime.fromtimestamp(timestamps[-1] / 1000)
                
                logger.info(f"  📅 {date}: {len(timestamps)} timestamps ({start_time.strftime('%H:%M:%S')}-{end_time.strftime('%H:%M:%S')}), {existing_count} existing")
                
                if args.dry_run:
                    logger.info(f"    [DRY RUN] Would process {len(timestamps)} timestamps")
                    continue
                
                if existing_count > 0:
                    logger.info(f"    ⏭️  Skipping - already has {existing_count} aggregated records")
                    continue
                
                # Process this symbol/date combination
                successful, failed = process_symbol_date(flow_calc, symbol, date, timestamps, logger)
                
                symbol_successful += successful
                symbol_failed += failed
                total_successful += successful
                total_failed += failed
                
                # Show final count and sample data
                final_count = check_existing_aggregations(DB_PATH, symbol, date)
                new_records = final_count - existing_count
                logger.info(f"    ✅ Created {new_records} new aggregation records")
                
                if new_records > 0:
                    show_sample_data(DB_PATH, symbol, date, logger)
            
            # Symbol summary
            if symbol_timestamps > 0:
                symbol_success_rate = (symbol_successful / symbol_timestamps * 100) if symbol_timestamps > 0 else 0
                logger.info(f"  📊 {symbol} Summary: {symbol_successful}/{symbol_timestamps} successful ({symbol_success_rate:.1f}%)")
        
        # Final summary
        logger.info("\n" + "="*60)
        logger.info("📊 ENHANCED BACKFILL SUMMARY")
        logger.info("="*60)
        logger.info(f"Symbols processed: {', '.join(symbols_to_process)}")
        logger.info(f"Total timestamps processed: {total_timestamps}")
        logger.info(f"Successful aggregations: {total_successful}")
        logger.info(f"Failed aggregations: {total_failed}")
        
        if total_timestamps > 0:
            success_rate = (total_successful / total_timestamps * 100)
            logger.info(f"Overall success rate: {success_rate:.1f}%")
            
            if total_successful > 0:
                logger.info("✅ Backfill completed successfully!")
            else:
                logger.warning("⚠️  No new aggregations were created")
        else:
            logger.info("ℹ️  No timestamps to process")
        
        return 0 if not args.dry_run else 0
        
    except Exception as e:
        logger.error(f"💥 Unexpected error during backfill: {e}")
        return 1

if __name__ == '__main__':
    exit(main())