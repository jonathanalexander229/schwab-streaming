import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from .ohlc_database import OHLCDatabase
from .rate_limited_collector import RateLimitedCollector
from ..utils.data_validator import DataValidator

logger = logging.getLogger(__name__)

class HistoricalDataManager:
    def __init__(self, db_path: str = None, watchlist_path: str = None, 
                 rate_limit_delay: float = 0.6):
        """
        Initialize the Historical Data Manager
        
        Args:
            db_path: Path to the historical data database
            watchlist_path: Path to the watchlist.json file
            rate_limit_delay: Delay between API calls in seconds
        """
        # Set default paths relative to project root
        if db_path is None:
            db_path = "data/historical_data.db"
        if watchlist_path is None:
            watchlist_path = "watchlist.json"
        
        self.db_path = db_path
        self.watchlist_path = watchlist_path
        
        # Initialize components
        self.database = OHLCDatabase(db_path)
        self.collector = RateLimitedCollector(rate_limit_delay)
        self.validator = DataValidator()
        
        # Load watchlist
        self.symbols = self._load_watchlist()
        
        logger.info(f"📊 Historical Data Manager initialized")
        logger.info(f"📍 Database: {db_path}")
        logger.info(f"📝 Watchlist: {watchlist_path} ({len(self.symbols)} symbols)")
    
    def _load_watchlist(self) -> List[str]:
        """Load symbols from watchlist.json"""
        try:
            with open(self.watchlist_path, 'r') as f:
                watchlist_data = json.load(f)
                symbols = watchlist_data.get('symbols', [])
                logger.info(f"✅ Loaded {len(symbols)} symbols from watchlist")
                return symbols
        except FileNotFoundError:
            logger.error(f"❌ Watchlist file not found: {self.watchlist_path}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in watchlist file: {e}")
            return []
    
    def collect_historical_data(self, symbol: str, years: int = 5, 
                              market_hours_only: bool = True,
                              validate_data: bool = True) -> Dict[str, Any]:
        """
        Collect historical data for a single symbol
        
        Args:
            symbol: Stock symbol to collect data for
            years: Number of years of historical data to collect
            market_hours_only: Filter to market hours only
            validate_data: Perform data quality validation
        
        Returns:
            Dictionary with collection results and statistics
        """
        logger.info(f"🎯 Starting data collection for {symbol} ({years} years)")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())
        
        # Check if data already exists for this specific date range
        existing_progress = self.database.get_collection_progress(symbol)
        if existing_progress and existing_progress['status'] == 'completed':
            # Check if existing collection covers the requested date range
            existing_start = existing_progress['start_date']
            existing_end = existing_progress['end_date']
            
            if existing_start <= start_timestamp and existing_end >= end_timestamp:
                logger.info(f"ℹ️  Data already collected for {symbol} covering requested date range")
                return {
                    'symbol': symbol,
                    'status': 'already_exists',
                    'message': f'Data already collected for this date range ({start_date.date()} to {end_date.date()})'
                }
            else:
                logger.info(f"🔄 Existing data for {symbol} doesn't cover full requested range, extending collection")
        
        # Update progress tracking
        self.database.update_collection_progress(
            symbol, start_timestamp, end_timestamp, start_timestamp, 'in_progress'
        )
        
        try:
            # Collect data from API
            raw_candles = self.collector.get_historical_data_chunked(
                symbol, start_date, end_date
            )
            
            if not raw_candles:
                logger.error(f"❌ No data returned for {symbol}")
                self.database.update_collection_progress(
                    symbol, start_timestamp, end_timestamp, start_timestamp, 'failed'
                )
                return {
                    'symbol': symbol,
                    'status': 'failed',
                    'message': 'No data returned from API'
                }
            
            logger.info(f"📥 Collected {len(raw_candles)} raw candles for {symbol}")
            
            # Data validation and cleaning
            processed_candles = raw_candles
            
            if validate_data:
                # Remove duplicates
                processed_candles = self.validator.remove_duplicates(processed_candles)
                
                # Filter to market hours if requested
                if market_hours_only:
                    processed_candles = self.validator.filter_market_hours_only(processed_candles)
                
                # Generate quality report
                quality_report = self.validator.get_data_quality_report(processed_candles, symbol)
                logger.info(f"📊 Data quality score for {symbol}: {quality_report['quality_score']:.1f}/100")
                
                # Log any issues
                if quality_report['issues']:
                    for issue in quality_report['issues']:
                        logger.warning(f"⚠️  {symbol}: {issue}")
            
            # Store in database
            inserted_count = self.database.insert_ohlc_data(symbol, processed_candles)
            
            # Update progress as completed
            self.database.update_collection_progress(
                symbol, start_timestamp, end_timestamp, end_timestamp, 'completed'
            )
            
            logger.info(f"✅ Successfully stored {inserted_count} candles for {symbol}")
            
            return {
                'symbol': symbol,
                'status': 'success',
                'raw_candles': len(raw_candles),
                'processed_candles': len(processed_candles),
                'inserted_candles': inserted_count,
                'quality_report': quality_report if validate_data else None,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error collecting data for {symbol}: {e}")
            self.database.update_collection_progress(
                symbol, start_timestamp, end_timestamp, start_timestamp, 'failed'
            )
            return {
                'symbol': symbol,
                'status': 'error',
                'message': str(e)
            }
    
    def collect_all_watchlist_data(self, years: int = 5, 
                                 market_hours_only: bool = True,
                                 validate_data: bool = True) -> Dict[str, Any]:
        """
        Collect historical data for all symbols in watchlist
        
        Args:
            years: Number of years of historical data to collect
            market_hours_only: Filter to market hours only
            validate_data: Perform data quality validation
        
        Returns:
            Dictionary with overall collection results
        """
        if not self.symbols:
            logger.error("❌ No symbols in watchlist")
            return {
                'status': 'error',
                'message': 'No symbols in watchlist'
            }
        
        logger.info(f"🚀 Starting collection for {len(self.symbols)} symbols")
        
        results = []
        successful_collections = 0
        failed_collections = 0
        
        for i, symbol in enumerate(self.symbols, 1):
            logger.info(f"📊 Processing symbol {i}/{len(self.symbols)}: {symbol}")
            
            result = self.collect_historical_data(
                symbol, years, market_hours_only, validate_data
            )
            
            results.append(result)
            
            if result['status'] == 'success':
                successful_collections += 1
            elif result['status'] == 'failed' or result['status'] == 'error':
                failed_collections += 1
            
            logger.info(f"✅ Completed {symbol}: {result['status']}")
        
        # Generate summary
        total_candles = sum(r.get('inserted_candles', 0) for r in results)
        
        summary = {
            'status': 'completed',
            'total_symbols': len(self.symbols),
            'successful_collections': successful_collections,
            'failed_collections': failed_collections,
            'already_existing': len(self.symbols) - successful_collections - failed_collections,
            'total_candles_collected': total_candles,
            'individual_results': results
        }
        
        logger.info(f"🎉 Collection complete! {successful_collections}/{len(self.symbols)} successful")
        logger.info(f"📊 Total candles collected: {total_candles:,}")
        
        return summary
    
    def get_collection_status(self) -> Dict[str, Any]:
        """Get current collection status for all symbols"""
        status_summary = {
            'symbols': [],
            'total_symbols': len(self.symbols),
            'completed': 0,
            'in_progress': 0,
            'failed': 0,
            'pending': 0
        }
        
        for symbol in self.symbols:
            progress = self.database.get_collection_progress(symbol)
            stats = self.database.get_symbol_stats(symbol)
            
            symbol_status = {
                'symbol': symbol,
                'status': progress['status'] if progress else 'pending',
                'candles_collected': stats['total_candles'],
                'last_updated': progress['updated_at'] if progress else None
            }
            
            status_summary['symbols'].append(symbol_status)
            
            # Update counters
            status = symbol_status['status']
            if status in status_summary:
                status_summary[status] += 1
        
        return status_summary
    
    def test_connection(self) -> bool:
        """Test the Schwab API connection"""
        logger.info("🔍 Testing Schwab API connection...")
        success = self.collector.test_connection()
        
        if success:
            logger.info("✅ Connection test successful")
        else:
            logger.error("❌ Connection test failed")
        
        return success