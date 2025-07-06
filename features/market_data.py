# market_data.py - Modular Market Data Manager
import os
import json
import logging
import time
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Set, Optional, Callable
import threading
from streaming.equity_stream_manager import EquityStreamManager

# Configure logging
logger = logging.getLogger(__name__)

class MarketDataManager:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.market_data: Dict[str, Any] = {}
        self.watchlist: Set[str] = set()
        self.is_mock_mode = False
        
        # Initialize equity streaming manager
        self.equity_stream_manager = EquityStreamManager()
        self.equity_stream_manager.set_equity_data_handler(self._process_equity_data_callback)
        
        # Watchlist file path - should be in the same directory as app.py
        self.watchlist_file = os.path.join(os.path.dirname(data_dir), 'watchlist.json')
        
        # Debug: Log the watchlist file path
        logger.info(f"Looking for watchlist at: {self.watchlist_file}")
        
        # Load watchlist on initialization
        self.load_watchlist()
    
    def set_dependencies(self, schwab_client, schwab_streamer, socketio, is_mock_mode: bool = False):
        """Inject external dependencies"""
        self.schwab_client = schwab_client
        self.socketio = socketio
        self.is_mock_mode = is_mock_mode
        
        # Configure equity stream manager
        self.equity_stream_manager.set_dependencies(schwab_streamer, socketio, is_mock_mode)
    
    def get_db_connection(self, is_mock_mode: Optional[bool] = None) -> sqlite3.Connection:
        """Get database connection with mock/real separation"""
        if is_mock_mode is None:
            is_mock_mode = self.is_mock_mode
        
        today_date = datetime.now().strftime('%y%m%d')
        
        if is_mock_mode:
            db_filename = os.path.join(self.data_dir, f'MOCK_market_data_{today_date}.db')
            logger.info(f"Using MOCK database: {db_filename}")
        else:
            db_filename = os.path.join(self.data_dir, f'market_data_{today_date}.db')
            logger.info(f"Using REAL database: {db_filename}")
        
        conn = sqlite3.connect(db_filename)
        cursor = conn.cursor()
        
        # Create equity quotes table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS equity_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            timestamp INTEGER,
            last_price REAL,
            bid_price REAL,
            ask_price REAL,
            volume INTEGER,
            net_change REAL,
            net_change_percent REAL,
            high_price REAL,
            low_price REAL,
            data_source TEXT DEFAULT 'UNKNOWN'
        )
        ''')
        
        # Metadata table to track data source
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at INTEGER,
            data_source TEXT,
            app_version TEXT,
            notes TEXT
        )
        ''')
        
        # Insert metadata record on first connection
        cursor.execute('SELECT COUNT(*) FROM data_metadata')
        if cursor.fetchone()[0] == 0:
            data_source = 'MOCK' if is_mock_mode else 'SCHWAB_API'
            cursor.execute('''
                INSERT INTO data_metadata (created_at, data_source, app_version, notes)
                VALUES (?, ?, ?, ?)
            ''', (
                int(time.time() * 1000),
                data_source,
                "1.0.0",
                f"Database created in {'mock' if is_mock_mode else 'real'} mode"
            ))
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_equity_symbol_ts ON equity_quotes (symbol, timestamp)')
        conn.commit()
        return conn
    
    def load_watchlist(self) -> Set[str]:
        """Load watchlist from JSON file"""
        try:
            logger.info(f"Attempting to load watchlist from: {self.watchlist_file}")
            logger.info(f"File exists: {os.path.exists(self.watchlist_file)}")
            
            if os.path.exists(self.watchlist_file):
                with open(self.watchlist_file, 'r') as f:
                    data = json.load(f)
                    self.watchlist = set(data.get('symbols', []))
                    logger.info(f"Successfully loaded watchlist with {len(self.watchlist)} symbols: {list(self.watchlist)}")
            else:
                self.watchlist = set()
                logger.warning(f"Watchlist file not found at {self.watchlist_file}, starting with empty watchlist")
        except Exception as e:
            logger.error(f"Error loading watchlist from {self.watchlist_file}: {e}")
            self.watchlist = set()
        
        return self.watchlist
    
    def save_watchlist(self):
        """Save watchlist to JSON file"""
        try:
            with open(self.watchlist_file, 'w') as f:
                json.dump({'symbols': list(self.watchlist)}, f, indent=2)
            logger.info(f"Watchlist saved with {len(self.watchlist)} symbols")
        except Exception as e:
            logger.error(f"Error saving watchlist: {e}")
    
    def add_symbol(self, symbol: str) -> bool:
        """Add symbol to watchlist and subscribe to streaming"""
        symbol = symbol.upper().strip()
        
        if symbol in self.watchlist:
            return False
        
        self.watchlist.add(symbol)
        self.save_watchlist()
        
        # Subscribe via equity stream manager (handles all subscription logic)
        success = self.equity_stream_manager.add_equity_subscription(symbol)
        return success
    
    def remove_symbol(self, symbol: str) -> bool:
        """Remove symbol from watchlist"""
        symbol = symbol.upper().strip()
        if symbol not in self.watchlist:
            return False
        
        self.watchlist.remove(symbol)
        self.save_watchlist()
        
        # Remove from market data
        if symbol in self.market_data:
            del self.market_data[symbol]
        
        # Remove from stream manager
        self.equity_stream_manager.remove_equity_subscription(symbol)
        
        return True
    
    def get_watchlist(self) -> list:
        """Get current watchlist as a list"""
        return list(self.watchlist)
    
    def get_market_data(self) -> Dict[str, Any]:
        """Get current market data with metadata"""
        return {
            'market_data': self.market_data,
            'is_mock_mode': self.is_mock_mode,
            'data_source': 'MOCK' if self.is_mock_mode else 'SCHWAB_API',
            'timestamp': int(time.time() * 1000)
        }
    
    def _process_equity_data_callback(self, equity_data: Dict[str, Any]):
        """Callback for processed equity data from EquityStreamManager"""
        symbol = equity_data.get('symbol')
        if not symbol:
            return
            
        # Store globally
        self.market_data[symbol] = equity_data
        
        # Save to database
        self._save_to_database(equity_data)
        
        # Emit to clients
        if self.socketio:
            self.socketio.emit('market_data', {
                'symbol': symbol, 
                'data': equity_data,
                'is_mock': self.is_mock_mode
            })
        
        # Enhanced logging
        source_label = "MOCK" if self.is_mock_mode else "REAL"
        logger.info(f"{source_label} data for {symbol}: Last ${equity_data.get('last_price', 'N/A')}")

    def _save_to_database(self, market_data_item: Dict[str, Any]):
        """Save market data to database"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO equity_quotes 
                (symbol, timestamp, last_price, bid_price, ask_price, volume, 
                 net_change, net_change_percent, high_price, low_price, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                market_data_item['symbol'], market_data_item['timestamp'], 
                market_data_item['last_price'], market_data_item['bid_price'],
                market_data_item['ask_price'], market_data_item['volume'], 
                market_data_item['net_change'], market_data_item['net_change_percent'], 
                market_data_item['high_price'], market_data_item['low_price'], 
                market_data_item['data_source']
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Database error: {e}")
    
    def start_streaming(self):
        """Start market data streaming via equity stream manager"""
        logger.info("Starting market data streaming")
        
        if not self.equity_stream_manager.start_streaming():
            logger.error("Failed to start equity stream manager")
            return False
        
        try:
            # Subscribe to all watchlist symbols
            if self.watchlist:
                for symbol in self.watchlist:
                    self.equity_stream_manager.add_equity_subscription(symbol)
                    time.sleep(0.1)  # Rate limit protection
                    
                logger.info(f"Subscribed to {len(self.watchlist)} symbols: {', '.join(list(self.watchlist))}")
            else:
                # Subscribe to default symbol if no watchlist
                default_symbol = "SPY"
                self.equity_stream_manager.add_equity_subscription(default_symbol)
                self.watchlist.add(default_symbol)
                self.save_watchlist()
                logger.info(f"Subscribed to default symbol: {default_symbol}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting streaming: {e}")
            return False
    
    def stop_streaming(self):
        """Stop market data streaming"""
        self.equity_stream_manager.stop_streaming()
        logger.info("Market data streaming stopped")
    
    def get_auth_status(self) -> Dict[str, Any]:
        """Get authentication and connection status"""
        return {
            'authenticated': True,  # Will be handled by main app
            'mock_mode': self.is_mock_mode,
            'using_real_api': self.schwab_client is not None and not self.is_mock_mode,
            'has_streamer': self.equity_stream_manager.streamer is not None,
            'data_source': 'MOCK' if self.is_mock_mode else 'SCHWAB_API',
            'database_prefix': 'MOCK_' if self.is_mock_mode else '',
            'watchlist_count': len(self.watchlist),
            'streaming_active': self.equity_stream_manager.is_active()
        }


# Global instance
market_data_manager = None

def get_market_data_manager(data_dir: str = None) -> Optional[MarketDataManager]:
    """Get the global market data manager instance"""
    global market_data_manager
    if market_data_manager is None and data_dir:
        market_data_manager = MarketDataManager(data_dir)
    return market_data_manager

def initialize_market_data_manager(data_dir: str) -> MarketDataManager:
    """Initialize the global market data manager"""
    global market_data_manager
    market_data_manager = MarketDataManager(data_dir)
    return market_data_manager