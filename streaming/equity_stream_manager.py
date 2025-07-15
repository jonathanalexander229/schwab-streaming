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
            # Send unsubscribe message to streamer
            try:
                if hasattr(self.streamer, 'add_symbol'):
                    # Mock streamer - no special handling needed
                    pass
                else:
                    # Real Schwab streamer - send UNSUBS command
                    self.streamer.send(self.streamer.level_one_equities(symbol, "0,1,2,3,4,5,6,8,10,11,12,17,18,42", command="UNSUBS"))
                    logger.info(f"Sent equity unsubscription for {symbol}")
            except Exception as e:
                logger.error(f"Error unsubscribing from equity {symbol}: {e}")
                
            logger.info(f"Removed equity subscription for {symbol}")
            
        return success
        
    def validate_symbol(self, symbol: str) -> bool:
        """Validate equity symbol format"""
        return self.equity_processor.validate_symbol(symbol)
        
    def get_market_status(self) -> Dict[str, Any]:
        """Get current equity market status"""
        return self.equity_processor.get_market_status()
    
    def clear_and_resubscribe_all(self) -> bool:
        """Clear all existing subscriptions and resubscribe to watchlist"""
        try:
            if hasattr(self.streamer, 'add_symbol'):
                # Mock streamer - just clear and resubscribe
                logger.info("Mock mode - clearing and resubscribing all symbols")
                subscribed_symbols = list(self.get_subscriptions())
                self.clear_subscriptions()
                for symbol in subscribed_symbols:
                    self.add_equity_subscription(symbol)
            else:
                # Real Schwab streamer - send VIEW command to clear all subscriptions
                logger.info("Clearing all existing subscriptions...")
                self.streamer.send(self.streamer.level_one_equities("", "", command="VIEW"))
                
                # Get subscribed symbols before clearing
                subscribed_symbols = list(self.get_subscriptions())
                self.clear_subscriptions()
                
                # Subscribe to all symbols at once using comma-separated string
                if subscribed_symbols:
                    symbols_str = ",".join(subscribed_symbols)
                    logger.info(f"Subscribing to all symbols at once: {symbols_str}")
                    self.streamer.send(self.streamer.level_one_equities(symbols_str, "0,1,2,3,4,5,6,8,10,11,12,17,18,42"))
                    
                    # Add all symbols back to subscription manager
                    for symbol in subscribed_symbols:
                        self.add_subscription(symbol)
                    
                    logger.info(f"Subscribed to {len(subscribed_symbols)} symbols in single request")
                
            return True
            
        except Exception as e:
            logger.error(f"Error clearing and resubscribing: {e}")
            return False
        
    def _process_equity_message(self, message_data: Dict[str, Any]):
        """Process incoming message through equity processor"""
        try:
            # Use equity processor to extract standardized data
            equity_data_list = self.equity_processor.process_message(message_data)
            
            if equity_data_list and self.equity_data_handler:
                # Pass each processed equity data item to the handler
                for equity_data in equity_data_list:
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
                self.streamer.send(self.streamer.level_one_equities(symbol, "0,1,2,3,4,5,6,8,10,11,12,17,18,42"))
                logger.info(f"Sent equity subscription for {symbol}")
                
        except Exception as e:
            logger.error(f"Error subscribing to equity {symbol}: {e}")