# mock_data.py - Mock Data Generator and Test Framework for Market Data Streaming

import random
import time
import json
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from enum import Enum
import queue
import unittest
from unittest.mock import Mock, patch, MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MarketState(Enum):
    """Market session states"""
    PRE_MARKET = "pre_market"
    REGULAR_HOURS = "regular_hours"
    AFTER_HOURS = "after_hours"
    CLOSED = "closed"

@dataclass
class MockQuote:
    """Represents a single market quote"""
    symbol: str
    last_price: float
    bid_price: float
    ask_price: float
    volume: int
    high_price: float
    low_price: float
    net_change: float
    net_change_percent: float
    timestamp: int
    
    def to_schwab_format(self) -> Dict[str, Any]:
        """Convert to Schwab API format with correct numeric field codes"""
        return {
            "key": self.symbol,
            "1": self.bid_price,       # Field 1: Bid Price
            "2": self.ask_price,       # Field 2: Ask Price
            "3": self.last_price,      # Field 3: Last Price
            "8": self.volume,          # Field 8: Total Volume
            "10": self.high_price,     # Field 10: High Price
            "11": self.low_price,      # Field 11: Low Price
            "18": self.net_change,     # Field 18: Net Change
            "42": self.net_change_percent  # Field 42: Net Percent Change
        }
    
    def to_app_format(self) -> Dict[str, Any]:
        """Convert to internal app format"""
        return {
            'symbol': self.symbol,
            'last_price': self.last_price,
            'bid_price': self.bid_price,
            'ask_price': self.ask_price,
            'volume': self.volume,
            'high_price': self.high_price,
            'low_price': self.low_price,
            'net_change': self.net_change,
            'net_change_percent': self.net_change_percent,
            'timestamp': self.timestamp
        }

