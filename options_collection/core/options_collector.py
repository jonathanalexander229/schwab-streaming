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
    
    def __init__(self, schwab_client, db_path: str = "data/options_data.db", rate_limit_delay: float = 0.6):
        """
        Initialize the options collector
        
        Args:
            schwab_client: Authenticated Schwab client
            db_path: Path to options database
            rate_limit_delay: Delay between API calls in seconds
        """
        self.client = schwab_client
        self.database = OptionsDatabase(db_path)
        self.rate_limit_delay = rate_limit_delay
        
        # Market hours setup (like the example)
        self.ET = pytz.timezone('US/Eastern')
        self.MARKET_OPEN = (9, 30)
        self.MARKET_CLOSE = (16, 0)
        self.EXTENDED_START = (4, 0)
        self.EXTENDED_END = (20, 0)
        
        logger.info(f"📊 Options collector initialized with {rate_limit_delay}s rate limit")
    
    def is_trading_time(self) -> bool:
        """Simple market hours check like the example"""
        now_et = datetime.now(self.ET)
        current_time = (now_et.hour, now_et.minute)
        
        # Weekend check
        if now_et.weekday() >= 5:
            return False
        
        # Extended hours check
        start_minutes = self.EXTENDED_START[0] * 60 + self.EXTENDED_START[1]
        end_minutes = self.EXTENDED_END[0] * 60 + self.EXTENDED_END[1]
        current_minutes = current_time[0] * 60 + current_time[1]
        
        return start_minutes <= current_minutes <= end_minutes
    
    def collect_options_chain(self, symbol: str, strike_count: int = 20) -> Dict[str, Any]:
        """
        Collect options chain data for a single symbol
        
        Args:
            symbol: Stock symbol to collect options for
            strike_count: Number of strikes to collect per side
            
        Returns:
            Dictionary with collection results
        """
        try:
            # Calculate date range (current to 7 days out)
            now = datetime.now(timezone.utc)
            from_date = now
            to_date = now + timedelta(days=7)
            
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
                return {'symbol': symbol, 'status': 'no_data', 'records_inserted': 0}
            
            # Process and store the data
            records = self._process_options_data(symbol, options_data)
            inserted, duplicates = self.database.insert_options_data(records)
            
            return {
                'symbol': symbol,
                'status': 'success',
                'records_inserted': inserted,
                'duplicates': duplicates,
                'total_records': len(records)
            }
            
        except Exception as e:
            logger.error(f"❌ Error collecting options for {symbol}: {e}")
            return {'symbol': symbol, 'status': 'error', 'message': str(e), 'records_inserted': 0}
    
    def collect_multiple_symbols(self, symbols: List[str], strike_count: int = 20) -> Dict[str, Any]:
        """
        Collect options for multiple symbols with rate limiting (like the example)
        """
        results = []
        total_inserted = 0
        
        for i, symbol in enumerate(symbols):
            # Rate limiting between symbols
            if i > 0:
                time.sleep(self.rate_limit_delay)
            
            result = self.collect_options_chain(symbol, strike_count)
            results.append(result)
            total_inserted += result.get('records_inserted', 0)
        
        return {
            'total_symbols': len(symbols),
            'total_records_inserted': total_inserted,
            'is_trading_time': self.is_trading_time(),
            'results': results
        }
    
    def _process_options_data(self, symbol: str, options_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert API response to database records
        """
        records = []
        timestamp = int(datetime.now().timestamp() * 1000)
        underlying_price = options_data.get("underlying", {}).get("mark", 0.0)
        
        # Process calls
        for expiry in options_data.get("callExpDateMap", {}):
            for strike_price in options_data["callExpDateMap"][expiry]:
                for option in options_data["callExpDateMap"][expiry][strike_price]:
                    record = self._create_record(symbol, timestamp, "CALL", expiry, 
                                               float(strike_price), option, underlying_price)
                    records.append(record)
        
        # Process puts  
        for expiry in options_data.get("putExpDateMap", {}):
            for strike_price in options_data["putExpDateMap"][expiry]:
                for option in options_data["putExpDateMap"][expiry][strike_price]:
                    record = self._create_record(symbol, timestamp, "PUT", expiry, 
                                               float(strike_price), option, underlying_price)
                    records.append(record)
        
        logger.info(f"📊 Processed {len(records)} options records for {symbol}")
        return records
    
    def _create_record(self, symbol: str, timestamp: int, option_type: str, 
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