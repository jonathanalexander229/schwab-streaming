import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import pytz
from .options_database import OptionsDatabase

logger = logging.getLogger(__name__)

class OptionsCollector:
    """
    Simple options data collector - fetches from Schwab API and stores in database.
    Includes basic market hours check and rate limiting like the example.
    """
    
    def __init__(self, schwab_client, db_path: str = "data/options_data.db", rate_limit_delay: float = 0.6, store_raw_data: bool = True):
        """
        Initialize the options collector
        
        Args:
            schwab_client: Authenticated Schwab client
            db_path: Path to options database
            rate_limit_delay: Delay between API calls in seconds
            store_raw_data: Whether to store raw individual option records for backtesting
        """
        self.client = schwab_client
        self.database = OptionsDatabase(db_path)
        self.rate_limit_delay = rate_limit_delay
        self.store_raw_data_enabled = store_raw_data
        
        # Cache for deduplicating raw option records
        self.last_option_hashes = {}
        
        # Market hours setup (like the example)
        self.ET = pytz.timezone('US/Eastern')
        self.MARKET_OPEN = (9, 30)
        self.MARKET_CLOSE = (16, 0)
        self.EXTENDED_START = (4, 0)
        self.EXTENDED_END = (20, 0)
        
        logger.info(f"📊 Options collector initialized with {rate_limit_delay}s rate limit")
    
    def is_trading_time(self, symbol: str = None) -> bool:
        """Check if options trading is active for given symbol"""
        now_et = datetime.now(self.ET)
        current_time = (now_et.hour, now_et.minute)
        
        # Weekend check
        if now_et.weekday() >= 5:
            return False
        
        # Regular market hours: 9:30 AM - 4:00 PM ET
        market_start_minutes = self.MARKET_OPEN[0] * 60 + self.MARKET_OPEN[1]
        market_end_minutes = self.MARKET_CLOSE[0] * 60 + self.MARKET_CLOSE[1]
        current_minutes = current_time[0] * 60 + current_time[1]
        
        # SPY and QQQ have 15-minute extended trading until 4:15 PM ET
        if symbol and symbol.upper() in ['SPY', 'QQQ']:
            extended_end_minutes = 16 * 60 + 15  # 4:15 PM
            return market_start_minutes <= current_minutes <= extended_end_minutes
        
        # All other symbols: regular market hours only
        return market_start_minutes <= current_minutes <= market_end_minutes
    
    def _calculate_option_metrics(self, symbol: str, options_data: Dict[str, Any]) -> tuple[float, float, int, int, float, List[Dict[str, Any]]]:
        """
        Calculate comprehensive option metrics and collect raw data in same loop
        Returns: (call_delta_vol, put_delta_vol, call_vol, put_vol, underlying_price, raw_records)
        """
        call_delta_vol = 0.0
        put_delta_vol = 0.0
        call_vol = 0
        put_vol = 0
        underlying_price = 0.0
        raw_records = []

        if not options_data:
            return call_delta_vol, put_delta_vol, call_vol, put_vol, underlying_price, raw_records

        # Get underlying price
        underlying_price = options_data.get("underlying", {}).get("mark", 0.0)
        timestamp = int(datetime.now().timestamp() * 1000)
        
        # Process calls
        for expiry in options_data.get("callExpDateMap", {}):
            for strike_price in options_data["callExpDateMap"][expiry]:
                for option in options_data["callExpDateMap"][expiry][strike_price]:
                    delta = option.get("delta", 0.0)
                    volume = option.get("totalVolume", 0)
                    if volume > 0:
                        call_delta_vol += delta * volume
                        call_vol += volume
                    
                    # Store raw data if enabled and data has changed
                    if self._should_store_option_record(symbol, expiry, float(strike_price), "CALL", option):
                        raw_records.append(self._create_option_record(symbol, timestamp, "CALL", expiry, 
                                                             float(strike_price), option, underlying_price))

        # Process puts (delta is negative, so we take absolute value for put_delta_vol)
        for expiry in options_data.get("putExpDateMap", {}):
            for strike_price in options_data["putExpDateMap"][expiry]:
                for option in options_data["putExpDateMap"][expiry][strike_price]:
                    delta = option.get("delta", 0.0)
                    volume = option.get("totalVolume", 0)
                    if volume > 0:
                        put_delta_vol += abs(delta) * volume  # Use absolute value
                        put_vol += volume
                    
                    # Store raw data if enabled and data has changed
                    if self._should_store_option_record(symbol, expiry, float(strike_price), "PUT", option):
                        raw_records.append(self._create_option_record(symbol, timestamp, "PUT", expiry, 
                                                             float(strike_price), option, underlying_price))

        return call_delta_vol, put_delta_vol, call_vol, put_vol, underlying_price, raw_records
    
    def _count_options_in_data(self, options_data: Dict[str, Any]) -> int:
        """Count total number of option contracts in the data"""
        count = 0
        
        for expiry in options_data.get("callExpDateMap", {}):
            for strike in options_data["callExpDateMap"][expiry]:
                count += len(options_data["callExpDateMap"][expiry][strike])
                
        for expiry in options_data.get("putExpDateMap", {}):
            for strike in options_data["putExpDateMap"][expiry]:
                count += len(options_data["putExpDateMap"][expiry][strike])
                
        return count
    
    def _get_option_hash(self, symbol: str, expiry: str, strike_price: float, option_type: str, option_data: Dict[str, Any]) -> str:
        """
        Generate hash for option based on key fields that indicate meaningful changes
        """
        import hashlib
        
        # Key fields that indicate the option data has meaningfully changed
        key_fields = [
            option_data.get("mark", 0),
            option_data.get("bid", 0), 
            option_data.get("ask", 0),
            option_data.get("last", 0),
            option_data.get("totalVolume", 0),
            option_data.get("openInterest", 0),
            option_data.get("delta", 0),
            option_data.get("gamma", 0),
            option_data.get("theta", 0),
            option_data.get("vega", 0),
            option_data.get("volatility", 0)
        ]
        
        # Create hash string from key fields
        hash_input = f"{symbol}|{expiry}|{strike_price}|{option_type}|{'|'.join(map(str, key_fields))}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def _should_store_option_record(self, symbol: str, expiry: str, strike_price: float, option_type: str, option_data: Dict[str, Any]) -> bool:
        """
        Check if option record should be stored based on whether data has changed
        """
        if not self.store_raw_data_enabled:
            return False
            
        option_key = (symbol, expiry, strike_price, option_type)
        current_hash = self._get_option_hash(symbol, expiry, strike_price, option_type, option_data)
        
        # Check if this option has changed since last time
        last_hash = self.last_option_hashes.get(option_key)
        if last_hash == current_hash:
            return False  # No change, don't store
        
        # Store the new hash and return True to indicate we should store
        self.last_option_hashes[option_key] = current_hash
        return True
    
    def _create_option_record(self, symbol: str, timestamp: int, option_type: str, 
                      expiry: str, strike_price: float, option_data: Dict[str, Any], 
                      underlying_price: float) -> Dict[str, Any]:
        """
        Create database record from option data - store everything we get from API
        """
        # Clean up expiration date format
        expiration_date = expiry.split(':')[0] if ':' in expiry else expiry
        
        # Simple intrinsic value calculation
        if option_type == "CALL":
            intrinsic_value = max(0, underlying_price - strike_price)
        else:  # PUT
            intrinsic_value = max(0, strike_price - underlying_price)
        
        mark = option_data.get("mark", 0.0)
        extrinsic_value = mark - intrinsic_value if mark else None
        
        # Calculate days to expiration
        try:
            exp_date = datetime.strptime(expiration_date, '%Y-%m-%d')
            time_to_expiration = (exp_date - datetime.now()).days
        except:
            time_to_expiration = None
        
        # Store all available data from API
        return {
            'symbol': symbol,
            'timestamp': timestamp,
            'option_type': option_type,
            'expiration_date': expiration_date,
            'strike_price': strike_price,
            
            # Pricing data (store whatever API gives us)
            'mark': option_data.get("mark"),
            'bid': option_data.get("bid"),
            'ask': option_data.get("ask"),
            'last': option_data.get("last"),
            
            # Volume and interest
            'total_volume': option_data.get("totalVolume"),
            'open_interest': option_data.get("openInterest"),
            
            # Greeks (store all available)
            'delta': option_data.get("delta"),
            'gamma': option_data.get("gamma"),
            'theta': option_data.get("theta"),
            'vega': option_data.get("vega"),
            'rho': option_data.get("rho"),
            
            # Volatility
            'implied_volatility': option_data.get("volatility"),
            'theoretical_value': option_data.get("theoreticalValue"),
            
            # Calculated fields
            'time_to_expiration': time_to_expiration,
            'intrinsic_value': intrinsic_value,
            'extrinsic_value': extrinsic_value,
            'underlying_price': underlying_price
        }
    
    def collect_options_chain(self, symbol: str, strike_count: int = 20) -> Dict[str, Any]:
        """
        Fetch options chain data from Schwab API
        
        Args:
            symbol: Stock symbol to collect options for
            strike_count: Number of strikes to collect per side
            
        Returns:
            Dictionary with options data or error info
        """
        try:
            logger.info(f"🎯 Collecting options chain for {symbol}")
            
            # Call Schwab API (using correct schwabdev method)
            response = self.client.option_chains(
                symbol=symbol,
                strikeCount=strike_count,
                includeUnderlyingQuote=True,
                contractType="ALL"
            )
            
            # Parse the response (schwabdev returns requests.Response object)
            if hasattr(response, 'json'):
                options_data = response.json()
            else:
                options_data = response
            
            if not options_data:
                return {'symbol': symbol, 'status': 'no_data', 'options_data': None}
            
            return {'symbol': symbol, 'status': 'success', 'options_data': options_data}
            
        except Exception as e:
            logger.error(f"❌ Error collecting options for {symbol}: {e}")
            return {'symbol': symbol, 'status': 'error', 'message': str(e), 'options_data': None}
    
    def calculate_flow_metrics(self, symbol: str, options_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate flow metrics from options data
        
        Args:
            symbol: Stock symbol
            options_data: Raw options data from API
            
        Returns:
            Dictionary with calculated metrics
        """
        call_delta_vol, put_delta_vol, call_vol, put_vol, underlying_price, raw_records = self._calculate_option_metrics(symbol, options_data)
        
        # Calculate derived metrics
        net_delta_vol = call_delta_vol - put_delta_vol
        delta_ratio = call_delta_vol / put_delta_vol if put_delta_vol > 0 else float('inf')
        total_volume = call_vol + put_vol
        put_call_ratio = put_vol / call_vol if call_vol > 0 else float('inf')
        
        # Determine sentiment
        sentiment = "Bullish" if net_delta_vol > 0 else "Bearish"
        sentiment_strength = abs(net_delta_vol) / (call_delta_vol + put_delta_vol) if (call_delta_vol + put_delta_vol) > 0 else 0
        
        return {
            'call_delta_volume': call_delta_vol,
            'put_delta_volume': put_delta_vol,
            'net_delta_volume': net_delta_vol,
            'delta_ratio': delta_ratio,
            'call_volume': call_vol,
            'put_volume': put_vol,
            'total_volume': total_volume,
            'put_call_ratio': put_call_ratio,
            'underlying_price': underlying_price,
            'sentiment': sentiment,
            'sentiment_strength': sentiment_strength,
            'total_records': self._count_options_in_data(options_data),
            'raw_records': raw_records
        }
    
    def store_aggregated_data(self, symbol: str, metrics: Dict[str, Any]) -> bool:
        """
        Store aggregated flow metrics to database
        
        Args:
            symbol: Stock symbol
            metrics: Calculated flow metrics
            
        Returns:
            True if successful, False otherwise
        """
        timestamp = int(datetime.now().timestamp() * 1000)
        aggregation = {
            'symbol': symbol,
            'timestamp': timestamp,
            'call_delta_volume': metrics['call_delta_volume'],
            'put_delta_volume': metrics['put_delta_volume'],
            'net_delta_volume': metrics['net_delta_volume'],
            'delta_ratio': metrics['delta_ratio'],
            'call_volume': metrics['call_volume'],
            'put_volume': metrics['put_volume'],
            'total_volume': metrics['total_volume'],
            'call_open_interest': 0,  # Could calculate if needed
            'put_open_interest': 0,   # Could calculate if needed
            'total_open_interest': 0,
            'put_call_ratio': metrics['put_call_ratio'],
            'put_call_oi_ratio': 0,
            'underlying_price': metrics['underlying_price'],
            'sentiment': metrics['sentiment'],
            'sentiment_strength': metrics['sentiment_strength'],
            'total_records': metrics['total_records'],
            'collection_timestamp': timestamp
        }
        
        # Log the aggregation values before storing
        logger.info(f"📊 {symbol} Flow: Call Δ×Vol={metrics['call_delta_volume']:,.0f}, Put Δ×Vol={metrics['put_delta_volume']:,.0f}, Net={metrics['net_delta_volume']:,.0f}, Underlying=${metrics['underlying_price']:.2f}")
        
        success = self.database.insert_flow_aggregation(aggregation)
        
        if success:
            logger.info(f"✅ Stored aggregated flow metrics for {symbol}")
        else:
            logger.error(f"❌ Failed to store aggregated metrics for {symbol}")
        
        return success
    
    def store_raw_data(self, symbol: str, raw_records: List[Dict[str, Any]]) -> int:
        """
        Store raw option records to database
        
        Args:
            symbol: Stock symbol
            raw_records: List of individual option records
            
        Returns:
            Number of records stored
        """
        logger.debug(f"store_raw_data called: store_raw_data_enabled={self.store_raw_data_enabled}, raw_records type={type(raw_records)}, len={len(raw_records) if isinstance(raw_records, list) else 'N/A'}")
        
        if not self.store_raw_data_enabled or not raw_records:
            return 0
        
        records_stored, duplicates = self.database.insert_options_data(raw_records)
        logger.info(f"📊 Stored {records_stored} raw option records for {symbol}")
        return records_stored
    
    def process_symbol(self, symbol: str, strike_count: int = 20) -> Dict[str, Any]:
        """
        Complete processing pipeline for a single symbol
        
        Args:
            symbol: Stock symbol to process
            strike_count: Number of strikes to collect per side
            
        Returns:
            Dictionary with processing results
        """
        # Step 1: Collect options data
        collection_result = self.collect_options_chain(symbol, strike_count)
        if collection_result['status'] != 'success':
            return {
                'symbol': symbol,
                'status': collection_result['status'],
                'message': collection_result.get('message', 'Failed to collect options data'),
                'aggregation_stored': False,
                'raw_records_stored': 0
            }
        
        # Step 2: Calculate flow metrics
        metrics = self.calculate_flow_metrics(symbol, collection_result['options_data'])
        
        # Step 3: Store aggregated data
        aggregation_stored = self.store_aggregated_data(symbol, metrics)
        
        # Step 4: Store raw data if enabled
        raw_records_stored = self.store_raw_data(symbol, metrics['raw_records'])
        
        return {
            'symbol': symbol,
            'status': 'success',
            'aggregation_stored': aggregation_stored,
            'raw_records_stored': raw_records_stored,
            'call_delta_volume': metrics['call_delta_volume'],
            'put_delta_volume': metrics['put_delta_volume'],
            'net_delta_volume': metrics['net_delta_volume'],
            'underlying_price': metrics['underlying_price']
        }
    
    def collect_multiple_symbols(self, symbols: List[str], strike_count: int = 20) -> Dict[str, Any]:
        """
        Process options for multiple symbols with rate limiting
        """
        results = []
        total_aggregations = 0
        total_raw_records = 0
        
        for i, symbol in enumerate(symbols):
            # Check trading hours for this specific symbol
            if not self.is_trading_time(symbol):
                logger.info(f"⏰ Skipping {symbol} - outside trading hours")
                results.append({
                    'symbol': symbol,
                    'status': 'skipped_hours',
                    'aggregation_stored': False,
                    'raw_records_stored': 0
                })
                continue
            
            # Rate limiting between symbols
            if i > 0:
                time.sleep(self.rate_limit_delay)
            
            result = self.process_symbol(symbol, strike_count)
            results.append(result)
            if result.get('aggregation_stored'):
                total_aggregations += 1
            total_raw_records += result.get('raw_records_stored', 0)
        
        return {
            'total_symbols': len(symbols),
            'total_aggregations_stored': total_aggregations,
            'total_raw_records_stored': total_raw_records,
            'is_trading_time': any(self.is_trading_time(s) for s in symbols),
            'results': results
        }
    
