import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import schwabdev
from auth import get_schwab_client

logger = logging.getLogger(__name__)

class RateLimitedCollector:
    def __init__(self, rate_limit_delay: float = 0.6):
        self.rate_limit_delay = rate_limit_delay  # 120 requests/minute = 0.5s, use 0.6s for safety
        self.last_request_time = 0
        self.client: Optional[schwabdev.Client] = None
        self._init_client()
    
    def _init_client(self) -> bool:
        """Initialize Schwab client using existing auth module"""
        try:
            self.client = get_schwab_client()
            if self.client:
                logger.info("✅ Schwab client initialized for historical data collection")
                return True
            else:
                logger.error("❌ Failed to initialize Schwab client")
                return False
        except Exception as e:
            logger.error(f"❌ Error initializing Schwab client: {e}")
            return False
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting between API calls"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def get_historical_data(self, symbol: str, period_type: str = "year", 
                          period: int = 5, frequency_type: str = "minute", 
                          frequency: int = 1, need_extended_hours_data: bool = False,
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch historical price data from Schwab API with rate limiting
        
        Args:
            symbol: Stock symbol to fetch data for
            period_type: The type of period to show (day, month, year, ytd)
            period: The number of periods to show
            frequency_type: The type of frequency (minute, daily, weekly, monthly)
            frequency: The frequency of data
            need_extended_hours_data: Include extended hours data
            start_date: Start date for date range queries
            end_date: End date for date range queries
        
        Returns:
            List of OHLC candle dictionaries or None if failed
        """
        if not self.client:
            logger.error("❌ Schwab client not initialized")
            return None
        
        try:
            self._enforce_rate_limit()
            logger.info(f"📊 Fetching historical data for {symbol}")
            
            # Build request parameters
            params = {
                "symbol": symbol,
                "frequencyType": frequency_type,
                "frequency": frequency,
                "needExtendedHoursData": need_extended_hours_data
            }
            
            # Add date range if provided, otherwise use period
            if start_date and end_date:
                params["startDate"] = int(start_date.timestamp() * 1000)  # Schwab expects milliseconds
                params["endDate"] = int(end_date.timestamp() * 1000)
            else:
                params["periodType"] = period_type
                params["period"] = period
            
            # Debug logging
            logger.info(f"🔍 API params for {symbol}: {params}")
            
            # Make API call
            response = self.client.price_history(**params)
            
            # Parse JSON response if it's a Response object
            if hasattr(response, 'json'):
                try:
                    response_data = response.json()
                    logger.info(f"🔍 API response status: {response.status_code}")
                    logger.info(f"🔍 Response keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
                except Exception as e:
                    logger.error(f"❌ Failed to parse JSON response: {e}")
                    logger.info(f"🔍 Raw response: {response.text[:200]}...")
                    return None
            else:
                response_data = response
                logger.info(f"🔍 Direct response type: {type(response_data)}")
            
            if response_data and "candles" in response_data:
                candles = response_data["candles"]
                logger.info(f"✅ Retrieved {len(candles)} candles for {symbol}")
                
                # Convert to standard format
                standardized_candles = []
                for candle in candles:
                    standardized_candles.append({
                        'datetime': int(candle['datetime'] / 1000),  # Convert from milliseconds
                        'open': candle['open'],
                        'high': candle['high'],
                        'low': candle['low'],
                        'close': candle['close'],
                        'volume': candle['volume']
                    })
                
                return standardized_candles
            else:
                logger.warning(f"⚠️  No candle data returned for {symbol}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error fetching historical data for {symbol}: {e}")
            return None
    
    def get_historical_data_by_frequency(self, symbol: str, frequency_type: str, 
                                       frequency: int = 1) -> List[Dict[str, Any]]:
        """
        Get historical data using optimal strategy for each frequency
        
        Args:
            symbol: Stock symbol
            frequency_type: 'minute' or 'daily'
            frequency: Frequency value (1, 5, 15, 30 for minute; 1 for daily)
        
        Returns:
            List of OHLC candles using best available strategy
        """
        logger.info(f"📊 Collecting {frequency}{frequency_type[0]} data for {symbol}")
        
        if frequency_type == 'daily':
            # Daily data: Use period parameters for maximum history
            return self._get_daily_data(symbol)
        elif frequency_type == 'minute':
            if frequency == 1:
                # 1-minute: Use date range for ~46 days
                return self._get_minute_data(symbol, frequency)
            elif frequency in [5, 15, 30]:
                # 5-30 minute: Use date range for ~259 days  
                return self._get_intraday_data(symbol, frequency)
        
        logger.warning(f"⚠️  Unsupported frequency: {frequency}{frequency_type}")
        return []
    
    def _get_daily_data(self, symbol: str) -> List[Dict[str, Any]]:
        """Get daily data using period parameters (2+ years)"""
        try:
            data = self.get_historical_data(
                symbol=symbol,
                period_type="year",
                period=2,  # 2 years
                frequency_type="daily",
                frequency=1
            )
            if data:
                logger.info(f"✅ Daily data: {len(data)} candles (~2 years)")
            return data or []
        except Exception as e:
            logger.error(f"❌ Error getting daily data: {e}")
            return []
    
    def _get_minute_data(self, symbol: str, frequency: int) -> List[Dict[str, Any]]:
        """Get 1-minute data using date range (~46 days)"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=60)  # Try 60 days, API will limit to ~46
            
            data = self.get_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                frequency_type="minute",
                frequency=frequency
            )
            if data:
                actual_days = (datetime.fromtimestamp(data[-1]['datetime']) - 
                             datetime.fromtimestamp(data[0]['datetime'])).days
                logger.info(f"✅ {frequency}m data: {len(data)} candles ({actual_days} days)")
            return data or []
        except Exception as e:
            logger.error(f"❌ Error getting {frequency}m data: {e}")
            return []
    
    def _get_intraday_data(self, symbol: str, frequency: int) -> List[Dict[str, Any]]:
        """Get 5-30 minute data using date range (~259 days)"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=300)  # Try 300 days, API will limit to ~259
            
            data = self.get_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                frequency_type="minute",
                frequency=frequency
            )
            if data:
                actual_days = (datetime.fromtimestamp(data[-1]['datetime']) - 
                             datetime.fromtimestamp(data[0]['datetime'])).days
                logger.info(f"✅ {frequency}m data: {len(data)} candles ({actual_days} days)")
            return data or []
        except Exception as e:
            logger.error(f"❌ Error getting {frequency}m data: {e}")
            return []

    def get_historical_data_chunked(self, symbol: str, start_date: datetime, 
                                  end_date: datetime, chunk_days: int = 90) -> List[Dict[str, Any]]:
        """
        Fetch historical data in chunks to handle large date ranges
        
        Args:
            symbol: Stock symbol
            start_date: Start date for data collection
            end_date: End date for data collection
            chunk_days: Size of each chunk in days
        
        Returns:
            Combined list of all OHLC candles
        """
        all_candles = []
        current_start = start_date
        
        while current_start < end_date:
            current_end = min(current_start + timedelta(days=chunk_days), end_date)
            
            logger.info(f"📅 Fetching {symbol} data from {current_start.date()} to {current_end.date()}")
            
            chunk_data = self.get_historical_data(
                symbol=symbol,
                start_date=current_start,
                end_date=current_end,
                frequency_type="minute",
                frequency=1,
                need_extended_hours_data=False
            )
            
            if chunk_data:
                all_candles.extend(chunk_data)
                logger.info(f"✅ Added {len(chunk_data)} candles from chunk")
            else:
                logger.warning(f"⚠️  No data returned for chunk {current_start.date()} to {current_end.date()}")
            
            current_start = current_end + timedelta(days=1)
        
        # Sort by timestamp to ensure chronological order
        all_candles.sort(key=lambda x: x['datetime'])
        
        logger.info(f"🎯 Total candles collected for {symbol}: {len(all_candles)}")
        return all_candles
    
    def test_connection(self) -> bool:
        """Test the connection by making a simple API call"""
        if not self.client:
            return False
        
        try:
            # Test with a simple quote request
            self._enforce_rate_limit()
            response = self.client.quotes(["AAPL"])
            return response is not None
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False