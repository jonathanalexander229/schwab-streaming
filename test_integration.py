# test_integration.py - Complete Integration Test Suite

import sys
import os
import time
import json
import requests
import threading
import unittest
from unittest.mock import patch, MagicMock
import socketio as client_socketio

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mock_data import MockSchwabClient, MockSchwabStreamer, MarketDataStreamingTests

class FlaskAppTester:
    """Integration tester for the Flask market data app"""
    
    def __init__(self):
        self.mock_client = MockSchwabClient()
        self.test_results = []
        
    def test_mock_data_quality(self):
        """Test the quality and realism of mock data"""
        print("Testing mock data quality...")
        
        streamer = self.mock_client.stream
        generator = streamer.data_generator
        
        test_symbols = ['AAPL', 'MSFT', 'SPY']
        results = {}
        
        for symbol in test_symbols:
            quotes = []
            
            # Generate 20 quotes to test consistency
            for _ in range(20):
                quote = generator.generate_quote(symbol)
                quotes.append(quote)
                time.sleep(0.01)  # Small delay to simulate time
            
            # Analyze the quotes
            prices = [q.last_price for q in quotes]
            volumes = [q.volume for q in quotes]
            spreads = [q.ask_price - q.bid_price for q in quotes]
            
            results[symbol] = {
                'price_range': (min(prices), max(prices)),
                'price_volatility': max(prices) - min(prices),
                'avg_volume': sum(volumes) / len(volumes),
                'avg_spread': sum(spreads) / len(spreads),
                'valid_quotes': len([q for q in quotes if q.bid_price < q.ask_price]),
                'total_quotes': len(quotes)
            }
            
            # Check data quality
            quality_checks = [
                all(q.bid_price < q.ask_price for q in quotes),  # Bid < Ask
                all(q.low_price <= q.last_price <= q.high_price for q in quotes),  # Price bounds
                all(q.volume >= 0 for q in quotes),  # Positive volume
                results[symbol]['price_volatility'] < results[symbol]['price_range'][1] * 0.2  # Reasonable volatility
            ]
            
            results[symbol]['quality_score'] = sum(quality_checks) / len(quality_checks)
            
            print(f"  ✓ {symbol}: Quality score {results[symbol]['quality_score']:.2f}")
        
        overall_quality = sum(r['quality_score'] for r in results.values()) / len(results)
        return {'success': overall_quality > 0.8, 'results': results, 'overall_quality': overall_quality}
    
    def test_performance(self):
        """Test performance of mock data generation"""
        print("Testing performance...")
        
        streamer = self.mock_client.stream
        
        # Test data generation speed
        start_time = time.time()
        
        for _ in range(100):
            quote = streamer.data_generator.generate_quote('AAPL')
        
        generation_time = time.time() - start_time
        generation_speed = 100 / generation_time
        
        # Test streaming performance
        received_count = 0
        
        def count_messages(message):
            nonlocal received_count
            received_count += 1
        
        streamer.start(count_messages)
        streamer.add_symbol('AAPL')
        streamer.add_symbol('MSFT')
        streamer.set_update_interval(0.1)  # Fast updates
        
        start_time = time.time()
        time.sleep(3)  # Stream for 3 seconds
        streaming_time = time.time() - start_time
        
        streamer.stop()
        
        streaming_rate = received_count / streaming_time
        
        results = {
            'generation_speed': generation_speed,
            'streaming_rate': streaming_rate,
            'success': generation_speed > 200 and streaming_rate > 3  # Performance thresholds
        }
        
        print(f"  ✓ Generation speed: {results['generation_speed']:.1f} quotes/sec")
        print(f"  ✓ Streaming rate: {results['streaming_rate']:.1f} messages/sec")
        
        return results
    
    def run_quick_test(self):
        """Run quick mock data validation"""
        print("="*60)
        print("QUICK MOCK DATA VALIDATION")
        print("="*60)
        
        # Test 1: Mock data quality
        quality_results = self.test_mock_data_quality()
        if not quality_results['success']:
            print("  ✗ Mock data quality insufficient")
            return False
        else:
            print(f"  ✓ Mock data quality: {quality_results['overall_quality']:.2f}")
        
        # Test 2: Performance
        perf_results = self.test_performance()
        if not perf_results['success']:
            print("  ⚠ Performance below optimal")
        else:
            print("  ✓ Performance acceptable")
        
        # Test 3: Unit tests
        print("\n3. Running unit tests...")
        try:
            # Run the unit tests from mock_data.py
            suite = unittest.TestLoader().loadTestsFromTestCase(MarketDataStreamingTests)
            runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
            result = runner.run(suite)
            
            if result.wasSuccessful():
                print(f"  ✓ Unit tests passed ({result.testsRun} tests)")
            else:
                print(f"  ✗ Unit tests failed ({len(result.failures + result.errors)} failures)")
                return False
        except Exception as e:
            print(f"  ✗ Unit test error: {e}")
            return False
        
        print("\n" + "="*60)
        print("✅ QUICK TEST PASSED - Mock framework is working!")
        print("="*60)
        return True
    
    def create_simple_test_script(self):
        """Create a simple standalone test script"""
        test_script = '''# simple_test.py - Simple test script for mock data

from mock_data import MockSchwabClient, MockSchwabStreamer
import time
import json

def simple_streaming_test():
    print("Simple Mock Streaming Test")
    print("-" * 30)
    
    # Create mock client
    client = MockSchwabClient()
    streamer = client.stream
    
    # Message handler
    def handle_message(message):
        data = json.loads(message)
        content = data['data'][0]['content'][0]
        symbol = content['key']
        price = content['3']  # Last price
        print(f"{symbol}: ${price}")
    
    # Start streaming
    streamer.start(handle_message)
    streamer.add_symbol('AAPL')
    streamer.add_symbol('MSFT')
    
    print("Streaming for 10 seconds...")
    time.sleep(10)
    
    # Test market event
    print("\\nSimulating market surge...")
    streamer.simulate_market_event('bullish_surge')
    time.sleep(5)
    
    streamer.stop()
    print("Test complete!")

if __name__ == "__main__":
    simple_streaming_test()
'''
        
        with open('simple_test.py', 'w') as f:
            f.write(test_script)
        
        print("Created simple_test.py")
        print("Run with: python simple_test.py")

def main():
    """Main test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Market Data Streaming Test Suite')
    parser.add_argument('--simple', action='store_true', help='Create simple test script')
    parser.add_argument('--quick', action='store_true', help='Run quick mock data test only')
    parser.add_argument('--full', action='store_true', help='Run full integration test suite')
    
    args = parser.parse_args()
    
    if args.simple:
        tester = FlaskAppTester()
        tester.create_simple_test_script()
        return
    
    tester = FlaskAppTester()
    
    if args.quick:
        success = tester.run_quick_test()
        exit_code = 0 if success else 1
        exit(exit_code)
    
    elif args.full:
        print("="*60)
        print("FULL INTEGRATION TEST SUITE")
        print("="*60)
        print("Note: Full Flask app testing requires the app to be properly set up.")
        print("This test only validates the mock data framework.")
        print("For complete Flask testing, ensure all files are updated per README.")
        print("="*60)
        
        success = tester.run_quick_test()
        exit_code = 0 if success else 1
        exit(exit_code)
    
    else:
        # Default help
        parser.print_help()

if __name__ == "__main__":
    main()
