# options_flow_web.py - Web-enabled Options Flow Monitor
import time
import sqlite3
from datetime import datetime, timedelta, timezone
from collections import deque
import pytz
import numpy as np
from typing import Dict, Any, Tuple, Optional
import logging
import threading
import json

# Configure logging
logger = logging.getLogger(__name__)

class OptionsFlowWebMonitor:
    def __init__(self, symbol: str = "SPY", strike_count: int = 20, max_points: int = 100):
        self.symbol = symbol
        self.strike_count = strike_count
        self.max_points = max_points
        
        # Data storage
        self.timestamps = deque(maxlen=max_points)
        self.call_deltas = deque(maxlen=max_points)
        self.put_deltas = deque(maxlen=max_points)
        self.net_deltas = deque(maxlen=max_points)
        self.delta_ratio = deque(maxlen=max_points)
        self.call_volume = deque(maxlen=max_points)
        self.put_volume = deque(maxlen=max_points)
        self.underlying_price = deque(maxlen=max_points)
        
        # Trading hours
        self.ET = pytz.timezone('US/Eastern')
        self.MARKET_OPEN = (9, 30)
        self.MARKET_CLOSE = (16, 0)
        self.EXTENDED_START = (4, 0)
        self.EXTENDED_END = (20, 0)
        
        # Performance tracking
        self.fetch_count = 0
        self.error_count = 0
        self.last_successful_fetch = None
        self.is_running = False
        self.update_interval = 30  # seconds
        
        # External dependencies (to be injected)
        self.schwab_client = None
        self.socketio = None
        self.db_connection_factory = None
        
    def set_dependencies(self, schwab_client, socketio, db_connection_factory):
        """Inject external dependencies"""
        self.schwab_client = schwab_client
        self.socketio = socketio
        self.db_connection_factory = db_connection_factory

    def is_trading_time(self) -> bool:
        """Check if current time is within extended trading hours"""
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

    def get_market_status(self) -> str:
        """Get detailed market status"""
        now_et = datetime.now(self.ET)
        current_time = (now_et.hour, now_et.minute)
        
        if now_et.weekday() >= 5:
            return "Market Closed (Weekend)"
        
        start_minutes = self.EXTENDED_START[0] * 60 + self.EXTENDED_START[1]
        end_minutes = self.EXTENDED_END[0] * 60 + self.EXTENDED_END[1]
        market_open_minutes = self.MARKET_OPEN[0] * 60 + self.MARKET_OPEN[1]
        market_close_minutes = self.MARKET_CLOSE[0] * 60 + self.MARKET_CLOSE[1]
        current_minutes = current_time[0] * 60 + current_time[1]
        
        if current_minutes < start_minutes or current_minutes > end_minutes:
            return "Market Closed"
        elif current_minutes < market_open_minutes:
            return "Pre-Market"
        elif current_minutes <= market_close_minutes:
            return "Regular Hours"
        else:
            return "After Hours"

    def calculate_option_metrics(self, options_data: Dict[str, Any]) -> Tuple[float, float, int, int, float]:
        """Calculate comprehensive option metrics"""
        call_delta_vol = 0.0
        put_delta_vol = 0.0
        call_vol = 0
        put_vol = 0
        underlying = 0.0

        if not options_data:
            return call_delta_vol, put_delta_vol, call_vol, put_vol, underlying

        # Get underlying price
        underlying = options_data.get("underlying", {}).get("mark", 0.0)
        
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
                        put_delta_vol += abs(delta) * volume
                        put_vol += volume

        return call_delta_vol, put_delta_vol, call_vol, put_vol, underlying

    def fetch_data(self) -> Tuple[float, float, int, int, float]:
        """Fetch options data with enhanced error handling"""
        try:
            if not self.schwab_client:
                logger.warning("No Schwab client available for options data")
                return 0.0, 0.0, 0, 0, 0.0
                
            now = datetime.now(timezone.utc)
            from_date = now
            to_date = now + timedelta(days=7)
            
            options_data = self.schwab_client.get_option_chains(
                self.symbol, from_date, to_date, self.strike_count
            )
            
            metrics = self.calculate_option_metrics(options_data)
            self.fetch_count += 1
            self.last_successful_fetch = datetime.now(self.ET)
            
            logger.info(f"Options data fetch #{self.fetch_count} successful for {self.symbol}")
            return metrics
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Options data fetch error #{self.error_count}: {e}")
            
            # Return last known values if available
            if self.call_deltas and self.put_deltas:
                return (self.call_deltas[-1], self.put_deltas[-1], 
                       self.call_volume[-1] if self.call_volume else 0,
                       self.put_volume[-1] if self.put_volume else 0,
                       self.underlying_price[-1] if self.underlying_price else 0.0)
            return 0.0, 0.0, 0, 0, 0.0

    def generate_mock_data(self) -> Tuple[float, float, int, int, float]:
        """Generate realistic mock options data for testing"""
        import random
        
        # Base values
        base_underlying = 420.0
        base_call_vol = 50000
        base_put_vol = 45000
        
        # Add some realistic variation
        underlying = base_underlying + random.uniform(-5, 5)
        call_vol = int(base_call_vol + random.uniform(-10000, 15000))
        put_vol = int(base_put_vol + random.uniform(-8000, 12000))
        
        # Realistic delta values (calls: 0.3-0.7, puts: -0.7 to -0.3)
        avg_call_delta = random.uniform(0.35, 0.65)
        avg_put_delta = random.uniform(0.3, 0.6)  # Using absolute value
        
        call_delta_vol = avg_call_delta * call_vol
        put_delta_vol = avg_put_delta * put_vol
        
        return call_delta_vol, put_delta_vol, call_vol, put_vol, underlying

    def calculate_technical_indicators(self) -> Dict[str, float]:
        """Calculate additional technical indicators"""
        indicators = {}
        
        if len(self.net_deltas) < 2:
            return indicators
        
        # Momentum (rate of change)
        if len(self.net_deltas) >= 5:
            recent_avg = np.mean(list(self.net_deltas)[-3:])
            earlier_avg = np.mean(list(self.net_deltas)[-6:-3])
            indicators['momentum'] = (recent_avg - earlier_avg) / abs(earlier_avg) if earlier_avg != 0 else 0
        
        # Volatility (standard deviation of net delta)
        if len(self.net_deltas) >= 10:
            indicators['volatility'] = np.std(list(self.net_deltas)[-10:])
        
        # Trend strength (correlation with time)
        if len(self.net_deltas) >= 10:
            time_series = np.arange(len(self.net_deltas))
            indicators['trend'] = np.corrcoef(time_series, list(self.net_deltas))[0, 1]
        
        return indicators

    def save_to_database(self, timestamp: int, call_delta_vol: float, put_delta_vol: float, 
                        net_delta: float, ratio: float, call_vol: int, put_vol: int, 
                        underlying: float, market_status: str):
        """Save options flow data to database"""
        try:
            if self.db_connection_factory:
                conn = self.db_connection_factory()
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO options_flow 
                    (symbol, timestamp, call_delta_vol, put_delta_vol, net_delta, 
                     delta_ratio, call_volume, put_volume, underlying_price, market_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (self.symbol, timestamp, call_delta_vol, put_delta_vol, net_delta,
                      ratio, call_vol, put_vol, underlying, market_status))
                
                conn.commit()
                conn.close()
                
        except Exception as e:
            logger.error(f"Database save error: {e}")

    def update_data(self):
        """Update options flow data and emit to clients"""
        try:
            market_status = self.get_market_status()
            
            # Fetch new data
            if self.schwab_client and self.is_trading_time():
                call_delta_vol, put_delta_vol, call_vol, put_vol, underlying = self.fetch_data()
            else:
                # Use mock data if no client or market closed
                call_delta_vol, put_delta_vol, call_vol, put_vol, underlying = self.generate_mock_data()
            
            current_time = datetime.now(self.ET)
            timestamp = int(current_time.timestamp() * 1000)
            
            # Calculate derived metrics
            net_delta = call_delta_vol - put_delta_vol
            ratio = call_delta_vol / put_delta_vol if put_delta_vol != 0 else float('inf')
            
            # Store data
            self.timestamps.append(current_time)
            self.call_deltas.append(call_delta_vol)
            self.put_deltas.append(put_delta_vol)
            self.net_deltas.append(net_delta)
            self.delta_ratio.append(ratio)
            self.call_volume.append(call_vol)
            self.put_volume.append(put_vol)
            self.underlying_price.append(underlying)
            
            # Save to database
            self.save_to_database(timestamp, call_delta_vol, put_delta_vol, net_delta, 
                                ratio, call_vol, put_vol, underlying, market_status)
            
            # Calculate technical indicators
            indicators = self.calculate_technical_indicators()
            
            # Prepare data for web client
            options_data = {
                'symbol': self.symbol,
                'timestamp': current_time.isoformat(),
                'market_status': market_status,
                'underlying_price': underlying,
                'call_delta_vol': call_delta_vol,
                'put_delta_vol': put_delta_vol,
                'net_delta': net_delta,
                'delta_ratio': ratio if ratio != float('inf') else 0,
                'call_volume': call_vol,
                'put_volume': put_vol,
                'sentiment': "Bullish" if net_delta > 0 else "Bearish",
                'sentiment_strength': abs(net_delta) / (call_delta_vol + put_delta_vol) if (call_delta_vol + put_delta_vol) > 0 else 0,
                'indicators': indicators,
                'performance': {
                    'fetch_count': self.fetch_count,
                    'error_count': self.error_count,
                    'success_rate': ((self.fetch_count - self.error_count) / self.fetch_count * 100) if self.fetch_count > 0 else 0
                },
                'historical_data': {
                    'timestamps': [ts.isoformat() for ts in self.timestamps],
                    'call_deltas': list(self.call_deltas),
                    'put_deltas': list(self.put_deltas),
                    'net_deltas': list(self.net_deltas),
                    'call_volume': list(self.call_volume),
                    'put_volume': list(self.put_volume),
                    'underlying_prices': list(self.underlying_price)
                }
            }
            
            # Emit to all connected clients
            if self.socketio:
                self.socketio.emit('options_flow_data', options_data)
            
            logger.info(f"Options flow data updated for {self.symbol}: Net Δ={net_delta:,.0f}, Sentiment={options_data['sentiment']}")
            
        except Exception as e:
            logger.error(f"Options flow update error: {e}")

    def get_current_data(self) -> Dict[str, Any]:
        """Get current options flow data for API endpoints"""
        if not self.timestamps:
            return {}
        
        indicators = self.calculate_technical_indicators()
        
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamps[-1].isoformat(),
            'market_status': self.get_market_status(),
            'underlying_price': self.underlying_price[-1] if self.underlying_price else 0,
            'call_delta_vol': self.call_deltas[-1] if self.call_deltas else 0,
            'put_delta_vol': self.put_deltas[-1] if self.put_deltas else 0,
            'net_delta': self.net_deltas[-1] if self.net_deltas else 0,
            'delta_ratio': self.delta_ratio[-1] if self.delta_ratio else 0,
            'call_volume': self.call_volume[-1] if self.call_volume else 0,
            'put_volume': self.put_volume[-1] if self.put_volume else 0,
            'sentiment': "Bullish" if (self.net_deltas and self.net_deltas[-1] > 0) else "Bearish",
            'indicators': indicators,
            'performance': {
                'fetch_count': self.fetch_count,
                'error_count': self.error_count,
                'success_rate': ((self.fetch_count - self.error_count) / self.fetch_count * 100) if self.fetch_count > 0 else 0
            }
        }

    def get_historical_data(self, limit: int = None) -> Dict[str, Any]:
        """Get historical options flow data"""
        if limit:
            timestamps = list(self.timestamps)[-limit:]
            call_deltas = list(self.call_deltas)[-limit:]
            put_deltas = list(self.put_deltas)[-limit:]
            net_deltas = list(self.net_deltas)[-limit:]
            call_volume = list(self.call_volume)[-limit:]
            put_volume = list(self.put_volume)[-limit:]
            underlying_prices = list(self.underlying_price)[-limit:]
        else:
            timestamps = list(self.timestamps)
            call_deltas = list(self.call_deltas)
            put_deltas = list(self.put_deltas)
            net_deltas = list(self.net_deltas)
            call_volume = list(self.call_volume)
            put_volume = list(self.put_volume)
            underlying_prices = list(self.underlying_price)
        
        return {
            'symbol': self.symbol,
            'data_points': len(timestamps),
            'historical_data': {
                'timestamps': [ts.isoformat() for ts in timestamps],
                'call_deltas': call_deltas,
                'put_deltas': put_deltas,
                'net_deltas': net_deltas,
                'call_volume': call_volume,
                'put_volume': put_volume,
                'underlying_prices': underlying_prices
            }
        }

    def start_monitoring(self, update_interval: int = 30):
        """Start the monitoring loop in a separate thread"""
        self.update_interval = update_interval
        self.is_running = True
        
        def monitoring_loop():
            while self.is_running:
                self.update_data()
                time.sleep(self.update_interval)
        
        monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitor_thread.start()
        logger.info(f"Started options flow monitoring for {self.symbol} with {update_interval}s interval")

    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.is_running = False
        logger.info(f"Stopped options flow monitoring for {self.symbol}")

    def change_symbol(self, new_symbol: str):
        """Change the monitored symbol and reset data"""
        old_symbol = self.symbol
        self.symbol = new_symbol
        
        # Clear historical data
        self.timestamps.clear()
        self.call_deltas.clear()
        self.put_deltas.clear()
        self.net_deltas.clear()
        self.delta_ratio.clear()
        self.call_volume.clear()
        self.put_volume.clear()
        self.underlying_price.clear()
        
        # Reset counters
        self.fetch_count = 0
        self.error_count = 0
        
        logger.info(f"Changed options flow monitoring from {old_symbol} to {new_symbol}")


# Global instances - to be initialized by the main app
options_flow_monitor = None

def get_options_monitor() -> Optional[OptionsFlowWebMonitor]:
    """Get the global options flow monitor instance"""
    return options_flow_monitor

def initialize_options_monitor(symbol: str = "SPY", strike_count: int = 20, 
                             max_points: int = 100) -> OptionsFlowWebMonitor:
    """Initialize the global options flow monitor"""
    global options_flow_monitor
    options_flow_monitor = OptionsFlowWebMonitor(symbol, strike_count, max_points)
    return options_flow_monitor