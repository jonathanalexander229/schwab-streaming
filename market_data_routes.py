# market_data_routes.py - Modular Market Data Routes
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from flask_socketio import emit
import logging
from market_data import get_market_data_manager

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
market_data_bp = Blueprint('market_data', __name__)

@market_data_bp.route('/market-data')
def index():
    """Main market data page"""
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template('index.html')

# API Routes for Market Data
@market_data_bp.route('/api/watchlist', methods=['GET'])
def get_watchlist():
    """Get current watchlist"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    manager = get_market_data_manager()
    if not manager:
        return jsonify({'error': 'Market data manager not initialized'}), 500
    
    return jsonify({'watchlist': manager.get_watchlist()})

@market_data_bp.route('/api/watchlist', methods=['POST'])
def add_to_watchlist():
    """Add symbol to watchlist"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').upper().strip()
        
        if not symbol:
            return jsonify({'error': 'Symbol is required'}), 400
        
        manager = get_market_data_manager()
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
def remove_from_watchlist():
    """Remove symbol from watchlist"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').upper().strip()
        
        manager = get_market_data_manager()
        if not manager:
            return jsonify({'error': 'Market data manager not initialized'}), 500
        
        manager.remove_symbol(symbol)
        return jsonify({'success': True, 'watchlist': manager.get_watchlist()})
        
    except Exception as e:
        logger.error(f"Error removing from watchlist: {e}")
        return jsonify({'error': str(e)}), 500

@market_data_bp.route('/api/market-data')
def get_market_data():
    """Get current market data"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    manager = get_market_data_manager()
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
    
    manager = get_market_data_manager()
    if not manager:
        return jsonify({'authenticated': True, 'error': 'Market data manager not initialized'})
    
    status = manager.get_auth_status()
    status['authenticated'] = is_authenticated
    return jsonify(status)

# Mock testing routes
@market_data_bp.route('/api/test/market-event', methods=['POST'])
def trigger_market_event():
    """Trigger mock market events for testing"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    manager = get_market_data_manager()
    if not manager or not manager.is_mock_mode:
        return jsonify({'error': 'Mock events only available in mock mode'}), 400
    
    try:
        data = request.get_json()
        event_type = data.get('event_type', 'bullish_surge')
        symbols = data.get('symbols', manager.get_watchlist())
        
        if hasattr(manager.schwab_streamer, 'simulate_market_event'):
            manager.schwab_streamer.simulate_market_event(event_type, symbols)
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

# Admin routes
@market_data_bp.route('/api/admin/data-info')
def data_info():
    """Get information about stored data"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        import os
        from datetime import datetime
        
        manager = get_market_data_manager()
        if not manager:
            return jsonify({'error': 'Market data manager not initialized'}), 500
        
        files = []
        data_dir = manager.data_dir
        
        for filename in os.listdir(data_dir):
            if filename.endswith('.db'):
                is_mock = filename.startswith('MOCK_')
                size = os.path.getsize(os.path.join(data_dir, filename))
                files.append({
                    'filename': filename,
                    'type': 'MOCK' if is_mock else 'REAL',
                    'size_mb': round(size / (1024*1024), 2),
                    'path': os.path.join(data_dir, filename)
                })
        
        stats = {
            'total_files': len(files),
            'mock_files': len([f for f in files if f['type'] == 'MOCK']),
            'real_files': len([f for f in files if f['type'] == 'REAL']),
            'total_size_mb': sum(f['size_mb'] for f in files),
            'mock_size_mb': sum(f['size_mb'] for f in files if f['type'] == 'MOCK'),
            'real_size_mb': sum(f['size_mb'] for f in files if f['type'] == 'REAL')
        }
        
        return jsonify({
            'current_mode': 'MOCK' if manager.is_mock_mode else 'REAL',
            'database_files': files,
            'statistics': stats,
            'current_database': f"{'MOCK_' if manager.is_mock_mode else ''}market_data_{datetime.now().strftime('%y%m%d')}.db"
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_data_bp.route('/api/admin/cleanup-mock', methods=['POST'])
def cleanup_mock():
    """Clean up mock database files"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        import os
        
        manager = get_market_data_manager()
        if not manager:
            return jsonify({'error': 'Market data manager not initialized'}), 500
        
        data_dir = manager.data_dir
        removed_files = []
        
        for filename in os.listdir(data_dir):
            if filename.startswith('MOCK_') and filename.endswith('.db'):
                file_path = os.path.join(data_dir, filename)
                os.remove(file_path)
                removed_files.append(filename)
        
        return jsonify({
            'success': True,
            'removed_files': removed_files,
            'count': len(removed_files)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_data_bp.route('/api/debug/session')
def debug_session():
    """Debug route to check session status"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    manager = get_market_data_manager()
    
    return jsonify({
        'authenticated': session.get('authenticated', False),
        'session_keys': list(session.keys()),
        'market_data_manager_available': manager is not None,
        'mock_mode': manager.is_mock_mode if manager else None,
        'watchlist_count': len(manager.watchlist) if manager else 0
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
        manager = get_market_data_manager()
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
        
        manager = get_market_data_manager()
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
        
        manager = get_market_data_manager()
        if not manager:
            emit('error', {'message': 'Market data manager not initialized'})
            return
        
        success = manager.remove_symbol(symbol)
        if success:
            emit('watchlist_updated', {'watchlist': manager.get_watchlist()}, broadcast=True)
            emit('symbol_removed', {'symbol': symbol}, broadcast=True)

# Initialization functions
def initialize_market_data(data_dir: str, schwab_client, schwab_streamer, socketio, is_mock_mode: bool = False):
    """Initialize market data module"""
    from market_data import initialize_market_data_manager
    
    try:
        # Initialize manager
        manager = initialize_market_data_manager(data_dir)
        manager.set_dependencies(schwab_client, schwab_streamer, socketio, is_mock_mode)
        
        # Register WebSocket handlers
        register_socketio_handlers(socketio)
        
        logger.info(f"Market data module initialized in {'MOCK' if is_mock_mode else 'REAL'} mode")
        logger.info(f"Loaded watchlist with {len(manager.watchlist)} symbols: {', '.join(list(manager.watchlist))}")
        
        return manager
        
    except Exception as e:
        logger.error(f"Failed to initialize market data: {e}")
        return None

def start_market_data_streaming():
    """Start market data streaming if manager exists"""
    manager = get_market_data_manager()
    if manager:
        return manager.start_streaming()
    return False

def stop_market_data_streaming():
    """Stop market data streaming if running"""
    manager = get_market_data_manager()
    if manager:
        manager.stop_streaming()
        return True
    return False