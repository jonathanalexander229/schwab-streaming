#!/usr/bin/env python3
"""
Backfill SPY Options Aggregation Script

This script processes yesterday's raw SPY options data and creates aggregated flow metrics
using today's aggregation logic. This allows us to populate the options_flow_agg table
with historical data for comparison and analysis.

Usage:
    python backfill_spy_aggregation.py

The script will:
1. Find all distinct timestamps for SPY from yesterday (July 1, 2025)
2. Process each timestamp using the flow calculator
3. Store aggregated results in the options_flow_agg table
4. Provide progress updates and summary statistics
"""

import logging
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from options_collection.core.flow_calculator import OptionsFlowCalculator

def setup_logging():
    """Set up logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('backfill_spy_aggregation.log')
        ]
    )

def get_spy_timestamps_from_yesterday(db_path: str) -> list:
    """
    Get all distinct timestamps for SPY from yesterday (July 1, 2025)
    
    Args:
        db_path: Path to options database
        
    Returns:
        List of timestamps sorted chronologically
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT timestamp 
            FROM options_data 
            WHERE symbol = 'SPY' 
            AND date(datetime(timestamp/1000, 'unixepoch')) = '2025-07-01'
            ORDER BY timestamp
        """)
        
        return [row[0] for row in cursor.fetchall()]

def check_existing_aggregations(db_path: str, symbol: str = 'SPY') -> int:
    """
    Check how many aggregated records already exist for SPY from yesterday
    
    Args:
        db_path: Path to options database
        symbol: Symbol to check (default: SPY)
        
    Returns:
        Number of existing aggregated records
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM options_flow_agg 
            WHERE symbol = ? 
            AND date(datetime(timestamp/1000, 'unixepoch')) = '2025-07-01'
        """, (symbol,))
        
        return cursor.fetchone()[0]

def main():
    """Main backfill process"""
    logger = logging.getLogger(__name__)
    
    # Configuration
    DB_PATH = 'data/options_data.db'
    SYMBOL = 'SPY'
    TARGET_DATE = '2025-07-01'
    
    logger.info(f"🚀 Starting SPY options aggregation backfill for {TARGET_DATE}")
    logger.info(f"📂 Database: {DB_PATH}")
    
    try:
        # Initialize flow calculator
        flow_calc = OptionsFlowCalculator(DB_PATH)
        
        # Check existing aggregations
        existing_count = check_existing_aggregations(DB_PATH, SYMBOL)
        logger.info(f"📊 Existing {SYMBOL} aggregations for {TARGET_DATE}: {existing_count}")
        
        # Get all timestamps to process
        timestamps = get_spy_timestamps_from_yesterday(DB_PATH)
        logger.info(f"🎯 Found {len(timestamps)} distinct {SYMBOL} collection timestamps to process")
        
        if not timestamps:
            logger.warning(f"❌ No {SYMBOL} data found for {TARGET_DATE}")
            return 1
        
        # Show time range
        start_time = datetime.fromtimestamp(timestamps[0] / 1000)
        end_time = datetime.fromtimestamp(timestamps[-1] / 1000)
        logger.info(f"📅 Time range: {start_time.strftime('%H:%M:%S')} to {end_time.strftime('%H:%M:%S')}")
        
        # Process each timestamp
        successful_aggregations = 0
        failed_aggregations = 0
        
        logger.info("🔄 Starting aggregation processing...")
        
        for i, timestamp in enumerate(timestamps, 1):
            try:
                # Calculate progress
                progress = (i / len(timestamps)) * 100
                timestamp_readable = datetime.fromtimestamp(timestamp / 1000).strftime('%H:%M:%S')
                
                # Process this timestamp
                success = flow_calc.calculate_and_store_aggregation(SYMBOL, timestamp)
                
                if success:
                    successful_aggregations += 1
                    if i % 50 == 0 or i <= 10:  # Log every 50th or first 10 for progress
                        logger.info(f"✅ [{i:3d}/{len(timestamps)}] ({progress:5.1f}%) {timestamp_readable} - Success")
                else:
                    failed_aggregations += 1
                    logger.warning(f"❌ [{i:3d}/{len(timestamps)}] ({progress:5.1f}%) {timestamp_readable} - Failed")
                    
            except Exception as e:
                failed_aggregations += 1
                logger.error(f"💥 [{i:3d}/{len(timestamps)}] {timestamp_readable} - Error: {e}")
                continue
        
        # Final summary
        logger.info("\n" + "="*60)
        logger.info("📊 BACKFILL SUMMARY")
        logger.info("="*60)
        logger.info(f"Symbol: {SYMBOL}")
        logger.info(f"Date: {TARGET_DATE}")
        logger.info(f"Total timestamps processed: {len(timestamps)}")
        logger.info(f"Successful aggregations: {successful_aggregations}")
        logger.info(f"Failed aggregations: {failed_aggregations}")
        logger.info(f"Success rate: {(successful_aggregations/len(timestamps)*100):.1f}%")
        
        # Check final aggregation count
        final_count = check_existing_aggregations(DB_PATH, SYMBOL)
        new_records = final_count - existing_count
        logger.info(f"New aggregation records created: {new_records}")
        logger.info(f"Total {SYMBOL} aggregations for {TARGET_DATE}: {final_count}")
        
        if successful_aggregations > 0:
            logger.info(f"✅ Backfill completed successfully!")
            
            # Show sample of what was created
            logger.info("\n📋 Sample aggregated data:")
            with sqlite3.connect(DB_PATH) as conn:
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
                    AND date(datetime(timestamp/1000, 'unixepoch')) = '2025-07-01'
                    ORDER BY timestamp 
                    LIMIT 5
                """, (SYMBOL,))
                
                for row in cursor.fetchall():
                    logger.info(f"  {row[0]} | Call ΔVol: {row[1]:8.0f} | Put ΔVol: {row[2]:8.0f} | Net: {row[3]:8.0f} | ${row[4]:6.2f} | {row[5]}")
        else:
            logger.error("❌ No aggregations were successful")
            return 1
            
        return 0
        
    except Exception as e:
        logger.error(f"💥 Unexpected error during backfill: {e}")
        return 1

if __name__ == '__main__':
    setup_logging()
    exit(main())