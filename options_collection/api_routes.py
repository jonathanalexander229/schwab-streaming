from flask import Blueprint, jsonify, request
import json
import os
import logging
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