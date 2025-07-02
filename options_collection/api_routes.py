from flask import Blueprint, jsonify, request
import json
import os
import logging
from datetime import datetime
from auth import require_auth
from .core.flow_calculator import OptionsFlowCalculator

logger = logging.getLogger(__name__)

# Create blueprint for options routes
options_bp = Blueprint('options', __name__, url_prefix='/api/options')

def load_watchlist_symbols(watchlist_path: str = 'watchlist.json') -> list:
    """Load symbols from watchlist file"""
    try:
        with open(watchlist_path, 'r') as f:
            watchlist_data = json.load(f)
            return watchlist_data.get('symbols', [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

@options_bp.route('/flow/<symbol>')
@require_auth
def get_symbol_flow(symbol):
    """Get options flow data for a specific symbol"""
    try:
        symbol = symbol.upper()
        
        calculator = OptionsFlowCalculator()
        flow_data = calculator.calculate_current_flow(symbol)
        
        return jsonify(flow_data)
        
    except Exception as e:
        logger.error(f"Error getting flow for {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@options_bp.route('/flow')
@require_auth
def get_watchlist_flow():
    """Get options flow data for all watchlist symbols"""
    try:
        # Load watchlist symbols
        symbols = load_watchlist_symbols()
        if not symbols:
            return jsonify({'error': 'No symbols found in watchlist'}), 404
        
        calculator = OptionsFlowCalculator()
        flow_data = calculator.get_multi_symbol_flow(symbols)
        
        return jsonify(flow_data)
        
    except Exception as e:
        logger.error(f"Error getting watchlist flow: {e}")
        return jsonify({'error': str(e)}), 500

@options_bp.route('/flow/<symbol>/history')
@require_auth
def get_symbol_flow_history(symbol):
    """Get longer-term flow data for a symbol"""
    try:
        symbol = symbol.upper()
        hours_back = request.args.get('hours', 1, type=int)
        
        calculator = OptionsFlowCalculator()
        flow_data = calculator.calculate_flow_for_timeframe(symbol, hours_back)
        
        return jsonify(flow_data)
        
    except Exception as e:
        logger.error(f"Error getting flow history for {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@options_bp.route('/chart/<symbol>')
@require_auth
def get_chart_data(symbol):
    """Get call/put premium data for charting"""
    try:
        symbol = symbol.upper()
        
        # Use direct SQL aggregation instead of loading all data
        import sqlite3
        
        db_path = 'data/options_data.db'
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Get raw data including delta, volume, and underlying price for flow calculation
            query = """
            SELECT timestamp, option_type, delta, total_volume, underlying_price
            FROM options_data 
            WHERE symbol = ? AND total_volume > 0 AND delta IS NOT NULL
            ORDER BY timestamp
            """
            
            results = cursor.execute(query, (symbol,)).fetchall()
        
        if not results:
            return jsonify({
                'symbol': symbol,
                'calls': [],
                'puts': [],
                'underlying': []
            })
        
        # Group by 5-minute buckets in Python
        from collections import defaultdict
        buckets = defaultdict(lambda: {'CALL': 0, 'PUT': 0, 'underlying_prices': []})
        
        for row in results:
            timestamp_ms, option_type, delta, total_volume, underlying_price = row
            # Convert to datetime and round to 5-minute bucket
            dt = datetime.fromtimestamp(timestamp_ms / 1000)
            # Round to 5-minute intervals
            minutes = (dt.minute // 5) * 5
            bucket_time = dt.replace(minute=minutes, second=0, microsecond=0)
            bucket_timestamp = int(bucket_time.timestamp())
            
            # Calculate delta × volume (flow metric like the reference)
            if option_type == 'CALL':
                delta_volume = delta * total_volume
            else:  # PUT
                delta_volume = abs(delta) * total_volume  # Use absolute value for puts
            
            buckets[bucket_timestamp][option_type] += delta_volume
            
            # Collect underlying prices for this bucket
            if underlying_price and underlying_price > 0:
                buckets[bucket_timestamp]['underlying_prices'].append(underlying_price)
        
        # Calculate cumulative net flow from baseline
        sorted_timestamps = sorted(buckets.keys())
        
        # Set baseline as first time period
        baseline_calls = buckets[sorted_timestamps[0]]['CALL'] if sorted_timestamps else 0
        baseline_puts = buckets[sorted_timestamps[0]]['PUT'] if sorted_timestamps else 0
        
        calls_data = []
        puts_data = []
        underlying_data = []
        
        for timestamp in sorted_timestamps:
            current_calls = buckets[timestamp]['CALL']
            current_puts = buckets[timestamp]['PUT']
            
            # Calculate cumulative change from baseline
            cumulative_call_change = current_calls - baseline_calls
            cumulative_put_change = current_puts - baseline_puts
            
            calls_data.append({
                'time': timestamp,
                'value': float(cumulative_call_change)
            })
            
            puts_data.append({
                'time': timestamp,
                'value': float(cumulative_put_change)
            })
            
            # Add underlying price (average for this bucket)
            underlying_prices = buckets[timestamp]['underlying_prices']
            if underlying_prices:
                avg_price = sum(underlying_prices) / len(underlying_prices)
                underlying_data.append({
                    'time': timestamp,
                    'value': float(avg_price)
                })
        
        return jsonify({
            'symbol': symbol,
            'calls': calls_data,
            'puts': puts_data,
            'underlying': underlying_data
        })
        
    except Exception as e:
        logger.error(f"Error getting chart data for {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@options_bp.route('/chart-agg/<symbol>')
@require_auth
def get_aggregated_chart_data(symbol):
    """Get pre-aggregated flow data for fast chart display"""
    try:
        symbol = symbol.upper()
        
        # Get query parameters
        hours_back = request.args.get('hours', 24, type=int)  # Default 24 hours
        limit = request.args.get('limit', 1000, type=int)  # Limit for performance
        date_str = request.args.get('date')  # Optional specific date YYYY-MM-DD
        
        # Calculate time range
        from datetime import datetime, timedelta
        
        if date_str:
            # Use specific date if provided
            try:
                selected_date = datetime.strptime(date_str, '%Y-%m-%d')
                # Get full day range for the selected date
                start_time = int(selected_date.timestamp() * 1000)
                end_time = int((selected_date + timedelta(days=1)).timestamp() * 1000)
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            # Use hours_back from current time (existing behavior)
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = end_time - (hours_back * 60 * 60 * 1000)
        
        # Use the new aggregation table for fast retrieval
        calculator = OptionsFlowCalculator()
        aggregations = calculator.database.get_flow_aggregations(
            symbol, start_time, end_time, limit
        )
        
        if not aggregations:
            return jsonify({
                'symbol': symbol,
                'data': [],
                'message': 'No aggregated data found'
            })
        
        # Convert to chart format (matching example script structure)
        chart_data = []
        for agg in reversed(aggregations):  # Reverse to get chronological order
            chart_data.append({
                'timestamp': agg['timestamp'],
                'time': datetime.fromtimestamp(agg['timestamp'] / 1000).isoformat(),
                'call_delta_volume': agg['call_delta_volume'],
                'put_delta_volume': agg['put_delta_volume'],
                'net_delta_volume': agg['net_delta_volume'],
                'delta_ratio': agg['delta_ratio'],
                'call_volume': agg['call_volume'],
                'put_volume': agg['put_volume'],
                'total_volume': agg['total_volume'],
                'underlying_price': agg['underlying_price'],
                'sentiment': agg['sentiment'],
                'sentiment_strength': agg['sentiment_strength']
            })
        
        return jsonify({
            'symbol': symbol,
            'data': chart_data,
            'total_points': len(chart_data),
            'time_range_hours': hours_back,
            'latest_timestamp': chart_data[-1]['timestamp'] if chart_data else None
        })
        
    except Exception as e:
        logger.error(f"Error getting aggregated chart data for {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@options_bp.route('/status')
@require_auth
def get_options_status():
    """Get status of options data collection"""
    try:
        calculator = OptionsFlowCalculator()
        symbols = calculator.database.get_all_symbols()
        
        status_data = {
            'database_path': calculator.database.db_path,
            'symbols_with_data': symbols,
            'total_symbols': len(symbols),
            'available': len(symbols) > 0
        }
        
        # Get stats for each symbol
        if symbols:
            symbol_stats = {}
            for symbol in symbols:
                stats = calculator.database.get_symbol_stats(symbol)
                symbol_stats[symbol] = stats
            status_data['symbol_stats'] = symbol_stats
        
        return jsonify(status_data)
        
    except Exception as e:
        logger.error(f"Error getting options status: {e}")
        return jsonify({'error': str(e)}), 500