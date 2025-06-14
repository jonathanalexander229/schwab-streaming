import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

class OHLCDatabase:
    def __init__(self, db_path: str = "data/historical_data.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize database with OHLC schema and indexes"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ohlc_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    timeframe TEXT NOT NULL DEFAULT '1m',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timestamp, timeframe)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_timestamp 
                ON ohlc_data(symbol, timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_timeframe_timestamp 
                ON ohlc_data(symbol, timeframe, timestamp)
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS collection_progress (
                    symbol TEXT PRIMARY KEY,
                    start_date INTEGER NOT NULL,
                    end_date INTEGER NOT NULL,
                    last_collected INTEGER,
                    total_candles INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def insert_ohlc_data(self, symbol: str, ohlc_data: List[Dict[str, Any]], timeframe: str = '1m') -> int:
        """Insert OHLC data with conflict handling"""
        if not ohlc_data:
            return 0
        
        with sqlite3.connect(self.db_path) as conn:
            inserted_count = 0
            for candle in ohlc_data:
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO ohlc_data 
                        (symbol, timestamp, open_price, high_price, low_price, close_price, volume, timeframe)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol,
                        int(candle['datetime']),
                        float(candle['open']),
                        float(candle['high']),
                        float(candle['low']),
                        float(candle['close']),
                        int(candle['volume']),
                        timeframe
                    ))
                    inserted_count += 1
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"Skipping invalid candle for {symbol}: {e}")
                    continue
            
            conn.commit()
            return inserted_count
    
    def get_ohlc_data(self, symbol: str, start_timestamp: int, end_timestamp: int, 
                      timeframe: str = '1m') -> List[Dict[str, Any]]:
        """Retrieve OHLC data for symbol and date range"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT symbol, timestamp, open_price, high_price, low_price, 
                       close_price, volume, timeframe
                FROM ohlc_data 
                WHERE symbol = ? AND timestamp >= ? AND timestamp <= ? AND timeframe = ?
                ORDER BY timestamp
            """, (symbol, start_timestamp, end_timestamp, timeframe))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_data_gaps(self, symbol: str, timeframe: str = '1m') -> List[Tuple[int, int]]:
        """Identify gaps in data collection"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT timestamp FROM ohlc_data 
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp
            """, (symbol, timeframe))
            
            timestamps = [row[0] for row in cursor.fetchall()]
            
            if len(timestamps) < 2:
                return []
            
            gaps = []
            expected_interval = 60 if timeframe == '1m' else 300
            
            for i in range(1, len(timestamps)):
                gap_size = timestamps[i] - timestamps[i-1]
                if gap_size > expected_interval * 2:
                    gaps.append((timestamps[i-1], timestamps[i]))
            
            return gaps
    
    def update_collection_progress(self, symbol: str, start_date: int, end_date: int, 
                                 last_collected: int, status: str = 'in_progress'):
        """Update collection progress tracking"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO collection_progress 
                (symbol, start_date, end_date, last_collected, status, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (symbol, start_date, end_date, last_collected, status))
            conn.commit()
    
    def get_collection_progress(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get collection progress for symbol"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM collection_progress WHERE symbol = ?
            """, (symbol,))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_symbol_stats(self, symbol: str, timeframe: str = '1m') -> Dict[str, Any]:
        """Get statistics for symbol data"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_candles,
                    MIN(timestamp) as earliest_timestamp,
                    MAX(timestamp) as latest_timestamp,
                    MIN(low_price) as min_price,
                    MAX(high_price) as max_price
                FROM ohlc_data 
                WHERE symbol = ? AND timeframe = ?
            """, (symbol, timeframe))
            
            row = cursor.fetchone()
            if row and row[0] > 0:
                return {
                    'total_candles': row[0],
                    'earliest_date': datetime.fromtimestamp(row[1]),
                    'latest_date': datetime.fromtimestamp(row[2]),
                    'price_range': {'min': row[3], 'max': row[4]}
                }
            return {'total_candles': 0}