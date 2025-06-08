# streaming/equity_stream_manager.py - Equity-specific stream manager
import logging
import time
from typing import Optional, Callable, Dict, Any, List
from .stream_manager import StreamManager
from .equity_stream import EquityStreamProcessor

logger = logging.getLogger(__name__)

class EquityStreamManager(StreamManager):
    """
    Equity-specific stream manager that extends the generic StreamManager
    with equity processing capabilities.
    """
    
    def __init__(self):
        super().__init__()
        self.equity_processor = EquityStreamProcessor()
        self.equity_data_handler: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # Override the message handler to use equity processing
        super().set_message_handler(self._process_equity_message)
        
    def set_dependencies(self, streamer, socketio, is_mock_mode: bool = False):
        """Inject dependencies and configure for equity streaming"""
        super().set_dependencies(streamer, socketio)
        self.equity_processor.set_mock_mode(is_mock_mode)
        
    def set_equity_data_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """Set handler for processed equity data"""
        self.equity_data_handler = handler
        
    def add_equity_subscription(self, symbol: str) -> bool:
        """
        Add equity symbol subscription with validation
        
        Args:
            symbol: Equity symbol to subscribe to
            
        Returns:
            True if subscription was successful
        """
        # Validate symbol format
        if not self.equity_processor.validate_symbol(symbol):
            logger.error(f"Invalid equity symbol format: {symbol}")
            return False
            
        symbol = symbol.upper().strip()
        
        # Add to subscription manager
        success = self.add_subscription(symbol)
        
        if success:
            # Send equity-specific subscription message
            self._subscribe_to_equity(symbol)
            logger.info(f"Added equity subscription for {symbol}")
            
        return success
        
    def remove_equity_subscription(self, symbol: str) -> bool:
        """Remove equity symbol subscription"""
        symbol = symbol.upper().strip()
        success = self.remove_subscription(symbol)
        
        if success:
            logger.info(f"Removed equity subscription for {symbol}")
            
        return success
        
    def validate_symbol(self, symbol: str) -> bool:
        """Validate equity symbol format"""
        return self.equity_processor.validate_symbol(symbol)
        
    def get_market_status(self) -> Dict[str, Any]:
        """Get current equity market status"""
        return self.equity_processor.get_market_status()
        
    def _process_equity_message(self, message_data: Dict[str, Any]):
        """Process incoming message through equity processor"""
        try:
            # Use equity processor to extract standardized data
            equity_data = self.equity_processor.process_message(message_data)
            
            if equity_data and self.equity_data_handler:
                # Pass processed equity data to the handler
                self.equity_data_handler(equity_data)
                
        except Exception as e:
            logger.error(f"Error processing equity message: {e}")
            
    def _subscribe_to_equity(self, symbol: str):
        """Send equity-specific subscription to streamer"""
        try:
            if hasattr(self.streamer, 'add_symbol'):
                # Mock streamer method
                self.streamer.add_symbol(symbol)
                logger.info(f"Added {symbol} to mock equity stream")
            else:
                # Real Schwab streamer - send level one equity subscription
                subscription_msg = self.equity_processor.format_subscription_message([symbol])
                self.streamer.send(subscription_msg)
                logger.info(f"Sent equity subscription for {symbol}")
                
        except Exception as e:
            logger.error(f"Error subscribing to equity {symbol}: {e}")