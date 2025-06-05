# market_data.py - Modular Market Data Manager
import os
import json
import logging
import time
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Set, Optional, Callable
import threading

# Configure logging
logger = logging.getLogger(__name__)

class MarketDataManager:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.market_data: Dict[str, Any] = {}
        self.watchlist: Set[str] = set()
        self.schwab_client = None
        self.schwab_streamer = None
        self.socketio = None
        self.is_mock_mode = False
        self.message_handler_registered = False
        
        # Watchlist file path - should be in the same directory as app.py
        self.watchlist_file = os.path.join(os.path.dirname(data_dir), 'watchlist.json')
        
        # Debug: Log the watchlist file path
        logger.info(f"Looking for watchlist at: {self.watchlist_file}")
        
        # Load watchlist on initialization
        self.load_watchlist()
    
    def set_dependencies(self, schwab_client, schwab_streamer, socketio, is_mock_mode: bool = False):
        """Inject external dependencies"""
        self.schwab_client = schwab_client
        self.schwab_streamer = schwab_streamer
        self.socketio = socketio
        self.is_mock_mode = is_mock_mode
    
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
        
        # Subscribe to streaming if available
        if self.schwab_streamer:
            try:
                if hasattr(self.schwab_streamer, 'add_symbol'):
                    # Mock streamer method
                    self.schwab_streamer.add_symbol(symbol)
                    logger.info(f"Added {symbol} to mock stream")
                else:
                    # Real Schwab streamer method
                    self.schwab_streamer.send(self.schwab_streamer.level_one_equities(symbol, "0,1,2,3,4,5,8,12,13,29,30"))
                    logger.info(f"Subscribed to Schwab data for {symbol}")
                return True
            except Exception as e:
                logger.error(f"Error subscribing to {symbol}: {e}")
                return False
        
        return True
    
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
    
    def schwab_message_handler(self, message: str):
        """Enhanced message handler with data source tracking"""
        try:
            data = json.loads(message)
            
            # Skip heartbeat messages
            if 'notify' in data and any('heartbeat' in item for item in data['notify']):
                return
            
            # Log the entire raw message for debugging
            logger.info("="*80)
            logger.info("COMPLETE SCHWAB MESSAGE:")
            logger.info(json.dumps(data, indent=2))
            logger.info("="*80)
            
            # Handle service messages
            if 'notify' in data:
                for item in data['notify']:
                    if item.get('service') == 'ADMIN':
                        logger.warning(f"Admin message: {item.get('content', {}).get('msg', 'Unknown')}")
                        return
            
            # Process actual market data
            if "data" not in data:
                return

            for item in data["data"]:
                service = item.get("service")
                if not service or "content" not in item:
                    continue
                
                timestamp = int(time.time() * 1000)
                
                # Process each content item
                for content in item["content"]:
                    symbol = content.get("key")
                    if not symbol:
                        continue

                    if service == "LEVELONE_EQUITIES":
                        # Process level one equity data (keeping original field mapping)
                        market_data_item = {
                            'symbol': symbol,
                            'last_price': content.get("1"),      # Last price
                            'bid_price': content.get("2"),       # Bid price  
                            'ask_price': content.get("3"),       # Ask price
                            'volume': content.get("8"),          # Volume
                            'high_price': content.get("12"),     # High price
                            'low_price': content.get("13"),      # Low price (or market indicator?)
                            'net_change': content.get("29"),     # Net change (or previous close?)
                            'net_change_percent': content.get("30"), # Net change percent (or volume?)
                            'timestamp': timestamp,
                            'data_source': 'MOCK' if self.is_mock_mode else 'SCHWAB_API'
                        }
                        
                        # Store globally
                        self.market_data[symbol] = market_data_item
                        
                        # Save to appropriate database
                        try:
                            conn = self.get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO equity_quotes 
                                (symbol, timestamp, last_price, bid_price, ask_price, volume, 
                                 net_change, net_change_percent, high_price, low_price, data_source)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (symbol, timestamp, market_data_item['last_price'], market_data_item['bid_price'],
                                  market_data_item['ask_price'], market_data_item['volume'], market_data_item['net_change'],
                                  market_data_item['net_change_percent'], market_data_item['high_price'], 
                                  market_data_item['low_price'], market_data_item['data_source']))
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            logger.error(f"Database error: {e}")
                        
                        # Emit to clients with source information
                        if self.socketio:
                            self.socketio.emit('market_data', {
                                'symbol': symbol, 
                                'data': market_data_item,
                                'is_mock': self.is_mock_mode
                            })
                        
                        # Enhanced logging
                        source_label = "MOCK" if self.is_mock_mode else "REAL"
                        logger.info(f"{source_label} data for {symbol}: Last ${market_data_item.get('last_price', 'N/A')}")
            
        except Exception as e:
            logger.error(f"Error processing Schwab message: {e}")
            logger.error(f"Problematic message: {message}")
    
    def start_streaming(self):
        """Start market data streaming"""
        if not self.schwab_streamer:
            logger.error("No Schwab streamer available")
            return False
        
        try:
            # Register message handler
            self.schwab_streamer.start(self.schwab_message_handler)
            logger.info("Market data streamer started")
            
            # Subscribe to all watchlist symbols
            if self.watchlist:
                for symbol in self.watchlist:
                    try:
                        if self.is_mock_mode:
                            if hasattr(self.schwab_streamer, 'add_symbol'):
                                self.schwab_streamer.add_symbol(symbol)
                                logger.info(f"Added {symbol} to mock stream")
                        else:
                            self.schwab_streamer.send(self.schwab_streamer.level_one_equities(symbol, "0,1,2,3,4,5,8,12,13,29,30"))
                            logger.info(f"Sent subscription request for {symbol}")
                        
                        # Add a small delay between subscriptions to avoid rate limits
                        time.sleep(0.1)
                        
                    except Exception as e:
                        logger.error(f"Failed to subscribe to {symbol}: {e}")
                        
                logger.info(f"Subscribed to {len(self.watchlist)} symbols: {', '.join(list(self.watchlist))}")
            else:
                # Subscribe to default symbol if no watchlist
                default_symbol = "SPY"
                if self.is_mock_mode:
                    if hasattr(self.schwab_streamer, 'add_symbol'):
                        self.schwab_streamer.add_symbol(default_symbol)
                else:
                    self.schwab_streamer.send(self.schwab_streamer.level_one_equities(default_symbol, "0,1,2,3,4,5,8,12,13,29,30"))
                
                self.watchlist.add(default_symbol)
                self.save_watchlist()
                logger.info(f"Subscribed to default symbol: {default_symbol}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting streaming: {e}")
            return False
    
    def stop_streaming(self):
        """Stop market data streaming"""
        if self.schwab_streamer:
            try:
                self.schwab_streamer.stop()
                logger.info("Market data streaming stopped")
            except Exception as e:
                logger.error(f"Error stopping streaming: {e}")
    
    def get_auth_status(self) -> Dict[str, Any]:
        """Get authentication and connection status"""
        return {
            'authenticated': True,  # Will be handled by main app
            'mock_mode': self.is_mock_mode,
            'using_real_api': self.schwab_client is not None and not self.is_mock_mode,
            'has_streamer': self.schwab_streamer is not None,
            'data_source': 'MOCK' if self.is_mock_mode else 'SCHWAB_API',
            'database_prefix': 'MOCK_' if self.is_mock_mode else '',
            'watchlist_count': len(self.watchlist)
        }


# Global instance
market_data_manager = None

def get_market_data_manager() -> Optional[MarketDataManager]:
    """Get the global market data manager instance"""
    return market_data_manager

def initialize_market_data_manager(data_dir: str) -> MarketDataManager:
    """Initialize the global market data manager"""
    global market_data_manager
    market_data_manager = MarketDataManager(data_dir)
    return market_data_manager