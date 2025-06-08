# market_data_routes.py - Modular Market Data Routes
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, current_app
from flask_socketio import emit
import logging
from auth import require_auth

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
market_data_bp = Blueprint('market_data', __name__)

def _get_manager():
    """Helper to get market data manager from feature manager"""
    return current_app.feature_manager.get_feature('market_data')

@market_data_bp.route('/market-data')
@require_auth
def index():
    """Main market data page"""
    return render_template('index.html')

# API Routes for Market Data
@market_data_bp.route('/api/watchlist', methods=['GET'])
@require_auth
def get_watchlist():
    """Get current watchlist"""
    
    manager = _get_manager()
    if not manager:
        return jsonify({'error': 'Market data manager not initialized'}), 500
    
    return jsonify({'watchlist': manager.get_watchlist()})

@market_data_bp.route('/api/watchlist', methods=['POST'])
@require_auth
def add_to_watchlist():
    """Add symbol to watchlist"""
    
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').upper().strip()
        
        if not symbol:
            return jsonify({'error': 'Symbol is required'}), 400
        
        manager = _get_manager()
        if not manager:
            return jsonify({'error': 'Market data manager not initialized'}), 500
        
        success = manager.add_symbol(symbol)
        if not success:
            return jsonify({'error': f'{symbol} is already in watchlist'}), 400
        
        return jsonify({'success': True, 'watchlist': manager.get_watchlist()})
        
    except Exception as e:
        logger.error(f"Error adding to watchlist: {e}")
        return jsonify({'error': str(e)}), 500

@market_data_bp.route('/api/watchlist', methods=['DELETE'])
@require_auth
def remove_from_watchlist():
    """Remove symbol from watchlist"""
    
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').upper().strip()
        
        manager = _get_manager()
        if not manager:
            return jsonify({'error': 'Market data manager not initialized'}), 500
        
        manager.remove_symbol(symbol)
        return jsonify({'success': True, 'watchlist': manager.get_watchlist()})
        
    except Exception as e:
        logger.error(f"Error removing from watchlist: {e}")
        return jsonify({'error': str(e)}), 500

@market_data_bp.route('/api/market-data')
@require_auth
def get_market_data():
    """Get current market data"""
    
    manager = _get_manager()
    if not manager:
        return jsonify({'error': 'Market data manager not initialized'}), 500
    
    return jsonify(manager.get_market_data())

@market_data_bp.route('/api/auth-status')
def auth_status():
    """Get authentication and system status"""
    import os
    is_authenticated = session.get('authenticated', False)
    
    if not is_authenticated:
        return jsonify({'authenticated': False})
    
    manager = _get_manager()
    if not manager:
        return jsonify({'authenticated': True, 'error': 'Market data manager not initialized'})
    
    status = manager.get_auth_status()
    status['authenticated'] = is_authenticated
    return jsonify(status)

# Mock testing routes
@market_data_bp.route('/api/test/market-event', methods=['POST'])
@require_auth
def trigger_market_event():
    """Trigger mock market events for testing"""
    
    manager = _get_manager()
    if not manager or not manager.is_mock_mode:
        return jsonify({'error': 'Mock events only available in mock mode'}), 400
    
    try:
        data = request.get_json()
        event_type = data.get('event_type', 'bullish_surge')
        symbols = data.get('symbols', manager.get_watchlist())
        
        if hasattr(manager.stream_manager.streamer, 'simulate_market_event'):
            manager.stream_manager.streamer.simulate_market_event(event_type, symbols)
            logger.info(f"Successfully triggered {event_type} for {len(symbols)} symbols")
        else:
            logger.warning("Streamer does not have simulate_market_event method")
            return jsonify({'error': 'Mock events not available on this streamer'}), 400
        
        return jsonify({
            'success': True, 
            'event_type': event_type,
            'symbols': symbols,
            'message': f'Triggered {event_type} for {len(symbols)} symbols'
        })
        
    except Exception as e:
        logger.error(f"Error triggering market event: {e}")
        return jsonify({'error': str(e)}), 500

@market_data_bp.route('/api/debug/session')
@require_auth
def debug_session():
    """Debug route to check session and system status"""
    
    manager = _get_manager()
    
    # Check feature manager status
    feature_manager_status = {
        'available': hasattr(current_app, 'feature_manager'),
        'features': list(current_app.feature_manager.features.keys()) if hasattr(current_app, 'feature_manager') else [],
        'mock_mode': current_app.feature_manager.get_mock_mode() if hasattr(current_app, 'feature_manager') else None
    }
    
    # Test if we can get auth client
    try:
        from auth import get_schwab_client
        test_client = get_schwab_client(use_mock=session.get('mock_mode', False))
        client_info = {
            'can_create_client': test_client is not None,
            'client_type': type(test_client).__name__ if test_client else None
        }
    except Exception as e:
        client_info = {'error': str(e)}
    
    return jsonify({
        'authenticated': session.get('authenticated', False),
        'session_keys': list(session.keys()),
        'session_mock_mode': session.get('mock_mode', None),
        'market_data_manager_available': manager is not None,
        'manager_mock_mode': manager.is_mock_mode if manager else None,
        'manager_watchlist': list(manager.watchlist) if manager else None,
        'manager_watchlist_count': len(manager.watchlist) if manager else 0,
        'manager_client_type': type(manager.schwab_client).__name__ if manager and manager.schwab_client else None,
        'streaming_active': manager.stream_manager.is_active() if manager else None,
        'data_source': manager.get_auth_status().get('data_source') if manager else None,
        'feature_manager': feature_manager_status,
        'client_test': client_info
    })

# WebSocket event handlers
def register_socketio_handlers(socketio):
    """Register WebSocket event handlers for market data"""
    
    @socketio.on('connect')
    def handle_connect():
        if not session.get('authenticated'):
            emit('error', {'message': 'Not authenticated'})
            return False
        
        logger.info('Client connected to market data')
        
        # Send current market data
        manager = _get_manager()
        if manager:
            for symbol, data in manager.market_data.items():
                emit('market_data', {'symbol': symbol, 'data': data})

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info('Client disconnected from market data')

    @socketio.on('add_symbol')
    def handle_add_symbol(data):
        if not session.get('authenticated'):
            emit('error', {'message': 'Not authenticated'})
            return
        
        symbol = data.get('symbol', '').upper().strip()
        if not symbol:
            emit('error', {'message': 'Symbol is required'})
            return
        
        manager = _get_manager()
        if not manager:
            emit('error', {'message': 'Market data manager not initialized'})
            return
        
        # Validate symbol format
        import re
        if not re.match(r'^[A-Z]{1,5}$', symbol):
            emit('error', {'message': 'Invalid symbol format'})
            return
        
        success = manager.add_symbol(symbol)
        if success:
            emit('watchlist_updated', {'watchlist': manager.get_watchlist()}, broadcast=True)
        else:
            emit('error', {'message': f'{symbol} is already in watchlist'})

    @socketio.on('remove_symbol')
    def handle_remove_symbol(data):
        if not session.get('authenticated'):
            emit('error', {'message': 'Not authenticated'})
            return
        
        symbol = data.get('symbol', '').upper().strip()
        
        manager = _get_manager()
        if not manager:
            emit('error', {'message': 'Market data manager not initialized'})
            return
        
        success = manager.remove_symbol(symbol)
        if success:
            emit('watchlist_updated', {'watchlist': manager.get_watchlist()}, broadcast=True)
            emit('symbol_removed', {'symbol': symbol}, broadcast=True)