class MockMarketDataGenerator:
    """Generates realistic mock market data"""
    
    # Realistic base prices for common stocks
    BASE_PRICES = {
        'AAPL': 150.00,
        'MSFT': 300.00,
        'GOOGL': 2500.00,
        'AMZN': 3000.00,
        'TSLA': 800.00,
        'NVDA': 400.00,
        'META': 250.00,
        'SPY': 420.00,
        'QQQ': 350.00,
        'IWM': 180.00,
        'DIA': 340.00,
        'VTI': 200.00
    }
    
    def __init__(self):
        self.current_prices = self.BASE_PRICES.copy()
        self.daily_opens = self.BASE_PRICES.copy()
        self.daily_highs = {k: v * 1.02 for k, v in self.BASE_PRICES.items()}
        self.daily_lows = {k: v * 0.98 for k, v in self.BASE_PRICES.items()}
        self.volumes = {symbol: 0 for symbol in self.BASE_PRICES.keys()}
        
        # Market conditions
        self.market_trend = 0.0  # -1.0 (bearish) to 1.0 (bullish)
        self.volatility = 0.5    # 0.0 (calm) to 1.0 (volatile)
        
    def get_market_state(self) -> MarketState:
        """Determine current market state based on time"""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()
        
        # Weekend
        if weekday >= 5:
            return MarketState.CLOSED
        
        # Convert to market time (EST)
        current_minutes = hour * 60 + minute
        
        if current_minutes < 4 * 60:  # Before 4 AM
            return MarketState.CLOSED
        elif current_minutes < 9 * 60 + 30:  # 4 AM - 9:30 AM
            return MarketState.PRE_MARKET
        elif current_minutes <= 16 * 60:  # 9:30 AM - 4:00 PM
            return MarketState.REGULAR_HOURS
        elif current_minutes <= 20 * 60:  # 4:00 PM - 8:00 PM
            return MarketState.AFTER_HOURS
        else:
            return MarketState.CLOSED
    
    def generate_price_movement(self, current_price: float, symbol: str) -> float:
        """Generate realistic price movement"""
        market_state = self.get_market_state()
        
        # Base volatility factors
        volatility_factors = {
            MarketState.PRE_MARKET: 0.3,
            MarketState.REGULAR_HOURS: 1.0,
            MarketState.AFTER_HOURS: 0.5,
            MarketState.CLOSED: 0.1
        }
        
        base_volatility = volatility_factors[market_state]
        
        # Symbol-specific volatility
        if symbol in ['TSLA', 'NVDA']:
            base_volatility *= 1.5  # High volatility stocks
        elif symbol in ['SPY', 'VTI']:
            base_volatility *= 0.7  # Lower volatility ETFs
        
        # Market trend influence
        trend_influence = self.market_trend * 0.001
        
        # Random walk with mean reversion
        price_change_percent = (
            random.gauss(trend_influence, base_volatility * self.volatility * 0.002) +
            random.gauss(0, 0.0005)  # Noise
        )
        
        # Mean reversion (stocks tend to revert to daily open)
        daily_open = self.daily_opens[symbol]
        if current_price > daily_open * 1.05:  # More than 5% above open
            price_change_percent -= 0.0002  # Slight downward pressure
        elif current_price < daily_open * 0.95:  # More than 5% below open
            price_change_percent += 0.0002  # Slight upward pressure
        
        new_price = current_price * (1 + price_change_percent)
        
        # Ensure reasonable bounds
        daily_open = self.daily_opens[symbol]
        max_daily_move = daily_open * 0.15  # 15% max daily move
        new_price = max(daily_open - max_daily_move, 
                       min(daily_open + max_daily_move, new_price))
        
        return round(new_price, 2)
    
    def generate_volume(self, symbol: str) -> int:
        """Generate realistic volume"""
        market_state = self.get_market_state()
        
        # Base volumes per symbol type
        base_volumes = {
            'AAPL': 80000000,
            'MSFT': 30000000,
            'GOOGL': 25000000,
            'AMZN': 35000000,
            'TSLA': 75000000,
            'NVDA': 45000000,
            'META': 20000000,
            'SPY': 60000000,
            'QQQ': 40000000,
            'IWM': 25000000,
            'DIA': 5000000,
            'VTI': 8000000
        }
        
        base_volume = base_volumes.get(symbol, 10000000)
        
        # Market state multipliers
        state_multipliers = {
            MarketState.PRE_MARKET: 0.1,
            MarketState.REGULAR_HOURS: 1.0,
            MarketState.AFTER_HOURS: 0.3,
            MarketState.CLOSED: 0.05
        }
        
        # Simulate intraday volume pattern (higher at open/close)
        hour = datetime.now().hour
        if 9 <= hour <= 10:  # Opening hour
            time_multiplier = 2.0
        elif 15 <= hour <= 16:  # Closing hour
            time_multiplier = 1.8
        elif 11 <= hour <= 14:  # Midday
            time_multiplier = 0.7
        else:
            time_multiplier = 1.0
        
        volume_multiplier = state_multipliers[market_state] * time_multiplier
        
        # Add some randomness
        volume_multiplier *= random.uniform(0.5, 1.5)
        
        daily_volume = int(base_volume * volume_multiplier)
        
        # Accumulate volume throughout the day
        self.volumes[symbol] += max(1000, daily_volume // 200)  # Add incremental volume
        
        return self.volumes[symbol]
    
    def generate_quote(self, symbol: str) -> MockQuote:
        """Generate a complete mock quote for a symbol"""
        if symbol not in self.current_prices:
            # Add new symbol with reasonable price
            base_price = random.uniform(20, 500)
            self.current_prices[symbol] = base_price
            self.daily_opens[symbol] = base_price
            self.daily_highs[symbol] = base_price
            self.daily_lows[symbol] = base_price
            self.volumes[symbol] = 0
        
        # Generate new price
        old_price = self.current_prices[symbol]
        new_price = self.generate_price_movement(old_price, symbol)
        self.current_prices[symbol] = new_price
        
        # Update daily high/low
        self.daily_highs[symbol] = max(self.daily_highs[symbol], new_price)
        self.daily_lows[symbol] = min(self.daily_lows[symbol], new_price)
        
        # Generate bid/ask spread (typically 0.01-0.05% of price)
        spread_percent = random.uniform(0.0001, 0.0005)
        spread = new_price * spread_percent
        
        bid_price = round(new_price - spread/2, 2)
        ask_price = round(new_price + spread/2, 2)
        
        # Calculate changes
        daily_open = self.daily_opens[symbol]
        net_change = round(new_price - daily_open, 2)
        net_change_percent = round((net_change / daily_open) * 100, 2) if daily_open > 0 else 0.0
        
        # Generate volume
        volume = self.generate_volume(symbol)
        
        return MockQuote(
            symbol=symbol,
            last_price=new_price,
            bid_price=bid_price,
            ask_price=ask_price,
            volume=volume,
            high_price=self.daily_highs[symbol],
            low_price=self.daily_lows[symbol],
            net_change=net_change,
            net_change_percent=net_change_percent,
            timestamp=int(time.time() * 1000)
        )
    
    def set_market_conditions(self, trend: float = 0.0, volatility: float = 0.5):
        """Set overall market conditions"""
        self.market_trend = max(-1.0, min(1.0, trend))
        self.volatility = max(0.0, min(1.0, volatility))
    
    def reset_daily_data(self):
        """Reset daily data (call at market open)"""
        self.daily_opens = self.current_prices.copy()
        self.daily_highs = self.current_prices.copy()
        self.daily_lows = self.current_prices.copy()
        self.volumes = {symbol: 0 for symbol in self.current_prices.keys()}

class MockSchwabStreamer:
    """Mock Schwab streamer that generates realistic streaming data"""
    
    def __init__(self):
        self.data_generator = MockMarketDataGenerator()
        self.subscribed_symbols = set()
        self.is_running = False
        self.message_handler = None
        self.update_interval = 1.0  # seconds
        self._thread = None
        self._stop_event = threading.Event()
        
    def start(self, message_handler: Callable[[str], None]):
        """Start the mock streamer"""
        self.message_handler = message_handler
        self.is_running = True
        self._stop_event.clear()
        
        self._thread = threading.Thread(target=self._streaming_loop, daemon=True)
        self._thread.start()
        
        logger.info("Mock Schwab streamer started")
    
    def stop(self):
        """Stop the mock streamer"""
        self.is_running = False
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        
        logger.info("Mock Schwab streamer stopped")
    
    def send(self, subscription_message: str):
        """Process subscription message (mock)"""
        # Parse subscription to extract symbols (simplified)
        if "LEVELONE_EQUITIES" in subscription_message:
            # Extract symbol from subscription message
            # This is a simplified parser - real implementation would be more robust
            try:
                import re
                symbols = re.findall(r'"keys":"([^"]+)"', subscription_message)
                for symbol_list in symbols:
                    for symbol in symbol_list.split(','):
                        if symbol.strip():
                            self.subscribed_symbols.add(symbol.strip())
                            logger.info(f"Mock: Subscribed to {symbol.strip()}")
            except Exception as e:
                logger.warning(f"Could not parse subscription: {e}")
    
    def level_one_equities(self, symbol: str, fields: str) -> str:
        """Generate subscription message (mock)"""
        return f'{{"service":"LEVELONE_EQUITIES","command":"SUBS","requestid":"1","keys":"{symbol}","fields":"{fields}"}}'
    
    def _streaming_loop(self):
        """Main streaming loop"""
        while self.is_running and not self._stop_event.is_set():
            try:
                if self.subscribed_symbols and self.message_handler:
                    # Generate updates for random subset of subscribed symbols
                    symbols_to_update = random.sample(
                        list(self.subscribed_symbols), 
                        min(3, len(self.subscribed_symbols))
                    )
                    
                    for symbol in symbols_to_update:
                        quote = self.data_generator.generate_quote(symbol)
                        message = self._create_schwab_message(quote)
                        self.message_handler(message)
                
                # Wait for next update
                self._stop_event.wait(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in mock streaming loop: {e}")
                self._stop_event.wait(1.0)
    
    def _create_schwab_message(self, quote: MockQuote) -> str:
        """Create a realistic Schwab WebSocket message"""
        message = {
            "data": [{
                "service": "LEVELONE_EQUITIES",
                "timestamp": quote.timestamp,
                "content": [quote.to_schwab_format()]
            }]
        }
        return json.dumps(message)
    
    def add_symbol(self, symbol: str):
        """Add a symbol to streaming"""
        self.subscribed_symbols.add(symbol.upper())
        logger.info(f"Added {symbol} to mock streaming")
    
    def remove_symbol(self, symbol: str):
        """Remove a symbol from streaming"""
        self.subscribed_symbols.discard(symbol.upper())
        logger.info(f"Removed {symbol} from mock streaming")
    
    def set_update_interval(self, interval: float):
        """Set the update interval in seconds"""
        self.update_interval = max(0.1, interval)
    
    def simulate_market_event(self, event_type: str, symbols: List[str] = None):
        """Simulate market events for testing"""
        symbols = symbols or list(self.subscribed_symbols)
        
        if event_type == "bullish_surge":
            self.data_generator.set_market_conditions(trend=0.8, volatility=0.7)
            logger.info("Simulating bullish surge")
        
        elif event_type == "bearish_crash":
            self.data_generator.set_market_conditions(trend=-0.8, volatility=0.9)
            logger.info("Simulating bearish crash")
        
        elif event_type == "high_volatility":
            self.data_generator.set_market_conditions(volatility=0.9)
            logger.info("Simulating high volatility")
        
        elif event_type == "low_volatility":
            self.data_generator.set_market_conditions(volatility=0.2)
            logger.info("Simulating low volatility")
        
        elif event_type == "market_open":
            self.data_generator.reset_daily_data()
            self.set_update_interval(0.5)  # More frequent updates at open
            logger.info("Simulating market open")
        
        elif event_type == "market_close":
            self.set_update_interval(2.0)  # Less frequent updates after close
            logger.info("Simulating market close")

class MockSchwabClient:
    """Mock Schwab client for testing"""
    
    def __init__(self):
        self.stream = MockSchwabStreamer()
        self.authenticated = True
    
    def get_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """Get mock quotes for symbols"""
        quotes = {}
        for symbol in symbols:
            quote = self.stream.data_generator.generate_quote(symbol)
            quotes[symbol] = quote.to_app_format()
        return quotes

# Test Framework
class MarketDataStreamingTests(unittest.TestCase):
    """Test framework for market data streaming"""
    
    def setUp(self):
        """Set up test environment"""
        self.mock_client = MockSchwabClient()
        self.mock_streamer = self.mock_client.stream
        self.received_messages = []
        
    def tearDown(self):
        """Clean up after tests"""
        if self.mock_streamer.is_running:
            self.mock_streamer.stop()
    
    def message_collector(self, message: str):
        """Collect messages for testing"""
        self.received_messages.append(message)
    
    def test_mock_data_generation(self):
        """Test mock data generation"""
        generator = MockMarketDataGenerator()
        
        # Test quote generation
        quote = generator.generate_quote('AAPL')
        self.assertEqual(quote.symbol, 'AAPL')
        self.assertGreater(quote.last_price, 0)
        self.assertGreater(quote.bid_price, 0)
        self.assertGreater(quote.ask_price, 0)
        self.assertGreaterEqual(quote.volume, 0)
        
        # Test bid/ask spread
        self.assertLess(quote.bid_price, quote.ask_price)
        
        # Test price bounds
        self.assertGreater(quote.last_price, quote.low_price)
        self.assertLess(quote.last_price, quote.high_price)
    
    def test_streaming_functionality(self):
        """Test streaming functionality"""
        self.mock_streamer.start(self.message_collector)
        self.mock_streamer.add_symbol('AAPL')
        
        # Wait for some messages
        time.sleep(3)
        self.mock_streamer.stop()
        
        # Verify messages received
        self.assertGreater(len(self.received_messages), 0)
        
        # Verify message format
        message = json.loads(self.received_messages[0])
        self.assertIn('data', message)
        self.assertEqual(message['data'][0]['service'], 'LEVELONE_EQUITIES')
    
    def test_subscription_management(self):
        """Test symbol subscription management"""
        self.mock_streamer.add_symbol('AAPL')
        self.mock_streamer.add_symbol('MSFT')
        
        self.assertIn('AAPL', self.mock_streamer.subscribed_symbols)
        self.assertIn('MSFT', self.mock_streamer.subscribed_symbols)
        
        self.mock_streamer.remove_symbol('AAPL')
        self.assertNotIn('AAPL', self.mock_streamer.subscribed_symbols)
        self.assertIn('MSFT', self.mock_streamer.subscribed_symbols)
    
    def test_market_events(self):
        """Test market event simulation"""
        generator = MockMarketDataGenerator()
        
        # Test bullish conditions
        generator.set_market_conditions(trend=0.8, volatility=0.3)
        quotes = [generator.generate_quote('SPY') for _ in range(10)]
        
        # Should generally trend upward (not guaranteed but likely)
        price_changes = [q.net_change for q in quotes]
        avg_change = sum(price_changes) / len(price_changes)
        
        # Test that market conditions are applied
        self.assertEqual(generator.market_trend, 0.8)
        self.assertEqual(generator.volatility, 0.3)
    
    def test_message_format_conversion(self):
        """Test message format conversions"""
        quote = MockQuote(
            symbol='TEST',
            last_price=100.0,
            bid_price=99.95,
            ask_price=100.05,
            volume=1000000,
            high_price=101.0,
            low_price=99.0,
            net_change=1.0,
            net_change_percent=1.0,
            timestamp=1234567890
        )
        
        # Test Schwab format
        schwab_format = quote.to_schwab_format()
        self.assertEqual(schwab_format['key'], 'TEST')
        self.assertEqual(schwab_format['1'], 99.95)  # Bid price
        self.assertEqual(schwab_format['2'], 100.05)  # Ask price
        self.assertEqual(schwab_format['3'], 100.0)  # Last price
        
        # Test app format
        app_format = quote.to_app_format()
        self.assertEqual(app_format['symbol'], 'TEST')
        self.assertEqual(app_format['last_price'], 100.0)
    
    def test_performance(self):
        """Test performance of mock data generation"""
        generator = MockMarketDataGenerator()
        
        start_time = time.time()
        for _ in range(1000):
            generator.generate_quote('AAPL')
        end_time = time.time()
        
        # Should generate 1000 quotes in less than 1 second
        self.assertLess(end_time - start_time, 1.0)

def run_integration_test():
    """Run an integration test with mock streaming"""
    print("Starting integration test...")
    
    # Create mock components
    mock_client = MockSchwabClient()
    mock_streamer = mock_client.stream
    
    received_data = []
    
    def test_handler(message: str):
        """Test message handler"""
        try:
            data = json.loads(message)
            received_data.append(data)
            print(f"Received: {data['data'][0]['content'][0]['key']} @ ${data['data'][0]['content'][0]['3']}")
        except Exception as e:
            print(f"Error processing message: {e}")
    
    # Start streaming
    mock_streamer.start(test_handler)
    
    # Add some symbols
    test_symbols = ['AAPL', 'MSFT', 'GOOGL', 'SPY']
    for symbol in test_symbols:
        mock_streamer.add_symbol(symbol)
    
    print(f"Subscribed to: {test_symbols}")
    print("Streaming for 10 seconds...")
    
    # Stream for 10 seconds
    time.sleep(10)
    
    # Simulate market event
    print("Simulating bullish surge...")
    mock_streamer.simulate_market_event('bullish_surge')
    time.sleep(5)
    
    # Stop streaming
    mock_streamer.stop()
    
    print(f"Test complete! Received {len(received_data)} messages")
    return len(received_data) > 0

if __name__ == "__main__":
    # Run tests
    print("Running unit tests...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    print("\n" + "="*50)
    print("Running integration test...")
    success = run_integration_test()
    print(f"Integration test {'PASSED' if success else 'FAILED'}")
