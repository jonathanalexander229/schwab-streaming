import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from .options_database import OptionsDatabase

logger = logging.getLogger(__name__)

class OptionsFlowCalculator:
    """
    Calculate options flow metrics from stored data, similar to the example script.
    """
    
    def __init__(self, db_path: str = "data/options_data.db"):
        """Initialize with database connection"""
        self.database = OptionsDatabase(db_path)
    
    def calculate_current_flow(self, symbol: str) -> Dict[str, Any]:
        """
        Calculate options flow metrics using most recent data for a symbol
        
        Args:
            symbol: Stock symbol to analyze
            
        Returns:
            Dictionary with flow metrics
        """
        try:
            # Get latest data by finding max timestamp and getting those records
            import sqlite3
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                
                # Get the latest timestamp for this symbol and all records with that timestamp
                cursor.execute("""
                    SELECT * FROM options_data 
                    WHERE symbol = ? AND timestamp = (
                        SELECT MAX(timestamp) FROM options_data WHERE symbol = ?
                    )
                """, (symbol, symbol))
                
                rows = cursor.fetchall()
                if not rows:
                    return self._empty_flow_result(symbol)
                
                # Convert to expected format (matching get_options_data output)
                options_data = []
                for row in rows:
                    options_data.append({
                        'symbol': row[1], 'timestamp': row[2], 'option_type': row[3],
                        'expiration_date': row[4], 'strike_price': row[5], 'mark': row[6],
                        'bid': row[7], 'ask': row[8], 'last': row[9], 'total_volume': row[10],
                        'open_interest': row[11], 'delta': row[12], 'gamma': row[13],
                        'theta': row[14], 'vega': row[15], 'rho': row[16],
                        'implied_volatility': row[17], 'theoretical_value': row[18],
                        'time_to_expiration': row[19], 'intrinsic_value': row[20],
                        'extrinsic_value': row[21], 'underlying_price': row[22]
                    })
                
                latest_timestamp = options_data[0]['timestamp'] if options_data else None
            
            # Calculate flow metrics with collection info
            result = self._calculate_flow_metrics(symbol, options_data, "latest")
            
            # Add collection metadata
            result['collection_timestamp'] = latest_timestamp
            result['collection_time'] = datetime.fromtimestamp(latest_timestamp / 1000).strftime('%H:%M:%S')
            result['unique_records'] = len(options_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating flow for {symbol}: {e}")
            return self._empty_flow_result(symbol)
    
    def calculate_flow_for_timeframe(self, symbol: str, hours_back: int = 1) -> Dict[str, Any]:
        """
        Calculate flow metrics over a longer timeframe
        
        Args:
            symbol: Stock symbol to analyze
            hours_back: Look back this many hours
            
        Returns:
            Dictionary with aggregated flow metrics
        """
        try:
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = end_time - (hours_back * 60 * 60 * 1000)
            
            options_data = self.database.get_options_data(symbol, start_time, end_time)
            
            if not options_data:
                return self._empty_flow_result(symbol)
            
            return self._calculate_flow_metrics(symbol, options_data, timeframe=f"{hours_back}h")
            
        except Exception as e:
            logger.error(f"Error calculating {hours_back}h flow for {symbol}: {e}")
            return self._empty_flow_result(symbol)
    
    def _calculate_flow_metrics(self, symbol: str, options_data: List[Dict[str, Any]], 
                               timeframe: str = "5m") -> Dict[str, Any]:
        """
        Calculate flow metrics from options data (matching example script logic)
        
        Args:
            symbol: Stock symbol
            options_data: List of options records from database
            timeframe: Time period for the calculation
            
        Returns:
            Flow metrics dictionary
        """
        call_delta_volume = 0.0
        put_delta_volume = 0.0
        call_volume = 0
        put_volume = 0
        call_open_interest = 0
        put_open_interest = 0
        underlying_price = 0.0
        total_records = len(options_data)
        
        # Process all options records (similar to example script's calculate_option_metrics)
        for record in options_data:
            delta = record.get('delta', 0.0)
            volume = record.get('total_volume', 0)
            open_interest = record.get('open_interest', 0)
            option_type = record.get('option_type', '')
            
            # Update underlying price (use most recent)
            if record.get('underlying_price'):
                underlying_price = record['underlying_price']
            
            # Process all records for open interest (even if no volume)
            if option_type == 'CALL':
                call_open_interest += open_interest or 0
            elif option_type == 'PUT':
                put_open_interest += open_interest or 0
            
            # Only process records with valid delta and volume for flow calculations
            if delta and volume and volume > 0:
                if option_type == 'CALL':
                    call_delta_volume += delta * volume
                    call_volume += volume
                elif option_type == 'PUT':
                    # Use absolute value of delta for puts (delta is negative for puts)
                    put_delta_volume += abs(delta) * volume
                    put_volume += volume
        
        # Calculate derived metrics (matching example script)
        net_delta_volume = call_delta_volume - put_delta_volume
        delta_ratio = call_delta_volume / put_delta_volume if put_delta_volume > 0 else float('inf')
        total_volume = call_volume + put_volume
        total_open_interest = call_open_interest + put_open_interest
        
        # Calculate Put/Call ratio (standard metric)
        put_call_ratio = put_volume / call_volume if call_volume > 0 else float('inf')
        put_call_oi_ratio = put_open_interest / call_open_interest if call_open_interest > 0 else float('inf')
        
        # Determine sentiment
        sentiment = "Bullish" if net_delta_volume > 0 else "Bearish"
        sentiment_emoji = "🟢" if net_delta_volume > 0 else "🔴"
        
        # Calculate sentiment strength (0-1 scale)
        total_delta_volume = call_delta_volume + put_delta_volume
        sentiment_strength = abs(net_delta_volume) / total_delta_volume if total_delta_volume > 0 else 0
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.now().isoformat(),
            
            # Core metrics (matching example script)
            'call_delta_volume': round(call_delta_volume, 0),
            'put_delta_volume': round(put_delta_volume, 0),
            'net_delta_volume': round(net_delta_volume, 0),
            'delta_ratio': round(delta_ratio, 2),
            
            # Volume metrics
            'call_volume': call_volume,
            'put_volume': put_volume,
            'total_volume': total_volume,
            
            # Open Interest metrics
            'call_open_interest': call_open_interest,
            'put_open_interest': put_open_interest,
            'total_open_interest': total_open_interest,
            'put_call_oi_ratio': round(put_call_oi_ratio, 2),
            
            # Put/Call ratios
            'put_call_ratio': round(put_call_ratio, 2),
            
            # Market context
            'underlying_price': round(underlying_price, 2) if underlying_price else 0,
            
            # Sentiment analysis
            'sentiment': sentiment,
            'sentiment_emoji': sentiment_emoji,
            'sentiment_strength': round(sentiment_strength, 3),
            
            # Metadata
            'total_records': total_records,
            'data_available': total_records > 0
        }
    
    def _empty_flow_result(self, symbol: str) -> Dict[str, Any]:
        """Return empty/default flow result when no data available"""
        return {
            'symbol': symbol,
            'timeframe': '5m',
            'timestamp': datetime.now().isoformat(),
            'call_delta_volume': 0,
            'put_delta_volume': 0,
            'net_delta_volume': 0,
            'delta_ratio': 0,
            'call_volume': 0,
            'put_volume': 0,
            'total_volume': 0,
            'call_open_interest': 0,
            'put_open_interest': 0,
            'total_open_interest': 0,
            'put_call_oi_ratio': 0,
            'put_call_ratio': 0,
            'underlying_price': 0,
            'sentiment': 'No Data',
            'sentiment_emoji': '⚪',
            'sentiment_strength': 0,
            'total_records': 0,
            'data_available': False
        }
    
    def get_multi_symbol_flow(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Calculate flow metrics for multiple symbols using most recent data
        
        Args:
            symbols: List of symbols to analyze
            
        Returns:
            Dictionary with flow data for all symbols
        """
        results = {}
        
        for symbol in symbols:
            results[symbol] = self.calculate_current_flow(symbol)
        
        # Calculate overall market sentiment
        total_net_delta = sum(result['net_delta_volume'] for result in results.values() 
                            if result['data_available'])
        
        overall_sentiment = "Bullish" if total_net_delta > 0 else "Bearish"
        overall_emoji = "🟢" if total_net_delta > 0 else "🔴"
        
        return {
            'symbols': results,
            'overall': {
                'net_delta_volume': round(total_net_delta, 0),
                'sentiment': overall_sentiment,
                'sentiment_emoji': overall_emoji,
                'active_symbols': len([r for r in results.values() if r['data_available']]),
                'total_symbols': len(symbols)
            },
            'timestamp': datetime.now().isoformat()
        }
    
    def calculate_and_store_aggregation(self, symbol: str, timestamp: int) -> bool:
        """
        Calculate flow metrics for the given timestamp and store in aggregation table
        This method bridges raw data storage and aggregated chart data
        
        Args:
            symbol: Stock symbol
            timestamp: Collection timestamp to aggregate
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get all raw options data for this exact timestamp
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM options_data 
                    WHERE symbol = ? AND timestamp = ?
                """, (symbol, timestamp))
                
                rows = cursor.fetchall()
                if not rows:
                    logger.warning(f"No raw data found for {symbol} at timestamp {timestamp}")
                    return False
                
                # Convert to expected format for _calculate_flow_metrics
                options_data = []
                for row in rows:
                    options_data.append({
                        'symbol': row[1], 'timestamp': row[2], 'option_type': row[3],
                        'expiration_date': row[4], 'strike_price': row[5], 'mark': row[6],
                        'bid': row[7], 'ask': row[8], 'last': row[9], 'total_volume': row[10],
                        'open_interest': row[11], 'delta': row[12], 'gamma': row[13],
                        'theta': row[14], 'vega': row[15], 'rho': row[16],
                        'implied_volatility': row[17], 'theoretical_value': row[18],
                        'time_to_expiration': row[19], 'intrinsic_value': row[20],
                        'extrinsic_value': row[21], 'underlying_price': row[22]
                    })
            
            # Calculate flow metrics using existing logic
            flow_metrics = self._calculate_flow_metrics(symbol, options_data, "5m")
            
            # Prepare aggregation record with timestamp from raw data
            agg_data = {
                'symbol': symbol,
                'timestamp': timestamp,  # Use the collection timestamp
                'call_delta_volume': flow_metrics['call_delta_volume'],
                'put_delta_volume': flow_metrics['put_delta_volume'],
                'net_delta_volume': flow_metrics['net_delta_volume'],
                'delta_ratio': flow_metrics['delta_ratio'],
                'call_volume': flow_metrics['call_volume'],
                'put_volume': flow_metrics['put_volume'],
                'total_volume': flow_metrics['total_volume'],
                'call_open_interest': flow_metrics['call_open_interest'],
                'put_open_interest': flow_metrics['put_open_interest'],
                'total_open_interest': flow_metrics['total_open_interest'],
                'put_call_ratio': flow_metrics['put_call_ratio'],
                'put_call_oi_ratio': flow_metrics['put_call_oi_ratio'],
                'underlying_price': flow_metrics['underlying_price'],
                'sentiment': flow_metrics['sentiment'],
                'sentiment_strength': flow_metrics['sentiment_strength'],
                'total_records': flow_metrics['total_records'],
                'collection_timestamp': timestamp
            }
            
            # Store aggregation
            success = self.database.insert_flow_aggregation(agg_data)
            
            if success:
                logger.info(f"✅ Stored flow aggregation for {symbol} at {datetime.fromtimestamp(timestamp/1000).strftime('%H:%M:%S')}")
            else:
                logger.error(f"❌ Failed to store flow aggregation for {symbol}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error calculating/storing aggregation for {symbol}: {e}")
            return False