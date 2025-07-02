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
            
            # Get raw data including delta and volume for flow calculation
            query = """
            SELECT timestamp, option_type, delta, total_volume
            FROM options_data 
            WHERE symbol = ? AND total_volume > 0 AND delta IS NOT NULL
            ORDER BY timestamp
            """
            
            results = cursor.execute(query, (symbol,)).fetchall()
        
        if not results:
            return jsonify({
                'symbol': symbol,
                'calls': [],
                'puts': []
            })
        
        # Group by 5-minute buckets in Python
        from collections import defaultdict
        buckets = defaultdict(lambda: {'CALL': 0, 'PUT': 0})
        
        for row in results:
            timestamp_ms, option_type, delta, total_volume = row
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
        
        # Calculate cumulative net flow from baseline
        sorted_timestamps = sorted(buckets.keys())
        
        # Set baseline as first time period
        baseline_calls = buckets[sorted_timestamps[0]]['CALL'] if sorted_timestamps else 0
        baseline_puts = buckets[sorted_timestamps[0]]['PUT'] if sorted_timestamps else 0
        
        calls_data = []
        puts_data = []
        
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
        
        return jsonify({
            'symbol': symbol,
            'calls': calls_data,
            'puts': puts_data
        })
        
    except Exception as e:
        logger.error(f"Error getting chart data for {symbol}: {e}")
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