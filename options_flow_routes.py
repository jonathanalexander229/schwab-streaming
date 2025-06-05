# options_flow_routes.py - Modular Options Flow Routes
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_socketio import emit
import logging
from options_flow import get_options_monitor, initialize_options_monitor

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
options_flow_bp = Blueprint('options_flow', __name__)

@options_flow_bp.route('/options-flow')
def options_flow():
    """Options flow monitoring page"""
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    
    options_monitor = get_options_monitor()
    current_symbol = options_monitor.symbol if options_monitor else 'SPY'
    
    return render_template('options_flow.html', current_symbol=current_symbol)

@options_flow_bp.route('/api/options-flow/current')
def get_current_options_flow():
    """Get current options flow data"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        options_monitor = get_options_monitor()
        if not options_monitor:
            return jsonify({'error': 'Options monitor not initialized'}), 500
        
        current_data = options_monitor.get_current_data()
        return jsonify(current_data)
        
    except Exception as e:
        logger.error(f"Error getting current options flow: {e}")
        return jsonify({'error': str(e)}), 500

@options_flow_bp.route('/api/options-flow/historical')
def get_historical_options_flow():
    """Get historical options flow data"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        limit = request.args.get('limit', type=int)
        
        options_monitor = get_options_monitor()
        if not options_monitor:
            return jsonify({'error': 'Options monitor not initialized'}), 500
        
        historical_data = options_monitor.get_historical_data(limit)
        return jsonify(historical_data)
        
    except Exception as e:
        logger.error(f"Error getting historical options flow: {e}")
        return jsonify({'error': str(e)}), 500

@options_flow_bp.route('/api/options-flow/symbol', methods=['POST'])
def change_options_symbol():
    """Change the options flow monitoring symbol"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        new_symbol = data.get('symbol', '').upper().strip()
        
        if not new_symbol:
            return jsonify({'error': 'Symbol is required'}), 400
        
        options_monitor = get_options_monitor()
        if not options_monitor:
            return jsonify({'error': 'Options monitor not initialized'}), 500
        
        options_monitor.change_symbol(new_symbol)
        return jsonify({'success': True, 'symbol': new_symbol})
        
    except Exception as e:
        logger.error(f"Error changing options symbol: {e}")
        return jsonify({'error': str(e)}), 500

# WebSocket event handlers
def register_socketio_handlers(socketio):
    """Register WebSocket event handlers for options flow"""
    
    @socketio.on('change_options_symbol')
    def handle_change_options_symbol(data):
        """Handle options symbol change via WebSocket"""
        if not session.get('authenticated'):
            emit('error', {'message': 'Not authenticated'})
            return
        
        try:
            new_symbol = data.get('symbol', '').upper().strip()
            
            if not new_symbol:
                emit('error', {'message': 'Symbol is required'})
                return
            
            options_monitor = get_options_monitor()
            if not options_monitor:
                emit('error', {'message': 'Options monitor not initialized'})
                return
            
            options_monitor.change_symbol(new_symbol)
            emit('options_symbol_changed', {'symbol': new_symbol}, broadcast=True)
            logger.info(f"Options symbol changed to {new_symbol} via WebSocket")
            
        except Exception as e:
            logger.error(f"Error changing options symbol via WebSocket: {e}")
            emit('error', {'message': str(e)})

# Initialization function
def initialize_options_flow(schwab_client, socketio, db_connection_factory):
    """Initialize options flow monitoring"""
    try:
        options_monitor = initialize_options_monitor("SPY", 20, 100)
        options_monitor.set_dependencies(schwab_client, socketio, db_connection_factory)
        
        # Register WebSocket handlers
        register_socketio_handlers(socketio)
        
        logger.info("Options flow module initialized successfully")
        return options_monitor
        
    except Exception as e:
        logger.error(f"Failed to initialize options flow: {e}")
        return None

def start_options_monitoring(update_interval: int = 30):
    """Start options flow monitoring if monitor exists"""
    options_monitor = get_options_monitor()
    if options_monitor and not options_monitor.is_running:
        options_monitor.start_monitoring(update_interval)
        logger.info("Options flow monitoring started")
        return True
    return False

def stop_options_monitoring():
    """Stop options flow monitoring if running"""
    options_monitor = get_options_monitor()
    if options_monitor and options_monitor.is_running:
        options_monitor.stop_monitoring()
        logger.info("Options flow monitoring stopped")
        return True
    return False