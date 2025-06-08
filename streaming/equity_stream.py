# streaming/equity_stream.py - Equity-specific streaming abstraction
import logging
import time
from typing import Dict, Any, Optional, Callable, List

logger = logging.getLogger(__name__)

class EquityStreamProcessor:
    """
    Equity-specific streaming processor that handles:
    - Equity field mapping and validation
    - Market hours awareness  
    - Equity subscription formatting
    - Real-time equity data processing
    """
    
    # Schwab equity field mappings
    EQUITY_FIELDS = {
        "symbol": "key",           # Symbol identifier
        "bid_price": "1",          # Field 1: Bid Price
        "ask_price": "2",          # Field 2: Ask Price  
        "last_price": "3",         # Field 3: Last Price
        "bid_size": "4",           # Field 4: Bid Size
        "ask_size": "5",           # Field 5: Ask Size
        "volume": "8",             # Field 8: Total Volume
        "high_price": "10",        # Field 10: High Price
        "low_price": "11",         # Field 11: Low Price
        "net_change": "18",        # Field 18: Net Change
        "net_change_percent": "42" # Field 42: Net Percent Change
    }
    
    def __init__(self):
        self.is_mock_mode = False
        
    def set_mock_mode(self, is_mock: bool):
        """Set whether this processor is handling mock or real data"""
        self.is_mock_mode = is_mock
        
    def validate_symbol(self, symbol: str) -> bool:
        """Validate equity symbol format (1-5 uppercase letters)"""
        if not symbol or not isinstance(symbol, str):
            return False
        symbol = symbol.strip().upper()
        return len(symbol) >= 1 and len(symbol) <= 5 and symbol.isalpha()
    
    def format_subscription_message(self, symbols: List[str], fields: str = "0,1,2,3,4,5,8,10,11,12,17,18,42") -> str:
        """
        Format Schwab subscription message for equity level one data
        
        Args:
            symbols: List of equity symbols to subscribe to
            fields: Comma-separated field numbers to request
            
        Returns:
            Formatted subscription message for Schwab WebSocket
        """
        # Validate and clean symbols
        valid_symbols = [s.upper().strip() for s in symbols if self.validate_symbol(s)]
        
        if not valid_symbols:
            raise ValueError("No valid equity symbols provided")
            
        symbols_str = ",".join(valid_symbols)
        
        # Schwab level one equity subscription format
        subscription = {
            "requests": [{
                "service": "LEVELONE_EQUITIES",
                "requestid": "1", 
                "command": "SUBS",
                "account": "",
                "source": "",
                "parameters": {
                    "keys": symbols_str,
                    "fields": fields
                }
            }]
        }
        
        import json
        return json.dumps(subscription)
    
    def process_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process equity streaming message and extract standardized data
        
        Args:
            message_data: Raw message data from Schwab WebSocket
            
        Returns:
            Standardized equity data dict or None if not processable
        """
        try:
            if not message_data.get("data"):
                return None
                
            for data_item in message_data["data"]:
                if data_item.get("service") == "LEVELONE_EQUITIES":
                    return self._process_equity_data(data_item)
                    
            return None
            
        except Exception as e:
            logger.error(f"Error processing equity message: {e}")
            return None
    
    def _process_equity_data(self, data_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process individual equity data item"""
        try:
            timestamp = data_item.get("timestamp", int(time.time() * 1000))
            
            if not data_item.get("content"):
                return None
                
            for content in data_item["content"]:
                symbol = content.get("key")
                
                if not symbol or not self.validate_symbol(symbol):
                    logger.warning(f"Invalid equity symbol in stream: {symbol}")
                    continue
                    
                # Extract and validate equity data
                equity_data = self._extract_equity_fields(symbol, content, timestamp)
                
                if equity_data and self._validate_equity_data(equity_data):
                    return equity_data
                    
            return None
            
        except Exception as e:
            logger.error(f"Error processing equity data item: {e}")
            return None
    
    def _extract_equity_fields(self, symbol: str, content: Dict[str, Any], timestamp: int) -> Dict[str, Any]:
        """Extract equity fields from Schwab content using field mappings"""
        return {
            'symbol': symbol,
            'last_price': self._safe_float(content.get(self.EQUITY_FIELDS["last_price"])),
            'bid_price': self._safe_float(content.get(self.EQUITY_FIELDS["bid_price"])),
            'ask_price': self._safe_float(content.get(self.EQUITY_FIELDS["ask_price"])),
            'volume': self._safe_int(content.get(self.EQUITY_FIELDS["volume"])),
            'high_price': self._safe_float(content.get(self.EQUITY_FIELDS["high_price"])),
            'low_price': self._safe_float(content.get(self.EQUITY_FIELDS["low_price"])),
            'net_change': self._safe_float(content.get(self.EQUITY_FIELDS["net_change"])),
            'net_change_percent': self._safe_float(content.get(self.EQUITY_FIELDS["net_change_percent"])),
            'timestamp': timestamp,
            'data_source': 'MOCK' if self.is_mock_mode else 'SCHWAB_API',
            'asset_type': 'EQUITY'
        }
    
    def _validate_equity_data(self, equity_data: Dict[str, Any]) -> bool:
        """Validate equity data for basic sanity checks"""
        try:
            # Check for required fields
            if not equity_data.get('symbol'):
                return False
                
            # Basic price validation
            last_price = equity_data.get('last_price')
            if last_price is not None and last_price <= 0:
                logger.warning(f"Invalid last price for {equity_data['symbol']}: {last_price}")
                return False
                
            # Volume validation
            volume = equity_data.get('volume')
            if volume is not None and volume < 0:
                logger.warning(f"Invalid volume for {equity_data['symbol']}: {volume}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating equity data: {e}")
            return False
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float"""
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_int(self, value) -> Optional[int]:
        """Safely convert value to int"""
        if value is None or value == "":
            return None
        try:
            return int(float(value))  # Convert through float to handle "123.0"
        except (ValueError, TypeError):
            return None
    
    def get_market_status(self) -> Dict[str, Any]:
        """Get current equity market status and hours"""
        # This could be enhanced with actual market hours logic
        import datetime
        
        now = datetime.datetime.now()
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        is_market_hours = market_open <= now <= market_close and now.weekday() < 5
        
        return {
            'is_market_hours': is_market_hours,
            'market_open': market_open.isoformat(),
            'market_close': market_close.isoformat(),
            'current_time': now.isoformat(),
            'asset_type': 'EQUITY'
        }