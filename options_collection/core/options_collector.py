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
    
    def _calculate_option_metrics(self, options_data: Dict[str, Any]) -> tuple[float, float, int, int, float]:
        """
        Calculate comprehensive option metrics (matching example script logic)
        Returns: (call_delta_vol, put_delta_vol, call_vol, put_vol, underlying_price)
        """
        call_delta_vol = 0.0
        put_delta_vol = 0.0
        call_vol = 0
        put_vol = 0
        underlying_price = 0.0

        if not options_data:
            return call_delta_vol, put_delta_vol, call_vol, put_vol, underlying_price

        # Get underlying price
        underlying_price = options_data.get("underlying", {}).get("mark", 0.0)
        
        # Process calls
        for expiry in options_data.get("callExpDateMap", {}):
            for strike in options_data["callExpDateMap"][expiry]:
                for option in options_data["callExpDateMap"][expiry][strike]:
                    delta = option.get("delta", 0.0)
                    volume = option.get("totalVolume", 0)
                    if volume > 0:
                        call_delta_vol += delta * volume
                        call_vol += volume

        # Process puts (delta is negative, so we take absolute value for put_delta_vol)
        for expiry in options_data.get("putExpDateMap", {}):
            for strike in options_data["putExpDateMap"][expiry]:
                for option in options_data["putExpDateMap"][expiry][strike]:
                    delta = option.get("delta", 0.0)
                    volume = option.get("totalVolume", 0)
                    if volume > 0:
                        put_delta_vol += abs(delta) * volume  # Use absolute value
                        put_vol += volume

        return call_delta_vol, put_delta_vol, call_vol, put_vol, underlying_price
    
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
    
    def collect_options_chain(self, symbol: str, strike_count: int = 20) -> Dict[str, Any]:
        """
        Streamlined options collection - calculate metrics on-the-fly like example script
        
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
                return {'symbol': symbol, 'status': 'no_data', 'aggregation_stored': False}
            
            # Calculate metrics immediately (like example script)
            call_delta_vol, put_delta_vol, call_vol, put_vol, underlying_price = self._calculate_option_metrics(options_data)
            
            # Calculate derived metrics
            net_delta_vol = call_delta_vol - put_delta_vol
            delta_ratio = call_delta_vol / put_delta_vol if put_delta_vol > 0 else float('inf')
            total_volume = call_vol + put_vol
            put_call_ratio = put_vol / call_vol if call_vol > 0 else float('inf')
            
            # Determine sentiment
            sentiment = "Bullish" if net_delta_vol > 0 else "Bearish"
            sentiment_strength = abs(net_delta_vol) / (call_delta_vol + put_delta_vol) if (call_delta_vol + put_delta_vol) > 0 else 0
            
            # Store only aggregated metrics (no raw data)
            timestamp = int(datetime.now().timestamp() * 1000)
            aggregation = {
                'symbol': symbol,
                'timestamp': timestamp,
                'call_delta_volume': call_delta_vol,
                'put_delta_volume': put_delta_vol,
                'net_delta_volume': net_delta_vol,
                'delta_ratio': delta_ratio,
                'call_volume': call_vol,
                'put_volume': put_vol,
                'total_volume': total_volume,
                'call_open_interest': 0,  # Could calculate if needed
                'put_open_interest': 0,   # Could calculate if needed
                'total_open_interest': 0,
                'put_call_ratio': put_call_ratio,
                'put_call_oi_ratio': 0,
                'underlying_price': underlying_price,
                'sentiment': sentiment,
                'sentiment_strength': sentiment_strength,
                'total_records': self._count_options_in_data(options_data),
                'collection_timestamp': timestamp
            }
            
            # Log the aggregation values before storing
            logger.info(f"📊 {symbol} Flow: Call Δ×Vol={call_delta_vol:,.0f}, Put Δ×Vol={put_delta_vol:,.0f}, Net={net_delta_vol:,.0f}, Underlying=${underlying_price:.2f}")
            
            aggregation_stored = self.database.insert_flow_aggregation(aggregation)
            
            if aggregation_stored:
                logger.info(f"✅ Stored aggregated flow metrics for {symbol}")
            else:
                logger.error(f"❌ Failed to store aggregated metrics for {symbol}")
            
            return {
                'symbol': symbol,
                'status': 'success',
                'aggregation_stored': aggregation_stored,
                'call_delta_volume': call_delta_vol,
                'put_delta_volume': put_delta_vol,
                'net_delta_volume': net_delta_vol,
                'underlying_price': underlying_price
            }
            
        except Exception as e:
            logger.error(f"❌ Error collecting options for {symbol}: {e}")
            return {'symbol': symbol, 'status': 'error', 'message': str(e), 'aggregation_stored': False}
    
    def collect_multiple_symbols(self, symbols: List[str], strike_count: int = 20) -> Dict[str, Any]:
        """
        Collect options for multiple symbols with rate limiting (streamlined approach)
        """
        results = []
        total_aggregations = 0
        
        for i, symbol in enumerate(symbols):
            # Check trading hours for this specific symbol
            if not self.is_trading_time(symbol):
                logger.info(f"⏰ Skipping {symbol} - outside trading hours")
                results.append({
                    'symbol': symbol,
                    'status': 'skipped_hours',
                    'aggregation_stored': False
                })
                continue
            
            # Rate limiting between symbols
            if i > 0:
                time.sleep(self.rate_limit_delay)
            
            result = self.collect_options_chain(symbol, strike_count)
            results.append(result)
            if result.get('aggregation_stored'):
                total_aggregations += 1
        
        return {
            'total_symbols': len(symbols),
            'total_aggregations_stored': total_aggregations,
            'is_trading_time': any(self.is_trading_time(s) for s in symbols),
            'results': results
        }
    
