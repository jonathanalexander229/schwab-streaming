import sqlite3
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class OptionsDatabase:
    """
    Database manager for options data storage and retrieval.
    Handles comprehensive options chain data with full Greeks and pricing information.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the options database
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.init_database()
        logger.info(f"📊 Options database initialized: {db_path}")
    
    def init_database(self):
        """Create the options_data table with comprehensive schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create comprehensive options_data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS options_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    
                    -- Core identifiers
                    symbol TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    option_type TEXT NOT NULL,
                    expiration_date TEXT NOT NULL,
                    strike_price REAL NOT NULL,
                    
                    -- Pricing data
                    mark REAL,
                    bid REAL,
                    ask REAL,
                    last REAL,
                    
                    -- Volume and interest
                    total_volume INTEGER,
                    open_interest INTEGER,
                    
                    -- Greeks (complete set)
                    delta REAL,
                    gamma REAL,
                    theta REAL,
                    vega REAL,
                    rho REAL,
                    
                    -- Volatility metrics
                    implied_volatility REAL,
                    theoretical_value REAL,
                    
                    -- Time and moneyness
                    time_to_expiration REAL,
                    intrinsic_value REAL,
                    extrinsic_value REAL,
                    
                    -- Market context
                    underlying_price REAL,
                    
                    -- Simple metadata
                    data_source TEXT DEFAULT 'SCHWAB_API',
                    
                    -- Ensure unique records
                    UNIQUE(symbol, timestamp, option_type, expiration_date, strike_price)
                )
            """)
            
            # Create performance indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_options_symbol_timestamp 
                ON options_data(symbol, timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_options_expiration 
                ON options_data(expiration_date)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_options_type_strike 
                ON options_data(option_type, strike_price)
            """)
            
            conn.commit()
            logger.info("✅ Options database schema created/verified")
    
    def insert_options_data(self, options_records: List[Dict[str, Any]]) -> tuple[int, int]:
        """
        Insert multiple options records into the database
        
        Args:
            options_records: List of options data dictionaries
            
        Returns:
            Tuple of (inserted_count, duplicate_count)
        """
        if not options_records:
            return 0, 0
        
        inserted_count = 0
        duplicate_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for record in options_records:
                try:
                    cursor.execute("""
                        INSERT INTO options_data (
                            symbol, timestamp, option_type, expiration_date, strike_price,
                            mark, bid, ask, last,
                            total_volume, open_interest,
                            delta, gamma, theta, vega, rho,
                            implied_volatility, theoretical_value,
                            time_to_expiration, intrinsic_value, extrinsic_value,
                            underlying_price, data_source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record.get('symbol'),
                        record.get('timestamp'),
                        record.get('option_type'),
                        record.get('expiration_date'),
                        record.get('strike_price'),
                        record.get('mark'),
                        record.get('bid'),
                        record.get('ask'),
                        record.get('last'),
                        record.get('total_volume'),
                        record.get('open_interest'),
                        record.get('delta'),
                        record.get('gamma'),
                        record.get('theta'),
                        record.get('vega'),
                        record.get('rho'),
                        record.get('implied_volatility'),
                        record.get('theoretical_value'),
                        record.get('time_to_expiration'),
                        record.get('intrinsic_value'),
                        record.get('extrinsic_value'),
                        record.get('underlying_price'),
                        record.get('data_source', 'SCHWAB_API')
                    ))
                    inserted_count += 1
                    
                except sqlite3.IntegrityError:
                    # Duplicate record (same symbol, timestamp, option_type, expiration, strike)
                    duplicate_count += 1
                    continue
                    
                except Exception as e:
                    logger.error(f"Error inserting options record: {e}")
                    continue
            
            conn.commit()
        
        logger.info(f"📊 Options data inserted: {inserted_count} new, {duplicate_count} duplicates")
        return inserted_count, duplicate_count
    
    def get_options_data(self, symbol: str, start_timestamp: int, end_timestamp: int,
                        option_type: Optional[str] = None, 
                        expiration_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve options data for analysis
        
        Args:
            symbol: Stock symbol
            start_timestamp: Start time (Unix timestamp)
            end_timestamp: End time (Unix timestamp)
            option_type: Optional filter for 'CALL' or 'PUT'
            expiration_date: Optional filter for specific expiration (YYYY-MM-DD)
            
        Returns:
            List of options data records
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM options_data
                WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
            """
            params = [symbol, start_timestamp, end_timestamp]
            
            if option_type:
                query += " AND option_type = ?"
                params.append(option_type)
            
            if expiration_date:
                query += " AND expiration_date = ?"
                params.append(expiration_date)
            
            query += " ORDER BY timestamp, expiration_date, strike_price"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def get_flow_summary(self, symbol: str, start_timestamp: int, end_timestamp: int) -> List[Dict[str, Any]]:
        """
        Calculate delta-weighted volume flow summary
        
        Args:
            symbol: Stock symbol
            start_timestamp: Start time
            end_timestamp: End time  
            
        Returns:
            List of flow summary records
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    timestamp,
                    symbol,
                    underlying_price,
                    
                    -- Call metrics
                    SUM(CASE WHEN option_type = 'CALL' THEN delta * total_volume ELSE 0 END) as call_delta_volume,
                    SUM(CASE WHEN option_type = 'CALL' THEN total_volume ELSE 0 END) as call_volume,
                    
                    -- Put metrics (use ABS(delta) for puts since delta is negative)
                    SUM(CASE WHEN option_type = 'PUT' THEN ABS(delta) * total_volume ELSE 0 END) as put_delta_volume,
                    SUM(CASE WHEN option_type = 'PUT' THEN total_volume ELSE 0 END) as put_volume,
                    
                    -- Derived metrics
                    (SUM(CASE WHEN option_type = 'CALL' THEN delta * total_volume ELSE 0 END) - 
                     SUM(CASE WHEN option_type = 'PUT' THEN ABS(delta) * total_volume ELSE 0 END)) as net_delta_volume
                    
                FROM options_data
                WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
                  AND delta IS NOT NULL AND total_volume IS NOT NULL AND total_volume > 0
                GROUP BY timestamp
                ORDER BY timestamp
            """, (symbol, start_timestamp, end_timestamp))
            
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                result = dict(row)
                
                # Calculate additional metrics
                call_dv = result['call_delta_volume'] or 0
                put_dv = result['put_delta_volume'] or 0
                
                result['delta_ratio'] = call_dv / put_dv if put_dv > 0 else float('inf')
                result['total_volume'] = (result['call_volume'] or 0) + (result['put_volume'] or 0)
                
                results.append(result)
            
            return results
    
    def get_symbol_stats(self, symbol: str) -> Dict[str, Any]:
        """
        Get statistics for a symbol's options data
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with symbol statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    MIN(timestamp) as earliest_timestamp,
                    MAX(timestamp) as latest_timestamp,
                    COUNT(DISTINCT expiration_date) as expiration_count,
                    COUNT(DISTINCT CASE WHEN option_type = 'CALL' THEN strike_price END) as call_strikes,
                    COUNT(DISTINCT CASE WHEN option_type = 'PUT' THEN strike_price END) as put_strikes,
                    AVG(underlying_price) as avg_underlying_price
                FROM options_data 
                WHERE symbol = ?
            """, (symbol,))
            
            result = dict(cursor.fetchone())
            
            # Convert timestamps to readable dates
            if result['earliest_timestamp']:
                result['earliest_date'] = datetime.fromtimestamp(result['earliest_timestamp'] / 1000).isoformat()
            if result['latest_timestamp']:
                result['latest_date'] = datetime.fromtimestamp(result['latest_timestamp'] / 1000).isoformat()
            
            return result
    
    def get_all_symbols(self) -> List[str]:
        """Get list of all symbols with options data"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT symbol FROM options_data ORDER BY symbol")
            return [row[0] for row in cursor.fetchall()]