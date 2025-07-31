import sqlite3
import logging
import time
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class OptionsDatabase:
    """
    Database manager for options data storage and retrieval.
    Handles comprehensive options chain data with full Greeks and pricing information.
    """
    
    def __init__(self, db_path: str, timeout: float = 30.0, max_retries: int = 3):
        """
        Initialize the options database
        
        Args:
            db_path: Path to the SQLite database file
            timeout: Connection timeout in seconds for lock conflicts
            max_retries: Maximum number of retry attempts for database operations
        """
        self.db_path = db_path
        self.timeout = timeout
        self.max_retries = max_retries
        self.init_database()
        logger.info(f"📊 Options database initialized: {db_path} (timeout: {timeout}s, retries: {max_retries})")
    
    @contextmanager
    def _get_connection(self, read_only: bool = False):
        """
        Get a database connection with proper timeout and configuration
        
        Args:
            read_only: If True, open connection in read-only mode for better concurrency
            
        Yields:
            sqlite3.Connection: Database connection with proper configuration
        """
        conn = None
        try:
            # Configure connection for better concurrency handling
            if read_only:
                # Read-only connections can have better concurrency
                conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", 
                                     uri=True, timeout=self.timeout)
            else:
                conn = sqlite3.connect(self.db_path, timeout=self.timeout)
            
            # Configure connection for better performance and reliability
            conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
            conn.execute("PRAGMA synchronous=NORMAL")  # Balance safety/performance
            conn.execute("PRAGMA temp_store=memory")  # Use memory for temp data
            conn.execute("PRAGMA cache_size=10000")  # Larger cache
            
            if read_only:
                conn.execute("PRAGMA query_only=1")  # Ensure read-only
            
            yield conn
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                logger.warning(f"Database lock detected: {e}")
                raise
            else:
                logger.error(f"Database operational error: {e}")
                raise
        finally:
            if conn:
                conn.close()
    
    def _execute_read(self, operation: Callable[[sqlite3.Connection], Any], 
                     operation_name: str = "read") -> Any:
        """
        Execute a read operation with retry logic and proper connection handling
        
        Args:
            operation: Function that takes a connection and returns a result
            operation_name: Name of the operation for logging
            
        Returns:
            Result from the operation
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                with self._get_connection(read_only=True) as conn:
                    return operation(conn)
                    
            except sqlite3.OperationalError as e:
                last_exception = e
                if "database is locked" in str(e).lower() and attempt < self.max_retries - 1:
                    retry_delay = 0.1 * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Database locked during {operation_name}, retrying in {retry_delay:.1f}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"Database error during {operation_name}: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error during {operation_name}: {e}")
                raise
        
        # If we get here, all retries failed
        logger.error(f"All {self.max_retries} attempts failed for {operation_name}")
        raise last_exception
    
    def _execute_write(self, operation: Callable[[sqlite3.Connection], Any], 
                      operation_name: str = "write") -> Any:
        """
        Execute a write operation with retry logic and proper transaction handling
        
        Args:
            operation: Function that takes a connection and returns a result
            operation_name: Name of the operation for logging
            
        Returns:
            Result from the operation
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                with self._get_connection(read_only=False) as conn:
                    # Start immediate transaction for write operations
                    conn.execute("BEGIN IMMEDIATE")
                    try:
                        result = operation(conn)
                        conn.commit()
                        return result
                    except Exception as e:
                        conn.rollback()
                        raise
                        
            except sqlite3.OperationalError as e:
                last_exception = e
                if "database is locked" in str(e).lower() and attempt < self.max_retries - 1:
                    retry_delay = 0.1 * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Database locked during {operation_name}, retrying in {retry_delay:.1f}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"Database error during {operation_name}: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error during {operation_name}: {e}")
                raise
        
        # If we get here, all retries failed
        logger.error(f"All {self.max_retries} attempts failed for {operation_name}")
        raise last_exception
    
    def init_database(self):
        """Create the options_data table with comprehensive schema"""
        def _create_schema(conn):
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
            
            # Create options flow aggregation table for fast chart data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS options_flow_agg (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    
                    -- Core identifiers
                    symbol TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    
                    -- Aggregated flow metrics (matching example script)
                    call_delta_volume REAL NOT NULL DEFAULT 0,
                    put_delta_volume REAL NOT NULL DEFAULT 0, 
                    net_delta_volume REAL NOT NULL DEFAULT 0,
                    delta_ratio REAL NOT NULL DEFAULT 0,
                    
                    -- Volume metrics
                    call_volume INTEGER NOT NULL DEFAULT 0,
                    put_volume INTEGER NOT NULL DEFAULT 0,
                    total_volume INTEGER NOT NULL DEFAULT 0,
                    
                    -- Open interest metrics
                    call_open_interest INTEGER NOT NULL DEFAULT 0,
                    put_open_interest INTEGER NOT NULL DEFAULT 0,
                    total_open_interest INTEGER NOT NULL DEFAULT 0,
                    
                    -- Put/Call ratios
                    put_call_ratio REAL NOT NULL DEFAULT 0,
                    put_call_oi_ratio REAL NOT NULL DEFAULT 0,
                    
                    -- Market context
                    underlying_price REAL,
                    
                    -- Sentiment analysis
                    sentiment TEXT,
                    sentiment_strength REAL NOT NULL DEFAULT 0,
                    
                    -- Metadata
                    total_records INTEGER NOT NULL DEFAULT 0,
                    collection_timestamp INTEGER,
                    
                    -- Ensure unique records per symbol per timestamp
                    UNIQUE(symbol, timestamp)
                )
            """)
            
            # Create indexes for fast chart queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_flow_agg_symbol_timestamp 
                ON options_flow_agg(symbol, timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_flow_agg_timestamp 
                ON options_flow_agg(timestamp)
            """)
            
            conn.commit()
            logger.info("✅ Options database schema created/verified")
            return True
        
        self._execute_write(_create_schema, "init_database")
    
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
        
        def _insert_records(conn):
            cursor = conn.cursor()
            inserted_count = 0
            duplicate_count = 0
            
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
            
            logger.info(f"📊 Options data inserted: {inserted_count} new, {duplicate_count} duplicates")
            return inserted_count, duplicate_count
        
        return self._execute_write(_insert_records, "insert_options_data")
    
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
        def _get_data(conn):
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
        
        return self._execute_read(_get_data, "get_options_data")
    
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
        def _get_flow_data(conn):
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
        
        return self._execute_read(_get_flow_data, "get_flow_summary")
    
    def get_symbol_stats(self, symbol: str) -> Dict[str, Any]:
        """
        Get statistics for a symbol's options data
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with symbol statistics
        """
        def _get_stats(conn):
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
        
        return self._execute_read(_get_stats, "get_symbol_stats")
    
    def get_all_symbols(self) -> List[str]:
        """Get list of all symbols with options data"""
        def _get_symbols(conn):
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT symbol FROM options_data ORDER BY symbol")
            return [row[0] for row in cursor.fetchall()]
        
        return self._execute_read(_get_symbols, "get_all_symbols")
    
    def insert_flow_aggregation(self, flow_data: Dict[str, Any]) -> bool:
        """
        Insert aggregated flow data for fast chart retrieval
        
        Args:
            flow_data: Dictionary with aggregated flow metrics
            
        Returns:
            True if successful, False otherwise
        """
        def _insert_flow_agg(conn):
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO options_flow_agg (
                    symbol, timestamp, call_delta_volume, put_delta_volume, net_delta_volume,
                    delta_ratio, call_volume, put_volume, total_volume,
                    call_open_interest, put_open_interest, total_open_interest,
                    put_call_ratio, put_call_oi_ratio, underlying_price,
                    sentiment, sentiment_strength, total_records, collection_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                flow_data.get('symbol'),
                flow_data.get('timestamp'),
                flow_data.get('call_delta_volume', 0),
                flow_data.get('put_delta_volume', 0),
                flow_data.get('net_delta_volume', 0),
                flow_data.get('delta_ratio', 0),
                flow_data.get('call_volume', 0),
                flow_data.get('put_volume', 0),
                flow_data.get('total_volume', 0),
                flow_data.get('call_open_interest', 0),
                flow_data.get('put_open_interest', 0),
                flow_data.get('total_open_interest', 0),
                flow_data.get('put_call_ratio', 0),
                flow_data.get('put_call_oi_ratio', 0),
                flow_data.get('underlying_price'),
                flow_data.get('sentiment'),
                flow_data.get('sentiment_strength', 0),
                flow_data.get('total_records', 0),
                flow_data.get('collection_timestamp')
            ))
            
            return True
        
        try:
            return self._execute_write(_insert_flow_agg, "insert_flow_aggregation")
        except Exception as e:
            logger.error(f"Error inserting flow aggregation: {e}")
            return False
    
    def get_flow_aggregations(self, symbol: str, start_timestamp: int, end_timestamp: int,
                             limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve pre-aggregated flow data for fast chart display
        
        Args:
            symbol: Stock symbol
            start_timestamp: Start time (Unix timestamp)
            end_timestamp: End time (Unix timestamp)  
            limit: Optional limit on number of records
            
        Returns:
            List of aggregated flow records
        """
        def _get_flow_agg(conn):
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM options_flow_agg
                WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
            """
            params = [symbol, start_timestamp, end_timestamp]
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
        
        return self._execute_read(_get_flow_agg, "get_flow_aggregations")
    
