import logging
from datetime import datetime, time as dt_time
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

class DataValidator:
    def __init__(self):
        # Standard market hours (Eastern Time)
        self.market_open = dt_time(9, 30)  # 9:30 AM
        self.market_close = dt_time(16, 0)  # 4:00 PM
    
    def validate_ohlc_candle(self, candle: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a single OHLC candle for data quality
        
        Args:
            candle: Dictionary containing OHLC data
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required fields
        required_fields = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        for field in required_fields:
            if field not in candle:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return False, errors
        
        try:
            # Extract values
            timestamp = candle['datetime']
            open_price = float(candle['open'])
            high_price = float(candle['high'])
            low_price = float(candle['low'])
            close_price = float(candle['close'])
            volume = int(candle['volume'])
            
            # Validate timestamp
            if not isinstance(timestamp, (int, float)) or timestamp <= 0:
                errors.append("Invalid timestamp")
            
            # Validate prices are positive
            prices = [open_price, high_price, low_price, close_price]
            if any(price <= 0 for price in prices):
                errors.append("Prices must be positive")
            
            # Validate OHLC relationships
            if high_price < max(open_price, close_price):
                errors.append(f"High ({high_price}) must be >= max(open, close)")
            
            if low_price > min(open_price, close_price):
                errors.append(f"Low ({low_price}) must be <= min(open, close)")
            
            if high_price < low_price:
                errors.append(f"High ({high_price}) must be >= Low ({low_price})")
            
            # Validate volume
            if volume < 0:
                errors.append("Volume cannot be negative")
            
            # Check for unrealistic price movements (> 50% in one minute)
            max_price_change = 0.5  # 50%
            price_change = abs(close_price - open_price) / open_price
            if price_change > max_price_change:
                errors.append(f"Unrealistic price change: {price_change:.2%}")
                
        except (ValueError, TypeError) as e:
            errors.append(f"Data type error: {e}")
        
        return len(errors) == 0, errors
    
    def validate_candle_batch(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate a batch of candles and return summary statistics
        
        Args:
            candles: List of OHLC candle dictionaries
        
        Returns:
            Dictionary with validation results and statistics
        """
        if not candles:
            return {
                'total_candles': 0,
                'valid_candles': 0,
                'invalid_candles': 0,
                'error_summary': {},
                'validation_rate': 0.0
            }
        
        valid_count = 0
        invalid_count = 0
        all_errors = []
        
        for i, candle in enumerate(candles):
            is_valid, errors = self.validate_ohlc_candle(candle)
            
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                all_errors.extend([f"Candle {i}: {error}" for error in errors])
        
        # Summarize error types
        error_summary = {}
        for error in all_errors:
            error_type = error.split(':')[1].strip() if ':' in error else error
            error_summary[error_type] = error_summary.get(error_type, 0) + 1
        
        validation_rate = valid_count / len(candles) if candles else 0.0
        
        return {
            'total_candles': len(candles),
            'valid_candles': valid_count,
            'invalid_candles': invalid_count,
            'error_summary': error_summary,
            'validation_rate': validation_rate,
            'all_errors': all_errors if invalid_count > 0 else []
        }
    
    def is_market_hours(self, timestamp: int) -> bool:
        """
        Check if timestamp falls within standard market hours (ET)
        
        Args:
            timestamp: Unix timestamp
        
        Returns:
            True if within market hours
        """
        try:
            dt = datetime.fromtimestamp(timestamp)
            # Convert to market time (assume Eastern Time for simplicity)
            time_of_day = dt.time()
            
            # Check if it's a weekday (Monday=0, Sunday=6)
            if dt.weekday() >= 5:  # Saturday or Sunday
                return False
            
            # Check if within market hours
            return self.market_open <= time_of_day <= self.market_close
            
        except (ValueError, OSError):
            return False
    
    def filter_market_hours_only(self, candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter candles to only include those during market hours
        
        Args:
            candles: List of OHLC candle dictionaries
        
        Returns:
            Filtered list of candles
        """
        filtered_candles = []
        
        for candle in candles:
            if 'datetime' in candle and self.is_market_hours(candle['datetime']):
                filtered_candles.append(candle)
        
        logger.info(f"Filtered {len(candles)} candles to {len(filtered_candles)} market hours only")
        return filtered_candles
    
    def detect_duplicates(self, candles: List[Dict[str, Any]]) -> List[int]:
        """
        Detect duplicate timestamps in candle data
        
        Args:
            candles: List of OHLC candle dictionaries
        
        Returns:
            List of indices of duplicate candles
        """
        seen_timestamps = set()
        duplicate_indices = []
        
        for i, candle in enumerate(candles):
            if 'datetime' in candle:
                timestamp = candle['datetime']
                if timestamp in seen_timestamps:
                    duplicate_indices.append(i)
                else:
                    seen_timestamps.add(timestamp)
        
        return duplicate_indices
    
    def remove_duplicates(self, candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate candles based on timestamp
        
        Args:
            candles: List of OHLC candle dictionaries
        
        Returns:
            List of candles with duplicates removed
        """
        seen_timestamps = set()
        unique_candles = []
        
        for candle in candles:
            if 'datetime' in candle:
                timestamp = candle['datetime']
                if timestamp not in seen_timestamps:
                    unique_candles.append(candle)
                    seen_timestamps.add(timestamp)
        
        duplicates_removed = len(candles) - len(unique_candles)
        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate candles")
        
        return unique_candles
    
    def get_data_quality_report(self, candles: List[Dict[str, Any]], symbol: str) -> Dict[str, Any]:
        """
        Generate comprehensive data quality report
        
        Args:
            candles: List of OHLC candle dictionaries
            symbol: Stock symbol for reporting
        
        Returns:
            Comprehensive data quality report
        """
        if not candles:
            return {
                'symbol': symbol,
                'total_candles': 0,
                'quality_score': 0.0,
                'issues': ['No data available']
            }
        
        # Basic validation
        validation_results = self.validate_candle_batch(candles)
        
        # Check for duplicates
        duplicate_indices = self.detect_duplicates(candles)
        
        # Check market hours coverage
        market_hours_count = len(self.filter_market_hours_only(candles))
        
        # Calculate quality score (0-100)
        quality_factors = {
            'validation_rate': validation_results['validation_rate'] * 40,  # 40% weight
            'duplicate_rate': (1 - len(duplicate_indices) / len(candles)) * 30,  # 30% weight
            'market_hours_coverage': (market_hours_count / len(candles)) * 30  # 30% weight
        }
        
        quality_score = sum(quality_factors.values())
        
        # Identify issues
        issues = []
        if validation_results['validation_rate'] < 0.95:
            issues.append(f"Low validation rate: {validation_results['validation_rate']:.1%}")
        
        if duplicate_indices:
            issues.append(f"{len(duplicate_indices)} duplicate timestamps found")
        
        if market_hours_count < len(candles) * 0.8:
            issues.append("Significant non-market hours data present")
        
        return {
            'symbol': symbol,
            'total_candles': len(candles),
            'valid_candles': validation_results['valid_candles'],
            'invalid_candles': validation_results['invalid_candles'],
            'duplicate_count': len(duplicate_indices),
            'market_hours_count': market_hours_count,
            'quality_score': round(quality_score, 1),
            'quality_factors': quality_factors,
            'issues': issues,
            'error_summary': validation_results['error_summary']
        }